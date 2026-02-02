"""使用 Pydantic Settings 进行配置管理。"""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 日志级别类型
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Config(BaseSettings):
    """从环境变量加载的应用配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API 密钥
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API 密钥，用于 Claude",
        alias="ANTHROPIC_API_KEY",
    )
    anthropic_base_url: str | None = Field(
        default=None,
        description="Anthropic API 基础 URL（用于代理或自定义端点）",
        alias="ANTHROPIC_BASE_URL",
    )
    tavily_api_key: str = Field(
        default="",
        description="Tavily API 密钥，用于网络搜索",
        alias="TAVILY_API_KEY",
    )

    # 模型设置
    model: str = Field(
        default="claude-sonnet-4-20250514",
        description="使用的 Claude 模型",
        alias="CODE_AGENT_MODEL",
    )
    max_tokens: int = Field(
        default=4096,
        description="响应的最大 token 数",
        alias="CODE_AGENT_MAX_TOKENS",
    )

    # Agent 设置
    working_directory: Path = Field(
        default_factory=Path.cwd,
        description="文件操作的工作目录",
        alias="CODE_AGENT_WORKING_DIR",
    )
    max_iterations: int = Field(
        default=50,
        description="Agent 循环的最大迭代次数",
        alias="CODE_AGENT_MAX_ITERATIONS",
    )

    # 输出设置
    verbose: bool = Field(
        default=False,
        description="启用详细输出",
        alias="CODE_AGENT_VERBOSE",
    )
    log_level: LogLevel = Field(
        default="INFO",
        description="日志级别（DEBUG、INFO、WARNING、ERROR、CRITICAL）",
        alias="CODE_AGENT_LOG_LEVEL",
    )
    log_file: Path = Field(
        default=Path.home() / ".code_agent" / "logs" / "code_agent.log",
        description="日志文件路径",
        alias="CODE_AGENT_LOG_FILE",
    )

    def validate_required(self) -> None:
        """验证必需的配置是否存在。

        Raises:
            ValueError: 如果缺少必需的配置
        """
        if not self.anthropic_api_key:
            raise ValueError(
                "需要设置 ANTHROPIC_API_KEY 环境变量。请在环境变量或 .env 文件中设置。"
            )

    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量创建配置。

        Returns:
            Config 实例
        """
        return cls()
