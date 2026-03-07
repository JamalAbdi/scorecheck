#!/bin/bash
set -euxo pipefail

# Install Docker
dnf update -y
dnf install -y docker git
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user

# Install Docker Compose plugin
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Clone the repo and start services
cd /home/ec2-user
git clone https://github.com/djclarke92/scorecheck.git || true
cd scorecheck

# Set domain for Caddy
export DOMAIN="${domain_name}"

# Start production stack
cd docker
DOMAIN="${domain_name}" docker compose -f docker-compose.prod.yml up -d --build

echo "Scorecheck deployment complete"
