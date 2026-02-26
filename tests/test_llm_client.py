from __future__ import annotations

import json
import unittest

from bot.llm import AzureOpenAIClient, OpenRouterClient


class TestAzureOpenAIClient(unittest.IsolatedAsyncioTestCase):
    async def test_generate_review_uses_chat_completion_payload(self) -> None:
        calls = []

        async def fake_post(url: str, headers: dict, payload: dict) -> dict:
            calls.append((url, headers, payload))
            return {
                "status": 200,
                "json": {
                    "choices": [
                        {"message": {"content": "Generated review"}}
                    ]
                },
            }

        client = AzureOpenAIClient(
            endpoint="https://example.openai.azure.com",
            api_key="secret",
            deployment="gpt-4o",
            api_version="2025-04-01-preview",
            post_json=fake_post,
        )

        text = await client.generate_review("system prompt", {"answers": []})

        self.assertEqual(text, "Generated review")
        self.assertEqual(len(calls), 1)
        url, headers, payload = calls[0]
        self.assertIn("/chat/completions?api-version=2025-04-01-preview", url)
        self.assertEqual(headers["api-key"], "secret")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertNotIn("temperature", payload)

    async def test_generate_review_handles_api_errors(self) -> None:
        async def fake_post(url: str, headers: dict, payload: dict) -> dict:
            return {"status": 500, "json": {"error": {"message": "boom"}}}

        client = AzureOpenAIClient(
            endpoint="https://example.openai.azure.com",
            api_key="secret",
            deployment="gpt-4o",
            api_version="2025-04-01-preview",
            post_json=fake_post,
        )

        with self.assertRaises(RuntimeError):
            await client.generate_review("system prompt", {"answers": []})

    async def test_rephrase_review_omits_temperature(self) -> None:
        calls = []

        async def fake_post(url: str, headers: dict, payload: dict) -> dict:
            calls.append(payload)
            return {
                "status": 200,
                "json": {
                    "choices": [
                        {"message": {"content": "Updated review"}}
                    ]
                },
            }

        client = AzureOpenAIClient(
            endpoint="https://example.openai.azure.com",
            api_key="secret",
            deployment="gpt-4o",
            api_version="2025-04-01-preview",
            post_json=fake_post,
        )

        text = await client.rephrase_review("system", "old", "make shorter")

        self.assertEqual(text, "Updated review")
        self.assertEqual(len(calls), 1)
        self.assertNotIn("temperature", calls[0])

    async def test_analyze_answer_parses_json_response(self) -> None:
        calls = []
        response_json = json.dumps(
            {"context": True, "moment": False, "style": True, "enough": False}
        )

        async def fake_post(url: str, headers: dict, payload: dict) -> dict:
            calls.append(payload)
            return {
                "status": 200,
                "json": {
                    "choices": [
                        {"message": {"content": response_json}}
                    ]
                },
            }

        client = AzureOpenAIClient(
            endpoint="https://example.openai.azure.com",
            api_key="secret",
            deployment="gpt-4o",
            api_version="2025-04-01-preview",
            post_json=fake_post,
        )

        result = await client.analyze_answer("system analyze", "user text here")

        self.assertEqual(result["context"], True)
        self.assertEqual(result["moment"], False)
        self.assertEqual(result["style"], True)
        self.assertEqual(result["enough"], False)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["temperature"], 0.1)
        self.assertEqual(calls[0]["messages"][1]["content"], "user text here")

    async def test_analyze_answer_returns_fallback_on_error(self) -> None:
        async def fake_post(url: str, headers: dict, payload: dict) -> dict:
            return {"status": 500, "json": {"error": {"message": "boom"}}}

        client = AzureOpenAIClient(
            endpoint="https://example.openai.azure.com",
            api_key="secret",
            deployment="gpt-4o",
            api_version="2025-04-01-preview",
            post_json=fake_post,
        )

        result = await client.analyze_answer("system", "text")

        self.assertFalse(result["context"])
        self.assertFalse(result["moment"])
        self.assertFalse(result["style"])
        self.assertFalse(result["enough"])

    async def test_analyze_answer_handles_markdown_wrapped_json(self) -> None:
        response_text = '```json\n{"context": true, "moment": true, "style": false, "enough": false}\n```'

        async def fake_post(url: str, headers: dict, payload: dict) -> dict:
            return {
                "status": 200,
                "json": {
                    "choices": [
                        {"message": {"content": response_text}}
                    ]
                },
            }

        client = AzureOpenAIClient(
            endpoint="https://example.openai.azure.com",
            api_key="secret",
            deployment="gpt-4o",
            api_version="2025-04-01-preview",
            post_json=fake_post,
        )

        result = await client.analyze_answer("system", "text")

        self.assertTrue(result["context"])
        self.assertTrue(result["moment"])
        self.assertFalse(result["style"])
        self.assertFalse(result["enough"])


class TestOpenRouterClient(unittest.IsolatedAsyncioTestCase):
    async def test_generate_review_uses_openrouter_payload(self) -> None:
        calls = []

        async def fake_post(url: str, headers: dict, payload: dict) -> dict:
            calls.append((url, headers, payload))
            return {
                "status": 200,
                "json": {
                    "choices": [
                        {"message": {"content": "Grok review"}}
                    ]
                },
            }

        client = OpenRouterClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="or-key",
            model="x-ai/grok-4.1-fast",
            post_json=fake_post,
        )
        text = await client.generate_review("system prompt", {"answers": []})

        self.assertEqual(text, "Grok review")
        self.assertEqual(len(calls), 1)
        url, headers, payload = calls[0]
        self.assertEqual(url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer or-key")
        self.assertEqual(payload["model"], "x-ai/grok-4.1-fast")


if __name__ == "__main__":
    unittest.main()
