"""Code Agent - 基于 Claude 的智能代码助手。"""

__version__ = "0.1.0"

from code_agent.agent import CodeAgent
from code_agent.config import Config
from code_agent.tools import (
    AskUserQuestionTool,
    BaseTool,
    BashTool,
    EditTool,
    GlobTool,
    GrepTool,
    ReadTool,
    TodoWriteTool,
    ToolRegistry,
    WebFetchTool,
    WebSearchTool,
    WriteTool,
)

__all__ = [
    # 核心
    "CodeAgent",
    "Config",
    # 工具基类
    "BaseTool",
    "ToolRegistry",
    # 文件操作
    "ReadTool",
    "WriteTool",
    "EditTool",
    "GlobTool",
    "GrepTool",
    # 系统工具
    "BashTool",
    "AskUserQuestionTool",
    # 网络工具
    "WebFetchTool",
    "WebSearchTool",
    # 任务管理
    "TodoWriteTool",
]
