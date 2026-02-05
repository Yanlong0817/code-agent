"""Code Agent - 集成 Claude API 的主 Agent 循环。"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, cast

from anthropic import AsyncAnthropic
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

from code_agent.config import Config
from code_agent.logging import get_logger
from code_agent.tools.base import ToolRegistry
from code_agent.tools.file_ops import EditTool, GlobTool, GrepTool, InsertTool, ReadTool, WriteTool
from code_agent.tools.network import WebFetchTool, WebSearchTool
from code_agent.tools.system import BashTool
from code_agent.tools.task import TodoWriteTool
from code_agent.ui import StatusBar, ToolDisplay

if TYPE_CHECKING:
    from code_agent.commands import CommandHandler

# 获取模块日志记录器
logger = get_logger("agent")


class CodeAgent:
    """基于 Claude 的代码 Agent，具备工具调用能力。"""

    SYSTEM_PROMPT = """你是一个有用的编程助手，可以使用各种工具。
你可以读取、写入和编辑文件，搜索代码库，执行 shell 命令，
获取网页内容，以及搜索网络。

在处理任务时：
1. 使用 TodoWrite 工具来规划和跟踪复杂任务
2. 在修改文件之前先读取它们
3. 使用 Glob 和 Grep 来探索代码库
4. 需要时使用 Bash 执行命令
5. 当需求不明确时提出澄清问题

