from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass
class PendingTranscript:
    answer_key: str
    job_id: str


@dataclass
class TranscriptCollection:
    transcripts: dict[str, str]
    failed: list[str]
    pending: list[str]


RequestJSON = Callable[[str, str, dict[str, str], object], Awaitable[dict[str, Any]]]


class AssemblyAIClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.assemblyai.com/v2",
        request_json: RequestJSON | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._request_json = request_json or self._default_request_json

    async def upload_and_start(self, audio_bytes: bytes) -> str:
        upload_result = await self._request_json(
            "POST",
            f"{self.base_url}/upload",
            self._headers(),
            audio_bytes,
        )
        upload_payload = upload_result.get("json", {})
        upload_url = str(upload_payload.get("upload_url", "")).strip()
        if int(upload_result.get("status", 500)) >= 400 or not upload_url:
            raise RuntimeError("AssemblyAI upload failed")

        transcript_result = await self._request_json(
            "POST",
            f"{self.base_url}/transcript",
            self._headers(),
            {
                "audio_url": upload_url,
                "language_code": "ru",
            },
        )
        transcript_payload = transcript_result.get("json", {})
        job_id = str(transcript_payload.get("id", "")).strip()
        if int(transcript_result.get("status", 500)) >= 400 or not job_id:
            raise RuntimeError("AssemblyAI transcript start failed")
        return job_id

    async def poll_job(self, job_id: str) -> dict[str, str]:
        result = await self._request_json(
            "GET",
            f"{self.base_url}/transcript/{job_id}",
            self._headers(),
            None,
        )
        payload = result.get("json", {})
        if int(result.get("status", 500)) >= 400:
            return {"status": "error", "error": str(payload)}
        return {
            "status": str(payload.get("status", "processing")),
            "text": str(payload.get("text", "")),
        }

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": self.api_key,
            "content-type": "application/json",
        }

    async def _default_request_json(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: object,
    ) -> dict[str, Any]:
        import aiohttp  # type: ignore

        request_kwargs: dict[str, Any] = {"headers": headers}
        if isinstance(payload, (bytes, bytearray)):
            request_kwargs["data"] = payload
            request_kwargs["headers"] = {k: v for k, v in headers.items() if k.lower() != "content-type"}
        elif isinstance(payload, dict):
            request_kwargs["json"] = payload

        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, **request_kwargs) as response:
                data = await response.json(content_type=None)
                return {
                    "status": response.status,
                    "json": data,
                }


class VoicePipeline:
    def __init__(self, client: object, poll_interval: float = 0.0) -> None:
        self.client = client
        self.poll_interval = poll_interval

    async def register_voice_answer(
        self, answer_key: str, audio_bytes: bytes
    ) -> PendingTranscript:
        job_id = await self.client.upload_and_start(audio_bytes)
        return PendingTranscript(answer_key=answer_key, job_id=job_id)

    async def collect_transcripts(
        self, pending_jobs: list[PendingTranscript], max_attempts: int = 5
    ) -> TranscriptCollection:
        remaining = list(pending_jobs)
        transcripts: dict[str, str] = {}
        failed: list[str] = []

        for attempt in range(max(1, max_attempts)):
            if not remaining:
                break

            next_remaining: list[PendingTranscript] = []
            for item in remaining:
                result = await self.client.poll_job(item.job_id)
                status = str(result.get("status", "")).lower()
                if status == "completed":
                    transcripts[item.answer_key] = str(result.get("text", "")).strip()
                elif status in {"error", "failed"}:
                    failed.append(item.answer_key)
                else:
                    next_remaining.append(item)

            remaining = next_remaining
            if remaining and attempt < max_attempts - 1 and self.poll_interval > 0:
                await asyncio.sleep(self.poll_interval)

        return TranscriptCollection(
            transcripts=transcripts,
            failed=failed,
            pending=[item.answer_key for item in remaining],
        )


async def download_telegram_voice_bytes(bot: Any, voice: Any) -> bytes:
    file_info = await bot.get_file(voice.file_id)
    downloaded = await bot.download_file(file_info.file_path)

    if isinstance(downloaded, (bytes, bytearray)):
        return bytes(downloaded)
    if isinstance(downloaded, io.BytesIO):
        return downloaded.getvalue()
    if hasattr(downloaded, "read"):
        data = downloaded.read()
        if asyncio.iscoroutine(data):
            data = await data
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)

    raise RuntimeError("Unsupported voice download response type")
