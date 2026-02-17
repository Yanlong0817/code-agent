"""文件操作工具：Read、Write、Edit、ApplyPatch、Undo、Insert、Glob、Grep。"""

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, Field

from code_agent.safety import confirm_dangerous_action, get_safety_checker
from code_agent.tools.base import BaseTool
from code_agent.utils.diff import generate_unified_diff

HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class _PatchHunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str]


@dataclass
class _FilePatch:
    old_path: str | None
    new_path: str | None
    hunks: list[_PatchHunk]


@dataclass
class _PatchOperation:
    action: Literal["create", "update", "delete"]
    path: Path
    old_content: str
    new_content: str


@dataclass
class FileCheckpoint:
    """文件变更检查点。"""

    path: Path
    existed_before: bool
    content_before: str
    reason: str


class CheckpointStore:
    """按时间顺序保存文件快照，用于回滚。"""

    def __init__(self, max_entries: int = 500) -> None:
        self._entries: list[FileCheckpoint] = []
        self._max_entries = max_entries

    def create(self, path: Path, reason: str) -> None:
        """记录一个新检查点。"""
        existed_before = path.exists()
        if existed_before:
            if not path.is_file():
                raise ValueError(f"检查点目标不是文件：{path}")
            with open(path, encoding="utf-8", errors="replace") as f:
                content_before = f.read()
        else:
            content_before = ""

        self._entries.append(
            FileCheckpoint(
                path=path,
                existed_before=existed_before,
                content_before=content_before,
                reason=reason,
            )
        )
        if len(self._entries) > self._max_entries:
            self._entries.pop(0)

    def pop(self, path: Path | None = None) -> FileCheckpoint | None:
        """弹出最新检查点，可选按路径过滤。"""
        if not self._entries:
            return None
        if path is None:
            return self._entries.pop()

        for idx in range(len(self._entries) - 1, -1, -1):
            if self._entries[idx].path == path:
                return self._entries.pop(idx)
        return None

    def size(self) -> int:
        """当前检查点数量。"""
        return len(self._entries)


class _PathGuardedTool(BaseTool):
    """带工作目录隔离和敏感文件检查的工具基类。"""

    def __init__(
        self,
        working_directory: str | Path | None = None,
        checkpoint_store: CheckpointStore | None = None,
    ) -> None:
        self._working_directory = (
            Path(working_directory).expanduser().resolve(strict=False)
            if working_directory is not None
            else None
        )
        self._checkpoint_store = checkpoint_store or CheckpointStore()

    def _resolve_path(self, raw_path: str) -> Path:
        """将输入路径解析为绝对路径，并校验是否在工作目录内。"""
        path = Path(raw_path).expanduser()

        if not path.is_absolute():
            base = self._working_directory or Path.cwd()
            path = base / path

        resolved = path.resolve(strict=False)
        self._ensure_within_workspace(resolved)
        return resolved

    def _ensure_within_workspace(self, path: Path) -> None:
        """校验路径是否在工作目录边界内。"""
        if self._working_directory is None:
            return

        if path != self._working_directory and self._working_directory not in path.parents:
            raise PermissionError(f"路径超出工作目录范围：{path}")

    def _confirm_sensitive_path(self, path: Path, operation: str) -> None:
        """访问敏感路径时要求用户确认。"""
        check = get_safety_checker().check_file_access(str(path), operation=operation)
        if check.is_dangerous and not confirm_dangerous_action(
            check, f"{operation} 文件", str(path)
        ):
            raise PermissionError(f"[已取消] 用户拒绝{operation}敏感文件：{path}")

    def _create_checkpoint(self, path: Path, reason: str) -> None:
        """记录文件检查点，用于后续回滚。"""
        self._checkpoint_store.create(path, reason)


class ReadTool(_PathGuardedTool):
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
        path = self._resolve_path(file_path)
        self._confirm_sensitive_path(path, "读取")

        if not path.exists():
            raise FileNotFoundError(f"文件未找到：{path}")

        if not path.is_file():
            raise ValueError(f"路径不是文件：{path}")

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


class WriteTool(_PathGuardedTool):
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
        path = self._resolve_path(file_path)
        self._confirm_sensitive_path(path, "写入")
        self._create_checkpoint(path, "Write")

        # 必要时创建父目录
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"成功写入 {len(content)} 字节到 {path}"


