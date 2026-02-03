"""清除对话历史命令。"""

from typing import ClassVar

from code_agent.commands.base import BaseCommand


class ClearCommand(BaseCommand):
    """清除对话历史，重新开始会话。"""

    name: ClassVar[str] = "clear"
    description: ClassVar[str] = "清除对话历史"

    async def execute(self, args: str) -> None:
        """执行清除操作。

        Args:
            args: 命令参数（未使用）
        """
        # 获取当前消息数量
        msg_count = len(self.agent.messages)

        # 重置对话
        self.agent.reset()

        self.agent.console.print(f"[green]已清除 {msg_count} 条消息，对话已重置。[/green]")
