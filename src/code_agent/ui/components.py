"""UI 组件模块 - Banner 和 Prompt。"""

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from code_agent.ui.theme import Theme

# 版本号
VERSION = "0.1.0"


def render_banner(model: str, console: Console | None = None) -> Panel:
    """渲染欢迎横幅。

    Args:
        model: 当前使用的模型名称
        console: Rich Console 实例

    Returns:
        Panel 组件
    """
    # 简化模型名称显示
    model_short = _get_short_model_name(model)

    # 创建内容网格
    content = Table.grid(padding=(0, 1))
    content.add_column(justify="left")

    # Logo 行
    title = Text()
    title.append("◆ ", style=f"bold {Theme.PRIMARY}")
    title.append("Code Agent", style=f"bold {Theme.PRIMARY}")
    content.add_row(title)

    # 模型信息行
    subtitle = Text()
    subtitle.append(f"  Powered by {model_short}", style=Theme.TEXT_MUTED)
    content.add_row(subtitle)

    # 提示行
    hint = Text()
    hint.append(f"  v{VERSION} · ", style="dim")
    hint.append("/help", style=f"dim {Theme.ACCENT}")
    hint.append(" for commands", style="dim")
    content.add_row(hint)

    return Panel(
        content,
        border_style="bright_black",
        box=box.ROUNDED,
        padding=(0, 1),
    )


def get_prompt_text() -> Text:
    """生成提示符文本。

    Returns:
        Rich Text 对象
    """
    text = Text()
    text.append("◆ ", style=f"bold {Theme.PRIMARY}")
    text.append("> ", style="bold")
    return text


def get_prompt_markup() -> str:
    """生成提示符 markup 字符串（用于 Prompt.ask）。

    Returns:
        Rich markup 字符串
    """
    return f"[bold {Theme.PRIMARY}]◆[/bold {Theme.PRIMARY}] [bold]>[/bold]"


def _get_short_model_name(model: str) -> str:
    """获取简化的模型名称。

    Args:
        model: 完整模型名称

    Returns:
        简化的模型名称
    """
    # 处理常见的模型名称格式
    if "opus" in model.lower():
        return "Claude Opus"
    elif "sonnet" in model.lower():
        return "Claude Sonnet"
    elif "haiku" in model.lower():
        return "Claude Haiku"
    else:
        # 返回前两部分
        parts = model.split("-")
        if len(parts) >= 2:
            return f"{parts[0].title()} {parts[1].title()}"
        return model
