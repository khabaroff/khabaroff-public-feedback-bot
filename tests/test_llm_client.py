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

    async def test_analyze_answer_parses_json_with_questions(self) -> None:
        calls = []
        response_json = json.dumps(
            {
                "context": True,
                "moment": False,
                "style": True,
                "questions": ["Q1 about moment", "Q2 about style"],
            }
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

        self.assertTrue(result["context"])
        self.assertFalse(result["moment"])
        self.assertTrue(result["style"])
        self.assertEqual(result["questions"], ["Q1 about moment", "Q2 about style"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["temperature"], 0.3)

    async def test_analyze_answer_retries_on_bad_json(self) -> None:
        attempt = {"count": 0}
        good_json = json.dumps(
            {"context": True, "moment": True, "style": True, "questions": ["Q1", "Q2"]}
        )

        async def fake_post(url: str, headers: dict, payload: dict) -> dict:
            attempt["count"] += 1
            if attempt["count"] <= 2:
                return {
                    "status": 200,
                    "json": {"choices": [{"message": {"content": "not json at all"}}]},
                }
            return {
                "status": 200,
                "json": {"choices": [{"message": {"content": good_json}}]},
            }

        client = AzureOpenAIClient(
            endpoint="https://example.openai.azure.com",
            api_key="secret",
            deployment="gpt-4o",
            api_version="2025-04-01-preview",
            post_json=fake_post,
        )

        result = await client.analyze_answer("system", "text")

        self.assertEqual(attempt["count"], 3)
        self.assertTrue(result["moment"])
        self.assertEqual(result["questions"], ["Q1", "Q2"])

    async def test_analyze_answer_raises_after_3_failures(self) -> None:
        async def fake_post(url: str, headers: dict, payload: dict) -> dict:
            return {
                "status": 200,
                "json": {"choices": [{"message": {"content": "broken"}}]},
            }

        client = AzureOpenAIClient(
            endpoint="https://example.openai.azure.com",
            api_key="secret",
            deployment="gpt-4o",
            api_version="2025-04-01-preview",
            post_json=fake_post,
        )

        with self.assertRaises(RuntimeError):
            await client.analyze_answer("system", "text")

    async def test_analyze_answer_handles_markdown_wrapped_json(self) -> None:
        response_text = '```json\n{"context": true, "moment": true, "style": false, "questions": ["Q1"]}\n```'

        async def fake_post(url: str, headers: dict, payload: dict) -> dict:
            return {
                "status": 200,
                "json": {"choices": [{"message": {"content": response_text}}]},
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
        self.assertEqual(result["questions"], ["Q1"])


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