始终解释你在做什么以及为什么这样做。"""

    def __init__(self, config: Config | None = None) -> None:
        """初始化 Agent。

        Args:
            config: 配置对象。如果为 None，则从环境变量加载。
        """
        self.config = config or Config.from_env()
        self.config.validate_required()

        logger.info("初始化 CodeAgent，模型: %s", self.config.model)

        self.client = AsyncAnthropic(
            api_key=self.config.anthropic_api_key,
            base_url=self.config.anthropic_base_url,
        )
        self.console = Console()
        self.messages: list[dict[str, Any]] = []

        # 初始化 UI 组件
        self.tool_display = ToolDisplay(self.console)
        self.status_bar = StatusBar(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            max_iterations=self.config.max_iterations,
            console=self.console,
        )

        # 初始化工具
        self.registry = ToolRegistry()
        self._register_tools()
        logger.debug("已注册 %d 个工具", len(self.registry.get_all()))

        # 命令处理器（延迟初始化，避免循环导入）
        self._command_handler: CommandHandler | None = None

        # 当前会话（用于会话管理命令）
        self._current_session: Any = None

    @property
    def command_handler(self) -> CommandHandler:
        """获取命令处理器（延迟初始化）。

        Returns:
            CommandHandler 实例
        """
        if self._command_handler is None:
            from code_agent.commands import CommandHandler

            self._command_handler = CommandHandler(self)
        return self._command_handler

    def _register_tools(self) -> None:
        """注册所有可用工具。"""
        # 文件操作
        self.registry.register(ReadTool())
        self.registry.register(WriteTool())
        self.registry.register(EditTool())
        self.registry.register(InsertTool())
        self.registry.register(GlobTool())
        self.registry.register(GrepTool())

        # 系统工具
        self.registry.register(BashTool())

        # 网络工具
        self.registry.register(WebFetchTool())
        web_search = WebSearchTool(api_key=self.config.tavily_api_key)
        self.registry.register(web_search)

        # 任务管理
        self.registry.register(TodoWriteTool())

    async def run(self, user_input: str) -> str:
        """使用用户输入运行 Agent。

        Args:
            user_input: 用户的消息/请求

        Returns:
            最终的助手响应
        """
        logger.info("开始处理用户请求")
        truncated = user_input[:100] + "..." if len(user_input) > 100 else user_input
        logger.debug("用户输入: %s", truncated)
        self.messages.append({"role": "user", "content": user_input})

        iteration = 0
        final_response = ""

        while iteration < self.config.max_iterations:
            iteration += 1
            self.status_bar.update_iteration(iteration)
            logger.debug("迭代 %d/%d", iteration, self.config.max_iterations)

            if self.config.verbose:
                self.console.print(f"[dim]迭代 {iteration}[/dim]")

            # 调用 Claude API（流式）
            logger.debug("调用 Claude API（流式）")
            response, text_content = await self._call_api_stream()
            logger.debug("API 响应停止原因: %s", response.stop_reason)

            # 更新 token 使用量
            if hasattr(response, "usage"):
                self.status_bar.update_tokens(
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                )

            if text_content:
                final_response = text_content

            # 从响应中提取工具调用
            assistant_content = []
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    tool_calls.append(block)
                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )

            # 将助手消息添加到历史记录
            self.messages.append({"role": "assistant", "content": assistant_content})

            # 检查停止原因
            if response.stop_reason == "end_turn":
                logger.info("Agent 完成处理，共 %d 次迭代", iteration)
                # 显示状态栏
                self.console.print(self.status_bar.render_simple())
                break

            # 执行工具调用
            if tool_calls:
                tool_results = await self._execute_tool_calls(tool_calls)
                self.messages.append({"role": "user", "content": tool_results})

        return final_response

    @staticmethod
    def _clean_text(text: str) -> str:
        """清理文本中的无效 Unicode 字符（surrogate characters）。

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        # 移除 surrogate 字符（U+D800 到 U+DFFF）
        return text.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="replace")

    async def _call_api_stream(self) -> tuple[Any, str]:
        """使用流式 API 调用 Claude，实时渲染 Markdown 输出。

        Returns:
            (最终消息对象, 累积的文本内容)
        """
        accumulated_text = ""

        async with self.client.messages.stream(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self.SYSTEM_PROMPT,
            tools=cast(Any, self.registry.get_schemas()),
            messages=cast(Any, self.messages),
        ) as stream:
            # 使用 Rich Live 实时渲染 Markdown
            with Live(Markdown(""), console=self.console, refresh_per_second=10) as live:
                async for text in stream.text_stream:
                    # 清理可能的无效字符
                    clean_text = self._clean_text(text)
                    accumulated_text += clean_text
                    # 实时更新 Markdown 渲染
                    live.update(Markdown(accumulated_text))

            # 获取最终消息
            response = await stream.get_final_message()

        return response, accumulated_text

    async def _execute_tool_calls(self, tool_calls: list[Any]) -> list[dict[str, Any]]:
        """执行工具调用并返回结果。

        Args:
            tool_calls: API 响应中的工具使用块列表

        Returns:
            用于 API 的工具结果字典列表
        """
        results = []

        for tool_call in tool_calls:
            tool_name = tool_call.name
            tool_input = tool_call.input
            tool_id = tool_call.id

            logger.debug("执行工具: %s", tool_name)

            # 显示工具调用 Panel
            panel = self.tool_display.render_tool_call(tool_name, tool_input)
            self.console.print(panel)

            start_time = time.time()

            try:
                # 使用 Spinner 执行工具
                async with self.tool_display.show_spinner(tool_name):
                    result = await self.registry.execute(tool_name, **tool_input)

                # 如果需要，将结果转换为字符串
                if not isinstance(result, str):
                    try:
                        result = json.dumps(result, indent=2, ensure_ascii=False)
                    except (TypeError, ValueError):
                        # 处理不可序列化的对象
                        result = str(result)

                duration = time.time() - start_time
                logger.debug("工具 %s 执行成功", tool_name)

                # 显示成功结果
                result_text = self.tool_display.render_tool_result(
                    success=True,
                    duration=duration,
                )
                self.console.print(result_text)

                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result,
                    }
                )

            except Exception as e:
                duration = time.time() - start_time
                error_msg = f"执行 {tool_name} 时出错：{str(e)}"
                logger.error("工具执行失败: %s - %s", tool_name, str(e))

                # 显示错误结果
                result_text = self.tool_display.render_tool_result(
                    success=False,
                    duration=duration,
                    error_msg=str(e),
                )
                self.console.print(result_text)

                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": error_msg,
                        "is_error": True,
                    }
                )

        return results

    def reset(self) -> None:
        """重置对话历史和状态。"""
        self.messages = []
        self.status_bar.reset()
        self._current_session = None
