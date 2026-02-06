"""文件差异比较工具模块。"""

from __future__ import annotations

import difflib
from pathlib import Path


def generate_unified_diff(
    old_content: str,
    new_content: str,
    file_path: str | None = None,
    context_lines: int = 3,
    max_lines: int = 500,
) -> str:
    """生成 unified diff 格式的文件差异。

    Args:
        old_content: 原始内容
        new_content: 修改后的内容
        file_path: 文件路径（用于显示文件名，可选）
        context_lines: 上下文行数（默认 3 行）
        max_lines: 最大输出行数（默认 500 行）

    Returns:
        格式化的 unified diff 字符串
    """
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    # 确定文件名显示
    if file_path:
        filename = Path(file_path).name
        fromfile = f"a/{filename}"
        tofile = f"b/{filename}"
    else:
        fromfile = "a/file"
        tofile = "b/file"

    diff_lines = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=fromfile,
        tofile=tofile,
        n=context_lines,
        lineterm="",
    )

    result = list(diff_lines)

    # 限制输出长度
    if len(result) > max_lines:
        result = result[:max_lines]
        result.append(f"\n... [diff 已截断，共 {len(result)} 行变更]")

    return "\n".join(result) if result else "[无差异]"
