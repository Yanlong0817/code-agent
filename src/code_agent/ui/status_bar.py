"""状态栏组件。"""

from dataclasses import dataclass

from rich import box
from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from code_agent.ui.theme import Theme


@dataclass
class TokenUsage:
    """Token 使用统计。"""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        """总 token 数。"""
        return self.input_tokens + self.output_tokens

    def format(self) -> str:
        """格式化显示。"""
        if self.total < 1000:
            return str(self.total)
        return f"{self.total / 1000:.1f}k"

    def update(self, input_tokens: int, output_tokens: int) -> None:
        """更新 token 使用量。

        Args:
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
        """
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def reset(self) -> None:
        """重置统计。"""
        self.input_tokens = 0
        self.output_tokens = 0


class StatusBar:
    """底部状态栏组件。"""

    def __init__(self, model: str, max_tokens: int, max_iterations: int) -> None:
        """初始化状态栏。

        Args:
            model: 模型名称
            max_tokens: 最大 token 数
            max_iterations: 最大迭代次数
        """
        self.model = model
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations
        self.token_usage = TokenUsage()
        self.current_iteration = 0

    def update_iteration(self, iteration: int) -> None:
        """更新当前迭代次数。

        Args:
            iteration: 当前迭代次数
        """
        self.current_iteration = iteration

    def update_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """更新 token 使用量。

        Args:
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
        """
        self.token_usage.update(input_tokens, output_tokens)

    def update_model(self, model: str) -> None:
        """更新模型名称。

        Args:
            model: 新的模型名称
        """
        self.model = model

    def reset(self) -> None:
        """重置状态栏。"""
        self.token_usage.reset()
        self.current_iteration = 0

    def _get_short_model_name(self) -> str:
        """获取简化的模型名称。"""
        model = self.model.lower()
        if "opus" in model:
            return "opus"
        elif "sonnet" in model:
            return "sonnet"
        elif "haiku" in model:
            return "haiku"
        else:
            parts = self.model.split("-")
            return parts[1] if len(parts) > 1 else self.model[:10]

    def render(self) -> RenderableType:
        """渲染状态栏。

        Returns:
            可渲染的组件
        """
        bar = Table.grid(expand=True)
        bar.add_column(justify="left", ratio=1)
        bar.add_column(justify="center", ratio=2)
        bar.add_column(justify="right", ratio=1)

        # 左侧：模型
        model_short = self._get_short_model_name()
        left = Text()
        left.append(" ◆ ", style=f"bold {Theme.PRIMARY}")
        left.append(model_short, style=Theme.ACCENT)

        # 中间：Token 使用和迭代次数
        center = Text()
        center.append("Tokens: ", style="dim")
        center.append(self.token_usage.format(), style=Theme.WARNING)
        center.append(f"/{self.max_tokens // 1000}k", style="dim")
        center.append(" │ ", style="dim")
        center.append("Iter: ", style="dim")
        center.append(str(self.current_iteration), style=Theme.ACCENT)
        center.append(f"/{self.max_iterations}", style="dim")

        # 右侧：帮助提示
        right = Text()
        right.append("/help ", style="dim")

        bar.add_row(left, center, right)

        return Panel(
            bar,
            box=box.SIMPLE,
            style="dim",
            padding=(0, 0),
        )

    def render_simple(self) -> Text:
        """渲染简化版状态栏（单行文本）。

        Returns:
            Text 对象
        """
        model_short = self._get_short_model_name()

        text = Text()
        text.append("─" * 50, style="dim")
        text.append("\n")
        text.append(" ◆ ", style=f"bold {Theme.PRIMARY}")
        text.append(model_short, style=Theme.ACCENT)
        text.append(" │ ", style="dim")
        text.append("Tokens: ", style="dim")
        text.append(self.token_usage.format(), style=Theme.WARNING)
        text.append(" │ ", style="dim")
        text.append("Iter: ", style="dim")
        text.append(f"{self.current_iteration}/{self.max_iterations}", style="dim")

        return text