class EditTool(_PathGuardedTool):
    """通过替换文本字符串编辑文件。"""

    name: ClassVar[str] = "Edit"
    description: ClassVar[str] = (
        "在文件中执行精确的字符串替换。除非 replace_all 为 True，否则 old_string 必须在文件中唯一。"
        "支持 preview 模式：设置 preview=True 可以先查看修改预览（diff），不实际修改文件。"
    )

    class Input(BaseModel):
        file_path: str = Field(description="要编辑的文件的绝对路径")
        old_string: str = Field(description="要替换的精确文本")
        new_string: str = Field(description="替换后的文本")
        replace_all: bool = Field(default=False, description="如果为 True，替换所有匹配项")
        preview: bool = Field(
            default=False,
            description="如果为 True，仅显示修改预览（diff），不实际修改文件",
        )

    async def execute(  # type: ignore[override]
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        preview: bool = False,
    ) -> str:
        """替换文件中的文本。

        Args:
            file_path: 文件的绝对路径
            old_string: 要查找和替换的文本
            new_string: 替换文本
            replace_all: 如果为 True，替换所有匹配项
            preview: 如果为 True，仅显示修改预览（diff），不实际修改文件

        Returns:
            包含替换次数和 diff 的成功消息，或预览模式下的 diff

        Raises:
            FileNotFoundError: 如果文件不存在
            ValueError: 如果 old_string 未找到或不唯一
        """
        path = self._resolve_path(file_path)
        self._confirm_sensitive_path(path, "编辑")

        if not path.exists():
            raise FileNotFoundError(f"文件未找到：{path}")

        with open(path, encoding="utf-8") as f:
            content = f.read()

        # 检查匹配次数
        count = content.count(old_string)

        if count == 0:
            raise ValueError(f"未找到精确匹配：{old_string[:100]}...")

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

        # 生成 diff
        diff_output = generate_unified_diff(content, new_content, file_path)

        # 如果是预览模式，返回 diff 不实际修改
        if preview:
            return (
                f"[预览模式] 将进行以下修改：\n\n{diff_output}\n\n使用 preview=False 执行实际修改"
            )

        # 实际写入文件
        self._create_checkpoint(path, "Edit")
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        replaced_count = count if replace_all else 1
        return f"成功在 {file_path} 中替换了 {replaced_count} 处\n\n修改详情：\n{diff_output}"


