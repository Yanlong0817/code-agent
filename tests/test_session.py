"""会话管理测试。"""

from datetime import datetime
from pathlib import Path

import pytest

from code_agent.session import Session, SessionManager, SessionMetadata


@pytest.fixture
def session_manager(tmp_path: Path) -> SessionManager:
    """创建临时会话管理器。"""
    return SessionManager(sessions_dir=tmp_path / "sessions")


@pytest.fixture
def sample_messages() -> list[dict]:
    """创建示例消息。"""
    return [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "I'm doing well!"},
                {"type": "tool_use", "id": "123", "name": "Read", "input": {}},
            ],
        },
    ]


class TestSessionMetadata:
    """SessionMetadata 测试类。"""

    def test_create_metadata(self) -> None:
        """测试创建元数据。"""
        now = datetime.now().isoformat()
        metadata = SessionMetadata(
            id="test_id",
            created_at=now,
            updated_at=now,
            model="gpt-4.1",
            message_count=5,
            title="Test Session",
        )

        assert metadata.id == "test_id"
        assert metadata.model == "gpt-4.1"
        assert metadata.message_count == 5
        assert metadata.title == "Test Session"

    def test_metadata_defaults(self) -> None:
        """测试元数据默认值。"""
        now = datetime.now().isoformat()
        metadata = SessionMetadata(
            id="test_id",
            created_at=now,
            updated_at=now,
            model="test-model",
        )

        assert metadata.message_count == 0
        assert metadata.title == ""


class TestSession:
    """Session 测试类。"""

    def test_create_session(self) -> None:
        """测试创建会话。"""
        now = datetime.now().isoformat()
        metadata = SessionMetadata(
            id="test_id",
            created_at=now,
            updated_at=now,
            model="test-model",
        )
        session = Session(metadata=metadata)

        assert session.metadata.id == "test_id"
        assert session.messages == []

    def test_session_with_messages(self, sample_messages: list[dict]) -> None:
        """测试带消息的会话。"""
        now = datetime.now().isoformat()
        metadata = SessionMetadata(
            id="test_id",
            created_at=now,
            updated_at=now,
            model="test-model",
        )
        session = Session(metadata=metadata, messages=sample_messages)

        assert len(session.messages) == 4
        assert session.messages[0]["role"] == "user"


class TestSessionManager:
    """SessionManager 测试类。"""

    def test_create_session(self, session_manager: SessionManager) -> None:
        """测试创建会话。"""
        session = session_manager.create(
            model="gpt-4.1",
            title="Test Session",
        )

        assert session.metadata.model == "gpt-4.1"
        assert session.metadata.title == "Test Session"
        assert session.messages == []
        assert session.metadata.id  # 应该有 ID

    def test_save_and_load(
        self, session_manager: SessionManager, sample_messages: list[dict]
    ) -> None:
        """测试保存和加载会话。"""
        # 创建并保存会话
        session = session_manager.create(model="test-model", title="Test")
        session.messages = sample_messages
        path = session_manager.save(session)

        assert path.exists()

        # 加载会话
        loaded = session_manager.load(session.metadata.id)

        assert loaded.metadata.id == session.metadata.id
        assert loaded.metadata.title == "Test"
        assert len(loaded.messages) == 4
        assert loaded.metadata.message_count == 4

    def test_load_nonexistent(self, session_manager: SessionManager) -> None:
        """测试加载不存在的会话。"""
        with pytest.raises(FileNotFoundError):
            session_manager.load("nonexistent_id")

    def test_load_from_path(self, session_manager: SessionManager, tmp_path: Path) -> None:
        """测试从路径加载会话。"""
        # 创建会话文件
        session = session_manager.create(model="test-model")
        session.messages = [{"role": "user", "content": "Test"}]
        path = session_manager.save(session)

        # 从路径加载
        loaded = session_manager.load_from_path(path)
        assert loaded.metadata.id == session.metadata.id

    def test_delete(self, session_manager: SessionManager, sample_messages: list[dict]) -> None:
        """测试删除会话。"""
        session = session_manager.create(model="test-model")
        session.messages = sample_messages
        session_manager.save(session)

        # 确认存在
        assert session_manager.load(session.metadata.id)

        # 删除
        result = session_manager.delete(session.metadata.id)
        assert result is True

        # 确认已删除
        with pytest.raises(FileNotFoundError):
            session_manager.load(session.metadata.id)

    def test_delete_nonexistent(self, session_manager: SessionManager) -> None:
        """测试删除不存在的会话。"""
        result = session_manager.delete("nonexistent_id")
        assert result is False

    def test_list_sessions(self, session_manager: SessionManager) -> None:
        """测试列出会话。"""
        # 创建多个会话
        for i in range(3):
            session = session_manager.create(model="test-model", title=f"Session {i}")
            session_manager.save(session)

        sessions = session_manager.list_sessions()

        assert len(sessions) == 3
        # 应该按更新时间倒序
        assert sessions[0].title == "Session 2"

    def test_list_sessions_limit(self, session_manager: SessionManager) -> None:
        """测试列出会话限制数量。"""
        for i in range(5):
            session = session_manager.create(model="test-model")
            session_manager.save(session)

        sessions = session_manager.list_sessions(limit=3)
        assert len(sessions) == 3

    def test_search(self, session_manager: SessionManager) -> None:
        """测试搜索会话。"""
        # 创建会话
        session1 = session_manager.create(model="test-model", title="Python Project")
        session1.messages = [{"role": "user", "content": "Help with Python"}]
        session_manager.save(session1)

        session2 = session_manager.create(model="test-model", title="JavaScript Project")
        session2.messages = [{"role": "user", "content": "Help with JavaScript"}]
        session_manager.save(session2)

        # 搜索标题
        results = session_manager.search("Python")
        assert len(results) == 1
        assert results[0].title == "Python Project"

        # 搜索内容
        results = session_manager.search("JavaScript")
        assert len(results) == 1

    def test_search_nested_message_content(self, session_manager: SessionManager) -> None:
        """测试搜索嵌套消息内容（assistant/tool 结构）。"""
        session = session_manager.create(model="test-model", title="Nested")
        session.messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "This mentions NestedKeyword"},
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "README.md"}},
                ],
            }
        ]
        session_manager.save(session)

        results = session_manager.search("nestedkeyword")
        assert len(results) == 1
        assert results[0].id == session.metadata.id

    def test_get_latest(self, session_manager: SessionManager) -> None:
        """测试获取最新会话。"""
        # 空时返回 None
        assert session_manager.get_latest() is None

        # 创建会话
        session = session_manager.create(model="test-model", title="Latest")
        session.messages = [{"role": "user", "content": "Test"}]
        session_manager.save(session)

        latest = session_manager.get_latest()
        assert latest is not None
        assert latest.metadata.title == "Latest"

    def test_sessions_dir_created(self, tmp_path: Path) -> None:
        """测试自动创建会话目录。"""
        sessions_dir = tmp_path / "new_sessions_dir"
        assert not sessions_dir.exists()

        SessionManager(sessions_dir=sessions_dir)
        assert sessions_dir.exists()
