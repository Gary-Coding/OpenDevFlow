import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status

from app.core.crypto import decrypt_secret
from app.models.ai_model import ModelProvider


@dataclass(frozen=True)
class ModelProviderConfig:
    provider_type: str
    base_url: str
    api_key_encrypted: str | None
    default_model: str | None


def snapshot_model_provider(provider: ModelProvider) -> ModelProviderConfig:
    return ModelProviderConfig(
        provider_type=provider.provider_type,
        base_url=provider.base_url,
        api_key_encrypted=provider.api_key_encrypted,
        default_model=provider.default_model,
    )


def _normalize_base_url(base_url: str) -> str:
    return base_url.strip().rstrip("/")


def _provider_headers(provider: ModelProviderConfig, api_key: str) -> dict[str, str]:
    if provider.provider_type == "anthropic_compatible":
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _chat_urls(provider: ModelProviderConfig) -> list[str]:
    base_url = _normalize_base_url(provider.base_url)
    if provider.provider_type == "anthropic_compatible":
        return [f"{base_url}/messages"]
    urls = [f"{base_url}/chat/completions"]
    if not base_url.endswith("/v1"):
        urls.append(f"{base_url}/v1/chat/completions")
    return urls


def _openai_payload(model: str, system_prompt: str, user_prompt: str) -> dict:
    return {
        "model": model,
        "stream": True,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }


def _anthropic_payload(model: str, system_prompt: str, user_prompt: str) -> dict:
    return {
        "model": model,
        "stream": True,
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }


async def stream_chat_completion(
    provider: ModelProviderConfig,
    system_prompt: str,
    user_prompt: str,
) -> AsyncIterator[str]:
    api_key = decrypt_secret(provider.api_key_encrypted)
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先配置 API Key")
    if not provider.default_model:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先设置默认模型")

    is_anthropic = provider.provider_type == "anthropic_compatible"
    payload = (
        _anthropic_payload(provider.default_model, system_prompt, user_prompt)
        if is_anthropic
        else _openai_payload(provider.default_model, system_prompt, user_prompt)
    )
    headers = _provider_headers(provider, api_key)
    timeout = httpx.Timeout(120.0, connect=10.0)
    last_error = ""

    async with httpx.AsyncClient(timeout=timeout) as client:
        for url in _chat_urls(provider):
            try:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code >= 400:
                        body = (await response.aread()).decode("utf-8", errors="ignore")
                        last_error = f"模型服务调用失败：HTTP {response.status_code} {body[:200]}"
                        continue
                    yielded = False
                    if is_anthropic:
                        async for chunk in _iter_anthropic_chunks(response):
                            yielded = True
                            yield chunk
                    else:
                        async for chunk in _iter_openai_chunks(response):
                            yielded = True
                            yield chunk
                    if yielded:
                        return
                    content_type = response.headers.get("content-type", "")
                    last_error = f"模型服务未返回有效流内容：{content_type or 'unknown content-type'}"
            except httpx.TimeoutException:
                last_error = "模型服务连接超时"
            except httpx.HTTPError as exc:
                last_error = f"模型服务连接失败：{exc.__class__.__name__}"

    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=last_error or "模型服务调用失败")


async def _iter_openai_chunks(response: httpx.Response) -> AsyncIterator[str]:
    async for line in response.aiter_lines():
        if not line:
            continue
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            break
        try:
            payload = json.loads(data)
        except ValueError:
            continue
        choices = payload.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta", {}).get("content")
        if delta:
            yield delta


async def _iter_anthropic_chunks(response: httpx.Response) -> AsyncIterator[str]:
    async for line in response.aiter_lines():
        if not line or not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        try:
            payload = json.loads(data)
        except ValueError:
            continue
        if payload.get("type") == "content_block_delta":
            text = payload.get("delta", {}).get("text")
            if text:
                yield text
