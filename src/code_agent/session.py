"""会话管理模块 - 保存和加载对话历史。"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SessionMetadata(BaseModel):
    """会话元数据。"""

    id: str = Field(description="会话 ID")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="最后更新时间")
    model: str = Field(description="使用的模型")
    message_count: int = Field(default=0, description="消息数量")
    title: str = Field(default="", description="会话标题（可选）")


class Session(BaseModel):
    """会话数据。"""

    metadata: SessionMetadata
    messages: list[dict[str, Any]] = Field(default_factory=list)


class SessionManager:
    """会话管理器，负责保存和加载会话。"""

    def __init__(self, sessions_dir: str | Path | None = None) -> None:
        """初始化会话管理器。

        Args:
            sessions_dir: 会话存储目录，默认为 ~/.code_agent/sessions
        """
        if sessions_dir:
            self.sessions_dir = Path(sessions_dir)
        else:
            self.sessions_dir = Path.home() / ".code_agent" / "sessions"

        # 确保目录存在
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _generate_id(self) -> str:
        """生成会话 ID。

        Returns:
            基于时间戳的会话 ID（包含毫秒）
        """
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    def _get_session_path(self, session_id: str) -> Path:
        """获取会话文件路径。

        Args:
            session_id: 会话 ID

        Returns:
            会话文件路径
        """
        return self.sessions_dir / f"{session_id}.json"

    def create(self, model: str, title: str = "") -> Session:
        """创建新会话。

        Args:
            model: 使用的模型
            title: 会话标题

        Returns:
            新创建的会话
        """
        now = datetime.now().isoformat()
        session_id = self._generate_id()

        metadata = SessionMetadata(
            id=session_id,
            created_at=now,
            updated_at=now,
            model=model,
            message_count=0,
            title=title,
        )

        return Session(metadata=metadata, messages=[])

    def save(self, session: Session) -> Path:
        """保存会话。

        Args:
            session: 要保存的会话

        Returns:
            保存的文件路径
        """
        # 更新元数据
        session.metadata.updated_at = datetime.now().isoformat()
        session.metadata.message_count = len(session.messages)

        # 写入文件
        path = self._get_session_path(session.metadata.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session.model_dump(), f, ensure_ascii=False, indent=2)

        return path

    def load(self, session_id: str) -> Session:
        """加载会话。

        Args:
            session_id: 会话 ID

        Returns:
            加载的会话

        Raises:
            FileNotFoundError: 如果会话不存在
        """
        path = self._get_session_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"会话不存在：{session_id}")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return Session.model_validate(data)

    def load_from_path(self, path: str | Path) -> Session:
        """从指定路径加载会话。

        Args:
            path: 会话文件路径

        Returns:
            加载的会话

        Raises:
            FileNotFoundError: 如果文件不存在
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在：{path}")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return Session.model_validate(data)

    def delete(self, session_id: str) -> bool:
        """删除会话。

        Args:
            session_id: 会话 ID

        Returns:
            是否删除成功
        """
        path = self._get_session_path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_sessions(self, limit: int = 20) -> list[SessionMetadata]:
        """列出所有会话。

        Args:
            limit: 最大返回数量

        Returns:
            会话元数据列表（按更新时间倒序）
        """
        sessions = []

        for path in self.sessions_dir.glob("*.json"):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                metadata = SessionMetadata.model_validate(data.get("metadata", {}))
                sessions.append(metadata)
            except (json.JSONDecodeError, KeyError, ValueError, OSError):
                # 跳过无效或损坏的会话文件
                continue

        # 按更新时间倒序排序
        sessions.sort(key=lambda s: s.updated_at, reverse=True)

        return sessions[:limit]

    def search(self, keyword: str) -> list[SessionMetadata]:
        """搜索会话。

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的会话元数据列表
        """
        results = []
        keyword_lower = keyword.lower()

        for path in self.sessions_dir.glob("*.json"):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)

                # 在标题中搜索
                metadata = data.get("metadata", {})
                title = metadata.get("title", "").lower()
                if keyword_lower in title:
                    results.append(SessionMetadata.model_validate(metadata))
                    continue

                # 在消息内容中搜索
                messages = data.get("messages", [])
                for msg in messages:
                    content = msg.get("content", "")
                    if isinstance(content, str) and keyword_lower in content.lower():
                        results.append(SessionMetadata.model_validate(metadata))
                        break
            except (json.JSONDecodeError, KeyError, ValueError, OSError):
                # 跳过无效或损坏的会话文件
                continue

        # 按更新时间倒序排序
        results.sort(key=lambda s: s.updated_at, reverse=True)

        return results

    def get_latest(self) -> Session | None:
        """获取最新的会话。

        Returns:
            最新的会话，如果没有则返回 None
        """
        sessions = self.list_sessions(limit=1)
        if sessions:
            return self.load(sessions[0].id)
        return None
