"""工具调用显示组件 - Panel + Spinner。"""

import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from code_agent.ui.theme import SPINNER_TEXT, TOOL_ICONS, Theme


@dataclass
class ToolResult:
    """工具执行结果。"""

    tool_name: str
    tool_input: dict[str, Any]
    success: bool
    result: str
    duration: float
    is_error: bool = False


class ToolDisplay:
    """工具调用显示组件。"""

    def __init__(self, console: Console) -> None:
        """初始化工具显示组件。

        Args:
            console: Rich Console 实例
        """
        self.console = console

    @asynccontextmanager
    async def show_spinner(self, tool_name: str) -> AsyncIterator[None]:
        """显示工具执行 Spinner。

        Args:
            tool_name: 工具名称

        Yields:
            None
        """
        spinner_text = SPINNER_TEXT.get(tool_name, f"Running {tool_name}")
        icon = TOOL_ICONS.get(tool_name, "🔧")

        with self.console.status(
            f"[{Theme.ACCENT}]{icon} {spinner_text}...[/{Theme.ACCENT}]",
            spinner="dots",
            spinner_style=Theme.ACCENT,
        ):
            yield

    def render_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        max_width: int = 60,
    ) -> Panel:
        """渲染工具调用面板。

        Args:
            tool_name: 工具名称
            tool_input: 工具输入参数
            max_width: 最大宽度

        Returns:
            Panel 组件
        """
        icon = TOOL_ICONS.get(tool_name, "🔧")

        # 格式化输入参数
        input_text = self._format_input(tool_input, max_width)

        return Panel(
            input_text,
            title=f"{icon} {tool_name}",
            title_align="left",
            border_style=Theme.TOOL_BORDER,
            box=box.ROUNDED,
            padding=(0, 1),
        )

    def render_tool_result(
        self,
        success: bool,
        duration: float,
        error_msg: str | None = None,
    ) -> Text:
        """渲染工具执行结果。

        Args:
            success: 是否成功
            duration: 执行时间（秒）
            error_msg: 错误信息（如果失败）

        Returns:
            Text 组件
        """
        text = Text()

        if success:
            text.append("   ✓ ", style=Theme.SUCCESS)
            text.append(f"Success ({duration:.1f}s)", style="dim")
        else:
            text.append("   ✗ ", style=Theme.ERROR)
            if error_msg:
                # 截断过长的错误信息
                short_error = error_msg[:50] + "..." if len(error_msg) > 50 else error_msg
                text.append(f"Error: {short_error}", style=Theme.ERROR)
            else:
                text.append("Error", style=Theme.ERROR)

        return text

    def _format_input(self, tool_input: dict[str, Any], max_width: int) -> Text:
        """格式化工具输入参数。

        Args:
            tool_input: 工具输入参数
            max_width: 最大宽度

        Returns:
            格式化后的 Text 对象
        """
        text = Text()

        for key, value in tool_input.items():
            # 格式化值
            if isinstance(value, str):
                # 截断过长的字符串
                if len(value) > max_width:
                    display_value = value[: max_width - 3] + "..."
                else:
                    display_value = value
            else:
                # JSON 序列化其他类型
                json_str = json.dumps(value, ensure_ascii=False)
                if len(json_str) > max_width:
                    display_value = json_str[: max_width - 3] + "..."
                else:
                    display_value = json_str

            text.append(f"{key}: ", style="dim")
            text.append(f"{display_value}\n", style=Theme.SECONDARY)

        # 移除最后的换行符
        if text.plain.endswith("\n"):
            text = Text(text.plain.rstrip("\n"))
            # 重新应用样式
            return self._format_input_styled(tool_input, max_width)

        return text

    def _format_input_styled(self, tool_input: dict[str, Any], max_width: int) -> Text:
        """格式化工具输入参数（带样式）。

        Args:
            tool_input: 工具输入参数
            max_width: 最大宽度

        Returns:
            格式化后的 Text 对象
        """
        lines = []

        for key, value in tool_input.items():
            if isinstance(value, str):
                if len(value) > max_width:
                    display_value = value[: max_width - 3] + "..."
                else:
                    display_value = value
            else:
                json_str = json.dumps(value, ensure_ascii=False)
                if len(json_str) > max_width:
                    display_value = json_str[: max_width - 3] + "..."
                else:
                    display_value = json_str

            lines.append((key, display_value))

        text = Text()
        for i, (key, value) in enumerate(lines):
            text.append(f"{key}: ", style="dim")
            text.append(value, style=Theme.SECONDARY)
            if i < len(lines) - 1:
                text.append("\n")

        return text


@dataclass
class ToolExecutionTracker:
    """工具执行追踪器。"""

    results: list[ToolResult] = field(default_factory=list)
    _start_time: float | None = None

    def start(self) -> None:
        """开始计时。"""
        self._start_time = time.time()

    def stop(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        result: str,
        is_error: bool = False,
    ) -> ToolResult:
        """停止计时并记录结果。

        Args:
            tool_name: 工具名称
            tool_input: 工具输入
            result: 执行结果
            is_error: 是否出错

        Returns:
            ToolResult 对象
        """
        duration = time.time() - (self._start_time or time.time())
        tool_result = ToolResult(
            tool_name=tool_name,
            tool_input=tool_input,
            success=not is_error,
            result=result,
            duration=duration,
            is_error=is_error,
        )
        self.results.append(tool_result)
        self._start_time = None
        return tool_result
