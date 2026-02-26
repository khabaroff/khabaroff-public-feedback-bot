from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Protocol


_BANNED_OUTPUT_TOKENS = (
    "бот",
    "анкета",
    "форма",
    "написал",
    "написала",
)

PostJSON = Callable[[str, dict[str, str], dict[str, Any]], Awaitable[dict[str, Any]]]


_SAFE_ANALYSIS_FALLBACK: dict[str, bool] = {
    "context": False,
    "moment": False,
    "style": False,
    "enough": False,
}


class LLMClient(Protocol):
    async def generate_review(self, system_prompt: str, payload: dict[str, Any]) -> str:
        ...

    async def rephrase_review(
        self, system_prompt: str, review_text: str, request: str
    ) -> str:
        ...

    async def analyze_answer(self, system_prompt: str, answer_text: str) -> dict[str, bool]:
        ...


def build_generation_payload(
    context: list[str],
    period: str,
    answers: list[dict[str, str]],
    signature: str,
) -> dict[str, Any]:
    return {
        "context": context,
        "period": period,
        "answers": answers,
        "signature": signature,
    }


def validate_review_text(text: str) -> list[str]:
    import re

    lowered = text.lower()
    violations: list[str] = []
    for token in _BANNED_OUTPUT_TOKENS:
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            violations.append(token)
    return violations


class AzureOpenAIClient:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str,
        post_json: PostJSON | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.deployment = deployment
        self.api_version = api_version
        self._post_json = post_json or self._default_post_json

    async def generate_review(self, system_prompt: str, payload: dict[str, Any]) -> str:
        body = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
        }
        result = await self._post_json(self._chat_url(), self._headers(), body)
        return _extract_chat_content(result, "Azure OpenAI")

    async def rephrase_review(
        self, system_prompt: str, review_text: str, request: str
    ) -> str:
        body = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "review": review_text,
                            "request": request,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        result = await self._post_json(self._chat_url(), self._headers(), body)
        return _extract_chat_content(result, "Azure OpenAI")

    async def analyze_answer(
        self, system_prompt: str, answer_text: str
    ) -> dict[str, bool]:
        body = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": answer_text},
            ],
            "temperature": 0.1,
        }
        try:
            result = await self._post_json(self._chat_url(), self._headers(), body)
            raw = _extract_chat_content(result, "Azure OpenAI")
            return _parse_analysis_json(raw)
        except Exception:
            return dict(_SAFE_ANALYSIS_FALLBACK)

    def _chat_url(self) -> str:
        return (
            f"{self.endpoint}/openai/deployments/{self.deployment}"
            f"/chat/completions?api-version={self.api_version}"
        )

    def _headers(self) -> dict[str, str]:
        return {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

    async def _default_post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        import aiohttp  # type: ignore

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                data = await response.json(content_type=None)
                return {
                    "status": response.status,
                    "json": data,
                }


class OpenRouterClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        post_json: PostJSON | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._post_json = post_json or self._default_post_json

    async def generate_review(self, system_prompt: str, payload: dict[str, Any]) -> str:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        }
        result = await self._post_json(self._chat_url(), self._headers(), body)
        return _extract_chat_content(result, "OpenRouter")

    async def rephrase_review(
        self, system_prompt: str, review_text: str, request: str
    ) -> str:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"review": review_text, "request": request},
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        result = await self._post_json(self._chat_url(), self._headers(), body)
        return _extract_chat_content(result, "OpenRouter")

    async def analyze_answer(
        self, system_prompt: str, answer_text: str
    ) -> dict[str, bool]:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": answer_text},
            ],
            "temperature": 0.1,
        }
        try:
            result = await self._post_json(self._chat_url(), self._headers(), body)
            raw = _extract_chat_content(result, "OpenRouter")
            return _parse_analysis_json(raw)
        except Exception:
            return dict(_SAFE_ANALYSIS_FALLBACK)

    def _chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _default_post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        import aiohttp  # type: ignore

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                data = await response.json(content_type=None)
                return {
                    "status": response.status,
                    "json": data,
                }


class FallbackLLMClient:
    def __init__(self, primary: LLMClient, fallback: LLMClient) -> None:
        self.primary = primary
        self.fallback = fallback

    async def generate_review(self, system_prompt: str, payload: dict[str, Any]) -> str:
        try:
            return await self.primary.generate_review(system_prompt, payload)
        except Exception as primary_error:
            try:
                return await self.fallback.generate_review(system_prompt, payload)
            except Exception as fallback_error:
                raise RuntimeError(
                    f"Primary and fallback LLM failed: {primary_error}; {fallback_error}"
                ) from fallback_error

    async def rephrase_review(
        self, system_prompt: str, review_text: str, request: str
    ) -> str:
        try:
            return await self.primary.rephrase_review(
                system_prompt, review_text, request
            )
        except Exception as primary_error:
            try:
                return await self.fallback.rephrase_review(
                    system_prompt, review_text, request
                )
            except Exception as fallback_error:
                raise RuntimeError(
                    f"Primary and fallback LLM failed: {primary_error}; {fallback_error}"
                ) from fallback_error

    async def analyze_answer(
        self, system_prompt: str, answer_text: str
    ) -> dict[str, bool]:
        try:
            return await self.primary.analyze_answer(system_prompt, answer_text)
        except Exception:
            try:
                return await self.fallback.analyze_answer(system_prompt, answer_text)
            except Exception:
                return dict(_SAFE_ANALYSIS_FALLBACK)


def _parse_analysis_json(raw: str) -> dict[str, bool]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    data = json.loads(cleaned)
    result: dict[str, bool] = {}
    for key in ("context", "moment", "style", "enough"):
        result[key] = bool(data.get(key, False))
    return result


def _extract_chat_content(result: dict[str, Any], provider_name: str) -> str:
    status = int(result.get("status", 500))
    payload = result.get("json", {})
    if status >= 400:
        error_text = payload.get("error", {}).get("message", "unknown error")
        raise RuntimeError(f"{provider_name} error {status}: {error_text}")

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError(f"{provider_name} response has no choices")

    message = choices[0].get("message", {})
    content = message.get("content", "")

    if isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                if text:
                    pieces.append(text)
            elif isinstance(item, str):
                if item.strip():
                    pieces.append(item.strip())
        content = "\n".join(pieces)

    text_content = str(content).strip()
    if not text_content:
        raise RuntimeError(f"{provider_name} returned empty content")
    return text_content

