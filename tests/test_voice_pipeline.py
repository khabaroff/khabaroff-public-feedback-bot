from __future__ import annotations

import unittest
from dataclasses import dataclass

from bot.voice import PendingTranscript, VoicePipeline


@dataclass
class FakeClient:
    jobs: dict[str, str]

    async def upload_and_start(self, audio_bytes: bytes) -> str:
        if not audio_bytes:
            raise ValueError("empty audio")
        return "job-1"

    async def poll_job(self, job_id: str) -> dict[str, str]:
        status = self.jobs.get(job_id, "processing")
        if status == "completed":
            return {"status": "completed", "text": "распознанный текст"}
        if status == "error":
            return {"status": "error", "error": "boom"}
        return {"status": "processing"}


class TestVoicePipeline(unittest.IsolatedAsyncioTestCase):
    async def test_register_job(self) -> None:
        pipeline = VoicePipeline(FakeClient(jobs={}))
        pending = await pipeline.register_voice_answer("open", b"voice")
        self.assertIsInstance(pending, PendingTranscript)
        self.assertEqual(pending.answer_key, "open")
        self.assertEqual(pending.job_id, "job-1")

    async def test_collect_transcripts_success(self) -> None:
        pipeline = VoicePipeline(FakeClient(jobs={"job-1": "completed"}))
        pending = [PendingTranscript(answer_key="open", job_id="job-1")]

        result = await pipeline.collect_transcripts(pending, max_attempts=1)
        self.assertEqual(result.transcripts["open"], "распознанный текст")
        self.assertEqual(result.failed, [])

    async def test_collect_transcripts_failure_and_timeout(self) -> None:
        pipeline = VoicePipeline(FakeClient(jobs={"job-err": "error", "job-wait": "processing"}))
        pending = [
            PendingTranscript(answer_key="q1", job_id="job-err"),
            PendingTranscript(answer_key="q2", job_id="job-wait"),
        ]

        result = await pipeline.collect_transcripts(pending, max_attempts=1)
        self.assertIn("q1", result.failed)
        self.assertIn("q2", result.pending)


if __name__ == "__main__":
    unittest.main()
