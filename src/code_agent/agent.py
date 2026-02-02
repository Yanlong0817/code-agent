"""Code Agent - 集成 Claude API 的主 Agent 循环。"""

import json
from typing import Any

from anthropic import AsyncAnthropic
from rich.console import Console

from code_agent.config import Config
from code_agent.logging import get_logger
from code_agent.tools.base import ToolRegistry
from code_agent.tools.file_ops import EditTool, GlobTool, GrepTool, ReadTool, WriteTool
from code_agent.tools.network import WebFetchTool, WebSearchTool
from code_agent.tools.system import AskUserQuestionTool, BashTool
from code_agent.tools.task import TodoWriteTool

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

        # 初始化工具
        self.registry = ToolRegistry()
        self._register_tools()
        logger.debug("已注册 %d 个工具", len(self.registry.get_all()))

    def _register_tools(self) -> None:
        """注册所有可用工具。"""
        # 文件操作
        self.registry.register(ReadTool())
        self.registry.register(WriteTool())
        self.registry.register(EditTool())
        self.registry.register(GlobTool())
        self.registry.register(GrepTool())

        # 系统工具
        self.registry.register(BashTool())
        self.registry.register(AskUserQuestionTool())

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
            logger.debug("迭代 %d/%d", iteration, self.config.max_iterations)

            if self.config.verbose:
                self.console.print(f"[dim]迭代 {iteration}[/dim]")

            # 调用 Claude API（流式）
            logger.debug("调用 Claude API（流式）")
            response, text_content = await self._call_api_stream()
            logger.debug("API 响应停止原因: %s", response.stop_reason)

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
                break

            # 执行工具调用
            if tool_calls:
                tool_results = await self._execute_tool_calls(tool_calls)
                self.messages.append({"role": "user", "content": tool_results})

        return final_response

    async def _call_api_stream(self) -> tuple[Any, str]:
        """使用流式 API 调用 Claude，实时输出文本。

        Returns:
            (最终消息对象, 累积的文本内容)
        """
        accumulated_text = ""
        self.console.print()  # 开始前换行

        async with self.client.messages.stream(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self.SYSTEM_PROMPT,
            tools=self.registry.get_schemas(),
            messages=self.messages,
        ) as stream:
            # 流式输出文本
            async for text in stream.text_stream:
                self.console.print(text, end="")
                accumulated_text += text

            # 获取最终消息
            response = await stream.get_final_message()

        if accumulated_text:
            self.console.print()  # 结束后换行

        return response, accumulated_text

    async def _execute_tool_calls(
        self, tool_calls: list[Any]
    ) -> list[dict[str, Any]]:
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

            if self.config.verbose:
                self.console.print(f"[cyan]工具：{tool_name}[/cyan]")
                input_str = json.dumps(tool_input, indent=2, ensure_ascii=False)
                self.console.print(f"[dim]输入：{input_str}[/dim]")

            logger.debug("执行工具: %s", tool_name)

            try:
                # 执行工具
                result = await self.registry.execute(tool_name, **tool_input)

                # 如果需要，将结果转换为字符串
                if not isinstance(result, str):
                    result = json.dumps(result, indent=2, ensure_ascii=False)

                logger.debug("工具 %s 执行成功", tool_name)

                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result,
                    }
                )

                if self.config.verbose:
                    self.console.print(f"[green]结果：{result[:200]}...[/green]")

            except Exception as e:
                error_msg = f"执行 {tool_name} 时出错：{str(e)}"
                logger.error("工具执行失败: %s - %s", tool_name, str(e))
                self.console.print(f"[red]{error_msg}[/red]")

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
        """重置对话历史。"""
        self.messages = []
