# Multi-stage build for frontend
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files from src/frontend when building from repo root context
COPY src/frontend/package*.json ./

# Install dependencies - fail if install fails
RUN npm install

# Copy source code
COPY src/frontend/ .

# Build the Vue application
RUN npm run build

# Production stage
FROM node:18-alpine

# Install serve to run the production build
RUN npm install -g serve

# Set working directory
WORKDIR /app

# Copy built application from builder
COPY --from=builder /app/dist .

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8080/ || exit 1

# Start the application
CMD ["serve", "-s", ".", "-l", "8080"]
