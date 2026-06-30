.PHONY: install-backend install-frontend run-backend run-frontend test lint format docker-up

install-backend:
	pip install -r requirements-dev.txt

install-frontend:
	cd frontend && npm install

run-backend:
	uvicorn main:app --reload

run-frontend:
	cd frontend && npm run dev

test:
	pytest

lint:
	ruff check src tests main.py cli.py
	black --check src tests main.py cli.py

format:
	ruff check --fix src tests main.py cli.py
	black src tests main.py cli.py

docker-up:
	docker-compose up --build
