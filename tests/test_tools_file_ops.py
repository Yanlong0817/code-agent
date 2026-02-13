"""文件操作工具测试。"""

from pathlib import Path

import pytest

from code_agent.tools.file_ops import (
    EditTool,
    GlobTool,
    GrepTool,
    InsertTool,
    ReadTool,
    WriteTool,
)


class TestReadTool:
    """ReadTool 测试。"""

    @pytest.fixture
    def tool(self) -> ReadTool:
        return ReadTool()

    @pytest.fixture
    def sample_file(self, tmp_path: Path) -> Path:
        """创建测试文件。"""
        file_path = tmp_path / "sample.txt"
        lines = [f"Line {i}" for i in range(1, 11)]
        file_path.write_text("\n".join(lines))
        return file_path

    async def test_read_file(self, tool: ReadTool, sample_file: Path) -> None:
        """测试读取整个文件。"""
        result = await tool.execute(str(sample_file))

        assert "Line 1" in result
        assert "Line 10" in result
        # 检查行号格式
        assert "     1\t" in result

    async def test_read_with_offset(self, tool: ReadTool, sample_file: Path) -> None:
        """测试使用 offset 读取。"""
        result = await tool.execute(str(sample_file), offset=5)

        # 应该从第 6 行开始（offset=5，显示行号 6）
        assert "Line 6" in result
        # 检查第一行不是 "Line 1"（注意 "Line 10" 包含 "Line 1" 子串）
        first_line = result.split("\n")[0]
        assert "Line 1\t" not in first_line  # 确保第一行不是 Line 1

    async def test_read_with_limit(self, tool: ReadTool, sample_file: Path) -> None:
        """测试使用 limit 读取。"""
        result = await tool.execute(str(sample_file), limit=3)

        assert "Line 1" in result
        assert "Line 3" in result
        assert "Line 4" not in result

    async def test_read_nonexistent_file(self, tool: ReadTool, tmp_path: Path) -> None:
        """测试读取不存在的文件。"""
        with pytest.raises(FileNotFoundError):
            await tool.execute(str(tmp_path / "nonexistent.txt"))

    async def test_read_directory(self, tool: ReadTool, tmp_path: Path) -> None:
        """测试读取目录（应该失败）。"""
        with pytest.raises(ValueError, match="不是文件"):
            await tool.execute(str(tmp_path))

    async def test_read_negative_offset(self, tool: ReadTool, sample_file: Path) -> None:
        """测试负数 offset（从末尾读取）。"""
        result = await tool.execute(str(sample_file), offset=-3)

        # 应该显示最后 3 行（Line 8, 9, 10）
        assert "Line 8" in result
        assert "Line 9" in result
        assert "Line 10" in result
        # Line 7 不应该在结果中（除非在头部信息里）
        lines = result.split("\n")
        content_lines = [line for line in lines if "\tLine" in line]
        assert all("Line 7" not in line for line in content_lines)

    async def test_read_shows_header(self, tool: ReadTool, sample_file: Path) -> None:
        """测试读取结果包含文件信息头。"""
        result = await tool.execute(str(sample_file))

        assert "[文件共" in result
        assert "行]" in result


class TestWriteTool:
    """WriteTool 测试。"""

    @pytest.fixture
    def tool(self) -> WriteTool:
        return WriteTool()

    async def test_write_new_file(self, tool: WriteTool, tmp_path: Path) -> None:
        """测试写入新文件。"""
        file_path = tmp_path / "new_file.txt"
        content = "Hello, World!"

        result = await tool.execute(str(file_path), content)

        assert file_path.exists()
        assert file_path.read_text() == content
        assert "成功写入" in result

    async def test_write_creates_directories(self, tool: WriteTool, tmp_path: Path) -> None:
        """测试写入时创建父目录。"""
        file_path = tmp_path / "nested" / "dir" / "file.txt"

        await tool.execute(str(file_path), "content")

        assert file_path.exists()

    async def test_write_overwrites(self, tool: WriteTool, tmp_path: Path) -> None:
        """测试覆盖已有文件。"""
        file_path = tmp_path / "existing.txt"
        file_path.write_text("old content")

        await tool.execute(str(file_path), "new content")

        assert file_path.read_text() == "new content"


