FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY bot/ bot/
COPY content/ content/
COPY prompts/ prompts/

CMD ["python", "-m", "bot.main"]
