"""网络工具测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from code_agent.tools.network import WebFetchTool, WebSearchTool


class TestWebFetchTool:
    """WebFetchTool 测试。"""

    @pytest.fixture
    def tool(self) -> WebFetchTool:
        return WebFetchTool()

    async def test_fetch_html(self, tool: WebFetchTool) -> None:
        """测试获取 HTML 页面。"""
        mock_response = MagicMock()
        mock_response.text = "<html><body><h1>Hello</h1><p>World</p></body></html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await tool.execute("https://example.com")

            assert "Hello" in result
            assert "World" in result
            assert "example.com" in result

    async def test_fetch_json(self, tool: WebFetchTool) -> None:
        """测试获取 JSON 响应。"""
        mock_response = MagicMock()
        mock_response.text = '{"key": "value"}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await tool.execute("https://api.example.com/data")

            assert "```json" in result
            assert '"key": "value"' in result

    async def test_fetch_with_prompt(self, tool: WebFetchTool) -> None:
        """测试带提取提示的获取。"""
        mock_response = MagicMock()
        mock_response.text = "<html><body>Content</body></html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await tool.execute("https://example.com", prompt="提取主要内容")

            assert "提取提示：提取主要内容" in result

    async def test_http_to_https_conversion(self, tool: WebFetchTool) -> None:
        """测试 HTTP 自动转换为 HTTPS。"""
        mock_response = MagicMock()
        mock_response.text = "content"
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            await tool.execute("http://example.com")

            # 验证调用时使用了 HTTPS
            call_args = mock_instance.get.call_args
            assert call_args[0][0] == "https://example.com"

    def test_tool_schema(self) -> None:
        """测试工具 schema。"""
        schema = WebFetchTool.get_schema()

        assert schema["name"] == "WebFetch"
        assert "input_schema" in schema
        assert "url" in schema["input_schema"]["properties"]


class TestWebSearchTool:
    """WebSearchTool 测试。"""

    @pytest.fixture
    def tool(self) -> WebSearchTool:
        return WebSearchTool(api_key="test-api-key")

    @pytest.fixture
    def tool_no_key(self) -> WebSearchTool:
        return WebSearchTool()

    async def test_search_without_api_key(self, tool_no_key: WebSearchTool) -> None:
        """测试无 API Key 时的错误。"""
        with pytest.raises(ValueError, match="未配置 Tavily API"):
            await tool_no_key.execute("test query")

    async def test_search_success(self, tool: WebSearchTool) -> None:
        """测试成功搜索。"""
        mock_results = {
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "content": "This is test content",
                }
            ]
        }

        with patch("tavily.TavilyClient") as mock_tavily:
            mock_client = MagicMock()
            mock_client.search.return_value = mock_results
            mock_tavily.return_value = mock_client

            result = await tool.execute("test query")

            assert "Test Result" in result
            assert "https://example.com" in result
            assert "test content" in result

    async def test_search_no_results(self, tool: WebSearchTool) -> None:
        """测试无结果的搜索。"""
        with patch("tavily.TavilyClient") as mock_tavily:
            mock_client = MagicMock()
            mock_client.search.return_value = {"results": []}
            mock_tavily.return_value = mock_client

            result = await tool.execute("obscure query")

            assert "未找到结果" in result

    async def test_search_with_domains(self, tool: WebSearchTool) -> None:
        """测试带域名过滤的搜索。"""
        with patch("tavily.TavilyClient") as mock_tavily:
            mock_client = MagicMock()
            mock_client.search.return_value = {"results": []}
            mock_tavily.return_value = mock_client

            await tool.execute(
                "test",
                include_domains=["example.com"],
                exclude_domains=["spam.com"],
            )

            mock_client.search.assert_called_once()
            call_kwargs = mock_client.search.call_args[1]
            assert call_kwargs["include_domains"] == ["example.com"]
            assert call_kwargs["exclude_domains"] == ["spam.com"]

    def test_tool_schema(self) -> None:
        """测试工具 schema。"""
        schema = WebSearchTool.get_schema()

        assert schema["name"] == "WebSearch"
        assert "input_schema" in schema
        assert "query" in schema["input_schema"]["properties"]

    def test_format_results(self, tool: WebSearchTool) -> None:
        """测试结果格式化。"""
        results = [
            {"title": "Title 1", "url": "http://a.com", "content": "Content 1"},
            {"title": "Title 2", "url": "http://b.com", "content": "Content 2"},
        ]

        formatted = tool._format_results(results)

        assert "## 1. Title 1" in formatted
        assert "## 2. Title 2" in formatted
        assert "http://a.com" in formatted
        assert "http://b.com" in formatted
