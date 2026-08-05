from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import ipaddress
import os
import re
from time import monotonic
from typing import Any, Protocol
from urllib.parse import unquote, urljoin, urlparse
import xml.etree.ElementTree as ET

import httpx

from .provider_errors import ProviderNotConfigured, ProviderUnavailable


@dataclass(frozen=True)
class SearchDocument:
    query: str
    title: str
    url: str
    content: str
    score: float | None = None
    retrieval_status: str = "search_service_extract"


class PublicSearchProvider(Protocol):
    provider_name: str
    search_tier: str

    @property
    def ready(self) -> bool: ...

    @property
    def readiness_message(self) -> str: ...

    def search(self, query: str, *, max_results: int = 5) -> list[SearchDocument]: ...


@dataclass(frozen=True)
class TavilySearchSettings:
    api_key: str
    base_url: str = "https://api.tavily.com"
    timeout_seconds: float = 45.0

    @classmethod
    def from_env(cls) -> "TavilySearchSettings":
        return cls(
            api_key=os.getenv("TAVILY_API_KEY", "").strip(),
            base_url=os.getenv("TAVILY_API_BASE_URL", "https://api.tavily.com").rstrip("/"),
            timeout_seconds=float(os.getenv("TOOL_TIMEOUT_SECONDS", "90") or "90"),
        )


