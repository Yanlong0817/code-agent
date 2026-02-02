"""Code Agent - 集成 Claude API 的主 Agent 循环。"""

import json
from typing import Any

import anthropic
from rich.console import Console
from rich.markdown import Markdown

from code_agent.config import Config
from code_agent.tools.base import ToolRegistry
from code_agent.tools.file_ops import EditTool, GlobTool, GrepTool, ReadTool, WriteTool
from code_agent.tools.network import WebFetchTool, WebSearchTool
from code_agent.tools.system import AskUserQuestionTool, BashTool
from code_agent.tools.task import TodoWriteTool


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

        self.client = anthropic.Anthropic(
            api_key=self.config.anthropic_api_key,
            base_url=self.config.anthropic_base_url,
        )
        self.console = Console()
        self.messages: list[dict[str, Any]] = []

        # 初始化工具
        self.registry = ToolRegistry()
        self._register_tools()

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
        self.messages.append({"role": "user", "content": user_input})

        iteration = 0
        final_response = ""

        while iteration < self.config.max_iterations:
            iteration += 1

            if self.config.verbose:
                self.console.print(f"[dim]迭代 {iteration}[/dim]")

            # 调用 Claude API
            response = self._call_api()

            # 处理响应内容
            assistant_content = []
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    # 向用户显示文本
                    self._display_text(block.text)
                    assistant_content.append({"type": "text", "text": block.text})
                    final_response = block.text

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
                break

            # 执行工具调用
            if tool_calls:
                tool_results = await self._execute_tool_calls(tool_calls)
                self.messages.append({"role": "user", "content": tool_results})

        return final_response

    def _call_api(self) -> anthropic.types.Message:
        """使用当前消息调用 Claude API。

        Returns:
            API 响应消息
        """
        return self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self.SYSTEM_PROMPT,
            tools=self.registry.get_schemas(),
            messages=self.messages,
        )

    async def _execute_tool_calls(
        self, tool_calls: list[anthropic.types.ToolUseBlock]
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

            try:
                # 执行工具
                result = await self.registry.execute(tool_name, **tool_input)

                # 如果需要，将结果转换为字符串
                if not isinstance(result, str):
                    result = json.dumps(result, indent=2, ensure_ascii=False)

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

    def _display_text(self, text: str) -> None:
        """向用户显示文本响应。

        Args:
            text: 要显示的文本
        """
        self.console.print()
        self.console.print(Markdown(text))
        self.console.print()

    def reset(self) -> None:
        """重置对话历史。"""
        self.messages = []
