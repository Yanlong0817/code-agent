"""prompt_toolkit 样式定义模块。"""

from prompt_toolkit.styles import Style

from code_agent.ui.theme import Theme


def get_prompt_style() -> Style:
    """获取 prompt_toolkit 样式。

    Returns:
        prompt_toolkit Style 实例
    """
    return Style.from_dict({
        "prompt": Theme.PRIMARY,
        "prompt.arrow": f"{Theme.PRIMARY} bold",
    })


def get_prompt_fragments() -> list[tuple[str, str]]:
    """获取提示符片段。

    Returns:
        提示符片段列表，格式为 [(style, text), ...]
    """
    return [
        ("class:prompt", "◆ "),
        ("class:prompt.arrow", "> "),
    ]
