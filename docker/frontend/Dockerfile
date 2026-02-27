# Multi-stage build for frontend
FROM node:14-alpine AS builder

# Set working directory
WORKDIR /app

# Build-time API base URL for Vue app (uses relative path through nginx proxy)
ARG VUE_APP_API_URL=/api
ENV VUE_APP_API_URL=$VUE_APP_API_URL

# Copy package files from src/frontend when building from repo root context
COPY src/frontend/package*.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Copy source code
COPY src/frontend/ .

# Build the Vue application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built application from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY src/frontend/nginx.conf /etc/nginx/nginx.conf

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8080/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
