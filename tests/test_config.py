"""配置模块测试。"""

import os
from pathlib import Path

import pytest

from code_agent.config import Config


class TestConfig:
    """Config 类测试。"""

    def test_default_values(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """测试默认配置值。"""
        # 清除环境变量并切换到无 .env 文件的目录
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        monkeypatch.delenv("CODE_AGENT_MODEL", raising=False)
        monkeypatch.chdir(tmp_path)  # 切换到空目录避免读取 .env

        config = Config()

        assert config.anthropic_api_key == ""
        assert config.tavily_api_key == ""
        assert config.model == "claude-sonnet-4-20250514"
        assert config.max_tokens == 4096
        assert config.max_iterations == 50
        assert config.verbose is False

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """测试从环境变量加载配置。"""
        monkeypatch.chdir(tmp_path)  # 避免读取 .env
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key")
        monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
        monkeypatch.setenv("CODE_AGENT_MODEL", "claude-3-opus")
        monkeypatch.setenv("CODE_AGENT_MAX_TOKENS", "8192")
        monkeypatch.setenv("CODE_AGENT_VERBOSE", "true")

        config = Config.from_env()

        assert config.anthropic_api_key == "test-api-key"
        assert config.tavily_api_key == "test-tavily-key"
        assert config.model == "claude-3-opus"
        assert config.max_tokens == 8192
        assert config.verbose is True

    def test_validate_required_missing_api_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """测试缺少 API Key 时的验证。"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.chdir(tmp_path)  # 避免读取 .env

        config = Config()

        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            config.validate_required()

    def test_validate_required_with_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """测试有 API Key 时的验证。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        config = Config.from_env()
        config.validate_required()  # 不应抛出异常

    def test_working_directory_default(self) -> None:
        """测试工作目录默认值。"""
        config = Config()
        assert config.working_directory == Path.cwd()

    def test_anthropic_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试自定义 API base URL。"""
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://custom.api.com")

        config = Config.from_env()

        assert config.anthropic_base_url == "https://custom.api.com"
