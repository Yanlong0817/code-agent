"""模型选择命令。"""

from typing import ClassVar

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from code_agent.commands.base import BaseCommand

# 可用的模型列表
AVAILABLE_MODELS = [
    ("claude-sonnet-4-20250514", "Claude Sonnet 4 - 平衡性能与成本"),
    ("claude-opus-4-5-20251101", "Claude Opus 4.5 - 最强大的模型"),
]


class ModelCommand(BaseCommand):
    """切换 Claude 模型的命令。"""

    name: ClassVar[str] = "model"
    description: ClassVar[str] = "切换 Claude 模型"

    async def execute(self, args: str) -> None:
        """执行模型切换。

        Args:
            args: 可选的模型名称，如果为空则显示选择菜单
        """
        console: Console = self.agent.console

        # 如果提供了模型名称，直接切换
        if args.strip():
            model_name = args.strip()
            # 验证模型名称
            valid_models = [m[0] for m in AVAILABLE_MODELS]
            if model_name not in valid_models:
                console.print(f"[red]无效的模型名称：{model_name}[/red]")
                console.print(f"[dim]可用模型：{', '.join(valid_models)}[/dim]")
                return
            self._switch_model(model_name)
            return

        # 显示当前模型
        current_model = self.agent.config.model
        console.print(f"\n[dim]当前模型：[/dim][cyan]{current_model}[/cyan]\n")

        # 显示可用模型表格
        table = Table(title="可用模型", show_header=True, header_style="bold")
        table.add_column("序号", style="dim", width=4)
        table.add_column("模型名称", style="cyan")
        table.add_column("描述")

        for i, (model_id, desc) in enumerate(AVAILABLE_MODELS, 1):
            # 标记当前模型
            marker = " [green]✓[/green]" if model_id == current_model else ""
            table.add_row(str(i), model_id + marker, desc)

        console.print(table)
        console.print()

        # 获取用户选择
        choice = Prompt.ask(
            "[bold]选择模型[/bold]",
            choices=[str(i) for i in range(1, len(AVAILABLE_MODELS) + 1)] + ["q"],
            default="q",
        )

        if choice == "q":
            console.print("[dim]已取消[/dim]")
            return

        # 切换模型
        selected_model = AVAILABLE_MODELS[int(choice) - 1][0]
        self._switch_model(selected_model)

    def _switch_model(self, model_name: str) -> None:
        """切换到指定模型。

        Args:
            model_name: 模型名称
        """
        old_model = self.agent.config.model
        self.agent.config.model = model_name
        status_bar = getattr(self.agent, "status_bar", None)
        if status_bar is not None and hasattr(status_bar, "update_model"):
            status_bar.update_model(model_name)

        if old_model == model_name:
            self.agent.console.print(f"[dim]模型未变更，仍为 {model_name}[/dim]")
        else:
            self.agent.console.print(
                f"[green]已切换模型：[/green]{old_model} → [cyan]{model_name}[/cyan]"
            )
