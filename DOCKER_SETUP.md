# Docker Deployment Guide

## What Was Created

A complete Docker containerization setup for Scorecheck:

```
docker/
├── backend/
│   ├── Dockerfile           # Multi-stage FastAPI container
│   └── .dockerignore        # Excludes unnecessary files from build
├── frontend/
│   ├── Dockerfile           # Multi-stage Vue.js build
│   └── .dockerignore        # Excludes unnecessary files from build
├── docker-compose.yml       # Orchestration with health checks
├── .env.example             # Example environment variables
└── README.md                # Detailed documentation
```

Plus at project root:
- `requirements.txt`         # Python dependencies
- `.dockerignore`            # Project-level exclusions
- `Makefile`                 # Convenient Docker commands

## Key Features

### Backend Dockerfile
- Based on `python:3.11-slim` (lightweight)
- Installs dependencies from `requirements.txt`
- Includes health checks
- Runs uvicorn on port 8000

### Frontend Dockerfile
- Multi-stage build for optimized image size
- Based on `node:18-alpine`
- Builds Vue.js production bundle
- Serves with `serve` on port 8080

### Docker Compose
- Orchestrates both services
- Service-to-service networking via `scorecheck-network`
- Health checks for both services
- Frontend depends on backend health
- Environment variable configuration
- Auto-restart policies

## Quick Start

### Option 1: Using docker-compose (Recommended)

```bash
cd docker
docker-compose up --build
```

Then access:
- Frontend: http://localhost:8080
- Backend: http://localhost:8000

### Option 2: Using Make commands

```bash
make build                   # Build both images
make up                      # Start services
make logs                    # View all logs
make down                    # Stop services
make status                  # Check service status
```

### Option 3: Manual Docker commands

```bash
# Build backend
docker build -f docker/backend/Dockerfile -t scorecheck-backend .

# Build frontend
docker build -f docker/frontend/Dockerfile -t scorecheck-frontend .

# Run both
docker run -p 8000:8000 scorecheck-backend &
docker run -p 8080:8080 scorecheck-frontend &
```

## Configuration

Edit `docker/docker-compose.yml` to:
- Change exposed ports
- Add environment variables
- Adjust resource limits
- Modify restart policies

## Environment Variables

Key variables in docker-compose.yml:

```yaml
environment:
  - SPORTS_DATA_SOURCE=espn
```

## Common Commands

```bash
# View logs
docker-compose -f docker/docker-compose.yml logs -f

# Stop services
docker-compose -f docker/docker-compose.yml down

# Rebuild after code changes
docker-compose -f docker/docker-compose.yml up --build

# Access backend shell
docker exec -it scorecheck-backend /bin/sh

# Check service health
docker-compose -f docker/docker-compose.yml ps
```

## Production Considerations

1. **Image Optimization**: Multi-stage builds reduce image size
2. **Health Checks**: Both services have health checks configured
3. **Security**: Runs as non-root in Alpine/slim images
4. **Restart Policy**: `unless-stopped` for reliability
5. **Networking**: Private bridge network for inter-service communication
6. **Environment**: Use `.env` files or Docker secrets in production

For production:
- Set specific version tags (not `latest`)
- Configure resource limits
- Use a reverse proxy (nginx)
- Set up logging aggregation
- Configure persistent volumes if needed

## Troubleshooting

**Services won't start:**
- Check logs: `docker-compose logs`
- Ensure ports 8000, 8080 are available
- Verify requirements.txt and package.json

**Frontend can't connect to backend:**
- Check backend is running: `docker-compose ps`
- Verify API URL in frontend environment
- Check docker network: `docker network ls`

**Images too large:**
- Multi-stage builds already optimize size
- Consider using Alpine variants
- Remove unnecessary dependencies

## Next Steps

1. Configure environment variables in `docker/docker-compose.yml`
2. Run `docker-compose up --build`
3. Access http://localhost:8080
4. Deploy to your infrastructure (Docker Swarm, Kubernetes, etc.)
