.PHONY: help build up down logs clean restart backend-build frontend-build

help:
	@echo "Scorecheck Docker Commands"
	@echo ""
	@echo "Available targets:"
	@echo "  make build              - Build both images"
	@echo "  make up                 - Start all services"
	@echo "  make down               - Stop all services"
	@echo "  make restart            - Restart all services"
	@echo "  make logs               - View logs (all services)"
	@echo "  make logs-backend       - View backend logs"
	@echo "  make logs-frontend      - View frontend logs"
	@echo "  make clean              - Remove containers and images"
	@echo "  make backend-build      - Build backend image only"
	@echo "  make frontend-build     - Build frontend image only"
	@echo "  make status             - Show service status"
	@echo "  make shell-backend      - Open shell in backend container"
	@echo "  make shell-frontend     - Open shell in frontend container"

build:
	cd docker && docker-compose build

up:
	cd docker && docker-compose up -d

down:
	cd docker && docker-compose down

restart:
	cd docker && docker-compose restart

logs:
	cd docker && docker-compose logs -f

logs-backend:
	cd docker && docker-compose logs -f backend

logs-frontend:
	cd docker && docker-compose logs -f frontend

clean:
	cd docker && docker-compose down -v
	docker rmi scorecheck-backend:latest scorecheck-frontend:latest 2>/dev/null || true

backend-build:
	docker build -f docker/backend/Dockerfile -t scorecheck-backend:latest .

frontend-build:
	docker build -f docker/frontend/Dockerfile -t scorecheck-frontend:latest .

status:
	cd docker && docker-compose ps

shell-backend:
	docker exec -it scorecheck-backend /bin/sh

shell-frontend:
	docker exec -it scorecheck-frontend /bin/sh