class TavilySearchProvider:
    provider_name = "tavily"
    search_tier = "external_api"

    def __init__(
        self,
        settings: TavilySearchSettings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or TavilySearchSettings.from_env()
        self._transport = transport

    @property
    def ready(self) -> bool:
        return bool(self.settings.api_key)

    @property
    def readiness_message(self) -> str:
        if self.ready:
            return "Tavily公开网页搜索已就绪"
        return "未配置TAVILY_API_KEY"

    def search(self, query: str, *, max_results: int = 5) -> list[SearchDocument]:
        if not self.ready:
            raise ProviderNotConfigured(self.readiness_message)
        body = {
            "query": query,
            "search_depth": "basic",
            "max_results": max(1, min(max_results, 10)),
            "include_answer": False,
            "include_raw_content": False,
        }
        try:
            with httpx.Client(
                base_url=self.settings.base_url,
                timeout=self.settings.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.post(
                    "/search",
                    headers={
                        "Authorization": f"Bearer {self.settings.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise ProviderUnavailable("公开网页搜索超时；本次没有形成身份结论") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderUnavailable(
                f"Tavily公开网页搜索失败（HTTP {exc.response.status_code}）"
            ) from exc
        except (httpx.RequestError, ValueError) as exc:
            raise ProviderUnavailable("无法连接Tavily公开网页搜索") from exc

        documents: list[SearchDocument] = []
        for item in payload.get("results", []):
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            score: Any = item.get("score")
            documents.append(
                SearchDocument(
                    query=query,
                    title=str(item.get("title") or url)[:300],
                    url=url,
                    content=str(item.get("content") or "")[:3000],
                    score=float(score) if isinstance(score, (int, float)) else None,
                )
            )
        return documents


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style", "noscript", "svg", "template"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript", "svg", "template"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0 and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


def _is_public_web_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            return False
        if parsed.port not in {None, 80, 443}:
            return False
        hostname = parsed.hostname.casefold().rstrip(".")
        if hostname == "localhost" or hostname.endswith((".local", ".internal")):
            return False
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return True
        return not (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        )
    except ValueError:
        return False


@dataclass(frozen=True)
class BingRssTestSearchSettings:
    base_url: str = "https://cn.bing.com"
    timeout_seconds: float = 20.0
    max_page_bytes: int = 524_288

    @classmethod
    def from_env(cls) -> "BingRssTestSearchSettings":
        return cls(
            base_url=os.getenv("TEST_SEARCH_BASE_URL", "https://cn.bing.com").rstrip("/"),
            timeout_seconds=min(
                30.0,
                max(5.0, float(os.getenv("TOOL_TIMEOUT_SECONDS", "20") or "20")),
            ),
            max_page_bytes=max(
                65_536,
                int(os.getenv("TEST_SEARCH_MAX_PAGE_BYTES", "524288") or "524288"),
            ),
        )


class BingRssTestSearchProvider:
    """Keyless, fail-closed search for local testing; not a production search API."""

    provider_name = "bing_rss_test"
    search_tier = "test_only"

    def __init__(
        self,
        settings: BingRssTestSearchSettings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or BingRssTestSearchSettings.from_env()
        self._transport = transport

    @property
    def ready(self) -> bool:
        return True

    @property
    def readiness_message(self) -> str:
        return (
            "测试级免密钥搜索已启用；依赖Bing中国公开RSS和网页直读，"
            "可能受页面变化或网络限制影响，不得用于正式报告。"
        )

    def _fetch_direct_page(self, client: httpx.Client, initial_url: str) -> tuple[str, str] | None:
        current_url = initial_url
        for _hop in range(4):
            if not _is_public_web_url(current_url):
                return None
            with client.stream("GET", current_url, follow_redirects=False) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        return None
                    current_url = urljoin(current_url, location)
                    continue
                if response.status_code != 200:
                    return None
                content_type = response.headers.get("content-type", "").casefold()
                if content_type and not (
                    content_type.startswith("text/") or "application/xhtml+xml" in content_type
                ):
                    return None
                chunks: list[bytes] = []
                received = 0
                for chunk in response.iter_bytes():
                    remaining = self.settings.max_page_bytes - received
                    if remaining <= 0:
                        break
                    chunks.append(chunk[:remaining])
                    received += min(len(chunk), remaining)
                raw = b"".join(chunks)
                encoding = response.encoding or "utf-8"
                try:
                    page_text = raw.decode(encoding, errors="replace")
                except LookupError:
                    page_text = raw.decode("utf-8", errors="replace")
                final_url = str(response.url)
                parser = _VisibleTextParser()
                parser.feed(page_text)
                extracted = parser.text()[:3000]
                if len(extracted) < 80:
                    return None
                return final_url, extracted
        return None

    @staticmethod
    def _normalized_match_text(value: str) -> str:
        return "".join(character for character in value.casefold() if character.isalnum())

    @classmethod
    def _quoted_targets(cls, query: str) -> list[str]:
        return [
            normalized
            for phrase in re.findall(r'"([^"\r\n]{2,80})"', query)
            if (normalized := cls._normalized_match_text(phrase))
        ]

    @classmethod
    def _relevance_score(
        cls,
        *,
        title: str,
        url: str,
        content: str,
        quoted_targets: list[str],
    ) -> float | None:
        """Require an exact quoted anchor when present; reject broad token-only matches."""
        if not quoted_targets:
            return 1.0
        normalized_title = cls._normalized_match_text(title)
        normalized_url = cls._normalized_match_text(unquote(url))
        normalized_content = cls._normalized_match_text(content)
        score = 0.0
        for target in quoted_targets:
            if target in normalized_title:
                score += 4.0
            if target in normalized_content:
                score += 3.0
            if target in normalized_url:
                score += 2.0
        return score or None

    def search(self, query: str, *, max_results: int = 5) -> list[SearchDocument]:
        requested = max(1, min(max_results, 10))
        rss_query = " ".join(query.replace("\x00", " ").split())[:240]
        quoted_targets = self._quoted_targets(rss_query)
        try:
            with httpx.Client(
                base_url=self.settings.base_url,
                timeout=self.settings.timeout_seconds,
                transport=self._transport,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 LegalAIAnalysisAgentTest/0.2.3"
                    )
                },
            ) as client:
                response = client.get(
                    "/search",
                    params={
                        "q": rss_query,
                        "format": "rss",
                        "setlang": "zh-hans",
                        "mkt": "zh-CN",
                        "cc": "cn",
                    },
                )
                response.raise_for_status()
                if len(response.content) > 2_000_000:
                    raise ProviderUnavailable("测试搜索返回内容异常过大，已停止本次任务")
                try:
                    root = ET.fromstring(response.content)
                except ET.ParseError as exc:
                    raise ProviderUnavailable("测试搜索返回格式已变化，已停止本次任务") from exc

                documents: list[SearchDocument] = []
                seen: set[str] = set()
                attempted_pages = 0
                unreadable_pages = 0
                started_at = monotonic()
                candidate_limit = max(6, requested * 2)
                for index, item in enumerate(root.findall(".//item")):
                    if index >= candidate_limit or monotonic() - started_at > 45:
                        break
                    title = (item.findtext("title") or "").strip()
                    result_url = (item.findtext("link") or "").strip()
                    if not result_url or result_url in seen or not _is_public_web_url(result_url):
                        continue
                    seen.add(result_url)
                    attempted_pages += 1
                    try:
                        fetched = self._fetch_direct_page(client, result_url)
                    except httpx.HTTPError:
                        # Search results commonly mix sites with incompatible TLS,
                        # dead links, or connection blocks. One such page must not
                        # make a healthy RSS search look unavailable.
                        unreadable_pages += 1
                        continue
                    if not fetched:
                        unreadable_pages += 1
                        continue
                    final_url, content = fetched
                    score = self._relevance_score(
                        title=title,
                        url=final_url,
                        content=content,
                        quoted_targets=quoted_targets,
                    )
                    if score is None:
                        continue
                    documents.append(
                        SearchDocument(
                            query=query,
                            title=(title or final_url)[:300],
                            url=final_url,
                            content=content,
                            score=score,
                            retrieval_status="direct_page",
                        )
                    )
                    if len(documents) >= requested:
                        break
        except ProviderUnavailable:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderUnavailable("测试级公开搜索超时，已停止本次任务") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderUnavailable(
                f"测试级公开搜索失败（HTTP {exc.response.status_code}），已停止本次任务"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderUnavailable("无法连接测试级公开搜索，已停止本次任务") from exc

        if not documents:
            if attempted_pages and unreadable_pages == attempted_pages:
                raise ProviderUnavailable(
                    "测试搜索入口连接正常，但候选结果网页均无法直接读取，"
                    "已停止当前查询；不会使用模型记忆补造证据"
                )
            raise ProviderUnavailable(
                "测试搜索没有取得与精确名称相关且可直接读取的公开网页，"
                "已停止当前查询；不会使用模型记忆补造证据"
            )
        return sorted(documents, key=lambda item: item.score or 0.0, reverse=True)
