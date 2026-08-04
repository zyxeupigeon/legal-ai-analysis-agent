from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Protocol

import httpx

from .provider_errors import ProviderNotConfigured, ProviderUnavailable


@dataclass(frozen=True)
class SearchDocument:
    query: str
    title: str
    url: str
    content: str
    score: float | None = None


class PublicSearchProvider(Protocol):
    provider_name: str

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
