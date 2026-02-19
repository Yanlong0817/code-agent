"""自定义命令加载与执行适配。"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from string import Formatter

from code_agent.commands.base import BaseCommand

COMMAND_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
ALLOWED_COMMAND_FIELDS = {"description", "prompt", "requires_args"}


@dataclass(frozen=True)
class CustomCommandSpec:
    """自定义命令定义。"""

    name: str
    description: str
    prompt: str
    source_path: Path
    requires_args: bool = False


def load_custom_commands(
    command_paths: list[Path],
    reserved_names: set[str],
) -> tuple[dict[str, CustomCommandSpec], list[str]]:
    """从 TOML 文件加载自定义命令。

    配置格式：

    [commands.review]
    description = "审查代码改动"
    prompt = "请审查当前改动，重点关注 bug 与回归风险。"
    requires_args = false
    """
    loaded: dict[str, CustomCommandSpec] = {}
    errors: list[str] = []

    for raw_path in command_paths:
        path = raw_path.expanduser()
        if not path.exists():
            continue
        if not path.is_file():
            errors.append(f"{path}: 不是文件，已跳过")
            continue

        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError) as e:
            errors.append(f"{path}: 读取失败（{e}）")
            continue

        raw_commands = data.get("commands")
        if raw_commands is None:
            continue
        if not isinstance(raw_commands, dict):
            errors.append(f"{path}: 顶层 'commands' 必须是 table")
            continue

        for raw_name, raw_spec in raw_commands.items():
            if not isinstance(raw_name, str):
                errors.append(f"{path}: 命令名必须是字符串，已跳过")
                continue

            name = raw_name.strip()
            if not COMMAND_NAME_PATTERN.fullmatch(name):
                errors.append(
                    f"{path}: 命令名 '{name}' 不合法（需匹配 {COMMAND_NAME_PATTERN.pattern}）"
                )
                continue

            if name in reserved_names:
                errors.append(f"{path}: 命令名 '{name}' 与内置命令冲突，已跳过")
                continue

            if not isinstance(raw_spec, dict):
                errors.append(f"{path}: 命令 '{name}' 必须使用 table 定义")
                continue

            unknown_fields = sorted(set(raw_spec.keys()) - ALLOWED_COMMAND_FIELDS)
            if unknown_fields:
                errors.append(
                    f"{path}: 命令 '{name}' 包含未知字段：{', '.join(unknown_fields)}"
                )

            prompt = raw_spec.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                errors.append(f"{path}: 命令 '{name}' 缺少非空 prompt")
                continue

            prompt_error = _validate_prompt_template(prompt)
            if prompt_error is not None:
                errors.append(f"{path}: 命令 '{name}' 的 prompt 无效（{prompt_error}）")
                continue

            description = raw_spec.get("description", f"自定义命令：{name}")
            if not isinstance(description, str):
                errors.append(f"{path}: 命令 '{name}' 的 description 必须是字符串")
                continue

            requires_args = raw_spec.get("requires_args", False)
            if not isinstance(requires_args, bool):
                errors.append(f"{path}: 命令 '{name}' 的 requires_args 必须是布尔值")
                continue

            loaded[name] = CustomCommandSpec(
                name=name,
                description=description.strip() or f"自定义命令：{name}",
                prompt=prompt,
                source_path=path,
                requires_args=requires_args,
            )

    return loaded, errors


def _validate_prompt_template(prompt: str) -> str | None:
    """校验 prompt 模板，仅允许 {args} 占位符。"""
    formatter = Formatter()

    try:
        fields: set[str] = set()
        for _, field_name, _, _ in formatter.parse(prompt):
            if field_name is None:
                continue
            fields.add(field_name)
    except ValueError as e:
        return str(e)

    invalid_fields = sorted(field for field in fields if field != "args")
    if invalid_fields:
        return f"仅支持占位符 {{args}}，检测到：{', '.join(invalid_fields)}"

    try:
        # 验证模板语法（如未转义花括号）
        prompt.format(args="__ARGS__")
    except (KeyError, ValueError) as e:
        return str(e)

    return None


def render_custom_prompt(prompt_template: str, args: str) -> str:
    """渲染自定义命令 prompt。"""
    args = args.strip()

    if "{args}" in prompt_template:
        return prompt_template.replace("{args}", args)

    if args:
        return f"{prompt_template}\n\n附加参数：{args}"

    return prompt_template


def build_custom_command_class(spec: CustomCommandSpec) -> type[BaseCommand]:
    """构造可注册到 CommandRegistry 的命令类。"""

    async def execute(self: BaseCommand, args: str) -> None:  # type: ignore[override]
        cleaned_args = args.strip()
        if spec.requires_args and not cleaned_args:
            self.agent.console.print(f"[yellow]/{spec.name} 需要参数[/yellow]")
            return

        prompt = render_custom_prompt(spec.prompt, cleaned_args)
        await self.agent.run(prompt)

    class_name = f"CustomCommand_{re.sub(r'[^a-zA-Z0-9_]', '_', spec.name)}"
    return type(
        class_name,
        (BaseCommand,),
        {
            "name": spec.name,
            "description": spec.description,
            "execute": execute,
            "__module__": __name__,
        },
    )
