"""命令处理器 - 解析和执行命令。"""

from pathlib import Path
from typing import TYPE_CHECKING

from code_agent.commands.base import BaseCommand, CommandRegistry
from code_agent.commands.clear import ClearCommand
from code_agent.commands.commands import CommandsCommand
from code_agent.commands.custom_commands import (
    CustomCommandSpec,
    build_custom_command_class,
    load_custom_commands,
)
from code_agent.commands.diff import DiffCommand
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

    def __init__(self, agent: "CodeAgent", custom_command_paths: list[Path] | None = None) -> None:
        """初始化命令处理器。

        Args:
            agent: CodeAgent 实例
            custom_command_paths: 可选，自定义命令配置路径（用于测试或覆盖默认配置）
        """
        self.agent = agent
        # 让命令实现可稳定拿到当前 handler（避免在测试桩中拿到错误对象）
        try:
            setattr(self.agent, "_command_handler", self)
        except Exception:
            pass

        self.registry = CommandRegistry()
        self._custom_command_names: set[str] = set()
        self._custom_commands: dict[str, CustomCommandSpec] = {}
        self._custom_command_errors: list[str] = []
        self._custom_command_paths = (
            custom_command_paths or self._get_default_custom_command_paths()
        )
        self._register_commands()
        self.reload_custom_commands()

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
        self.registry.register(DiffCommand)
        self.registry.register(CommandsCommand)

        # 会话管理命令
        self.registry.register(SaveCommand)
        self.registry.register(LoadCommand)
        self.registry.register(SessionsCommand)

    def _get_default_custom_command_paths(self) -> list[Path]:
        """返回默认的自定义命令配置路径（全局 + 项目级）。"""
        global_path = Path.home() / ".code_agent" / "commands.toml"

        raw_workspace = getattr(getattr(self.agent, "config", None), "working_directory", None)
        if isinstance(raw_workspace, Path):
            workspace = raw_workspace
        elif isinstance(raw_workspace, str):
            workspace = Path(raw_workspace)
        else:
            workspace = Path.cwd()

        project_path = (
            workspace.expanduser().resolve(strict=False) / ".code_agent" / "commands.toml"
        )

        paths = [global_path]
        if project_path != global_path:
            paths.append(project_path)
        return paths

    def reload_custom_commands(self) -> tuple[int, list[str]]:
        """重载自定义命令。

        Returns:
            (加载命令数量, 告警列表)
        """
        # 先移除旧的自定义命令，避免脏状态
        for name in self._custom_command_names:
            self.registry.remove(name)
        self._custom_command_names.clear()
        self._custom_commands.clear()

        reserved_names = set(self.registry.get_all_names())
        loaded, errors = load_custom_commands(self._custom_command_paths, reserved_names)

        for name, spec in loaded.items():
            command_class = build_custom_command_class(spec)
            self.registry.register(command_class)
            self._custom_command_names.add(name)
            self._custom_commands[name] = spec

        self._custom_command_errors = errors
        return len(self._custom_commands), list(self._custom_command_errors)

    def get_custom_commands(self) -> list[CustomCommandSpec]:
        """获取当前已加载的自定义命令。"""
        return sorted(self._custom_commands.values(), key=lambda c: c.name)

    def get_custom_command_errors(self) -> list[str]:
        """获取最近一次加载自定义命令的告警。"""
        return list(self._custom_command_errors)

    def get_custom_command_paths(self) -> list[Path]:
        """获取自定义命令配置文件路径。"""
        return list(self._custom_command_paths)

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
                if command_class is None:
                    self.agent.console.print(f"[red]未知命令：/{command_name}[/red]")
                    return True
            elif len(completions) > 1:
                # 多个匹配，显示建议
                self.agent.console.print(
                    f"[yellow]多个匹配的命令：{', '.join('/' + c for c in completions)}[/yellow]"
                )
                return True
            else:
                # 无匹配，显示帮助
                self.agent.console.print(f"[red]未知命令：/{command_name}[/red]")
                self.agent.console.print(self.registry.get_help())
                return True

        # 执行命令
        command: BaseCommand = command_class(self.agent)
        await command.execute(args)
        return True

    def show_help(self) -> None:
        """显示命令帮助。"""
        self.agent.console.print(self.registry.get_help())
