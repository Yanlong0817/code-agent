"""Code Agent 命令行入口。"""

import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from code_agent.agent import CodeAgent
from code_agent.config import Config
from code_agent.logging import setup_logging


async def run_interactive(agent: CodeAgent, console: Console) -> None:
    """运行交互模式。

    Args:
        agent: CodeAgent 实例
        console: Rich Console 实例
    """
    console.print("[dim]输入你的请求，或输入 'quit' 退出。[/dim]\n")

    while True:
        try:
            # 在线程池中运行同步的 Prompt.ask，避免阻塞事件循环
            user_input = await asyncio.to_thread(Prompt.ask, "[bold green]>[/bold green]")

            if user_input.lower() in ("quit", "exit", "q"):
                console.print("[dim]再见！[/dim]")
                break

            if not user_input.strip():
                continue

            await agent.run(user_input)

        except KeyboardInterrupt:
            console.print("\n[dim]已中断。输入 'quit' 退出。[/dim]")
        except Exception as e:
            console.print(f"[red]错误：{e}[/red]")


def main() -> None:
    """CLI 主入口函数。"""
    console = Console()

    # 显示横幅
    console.print(
        Panel.fit(
            "[bold cyan]Code Agent[/bold cyan]\n[dim]基于 Claude 的智能代码助手[/dim]",
            border_style="cyan",
        )
    )

    try:
        config = Config.from_env()
        config.validate_required()
    except ValueError as e:
        console.print(f"[red]配置错误：{e}[/red]")
        sys.exit(1)

    # 初始化日志系统
    setup_logging(level=config.log_level, log_file=config.log_file)

    agent = CodeAgent(config)

    # 检查是否通过命令行参数提供输入
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
        asyncio.run(agent.run(user_input))
        return

    # 交互模式 - 使用单一事件循环
    asyncio.run(run_interactive(agent, console))


if __name__ == "__main__":
    main()
