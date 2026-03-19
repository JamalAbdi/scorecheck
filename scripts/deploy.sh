#!/bin/bash
# =============================================================================
# Deploy scorecheck to EC2 instance
#
# Prerequisites:
#   - Terraform has been applied (terraform/ directory)
#   - SSH key pair exists locally
#
# Usage: ./scripts/deploy.sh [--key ~/.ssh/mykey.pem]
# =============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY_PATH=""

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --key) KEY_PATH="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# Get outputs from Terraform
cd "$PROJECT_DIR/terraform"
PUBLIC_IP=$(terraform output -raw public_ip 2>/dev/null)
if [[ -z "$PUBLIC_IP" ]]; then
  echo "Error: Could not get public_ip from Terraform. Run 'terraform apply' first."
  exit 1
fi

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10"
if [[ -n "$KEY_PATH" ]]; then
  SSH_OPTS="$SSH_OPTS -i $KEY_PATH"
fi

echo "Deploying scorecheck to $PUBLIC_IP..."

# Sync project files to EC2
echo "Syncing project files..."
rsync -avz --exclude='.git' --exclude='node_modules' --exclude='.venv' --exclude='__pycache__' \
  -e "ssh $SSH_OPTS" \
  "$PROJECT_DIR/" "ec2-user@${PUBLIC_IP}:~/scorecheck/"

# Build and start on remote
echo "Building and starting services on remote..."
ssh $SSH_OPTS "ec2-user@${PUBLIC_IP}" << 'REMOTE_SCRIPT'
cd ~/scorecheck/docker

# Get domain from Caddyfile or use default
DOMAIN="${DOMAIN:-}"
if [[ -z "$DOMAIN" ]]; then
  echo "Note: DOMAIN not set. Caddy will use localhost (HTTP only)."
  echo "Set DOMAIN env var for HTTPS: DOMAIN=scorecheck.ca ./scripts/deploy.sh"
fi

# Pull latest images and rebuild
docker compose -f docker-compose.prod.yml down 2>/dev/null || true
DOMAIN="$DOMAIN" docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo "Services started. Checking health..."
sleep 10
docker compose -f docker-compose.prod.yml ps
REMOTE_SCRIPT

echo ""
echo "Deployment complete!"
echo "  SSH:  ssh $SSH_OPTS ec2-user@${PUBLIC_IP}"
echo "  App:  https://${PUBLIC_IP} (or your domain once DNS propagates)"
