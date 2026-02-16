"""安全检查模块 - 检测和确认危险操作。"""

import re
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

# 危险命令模式
DANGEROUS_PATTERNS: list[tuple[str, str, str]] = [
    # (正则模式, 危险级别, 说明)
    (r"\brm\s+(-[rfRF]+\s+)*(/|~|\*|\.\.|\.(?:/)?)($|\s)", "high", "删除重要目录或使用通配符"),
    (r"\brm\s+-[rfRF]*\s+\*", "high", "使用 rm 删除通配符匹配的文件"),
    (r"\bsudo\b", "medium", "使用管理员权限执行命令"),
    (r"\bchmod\s+777\b", "medium", "设置过于宽松的文件权限"),
    (r"\bchown\s+-R\b", "medium", "递归更改文件所有者"),
    (r"\bdd\s+.*\bof=/dev/", "high", "直接写入设备"),
    (r"\bmkfs\b", "high", "格式化文件系统"),
    (r">\s*/dev/sd[a-z]", "high", "直接写入磁盘设备"),
    (r"\bshutdown\b|\breboot\b|\bpoweroff\b", "high", "关机或重启系统"),
    (r"\bkill\s+-9\s+(-1|1)\b", "high", "杀死所有进程"),
    (r"\bkillall\b", "medium", "批量杀死进程"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;", "high", "Fork 炸弹"),
    (r"\bcurl\b.*\|\s*(ba)?sh", "high", "从网络下载并执行脚本"),
    (r"\bwget\b.*\|\s*(ba)?sh", "high", "从网络下载并执行脚本"),
    (r"\beval\s+", "medium", "使用 eval 执行动态代码"),
    (r">\s*/etc/", "high", "覆盖系统配置文件"),
    (r"\bgit\s+push\s+.*--force", "medium", "强制推送到远程仓库"),
    (r"\bgit\s+reset\s+--hard", "medium", "硬重置 Git 仓库"),
    (r"\bdrop\s+database\b", "high", "删除数据库"),
    (r"\bdrop\s+table\b", "high", "删除数据表"),
    (r"\btruncate\s+table\b", "high", "清空数据表"),
    (r"\bdelete\s+from\s+\w+\s*;?\s*$", "high", "无条件删除表中所有数据"),
]

# 受保护的文件模式
PROTECTED_FILE_PATTERNS: list[str] = [
    r"\.env$",
    r"\.env\.",
    r"credentials",
    r"secret",
    r"\.pem$",
    r"\.key$",
    r"id_rsa",
    r"id_ed25519",
    r"\.ssh/",
    r"\.gnupg/",
    r"\.aws/",
    r"password",
    r"token",
    r"api[-_]?key",
]


@dataclass
class SafetyCheck:
    """安全检查结果。"""

    is_dangerous: bool
    level: str  # "low", "medium", "high"
    reason: str
    pattern: str | None = None


class SafetyChecker:
    """安全检查器。"""

    def __init__(
        self,
        console: Console | None = None,
        auto_confirm_low: bool = True,
        disabled: bool = False,
    ) -> None:
        """初始化安全检查器。

        Args:
            console: Console 实例
            auto_confirm_low: 自动确认低风险操作
            disabled: 禁用安全检查
        """
        self.console = console or Console()
        self.auto_confirm_low = auto_confirm_low
        self.disabled = disabled

        # 编译正则表达式
        self._patterns = [
            (re.compile(pattern, re.IGNORECASE), level, desc)
            for pattern, level, desc in DANGEROUS_PATTERNS
        ]
        self._protected_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in PROTECTED_FILE_PATTERNS
        ]

    def check_command(self, command: str) -> SafetyCheck:
        """检查命令是否危险。

        Args:
            command: 要检查的命令

        Returns:
            SafetyCheck 结果
        """
        if self.disabled:
            return SafetyCheck(is_dangerous=False, level="low", reason="")

        # 检查危险模式
        for pattern, level, desc in self._patterns:
            if pattern.search(command):
                return SafetyCheck(
                    is_dangerous=True,
                    level=level,
                    reason=desc,
                    pattern=pattern.pattern,
                )

        return SafetyCheck(is_dangerous=False, level="low", reason="")

    def check_file_access(self, path: str, operation: str = "access") -> SafetyCheck:
        """检查文件访问是否涉及敏感文件。

        Args:
            path: 文件路径
            operation: 操作类型

        Returns:
            SafetyCheck 结果
        """
        if self.disabled:
            return SafetyCheck(is_dangerous=False, level="low", reason="")

        for pattern in self._protected_patterns:
            if pattern.search(path):
                return SafetyCheck(
                    is_dangerous=True,
                    level="medium",
                    reason=f"尝试{operation}可能包含敏感信息的文件",
                    pattern=pattern.pattern,
                )

        return SafetyCheck(is_dangerous=False, level="low", reason="")

    def confirm_action(
        self,
        check: SafetyCheck,
        action_description: str,
        command: str | None = None,
    ) -> bool:
        """显示确认提示并获取用户确认。

        Args:
            check: 安全检查结果
            action_description: 操作描述
            command: 可选的命令文本

        Returns:
            用户是否确认执行
        """
        if not check.is_dangerous:
            return True

        if self.auto_confirm_low and check.level == "low":
            return True

        # 根据级别选择样式
        if check.level == "high":
            border_style = "bold red"
            level_text = "[bold red]高风险[/bold red]"
        elif check.level == "medium":
            border_style = "yellow"
            level_text = "[yellow]中风险[/yellow]"
        else:
            border_style = "dim"
            level_text = "[dim]低风险[/dim]"

        # 构建警告内容
        content = f"风险级别：{level_text}\n"
        content += f"原因：{check.reason}\n"
        if command:
            # 截断过长的命令
            cmd_display = command if len(command) < 100 else command[:97] + "..."
            content += f"\n命令：[cyan]{cmd_display}[/cyan]"

        self.console.print()
        self.console.print(
            Panel(
                content,
                title=f"[bold]安全警告：{action_description}[/bold]",
                border_style=border_style,
            )
        )

        return Confirm.ask("[bold]确认执行此操作？[/bold]", default=False)


# 全局安全检查器实例
_checker: SafetyChecker | None = None


def get_safety_checker() -> SafetyChecker:
    """获取全局安全检查器实例。

    Returns:
        SafetyChecker 实例
    """
    global _checker
    if _checker is None:
        _checker = SafetyChecker()
    return _checker


def set_safety_checker(checker: SafetyChecker) -> None:
    """设置全局安全检查器实例。

    Args:
        checker: SafetyChecker 实例
    """
    global _checker
    _checker = checker


def check_command_safety(command: str) -> SafetyCheck:
    """检查命令安全性（便捷函数）。

    Args:
        command: 要检查的命令

    Returns:
        SafetyCheck 结果
    """
    return get_safety_checker().check_command(command)


def confirm_dangerous_action(
    check: SafetyCheck,
    action_description: str,
    command: str | None = None,
) -> bool:
    """确认危险操作（便捷函数）。

    Args:
        check: 安全检查结果
        action_description: 操作描述
        command: 可选的命令文本

    Returns:
        是否确认执行
    """
    return get_safety_checker().confirm_action(check, action_description, command)
