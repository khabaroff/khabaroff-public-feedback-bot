import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bot.config import ConfigError, ContentError, load_content, load_settings


def _write_base_content(base: Path) -> None:
    """Write the minimum set of content files needed for load_content to succeed."""
    content_dir = base / "content"
    prompts_dir = base / "prompts"
    content_dir.mkdir(exist_ok=True)
    prompts_dir.mkdir(exist_ok=True)

    (content_dir / "texts.yaml").write_text(
        "greeting_intro: hello\ncta_start: go\n", encoding="utf-8"
    )
    (content_dir / "thinking.yaml").write_text(
        "phrases:\n  - one\n  - two\n", encoding="utf-8"
    )
    (content_dir / "clarify_questions.yaml").write_text(
        "moment:\n  - q1\nstyle:\n  - q2\ncontext:\n  - q3\n", encoding="utf-8"
    )
    (content_dir / "review_template.yaml").write_text(
        "fields:\n  - context\n", encoding="utf-8"
    )
    (prompts_dir / "generate_review.md").write_text("system generate", encoding="utf-8")
    (prompts_dir / "rephrase_review.md").write_text("system rephrase", encoding="utf-8")
    (prompts_dir / "analyze_answer.md").write_text("system analyze", encoding="utf-8")


class TestConfigContent(unittest.TestCase):
    def test_load_settings_success(self) -> None:
        env = {
            "TELEGRAM_BOT_TOKEN": "123:token",
            "OWNER_TELEGRAM_ID": "123456",
            "ASSEMBLYAI_API_KEY": "assembly-key",
            "AZURE_OPENAI_API_KEY": "azure-key",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            "AZURE_OPENAI_MODEL": "gpt-4o",
        }
        settings = load_settings(env)
        self.assertEqual(settings.owner_telegram_id, 123456)
        self.assertEqual(settings.azure_openai_model, "gpt-4o")

    def test_load_settings_missing_required(self) -> None:
        env = {
            "OWNER_TELEGRAM_ID": "123456",
            "ASSEMBLYAI_API_KEY": "assembly-key",
            "AZURE_OPENAI_API_KEY": "azure-key",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            "AZURE_OPENAI_MODEL": "gpt-4o",
        }
        with self.assertRaises(ConfigError):
            load_settings(env)

    def test_load_content_success(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_base_content(base)

            app_content = load_content(base)
            self.assertEqual(app_content.texts["greeting_intro"], "hello")
            self.assertEqual(len(app_content.thinking_phrases), 2)
            self.assertIn("generate", app_content.generate_prompt)
            self.assertIn("analyze", app_content.analyze_prompt)
            self.assertIn("moment", app_content.clarify_questions)
            self.assertIn("style", app_content.clarify_questions)
            self.assertIn("context", app_content.clarify_questions)
            self.assertIsInstance(app_content.review_template, dict)

    def test_load_content_missing_required_key(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_base_content(base)
            # Overwrite texts.yaml without greeting_intro
            (base / "content" / "texts.yaml").write_text(
                "cta_start: go\n", encoding="utf-8"
            )

            with self.assertRaises(ContentError):
                load_content(base)

    def test_load_content_empty_thinking_phrases(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_base_content(base)
            (base / "content" / "thinking.yaml").write_text(
                "phrases: []\n", encoding="utf-8"
            )

            with self.assertRaises(ContentError):
                load_content(base)

    def test_load_content_missing_analyze_prompt(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_base_content(base)
            (base / "prompts" / "analyze_answer.md").unlink()

            with self.assertRaises(ContentError):
                load_content(base)

    def test_load_content_missing_clarify_questions(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_base_content(base)
            (base / "content" / "clarify_questions.yaml").unlink()

            with self.assertRaises(ContentError):
                load_content(base)

    def test_load_content_clarify_questions_missing_key(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_base_content(base)
            # Write clarify_questions without "moment"
            (base / "content" / "clarify_questions.yaml").write_text(
                "style:\n  - q1\ncontext:\n  - q2\n", encoding="utf-8"
            )

            with self.assertRaises(ContentError):
                load_content(base)


if __name__ == "__main__":
    unittest.main()
