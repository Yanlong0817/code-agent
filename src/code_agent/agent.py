"""Code Agent - 集成 OpenAI API 的主 Agent 循环。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from openai import AsyncOpenAI
from rich.console import Console
from rich.markdown import Markdown

from code_agent.config import Config
from code_agent.logging import get_logger
from code_agent.tools.base import ToolRegistry
from code_agent.tools.file_ops import (
    ApplyPatchTool,
    CheckpointStore,
    EditTool,
    GlobTool,
    GrepTool,
    InsertTool,
    ListDirectoryTool,
    ReadTool,
    UndoTool,
    WriteTool,
)
from code_agent.tools.network import WebFetchTool, WebSearchTool
from code_agent.tools.system import BashTool
from code_agent.ui import StatusBar, ToolDisplay

if TYPE_CHECKING:
    from code_agent.commands import CommandHandler

# 获取模块日志记录器
logger = get_logger("agent")


@dataclass
class _OpenAIToolCall:
    """内部统一的工具调用结构。"""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class _ModelResponse:
    """模型响应的内部表示。"""

    text: str
    tool_calls: list[_OpenAIToolCall]
    input_tokens: int
    output_tokens: int
    stop_reason: str


class CodeAgent:
    """基于 OpenAI 的代码 Agent，具备工具调用能力。"""

    SYSTEM_PROMPT = """你是一个有用的编程助手，可以使用各种工具。
你可以读取、写入和编辑文件，搜索代码库，执行 shell 命令，
获取网页内容，以及搜索网络。

在处理任务时：
1. 在修改文件之前先读取它们
2. 使用 Glob 和 Grep 来探索代码库
3. 需要时使用 Bash 执行命令
4. 当需求不明确时提出澄清问题

始终解释你在做什么以及为什么这样做。"""
    COMPACTION_PROMPT = """请将此前对话历史压缩为可继续工作的摘要，要求：
