"""命令模块测试。"""

from pathlib import Path
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest

from code_agent.commands.base import BaseCommand, CommandRegistry
from code_agent.commands.handler import CommandHandler
from code_agent.commands.model import AVAILABLE_MODELS, ModelCommand
from code_agent.commands.tools import ToolsCommand


class MockCommand(BaseCommand):
    """用于测试的模拟命令。"""

    name: ClassVar[str] = "mock"
    description: ClassVar[str] = "模拟命令"

    async def execute(self, args: str) -> None:
        self.agent.console.print(f"Mock executed with: {args}")


class AnotherMockCommand(BaseCommand):
    """另一个模拟命令。"""

    name: ClassVar[str] = "another"
    description: ClassVar[str] = "另一个模拟命令"

    async def execute(self, args: str) -> None:
        pass


class TestCommandRegistry:
    """CommandRegistry 测试。"""

    @pytest.fixture
    def registry(self) -> CommandRegistry:
        return CommandRegistry()

    def test_register(self, registry: CommandRegistry) -> None:
        """测试注册命令。"""
        registry.register(MockCommand)
        assert registry.get("mock") is MockCommand

    def test_get_nonexistent(self, registry: CommandRegistry) -> None:
        """测试获取不存在的命令。"""
        assert registry.get("nonexistent") is None

    def test_get_all_names(self, registry: CommandRegistry) -> None:
        """测试获取所有命令名称。"""
        registry.register(MockCommand)
        registry.register(AnotherMockCommand)

        names = registry.get_all_names()
        assert set(names) == {"mock", "another"}

    def test_get_completions(self, registry: CommandRegistry) -> None:
        """测试命令补全。"""
        registry.register(MockCommand)
        registry.register(AnotherMockCommand)

        # 完全匹配
        assert registry.get_completions("mock") == ["mock"]
        # 前缀匹配
        assert registry.get_completions("m") == ["mock"]
        # 无匹配
        assert registry.get_completions("xyz") == []
        # 空前缀匹配所有
        assert set(registry.get_completions("")) == {"mock", "another"}

    def test_get_help(self, registry: CommandRegistry) -> None:
        """测试获取帮助信息。"""
        registry.register(MockCommand)

        help_panel = registry.get_help()
        # get_help 现在返回 Panel 对象
        from rich.panel import Panel

        assert isinstance(help_panel, Panel)


