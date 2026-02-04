"""输入会话模块。"""

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from code_agent.commands.base import CommandRegistry

from .completer import CommandCompleter
from .history import HistoryManager
from .style import get_prompt_fragments, get_prompt_style


class InputSession:
    """输入会话管理器。

    组合历史管理、命令补全和样式，提供增强的输入体验。
    """

    def __init__(self, registry: CommandRegistry) -> None:
        """初始化输入会话。

        Args:
            registry: 命令注册表，用于命令补全
        """
        self._history_manager = HistoryManager()
        self._completer = CommandCompleter(registry)
        self._style = get_prompt_style()

        # 创建 PromptSession
        self._session: PromptSession[str] = PromptSession(
            history=self._history_manager.get_history(),
            completer=self._completer,
            style=self._style,
            enable_history_search=True,  # 启用 Ctrl+R 搜索历史
            complete_while_typing=False,  # 不在输入时自动补全，按 Tab 触发
        )

    async def prompt_async(self) -> str:
        """异步获取用户输入。

        使用 patch_stdout() 确保其他输出不会干扰提示符。

        Returns:
            用户输入的文本
        """
        prompt_fragments = get_prompt_fragments()

        with patch_stdout():
            return await self._session.prompt_async(prompt_fragments)
