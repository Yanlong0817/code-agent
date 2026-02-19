# CLAUDE.md

This file provides guidance to coding agents when working with code in this repository.

## Project Overview

Code Agent 是一个基于 OpenAI API 的智能代码助手，采用插件化工具架构，支持文件操作、系统交互、网络工具和会话管理。

## Development Commands

### Environment Setup
```bash
# 使用 uv 创建虚拟环境并安装依赖（包含开发依赖）
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Running the Agent
```bash
# 交互模式
code-agent

# 单次执行
code-agent "你的提示"

# 指定模型
code-agent -m gpt-4.1 "你的提示"

# 加载会话
code-agent --load <session_id>
code-agent --continue  # 继续上次会话
```

### Testing
```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_tools_file_ops.py -v

# 运行特定测试函数
pytest tests/test_tools_file_ops.py::test_read_tool -v

# 带覆盖率报告
pytest tests/ --cov=src/code_agent --cov-report=html
```

### Code Quality
```bash
# 检查代码风格
ruff check src/

# 自动修复
ruff check src/ --fix

# 格式化代码
ruff format src/
```

## Architecture

### Core Agent Loop (agent.py)

Agent 的核心是一个异步迭代循环：
1. 接收用户输入 → 添加到消息历史
2. 调用 OpenAI API（流式）→ 实时渲染 Markdown
3. 解析响应中的工具调用
4. 执行工具 → 收集结果
5. 将工具结果添加到消息历史
6. 重复直到 `stop_reason == "end_turn"` 或达到最大迭代次数

关键方法：
- `run()`: 主循环入口
- `_call_api_stream()`: 流式 API 调用，使用 Rich Live 实时渲染
- `_execute_tool_calls()`: 批量执行工具调用

### Tool System Architecture

工具系统采用插件化设计，所有工具继承自 `BaseTool`：

```python
class BaseTool(ABC):
    name: ClassVar[str]           # 工具名称
    description: ClassVar[str]    # 工具描述

    class Input(BaseModel):       # Pydantic 输入模型
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        pass

    @classmethod
    def get_schema(cls) -> dict:  # 自动生成工具 schema
        pass
