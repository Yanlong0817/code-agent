"""系统工具测试。"""

import asyncio
from pathlib import Path

import pytest

from code_agent.tools.system import BashTool


class TestBashTool:
    """BashTool 测试。"""

    @pytest.fixture
    def tool(self) -> BashTool:
        return BashTool()

    async def test_simple_command(self, tool: BashTool) -> None:
        """测试简单命令执行。"""
        result = await tool.execute("echo 'hello world'")
        assert "hello world" in result

    async def test_command_with_exit_code(self, tool: BashTool) -> None:
        """测试返回非零退出码的命令。"""
        result = await tool.execute("exit 1")
        assert "退出码 1" in result

    async def test_command_with_stderr(self, tool: BashTool) -> None:
        """测试产生 stderr 的命令。"""
        result = await tool.execute("echo 'error' >&2")
        assert "error" in result
        assert "stderr" in result

    async def test_command_working_dir(self, tool: BashTool, tmp_path: Path) -> None:
        """测试在指定工作目录执行命令。"""
        result = await tool.execute("pwd", working_dir=str(tmp_path))
        assert str(tmp_path) in result

    async def test_command_timeout(self, tool: BashTool) -> None:
        """测试命令超时。"""
        with pytest.raises(TimeoutError):
            await tool.execute("sleep 10", timeout=100)  # 100ms 超时

    async def test_multiline_output(self, tool: BashTool) -> None:
        """测试多行输出。"""
        result = await tool.execute("echo 'line1'; echo 'line2'; echo 'line3'")
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result

    async def test_command_with_pipe(self, tool: BashTool) -> None:
        """测试包含管道的命令。"""
        result = await tool.execute("echo 'hello world' | tr 'a-z' 'A-Z'")
        assert "HELLO WORLD" in result

    async def test_empty_output(self, tool: BashTool) -> None:
        """测试无输出的命令。"""
        result = await tool.execute("true")
        assert "无输出" in result

    async def test_tool_schema(self) -> None:
        """测试工具 schema。"""
        schema = BashTool.get_schema()

        assert schema["name"] == "Bash"
        assert "input_schema" in schema
        assert "command" in schema["input_schema"]["properties"]
        assert "timeout" in schema["input_schema"]["properties"]

    async def test_call_with_validation(self, tool: BashTool) -> None:
        """测试通过 __call__ 调用（带验证）。"""
        result = await tool(command="echo 'test'")
        assert "test" in result


# AskUserQuestionTool 需要交互式输入，不适合自动化测试
# 可以通过 mock 来测试，但这里略过
