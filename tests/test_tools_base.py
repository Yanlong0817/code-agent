"""工具基类测试。"""

from typing import Any, ClassVar

import pytest
from pydantic import BaseModel, Field

from code_agent.tools.base import BaseTool, ToolRegistry


class MockTool(BaseTool):
    """用于测试的模拟工具。"""

    name: ClassVar[str] = "MockTool"
    description: ClassVar[str] = "一个用于测试的模拟工具"

    class Input(BaseModel):
        message: str = Field(description="要处理的消息")
        count: int = Field(default=1, description="重复次数")

    async def execute(self, message: str, count: int = 1) -> str:
        return message * count


class AnotherMockTool(BaseTool):
    """另一个用于测试的模拟工具。"""

    name: ClassVar[str] = "AnotherMockTool"
    description: ClassVar[str] = "另一个模拟工具"

    class Input(BaseModel):
        value: int = Field(description="要处理的值")

    async def execute(self, value: int) -> int:
        return value * 2


class TestBaseTool:
    """BaseTool 类测试。"""

    @pytest.fixture
    def tool(self) -> MockTool:
        return MockTool()

    async def test_execute(self, tool: MockTool) -> None:
        """测试 execute 方法。"""
        result = await tool.execute("hello", count=3)
        assert result == "hellohellohello"

    async def test_call(self, tool: MockTool) -> None:
        """测试 __call__ 方法（带验证）。"""
        result = await tool(message="test", count=2)
        assert result == "testtest"

    async def test_call_with_defaults(self, tool: MockTool) -> None:
        """测试 __call__ 使用默认参数。"""
        result = await tool(message="x")
        assert result == "x"

    def test_get_schema(self) -> None:
        """测试 schema 生成。"""
        schema = MockTool.get_schema()

        assert schema["name"] == "MockTool"
        assert schema["description"] == "一个用于测试的模拟工具"
        assert "input_schema" in schema
        assert "properties" in schema["input_schema"]
        assert "message" in schema["input_schema"]["properties"]
        assert "count" in schema["input_schema"]["properties"]

    def test_schema_no_title(self) -> None:
        """测试 schema 不包含 title。"""
        schema = MockTool.get_schema()
        assert "title" not in schema["input_schema"]


class TestToolRegistry:
    """ToolRegistry 类测试。"""

    @pytest.fixture
    def registry(self) -> ToolRegistry:
        return ToolRegistry()

    def test_register(self, registry: ToolRegistry) -> None:
        """测试注册工具。"""
        tool = MockTool()
        registry.register(tool)

        assert registry.get("MockTool") is tool

    def test_register_class(self, registry: ToolRegistry) -> None:
        """测试通过类注册工具。"""
        registry.register_class(MockTool)

        tool = registry.get("MockTool")
        assert tool is not None
        assert isinstance(tool, MockTool)

    def test_get_nonexistent(self, registry: ToolRegistry) -> None:
        """测试获取不存在的工具。"""
        assert registry.get("NonExistent") is None

    def test_get_all(self, registry: ToolRegistry) -> None:
        """测试获取所有工具。"""
        registry.register(MockTool())
        registry.register(AnotherMockTool())

        tools = registry.get_all()
        assert len(tools) == 2

    def test_get_schemas(self, registry: ToolRegistry) -> None:
        """测试获取所有工具的 schema。"""
        registry.register(MockTool())
        registry.register(AnotherMockTool())

        schemas = registry.get_schemas()
        assert len(schemas) == 2

        names = {s["name"] for s in schemas}
        assert names == {"MockTool", "AnotherMockTool"}

    async def test_execute(self, registry: ToolRegistry) -> None:
        """测试通过 registry 执行工具。"""
        registry.register(MockTool())

        result = await registry.execute("MockTool", message="abc", count=2)
        assert result == "abcabc"

    async def test_execute_nonexistent(self, registry: ToolRegistry) -> None:
        """测试执行不存在的工具。"""
        with pytest.raises(ValueError, match="工具未找到"):
            await registry.execute("NonExistent")
