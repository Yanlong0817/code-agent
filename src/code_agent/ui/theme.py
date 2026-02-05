"""颜色主题定义模块。"""

from rich.style import Style
from rich.theme import Theme as RichTheme


class Theme:
    """颜色主题定义。"""

    # === 品牌色 ===
    PRIMARY = "#E07A5F"  # 主色调（珊瑚橙）
    SECONDARY = "#3D5A80"  # 次要色（深蓝灰）
    ACCENT = "#81B29A"  # 强调色（薄荷绿）

    # === 语义色 ===
    SUCCESS = "#81B29A"  # 成功（绿色）
    WARNING = "#F2CC8F"  # 警告（金黄色）
    ERROR = "#E07A5F"  # 错误（珊瑚红）
    INFO = "#3D5A80"  # 信息（蓝灰）

    # === 文本色 ===
    TEXT_MUTED = "#888888"  # 次要文本

    # === 工具调用专用色 ===
    TOOL_NAME = "#81B29A"  # 工具名称（薄荷绿）
    TOOL_BORDER = "#555555"  # 工具面板边框


# Rich 样式定义
STYLES = {
    # 品牌样式
    "brand.primary": Style(color=Theme.PRIMARY, bold=True),
    "brand.icon": Style(color=Theme.PRIMARY, bold=True),
    # 工具样式
    "tool.name": Style(color=Theme.TOOL_NAME, bold=True),
    "tool.border": Style(color=Theme.TOOL_BORDER),
    "tool.success": Style(color=Theme.SUCCESS),
    "tool.error": Style(color=Theme.ERROR, bold=True),
    # 提示符样式
    "prompt.icon": Style(color=Theme.PRIMARY, bold=True),
    "prompt.text": Style(bold=True),
    # 状态栏样式
    "status.model": Style(color=Theme.ACCENT),
    "status.tokens": Style(color=Theme.WARNING),
    "status.dim": Style(color=Theme.TEXT_MUTED),
    # 横幅样式
    "banner.title": Style(color=Theme.PRIMARY, bold=True),
    "banner.subtitle": Style(color=Theme.TEXT_MUTED),
}

# 创建 Rich Theme 对象
CODE_AGENT_THEME = RichTheme(STYLES)


# 工具图标映射
TOOL_ICONS: dict[str, str] = {
    "Read": "📖",
    "Write": "✏️",
    "Edit": "🔧",
    "Bash": "⚡",
    "Glob": "🔍",
    "Grep": "🔎",
    "WebFetch": "🌐",
    "WebSearch": "🔍",
    "AskUserQuestion": "💬",
}


# Spinner 文本映射
SPINNER_TEXT: dict[str, str] = {
    "Read": "Reading file",
    "Write": "Writing file",
    "Edit": "Editing file",
    "Bash": "Running command",
    "Glob": "Searching files",
    "Grep": "Searching content",
    "WebFetch": "Fetching URL",
    "WebSearch": "Searching web",
    "AskUserQuestion": "Waiting for input",
}
