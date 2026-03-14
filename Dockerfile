FROM python:3.14-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv pip install --system \
    aiogram \
    apscheduler \
    asyncpg \
    python-dotenv

COPY . .

CMD ["python", "bot.py"]
