"""Code Agent 命令行入口。"""

import argparse
import asyncio
import sys
from pathlib import Path

from rich.console import Console

from code_agent import __version__
from code_agent.agent import CodeAgent
from code_agent.config import Config
from code_agent.input import InputSession
from code_agent.logging import setup_logging
from code_agent.session import SessionManager
from code_agent.ui import render_banner


def parse_args() -> argparse.Namespace:
    """解析命令行参数。

    Returns:
        解析后的参数
    """
    parser = argparse.ArgumentParser(
        prog="code-agent",
        description="基于 Claude 的智能代码助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  code-agent                          # 交互模式
  code-agent "读取 README.md"          # 单次执行
  code-agent -m claude-opus-4-5-20251101 "你好"    # 指定模型
  code-agent --load 20240101_120000   # 加载会话
  code-agent --continue               # 继续上次会话
        """,
    )

    parser.add_argument(
        "prompt",
        nargs="*",
        help="要执行的提示（如果不提供则进入交互模式）",
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    parser.add_argument(
        "-m",
        "--model",
        type=str,
        help="使用的模型（覆盖配置）",
    )

    parser.add_argument(
        "--load",
        type=str,
        metavar="SESSION",
        help="加载指定的会话（ID 或文件路径）",
    )

    parser.add_argument(
        "-c",
        "--continue",
        dest="continue_session",
        action="store_true",
        help="继续上次的会话",
    )

    parser.add_argument(
        "--max-tokens",
        type=int,
        help="最大输出 token 数（覆盖配置）",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        help="最大迭代次数（覆盖配置）",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细输出",
    )

    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="不显示欢迎横幅",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别（覆盖配置）",
    )

    parser.add_argument(
        "--log-file",
        type=str,
        help="日志文件路径",
    )

    parser.add_argument(
        "-w",
        "--working-dir",
        type=str,
        help="工作目录",
    )

    return parser.parse_args()


async def run_interactive(agent: CodeAgent, console: Console) -> None:
    """运行交互模式。

    Args:
        agent: CodeAgent 实例
        console: Rich Console 实例
    """
    # 使用 agent 的命令处理器
    command_handler = agent.command_handler

    # 创建输入会话
    input_session = InputSession(command_handler.registry)

    while True:
        try:
            # 使用 prompt_toolkit 异步获取输入
            user_input = await input_session.prompt_async()

            if user_input.lower() in ("quit", "exit", "q"):
                console.print("[dim]再见！[/dim]")
                break

            if not user_input.strip():
                continue

            # 检查是否是命令
            if command_handler.is_command(user_input):
                await command_handler.execute(user_input)
                continue

            await agent.run(user_input)

        except EOFError:
            # 处理 Ctrl+D
            console.print("\n[dim]再见！[/dim]")
            break
        except KeyboardInterrupt:
            console.print("\n[dim]已中断。输入 'quit' 退出。[/dim]")
        except Exception as e:
            # 处理可能的编码问题
            error_msg = str(e).encode("utf-8", errors="replace").decode("utf-8")
            console.print(f"[red]错误：{error_msg}[/red]")
            console.print(
                "[dim]*** You may need to add PYTHONIOENCODING=utf-8 to your environment ***[/dim]"
            )


def main() -> None:
    """CLI 主入口函数。"""
    args = parse_args()
    console = Console()

    try:
        config = Config.from_env()

        # 应用命令行参数覆盖
        if args.model:
            config.model = args.model
        if args.max_tokens:
            config.max_tokens = args.max_tokens
        if args.max_iterations:
            config.max_iterations = args.max_iterations
        if args.verbose:
            config.verbose = True
        if args.log_level:
            config.log_level = args.log_level
        if args.log_file:
            config.log_file = args.log_file
        if args.working_dir:
            config.working_directory = Path(args.working_dir)

        config.validate_required()
    except ValueError as e:
        console.print(f"[red]配置错误：{e}[/red]")
        sys.exit(1)

    # 显示欢迎横幅
    if not args.no_banner:
        banner = render_banner(config.model)
        console.print(banner)
        console.print()  # 空行

    # 初始化日志系统
    setup_logging(level=config.log_level, log_file=config.log_file)

    agent = CodeAgent(config)

    # 处理会话加载
    if args.continue_session:
        # 加载最新会话
        manager = SessionManager()
        session = manager.get_latest()
        if session:
            agent.messages = session.messages
            agent._current_session = session
            console.print(f"[dim]已加载会话：{session.metadata.title or session.metadata.id}[/dim]")
        else:
            console.print("[dim]没有可继续的会话[/dim]")
    elif args.load:
        # 加载指定会话
        manager = SessionManager()
        try:
            if args.load.endswith(".json"):
                session = manager.load_from_path(args.load)
            else:
                session = manager.load(args.load)
            agent.messages = session.messages
            agent._current_session = session
            console.print(f"[dim]已加载会话：{session.metadata.title or session.metadata.id}[/dim]")
        except FileNotFoundError:
            console.print(f"[red]会话不存在：{args.load}[/red]")
            sys.exit(1)

    # 检查是否通过命令行参数提供输入
    if args.prompt:
        user_input = " ".join(args.prompt)
        asyncio.run(agent.run(user_input))
        return

    # 交互模式 - 使用单一事件循环
    asyncio.run(run_interactive(agent, console))


if __name__ == "__main__":
    main()
