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

# Install Docker Buildx plugin (required by docker compose build)
BUILDX_URL=$(python3 - <<'PY'
import json
import urllib.request

with urllib.request.urlopen("https://api.github.com/repos/docker/buildx/releases/latest") as response:
    release = json.load(response)

for asset in release.get("assets", []):
    url = asset.get("browser_download_url", "")
    if url.endswith(".linux-amd64"):
        print(url)
        break
PY
)

if [[ -z "$BUILDX_URL" ]]; then
  BUILDX_URL="https://github.com/docker/buildx/releases/download/v0.17.1/buildx-v0.17.1.linux-amd64"
fi

for PLUGIN_DIR in /usr/local/lib/docker/cli-plugins /usr/libexec/docker/cli-plugins; do
  mkdir -p "$PLUGIN_DIR"
  curl -SL "$BUILDX_URL" -o "$PLUGIN_DIR/docker-buildx"
  chmod +x "$PLUGIN_DIR/docker-buildx"
done

docker buildx version

# Clone the repo and start services
cd /home/ec2-user
if [[ ! -d scorecheck/.git ]]; then
  git clone --branch "${repository_branch}" --single-branch "${repository_url}" scorecheck
fi

cd scorecheck
git fetch origin "${repository_branch}" || true
git checkout "${repository_branch}" || true
git pull --ff-only origin "${repository_branch}" || true

# Set domain for Caddy
export DOMAIN="${domain_name}"

# Start production stack
cd docker
cat > Caddyfile <<EOF
${domain_name} {
  reverse_proxy scorecheck-frontend:8080
}

www.${domain_name} {
  redir https://${domain_name}{uri}
}
EOF

DOMAIN="${domain_name}" docker compose -f docker-compose.prod.yml up -d --build

echo "Scorecheck deployment complete"