class TestEditTool:
    """EditTool 测试。"""

    @pytest.fixture
    def tool(self) -> EditTool:
        return EditTool()

    @pytest.fixture
    def sample_file(self, tmp_path: Path) -> Path:
        """创建测试文件。"""
        file_path = tmp_path / "code.py"
        file_path.write_text("def hello():\n    print('Hello')\n")
        return file_path

    async def test_replace_single(self, tool: EditTool, sample_file: Path) -> None:
        """测试单次替换。"""
        result = await tool.execute(str(sample_file), old_string="hello", new_string="greet")

        content = sample_file.read_text()
        assert "def greet():" in content
        assert "成功" in result

    async def test_replace_all(self, tool: EditTool, tmp_path: Path) -> None:
        """测试替换所有匹配项。"""
        file_path = tmp_path / "test.txt"
        file_path.write_text("foo bar foo baz foo")

        await tool.execute(str(file_path), old_string="foo", new_string="qux", replace_all=True)

        assert file_path.read_text() == "qux bar qux baz qux"

    async def test_replace_not_unique(self, tool: EditTool, tmp_path: Path) -> None:
        """测试字符串不唯一时的错误。"""
        file_path = tmp_path / "test.txt"
        file_path.write_text("foo foo foo")

        with pytest.raises(ValueError, match="出现 3 次"):
            await tool.execute(str(file_path), old_string="foo", new_string="bar")

    async def test_replace_not_found(self, tool: EditTool, sample_file: Path) -> None:
        """测试字符串未找到。"""
        with pytest.raises(ValueError, match="未找到"):
            await tool.execute(str(sample_file), old_string="nonexistent", new_string="x")

    async def test_replace_nonexistent_file(self, tool: EditTool, tmp_path: Path) -> None:
        """测试编辑不存在的文件。"""
        with pytest.raises(FileNotFoundError):
            await tool.execute(str(tmp_path / "nope.txt"), old_string="a", new_string="b")

    async def test_replace_not_found_shows_context(
        self, tool: EditTool, sample_file: Path
    ) -> None:
        """测试字符串未找到时显示相似上下文。"""
        try:
            await tool.execute(str(sample_file), old_string="def Hello", new_string="x")
        except ValueError as e:
            error_msg = str(e)
            # 应该包含提示信息
            assert "未找到精确匹配" in error_msg


class TestInsertTool:
    """InsertTool 测试。"""

    @pytest.fixture
    def tool(self) -> InsertTool:
        return InsertTool()

    @pytest.fixture
    def sample_file(self, tmp_path: Path) -> Path:
        """创建测试文件。"""
        file_path = tmp_path / "code.py"
        file_path.write_text("line 1\nline 2\nline 3\n")
        return file_path

    async def test_insert_at_beginning(self, tool: InsertTool, sample_file: Path) -> None:
        """测试在文件开头插入。"""
        result = await tool.execute(
            str(sample_file), insert_line=0, insert_text="import os"
        )

        content = sample_file.read_text()
        assert content.startswith("import os\n")
        assert "line 1" in content
        assert "成功" in result
        assert "文件开头" in result

    async def test_insert_after_line(self, tool: InsertTool, sample_file: Path) -> None:
        """测试在指定行后插入。"""
        result = await tool.execute(
            str(sample_file), insert_line=2, insert_text="inserted line"
        )

        content = sample_file.read_text()
        lines = content.splitlines()
        assert lines[0] == "line 1"
        assert lines[1] == "line 2"
        assert lines[2] == "inserted line"
        assert lines[3] == "line 3"
        assert "第 2 行后" in result

    async def test_insert_at_end(self, tool: InsertTool, sample_file: Path) -> None:
        """测试在文件末尾插入。"""
        await tool.execute(
            str(sample_file), insert_line=3, insert_text="line 4"
        )

        content = sample_file.read_text()
        assert "line 4" in content
        lines = content.splitlines()
        assert lines[-1] == "line 4"

    async def test_insert_out_of_range(self, tool: InsertTool, sample_file: Path) -> None:
        """测试行号超出范围。"""
        with pytest.raises(ValueError, match="超出文件范围"):
            await tool.execute(str(sample_file), insert_line=100, insert_text="x")

    async def test_insert_nonexistent_file(self, tool: InsertTool, tmp_path: Path) -> None:
        """测试插入到不存在的文件。"""
        with pytest.raises(FileNotFoundError):
            await tool.execute(
                str(tmp_path / "nope.txt"), insert_line=0, insert_text="x"
            )

    async def test_insert_multiline(self, tool: InsertTool, sample_file: Path) -> None:
        """测试插入多行文本。"""
        result = await tool.execute(
            str(sample_file),
            insert_line=1,
            insert_text="new line 1\nnew line 2\nnew line 3",
        )

        content = sample_file.read_text()
        assert "new line 1" in content
        assert "new line 2" in content
        assert "new line 3" in content
        assert "插入了 3 行" in result


