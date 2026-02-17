"""使用 Pydantic Settings 进行配置管理。"""

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
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
    openai_api_key: str = Field(
        default="",
        description="OpenAI API 密钥",
        alias="OPENAI_API_KEY",
        validation_alias=AliasChoices("OPENAI_API_KEY", "ANTHROPIC_API_KEY"),
    )
    openai_base_url: str | None = Field(
        default=None,
        description="OpenAI API 基础 URL（用于代理或自定义端点）",
        alias="OPENAI_BASE_URL",
        validation_alias=AliasChoices("OPENAI_BASE_URL", "ANTHROPIC_BASE_URL"),
    )
    tavily_api_key: str = Field(
        default="",
        description="Tavily API 密钥，用于网络搜索",
        alias="TAVILY_API_KEY",
    )

    # 模型设置
    model: str = Field(
        default="gpt-4.1",
        description="使用的 OpenAI 模型",
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
    auto_compact_enabled: bool = Field(
        default=True,
        description="是否启用上下文自动压缩",
        alias="CODE_AGENT_AUTO_COMPACT",
    )
    auto_compact_threshold: float = Field(
        default=0.8,
        ge=0.5,
        le=0.98,
        description="触发上下文压缩的阈值（输入 token / 上下文上限）",
        alias="CODE_AGENT_AUTO_COMPACT_THRESHOLD",
    )
    auto_compact_keep_recent_messages: int = Field(
        default=8,
        ge=2,
        le=50,
        description="压缩后保留的最近消息数量",
        alias="CODE_AGENT_AUTO_COMPACT_KEEP_RECENT",
    )
    auto_compact_summary_max_tokens: int = Field(
        default=2048,
        ge=256,
        le=8192,
        description="压缩摘要生成时的最大输出 token",
        alias="CODE_AGENT_AUTO_COMPACT_SUMMARY_MAX_TOKENS",
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
        if not self.openai_api_key:
            raise ValueError("需要设置 OPENAI_API_KEY 环境变量。请在环境变量或 .env 文件中设置。")

    @property
    def anthropic_api_key(self) -> str:
        """兼容旧字段名，映射到 openai_api_key。"""
        return self.openai_api_key

    @property
    def anthropic_base_url(self) -> str | None:
        """兼容旧字段名，映射到 openai_base_url。"""
        return self.openai_base_url

    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量创建配置。

        Returns:
            Config 实例
        """
        return cls()
