"""系统交互工具：Bash、AskUserQuestion。"""

import asyncio
from typing import Any, ClassVar

from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

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

    async def execute(
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

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
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


class AskUserQuestionTool(BaseTool):
    """交互式向用户提问。"""

    name: ClassVar[str] = "AskUserQuestion"
    description: ClassVar[str] = "向用户提问以收集信息、澄清需求或获取实现选择的决定。"

    class Option(BaseModel):
        label: str = Field(description="此选项的显示文本")
        description: str = Field(default="", description="此选项的说明")

    class Question(BaseModel):
        question: str = Field(description="要问的问题")
        header: str = Field(description="问题的简短标签（最多 12 个字符）")
        options: list["AskUserQuestionTool.Option"] = Field(
            min_length=2, max_length=4, description="可用选项"
        )
        multi_select: bool = Field(default=False, description="允许多选")

    class Input(BaseModel):
        questions: list["AskUserQuestionTool.Question"] = Field(
            min_length=1, max_length=4, description="要问的问题（1-4 个）"
        )

    def __init__(self) -> None:
        self.console = Console()

    async def execute(self, questions: list[dict[str, Any]]) -> dict[str, Any]:
        """提问并收集答案。

        Args:
            questions: 问题字典列表

        Returns:
            问题文本到选择答案的映射字典
        """
        answers = {}

        for q in questions:
            question_text = q["question"]
            header = q.get("header", "问题")
            options = q.get("options", [])
            multi_select = q.get("multi_select", False)

            # 构建选项表格
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column("序号", style="cyan")
            table.add_column("选项")
            table.add_column("说明", style="dim")

            for i, opt in enumerate(options, 1):
                label = opt.get("label", f"选项 {i}")
                desc = opt.get("description", "")
                table.add_row(f"[{i}]", label, desc)

            # 添加"其他"选项
            table.add_row(f"[{len(options) + 1}]", "其他", "提供自定义输入")

            # 显示问题
            self.console.print()
            self.console.print(Panel(question_text, title=header, border_style="blue"))
            self.console.print(table)
            self.console.print()

            if multi_select:
                prompt_text = "输入数字，用逗号分隔（如 1,3）"
            else:
                prompt_text = "输入数字"

            while True:
                choice = Prompt.ask(prompt_text)

                try:
                    if multi_select:
                        indices = [int(x.strip()) for x in choice.split(",")]
                        selected = []
                        for idx in indices:
                            if idx == len(options) + 1:
                                custom = Prompt.ask("输入自定义值")
                                selected.append(custom)
                            elif 1 <= idx <= len(options):
                                selected.append(options[idx - 1].get("label", ""))
                            else:
                                raise ValueError("无效选择")
                        answers[question_text] = ", ".join(selected)
                        break
                    else:
                        idx = int(choice)
                        if idx == len(options) + 1:
                            custom = Prompt.ask("输入自定义值")
                            answers[question_text] = custom
                        elif 1 <= idx <= len(options):
                            answers[question_text] = options[idx - 1].get("label", "")
                        else:
                            raise ValueError("无效选择")
                        break
                except (ValueError, IndexError):
                    self.console.print("[red]输入无效，请重试[/red]")

        return answers
