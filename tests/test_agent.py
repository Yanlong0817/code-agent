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
        model="claude-sonnet-4-20250514",
    )
    agent.status_bar = StatusBar(
        model="claude-sonnet-4-20250514",
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
    # context_limit 默认 200k，阈值 80%
    assert agent._should_compact_context(150_000) is False
    assert agent._should_compact_context(160_000) is True


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
        content=[SimpleNamespace(type="text", text="这是压缩摘要")],
    )
    agent.client = SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock(return_value=summary_response))
    )

    await agent._compact_context(reason="post_turn")

    assert len(agent.messages) == 1 + agent.config.auto_compact_keep_recent_messages
    assert agent.messages[1:] == original_messages[
        -agent.config.auto_compact_keep_recent_messages :
    ]
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
