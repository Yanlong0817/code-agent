"""CLI 主入口相关测试。"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from code_agent import __main__ as main_module
from code_agent.session import SessionManager


def _patch_session_manager(monkeypatch: pytest.MonkeyPatch, tmp_path) -> SessionManager:
    """将 main 模块中的 SessionManager 重定向到临时目录。"""
    sessions_dir = tmp_path / "sessions"

    class TestSessionManager(SessionManager):
        def __init__(self) -> None:
            super().__init__(sessions_dir=sessions_dir)

    monkeypatch.setattr(main_module, "SessionManager", TestSessionManager)
    return SessionManager(sessions_dir=sessions_dir)


def test_generate_session_title() -> None:
    """测试从用户消息生成标题。"""
    messages = [
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "这是第一条用户消息\n第二行"},
    ]
    assert main_module._generate_session_title(messages) == "这是第一条用户消息 第二行"


def test_auto_save_skips_when_no_messages(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """测试没有消息时不会自动保存。"""
    manager = _patch_session_manager(monkeypatch, tmp_path)

    agent = SimpleNamespace(
        messages=[],
        _current_session=None,
        config=SimpleNamespace(model="claude-sonnet-4-20250514"),
    )
    console = MagicMock()

    main_module._auto_save_session(agent, console)

    assert manager.list_sessions() == []


def test_auto_save_creates_new_session(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """测试自动保存会创建新会话。"""
    manager = _patch_session_manager(monkeypatch, tmp_path)

    agent = SimpleNamespace(
        messages=[{"role": "user", "content": "帮我看一下这个项目"}],
        _current_session=None,
        config=SimpleNamespace(model="claude-sonnet-4-20250514"),
    )
    console = MagicMock()

    main_module._auto_save_session(agent, console)

    sessions = manager.list_sessions()
    assert len(sessions) == 1
    loaded = manager.load(sessions[0].id)
    assert loaded.messages == agent.messages
    assert loaded.metadata.title == "帮我看一下这个项目"
    assert agent._current_session is not None


def test_auto_save_updates_existing_session(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """测试自动保存会更新已有会话。"""
    manager = _patch_session_manager(monkeypatch, tmp_path)
    session = manager.create(model="claude-sonnet-4-20250514", title="")

    agent = SimpleNamespace(
        messages=[{"role": "user", "content": "更新会话内容"}],
        _current_session=session,
        config=SimpleNamespace(model="claude-sonnet-4-20250514"),
    )
    console = MagicMock()

    main_module._auto_save_session(agent, console)

    loaded = manager.load(session.metadata.id)
    assert loaded.messages == agent.messages
    assert loaded.metadata.title == "更新会话内容"


def test_main_converts_log_file_to_path(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """测试 main 会将 --log-file 参数转换为 Path。"""

    class DummyAgent:
        def __init__(self, config) -> None:
            self.config = config
            self.messages = []
            self._current_session = None

        async def run(self, user_input: str) -> str:
            return user_input

    fake_config = SimpleNamespace(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        max_iterations=50,
        verbose=False,
        log_level="INFO",
        log_file=tmp_path / "default.log",
        working_directory=tmp_path,
        validate_required=lambda: None,
    )
    log_file_arg = tmp_path / "cli.log"
    args = SimpleNamespace(
        prompt=["hello"],
        model=None,
        load=None,
        continue_session=False,
        max_tokens=None,
        max_iterations=None,
        verbose=False,
        no_banner=True,
        log_level=None,
        log_file=str(log_file_arg),
        working_dir=None,
    )

    captured: dict[str, object] = {}

    monkeypatch.setattr(main_module, "parse_args", lambda: args)
    monkeypatch.setattr(main_module.Config, "from_env", staticmethod(lambda: fake_config))
    monkeypatch.setattr(main_module, "CodeAgent", DummyAgent)
    monkeypatch.setattr(
        main_module,
        "setup_logging",
        lambda level, log_file: captured.update({"level": level, "log_file": log_file}),
    )

    main_module.main()

    assert fake_config.log_file == Path(log_file_arg)
    assert isinstance(captured["log_file"], Path)
