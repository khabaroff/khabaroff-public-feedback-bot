from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class ConfigError(ValueError):
    """Raised when required environment configuration is missing."""


class ContentError(ValueError):
    """Raised when content/prompts cannot be loaded or validated."""


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    owner_telegram_id: int
    assemblyai_api_key: str
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_model: str
    azure_openai_api_version: str = "2025-04-01-preview"
    azure_openai_deployment: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = ""
    db_path: str = "reviews.db"
    video_note_path: str = ""


@dataclass(frozen=True)
class AppContent:
    texts: dict[str, str]
    thinking_phrases: list[str]
    generate_prompt: str
    rephrase_prompt: str
    analyze_prompt: str
    clarify_questions: dict[str, list[str]]
    review_template: dict[str, Any]


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    if env is None:
        source: dict[str, str] = dict(os.environ)
        env_path = Path(source.get("ENV_FILE", ".env"))
        if env_path.exists():
            dotenv_values = _load_env_file(env_path)
            for key, value in dotenv_values.items():
                if not source.get(key):
                    source[key] = value

        creds_path = Path(source.get("CREDS_FILE", "creds.txt"))
        if creds_path.exists():
            fallback = _load_creds_file(creds_path)
            for key, value in fallback.items():
                if not source.get(key):
                    source[key] = value
    else:
        source = dict(env)
    required = {
        "TELEGRAM_BOT_TOKEN": source.get("TELEGRAM_BOT_TOKEN", "").strip(),
        "OWNER_TELEGRAM_ID": source.get("OWNER_TELEGRAM_ID", "").strip(),
        "ASSEMBLYAI_API_KEY": source.get("ASSEMBLYAI_API_KEY", "").strip(),
        "AZURE_OPENAI_API_KEY": source.get("AZURE_OPENAI_API_KEY", "").strip(),
        "AZURE_OPENAI_ENDPOINT": source.get("AZURE_OPENAI_ENDPOINT", "").strip(),
        "AZURE_OPENAI_MODEL": source.get("AZURE_OPENAI_MODEL", "").strip(),
    }

    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ConfigError(f"Missing required environment variables: {', '.join(missing)}")

    try:
        owner_id = int(required["OWNER_TELEGRAM_ID"])
    except ValueError as exc:
        raise ConfigError("OWNER_TELEGRAM_ID must be an integer") from exc

    return Settings(
        telegram_bot_token=required["TELEGRAM_BOT_TOKEN"],
        owner_telegram_id=owner_id,
        assemblyai_api_key=required["ASSEMBLYAI_API_KEY"],
        azure_openai_api_key=required["AZURE_OPENAI_API_KEY"],
        azure_openai_endpoint=required["AZURE_OPENAI_ENDPOINT"],
        azure_openai_model=required["AZURE_OPENAI_MODEL"],
        azure_openai_api_version=source.get(
            "AZURE_OPENAI_API_VERSION", "2025-04-01-preview"
        ),
        azure_openai_deployment=source.get(
            "AZURE_OPENAI_DEPLOYMENT", required["AZURE_OPENAI_MODEL"]
        ),
        openrouter_api_key=source.get("OPENROUTER_API_KEY", "").strip(),
        openrouter_base_url=source.get(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ).strip(),
        openrouter_model=source.get("OPENROUTER_MODEL", "").strip(),
        db_path=source.get("DB_PATH", "reviews.db"),
        video_note_path=source.get("WELCOME_VIDEO_NOTE_PATH", ""),
    )


