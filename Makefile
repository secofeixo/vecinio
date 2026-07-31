.PHONY: build up up-fg down logs migrate destroy-database

build:
	docker compose build

up:
	docker compose up -d

up-fg:
	docker compose up

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose run --rm backend alembic upgrade head

destroy-database:
	docker compose stop db
	docker volume rm vecinio_postgres_data
