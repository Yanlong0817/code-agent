"""UI 模块 - 提供 CLI 界面组件。"""

from code_agent.ui.components import (
    VERSION,
    get_prompt_markup,
    get_prompt_text,
    render_banner,
)
from code_agent.ui.status_bar import StatusBar, TokenUsage
from code_agent.ui.theme import (
    CODE_AGENT_THEME,
    SPINNER_TEXT,
    STYLES,
    TOOL_ICONS,
    Theme,
)
from code_agent.ui.tool_display import ToolDisplay, ToolExecutionTracker, ToolResult

__all__ = [
    # Theme
    "Theme",
    "STYLES",
    "CODE_AGENT_THEME",
    "TOOL_ICONS",
    "SPINNER_TEXT",
    # Components
    "VERSION",
    "render_banner",
    "get_prompt_text",
    "get_prompt_markup",
    # Tool Display
    "ToolDisplay",
    "ToolResult",
    "ToolExecutionTracker",
    # Status Bar
    "StatusBar",
    "TokenUsage",
]
