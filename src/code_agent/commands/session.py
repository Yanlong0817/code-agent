"""会话管理命令。"""

from typing import ClassVar

from rich import box
from rich.prompt import Prompt
from rich.table import Table

from code_agent.commands.base import BaseCommand
from code_agent.session import SessionManager


class SaveCommand(BaseCommand):
    """保存当前会话。"""

    name: ClassVar[str] = "save"
    description: ClassVar[str] = "保存当前会话"

    async def execute(self, args: str) -> None:
        """保存当前会话。

        Args:
            args: 可选的会话标题
        """
        console = self.agent.console
        messages = self.agent.messages

        if not messages:
            console.print("[yellow]对话历史为空，无需保存[/yellow]")
            return

        # 获取会话管理器
        manager = SessionManager()

        # 创建或获取当前会话
        if hasattr(self.agent, "_current_session") and self.agent._current_session:
            session = self.agent._current_session
            # 更新标题（如果提供）
            if args.strip():
                session.metadata.title = args.strip()
        else:
            # 创建新会话
            title = args.strip() if args.strip() else self._generate_title(messages)
            session = manager.create(model=self.agent.config.model, title=title)
            self.agent._current_session = session

        # 更新消息
        session.messages = messages

        # 保存
        path = manager.save(session)

        console.print(
            f"[green]会话已保存[/green]\n"
            f"  ID: [cyan]{session.metadata.id}[/cyan]\n"
            f"  标题: {session.metadata.title or '(无标题)'}\n"
            f"  消息数: {len(messages)}\n"
            f"  文件: [dim]{path}[/dim]"
        )

    def _generate_title(self, messages: list) -> str:
        """从第一条用户消息生成标题。

        Args:
            messages: 消息列表

        Returns:
            生成的标题
        """
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    # 截取前 50 个字符作为标题
                    title = content.replace("\n", " ").strip()
                    if len(title) > 50:
                        title = title[:47] + "..."
                    return title
        return ""


class LoadCommand(BaseCommand):
    """加载历史会话。"""

    name: ClassVar[str] = "load"
    description: ClassVar[str] = "加载历史会话"

    async def execute(self, args: str) -> None:
        """加载会话。

        Args:
            args: 会话 ID 或文件路径，为空则显示会话列表
        """
        console = self.agent.console
        manager = SessionManager()

        args = args.strip()

        if not args:
            # 显示会话列表供选择
            await self._show_session_list(manager)
            return

        # 尝试加载指定会话
        try:
            if args.endswith(".json"):
                # 从路径加载
                session = manager.load_from_path(args)
            else:
                # 从 ID 加载
                session = manager.load(args)

            # 恢复会话
            self.agent.messages = session.messages
            self.agent._current_session = session

            console.print(
                f"[green]会话已加载[/green]\n"
                f"  ID: [cyan]{session.metadata.id}[/cyan]\n"
                f"  标题: {session.metadata.title or '(无标题)'}\n"
                f"  消息数: {len(session.messages)}\n"
                f"  创建于: {session.metadata.created_at}"
            )

        except FileNotFoundError as e:
            console.print(f"[red]{e}[/red]")
        except Exception as e:
            console.print(f"[red]加载会话失败：{e}[/red]")

    async def _show_session_list(self, manager: SessionManager) -> None:
        """显示会话列表供选择。

        Args:
            manager: 会话管理器
        """
        console = self.agent.console

        sessions = manager.list_sessions(limit=10)

        if not sessions:
            console.print("[dim]没有保存的会话[/dim]")
            return

        # 创建表格
        table = Table(
            title="历史会话",
            show_header=True,
            header_style="bold",
            box=box.ROUNDED,
        )
        table.add_column("序号", style="dim", width=4)
        table.add_column("ID", style="cyan")
        table.add_column("标题")
        table.add_column("消息数", justify="right")
        table.add_column("更新时间", style="dim")

        for i, s in enumerate(sessions, 1):
            # 格式化时间
            updated = s.updated_at[:16].replace("T", " ") if s.updated_at else ""
            table.add_row(
                str(i),
                s.id,
                s.title or "(无标题)",
                str(s.message_count),
                updated,
            )

        console.print()
        console.print(table)
        console.print()

        # 获取用户选择
        choice = Prompt.ask(
            "输入序号加载会话（q 取消）",
            default="q",
        )

        if choice.lower() == "q":
            console.print("[dim]已取消[/dim]")
            return

        try:
            idx = int(choice)
            if 1 <= idx <= len(sessions):
                session = manager.load(sessions[idx - 1].id)
                self.agent.messages = session.messages
                self.agent._current_session = session

                console.print(
                    f"[green]会话已加载：[/green]{session.metadata.title or session.metadata.id}"
                )
            else:
                console.print("[red]无效的选择[/red]")
        except ValueError:
            console.print("[red]请输入有效的数字[/red]")


class SessionsCommand(BaseCommand):
    """列出所有会话。"""

    name: ClassVar[str] = "sessions"
    description: ClassVar[str] = "列出保存的会话"

    async def execute(self, args: str) -> None:
        """列出会话。

        Args:
            args: 可选的搜索关键词
        """
        console = self.agent.console
        manager = SessionManager()

        args = args.strip()

        if args:
            # 搜索会话
            sessions = manager.search(args)
            title = f"搜索结果：{args}"
        else:
            sessions = manager.list_sessions(limit=20)
            title = "历史会话"

        if not sessions:
            if args:
                console.print(f"[dim]未找到包含 '{args}' 的会话[/dim]")
            else:
                console.print("[dim]没有保存的会话[/dim]")
            return

        # 创建表格
        table = Table(
            title=title,
            show_header=True,
            header_style="bold",
            box=box.ROUNDED,
        )
        table.add_column("ID", style="cyan")
        table.add_column("标题")
        table.add_column("模型", style="dim")
        table.add_column("消息数", justify="right")
        table.add_column("更新时间", style="dim")

        for s in sessions:
            updated = s.updated_at[:16].replace("T", " ") if s.updated_at else ""
            # 简化模型名
            model = s.model.split("-")[0] if s.model else ""
            table.add_row(
                s.id,
                s.title or "(无标题)",
                model,
                str(s.message_count),
                updated,
            )

        console.print()
        console.print(table)
        console.print()
        console.print(f"[dim]共 {len(sessions)} 个会话。使用 /load <ID> 加载会话[/dim]")