class TestCommandHandler:
    """CommandHandler 测试。"""

    @pytest.fixture
    def mock_agent(self) -> MagicMock:
        """创建模拟 Agent。"""
        agent = MagicMock()
        agent.console = MagicMock()
        agent.config = MagicMock()
        agent.config.model = "gpt-4.1"
        agent.config.working_directory = Path.cwd()
        agent.run = AsyncMock(return_value="ok")
        return agent

    @pytest.fixture
    def handler(self, mock_agent: MagicMock) -> CommandHandler:
        return CommandHandler(mock_agent)

    def test_is_command(self, handler: CommandHandler) -> None:
        """测试命令检测。"""
        assert handler.is_command("/model") is True
        assert handler.is_command("/help") is True
        assert handler.is_command("  /test  ") is True
        assert handler.is_command("hello") is False
        assert handler.is_command("") is False

    def test_get_completions(self, handler: CommandHandler) -> None:
        """测试命令补全。"""
        completions = handler.get_completions("/m")
        assert "/model" in completions

        # 非命令输入
        assert handler.get_completions("hello") == []

    async def test_execute_unknown_command(
        self, handler: CommandHandler, mock_agent: MagicMock
    ) -> None:
        """测试执行未知命令。"""
        result = await handler.execute("/unknown")

        assert result is True
        # 应该显示错误信息
        mock_agent.console.print.assert_called()
        help_panel = mock_agent.console.print.call_args_list[1].args[0]
        from rich.panel import Panel

        assert isinstance(help_panel, Panel)

    async def test_execute_non_command(self, handler: CommandHandler) -> None:
        """测试执行非命令输入。"""
        result = await handler.execute("hello world")
        assert result is False

    async def test_execute_custom_command_from_toml(
        self, tmp_path: Path, mock_agent: MagicMock
    ) -> None:
        """测试从 TOML 加载并执行自定义命令。"""
        command_file = tmp_path / "commands.toml"
        command_file.write_text(
            """
[commands.explain]
description = "解释指定内容"
prompt = "请解释：{args}"
requires_args = true
            """.strip(),
            encoding="utf-8",
        )

        handler = CommandHandler(mock_agent, custom_command_paths=[command_file])
        completions = handler.get_completions("/exp")
        assert "/explain" in completions

        await handler.execute("/explain Python MRO")
        mock_agent.run.assert_awaited_once_with("请解释：Python MRO")

    async def test_custom_command_requires_args(
        self, tmp_path: Path, mock_agent: MagicMock
    ) -> None:
        """测试 requires_args 在无参数时阻止执行。"""
        command_file = tmp_path / "commands.toml"
        command_file.write_text(
            """
[commands.fix]
description = "修复问题"
prompt = "请修复：{args}"
requires_args = true
            """.strip(),
            encoding="utf-8",
        )

        handler = CommandHandler(mock_agent, custom_command_paths=[command_file])
        await handler.execute("/fix")

        mock_agent.run.assert_not_called()
        mock_agent.console.print.assert_called()

    async def test_project_command_overrides_global(
        self, tmp_path: Path, mock_agent: MagicMock
    ) -> None:
        """测试项目级配置可覆盖同名全局命令。"""
        global_file = tmp_path / "global.toml"
        project_file = tmp_path / "project.toml"

        global_file.write_text(
            """
[commands.review]
description = "全局审查"
prompt = "GLOBAL {args}"
            """.strip(),
            encoding="utf-8",
        )
        project_file.write_text(
            """
[commands.review]
description = "项目审查"
prompt = "PROJECT {args}"
            """.strip(),
            encoding="utf-8",
        )

        handler = CommandHandler(mock_agent, custom_command_paths=[global_file, project_file])
        await handler.execute("/review diff")

        mock_agent.run.assert_awaited_once_with("PROJECT diff")

    async def test_commands_reload_refreshes_custom_commands(
        self, tmp_path: Path, mock_agent: MagicMock
    ) -> None:
        """测试 /commands reload 会刷新自定义命令集合。"""
        command_file = tmp_path / "commands.toml"
        command_file.write_text(
            """
[commands.one]
description = "第一条命令"
prompt = "ONE"
            """.strip(),
            encoding="utf-8",
        )
        handler = CommandHandler(mock_agent, custom_command_paths=[command_file])
        assert "/one" in handler.get_completions("/o")

        command_file.write_text(
            """
[commands.two]
description = "第二条命令"
prompt = "TWO"
            """.strip(),
            encoding="utf-8",
        )

        await handler.execute("/commands reload")
        assert "/one" not in handler.get_completions("/o")
        assert "/two" in handler.get_completions("/t")

    async def test_commands_init_creates_project_template(
        self, tmp_path: Path, mock_agent: MagicMock
    ) -> None:
        """测试 /commands init 默认创建项目级模板。"""
        global_file = tmp_path / "global.toml"
        project_file = tmp_path / ".code_agent" / "commands.toml"

        handler = CommandHandler(
            mock_agent,
            custom_command_paths=[global_file, project_file],
        )

        await handler.execute("/commands init")
        assert project_file.exists()
        content = project_file.read_text(encoding="utf-8")
        assert "[commands.review]" in content
        assert "/review" in handler.get_completions("/r")

    async def test_commands_init_force_overwrites(
        self, tmp_path: Path, mock_agent: MagicMock
    ) -> None:
        """测试 /commands init --force 会覆盖已有模板文件。"""
        global_file = tmp_path / "global.toml"
        project_file = tmp_path / ".code_agent" / "commands.toml"
        project_file.parent.mkdir(parents=True, exist_ok=True)
        project_file.write_text(
            """
[commands.keep]
description = "保留"
prompt = "KEEP"
            """.strip(),
            encoding="utf-8",
        )

        handler = CommandHandler(
            mock_agent,
            custom_command_paths=[global_file, project_file],
        )

        await handler.execute("/commands init")
        assert "/keep" in handler.get_completions("/k")

        await handler.execute("/commands init --force")
        assert "/keep" not in handler.get_completions("/k")
        assert "/review" in handler.get_completions("/r")

    def test_custom_command_unknown_field_reports_warning(
        self, tmp_path: Path, mock_agent: MagicMock
    ) -> None:
        """测试未知字段会提示告警，但命令仍可加载。"""
        command_file = tmp_path / "commands.toml"
        command_file.write_text(
            """
[commands.review]
description = "审查"
prompt = "REVIEW"
extra = "unexpected"
            """.strip(),
            encoding="utf-8",
        )

        handler = CommandHandler(mock_agent, custom_command_paths=[command_file])
        assert "/review" in handler.get_completions("/r")
        errors = handler.get_custom_command_errors()
        assert any("未知字段" in message for message in errors)

    def test_custom_command_invalid_placeholder_is_rejected(
        self, tmp_path: Path, mock_agent: MagicMock
    ) -> None:
        """测试非法占位符会阻止命令加载。"""
        command_file = tmp_path / "commands.toml"
        command_file.write_text(
            """
[commands.bad]
description = "错误模板"
prompt = "topic={topic}"
            """.strip(),
            encoding="utf-8",
        )

        handler = CommandHandler(mock_agent, custom_command_paths=[command_file])
        assert "/bad" not in handler.get_completions("/b")
        errors = handler.get_custom_command_errors()
        assert any("{args}" in message for message in errors)


