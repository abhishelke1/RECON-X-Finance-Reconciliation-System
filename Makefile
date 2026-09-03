.PHONY: up down logs test migrate generate-data clean lint shell

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose exec backend pytest -v

migrate:
	docker compose exec backend alembic upgrade head

generate-data:
	docker compose exec backend python -m data.generators.generate_dataset --rows 5000 --seed 42

clean:
	docker compose down -v --remove-orphans

lint:
	docker compose exec backend ruff check .

shell:
	docker compose exec backend bash
