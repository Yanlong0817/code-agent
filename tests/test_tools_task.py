"""任务管理工具测试。"""

import pytest

from code_agent.tools.task import TodoItem, TodoWriteTool


class TestTodoItem:
    """TodoItem 模型测试。"""

    def test_create_with_defaults(self) -> None:
        """测试创建带默认值的 TodoItem。"""
        item = TodoItem(content="Test task", activeForm="正在测试")

        assert item.content == "Test task"
        assert item.status == "pending"
        assert item.active_form == "正在测试"

    def test_create_with_status(self) -> None:
        """测试创建指定状态的 TodoItem。"""
        item = TodoItem(content="Test task", status="in_progress", activeForm="正在测试")

        assert item.status == "in_progress"

    def test_alias_active_form(self) -> None:
        """测试 active_form 别名。"""
        item = TodoItem(content="Test", active_form="Testing")
        assert item.active_form == "Testing"


class TestTodoWriteTool:
    """TodoWriteTool 测试。"""

    @pytest.fixture
    def tool(self) -> TodoWriteTool:
        return TodoWriteTool()

    async def test_write_todos(self, tool: TodoWriteTool) -> None:
        """测试写入待办事项。"""
        todos = [
            {"content": "Task 1", "status": "completed", "activeForm": "完成任务 1"},
            {"content": "Task 2", "status": "in_progress", "activeForm": "正在处理任务 2"},
            {"content": "Task 3", "status": "pending", "activeForm": "处理任务 3"},
        ]

        result = await tool.execute(todos)

        assert "1 已完成" in result
        assert "1 进行中" in result
        assert "1 待处理" in result

    async def test_todos_stored(self, tool: TodoWriteTool) -> None:
        """测试待办事项被正确存储。"""
        todos = [
            {"content": "Task 1", "status": "pending", "activeForm": "处理任务 1"},
        ]

        await tool.execute(todos)

        assert len(tool.todos) == 1
        assert tool.todos[0].content == "Task 1"

    async def test_get_current_task(self, tool: TodoWriteTool) -> None:
        """测试获取当前进行中的任务。"""
        todos = [
            {"content": "Task 1", "status": "completed", "activeForm": "完成任务 1"},
            {"content": "Task 2", "status": "in_progress", "activeForm": "正在处理任务 2"},
            {"content": "Task 3", "status": "pending", "activeForm": "处理任务 3"},
        ]

        await tool.execute(todos)

        current = tool.get_current_task()
        assert current is not None
        assert current.content == "Task 2"

    async def test_get_current_task_none(self, tool: TodoWriteTool) -> None:
        """测试无进行中任务时返回 None。"""
        todos = [
            {"content": "Task 1", "status": "completed", "activeForm": "完成任务 1"},
            {"content": "Task 2", "status": "pending", "activeForm": "处理任务 2"},
        ]

        await tool.execute(todos)

        current = tool.get_current_task()
        assert current is None

    async def test_empty_todos(self, tool: TodoWriteTool) -> None:
        """测试空待办列表。"""
        result = await tool.execute([])

        assert "0 已完成" in result
        assert "0 进行中" in result
        assert "0 待处理" in result

    def test_tool_schema(self) -> None:
        """测试工具 schema。"""
        schema = TodoWriteTool.get_schema()

        assert schema["name"] == "TodoWrite"
        assert "input_schema" in schema
        assert "todos" in schema["input_schema"]["properties"]

    async def test_call_with_validation(self, tool: TodoWriteTool) -> None:
        """测试通过 __call__ 调用（带验证）。"""
        todos = [
            TodoItem(content="Test", status="pending", activeForm="Testing"),
        ]

        result = await tool(todos=todos)

        assert "待办事项已更新" in result