def load_content(base_dir: Path | str) -> AppContent:
    root = Path(base_dir)
    texts = _as_string_map(_load_yaml_file(root / "content" / "texts.yaml"))
    thinking = _load_yaml_file(root / "content" / "thinking.yaml")
    generate_prompt = _read_required_text(root / "prompts" / "generate_review.md")
    rephrase_prompt = _read_required_text(root / "prompts" / "rephrase_review.md")
    analyze_prompt = _read_required_text(root / "prompts" / "analyze_answer.md")
    clarify_raw = _load_yaml_file(root / "content" / "clarify_questions.yaml")
    review_template_raw = _load_yaml_file(root / "content" / "review_template.yaml")

    required_text_keys = ("greeting_intro", "cta_start")
    missing_texts = [key for key in required_text_keys if not texts.get(key)]
    if missing_texts:
        raise ContentError(
            f"Missing required content.texts keys: {', '.join(missing_texts)}"
        )

    phrases = thinking.get("phrases") if isinstance(thinking, dict) else None
    if not isinstance(phrases, list):
        raise ContentError("content/thinking.yaml must include list key 'phrases'")
    normalized_phrases = [str(item).strip() for item in phrases if str(item).strip()]
    if not normalized_phrases:
        raise ContentError("content/thinking.yaml key 'phrases' must not be empty")

    if not isinstance(clarify_raw, dict):
        raise ContentError("content/clarify_questions.yaml must be a mapping")
    clarify_questions: dict[str, list[str]] = {}
    for cq_key in ("moment", "style", "context"):
        items = clarify_raw.get(cq_key)
        if not isinstance(items, list) or not items:
            raise ContentError(
                f"content/clarify_questions.yaml key '{cq_key}' must be a non-empty list"
            )
        clarify_questions[cq_key] = [str(q).strip() for q in items]

    review_template = review_template_raw if isinstance(review_template_raw, dict) else {}

    return AppContent(
        texts=texts,
        thinking_phrases=normalized_phrases,
        generate_prompt=generate_prompt,
        rephrase_prompt=rephrase_prompt,
        analyze_prompt=analyze_prompt,
        clarify_questions=clarify_questions,
        review_template=review_template,
    )


def _read_required_text(path: Path) -> str:
    if not path.exists():
        raise ContentError(f"Missing required file: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ContentError(f"File is empty: {path}")
    return text


def _as_string_map(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ContentError("texts.yaml must be a mapping")
    result: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(value, (str, int, float, bool)):
            result[str(key)] = str(value)
    return result


def _load_yaml_file(path: Path) -> Any:
    if not path.exists():
        raise ContentError(f"Missing required file: {path}")
    text = path.read_text(encoding="utf-8")
    if "\n" not in text and "\\n" in text:
        text = text.replace("\\n", "\n")
    if not text.strip():
        raise ContentError(f"File is empty: {path}")

    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except Exception:
        return _parse_simple_yaml(text)


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_list_key: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0 and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if not value:
                data[key] = []
                current_list_key = key
            elif value == "[]":
                data[key] = []
                current_list_key = None
            else:
                data[key] = _strip_quotes(value)
                current_list_key = None
            continue

        if stripped.startswith("- "):
            if current_list_key is None:
                raise ContentError("Invalid YAML list structure")
            data[current_list_key].append(_strip_quotes(stripped[2:].strip()))
            continue

        raise ContentError("Unsupported YAML structure for built-in parser")

    return data


def _strip_quotes(value: str) -> str:
    if (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    ) and len(value) >= 2:
        return value[1:-1]
    return value


def _load_creds_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    section_hint = ""

    for line in lines:
        if not line:
            continue

        lower = line.lower()

        if "=" in line:
            key, raw_value = line.split("=", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            if key and raw_value:
                values[key] = raw_value
                continue

        if _looks_like_bot_token(line) and "TELEGRAM_BOT_TOKEN" not in values:
            values["TELEGRAM_BOT_TOKEN"] = line
            continue

        if line.startswith("http") and "azure.com" in lower and "openai" in lower:
            values.setdefault("AZURE_OPENAI_ENDPOINT", line)
            continue

        if line.startswith("gpt-") and "AZURE_OPENAI_MODEL" not in values:
            values["AZURE_OPENAI_MODEL"] = line
            continue

        if _looks_like_secret_token(line):
            if "assembly" in section_hint and "ASSEMBLYAI_API_KEY" not in values:
                values["ASSEMBLYAI_API_KEY"] = line
                continue
            if "azure" in section_hint and "AZURE_OPENAI_API_KEY" not in values:
                values["AZURE_OPENAI_API_KEY"] = line
                continue

        section_hint = lower

    return values


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not key:
            continue
        values[key] = _strip_quotes(raw_value)
    return values


def _looks_like_bot_token(value: str) -> bool:
    return bool(re.fullmatch(r"\d{6,}:[A-Za-z0-9_-]{20,}", value))


def _looks_like_secret_token(value: str) -> bool:
    if " " in value:
        return False
    if value.startswith("http"):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_\-]{24,}", value))
