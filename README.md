# Code Agent

一个基于 OpenAI API 的智能代码助手，采用插件化工具架构，支持文件操作、系统交互、网络工具和会话管理。

## ✨ 核心特性

- 🔧 **插件化工具系统** - 12 个内置工具，易于扩展
- 💬 **交互式命令** - 10 个内置命令，支持会话管理
- 🔒 **安全检查** - 危险操作自动检测和确认
- 📝 **会话管理** - 保存/加载对话历史
- 🎨 **Markdown 输出** - 终端友好的渲染展示
- 🚀 **智能输入** - 命令补全、历史记录

## 🛠️ 工具列表

### 文件操作（9个工具）
- **Read** - 读取文件内容，支持行号范围和偏移
- **Write** - 创建或覆盖文件，自动创建目录
- **Edit** - 精确字符串替换，支持预览模式（diff）
- **ApplyPatch** - 应用 unified diff 补丁（新增/修改/删除）
- **Undo** - 回滚最近的文件变更（支持按文件和步数）
- **Insert** - 在指定行后插入文本
- **ListDirectory** - 树形显示目录结构，支持递归
- **Glob** - 文件模式匹配搜索（如 `**/*.py`）
- **Grep** - 基于 ripgrep 的内容搜索，支持正则

### 系统交互（1个工具）
- **Bash** - 执行 shell 命令，含安全检查和超时控制

### 网络工具（2个工具）
- **WebFetch** - 获取网页内容并转换为 Markdown
- **WebSearch** - 基于 Tavily API 的网络搜索

## 📋 交互式命令

在交互模式下，使用 `/` 开头的命令：

| 命令 | 说明 |
|------|------|
| `/help` | 显示所有可用命令 |
| `/clear` | 清除对话历史 |
| `/model` | 切换 OpenAI 模型 |
| `/tools` | 列出所有可用工具 |
| `/diff` | 显示本次会话文件变更 |
| `/save [title]` | 保存当前会话 |
| `/load <id>` | 加载历史会话 |
| `/sessions` | 列出所有会话 |
| `/history` | 显示对话历史 |
| `/export <path>` | 导出会话到文件 |

## 安装

