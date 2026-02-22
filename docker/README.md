# Scorecheck Docker Setup

Complete Docker containerization for the Scorecheck application with both frontend and backend services.

## Directory Structure

```
docker/
├── backend/
│   ├── Dockerfile          # Backend FastAPI container
│   └── .dockerignore
├── frontend/
│   ├── Dockerfile          # Frontend Vue.js container  
│   └── .dockerignore
├── docker-compose.yml      # Orchestration file
└── README.md              # This file
```

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+

## Quick Start

### Build and Run with Docker Compose

```bash
cd docker
docker-compose up --build
```

The services will be available at:
- Frontend: http://localhost:8080
- Backend API: http://localhost:8000
- API Health: http://localhost:8000/api/health

### Stop Services

```bash
docker-compose down
```

## Building Individual Images

### Backend Image

```bash
# From project root
docker build -f docker/backend/Dockerfile -t scorecheck-backend:latest .

# Run backend only
docker run -p 8000:8000 scorecheck-backend:latest
```

### Frontend Image

```bash
# From project root
docker build -f docker/frontend/Dockerfile -t scorecheck-frontend:latest .

# Run frontend only
docker run -p 8080:8080 scorecheck-frontend:latest
```

## Configuration

### Environment Variables

The backend service supports the following environment variables in `docker-compose.yml`:

- `SPORTS_DATA_SOURCE`: Data source connector (default: `thesportsdb`)
- `APISPORTS_KEY`: API-Sports API key (optional, for full data support)
- `APISPORTS_SEASON`: Sports season for API-Sports (default: `2024`)
- `APISPORTS_NBA_SEASON`: NBA season override (optional)
- `APISPORTS_NHL_SEASON`: NHL season override (optional)
- `APISPORTS_MLB_SEASON`: MLB season override (optional)

Edit `docker/docker-compose.yml` to configure these as needed.

## Network Communication

- Services communicate via the `scorecheck-network` bridge network
- Frontend API URL is automatically set to `http://backend:8000/api`
- Frontend depends on backend health check before starting

## Health Checks

Both services include health checks:
- **Backend**: Checks `/api/health` endpoint
- **Frontend**: Checks if port 8080 is accessible

## Logs

View logs for all services:

```bash
docker-compose logs -f
```

View logs for specific service:

```bash
docker-compose logs -f backend
docker-compose logs -f frontend
```

## Troubleshooting

### Backend fails to start

Check logs: `docker-compose logs backend`

Common issues:
- Missing environment variables
- Port 8000 already in use

### Frontend cannot connect to backend

Ensure `docker-compose.yml` has `depends_on` configured correctly and backend is healthy.

### Port conflicts

Change exposed ports in `docker-compose.yml`:

```yaml
ports:
  - "9000:8000"  # Backend on 9000
  - "3000:8080"  # Frontend on 3000
```

## Development

For development with hot-reload, use the `.entrypoint.sh` script instead:

```bash
bash .entrypoint.sh
```

## Production Deployment

For production:

1. Use specific version tags instead of `latest`
2. Consider using a reverse proxy (nginx) for better performance
3. Set proper environment variables and secrets
4. Use persistent volumes for any data
5. Configure resource limits in docker-compose.yml

Example production configuration:

```yaml
backend:
  # ... other config ...
  deploy:
    resources:
      limits:
        cpus: '0.5'
        memory: 512M
```
