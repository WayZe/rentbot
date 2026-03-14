FROM python:3.14-slim

# Install postgresql-client for pg_dump and psql commands
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv pip install --system \
    aiogram \
    apscheduler \
    asyncpg \
    python-dotenv \
    aiohttp

COPY . .

CMD ["python", "-m", "rentbot"]
