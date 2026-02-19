"""自定义命令管理命令。"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from rich import box
from rich.table import Table

from code_agent.commands.base import BaseCommand


class CommandsCommand(BaseCommand):
    """管理自定义命令。"""

    name: ClassVar[str] = "commands"
    description: ClassVar[str] = "管理自定义命令（list/reload/init）"
    TEMPLATE: ClassVar[str] = (
        "[commands.review]\n"
        'description = "审查改动风险"\n'
        'prompt = "请审查当前改动，重点关注 bug、行为回归与测试缺口。"\n\n'
        "[commands.explain]\n"
        'description = "解释一个概念"\n'
        'prompt = "请用中文解释：{args}"\n'
        "requires_args = true\n"
    )

    async def execute(self, args: str) -> None:
        tokens = [token for token in args.strip().split() if token]
        subcommand = tokens[0].lower() if tokens else "list"
        rest = tokens[1:]

        if subcommand in {"list", "ls"}:
            self._show_commands()
            return

        if subcommand == "reload":
            handler = self._resolve_handler()
            if handler is None:
                self.agent.console.print("[red]无法获取命令处理器[/red]")
                return
            if rest:
                self.agent.console.print("[yellow]用法：/commands reload[/yellow]")
                return
            count, errors = handler.reload_custom_commands()
            self.agent.console.print(f"[green]已重载自定义命令：{count} 个[/green]")
            if errors:
                self.agent.console.print(f"[yellow]加载告警：{len(errors)} 条[/yellow]")
                for error in errors[:10]:
                    self.agent.console.print(f"[dim]- {error}[/dim]")
                if len(errors) > 10:
                    self.agent.console.print(f"[dim]... 其余 {len(errors) - 10} 条告警已省略[/dim]")
            return

        if subcommand == "init":
            await self._init_template(rest)
            return

        self.agent.console.print("[yellow]用法：/commands [list|reload|init][/yellow]")

    def _show_commands(self) -> None:
        handler = self._resolve_handler()
        if handler is None:
            self.agent.console.print("[red]无法获取命令处理器[/red]")
            return
        console = self.agent.console
        specs = handler.get_custom_commands()

        if not specs:
            console.print("[dim]当前没有自定义命令[/dim]")
            console.print("[dim]可在以下文件中配置：[/dim]")
            for path in handler.get_custom_command_paths():
                console.print(f"[dim]- {path}[/dim]")
            return

        table = Table(
            title="自定义命令",
            show_header=True,
            header_style="bold",
            box=box.ROUNDED,
            title_style="bold cyan",
        )
        table.add_column("命令", style="cyan")
        table.add_column("描述")
        table.add_column("来源", style="dim")

        for spec in specs:
            desc = spec.description
            if len(desc) > 48:
                desc = desc[:45] + "..."
            table.add_row(f"/{spec.name}", desc, str(spec.source_path))

        console.print()
        console.print(table)
        console.print()

        errors = handler.get_custom_command_errors()
        if errors:
            console.print(
                f"[yellow]加载告警：{len(errors)} 条（使用 /commands reload 重新加载）[/yellow]"
            )

    async def _init_template(self, args: list[str]) -> None:
        handler = self._resolve_handler()
        if handler is None:
            self.agent.console.print("[red]无法获取命令处理器[/red]")
            return

        scope = "project"
        force = False

        for token in args:
            lowered = token.lower()
            if lowered in {"project", "global"}:
                scope = lowered
                continue
            if lowered == "--force":
                force = True
                continue
            self.agent.console.print(
                "[yellow]用法：/commands init [project|global] [--force][/yellow]"
            )
            return

        target_path = self._resolve_init_path(scope, handler.get_custom_command_paths())

        if target_path.exists() and not force:
            self.agent.console.print(f"[yellow]文件已存在：{target_path}[/yellow]")
            self.agent.console.print("[dim]使用 --force 覆盖模板[/dim]")
            return

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(self.TEMPLATE)

        count, errors = handler.reload_custom_commands()
        self.agent.console.print(f"[green]已写入模板：{target_path}[/green]")
        self.agent.console.print(f"[green]当前已加载自定义命令：{count} 个[/green]")
        if errors:
            self.agent.console.print(f"[yellow]加载告警：{len(errors)} 条[/yellow]")

    def _resolve_init_path(self, scope: str, paths: list[Path]) -> Path:
        """根据 scope 选择模板写入路径。"""
        if not paths:
            return Path.home() / ".code_agent" / "commands.toml"

        global_path = paths[0]
        project_path = paths[1] if len(paths) > 1 else global_path
        return project_path if scope == "project" else global_path

    def _resolve_handler(self):
        """解析当前会话中的 CommandHandler。"""
        handler = getattr(self.agent, "_command_handler", None)
        if handler is not None and hasattr(handler, "reload_custom_commands"):
            return handler

        candidate = getattr(self.agent, "command_handler", None)
        if candidate is not None and hasattr(candidate, "reload_custom_commands"):
            return candidate

        return None
