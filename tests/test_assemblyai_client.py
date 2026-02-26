from __future__ import annotations

import unittest

from bot.voice import AssemblyAIClient


class TestAssemblyAIClient(unittest.IsolatedAsyncioTestCase):
    async def test_upload_and_start(self) -> None:
        calls = []

        async def fake_request(method: str, url: str, headers: dict, payload: object) -> dict:
            calls.append((method, url, headers, payload))
            if url.endswith("/upload"):
                return {"status": 200, "json": {"upload_url": "https://u"}}
            return {"status": 200, "json": {"id": "job-1"}}

        client = AssemblyAIClient(api_key="key", request_json=fake_request)
        job_id = await client.upload_and_start(b"voice")

        self.assertEqual(job_id, "job-1")
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0][1].endswith("/upload"))
        self.assertTrue(calls[1][1].endswith("/transcript"))

    async def test_poll_job(self) -> None:
        async def fake_request(method: str, url: str, headers: dict, payload: object) -> dict:
            return {"status": 200, "json": {"status": "completed", "text": "ok"}}

        client = AssemblyAIClient(api_key="key", request_json=fake_request)
        result = await client.poll_job("job-1")

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["text"], "ok")


if __name__ == "__main__":
    unittest.main()
