"""命令处理器 - 解析和执行命令。"""

from typing import TYPE_CHECKING

from code_agent.commands.base import BaseCommand, CommandRegistry
from code_agent.commands.clear import ClearCommand
from code_agent.commands.export import ExportCommand
from code_agent.commands.help import HelpCommand
from code_agent.commands.history import HistoryCommand
from code_agent.commands.model import ModelCommand
from code_agent.commands.session import LoadCommand, SaveCommand, SessionsCommand
from code_agent.commands.tools import ToolsCommand

if TYPE_CHECKING:
    from code_agent.agent import CodeAgent


class CommandHandler:
    """命令处理器，负责解析和执行以 / 开头的命令。"""

    def __init__(self, agent: "CodeAgent") -> None:
        """初始化命令处理器。

        Args:
            agent: CodeAgent 实例
        """
        self.agent = agent
        self.registry = CommandRegistry()
        self._register_commands()

    def _register_commands(self) -> None:
        """注册所有可用命令。"""
        # 核心命令
        self.registry.register(HelpCommand)
        self.registry.register(ClearCommand)

        # 功能命令
        self.registry.register(ModelCommand)
        self.registry.register(ToolsCommand)
        self.registry.register(HistoryCommand)
        self.registry.register(ExportCommand)

        # 会话管理命令
        self.registry.register(SaveCommand)
        self.registry.register(LoadCommand)
        self.registry.register(SessionsCommand)

    def is_command(self, text: str) -> bool:
        """检查输入是否是命令。

        Args:
            text: 用户输入

        Returns:
            如果是命令返回 True
        """
        return text.strip().startswith("/")

    def get_completions(self, text: str) -> list[str]:
        """获取命令补全建议。

        Args:
            text: 用户输入（以 / 开头）

        Returns:
            补全建议列表（完整命令，含 /）
        """
        if not text.startswith("/"):
            return []

        prefix = text[1:]  # 去掉 /
        matches = self.registry.get_completions(prefix)
        return [f"/{name}" for name in matches]

    async def execute(self, text: str) -> bool:
        """解析并执行命令。

        Args:
            text: 用户输入（以 / 开头）

        Returns:
            如果命令执行成功返回 True，否则返回 False
        """
        if not self.is_command(text):
            return False

        # 解析命令名和参数
        text = text.strip()[1:]  # 去掉 /
        parts = text.split(maxsplit=1)
        command_name = parts[0] if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        # 如果只输入了 /，显示所有可用命令
        if not command_name:
            self.show_help()
            return True

        # 查找命令
        command_class = self.registry.get(command_name)
        if command_class is None:
            # 尝试补全
            completions = self.registry.get_completions(command_name)
            if len(completions) == 1:
                # 唯一匹配，执行该命令
                command_class = self.registry.get(completions[0])
            elif len(completions) > 1:
                # 多个匹配，显示建议
                self.agent.console.print(
                    f"[yellow]多个匹配的命令：{', '.join('/' + c for c in completions)}[/yellow]"
                )
                return True
            else:
                # 无匹配，显示帮助
                self.agent.console.print(f"[red]未知命令：/{command_name}[/red]")
                self.agent.console.print(f"[dim]{self.registry.get_help()}[/dim]")
                return True

        # 执行命令
        command: BaseCommand = command_class(self.agent)
        await command.execute(args)
        return True

    def show_help(self) -> None:
        """显示命令帮助。"""
        self.agent.console.print(self.registry.get_help())
