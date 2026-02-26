FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY bot/ bot/
COPY content/ content/
COPY prompts/ prompts/

RUN pip install --no-cache-dir .

CMD ["python", "-m", "bot.main"]
