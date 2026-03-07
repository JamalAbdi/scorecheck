.PHONY: help build up down logs clean restart backend-build frontend-build prod-up prod-down prod-logs deploy teardown-old infra-plan infra-apply infra-destroy

help:
	@echo "Scorecheck Commands"
	@echo ""
	@echo "Local development:"
	@echo "  make build              - Build both images"
	@echo "  make up                 - Start all services (local dev)"
	@echo "  make down               - Stop all services"
	@echo "  make restart            - Restart all services"
	@echo "  make logs               - View logs (all services)"
	@echo "  make logs-backend       - View backend logs"
	@echo "  make logs-frontend      - View frontend logs"
	@echo "  make clean              - Remove containers and images"
	@echo "  make status             - Show service status"
	@echo "  make shell-backend      - Open shell in backend container"
	@echo "  make shell-frontend     - Open shell in frontend container"
	@echo ""
	@echo "Production (EC2 + Docker Compose + Caddy):"
	@echo "  make prod-up            - Start production stack locally (test)"
	@echo "  make prod-down          - Stop production stack"
	@echo "  make prod-logs          - View production logs"
	@echo "  make deploy             - Deploy to EC2 via SSH"
	@echo ""
	@echo "Infrastructure (Terraform):"
	@echo "  make infra-plan         - Plan Terraform changes"
	@echo "  make infra-apply        - Apply Terraform (create EC2 + Route 53)"
	@echo "  make infra-destroy      - Destroy new infrastructure"
	@echo "  make teardown-old       - Tear down old EKS/RDS/ECR infrastructure"

# --- Local development ---

build:
	cd docker && docker compose build

up:
	cd docker && docker compose up -d

down:
	cd docker && docker compose down

restart:
	cd docker && docker compose restart

logs:
	cd docker && docker compose logs -f

logs-backend:
	cd docker && docker compose logs -f backend

logs-frontend:
	cd docker && docker compose logs -f frontend

clean:
	cd docker && docker compose down -v
	docker rmi scorecheck-backend:latest scorecheck-frontend:latest 2>/dev/null || true

backend-build:
	docker build -f docker/backend/Dockerfile -t scorecheck-backend:latest .

frontend-build:
	docker build -f docker/frontend/Dockerfile -t scorecheck-frontend:latest .

status:
	cd docker && docker compose ps

shell-backend:
	docker exec -it scorecheck-backend /bin/sh

shell-frontend:
	docker exec -it scorecheck-frontend /bin/sh

# --- Production ---

prod-up:
	cd docker && DOMAIN=$${DOMAIN:-localhost} docker compose -f docker-compose.prod.yml up -d --build

prod-down:
	cd docker && docker compose -f docker-compose.prod.yml down

prod-logs:
	cd docker && docker compose -f docker-compose.prod.yml logs -f

deploy:
	./scripts/deploy.sh

# --- Infrastructure ---

infra-plan:
	cd terraform && terraform plan

infra-apply:
	cd terraform && terraform apply

infra-destroy:
	cd terraform && terraform destroy

teardown-old:
	./scripts/teardown-old-infra.sh