class TestModelCommand:
    """ModelCommand 测试。"""

    @pytest.fixture
    def mock_agent(self) -> MagicMock:
        """创建模拟 Agent。"""
        agent = MagicMock()
        agent.console = MagicMock()
        agent.config = MagicMock()
        agent.config.model = "gpt-4.1"
        agent.status_bar = MagicMock()
        return agent

    @pytest.fixture
    def command(self, mock_agent: MagicMock) -> ModelCommand:
        return ModelCommand(mock_agent)

    async def test_execute_with_valid_model(
        self, command: ModelCommand, mock_agent: MagicMock
    ) -> None:
        """测试直接指定有效模型。"""
        await command.execute("gpt-4.1-mini")

        assert mock_agent.config.model == "gpt-4.1-mini"
        mock_agent.status_bar.update_model.assert_called_once_with("gpt-4.1-mini")

    async def test_execute_with_invalid_model(
        self, command: ModelCommand, mock_agent: MagicMock
    ) -> None:
        """测试指定无效模型。"""
        original_model = mock_agent.config.model

        await command.execute("invalid-model")

        # 模型不应该改变
        assert mock_agent.config.model == original_model
        # 应该显示错误
        mock_agent.console.print.assert_called()

    async def test_execute_same_model(self, command: ModelCommand, mock_agent: MagicMock) -> None:
        """测试切换到相同模型。"""
        mock_agent.config.model = "gpt-4.1"

        await command.execute("gpt-4.1")

        # 应该显示未变更消息
        calls = mock_agent.console.print.call_args_list
        assert any("未变更" in str(call) for call in calls)

    def test_available_models(self) -> None:
        """测试可用模型列表。"""
        assert len(AVAILABLE_MODELS) > 0
        # 每个模型应该有 ID 和描述
        for model_id, description in AVAILABLE_MODELS:
            assert isinstance(model_id, str)
            assert isinstance(description, str)
            assert len(model_id) > 0
            assert len(description) > 0


class TestToolsCommand:
    """ToolsCommand 测试。"""

    def test_file_tools_category_mapping(self) -> None:
        """测试新增文件工具分类。"""
        command = ToolsCommand(MagicMock())

        assert command._get_tool_category("ApplyPatch", command.TOOL_CATEGORIES) == "文件操作"
        assert command._get_tool_category("Undo", command.TOOL_CATEGORIES) == "文件操作"
        assert command._get_tool_category("Insert", command.TOOL_CATEGORIES) == "文件操作"
        assert command._get_tool_category("ListDirectory", command.TOOL_CATEGORIES) == "文件操作"
        assert command._get_category_order("ApplyPatch")[0] == command.CATEGORY_ORDER["文件操作"]
