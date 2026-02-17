"""状态栏组件。"""

from dataclasses import dataclass, field

from rich import box
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from code_agent.ui.theme import Theme

# 模型上下文窗口大小（token 数）
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    "gpt-4.1": 128000,
    "gpt-4.1-mini": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "default": 128000,
}

# Token 使用警告阈值
TOKEN_WARNING_THRESHOLD = 0.7  # 70%
TOKEN_CRITICAL_THRESHOLD = 0.9  # 90%


@dataclass
class TokenUsage:
    """Token 使用统计。"""

    input_tokens: int = 0
    output_tokens: int = 0
    context_limit: int = 128000
    warnings_shown: set[str] = field(default_factory=set)

    @property
    def total(self) -> int:
        """总 token 数。"""
        return self.input_tokens + self.output_tokens

    @property
    def usage_ratio(self) -> float:
        """使用率（0-1）。"""
        if self.context_limit <= 0:
            return 0
        return self.input_tokens / self.context_limit

    def format(self) -> str:
        """格式化显示。"""
        if self.total < 1000:
            return str(self.total)
        return f"{self.total / 1000:.1f}k"

    def format_input(self) -> str:
        """格式化输入 token 显示。"""
        if self.input_tokens < 1000:
            return str(self.input_tokens)
        return f"{self.input_tokens / 1000:.1f}k"

    def format_context_limit(self) -> str:
        """格式化上下文限制显示。"""
        return f"{self.context_limit // 1000}k"

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
        self.warnings_shown.clear()

    def check_warning(self, console: Console | None = None) -> str | None:
        """检查是否需要显示警告。

        Args:
            console: 可选的 Console 用于直接显示警告

        Returns:
            警告消息，如果不需要警告则返回 None
        """
        ratio = self.usage_ratio

        if ratio >= TOKEN_CRITICAL_THRESHOLD:
            warning_key = "critical"
            if warning_key not in self.warnings_shown:
                self.warnings_shown.add(warning_key)
                msg = (
                    f"[bold red]警告：上下文使用已达 {ratio:.0%}！[/bold red]\n"
                    f"建议使用 [cyan]/clear[/cyan] 清除历史或 "
                    f"[cyan]/save[/cyan] 保存后开始新会话。"
                )
                if console:
                    console.print(f"\n{msg}\n")
                return msg
        elif ratio >= TOKEN_WARNING_THRESHOLD:
            warning_key = "warning"
            if warning_key not in self.warnings_shown:
                self.warnings_shown.add(warning_key)
                msg = (
                    f"[yellow]提示：上下文使用已达 {ratio:.0%}[/yellow]\n"
                    f"[dim]接近上下文限制，可考虑保存会话或清除历史。[/dim]"
                )
                if console:
                    console.print(f"\n{msg}\n")
                return msg

        return None


class StatusBar:
    """底部状态栏组件。"""

    def __init__(
        self,
        model: str,
        max_tokens: int,
        max_iterations: int,
        console: Console | None = None,
    ) -> None:
        """初始化状态栏。

        Args:
            model: 模型名称
            max_tokens: 最大 token 数
            max_iterations: 最大迭代次数
            console: Console 实例用于显示警告
        """
        self.model = model
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations
        self.console = console

        # 获取模型上下文限制
        context_limit = self._get_context_limit(model)
        self.token_usage = TokenUsage(context_limit=context_limit)
        self.current_iteration = 0

    def _get_context_limit(self, model: str) -> int:
        """获取模型的上下文限制。

        Args:
            model: 模型名称

        Returns:
            上下文 token 限制
        """
        # 先尝试完整匹配
        if model in MODEL_CONTEXT_LIMITS:
            return MODEL_CONTEXT_LIMITS[model]

        # 尝试部分匹配
        model_lower = model.lower()
        for key, limit in MODEL_CONTEXT_LIMITS.items():
            if key in model_lower:
                return limit

        return MODEL_CONTEXT_LIMITS["default"]

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

        # 检查并显示警告
        self.token_usage.check_warning(self.console)

    def update_model(self, model: str) -> None:
        """更新模型名称。

        Args:
            model: 新的模型名称
        """
        self.model = model
        self.token_usage.context_limit = self._get_context_limit(model)

    def reset(self) -> None:
        """重置状态栏。"""
        self.token_usage.reset()
        self.current_iteration = 0

    def _get_short_model_name(self) -> str:
        """获取简化的模型名称。"""
        model = self.model.lower()
        if "gpt-4.1-mini" in model:
            return "4.1-mini"
        elif "gpt-4.1" in model:
            return "4.1"
        elif "gpt-4o-mini" in model:
            return "4o-mini"
        elif "gpt-4o" in model:
            return "4o"
        elif "gpt-5" in model:
            return "gpt-5"
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

        # 根据使用率选择颜色
        ratio = self.token_usage.usage_ratio
        if ratio >= TOKEN_CRITICAL_THRESHOLD:
            token_style = "bold red"
        elif ratio >= TOKEN_WARNING_THRESHOLD:
            token_style = Theme.WARNING
        else:
            token_style = Theme.ACCENT

        center.append("Context: ", style="dim")
        center.append(self.token_usage.format_input(), style=token_style)
        center.append(f"/{self.token_usage.format_context_limit()}", style="dim")
        if ratio > 0:
            center.append(f" ({ratio:.0%})", style="dim")
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
        # 根据使用率选择颜色
        ratio = self.token_usage.usage_ratio
        if ratio >= TOKEN_CRITICAL_THRESHOLD:
            token_style = "bold red"
        elif ratio >= TOKEN_WARNING_THRESHOLD:
            token_style = Theme.WARNING
        else:
            token_style = Theme.ACCENT

        text.append(" ◆ ", style=f"bold {Theme.PRIMARY}")
        text.append(model_short, style=Theme.ACCENT)
        text.append(" │ ", style="dim")
        text.append("Context: ", style="dim")
        text.append(self.token_usage.format_input(), style=token_style)
        text.append(f"/{self.token_usage.format_context_limit()}", style="dim")
        if ratio > 0:
            text.append(f" ({ratio:.0%})", style="dim")
        text.append(" │ ", style="dim")
        text.append("Iter: ", style="dim")
        text.append(f"{self.current_iteration}/{self.max_iterations}", style="dim")

        return text
