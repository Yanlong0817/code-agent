"""Agent 核心流程测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from code_agent.agent import CodeAgent
from code_agent.ui.status_bar import StatusBar


def _make_agent_for_unit_tests() -> CodeAgent:
    """构造仅用于单元测试的轻量 Agent 实例。"""
    agent = CodeAgent.__new__(CodeAgent)
    agent.config = SimpleNamespace(
        auto_compact_enabled=True,
        auto_compact_threshold=0.8,
        auto_compact_keep_recent_messages=4,
        auto_compact_summary_max_tokens=512,
        model="gpt-4.1",
        max_tokens=4096,
    )
    agent.status_bar = StatusBar(
        model="gpt-4.1",
        max_tokens=4096,
        max_iterations=50,
    )
    agent.console = MagicMock()
    agent.messages = []
    agent._last_input_tokens = 0
    return agent


def test_should_compact_context_threshold() -> None:
    """测试上下文压缩阈值判断。"""
    agent = _make_agent_for_unit_tests()
    threshold = int(agent.status_bar.token_usage.context_limit * 0.8)
    assert agent._should_compact_context(threshold - 1) is False
    assert agent._should_compact_context(threshold) is True


async def test_compact_context_rewrites_history() -> None:
    """测试压缩后历史会被替换为摘要 + 最近消息。"""
    agent = _make_agent_for_unit_tests()
    original_messages = [
        (
            {"role": "user", "content": f"user-{i}"}
            if i % 2 == 0
            else {"role": "assistant", "content": f"assistant-{i}"}
        )
        for i in range(10)
    ]
    agent.messages = original_messages.copy()
    agent._last_input_tokens = 12345
    agent.status_bar.update_tokens(1000, 200)

    summary_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="这是压缩摘要"))],
    )
    agent.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(return_value=summary_response))
        )
    )

    await agent._compact_context(reason="post_turn")

    assert len(agent.messages) == 1 + agent.config.auto_compact_keep_recent_messages
    assert (
        agent.messages[1:] == original_messages[-agent.config.auto_compact_keep_recent_messages :]
    )
    assert "[上下文压缩摘要]" in agent.messages[0]["content"]
    assert agent._last_input_tokens == 0
    assert agent.status_bar.token_usage.input_tokens == 0
    assert agent.status_bar.token_usage.output_tokens == 0


async def test_maybe_compact_context_swallow_errors() -> None:
    """测试压缩异常不会向上抛出。"""
    agent = _make_agent_for_unit_tests()
    agent._compact_context = AsyncMock(side_effect=RuntimeError("boom"))

    await agent._maybe_compact_context(180_000, reason="post_turn")

    agent._compact_context.assert_called_once_with(reason="post_turn")


async def test_call_api_stream_enables_include_usage() -> None:
    """测试流式请求显式开启 usage，并正确读取 token 统计。"""
    agent = _make_agent_for_unit_tests()
    agent.messages = [{"role": "user", "content": "hello"}]
    agent._to_openai_messages = MagicMock(return_value=[{"role": "user", "content": "hello"}])  # type: ignore[method-assign]
    agent._to_openai_tools = MagicMock(return_value=[])  # type: ignore[method-assign]

    completion = SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(tool_calls=[]))],
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=7),
    )

    class _FakeStream:
        def __init__(self, final_completion: SimpleNamespace) -> None:
            self._final_completion = final_completion
            self._events = [SimpleNamespace(type="content.delta", delta="Hello")]
            self._index = 0

        async def __aenter__(self) -> "_FakeStream":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        def __aiter__(self) -> "_FakeStream":
            return self

        async def __anext__(self) -> SimpleNamespace:
            if self._index >= len(self._events):
                raise StopAsyncIteration
            event = self._events[self._index]
            self._index += 1
            return event

        async def get_final_completion(self) -> SimpleNamespace:
            return self._final_completion

    stream_mock = MagicMock(return_value=_FakeStream(completion))
    agent.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(stream=stream_mock))
    )

    response = await agent._call_api_stream()

    stream_mock.assert_called_once()
    call_kwargs = stream_mock.call_args.kwargs
    assert call_kwargs["stream_options"] == {"include_usage": True}
    assert response.text == "Hello"
    assert response.input_tokens == 12
    assert response.output_tokens == 7
