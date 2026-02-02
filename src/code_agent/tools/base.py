"""Code Agent 工具基类和工具注册表。"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel


class BaseTool(ABC):
    """所有工具的抽象基类。

    每个工具必须定义：
    - name: Claude API 的工具名称
    - description: Claude API 的工具描述
    - Input: 用于输入验证的 Pydantic 模型
    - execute(): 执行工具的异步方法
    """

    name: ClassVar[str]
    description: ClassVar[str]

    class Input(BaseModel):
        """基础输入模型 - 在子类中重写。"""

        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """使用验证后的输入执行工具。

        Args:
            **kwargs: 与 Input 模型匹配的工具特定参数

        Returns:
            工具执行结果
        """
        pass

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        """从 Input 模型生成 Claude API 工具 schema。

        Returns:
            与 Claude API 兼容的工具 schema 字典
        """
        json_schema = cls.Input.model_json_schema()

        # 移除 Claude 不需要的 title 和 definitions
        json_schema.pop("title", None)
        json_schema.pop("$defs", None)

        return {
            "name": cls.name,
            "description": cls.description,
            "input_schema": json_schema,
        }

    async def __call__(self, **kwargs: Any) -> Any:
        """允许直接调用工具实例。

        验证输入并执行工具。
        """
        # 使用 Pydantic 模型验证输入
        validated = self.Input(**kwargs)
        return await self.execute(**validated.model_dump())


T = TypeVar("T", bound=BaseTool)


class ToolRegistry:
    """管理可用工具的注册表。"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册一个工具实例。"""
        self._tools[tool.name] = tool

    def register_class(self, tool_class: type[T]) -> None:
        """通过类注册工具（创建实例）。"""
        tool = tool_class()
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """按名称获取工具。"""
        return self._tools.get(name)

    def get_all(self) -> list[BaseTool]:
        """获取所有已注册的工具。"""
        return list(self._tools.values())

    def get_schemas(self) -> list[dict[str, Any]]:
        """获取所有已注册工具的 Claude API schema。"""
        return [tool.get_schema() for tool in self._tools.values()]

    async def execute(self, name: str, **kwargs: Any) -> Any:
        """按名称执行工具。

        Args:
            name: 工具名称
            **kwargs: 工具参数

        Returns:
            工具执行结果

        Raises:
            ValueError: 如果工具未找到
        """
        tool = self.get(name)
        if tool is None:
            raise ValueError(f"工具未找到：{name}")
        return await tool(**kwargs)