### 前置要求
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) 包管理器
- [ripgrep](https://github.com/BurntSushi/ripgrep) (用于 Grep 工具)

### 安装步骤

```bash
# 克隆项目
cd /path/to/code_agent

# 使用 uv 创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

uv pip install -e ".[dev]"
```

## ⚙️ 配置

创建 `.env` 文件或设置环境变量：

```bash
# 必需
OPENAI_API_KEY=your_openai_api_key

# 可选 - API 设置
OPENAI_BASE_URL=https://api.openai.com/v1      # API 基础 URL（用于代理）
TAVILY_API_KEY=your_tavily_api_key            # WebSearch 功能需要

# 可选 - 模型设置
CODE_AGENT_MODEL=gpt-4.1                       # 默认模型
CODE_AGENT_MAX_TOKENS=4096                    # 最大响应 token
CODE_AGENT_MAX_ITERATIONS=50                  # 最大迭代次数

# 可选 - 运行设置
CODE_AGENT_WORKING_DIR=/path/to/project       # 工具可访问的工作目录边界
CODE_AGENT_VERBOSE=false                      # 详细输出
CODE_AGENT_AUTO_COMPACT=true                  # 启用上下文自动压缩
CODE_AGENT_AUTO_COMPACT_THRESHOLD=0.8         # 触发压缩阈值
CODE_AGENT_AUTO_COMPACT_KEEP_RECENT=8         # 压缩后保留最近消息数
CODE_AGENT_AUTO_COMPACT_SUMMARY_MAX_TOKENS=2048  # 摘要最大 token

# 可选 - 日志设置
CODE_AGENT_LOG_LEVEL=INFO                     # 日志级别（DEBUG/INFO/WARNING/ERROR）
CODE_AGENT_LOG_FILE=~/.code_agent/logs/code_agent.log  # 日志文件路径
```

### 可用模型

- `gpt-4.1` - 高质量通用模型
- `gpt-4.1-mini` - 更快更省成本
- `gpt-4o` - 多模态通用模型
- `gpt-4o-mini` - 轻量多模态模型

## 🚀 快速开始

### 单次执行

```bash
# 基本用法
code-agent "读取 README.md 文件内容"

# 指定模型
code-agent -m gpt-4.1 "重构这个函数"

# 指定工作目录
code-agent -w /path/to/project "分析代码结构"
```

### 交互模式

```bash
# 启动交互模式
code-agent

# 加载历史会话
code-agent --load 20240101_120000

# 继续上次会话
code-agent --continue
```

**交互模式特性**：
- 🔄 命令历史记录（上下箭头）
- ✨ 命令自动补全（Tab 键）
- 📝 多行输入支持（Shift+Enter）
- 🎨 语法高亮

### 作为库使用

```python
import asyncio
from code_agent import CodeAgent, Config

async def main():
    config = Config.from_env()
    agent = CodeAgent(config)

    # 单次执行
    response = await agent.run("列出当前目录的所有 Python 文件")
    print(response)

asyncio.run(main())
```

## 🔧 工具详解

### Edit - 编辑文件（支持预览）

```python
# 预览修改（不实际修改文件）
Edit(
    file_path="/path/to/file.py",
    old_string="old_function_name",
    new_string="new_function_name",
    preview=True  # 显示 diff，不修改文件
)

# 执行修改（显示 diff）
Edit(
    file_path="/path/to/file.py",
    old_string="old_function_name",
    new_string="new_function_name",
    preview=False  # 或不传，默认执行修改
)

# 替换所有匹配
Edit(
    file_path="/path/to/file.py",
    old_string="TODO",
    new_string="DONE",
    replace_all=True
)
```

### Insert - 插入文本

```python
# 在文件开头插入
Insert(file_path="/path/to/file.py", insert_line=0, insert_text="# Header\n")

# 在第 10 行后插入
Insert(file_path="/path/to/file.py", insert_line=10, insert_text="new_code()\n")
```

### ListDirectory - 目录树

```python
# 显示目录结构（递归 2 层）
ListDirectory(path=".", depth=2)

# 包含隐藏文件
ListDirectory(path="src/", depth=3, include_hidden=True)
```

### Grep - 内容搜索

```python
# 搜索包含 "def " 的文件
Grep(pattern="def ", path="src/", file_type="py")

# 显示匹配内容和上下文（前后 2 行）
Grep(
    pattern="class.*Tool",
    output_mode="content",
    context_lines=2
)

# 不区分大小写搜索
Grep(pattern="error", case_insensitive=True)
```

## 📁 项目结构

```
code_agent/
├── pyproject.toml              # 项目配置和依赖
├── README.md                   # 项目文档
├── CLAUDE.md                   # 开发指南
├── src/code_agent/
│   ├── __init__.py             # 包入口
│   ├── __main__.py             # CLI 入口
│   ├── agent.py                # Agent 主循环
│   ├── config.py               # 配置管理（Pydantic Settings）
│   ├── logging.py              # 日志系统
│   ├── safety.py               # 安全检查器
│   ├── session.py              # 会话管理器
│   ├── commands/               # 交互式命令
│   │   ├── base.py             # 命令基类和注册表
│   │   ├── handler.py          # 命令处理器
│   │   ├── clear.py            # /clear 命令
│   │   ├── diff.py             # /diff 命令
│   │   ├── export.py           # /export 命令
│   │   ├── help.py             # /help 命令
│   │   ├── history.py          # /history 命令
│   │   ├── model.py            # /model 命令
│   │   ├── session.py          # /save, /load, /sessions 命令
│   │   └── tools.py            # /tools 命令
│   ├── input/                  # 输入系统（prompt_toolkit）
│   │   ├── completer.py        # 命令补全
│   │   ├── history.py          # 历史记录
│   │   ├── session.py          # 输入会话
│   │   └── style.py            # 输入样式
│   ├── tools/                  # 工具系统
│   │   ├── base.py             # 工具基类和注册表
│   │   ├── file_ops.py         # 文件操作工具
│   │   ├── system.py           # 系统交互工具
│   │   └── network.py          # 网络工具
│   ├── ui/                     # UI 组件（Rich）
│   │   ├── components.py       # 横幅、提示符等
│   │   ├── status_bar.py       # 状态栏
│   │   ├── theme.py            # 颜色主题
│   │   └── tool_display.py     # 工具调用显示
│   └── utils/                  # 工具函数
│       └── diff.py             # Diff 生成工具
└── tests/                      # 测试套件
    ├── test_config.py
    ├── test_tools_*.py
    ├── test_commands.py
    ├── test_safety.py
    └── test_session.py
```

## 🔌 扩展工具

创建自定义工具非常简单，只需继承 `BaseTool` 并实现 `execute()` 方法：

```python
from typing import ClassVar
from pydantic import BaseModel, Field
from code_agent.tools.base import BaseTool

class MyCustomTool(BaseTool):
    """自定义工具示例"""

    name: ClassVar[str] = "MyTool"
    description: ClassVar[str] = (
        "这是一个自定义工具，用于演示如何扩展 Code Agent"
    )

    class Input(BaseModel):
        param1: str = Field(description="参数1说明")
        param2: int = Field(default=10, description="参数2说明")

    async def execute(self, param1: str, param2: int = 10) -> str:
        """执行工具逻辑。

        Args:
            param1: 第一个参数
            param2: 第二个参数

        Returns:
            工具执行结果
        """
        # 实现你的工具逻辑
        result = f"处理 {param1}，参数2={param2}"
        return result
```

**注册到 Agent**：

```python
# 在 agent.py 的 _register_tools() 方法中添加
from my_tools import MyCustomTool

def _register_tools(self) -> None:
    # ... 现有工具 ...
    self.registry.register(MyCustomTool())
```

**关键点**：
- 使用 `ClassVar` 定义 `name` 和 `description`
- 使用 Pydantic `BaseModel` 定义输入参数
- `execute()` 方法必须是 `async def`
- 返回字符串结果（会传递给模型）

## 🧪 开发

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_tools_file_ops.py -v

# 运行特定测试函数
pytest tests/test_tools_file_ops.py::test_edit_tool -v

# 带覆盖率报告
pytest tests/ --cov=src/code_agent --cov-report=html
```

### 代码检查

```bash
# 检查代码风格
ruff check src/

# 自动修复问题
ruff check src/ --fix

# 格式化代码
ruff format src/
```

### 项目统计

- **代码行数**: ~3000+ 行 Python 代码
- **测试覆盖**: 9 个测试文件，覆盖核心功能
- **工具数量**: 12 个内置工具
- **命令数量**: 10 个交互式命令

## 🏗️ 架构设计

### 核心组件

1. **Agent 主循环** (`agent.py`)
   - 异步迭代循环
   - API 调用与工具编排
   - 工具调用执行
   - 消息历史管理

2. **工具系统** (`tools/`)
   - 插件化架构
   - Pydantic 输入验证
   - 统一的注册表
   - 自动 schema 生成

3. **命令系统** (`commands/`)
   - 命令模式实现
   - 注册表管理
   - 智能补全
   - 前缀匹配

4. **安全系统** (`safety.py`)
   - 危险命令检测
   - 敏感文件保护
   - 用户确认机制

5. **会话管理** (`session.py`)
   - JSON 格式存储
   - 元数据跟踪
   - 搜索和加载

### 设计模式

- **命令模式**: 交互式命令系统
- **注册表模式**: 工具和命令管理
- **策略模式**: 安全检查器
- **依赖注入**: 命令访问 Agent 能力

## 🔒 安全特性

- ✅ 危险命令自动检测（`rm -rf`, `sudo`, `git push --force` 等）
- ✅ 敏感文件保护（`.env`, `.ssh/`, `credentials` 等）
- ✅ 用户确认机制（高风险操作需要确认）
- ✅ 工作目录隔离（默认启用，禁止越界访问）
- ✅ UTF-8 编码安全处理

## 📚 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| LLM 交互 | OpenAI SDK | OpenAI API 客户端 |
| 数据验证 | Pydantic v2 | 配置和输入验证 |
| HTTP 客户端 | httpx | 异步 HTTP 请求 |
| 网络搜索 | Tavily API | 网络搜索功能 |
| HTML 解析 | html2text | HTML 转 Markdown |
| CLI 界面 | Rich | 终端 UI 和格式化 |
| 输入系统 | prompt_toolkit | 命令补全和历史 |
| 内容搜索 | ripgrep | 高性能代码搜索 |
| 测试框架 | pytest | 单元测试和集成测试 |
| 代码检查 | ruff | 代码风格和格式化 |

## 📖 相关文档

- [CLAUDE.md](CLAUDE.md) - 完整的开发指南和架构文档
- [API 文档](https://platform.openai.com/docs/overview) - OpenAI API 官方文档
- [Rich 文档](https://rich.readthedocs.io/) - 终端 UI 库文档
- [Pydantic 文档](https://docs.pydantic.dev/) - 数据验证库文档

## 🤝 贡献

欢迎贡献！请遵循以下步骤：

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'feat: 添加某个功能'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

**提交规范**：
- `feat:` - 新功能
- `fix:` - 修复 bug
- `docs:` - 文档更新
- `refactor:` - 代码重构
- `test:` - 测试相关
- `style:` - 代码格式

## 📝 更新日志

### v0.1.0 (2024-02)

**新增功能**：
- ✨ 添加 Diff 工具模块和 EditTool 预览功能
- ✨ 添加 ListDirectoryTool 目录列表工具
- ✨ 添加 InsertTool 文本插入工具
- ✨ 引入 prompt_toolkit 增强 CLI 输入体验
- ✨ 实现流式 Markdown 渲染

**重构**：
- 🔧 移除 TodoWriteTool 任务管理功能
- 🔧 移除 AskUserQuestionTool（模型可直接提问）
- 🔧 移除 GitTool（使用 Bash 替代）

**修复**：
- 🐛 修复 UTF-8 编码错误（surrogates not allowed）
- 🐛 修复 EditTool 和 InsertTool 的测试失败

## 📄 License

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [OpenAI](https://platform.openai.com/) - OpenAI API
- [Rich](https://github.com/Textualize/rich) - 终端 UI
- [Pydantic](https://github.com/pydantic/pydantic) - 数据验证
- [ripgrep](https://github.com/BurntSushi/ripgrep) - 代码搜索

---

**Made with ❤️ by tyl**
