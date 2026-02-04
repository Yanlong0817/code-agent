"""导出对话命令。"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from code_agent.commands.base import BaseCommand


def _sanitize_for_json(obj: Any) -> Any:
    """递归清理数据中的 surrogate 字符。

    当子进程输出包含无效 UTF-8 字节序列时，decode() 可能创建 Unicode 代理字符
    （U+D800-U+DFFF），这些字符在 JSON 序列化时会导致编码失败。

    Args:
        obj: 要清理的数据对象

    Returns:
        清理后的数据对象
    """
    if isinstance(obj, str):
        return obj.encode("utf-8", errors="replace").decode("utf-8")
    elif isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(item) for item in obj]
    return obj


class ExportCommand(BaseCommand):
    """导出对话历史到文件。"""

    name: ClassVar[str] = "export"
    description: ClassVar[str] = "导出对话历史到文件"

    async def execute(self, args: str) -> None:
        """导出对话历史。

        Args:
            args: 可选的文件路径，默认为 conversation_<timestamp>.json
        """
        console = self.agent.console
        messages = self.agent.messages

        if not messages:
            console.print("[yellow]对话历史为空，无需导出[/yellow]")
            return

        # 确定输出文件路径
        args = args.strip()
        if args:
            output_path = Path(args)
        else:
            # 生成默认文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"conversation_{timestamp}.json")

        # 确保父目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 准备导出数据
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "model": self.agent.config.model,
            "message_count": len(messages),
            "messages": messages,
            "stats": self._collect_stats(messages),
        }

        # 清理可能包含 surrogate 字符的数据并写入文件
        try:
            sanitized_data = _sanitize_for_json(export_data)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(sanitized_data, f, ensure_ascii=False, indent=2)

            console.print(
                f"[green]已导出 {len(messages)} 条消息到：[/green][cyan]{output_path}[/cyan]"
            )
        except Exception as e:
            console.print(f"[red]导出失败：{e}[/red]")

    def _collect_stats(self, messages: list) -> dict:
        """收集对话统计信息。

        Args:
            messages: 消息列表

        Returns:
            统计信息字典
        """
        stats = {
            "user_messages": 0,
            "assistant_messages": 0,
            "tool_calls": 0,
            "tool_results": 0,
        }

        for msg in messages:
            role = msg.get("role", "")
            if role == "user":
                stats["user_messages"] += 1
            elif role == "assistant":
                stats["assistant_messages"] += 1

            content = msg.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        item_type = item.get("type", "")
                        if item_type == "tool_use":
                            stats["tool_calls"] += 1
                        elif item_type == "tool_result":
                            stats["tool_results"] += 1

        return stats
