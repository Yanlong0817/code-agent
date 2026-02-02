# Code Agent

一个基于 Claude API 的智能代码助手，具备文件操作、系统交互和网络工具能力。

## 功能特性

### 文件操作
- **Read** - 读取文件内容，支持行号范围
- **Write** - 创建或覆盖文件
- **Edit** - 精确字符串替换编辑
- **Glob** - 文件模式匹配搜索
- **Grep** - 基于 ripgrep 的内容搜索

### 系统交互
- **Bash** - 执行 shell 命令
- **AskUserQuestion** - 交互式用户提问

### 网络工具
- **WebFetch** - 获取网页内容并转换为 Markdown
- **WebSearch** - 基于 Tavily API 的网络搜索

### 任务管理
- **TodoWrite** - 任务列表管理和进度跟踪

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

## 配置

创建 `.env` 文件或设置环境变量：

```bash
# 必需
ANTHROPIC_API_KEY=your_anthropic_api_key

# 可选
TAVILY_API_KEY=your_tavily_api_key          # WebSearch 功能需要
CODE_AGENT_MODEL=claude-sonnet-4-20250514   # 默认模型
CODE_AGENT_MAX_TOKENS=4096                  # 最大响应 token
CODE_AGENT_VERBOSE=false                    # 详细输出
```

## 使用方法

### 命令行模式

```bash
# 单次执行
code-agent "读取 README.md 文件内容"

# 或使用 python -m
python -m code_agent "搜索所有 Python 文件"
```

### 交互模式

```bash
code-agent
# 进入交互式对话，输入 quit 退出
```

### 作为库使用

```python
import asyncio
from code_agent import CodeAgent, Config

async def main():
    config = Config.from_env()
    agent = CodeAgent(config)

    response = await agent.run("列出当前目录的所有 Python 文件")
    print(response)

asyncio.run(main())
```

## 工具详解

### Read - 读取文件

```python
# 读取整个文件
Read(file_path="/path/to/file.py")

# 读取指定行范围
Read(file_path="/path/to/file.py", offset=10, limit=50)
```

### Write - 写入文件

```python
Write(file_path="/path/to/new_file.py", content="print('Hello')")
```

### Edit - 编辑文件

```python
# 替换单个匹配
Edit(
    file_path="/path/to/file.py",
    old_string="old_function_name",
    new_string="new_function_name"
)

# 替换所有匹配
Edit(
    file_path="/path/to/file.py",
    old_string="TODO",
    new_string="DONE",
    replace_all=True
)
```

### Glob - 文件搜索

```python
# 搜索所有 Python 文件
Glob(pattern="**/*.py")

# 在指定目录搜索
Glob(pattern="*.ts", path="src/")
```

### Grep - 内容搜索

```python
# 搜索包含 "def " 的文件
Grep(pattern="def ", path="src/", file_type="py")

# 显示匹配内容和上下文
Grep(
    pattern="class.*Tool",
    output_mode="content",
    context_lines=2
)
```

### Bash - 执行命令

```python
Bash(command="git status")
Bash(command="npm install", timeout=300000)
```

### WebFetch - 获取网页

```python
WebFetch(
    url="https://docs.python.org/3/library/asyncio.html",
    prompt="提取 asyncio 的主要功能"
)
```

### WebSearch - 网络搜索

```python
WebSearch(
    query="Python asyncio best practices 2024",
    max_results=5
)
```

## 项目结构

```
code_agent/
├── pyproject.toml              # 项目配置
├── README.md                   # 项目文档
├── src/
│   └── code_agent/
│       ├── __init__.py         # 包入口
│       ├── __main__.py         # CLI 入口
│       ├── agent.py            # Agent 主循环
│       ├── config.py           # 配置管理
│       ├── tools/
│       │   ├── __init__.py     # 工具导出
│       │   ├── base.py         # 工具基类
│       │   ├── file_ops.py     # 文件操作工具
│       │   ├── system.py       # 系统交互工具
│       │   ├── network.py      # 网络工具
│       │   └── task.py         # 任务管理工具
│       └── utils/
│           └── __init__.py
└── tests/
    └── __init__.py
```

## 扩展工具

创建自定义工具：

```python
from typing import ClassVar
from pydantic import BaseModel, Field
from code_agent.tools.base import BaseTool

class MyCustomTool(BaseTool):
    """自定义工具示例"""

    name: ClassVar[str] = "MyTool"
    description: ClassVar[str] = "这是一个自定义工具"

    class Input(BaseModel):
        param1: str = Field(description="参数1说明")
        param2: int = Field(default=10, description="参数2说明")

    async def execute(self, param1: str, param2: int = 10) -> str:
        # 实现工具逻辑
        return f"处理结果: {param1}, {param2}"
```

注册到 Agent：

```python
from code_agent import CodeAgent

agent = CodeAgent()
agent.registry.register(MyCustomTool())
```

## 开发

### 运行测试

```bash
pytest tests/ -v
```

### 代码检查

```bash
ruff check src/
ruff format src/
```

## 技术栈

| 组件 | 技术 |
|------|------|
| LLM 交互 | Anthropic SDK |
| 数据验证 | Pydantic v2 |
| HTTP 客户端 | httpx |
| 网络搜索 | Tavily API |
| HTML 解析 | html2text |
| CLI 界面 | Rich |
| 内容搜索 | ripgrep |

## License

MIT
