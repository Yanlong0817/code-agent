"""帮助命令。"""

from typing import TYPE_CHECKING, ClassVar

from rich import box
from rich.panel import Panel
from rich.table import Table

from code_agent.commands.base import BaseCommand

if TYPE_CHECKING:
    from code_agent.commands.handler import CommandHandler


class HelpCommand(BaseCommand):
    """显示帮助信息。"""

    name: ClassVar[str] = "help"
    description: ClassVar[str] = "显示帮助信息"

    async def execute(self, args: str) -> None:
        """显示帮助信息。

        Args:
            args: 可选的命令或工具名称
        """
        args = args.strip()

        if args:
            # 显示特定命令或工具的帮助
            await self._show_specific_help(args)
        else:
            # 显示所有帮助
            await self._show_all_help()

    async def _show_all_help(self) -> None:
        """显示所有帮助信息。"""
        console = self.agent.console

        # 显示命令帮助
        handler: CommandHandler = self.agent.command_handler  # type: ignore
        console.print(handler.registry.get_help())
        console.print()

        # 显示工具简介
        tools = self.agent.registry.get_all()

        table = Table(show_header=True, header_style="bold", box=box.ROUNDED)
        table.add_column("工具名称", style="cyan")
        table.add_column("描述")

        for tool in sorted(tools, key=lambda t: t.name):
            # 截断过长的描述
            desc = tool.description
            if len(desc) > 60:
                desc = desc[:57] + "..."
            table.add_row(tool.name, desc)

        console.print(
            Panel(
                table,
                title="可用工具",
                title_align="left",
                border_style="bright_black",
            )
        )
        console.print()
        console.print("[dim]使用 /help <命令或工具名> 查看详细帮助[/dim]")

    async def _show_specific_help(self, name: str) -> None:
        """显示特定命令或工具的帮助。

        Args:
            name: 命令或工具名称
        """
        console = self.agent.console

        # 先检查是否是命令
        handler: CommandHandler = self.agent.command_handler  # type: ignore
        cmd_name = name.lstrip("/")
        cmd_class = handler.registry.get(cmd_name)

        if cmd_class:
            console.print(
                Panel(
                    f"[cyan]/{cmd_class.name}[/cyan]\n\n{cmd_class.description}",
                    title="命令帮助",
                    border_style="cyan",
                )
            )
            return

        # 检查是否是工具
        tool = self.agent.registry.get(name)
        if tool:
            # 显示工具详细信息
            schema = tool.get_schema()
            input_schema = schema.get("input_schema", {})
            properties = input_schema.get("properties", {})
            required = input_schema.get("required", [])

            # 构建参数表格
            if properties:
                param_table = Table(show_header=True, header_style="bold", box=box.SIMPLE)
                param_table.add_column("参数", style="green")
                param_table.add_column("类型", style="yellow")
                param_table.add_column("必需", style="red")
                param_table.add_column("描述")

                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "any")
                    is_required = "✓" if param_name in required else ""
                    param_desc = param_info.get("description", "")
                    param_table.add_row(param_name, param_type, is_required, param_desc)

                content = f"[cyan]{tool.name}[/cyan]\n\n{tool.description}\n\n"
                console.print(
                    Panel(
                        content,
                        title="工具帮助",
                        border_style="cyan",
                    )
                )
                console.print(param_table)
            else:
                console.print(
                    Panel(
                        f"[cyan]{tool.name}[/cyan]\n\n{tool.description}",
                        title="工具帮助",
                        border_style="cyan",
                    )
                )
            return

        # 未找到
        console.print(f"[red]未找到命令或工具：{name}[/red]")