class TestGlobTool:
    """GlobTool 测试。"""

    @pytest.fixture
    def tool(self) -> GlobTool:
        return GlobTool()

    @pytest.fixture
    def sample_dir(self, tmp_path: Path) -> Path:
        """创建测试目录结构。"""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("main")
        (tmp_path / "src" / "utils.py").write_text("utils")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_main.py").write_text("test")
        (tmp_path / "README.md").write_text("readme")
        return tmp_path

    async def test_glob_pattern(self, tool: GlobTool, sample_dir: Path) -> None:
        """测试 glob 模式匹配。"""
        result = await tool.execute("**/*.py", str(sample_dir))

        assert "main.py" in result
        assert "utils.py" in result
        assert "test_main.py" in result
        assert "README.md" not in result

    async def test_glob_specific_dir(self, tool: GlobTool, sample_dir: Path) -> None:
        """测试在特定目录中搜索。"""
        result = await tool.execute("*.py", str(sample_dir / "src"))

        assert "main.py" in result
        assert "test_main.py" not in result

    async def test_glob_no_matches(self, tool: GlobTool, sample_dir: Path) -> None:
        """测试无匹配结果。"""
        result = await tool.execute("*.xyz", str(sample_dir))

        assert "未找到" in result

    async def test_glob_nonexistent_dir(self, tool: GlobTool, tmp_path: Path) -> None:
        """测试在不存在的目录中搜索。"""
        with pytest.raises(FileNotFoundError):
            await tool.execute("*", str(tmp_path / "nonexistent"))


class TestFileWorkspaceIsolation:
    """文件工具工作目录隔离测试。"""

    async def test_read_blocks_outside_workspace(self, tmp_path: Path) -> None:
        """测试读取工作目录外文件会被拒绝。"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        outside_file = tmp_path / "outside.txt"
        outside_file.write_text("outside")

        tool = ReadTool(working_directory=workspace)
        with pytest.raises(PermissionError, match="超出工作目录范围"):
            await tool.execute(str(outside_file))

    async def test_write_relative_path_uses_workspace(self, tmp_path: Path) -> None:
        """测试相对路径会落在工作目录内。"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        tool = WriteTool(working_directory=workspace)
        await tool.execute("nested/notes.txt", "hello")

        output_file = workspace / "nested" / "notes.txt"
        assert output_file.exists()
        assert output_file.read_text() == "hello"

    async def test_sensitive_file_requires_confirmation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """测试访问敏感文件时会要求确认。"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        env_file = workspace / ".env"
        env_file.write_text("SECRET=1")

        monkeypatch.setattr("code_agent.tools.file_ops.confirm_dangerous_action", lambda *_: False)

        tool = ReadTool(working_directory=workspace)
        with pytest.raises(PermissionError, match="用户拒绝"):
            await tool.execute(str(env_file))


def has_ripgrep() -> bool:
    """检查是否安装了 ripgrep。"""
    import shutil

    return shutil.which("rg") is not None


@pytest.mark.skipif(not has_ripgrep(), reason="ripgrep (rg) 未安装")
class TestGrepTool:
    """GrepTool 测试。需要安装 ripgrep。"""

    @pytest.fixture
    def tool(self) -> GrepTool:
        return GrepTool()

    @pytest.fixture
    def sample_dir(self, tmp_path: Path) -> Path:
        """创建测试目录。"""
        (tmp_path / "code.py").write_text("def hello():\n    return 'world'\n")
        (tmp_path / "data.txt").write_text("hello world\nfoo bar\n")
        return tmp_path

    async def test_grep_files_with_matches(self, tool: GrepTool, sample_dir: Path) -> None:
        """测试搜索并返回文件列表。"""
        result = await tool.execute(
            pattern="hello", path=str(sample_dir), output_mode="files_with_matches"
        )

        assert "code.py" in result
        assert "data.txt" in result

    async def test_grep_content(self, tool: GrepTool, sample_dir: Path) -> None:
        """测试搜索并返回内容。"""
        result = await tool.execute(pattern="def", path=str(sample_dir), output_mode="content")

        assert "def hello" in result

    async def test_grep_case_insensitive(self, tool: GrepTool, sample_dir: Path) -> None:
        """测试不区分大小写搜索。"""
        result = await tool.execute(
            pattern="HELLO",
            path=str(sample_dir),
            case_insensitive=True,
            output_mode="files_with_matches",
        )

        assert "code.py" in result or "data.txt" in result

    async def test_grep_no_matches(self, tool: GrepTool, sample_dir: Path) -> None:
        """测试无匹配结果。"""
        result = await tool.execute(
            pattern="xyz_not_found", path=str(sample_dir), output_mode="files_with_matches"
        )

        assert "未找到" in result

    async def test_grep_with_file_type(self, tool: GrepTool, sample_dir: Path) -> None:
        """测试按文件类型过滤。"""
        result = await tool.execute(
            pattern="hello",
            path=str(sample_dir),
            file_type="py",
            output_mode="files_with_matches",
        )

        assert "code.py" in result
        # txt 文件应该被过滤
        lines = result.strip().split("\n")
        assert not any("data.txt" in line for line in lines)