1. 保留用户目标、约束与偏好。
2. 保留已完成工作、关键决策、错误与修复。
3. 保留后续继续所需的具体上下文（文件路径、命令、参数、结果）。
4. 保留未完成事项与下一步建议。
5. 输出简洁、结构化的中文摘要。"""

    def __init__(self, config: Config | None = None) -> None:
        """初始化 Agent。

        Args:
            config: 配置对象。如果为 None，则从环境变量加载。
        """
        self.config = config or Config.from_env()
        self.config.validate_required()

        logger.info("初始化 CodeAgent，模型: %s", self.config.model)

        self.client = AsyncOpenAI(
            api_key=self.config.openai_api_key,
            base_url=self.config.openai_base_url,
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
        self._last_input_tokens: int = 0

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
        workspace = self.config.working_directory
        checkpoint_store = CheckpointStore()

        # 文件操作
        self.registry.register(ReadTool(working_directory=workspace))
        self.registry.register(
            WriteTool(working_directory=workspace, checkpoint_store=checkpoint_store)
        )
        self.registry.register(
            EditTool(working_directory=workspace, checkpoint_store=checkpoint_store)
        )
        self.registry.register(
            ApplyPatchTool(working_directory=workspace, checkpoint_store=checkpoint_store)
        )
        self.registry.register(
            UndoTool(working_directory=workspace, checkpoint_store=checkpoint_store)
        )
        self.registry.register(
            InsertTool(working_directory=workspace, checkpoint_store=checkpoint_store)
        )
        self.registry.register(ListDirectoryTool(working_directory=workspace))
        self.registry.register(GlobTool(working_directory=workspace))
        self.registry.register(GrepTool(working_directory=workspace))

        # 系统工具
        self.registry.register(BashTool(default_working_dir=workspace))

        # 网络工具
        self.registry.register(WebFetchTool())
        web_search = WebSearchTool(api_key=self.config.tavily_api_key)
        self.registry.register(web_search)

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

            await self._maybe_compact_context(self._last_input_tokens, reason="pre_request")

            if self.config.verbose:
                self.console.print(f"[dim]迭代 {iteration}[/dim]")

            # 调用 OpenAI API
            logger.debug("调用 OpenAI API")
            response = await self._call_api_stream()
            logger.debug("API 响应停止原因: %s", response.stop_reason)

            # 更新 token 使用量
            current_input_tokens = response.input_tokens
            self._last_input_tokens = current_input_tokens
            self.status_bar.update_tokens(
                response.input_tokens,
                response.output_tokens,
            )

            if response.text:
                final_response = response.text

            # 从响应中提取文本和工具调用，保持内部消息格式不变
            assistant_content: list[dict[str, Any]] = []
            if response.text:
                assistant_content.append({"type": "text", "text": response.text})

            for tool_call in response.tool_calls:
                assistant_content.append(
                    {
                        "type": "tool_use",
                        "id": tool_call.id,
                        "name": tool_call.name,
                        "input": tool_call.input,
                    }
                )

            if assistant_content:
                self.messages.append({"role": "assistant", "content": assistant_content})

            # 无工具调用则本轮结束
            if not response.tool_calls:
                await self._maybe_compact_context(current_input_tokens, reason="post_turn")
                logger.info("Agent 完成处理，共 %d 次迭代", iteration)
                self.console.print(self.status_bar.render_simple())
                break

            # 执行工具调用
            tool_results = await self._execute_tool_calls(response.tool_calls)
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

    def _should_compact_context(self, input_tokens: int) -> bool:
        """判断是否需要触发上下文自动压缩。"""
        if not self.config.auto_compact_enabled:
            return False
        if input_tokens <= 0:
            return False
        context_limit = self.status_bar.token_usage.context_limit
        if context_limit <= 0:
            return False
        threshold_tokens = int(context_limit * self.config.auto_compact_threshold)
        return input_tokens >= threshold_tokens

    async def _maybe_compact_context(self, input_tokens: int, reason: str) -> None:
        """在满足条件时尝试进行上下文压缩。"""
        if not self._should_compact_context(input_tokens):
            return
        try:
            await self._compact_context(reason=reason)
        except Exception as e:
            logger.warning("上下文压缩失败: %s", e)

    async def _compact_context(self, reason: str) -> None:
        """压缩历史上下文，保留最近消息以继续对话。"""
        keep_recent = min(self.config.auto_compact_keep_recent_messages, len(self.messages))
        if keep_recent <= 0:
            return
        if len(self.messages) <= keep_recent:
            return

        historical_messages = self.messages[:-keep_recent]
        if not historical_messages:
            return

        summary_messages = historical_messages + [
            {"role": "user", "content": self.COMPACTION_PROMPT}
        ]
        summary_response = await self.client.chat.completions.create(
            model=self.config.model,
            max_tokens=self.config.auto_compact_summary_max_tokens,
            messages=cast(Any, self._to_openai_messages(summary_messages)),
        )

        summary_text = (
            (summary_response.choices[0].message.content or "")
            if getattr(summary_response, "choices", None)
            else ""
        )
        summary_text = summary_text.strip()
        if not summary_text:
            raise ValueError("未能生成可用的上下文摘要")

        summary_message = {
            "role": "user",
            "content": (
                f"[上下文压缩摘要]\n{summary_text}\n\n请在后续回答中将以上内容视为既有历史上下文。"
            ),
        }
        recent_messages = self.messages[-keep_recent:]
        old_count = len(self.messages)
        self.messages = [summary_message, *recent_messages]
        self._last_input_tokens = 0
        self.status_bar.token_usage.reset()

        logger.info("已触发上下文压缩 (%s): %d -> %d 条消息", reason, old_count, len(self.messages))
        compact_msg = (
            f"[dim]上下文已自动压缩（{reason}）："
            f"{old_count} 条历史 -> {len(self.messages)} 条[/dim]"
        )
        self.console.print(compact_msg)

    async def _call_api_stream(self) -> _ModelResponse:
        """调用 OpenAI Chat Completions API。"""
        response = await self.client.chat.completions.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            messages=cast(Any, self._to_openai_messages(self.messages)),
            tools=cast(Any, self._to_openai_tools()),
            tool_choice="auto",
        )

        choice = response.choices[0]
        message = choice.message

        raw_text = message.content or ""
        accumulated_text = self._clean_text(raw_text)
        if accumulated_text:
            self.console.print(Markdown(accumulated_text))

        parsed_tool_calls: list[_OpenAIToolCall] = []
        for index, tool_call in enumerate(message.tool_calls or []):
            tool_name = tool_call.function.name or ""
            if not tool_name:
                continue

            raw_arguments = tool_call.function.arguments or "{}"
            try:
                parsed_arguments = json.loads(raw_arguments) if raw_arguments else {}
            except json.JSONDecodeError:
                logger.warning("工具参数不是合法 JSON，将作为原始字符串传递: %s", raw_arguments)
                parsed_arguments = {"_raw_arguments": raw_arguments}

            if not isinstance(parsed_arguments, dict):
                parsed_arguments = {"_value": parsed_arguments}

            parsed_tool_calls.append(
                _OpenAIToolCall(
                    id=tool_call.id or f"tool_call_{index + 1}",
                    name=tool_name,
                    input=parsed_arguments,
                )
            )

        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        stop_reason = choice.finish_reason or "stop"

        return _ModelResponse(
            text=accumulated_text,
            tool_calls=parsed_tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=stop_reason,
        )

    def _to_openai_tools(self) -> list[dict[str, Any]]:
        """将内部工具 schema 转换为 OpenAI tools 格式。"""
        openai_tools: list[dict[str, Any]] = []
        for schema in self.registry.get_schemas():
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": schema["name"],
                        "description": schema["description"],
                        "parameters": schema.get("input_schema", {}),
                    },
                }
            )
        return openai_tools

    def _to_openai_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """将内部消息格式转换为 OpenAI Chat Completions messages。"""
        openai_messages: list[dict[str, Any]] = [{"role": "system", "content": self.SYSTEM_PROMPT}]

        for message in messages:
            role = message.get("role")
            content = message.get("content")

            if role == "user":
                if isinstance(content, str):
                    openai_messages.append({"role": "user", "content": content})
                    continue

                # user + tool_result（内部格式） -> OpenAI tool 消息
                if isinstance(content, list):
                    for item in content:
                        if not isinstance(item, dict) or item.get("type") != "tool_result":
                            continue
                        tool_call_id = item.get("tool_use_id")
                        if not isinstance(tool_call_id, str) or not tool_call_id:
                            continue
                        tool_content = item.get("content", "")
                        if not isinstance(tool_content, str):
                            try:
                                tool_content = json.dumps(tool_content, ensure_ascii=False)
                            except (TypeError, ValueError):
                                tool_content = str(tool_content)
                        openai_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": tool_content,
                            }
                        )
                continue

            if role == "assistant":
                if isinstance(content, str):
                    openai_messages.append({"role": "assistant", "content": content})
                    continue

                if isinstance(content, list):
                    text_parts: list[str] = []
                    tool_calls: list[dict[str, Any]] = []
                    for item in content:
                        if not isinstance(item, dict):
                            continue
                        item_type = item.get("type")
                        if item_type == "text":
                            text = item.get("text")
                            if isinstance(text, str) and text:
                                text_parts.append(text)
                        elif item_type == "tool_use":
                            tool_name = item.get("name")
                            tool_id = item.get("id")
                            tool_input = item.get("input", {})
                            if (
                                not isinstance(tool_name, str)
                                or not tool_name
                                or not isinstance(tool_id, str)
                                or not tool_id
                            ):
                                continue
                            if not isinstance(tool_input, dict):
                                tool_input = {}
                            tool_calls.append(
                                {
                                    "id": tool_id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": json.dumps(tool_input, ensure_ascii=False),
                                    },
                                }
                            )

                    if text_parts or tool_calls:
                        assistant_message: dict[str, Any] = {
                            "role": "assistant",
                            "content": "\n".join(text_parts) if text_parts else "",
                        }
                        if tool_calls:
                            assistant_message["tool_calls"] = tool_calls
                        openai_messages.append(assistant_message)

        return openai_messages

    async def _execute_tool_calls(self, tool_calls: list[_OpenAIToolCall]) -> list[dict[str, Any]]:
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
        self._last_input_tokens = 0
