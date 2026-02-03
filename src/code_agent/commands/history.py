"""对话历史命令。"""

from typing import Any, ClassVar

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from code_agent.commands.base import BaseCommand


class HistoryCommand(BaseCommand):
    """显示对话历史摘要。"""

    name: ClassVar[str] = "history"
    description: ClassVar[str] = "显示对话历史"

    async def execute(self, args: str) -> None:
        """显示对话历史。

        Args:
            args: 可选参数：
                - 数字：显示最近 N 条消息
                - "full"：显示完整历史
                - "stats"：只显示统计信息
        """
        args = args.strip().lower()
        messages = self.agent.messages

        if not messages:
            self.agent.console.print("[dim]对话历史为空[/dim]")
            return

        if args == "stats":
            self._show_stats(messages)
        elif args == "full":
            self._show_history(messages, limit=None)
        elif args.isdigit():
            self._show_history(messages, limit=int(args))
        else:
            # 默认显示统计和最近 5 条
            self._show_stats(messages)
            self.agent.console.print()
            self._show_history(messages, limit=5)

    def _show_stats(self, messages: list[dict[str, Any]]) -> None:
        """显示历史统计信息。

        Args:
            messages: 消息列表
        """
        console = self.agent.console

        # 统计消息类型
        user_count = sum(1 for m in messages if m.get("role") == "user")
        assistant_count = sum(1 for m in messages if m.get("role") == "assistant")

        # 统计工具调用
        tool_calls = 0
        tool_results = 0
        for msg in messages:
            content = msg.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "tool_use":
                            tool_calls += 1
                        elif item.get("type") == "tool_result":
                            tool_results += 1

        # 创建统计表格
        table = Table(show_header=False, box=box.SIMPLE)
        table.add_column("项目", style="dim")
        table.add_column("数量", style="cyan")

        table.add_row("用户消息", str(user_count))
        table.add_row("助手响应", str(assistant_count))
        table.add_row("工具调用", str(tool_calls))
        table.add_row("总消息数", str(len(messages)))

        console.print(
            Panel(
                table,
                title="对话统计",
                border_style="bright_black",
                box=box.ROUNDED,
            )
        )

    def _show_history(self, messages: list[dict[str, Any]], limit: int | None) -> None:
        """显示对话历史。

        Args:
            messages: 消息列表
            limit: 显示的消息数量限制
        """
        console = self.agent.console

        # 限制显示数量
        if limit:
            display_messages = messages[-limit:]
            if len(messages) > limit:
                console.print(f"[dim]...省略了 {len(messages) - limit} 条早期消息...[/dim]")
        else:
            display_messages = messages

        for i, msg in enumerate(display_messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            # 根据角色设置样式
            if role == "user":
                role_style = "bold green"
                role_label = "用户"
            elif role == "assistant":
                role_style = "bold blue"
                role_label = "助手"
            else:
                role_style = "dim"
                role_label = role

            # 处理内容
            if isinstance(content, str):
                display_content = self._truncate(content, 200)
            elif isinstance(content, list):
                # 处理复杂内容（包含工具调用等）
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        item_type = item.get("type", "")
                        if item_type == "text":
                            parts.append(self._truncate(item.get("text", ""), 100))
                        elif item_type == "tool_use":
                            parts.append(f"[dim][工具调用: {item.get('name')}][/dim]")
                        elif item_type == "tool_result":
                            parts.append("[dim][工具结果][/dim]")
                display_content = " | ".join(parts) if parts else "[dim]空[/dim]"
            else:
                display_content = str(content)

            # 创建消息文本
            text = Text()
            text.append(f"[{role_label}] ", style=role_style)
            text.append(display_content)

            console.print(text)

    def _truncate(self, text: str, max_length: int) -> str:
        """截断文本。

        Args:
            text: 原始文本
            max_length: 最大长度

        Returns:
            截断后的文本
        """
        # 移除换行符
        text = text.replace("\n", " ").strip()
        if len(text) > max_length:
            return text[: max_length - 3] + "..."
        return text
