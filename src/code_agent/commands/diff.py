"""显示本次会话文件变更 diff 的命令。"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from rich import box
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from code_agent.commands.base import BaseCommand
from code_agent.utils.diff import generate_unified_diff


class DiffCommand(BaseCommand):
    """显示本次会话中所有文件变更的 diff。"""

    name: ClassVar[str] = "diff"
    description: ClassVar[str] = "显示本次会话的文件变更"

    async def execute(self, args: str) -> None:
        console = self.agent.console
        checkpoint_store = getattr(self.agent, "checkpoint_store", None)

        if checkpoint_store is None:
            console.print("[red]无法获取文件变更记录[/red]")
            return

        entries = checkpoint_store.get_all()
        if not entries:
            console.print("[dim]本次会话没有文件变更[/dim]")
            return

        # 每个文件只取最早的检查点（最原始的 before 状态）
        oldest: dict[Path, str] = {}
        existed_before: dict[Path, bool] = {}
        for entry in entries:
            if entry.path not in oldest:
                oldest[entry.path] = entry.content_before
                existed_before[entry.path] = entry.existed_before

        changed = 0
        for path, before in oldest.items():
            if path.exists():
                with open(path, encoding="utf-8", errors="replace") as f:
                    after = f.read()
            elif existed_before.get(path):
                after = ""
            else:
                continue

            if before == after:
                continue

            diff_text = generate_unified_diff(before, after, file_path=str(path))

            label = Text()
            label.append(str(path), style="bold cyan")
            if not existed_before.get(path):
                label.append("  [new file]", style="green")
            elif not path.exists():
                label.append("  [deleted]", style="red")

            console.print(label)
            console.print(
                Panel(
                    Syntax(diff_text, "diff", theme="monokai", word_wrap=True),
                    border_style="bright_black",
                    box=box.ROUNDED,
                    padding=(0, 1),
                )
            )
            changed += 1

        if changed == 0:
            console.print("[dim]所有已修改文件当前内容与修改前一致[/dim]")
        else:
            console.print(f"[dim]共 {changed} 个文件有变更[/dim]")
