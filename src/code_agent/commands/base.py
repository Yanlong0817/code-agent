"""命令基类和注册表。"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from rich import box
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from code_agent.agent import CodeAgent


class BaseCommand(ABC):
    """命令基类。所有命令都应继承此类。"""

    # 命令名称（不含 /）
    name: ClassVar[str]
    # 命令描述
    description: ClassVar[str]

    def __init__(self, agent: "CodeAgent") -> None:
        """初始化命令。

        Args:
            agent: CodeAgent 实例
        """
        self.agent = agent

    @abstractmethod
    async def execute(self, args: str) -> None:
        """执行命令。

        Args:
            args: 命令参数（/ 后面的部分，不含命令名）
        """
        pass


class CommandRegistry:
    """命令注册表，管理所有可用命令。"""

    def __init__(self) -> None:
        """初始化注册表。"""
        self._commands: dict[str, type[BaseCommand]] = {}

    def register(self, command_class: type[BaseCommand]) -> None:
        """注册命令类。

        Args:
            command_class: 命令类
        """
        self._commands[command_class.name] = command_class

    def get(self, name: str) -> type[BaseCommand] | None:
        """获取命令类。

        Args:
            name: 命令名称

        Returns:
            命令类，如果不存在则返回 None
        """
        return self._commands.get(name)

    def get_all_names(self) -> list[str]:
        """获取所有命令名称。

        Returns:
            命令名称列表
        """
        return list(self._commands.keys())

    def get_completions(self, prefix: str) -> list[str]:
        """获取命令补全建议。

        Args:
            prefix: 输入前缀（不含 /）

        Returns:
            匹配的命令名称列表
        """
        return [name for name in self._commands if name.startswith(prefix)]

    def get_help(self) -> Panel:
        """获取所有命令的帮助信息。

        Returns:
            格式化的帮助 Panel
        """
        # 创建命令表格
        table = Table.grid(padding=(0, 2))
        table.add_column(style="cyan", justify="left")
        table.add_column(style="dim")

        for name, cmd_class in sorted(self._commands.items()):
            table.add_row(f"/{name}", cmd_class.description)

        # 添加退出提示
        table.add_row("")
        table.add_row("[dim]quit[/dim]", "[dim]Exit the program[/dim]")

        return Panel(
            table,
            title="Commands",
            title_align="left",
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(0, 1),
        )
