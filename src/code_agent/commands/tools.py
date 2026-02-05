"""工具列表命令。"""

from typing import ClassVar

from rich import box
from rich.table import Table

from code_agent.commands.base import BaseCommand


class ToolsCommand(BaseCommand):
    """列出所有可用工具。"""

    name: ClassVar[str] = "tools"
    description: ClassVar[str] = "列出所有可用工具"

    async def execute(self, args: str) -> None:
        """显示所有可用工具列表。

        Args:
            args: 命令参数（未使用）
        """
        console = self.agent.console
        tools = self.agent.registry.get_all()

        # 按类别分组工具
        categories = {
            "文件操作": ["Read", "Write", "Edit", "Glob", "Grep"],
            "Git": ["Git"],
            "系统交互": ["Bash", "AskUserQuestion"],
            "网络工具": ["WebFetch", "WebSearch"],
        }

        # 创建工具到类别的映射
        tool_category = {}
        for cat, prefixes in categories.items():
            for prefix in prefixes:
                tool_category[prefix] = cat

        # 主表格
        table = Table(
            title="可用工具",
            show_header=True,
            header_style="bold",
            box=box.ROUNDED,
            title_style="bold cyan",
        )
        table.add_column("类别", style="magenta")
        table.add_column("工具名称", style="cyan")
        table.add_column("描述")

        # 对工具进行分组
        current_category = ""
        for tool in sorted(tools, key=lambda t: self._get_category_order(t.name)):
            # 获取类别
            cat = self._get_tool_category(tool.name, categories)

            # 如果是新类别，显示类别名
            if cat != current_category:
                if current_category:
                    table.add_row("", "", "")  # 添加空行分隔
                current_category = cat
                cat_display = cat
            else:
                cat_display = ""

            # 截断过长的描述
            desc = tool.description
            if len(desc) > 50:
                desc = desc[:47] + "..."

            table.add_row(cat_display, tool.name, desc)

        console.print()
        console.print(table)
        console.print()
        console.print(f"[dim]共 {len(tools)} 个工具可用[/dim]")
        console.print("[dim]使用 /help <工具名> 查看工具详情[/dim]")

    def _get_tool_category(self, tool_name: str, categories: dict[str, list[str]]) -> str:
        """获取工具所属类别。

        Args:
            tool_name: 工具名称
            categories: 类别定义

        Returns:
            类别名称
        """
        for cat, prefixes in categories.items():
            for prefix in prefixes:
                if tool_name.startswith(prefix):
                    return cat
        return "其他"

    def _get_category_order(self, tool_name: str) -> tuple[int, str]:
        """获取工具排序键（类别顺序，工具名）。

        Args:
            tool_name: 工具名称

        Returns:
            排序键元组
        """
        category_order = {
            "文件操作": 0,
            "Git": 1,
            "系统交互": 2,
            "网络工具": 3,
            "其他": 4,
        }
        categories = {
            "文件操作": ["Read", "Write", "Edit", "Glob", "Grep"],
            "Git": ["Git"],
            "系统交互": ["Bash", "AskUserQuestion"],
            "网络工具": ["WebFetch", "WebSearch"],
        }
        cat = self._get_tool_category(tool_name, categories)
        return (category_order.get(cat, 99), tool_name)
