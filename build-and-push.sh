#!/bin/bash

# Script to build and push Docker images to ECR
# Usage: ./build-and-push.sh

set -e

# Configuration
AWS_REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
FRONTEND_REPO="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/scorecheck-frontend"
BACKEND_REPO="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/scorecheck-backend"

echo "Building and pushing images to ECR..."
echo "Frontend repo: $FRONTEND_REPO"
echo "Backend repo: $BACKEND_REPO"

# Authenticate Docker with ECR
echo "Authenticating with ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build and push frontend (use repo root as build context and Dockerfile in docker/frontend)
echo "Building frontend image..."
docker build -f docker/frontend/Dockerfile -t scorecheck-frontend:latest .
docker tag scorecheck-frontend:latest $FRONTEND_REPO:latest
echo "Pushing frontend image..."
docker push $FRONTEND_REPO:latest

# Build and push backend (use repo root as build context and Dockerfile in docker/backend)
echo "Building backend image..."
docker build -f docker/backend/Dockerfile -t scorecheck-backend:latest .
docker tag scorecheck-backend:latest $BACKEND_REPO:latest
echo "Pushing backend image..."
docker push $BACKEND_REPO:latest

echo "✅ All images built and pushed successfully!"
echo "Frontend: $FRONTEND_REPO:latest"
echo "Backend: $BACKEND_REPO:latest"