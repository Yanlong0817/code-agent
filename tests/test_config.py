"""配置模块测试。"""

from pathlib import Path

import pytest

from code_agent.config import Config


class TestConfig:
    """Config 类测试。"""

    def test_default_values(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """测试默认配置值。"""
        # 清除环境变量并切换到无 .env 文件的目录
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        monkeypatch.delenv("CODE_AGENT_MODEL", raising=False)
        monkeypatch.chdir(tmp_path)  # 切换到空目录避免读取 .env

        config = Config()

        assert config.openai_api_key == ""
        assert config.tavily_api_key == ""
        assert config.model == "gpt-4.1"
        assert config.max_tokens == 4096
        assert config.max_iterations == 50
        assert config.auto_compact_enabled is True
        assert config.auto_compact_threshold == 0.8
        assert config.verbose is False

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """测试从环境变量加载配置。"""
        monkeypatch.chdir(tmp_path)  # 避免读取 .env
        monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
        monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
        monkeypatch.setenv("CODE_AGENT_MODEL", "gpt-4.1-mini")
        monkeypatch.setenv("CODE_AGENT_MAX_TOKENS", "8192")
        monkeypatch.setenv("CODE_AGENT_AUTO_COMPACT_THRESHOLD", "0.9")
        monkeypatch.setenv("CODE_AGENT_VERBOSE", "true")

        config = Config.from_env()

        assert config.openai_api_key == "test-api-key"
        assert config.tavily_api_key == "test-tavily-key"
        assert config.model == "gpt-4.1-mini"
        assert config.max_tokens == 8192
        assert config.auto_compact_threshold == 0.9
        assert config.verbose is True

    def test_validate_required_missing_api_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """测试缺少 API Key 时的验证。"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.chdir(tmp_path)  # 避免读取 .env

        config = Config()

        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            config.validate_required()

    def test_validate_required_with_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试有 API Key 时的验证。"""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        config = Config.from_env()
        config.validate_required()  # 不应抛出异常

    def test_working_directory_default(self) -> None:
        """测试工作目录默认值。"""
        config = Config()
        assert config.working_directory == Path.cwd()

    def test_openai_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试自定义 API base URL。"""
        monkeypatch.setenv("OPENAI_BASE_URL", "https://custom.api.com")

        config = Config.from_env()

        assert config.openai_base_url == "https://custom.api.com"
