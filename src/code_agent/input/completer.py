"""命令自动补全模块。"""

from collections.abc import Iterable

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

from code_agent.commands.base import CommandRegistry


class CommandCompleter(Completer):
    """命令自动补全器。

    只在输入以 `/` 开头时提供补全建议。
    """

    def __init__(self, registry: CommandRegistry) -> None:
        """初始化补全器。

        Args:
            registry: 命令注册表
        """
        self._registry = registry

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """获取补全建议。

        Args:
            document: 当前文档
            complete_event: 补全事件

        Yields:
            补全建议
        """
        text = document.text_before_cursor

        # 只在 `/` 开头时补全
        if not text.startswith("/"):
            return

        # 获取 `/` 后面的前缀
        prefix = text[1:]

        # 获取所有命令名称
        for name in self._registry.get_all_names():
            if name.startswith(prefix):
                # 获取命令描述
                cmd_class = self._registry.get(name)
                description = cmd_class.description if cmd_class else ""

                # 计算需要补全的文本长度（从 / 开始）
                yield Completion(
                    text=name,
                    start_position=-len(prefix),
                    display=f"/{name}",
                    display_meta=description,
                )
