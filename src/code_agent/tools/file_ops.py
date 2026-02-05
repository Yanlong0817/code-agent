"""文件操作工具：Read、Write、Edit、Insert、Glob、Grep。"""

import asyncio
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, Field

from code_agent.tools.base import BaseTool


class ReadTool(BaseTool):
    """读取文件内容，支持行号范围。"""

    name: ClassVar[str] = "Read"
    description: ClassVar[str] = (
        "从文件系统读取文件。返回带行号的文件内容。"
        "支持 offset（正数从头开始，负数从末尾开始）和 limit 参数读取指定行范围。"
    )

    class Input(BaseModel):
        file_path: str = Field(description="要读取的文件的绝对路径")
        offset: int = Field(
            default=0,
            description="开始读取的行号。正数从头开始(0-indexed)，负数从末尾开始(-1为最后一行)",
        )
        limit: int = Field(default=2000, gt=0, le=10000, description="最大读取行数")

    async def execute(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:  # type: ignore[override]
        """读取带行号的文件内容。

        Args:
            file_path: 文件的绝对路径
            offset: 起始行号。正数从头开始（0-indexed），负数从末尾开始（-1 为最后一行）
            limit: 最大读取行数

        Returns:
            带行号前缀的文件内容

        Raises:
            FileNotFoundError: 如果文件不存在
            PermissionError: 如果文件无法读取
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"文件未找到：{file_path}")

        if not path.is_file():
            raise ValueError(f"路径不是文件：{file_path}")

        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)

        # 处理负数 offset（从末尾开始）
        if offset < 0:
            offset = max(0, total_lines + offset)

        # 应用 offset 和 limit
        selected_lines = lines[offset : offset + limit]

        # 格式化行号（显示时从 1 开始）
        result_lines = []
        for i, line in enumerate(selected_lines, start=offset + 1):
            # 截断过长的行
            if len(line) > 2000:
                line = line[:2000] + "...[已截断]\n"
            result_lines.append(f"{i:6d}\t{line.rstrip()}")

        # 添加文件信息
        if not result_lines:
            return f"文件为空或 offset 超出范围（文件共 {total_lines} 行）"

        end_line = offset + len(selected_lines)
        header = f"[文件共 {total_lines} 行，显示第 {offset + 1}-{end_line} 行]\n"
        return header + "\n".join(result_lines)


class WriteTool(BaseTool):
    """写入文件内容，必要时创建目录。"""

    name: ClassVar[str] = "Write"
    description: ClassVar[str] = (
        "将内容写入文件。如果文件不存在则创建，如果存在则覆盖。必要时创建父目录。"
    )

    class Input(BaseModel):
        file_path: str = Field(description="要写入的文件的绝对路径")
        content: str = Field(description="要写入文件的内容")

    async def execute(self, file_path: str, content: str) -> str:  # type: ignore[override]
        """将内容写入文件。

        Args:
            file_path: 文件的绝对路径
            content: 要写入的内容

        Returns:
            成功消息
        """
        path = Path(file_path)

        # 必要时创建父目录
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"成功写入 {len(content)} 字节到 {file_path}"


class EditTool(BaseTool):
    """通过替换文本字符串编辑文件。"""

    name: ClassVar[str] = "Edit"
    description: ClassVar[str] = (
        "在文件中执行精确的字符串替换。除非 replace_all 为 True，否则 old_string 必须在文件中唯一。"
    )

    class Input(BaseModel):
        file_path: str = Field(description="要编辑的文件的绝对路径")
        old_string: str = Field(description="要替换的精确文本")
        new_string: str = Field(description="替换后的文本")
        replace_all: bool = Field(default=False, description="如果为 True，替换所有匹配项")

    async def execute(  # type: ignore[override]
        self, file_path: str, old_string: str, new_string: str, replace_all: bool = False
    ) -> str:
        """替换文件中的文本。

        Args:
            file_path: 文件的绝对路径
            old_string: 要查找和替换的文本
            new_string: 替换文本
            replace_all: 如果为 True，替换所有匹配项

        Returns:
            包含替换次数的成功消息

        Raises:
            FileNotFoundError: 如果文件不存在
            ValueError: 如果 old_string 未找到或不唯一
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"文件未找到：{file_path}")

        with open(path, encoding="utf-8") as f:
            content = f.read()

        # 检查匹配次数
        count = content.count(old_string)

        if count == 0:
            raise ValueError(f"在文件中未找到字符串：{old_string[:100]}...")

        if count > 1 and not replace_all:
            raise ValueError(
                f"字符串在文件中出现 {count} 次。"
                "使用 replace_all=True 替换所有，或提供更多上下文使其唯一。"
            )

        # 执行替换
        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        replaced_count = count if replace_all else 1
        return f"成功在 {file_path} 中替换了 {replaced_count} 处"


