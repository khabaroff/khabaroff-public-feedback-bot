from __future__ import annotations

import unittest

from bot.llm import FallbackLLMClient


class _PrimaryFail:
    async def generate_review(self, system_prompt: str, payload: dict) -> str:
        raise RuntimeError("azure failed")

    async def rephrase_review(self, system_prompt: str, review_text: str, request: str) -> str:
        raise RuntimeError("azure failed")


class _PrimaryOk:
    async def generate_review(self, system_prompt: str, payload: dict) -> str:
        return "azure ok"

    async def rephrase_review(self, system_prompt: str, review_text: str, request: str) -> str:
        return "azure rephrase ok"


class _Fallback:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_review(self, system_prompt: str, payload: dict) -> str:
        self.calls += 1
        return "grok ok"

    async def rephrase_review(self, system_prompt: str, review_text: str, request: str) -> str:
        self.calls += 1
        return "grok rephrase ok"


class TestFallbackLLMClient(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_used_on_primary_error(self) -> None:
        fallback = _Fallback()
        client = FallbackLLMClient(primary=_PrimaryFail(), fallback=fallback)

        text = await client.generate_review("system", {"answers": []})

        self.assertEqual(text, "grok ok")
        self.assertEqual(fallback.calls, 1)

    async def test_fallback_not_used_when_primary_ok(self) -> None:
        fallback = _Fallback()
        client = FallbackLLMClient(primary=_PrimaryOk(), fallback=fallback)

        text = await client.generate_review("system", {"answers": []})

        self.assertEqual(text, "azure ok")
        self.assertEqual(fallback.calls, 0)


if __name__ == "__main__":
    unittest.main()