class ApplyPatchTool(_PathGuardedTool):
    """应用 unified diff 补丁。"""

    name: ClassVar[str] = "ApplyPatch"
    description: ClassVar[str] = (
        "将 unified diff 补丁应用到文件。支持新增、修改、删除文件，"
        "并遵循工作目录边界和敏感文件安全确认。"
    )

    class Input(BaseModel):
        patch: str = Field(description="要应用的 unified diff 补丁文本")
        dry_run: bool = Field(default=False, description="如果为 True，仅验证并预览，不实际写入")

    async def execute(self, patch: str, dry_run: bool = False) -> str:  # type: ignore[override]
        """应用补丁。"""
        file_patches = self._parse_patch(patch)
        if not file_patches:
            raise ValueError("补丁中未找到可应用的文件变更")

        operations: list[_PatchOperation] = []

        for file_patch in file_patches:
            # /dev/null <-> path：新增或删除
            # path <-> path：修改（暂不支持重命名）
            if (
                file_patch.old_path
                and file_patch.new_path
                and file_patch.old_path != file_patch.new_path
            ):
                raise ValueError(
                    f"暂不支持重命名补丁：{file_patch.old_path} -> {file_patch.new_path}"
                )

            target_raw_path = file_patch.new_path or file_patch.old_path
            if target_raw_path is None:
                raise ValueError("无效补丁：old_path 和 new_path 不能同时为空")

            target_path = self._resolve_path(target_raw_path)

            if file_patch.old_path is None and file_patch.new_path is not None:
                # create
                self._confirm_sensitive_path(target_path, "写入")
                if target_path.exists():
                    raise ValueError(f"新增文件补丁目标已存在：{target_path}")
                new_content = self._build_patched_content([], file_patch.hunks, str(target_path))
                operations.append(
                    _PatchOperation(
                        action="create",
                        path=target_path,
                        old_content="",
                        new_content=new_content,
                    )
                )
                continue

            if file_patch.new_path is None and file_patch.old_path is not None:
                # delete
                self._confirm_sensitive_path(target_path, "删除")
                if not target_path.exists():
                    raise FileNotFoundError(f"删除补丁目标不存在：{target_path}")
                if not target_path.is_file():
                    raise ValueError(f"删除补丁目标不是文件：{target_path}")
                with open(target_path, encoding="utf-8", errors="replace") as f:
                    old_content = f.read()
                new_content = self._build_patched_content(
                    old_content.splitlines(keepends=True),
                    file_patch.hunks,
                    str(target_path),
                )
                if new_content:
                    raise ValueError(f"删除补丁应用后文件内容非空，拒绝删除：{target_path}")
                operations.append(
                    _PatchOperation(
                        action="delete",
                        path=target_path,
                        old_content=old_content,
                        new_content="",
                    )
                )
                continue

            # update
            self._confirm_sensitive_path(target_path, "编辑")
            if not target_path.exists():
                raise FileNotFoundError(f"修改补丁目标不存在：{target_path}")
            if not target_path.is_file():
                raise ValueError(f"修改补丁目标不是文件：{target_path}")
            with open(target_path, encoding="utf-8", errors="replace") as f:
                old_content = f.read()
            new_content = self._build_patched_content(
                old_content.splitlines(keepends=True),
                file_patch.hunks,
                str(target_path),
            )
            operations.append(
                _PatchOperation(
                    action="update",
                    path=target_path,
                    old_content=old_content,
                    new_content=new_content,
                )
            )

        # dry-run: 仅返回变更预览
        if dry_run:
            return self._format_patch_result(operations, dry_run=True)

        # 所有补丁都验证通过后再执行，避免半应用状态
        for op in operations:
            self._create_checkpoint(op.path, f"ApplyPatch:{op.action}")

        for op in operations:
            if op.action == "delete":
                op.path.unlink()
                continue

            op.path.parent.mkdir(parents=True, exist_ok=True)
            with open(op.path, "w", encoding="utf-8") as f:
                f.write(op.new_content)

        return self._format_patch_result(operations, dry_run=False)

    def _build_patched_content(
        self,
        original_lines: list[str],
        hunks: list[_PatchHunk],
        target_path: str,
    ) -> str:
        """将 hunks 应用到原始行，返回新内容。"""
        result: list[str] = []
        cursor = 0

        for hunk in hunks:
            old_start_idx = hunk.old_start - 1
            if hunk.old_start == 0 and hunk.old_count == 0:
                old_start_idx = 0
            if old_start_idx < 0:
                raise ValueError(f"补丁 hunk 起始行无效：{target_path} @ {hunk.old_start}")
            if old_start_idx < cursor:
                raise ValueError(f"补丁 hunk 存在重叠：{target_path} @ {hunk.old_start}")
            if old_start_idx > len(original_lines):
                raise ValueError(f"补丁 hunk 超出文件范围：{target_path} @ {hunk.old_start}")

            result.extend(original_lines[cursor:old_start_idx])
            line_idx = old_start_idx

            for hunk_line in hunk.lines:
                if not hunk_line:
                    continue
                marker = hunk_line[0]
                if marker == "\\":
                    # "\ No newline at end of file" 注释行，不参与内容匹配
                    continue
                if marker not in (" ", "+", "-"):
                    raise ValueError(f"补丁行格式无效：{hunk_line!r}")

                content = hunk_line[1:]
                if marker == " ":
                    if line_idx >= len(original_lines) or original_lines[line_idx] != content:
                        got = (
                            original_lines[line_idx] if line_idx < len(original_lines) else "<EOF>"
                        )
                        raise ValueError(
                            f"补丁上下文不匹配：{target_path}，期望 {content!r}，实际 {got!r}"
                        )
                    result.append(original_lines[line_idx])
                    line_idx += 1
                elif marker == "-":
                    if line_idx >= len(original_lines) or original_lines[line_idx] != content:
                        got = (
                            original_lines[line_idx] if line_idx < len(original_lines) else "<EOF>"
                        )
                        raise ValueError(
                            f"补丁删除行不匹配：{target_path}，期望 {content!r}，实际 {got!r}"
                        )
                    line_idx += 1
                else:  # marker == "+"
                    result.append(content)

            cursor = line_idx

        result.extend(original_lines[cursor:])
        return "".join(result)

    def _parse_patch(self, patch: str) -> list[_FilePatch]:
        """解析 unified diff。"""
        lines = patch.splitlines(keepends=True)
        idx = 0
        files: list[_FilePatch] = []

        while idx < len(lines):
            line = lines[idx]
            if not line.startswith("--- "):
                idx += 1
                continue

            old_path = self._normalize_diff_path(line[4:])
            idx += 1
            if idx >= len(lines) or not lines[idx].startswith("+++ "):
                raise ValueError("补丁格式错误：缺少 '+++ <path>' 行")

            new_path = self._normalize_diff_path(lines[idx][4:])
            idx += 1

            hunks: list[_PatchHunk] = []
            while idx < len(lines):
                current = lines[idx]
                if current.startswith("--- "):
                    break
                if not current.startswith("@@ "):
                    idx += 1
                    continue

                header = current.rstrip("\n")
                match = HUNK_HEADER_RE.match(header)
                if not match:
                    raise ValueError(f"无法解析 hunk 头：{header}")

                old_start = int(match.group(1))
                old_count = int(match.group(2) or "1")
                new_start = int(match.group(3))
                new_count = int(match.group(4) or "1")
                idx += 1

                hunk_lines: list[str] = []
                while idx < len(lines):
                    hunk_line = lines[idx]
                    if hunk_line.startswith("@@ ") or hunk_line.startswith("--- "):
                        break
                    if hunk_line.startswith((" ", "+", "-", "\\")):
                        hunk_lines.append(hunk_line)
                    idx += 1

                hunks.append(
                    _PatchHunk(
                        old_start=old_start,
                        old_count=old_count,
                        new_start=new_start,
                        new_count=new_count,
                        lines=hunk_lines,
                    )
                )

            if not hunks:
                raise ValueError("补丁格式错误：文件变更缺少 hunk")

            files.append(_FilePatch(old_path=old_path, new_path=new_path, hunks=hunks))

        return files

    @staticmethod
    def _normalize_diff_path(raw_path: str) -> str | None:
        """规范化 diff 路径。"""
        token = raw_path.strip().split("\t", 1)[0]
        token = token.split(" ", 1)[0]
        if token == "/dev/null":
            return None
        if token.startswith("a/") or token.startswith("b/"):
            token = token[2:]
        return token

    def _format_patch_result(self, operations: list[_PatchOperation], dry_run: bool) -> str:
        """格式化补丁执行结果。"""
        lines = ["[预览] 补丁验证通过，将执行以下变更：" if dry_run else "补丁应用成功："]
        for op in operations:
            if op.action == "create":
                lines.append(f"- 新增 {op.path}")
            elif op.action == "delete":
                lines.append(f"- 删除 {op.path}")
            else:
                lines.append(f"- 修改 {op.path}")
            diff_output = generate_unified_diff(
                op.old_content,
                op.new_content,
                str(op.path),
                max_lines=120,
            )
            lines.append(diff_output)
        return "\n".join(lines)


