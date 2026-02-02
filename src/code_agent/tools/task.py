"""任务管理工具：TodoWrite。"""

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table

from code_agent.tools.base import BaseTool


class TodoItem(BaseModel):
    """单个待办事项。"""

    model_config = {"populate_by_name": True}

    content: str = Field(description="任务描述（祈使句形式）")
    status: Literal["pending", "in_progress", "completed"] = Field(
        default="pending", description="任务状态"
    )
    active_form: str = Field(
        alias="activeForm",
        description="进行时形式（如 '正在运行测试'）",
    )


class TodoWriteTool(BaseTool):
    """管理待办事项列表以跟踪任务进度。"""

    name: ClassVar[str] = "TodoWrite"
    description: ClassVar[str] = (
        "创建和管理结构化的任务列表。用于跟踪进度、组织复杂任务，并向用户展示当前工作内容。"
    )

    class Input(BaseModel):
        todos: list[TodoItem] = Field(description="更新后的待办事项列表")

    def __init__(self) -> None:
        self.console = Console()
        self.todos: list[TodoItem] = []

    async def execute(self, todos: list[dict[str, Any]]) -> str:
        """更新并显示待办事项列表。

        Args:
            todos: 待办事项字典列表

        Returns:
            确认消息
        """
        # 解析并存储待办事项
        self.todos = [TodoItem(**item) for item in todos]

        # 显示待办事项列表
        self._render_todos()

        # 按状态统计
        pending = sum(1 for t in self.todos if t.status == "pending")
        in_progress = sum(1 for t in self.todos if t.status == "in_progress")
        completed = sum(1 for t in self.todos if t.status == "completed")

        return f"待办事项已更新：{completed} 已完成，{in_progress} 进行中，{pending} 待处理"

    def _render_todos(self) -> None:
        """将待办事项列表渲染到控制台。"""
        if not self.todos:
            self.console.print("[dim]待办事项列表为空[/dim]")
            return

        table = Table(
            title="任务进度",
            show_header=True,
            header_style="bold cyan",
            box=None,
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("状态", width=12)
        table.add_column("任务")

        status_icons = {
            "pending": "[dim]○[/dim] 待处理",
            "in_progress": "[yellow]◐[/yellow] 进行中",
            "completed": "[green]●[/green] 已完成",
        }

        for i, todo in enumerate(self.todos, 1):
            status_display = status_icons.get(todo.status, todo.status)

            # 进行中显示 active_form，否则显示 content
            if todo.status == "in_progress":
                task_text = f"[yellow]{todo.active_form}[/yellow]"
            elif todo.status == "completed":
                task_text = f"[dim strikethrough]{todo.content}[/dim strikethrough]"
            else:
                task_text = todo.content

            table.add_row(str(i), status_display, task_text)

        self.console.print()
        self.console.print(table)
        self.console.print()

    def get_current_task(self) -> TodoItem | None:
        """获取当前进行中的任务。"""
        for todo in self.todos:
            if todo.status == "in_progress":
                return todo
        return None
