"""Git 操作工具。"""

import asyncio
from enum import Enum
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

from code_agent.tools.base import BaseTool


class GitOperation(str, Enum):
    """支持的 Git 操作。"""

    STATUS = "status"
    DIFF = "diff"
    LOG = "log"
    BRANCH = "branch"
    ADD = "add"
    COMMIT = "commit"
    CHECKOUT = "checkout"
    PULL = "pull"
    PUSH = "push"
    STASH = "stash"
    SHOW = "show"


class GitTool(BaseTool):
    """执行 Git 操作，比直接使用 Bash 更安全。"""

    name: ClassVar[str] = "Git"
    description: ClassVar[str] = (
        "执行 Git 操作。支持 status、diff、log、branch、add、commit、"
        "checkout、pull、push、stash、show 等操作。比 Bash 更安全，有参数验证。"
    )

    class Input(BaseModel):
        operation: GitOperation = Field(description="Git 操作类型")
        args: str = Field(default="", description="操作参数（如文件路径、分支名等）")
        working_dir: str | None = Field(default=None, description="Git 仓库目录（默认当前目录）")

    async def execute(
        self,
        operation: str,
        args: str = "",
        working_dir: str | None = None,
    ) -> str:
        """执行 Git 操作。

        Args:
            operation: Git 操作类型
            args: 操作参数
            working_dir: 工作目录

        Returns:
            Git 命令输出

        Raises:
            ValueError: 如果操作不支持或参数无效
            RuntimeError: 如果 Git 命令失败
        """
        # 验证操作类型
        try:
            op = GitOperation(operation)
        except ValueError:
            valid_ops = ", ".join([o.value for o in GitOperation])
            raise ValueError(f"不支持的操作：{operation}。支持的操作：{valid_ops}")

        # 验证工作目录
        if working_dir:
            work_path = Path(working_dir)
            if not work_path.exists():
                raise ValueError(f"目录不存在：{working_dir}")
            if not (work_path / ".git").exists() and not self._is_git_dir(work_path):
                raise ValueError(f"不是 Git 仓库：{working_dir}")

        # 构建命令
        command = self._build_command(op, args)

        # 执行命令
        return await self._run_git(command, working_dir)

    def _is_git_dir(self, path: Path) -> bool:
        """检查是否在 Git 仓库中（向上查找）。

        Args:
            path: 检查的路径

        Returns:
            是否在 Git 仓库中
        """
        current = path.resolve()
        while current != current.parent:
            if (current / ".git").exists():
                return True
            current = current.parent
        return False

    def _build_command(self, op: GitOperation, args: str) -> str:
        """构建 Git 命令。

        Args:
            op: Git 操作
            args: 参数

        Returns:
            完整的 Git 命令
        """
        # 基础命令映射
        base_commands = {
            GitOperation.STATUS: "git status",
            GitOperation.DIFF: "git diff",
            GitOperation.LOG: "git log --oneline -20",
            GitOperation.BRANCH: "git branch",
            GitOperation.ADD: "git add",
            GitOperation.COMMIT: "git commit",
            GitOperation.CHECKOUT: "git checkout",
            GitOperation.PULL: "git pull",
            GitOperation.PUSH: "git push",
            GitOperation.STASH: "git stash",
            GitOperation.SHOW: "git show",
        }

        base = base_commands[op]

        # 特殊处理某些命令
        if op == GitOperation.STATUS:
            # status 不需要额外参数，但可以接受
            return f"{base} {args}".strip() if args else f"{base} --short"
        elif op == GitOperation.DIFF:
            # diff 可以接受文件或 commit
            return f"{base} {args}".strip() if args else base
        elif op == GitOperation.LOG:
            # log 可以自定义格式
            if args:
                # 如果有参数，使用完整的 git log
                return f"git log {args}"
            return base
        elif op == GitOperation.BRANCH:
            # branch 可以列出、创建或删除
            return f"{base} {args}".strip() if args else f"{base} -a"
        elif op == GitOperation.ADD:
            # add 需要文件参数
            if not args:
                return f"{base} ."
            return f"{base} {args}"
        elif op == GitOperation.COMMIT:
            # commit 需要消息
            if not args:
                raise ValueError("commit 需要提供消息，使用 -m 'message'")
            # 确保有 -m 参数
            if "-m" not in args and "--message" not in args:
                # 将 args 作为消息
                return f'{base} -m "{args}"'
            return f"{base} {args}"
        elif op == GitOperation.CHECKOUT:
            # checkout 需要分支或文件
            if not args:
                raise ValueError("checkout 需要提供分支名或文件路径")
            return f"{base} {args}"
        elif op == GitOperation.PULL:
            return f"{base} {args}".strip() if args else base
        elif op == GitOperation.PUSH:
            return f"{base} {args}".strip() if args else base
        elif op == GitOperation.STASH:
            # stash 可以是 push、pop、list 等
            return f"{base} {args}".strip() if args else f"{base} list"
        elif op == GitOperation.SHOW:
            # show 可以显示 commit 详情
            return f"{base} {args}".strip() if args else f"{base} --stat"

        return f"{base} {args}".strip()

    async def _run_git(self, command: str, working_dir: str | None) -> str:
        """执行 Git 命令。

        Args:
            command: Git 命令
            working_dir: 工作目录

        Returns:
            命令输出
        """
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            output_parts = []

            if stdout:
                output_parts.append(stdout.decode(errors="replace"))

            if stderr:
                stderr_text = stderr.decode(errors="replace")
                # Git 有时将正常输出放在 stderr
                if stderr_text.strip():
                    # 检查是否是错误
                    if proc.returncode != 0:
                        output_parts.append(f"[错误]\n{stderr_text}")
                    else:
                        output_parts.append(stderr_text)

            output = "\n".join(output_parts).strip()

            if proc.returncode != 0 and not output:
                return f"Git 命令失败，退出码：{proc.returncode}"

            return output if output else "（无输出）"

        except TimeoutError:
            raise TimeoutError("Git 命令超时（30 秒）")
        except Exception as e:
            raise RuntimeError(f"执行 Git 命令失败：{e}")
