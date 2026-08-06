from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .provider_errors import ProviderInvalidResponse, ProviderNotConfigured, ProviderUnavailable


class StructuredModelProvider(Protocol):
    provider_name: str
    model_name: str

    @property
    def ready(self) -> bool: ...

    @property
    def readiness_message(self) -> str: ...

    def generate_json(self, system_prompt: str, user_prompt: str) -> str: ...


StructuredResult = TypeVar("StructuredResult", bound=BaseModel)


def generate_validated_json(
    model: StructuredModelProvider,
    system_prompt: str,
    user_prompt: str,
    output_type: type[StructuredResult],
    *,
    contract_name: str,
) -> StructuredResult:
    """Validate structured output and make one evidence-preserving repair attempt."""
    active_prompt = user_prompt
    for attempt in range(2):
        output_text = model.generate_json(system_prompt, active_prompt)
        try:
            return output_type.model_validate(json.loads(output_text))
        except (json.JSONDecodeError, ValidationError) as exc:
            if attempt:
                raise ProviderInvalidResponse(
                    f"{contract_name}；已自动修复重试，但仍无法形成可用结果"
                ) from exc
            detail = (
                json.dumps(exc.errors(include_url=False), ensure_ascii=False)[:2400]
                if isinstance(exc, ValidationError)
                else str(exc)[:2400]
            )
            active_prompt = f"""{user_prompt}

格式修复任务：上一次输出未通过程序校验。只能修复JSON语法、缺失字段、字段类型、枚举值和层级；不得增加公开证据中没有的事实、主体、产品、功能或URL。不要解释，直接重新输出完整JSON对象。
校验错误：{detail}
上一次输出：
{output_text[:12000]}
"""
    raise ProviderInvalidResponse(contract_name)


@dataclass(frozen=True)
class ChatCompletionsSettings:
    provider_name: str
    api_key_name: str
    api_key: str
    model: str
    base_url: str
    timeout_seconds: float = 90.0
    max_retries: int = 1
    max_tokens: int = 4096

    @classmethod
    def deepseek_from_env(cls) -> "ChatCompletionsSettings":
        return cls(
            provider_name="deepseek",
            api_key_name="DEEPSEEK_API_KEY",
            api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            model=os.getenv("MODEL_CLASSIFIER", "deepseek-v4-flash").strip()
            or "deepseek-v4-flash",
            base_url=os.getenv("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com").rstrip("/"),
            timeout_seconds=float(os.getenv("TOOL_TIMEOUT_SECONDS", "90") or "90"),
            max_retries=max(0, int(os.getenv("MAX_TOOL_RETRIES", "1") or "1")),
            max_tokens=max(512, int(os.getenv("MODEL_MAX_OUTPUT_TOKENS", "4096") or "4096")),
        )

    @classmethod
    def compatible_from_env(cls) -> "ChatCompletionsSettings":
        return cls(
            provider_name=os.getenv("MODEL_PROVIDER_LABEL", "openai_compatible").strip()
            or "openai_compatible",
            api_key_name="MODEL_API_KEY",
            api_key=os.getenv("MODEL_API_KEY", "").strip(),
            model=os.getenv("MODEL_CLASSIFIER", "").strip(),
            base_url=os.getenv("MODEL_API_BASE_URL", "").rstrip("/"),
            timeout_seconds=float(os.getenv("TOOL_TIMEOUT_SECONDS", "90") or "90"),
            max_retries=max(0, int(os.getenv("MAX_TOOL_RETRIES", "1") or "1")),
            max_tokens=max(512, int(os.getenv("MODEL_MAX_OUTPUT_TOKENS", "4096") or "4096")),
        )


class OpenAICompatibleJSONModel:
    """JSON-mode adapter for OpenAI-compatible Chat Completions APIs."""

    def __init__(
        self,
        settings: ChatCompletionsSettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.provider_name = settings.provider_name
        self.model_name = settings.model
        self._transport = transport

    @property
    def ready(self) -> bool:
        return bool(self.settings.api_key and self.settings.model and self.settings.base_url)

    @property
    def readiness_message(self) -> str:
        missing: list[str] = []
        if not self.settings.api_key:
            missing.append(self.settings.api_key_name)
        if not self.settings.model:
            missing.append("MODEL_CLASSIFIER")
        if not self.settings.base_url:
            missing.append("MODEL_API_BASE_URL")
        if missing:
            return f"未配置{'、'.join(missing)}"
        return f"{self.provider_name}模型接口已就绪"

    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        if not self.ready:
            raise ProviderNotConfigured(self.readiness_message)
        body = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
            "max_tokens": self.settings.max_tokens,
        }
        if self.provider_name == "deepseek":
            # DeepSeek V4 defaults to thinking mode. For strict JSON extraction,
            # disabling it avoids spending the completion budget on reasoning
            # while leaving the final content empty.
            body["thinking"] = {"type": "disabled"}
        last_empty = False
        for attempt in range(self.settings.max_retries + 1):
            request_body = dict(body)
            if attempt:
                request_body["messages"] = [
                    *body["messages"],
                    {
                        "role": "user",
                        "content": (
                            "上次响应正文为空。请不要输出解释或思考过程，"
                            "立即按照既定Schema输出一个完整JSON对象。"
                        ),
                    },
                ]
            try:
                with httpx.Client(
                    base_url=self.settings.base_url,
                    timeout=self.settings.timeout_seconds,
                    transport=self._transport,
                ) as client:
                    response = client.post(
                        "/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.settings.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=request_body,
                    )
                    response.raise_for_status()
                    payload = response.json()
            except httpx.TimeoutException as exc:
                raise ProviderUnavailable(f"{self.provider_name}模型调用超时，请稍后重试") from exc
            except httpx.HTTPStatusError as exc:
                detail = ""
                try:
                    detail = exc.response.json().get("error", {}).get("message", "")
                except (ValueError, AttributeError):
                    pass
                suffix = f"：{detail[:240]}" if detail else ""
                raise ProviderUnavailable(
                    f"{self.provider_name}模型调用失败（HTTP {exc.response.status_code}）{suffix}"
                ) from exc
            except (httpx.RequestError, ValueError) as exc:
                raise ProviderUnavailable(f"无法连接{self.provider_name}模型接口") from exc

            try:
                content = payload["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise ProviderInvalidResponse(f"{self.provider_name}没有返回标准对话结果") from exc
            if isinstance(content, str) and content.strip():
                return content
            last_empty = True

        if last_empty:
            raise ProviderInvalidResponse(
                f"{self.provider_name}返回了空内容；已自动重试，未形成身份结论"
            )
        raise ProviderInvalidResponse(f"{self.provider_name}没有返回可解析内容")
