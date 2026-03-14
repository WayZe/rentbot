build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose down
	docker compose up -d

logs:
	docker compose logs -f

rebuild:
	docker compose down
	docker compose build --no-cache
	docker compose up -d

clean:
	docker compose down -v

install:
	uv pip install -r requirements.txt

run:
	uv run python bot.py

lock:
	uv lock

sync:
	uv sync