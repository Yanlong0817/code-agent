"""Code Agent - 基于 Claude 的智能代码助手。"""

__version__ = "0.1.0"

from code_agent.agent import CodeAgent
from code_agent.config import Config
from code_agent.logging import get_logger, setup_logging
from code_agent.safety import SafetyCheck, SafetyChecker, get_safety_checker
from code_agent.session import Session, SessionManager, SessionMetadata
from code_agent.tools import (
    ApplyPatchTool,
    BaseTool,
    BashTool,
    CheckpointStore,
    EditTool,
    GlobTool,
    GrepTool,
    InsertTool,
    ReadTool,
    ToolRegistry,
    UndoTool,
    WebFetchTool,
    WebSearchTool,
    WriteTool,
)

__all__ = [
    # 核心
    "CodeAgent",
    "Config",
    # 会话管理
    "Session",
    "SessionManager",
    "SessionMetadata",
    # 安全
    "SafetyCheck",
    "SafetyChecker",
    "get_safety_checker",
    # 日志
    "setup_logging",
    "get_logger",
    # 工具基类
    "BaseTool",
    "ToolRegistry",
    # 文件操作
    "ReadTool",
    "WriteTool",
    "EditTool",
    "ApplyPatchTool",
    "UndoTool",
    "InsertTool",
    "GlobTool",
    "GrepTool",
    "CheckpointStore",
    # 系统工具
    "BashTool",
    # 网络工具
    "WebFetchTool",
    "WebSearchTool",
]
