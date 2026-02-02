"""Code Agent 命令行入口。"""

import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from code_agent.agent import CodeAgent
from code_agent.config import Config


def main() -> None:
    """CLI 主入口函数。"""
    console = Console()

    # 显示横幅
    console.print(
        Panel.fit(
            "[bold cyan]Code Agent[/bold cyan]\n"
            "[dim]基于 Claude 的智能代码助手[/dim]",
            border_style="cyan",
        )
    )

    try:
        config = Config.from_env()
        config.validate_required()
    except ValueError as e:
        console.print(f"[red]配置错误：{e}[/red]")
        sys.exit(1)

    agent = CodeAgent(config)

    # 检查是否通过命令行参数提供输入
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
        asyncio.run(agent.run(user_input))
        return

    # 交互模式
    console.print("[dim]输入你的请求，或输入 'quit' 退出。[/dim]\n")

    while True:
        try:
            user_input = Prompt.ask("[bold green]>[/bold green]")

            if user_input.lower() in ("quit", "exit", "q"):
                console.print("[dim]再见！[/dim]")
                break

            if not user_input.strip():
                continue

            asyncio.run(agent.run(user_input))

        except KeyboardInterrupt:
            console.print("\n[dim]已中断。输入 'quit' 退出。[/dim]")
        except Exception as e:
            console.print(f"[red]错误：{e}[/red]")


if __name__ == "__main__":
    main()
