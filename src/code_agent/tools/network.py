"""网络工具：WebFetch、WebSearch。"""

from typing import Any, ClassVar, Literal

import html2text
import httpx
from pydantic import BaseModel, Field

from code_agent.tools.base import BaseTool


class WebFetchTool(BaseTool):
    """获取并处理网页内容。"""

    name: ClassVar[str] = "WebFetch"
    description: ClassVar[str] = (
        "从 URL 获取内容并将 HTML 转换为 Markdown。"
        "用于获取文档、网页或 API 响应。"
    )

    class Input(BaseModel):
        url: str = Field(description="要获取的 URL")
        prompt: str = Field(
            default="",
            description="可选的提示，描述要提取的信息",
        )
        timeout: int = Field(default=30, gt=0, le=120, description="请求超时时间（秒）")

    def __init__(self) -> None:
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True
        self.html_converter.ignore_emphasis = False
        self.html_converter.body_width = 0  # 不换行

    async def execute(
        self,
        url: str,
        prompt: str = "",
        timeout: int = 30,
    ) -> str:
        """获取 URL 并转换为 Markdown。

        Args:
            url: 要获取的 URL
            prompt: 可选的提取提示
            timeout: 请求超时时间

        Returns:
            Markdown 格式的页面内容
        """
        # 确保使用 HTTPS
        if url.startswith("http://"):
            url = "https://" + url[7:]

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; CodeAgent/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            if "text/html" in content_type:
                # 将 HTML 转换为 Markdown
                markdown = self.html_converter.handle(response.text)
            elif "application/json" in content_type:
                # 直接返回 JSON
                markdown = f"```json\n{response.text}\n```"
            else:
                # 返回纯文本
                markdown = response.text

            # 内容过长时截断
            max_length = 50000
            if len(markdown) > max_length:
                markdown = markdown[:max_length] + "\n\n...[内容已截断]"

            result = f"# 来自 {url} 的内容\n\n{markdown}"

            if prompt:
                result = f"提取提示：{prompt}\n\n{result}"

            return result


class WebSearchTool(BaseTool):
    """使用 Tavily API 进行网络搜索。"""

    name: ClassVar[str] = "WebSearch"
    description: ClassVar[str] = (
        "使用 Tavily API 搜索网络。返回包含标题、URL 和内容摘要的相关搜索结果。"
    )

    class Input(BaseModel):
        query: str = Field(description="搜索查询")
        search_depth: Literal["basic", "advanced"] = Field(
            default="basic",
            description="搜索深度：'basic' 快速搜索，'advanced' 深度搜索",
        )
        include_domains: list[str] = Field(
            default_factory=list,
            description="仅包含这些域名的结果",
        )
        exclude_domains: list[str] = Field(
            default_factory=list,
            description="排除这些域名的结果",
        )
        max_results: int = Field(
            default=5, gt=0, le=20, description="最大结果数量"
        )

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    async def execute(
        self,
        query: str,
        search_depth: str = "basic",
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        max_results: int = 5,
    ) -> str:
        """执行网络搜索。

        Args:
            query: 搜索查询
            search_depth: basic 或 advanced
            include_domains: 白名单域名
            exclude_domains: 黑名单域名
            max_results: 最大返回结果数

        Returns:
            格式化的搜索结果
        """
        if not self.api_key:
            raise ValueError("未配置 Tavily API 密钥")

        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=self.api_key)

            response = client.search(
                query=query,
                search_depth=search_depth,
                include_domains=include_domains or [],
                exclude_domains=exclude_domains or [],
                max_results=max_results,
            )

            return self._format_results(response.get("results", []))

        except ImportError:
            raise RuntimeError("未安装 tavily-python 包")

    def _format_results(self, results: list[dict[str, Any]]) -> str:
        """将搜索结果格式化为 Markdown。

        Args:
            results: 搜索结果字典列表

        Returns:
            格式化的 Markdown 字符串
        """
        if not results:
            return "未找到结果。"

        lines = ["# 搜索结果\n"]

        for i, result in enumerate(results, 1):
            title = result.get("title", "无标题")
            url = result.get("url", "")
            content = result.get("content", "")

            lines.append(f"## {i}. {title}")
            lines.append(f"**链接：** {url}")
            lines.append(f"\n{content}\n")
            lines.append("---\n")

        return "\n".join(lines)
