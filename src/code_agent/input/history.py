"""输入历史管理模块。"""

from pathlib import Path

from prompt_toolkit.history import FileHistory


class HistoryManager:
    """输入历史管理器。"""

    # 历史文件默认路径
    DEFAULT_HISTORY_PATH = Path.home() / ".code_agent" / "input_history"

    def __init__(self, history_path: Path | None = None) -> None:
        """初始化历史管理器。

        Args:
            history_path: 历史文件路径，默认为 ~/.code_agent/input_history
        """
        self._history_path = history_path or self.DEFAULT_HISTORY_PATH
        # 确保目录存在
        self._history_path.parent.mkdir(parents=True, exist_ok=True)

    def get_history(self) -> FileHistory:
        """获取 FileHistory 实例。

        Returns:
            FileHistory 实例
        """
        return FileHistory(str(self._history_path))
