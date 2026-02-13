"""系统交互工具：Bash。"""

import asyncio
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

from code_agent.safety import check_command_safety, confirm_dangerous_action
from code_agent.tools.base import BaseTool


class BashTool(BaseTool):
    """执行 shell 命令。"""

    name: ClassVar[str] = "Bash"
    description: ClassVar[str] = (
        "执行带有可选超时的 bash 命令。用于系统操作、git 命令、运行脚本等。"
        "危险命令会在执行前请求用户确认。"
    )

    class Input(BaseModel):
        command: str = Field(description="要执行的 bash 命令")
        timeout: int = Field(
            default=120000,
            gt=0,
            le=600000,
            description="超时时间（毫秒，最大 10 分钟）",
        )
        working_dir: str | None = Field(default=None, description="命令执行的工作目录")

    def __init__(self, default_working_dir: str | Path | None = None) -> None:
        self._default_working_dir = (
            Path(default_working_dir).expanduser().resolve(strict=False)
            if default_working_dir is not None
            else None
        )

    def _is_within_workspace(self, path: Path) -> bool:
        """检查路径是否在默认工作目录边界内。"""
        if self._default_working_dir is None:
            return True
        return path == self._default_working_dir or self._default_working_dir in path.parents

    def _resolve_working_dir(self, working_dir: str | None) -> str | None:
        """解析最终的命令工作目录。"""
        if working_dir is None:
            if self._default_working_dir is None:
                return None
            if not self._default_working_dir.exists():
                raise FileNotFoundError(f"工作目录不存在：{self._default_working_dir}")
            if not self._default_working_dir.is_dir():
                raise ValueError(f"工作目录不是目录：{self._default_working_dir}")
            return str(self._default_working_dir)

        candidate = Path(working_dir).expanduser()
        if not candidate.is_absolute():
            base = self._default_working_dir or Path.cwd()
            candidate = base / candidate

        resolved = candidate.resolve(strict=False)

        if self._default_working_dir is not None and not self._is_within_workspace(resolved):
            raise PermissionError(f"工作目录超出允许范围：{resolved}")

        if not resolved.exists():
            raise FileNotFoundError(f"工作目录不存在：{resolved}")
        if not resolved.is_dir():
            raise ValueError(f"工作目录不是目录：{resolved}")

        return str(resolved)

    async def execute(  # type: ignore[override]
        self,
        command: str,
        timeout: int = 120000,
        working_dir: str | None = None,
    ) -> str:
        """执行 bash 命令。

        Args:
            command: 要执行的 shell 命令
            timeout: 超时时间（毫秒）
            working_dir: 工作目录

        Returns:
            命令输出（stdout + stderr）

        Raises:
            TimeoutError: 如果命令超时
            RuntimeError: 如果命令执行失败
            PermissionError: 如果用户拒绝执行危险命令
        """
        # 安全检查
        safety_check = check_command_safety(command)
        if safety_check.is_dangerous:
            confirmed = confirm_dangerous_action(
                safety_check,
                "执行命令",
                command,
            )
            if not confirmed:
                return "[已取消] 用户拒绝执行此危险命令"

        timeout_seconds = timeout / 1000
        resolved_working_dir = self._resolve_working_dir(working_dir)

        try:
            # 异步创建子进程
            proc = await asyncio.create_subprocess_shell(
                command,  # 传入命令
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=resolved_working_dir,
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)

            output_parts = []

            if stdout:
                output_parts.append(stdout.decode(errors="replace"))

            if stderr:
                stderr_text = stderr.decode(errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"[stderr]\n{stderr_text}")

            output = "\n".join(output_parts).strip()

            # 输出过长时截断
            max_length = 30000
            if len(output) > max_length:
                output = output[:max_length] + "\n...[输出已截断]"

            if proc.returncode != 0:
                return f"退出码 {proc.returncode}\n{output}"

            return output if output else "（无输出）"

        except TimeoutError:
            raise TimeoutError(f"命令超时（{timeout_seconds} 秒）")