class UndoTool(_PathGuardedTool):
    """回滚最近的文件改动。"""

    name: ClassVar[str] = "Undo"
    description: ClassVar[str] = (
        "回滚最近的文件改动检查点。支持按文件路径回滚，默认回滚最近一次改动。"
    )

    class Input(BaseModel):
        file_path: str | None = Field(
            default=None,
            description="可选：仅回滚该文件的最近改动",
        )
        steps: int = Field(
            default=1,
            gt=0,
            le=50,
            description="回滚步数，默认 1",
        )

    async def execute(self, file_path: str | None = None, steps: int = 1) -> str:  # type: ignore[override]
        """执行回滚。"""
        target_path = self._resolve_path(file_path) if file_path else None
        restored: list[Path] = []

        for _ in range(steps):
            checkpoint = self._checkpoint_store.pop(path=target_path)
            if checkpoint is None:
                break

            self._ensure_within_workspace(checkpoint.path)
            self._confirm_sensitive_path(checkpoint.path, "回滚")

            if checkpoint.existed_before:
                checkpoint.path.parent.mkdir(parents=True, exist_ok=True)
                with open(checkpoint.path, "w", encoding="utf-8") as f:
                    f.write(checkpoint.content_before)
            elif checkpoint.path.exists():
                if not checkpoint.path.is_file():
                    raise ValueError(f"无法回滚，路径不是文件：{checkpoint.path}")
                checkpoint.path.unlink()

            restored.append(checkpoint.path)

        if not restored:
            if target_path is not None:
                return f"未找到可回滚的检查点：{target_path}"
            return "没有可回滚的检查点"

        lines = [f"已回滚 {len(restored)} 个检查点："]
        for path in restored:
            lines.append(f"- {path}")

        if self._checkpoint_store.size() > 0:
            lines.append(f"[剩余检查点 {self._checkpoint_store.size()} 个]")

        return "\n".join(lines)


class InsertTool(_PathGuardedTool):
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
        path = self._resolve_path(file_path)
        self._confirm_sensitive_path(path, "插入")

        if not path.exists():
            raise FileNotFoundError(f"文件未找到：{path}")

        with open(path, encoding="utf-8") as f:
            content = f.read()

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        # 验证行号
        if insert_line > total_lines:
            raise ValueError(f"行号 {insert_line} 超出文件范围（文件共 {total_lines} 行）")

        # 处理文件末尾没有换行符的情况，确保“在最后一行后插入”时不会黏连在同一行
        if insert_line == total_lines and total_lines > 0 and not lines[-1].endswith("\n"):
            lines[-1] += "\n"

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

        self._create_checkpoint(path, "Insert")
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        insert_lines_count = insert_text.count("\n")
        location = "文件开头" if insert_line == 0 else f"第 {insert_line} 行后"
        return f"成功在 {file_path} 的{location}插入了 {insert_lines_count} 行"


