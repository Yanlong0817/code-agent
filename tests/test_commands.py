"""命令模块测试。"""

from typing import ClassVar
from unittest.mock import MagicMock

import pytest

from code_agent.commands.base import BaseCommand, CommandRegistry
from code_agent.commands.handler import CommandHandler
from code_agent.commands.model import AVAILABLE_MODELS, ModelCommand


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
        agent.config.model = "claude-sonnet-4-20250514"
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

    async def test_execute_non_command(self, handler: CommandHandler) -> None:
        """测试执行非命令输入。"""
        result = await handler.execute("hello world")
        assert result is False


class TestModelCommand:
    """ModelCommand 测试。"""

    @pytest.fixture
    def mock_agent(self) -> MagicMock:
        """创建模拟 Agent。"""
        agent = MagicMock()
        agent.console = MagicMock()
        agent.config = MagicMock()
        agent.config.model = "claude-sonnet-4-20250514"
        return agent

    @pytest.fixture
    def command(self, mock_agent: MagicMock) -> ModelCommand:
        return ModelCommand(mock_agent)

    async def test_execute_with_valid_model(
        self, command: ModelCommand, mock_agent: MagicMock
    ) -> None:
        """测试直接指定有效模型。"""
        await command.execute("claude-opus-4-5-20251101")

        assert mock_agent.config.model == "claude-opus-4-5-20251101"

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
        mock_agent.config.model = "claude-sonnet-4-20250514"

        await command.execute("claude-sonnet-4-20250514")

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