```

**关键设计**：
- 使用 Pydantic 模型自动生成工具 schema
- `ToolRegistry` 管理工具注册和执行
- 输入验证在 `__call__` 中自动完成
- 工具执行结果自动转换为字符串（如果需要）

**添加新工具的步骤**：
1. 在 `src/code_agent/tools/` 创建工具类，继承 `BaseTool`
2. 定义 `name`、`description` 和 `Input` 模型
3. 实现 `execute()` 方法
4. 在 `agent.py` 的 `_register_tools()` 中注册
5. 在 `tools/__init__.py` 中导出

### Safety System (safety.py)

安全检查器在工具执行前检测危险操作：
- **命令检查**：检测 `rm -rf`、`sudo`、`git push --force` 等危险命令
- **文件检查**：检测访问 `.env`、`credentials`、`.ssh/` 等敏感文件
- **风险级别**：high（红色）、medium（黄色）、low（灰色）
- **确认机制**：高风险操作需要用户确认

在 `BashTool` 和文件操作工具中集成使用。

### Session Management (session.py)

会话管理器负责保存和加载对话历史：
- 会话存储在 `~/.code_agent/sessions/`
- 每个会话包含元数据（ID、创建时间、模型等）和消息历史
- 支持按 ID 或路径加载、搜索、列出最近会话

**会话文件格式**：
```json
{
  "metadata": {
    "id": "20240101_120000_123456",
    "created_at": "2024-01-01T12:00:00",
    "updated_at": "2024-01-01T12:30:00",
    "model": "gpt-4.1",
    "message_count": 10,
    "title": "可选标题"
  },
  "messages": [...]
}
```

### Command System (commands/)

交互模式支持以 `/` 开头的命令：
- `/help` - 显示帮助
- `/clear` - 清除对话历史
- `/model` - 切换模型
- `/tools` - 列出可用工具
- `/commands [list|reload|init]` - 管理自定义命令
- `/save [title]` - 保存当前会话
- `/load <id>` - 加载会话
- `/sessions` - 列出所有会话
- `/history` - 显示对话历史
- `/export <path>` - 导出会话

**命令架构**：
- `BaseCommand` 抽象基类
- `CommandRegistry` 管理命令注册
- `CommandHandler` 解析和执行命令
- 支持命令补全（前缀匹配）

### UI Components (ui/)

使用 Rich 库构建终端 UI：
- **StatusBar**: 显示模型、token 使用量、迭代次数
- **ToolDisplay**: 渲染工具调用和结果（Panel + Spinner）
- **Theme**: 统一的颜色主题
- **Components**: 横幅、提示符等可复用组件

## Configuration

配置通过环境变量或 `.env` 文件加载（使用 `pydantic-settings`）：

**必需**：
- `OPENAI_API_KEY`: OpenAI API 密钥

**可选**：
- `OPENAI_BASE_URL`: API 基础 URL（用于代理）
- `TAVILY_API_KEY`: 网络搜索 API 密钥
- `CODE_AGENT_MODEL`: 模型名称（默认：gpt-4.1）
- `CODE_AGENT_MAX_TOKENS`: 最大响应 token（默认：4096）
- `CODE_AGENT_MAX_ITERATIONS`: 最大迭代次数（默认：50）
- `CODE_AGENT_AUTO_COMPACT`: 是否启用上下文自动压缩（默认：true）
- `CODE_AGENT_AUTO_COMPACT_THRESHOLD`: 压缩触发阈值（默认：0.8）
- `CODE_AGENT_AUTO_COMPACT_KEEP_RECENT`: 压缩后保留最近消息数（默认：8）
- `CODE_AGENT_AUTO_COMPACT_SUMMARY_MAX_TOKENS`: 摘要最大 token（默认：2048）
- `CODE_AGENT_WORKING_DIR`: 工作目录
- `CODE_AGENT_VERBOSE`: 详细输出
- `CODE_AGENT_LOG_LEVEL`: 日志级别（DEBUG/INFO/WARNING/ERROR）
- `CODE_AGENT_LOG_FILE`: 日志文件路径

## Key Patterns

### Async/Await Throughout
所有工具的 `execute()` 方法都是异步的，即使是同步操作也要用 `async def`。这保证了架构的一致性。

### Pydantic for Everything
- 配置：`Config` 类使用 `pydantic-settings`
- 工具输入：每个工具的 `Input` 类
- 会话数据：`Session`、`SessionMetadata`
- 安全检查：`SafetyCheck`

### Type Hints Everywhere
代码库严格使用类型注解，遵循 PEP 484。使用 `from __future__ import annotations` 避免循环导入。

### Logging Strategy
- 使用 Python 标准 `logging` 模块
- 每个模块获取自己的 logger：`logger = get_logger(__name__)`
- 日志级别：DEBUG（工具执行细节）、INFO（主要流程）、ERROR（错误）
- 用户可见输出使用 Rich Console，不使用 logging

### Error Handling in Tools
工具执行错误在 `_execute_tool_calls()` 中统一捕获，返回带 `is_error: True` 的工具结果给模型。不要在工具内部捕获所有异常。

### UTF-8 Encoding Handling
处理子进程输出和文件内容时必须正确处理 UTF-8 编码错误：

**问题**：当子进程输出包含无效 UTF-8 字节序列时，`bytes.decode()` 默认会创建 Unicode 代理字符（U+D800-U+DFFF），这些字符在后续的 JSON 序列化或终端输出时会导致编码失败。

**解决方案**：
1. **源头防御**：在所有 `decode()` 调用处添加 `errors="replace"` 参数
   ```python
   stdout.decode(errors="replace")  # 将无效字节替换为 �
   ```

2. **输出防御**：在 JSON 序列化前清理数据中的 surrogate 字符
   ```python
   def _sanitize_for_json(obj: Any) -> Any:
       if isinstance(obj, str):
           return obj.encode("utf-8", errors="replace").decode("utf-8")
       elif isinstance(obj, dict):
           return {k: _sanitize_for_json(v) for k, v in obj.items()}
       elif isinstance(obj, list):
           return [_sanitize_for_json(item) for item in obj]
       return obj
   ```

**已实施位置**：
- [tools/file_ops.py:299](src/code_agent/tools/file_ops.py#L299): GrepTool 的 stderr 解码
- [tools/file_ops.py:305](src/code_agent/tools/file_ops.py#L305): GrepTool 的 stdout 解码
- [session.py:89-108](src/code_agent/session.py#L89-L108): SessionManager 的 `_sanitize_for_json()` 方法
- [commands/export.py:11-29](src/code_agent/commands/export.py#L11-L29): ExportCommand 的数据清理函数

## Testing Strategy

测试文件按模块组织：
- `test_config.py`: 配置加载和验证
- `test_tools_*.py`: 各类工具的单元测试
- `test_session.py`: 会话管理
- `test_safety.py`: 安全检查
- `test_commands.py`: 命令系统

使用 `pytest-asyncio` 测试异步代码，配置 `asyncio_mode = "auto"`。

## Important Files

- `agent.py`: Agent 主循环和 API 交互
- `tools/base.py`: 工具基类和注册表
- `tools/file_ops.py`: 文件操作工具（Read/Write/Edit/ApplyPatch/Insert/Glob/Grep）
- `safety.py`: 安全检查系统
- `session.py`: 会话管理
- `commands/handler.py`: 命令处理器
- `config.py`: 配置管理
- `__main__.py`: CLI 入口

## Dependencies

核心依赖：
- `openai`: OpenAI API SDK
- `pydantic`: 数据验证和配置管理
- `httpx`: HTTP 客户端（用于网络工具）
- `tavily-python`: 网络搜索 API
- `html2text`: HTML 转 Markdown
- `rich`: 终端 UI

开发依赖：
- `pytest`: 测试框架
- `pytest-asyncio`: 异步测试支持
- `pytest-cov`: 覆盖率报告
- `ruff`: 代码检查和格式化

## Notes

- 项目使用 `uv` 作为包管理器，不使用 `pip` 或 `poetry`
- 所有中文注释和文档遵循用户的全局编码规范
- 工具的 `description` 字段会直接传给模型，需要清晰描述工具功能和参数
- 流式输出使用 `Rich Live` 实时渲染 Markdown，提供更好的用户体验
- 会话文件使用 JSON 格式，便于手动查看和编辑