class ListDirectoryTool(_PathGuardedTool):
    """列出目录内容，支持递归和树形显示。"""

    name: ClassVar[str] = "ListDirectory"
    description: ClassVar[str] = (
        "列出目录内容，返回树形结构。支持递归深度控制和隐藏文件过滤。"
        "适用于了解项目结构、查找文件位置。"
    )

    # 默认忽略的目录
    DEFAULT_IGNORE = {".git", "__pycache__", "node_modules", ".venv", "venv", ".idea", ".vscode"}

    class Input(BaseModel):
        path: str = Field(default=".", description="要列出的目录路径")
        depth: int = Field(default=2, ge=1, le=5, description="递归深度，1 表示只列当前层")
        include_hidden: bool = Field(default=False, description="是否包含隐藏文件（.开头）")
        ignore_patterns: list[str] | None = Field(
            default=None, description="要忽略的目录名列表，默认忽略 .git、__pycache__ 等"
        )

    async def execute(  # type: ignore[override]
        self,
        path: str = ".",
        depth: int = 2,
        include_hidden: bool = False,
        ignore_patterns: list[str] | None = None,
    ) -> str:
        """列出目录内容。

        Args:
            path: 目录路径
            depth: 递归深度
            include_hidden: 是否包含隐藏文件
            ignore_patterns: 要忽略的目录名列表

        Returns:
            树形结构的目录内容
        """
        base_path = self._resolve_path(path)
        self._confirm_sensitive_path(base_path, "访问")

        if not base_path.exists():
            raise FileNotFoundError(f"目录未找到：{base_path}")

        if not base_path.is_dir():
            raise ValueError(f"路径不是目录：{base_path}")

        ignore_set = set(ignore_patterns) if ignore_patterns else self.DEFAULT_IGNORE

        lines: list[str] = []
        file_count = 0
        dir_count = 0
        max_entries = 500  # 限制最大条目数

        def should_include(p: Path) -> bool:
            """判断是否应该包含该路径"""
            name = p.name
            # 隐藏文件检查
            if not include_hidden and name.startswith("."):
                return False
            # 忽略模式检查
            if name in ignore_set:
                return False
            return True

        def build_tree(dir_path: Path, prefix: str, current_depth: int) -> None:
            """递归构建目录树"""
            nonlocal file_count, dir_count

            if current_depth > depth or file_count + dir_count >= max_entries:
                return

            try:
                entries = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            except PermissionError:
                lines.append(f"{prefix}[权限不足]")
                return

            # 过滤条目
            entries = [e for e in entries if should_include(e)]

            for i, entry in enumerate(entries):
                if file_count + dir_count >= max_entries:
                    lines.append(f"{prefix}... (已达到 {max_entries} 条目限制)")
                    return

                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "
                child_prefix = prefix + ("    " if is_last else "│   ")

                if entry.is_dir():
                    dir_count += 1
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    if current_depth < depth:
                        build_tree(entry, child_prefix, current_depth + 1)
                else:
                    file_count += 1
                    # 显示文件大小
                    try:
                        size = entry.stat().st_size
                        size_str = self._format_size(size)
                        lines.append(f"{prefix}{connector}{entry.name}  ({size_str})")
                    except OSError:
                        lines.append(f"{prefix}{connector}{entry.name}")

        # 构建树
        lines.append(f"{base_path.name}/")
        build_tree(base_path, "", 1)

        # 添加统计信息
        summary = f"\n[共 {dir_count} 个目录，{file_count} 个文件]"
        if file_count + dir_count >= max_entries:
            summary += f" (已截断，达到 {max_entries} 条目限制)"

        return "\n".join(lines) + summary

    @staticmethod
    def _format_size(size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        else:
            return f"{size / (1024 * 1024):.1f}MB"


class GlobTool(_PathGuardedTool):
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
        base_path = self._resolve_path(path)
        self._confirm_sensitive_path(base_path, "访问")

        if not base_path.exists():
            raise FileNotFoundError(f"目录未找到：{base_path}")

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


class GrepTool(_PathGuardedTool):
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
        search_path = self._resolve_path(path)
        self._confirm_sensitive_path(search_path, "访问")

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
        cmd.append(str(search_path))

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