class InsertTool(BaseTool):
    """在指定行后插入文本。"""

    name: ClassVar[str] = "Insert"
    description: ClassVar[str] = (
        "在文件的指定行后插入文本。适用于添加新函数、导入语句等场景。"
        "insert_line=0 表示在文件开头插入。"
    )

    class Input(BaseModel):
        file_path: str = Field(description="要编辑的文件的绝对路径")
        insert_line: int = Field(
            ge=0,
            description="在此行后插入文本（1-indexed）。0 表示在文件开头插入",
        )
        insert_text: str = Field(description="要插入的文本内容")

    async def execute(self, file_path: str, insert_line: int, insert_text: str) -> str:  # type: ignore[override]
        """在指定行后插入文本。

        Args:
            file_path: 文件的绝对路径
            insert_line: 在此行后插入（1-indexed，0 表示文件开头）
            insert_text: 要插入的文本

        Returns:
            成功消息

        Raises:
            FileNotFoundError: 如果文件不存在
            ValueError: 如果行号超出范围
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"文件未找到：{file_path}")

        with open(path, encoding="utf-8") as f:
            content = f.read()

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        # 验证行号
        if insert_line > total_lines:
            insert_line = total_lines - 1

        # 确保插入文本以换行符结尾
        if insert_text and not insert_text.endswith("\n"):
            insert_text += "\n"

        # 在指定位置插入
        if insert_line == 0:
            # 在文件开头插入
            new_lines = [insert_text] + lines
        else:
            # 在指定行后插入
            new_lines = lines[:insert_line] + [insert_text] + lines[insert_line:]

        new_content = "".join(new_lines)

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        insert_lines_count = insert_text.count("\n")
        location = "文件开头" if insert_line == 0 else f"第 {insert_line} 行后"
        return f"成功在 {file_path} 的{location}插入了 {insert_lines_count} 行"


class GlobTool(BaseTool):
    """查找匹配 glob 模式的文件。"""

    name: ClassVar[str] = "Glob"
    description: ClassVar[str] = (
        "使用 glob 模式（如 '**/*.py'）进行快速文件模式匹配。返回按修改时间排序的匹配文件路径。"
    )

    class Input(BaseModel):
        pattern: str = Field(description="要匹配的 glob 模式（如 '**/*.py'、'src/**/*.ts'）")
        path: str = Field(default=".", description="要搜索的目录")

    async def execute(self, pattern: str, path: str = ".") -> str:  # type: ignore[override]
        """查找匹配 glob 模式的文件。

        Args:
            pattern: Glob 模式
            path: 搜索的基础目录

        Returns:
            换行分隔的匹配文件路径列表
        """
        base_path = Path(path).resolve()  # 获取绝对路径，转化成Path对象

        if not base_path.exists():
            raise FileNotFoundError(f"目录未找到：{path}")

        # 查找匹配的文件
        matches = list(base_path.glob(pattern))

        # 仅保留文件并按修改时间排序（最新优先）
        files = [f for f in matches if f.is_file()]
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        # 返回相对路径
        result = []
        for f in files[:1000]:  # 限制结果数量
            try:
                rel_path = f.relative_to(base_path)
                result.append(str(rel_path))
            except ValueError:
                result.append(str(f))

        if not result:
            return f"未找到匹配模式的文件：{pattern}"

        return "\n".join(result)


class GrepTool(BaseTool):
    """使用 ripgrep 搜索文件内容。"""

    name: ClassVar[str] = "Grep"
    description: ClassVar[str] = (
        "使用正则表达式模式搜索文件内容（基于 ripgrep）。"
        "支持按文件类型或 glob 模式过滤。默认返回匹配的文件列表。"
    )

    class Input(BaseModel):
        pattern: str = Field(description="要搜索的正则表达式模式")
        path: str = Field(default=".", description="要搜索的文件或目录")
        glob: str | None = Field(default=None, description="用于过滤文件的 glob 模式（如 '*.py'）")
        file_type: str | None = Field(default=None, description="要搜索的文件类型（如 'py'、'js'）")
        output_mode: Literal["content", "files_with_matches", "count"] = Field(
            default="files_with_matches",
            description="输出模式：content 显示行，files_with_matches 显示路径，count 显示计数",
        )
        context_lines: int = Field(default=0, ge=0, le=10, description="匹配周围的上下文行数")
        case_insensitive: bool = Field(default=False, description="不区分大小写搜索")
        max_results: int = Field(default=100, gt=0, le=1000, description="最大返回结果数")

    async def execute(  # type: ignore[override]
        self,
        pattern: str,
        path: str = ".",
        glob: str | None = None,
        file_type: str | None = None,
        output_mode: str = "files_with_matches",
        context_lines: int = 0,
        case_insensitive: bool = False,
        max_results: int = 100,
    ) -> str:
        """使用 ripgrep 搜索文件。

        Args:
            pattern: 正则表达式模式
            path: 搜索路径
            glob: 文件 glob 过滤器
            file_type: 文件类型过滤器
            output_mode: 输出格式
            context_lines: 匹配周围的上下文行数
            case_insensitive: 不区分大小写标志
            max_results: 最大结果数限制

        Returns:
            基于 output_mode 的搜索结果
        """
        # 构建 ripgrep 命令
        cmd = ["rg", "--no-heading"]

        # 支持三种输出模式
        if output_mode == "files_with_matches":
            cmd.append("-l")  # 只显示匹配的文件名
        elif output_mode == "count":
            cmd.append("-c")  # 显示每个文件的匹配计数
        else:
            cmd.append("-n")  # 显示匹配内容和行号

        if context_lines > 0 and output_mode == "content":  # 显示前后三行上下文
            cmd.extend(["-C", str(context_lines)])

        if case_insensitive:  # 忽略大小写
            cmd.append("-i")

        if glob:
            cmd.extend(["--glob", glob])

        if file_type:  # 按文件类型过滤
            cmd.extend(["-t", file_type])

        cmd.extend(["-m", str(max_results)])  # 限制最大返回结果数
        cmd.append(pattern)
        cmd.append(path)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            if proc.returncode == 1:
                # 未找到匹配
                return f"未找到匹配模式的内容：{pattern}"
            elif proc.returncode != 0:
                # 使用 errors="replace" 处理无效 UTF-8 字节序列
                error_msg = stderr.decode(errors="replace").strip()
                if "not found" in error_msg.lower() or "command not found" in error_msg.lower():
                    raise RuntimeError("ripgrep (rg) 未安装。请先安装它。")
                raise RuntimeError(f"ripgrep 错误：{error_msg}")

            # 使用 errors="replace" 处理无效 UTF-8 字节序列，避免 surrogate 字符
            return stdout.decode(errors="replace").strip()

        except FileNotFoundError:
            raise RuntimeError("ripgrep (rg) 未安装。请先安装它。")
        except TimeoutError:
            raise RuntimeError("搜索超时（30 秒）")
