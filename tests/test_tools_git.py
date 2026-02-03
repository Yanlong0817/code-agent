"""GitTool 测试。"""

import subprocess
from pathlib import Path

import pytest

from code_agent.tools.git import GitOperation, GitTool


def has_git() -> bool:
    """检查是否安装了 Git。"""
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.fixture
def git_tool() -> GitTool:
    """创建 GitTool 实例。"""
    return GitTool()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """创建临时 Git 仓库。"""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # 初始化仓库
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    # 创建初始文件
    (repo_path / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    return repo_path


@pytest.mark.skipif(not has_git(), reason="Git 未安装")
class TestGitTool:
    """GitTool 测试类。"""

    @pytest.mark.asyncio
    async def test_status(self, git_tool: GitTool, git_repo: Path) -> None:
        """测试 git status。"""
        result = await git_tool.execute(
            operation="status",
            working_dir=str(git_repo),
        )
        # 应该显示工作目录干净
        assert "nothing to commit" in result or "无" in result or result.strip() == ""

    @pytest.mark.asyncio
    async def test_status_with_changes(self, git_tool: GitTool, git_repo: Path) -> None:
        """测试有变更时的 git status。"""
        # 创建新文件
        (git_repo / "new_file.txt").write_text("New content")

        result = await git_tool.execute(
            operation="status",
            working_dir=str(git_repo),
        )
        assert "new_file" in result or "Untracked" in result or "?" in result

    @pytest.mark.asyncio
    async def test_log(self, git_tool: GitTool, git_repo: Path) -> None:
        """测试 git log。"""
        result = await git_tool.execute(
            operation="log",
            working_dir=str(git_repo),
        )
        assert "Initial commit" in result

    @pytest.mark.asyncio
    async def test_branch(self, git_tool: GitTool, git_repo: Path) -> None:
        """测试 git branch。"""
        result = await git_tool.execute(
            operation="branch",
            working_dir=str(git_repo),
        )
        # 应该显示 master 或 main 分支
        assert "master" in result or "main" in result

    @pytest.mark.asyncio
    async def test_diff_no_changes(self, git_tool: GitTool, git_repo: Path) -> None:
        """测试无变更时的 git diff。"""
        result = await git_tool.execute(
            operation="diff",
            working_dir=str(git_repo),
        )
        # 无变更时应该是空的或显示无输出
        assert result.strip() == "" or "无输出" in result

    @pytest.mark.asyncio
    async def test_diff_with_changes(self, git_tool: GitTool, git_repo: Path) -> None:
        """测试有变更时的 git diff。"""
        # 修改文件
        (git_repo / "README.md").write_text("# Test Repo\n\nModified content")

        result = await git_tool.execute(
            operation="diff",
            working_dir=str(git_repo),
        )
        assert "Modified content" in result or "README" in result

    @pytest.mark.asyncio
    async def test_add(self, git_tool: GitTool, git_repo: Path) -> None:
        """测试 git add。"""
        # 创建新文件
        (git_repo / "test.txt").write_text("Test content")

        result = await git_tool.execute(
            operation="add",
            args="test.txt",
            working_dir=str(git_repo),
        )
        # add 通常没有输出
        assert "无输出" in result or result.strip() == ""

        # 验证文件已暂存
        status = await git_tool.execute(
            operation="status",
            working_dir=str(git_repo),
        )
        assert "test.txt" in status

    @pytest.mark.asyncio
    async def test_commit(self, git_tool: GitTool, git_repo: Path) -> None:
        """测试 git commit。"""
        # 创建并暂存文件
        (git_repo / "commit_test.txt").write_text("Commit test")
        subprocess.run(
            ["git", "add", "commit_test.txt"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        result = await git_tool.execute(
            operation="commit",
            args="Test commit message",
            working_dir=str(git_repo),
        )
        assert "commit" in result.lower() or "Test commit" in result

    @pytest.mark.asyncio
    async def test_show(self, git_tool: GitTool, git_repo: Path) -> None:
        """测试 git show。"""
        result = await git_tool.execute(
            operation="show",
            working_dir=str(git_repo),
        )
        assert "Initial commit" in result or "README" in result

    @pytest.mark.asyncio
    async def test_invalid_operation(self, git_tool: GitTool, git_repo: Path) -> None:
        """测试无效的操作。"""
        with pytest.raises(ValueError) as exc_info:
            await git_tool.execute(
                operation="invalid_op",
                working_dir=str(git_repo),
            )
        assert "不支持的操作" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_checkout_requires_args(self, git_tool: GitTool, git_repo: Path) -> None:
        """测试 checkout 需要参数。"""
        with pytest.raises(ValueError) as exc_info:
            await git_tool.execute(
                operation="checkout",
                working_dir=str(git_repo),
            )
        assert "需要提供" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_commit_requires_message(self, git_tool: GitTool, git_repo: Path) -> None:
        """测试 commit 需要消息。"""
        with pytest.raises(ValueError) as exc_info:
            await git_tool.execute(
                operation="commit",
                working_dir=str(git_repo),
            )
        assert "需要提供消息" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_working_dir(self, git_tool: GitTool, tmp_path: Path) -> None:
        """测试无效的工作目录。"""
        non_git_dir = tmp_path / "not_a_repo"
        non_git_dir.mkdir()

        with pytest.raises(ValueError) as exc_info:
            await git_tool.execute(
                operation="status",
                working_dir=str(non_git_dir),
            )
        assert "不是 Git 仓库" in str(exc_info.value)

    def test_tool_schema(self, git_tool: GitTool) -> None:
        """测试工具 schema 生成。"""
        schema = git_tool.get_schema()
        assert schema["name"] == "Git"
        assert "description" in schema
        assert "input_schema" in schema
        assert "operation" in schema["input_schema"]["properties"]


class TestGitOperation:
    """GitOperation 枚举测试。"""

    def test_all_operations(self) -> None:
        """测试所有操作值。"""
        expected = {
            "status",
            "diff",
            "log",
            "branch",
            "add",
            "commit",
            "checkout",
            "pull",
            "push",
            "stash",
            "show",
        }
        actual = {op.value for op in GitOperation}
        assert actual == expected
