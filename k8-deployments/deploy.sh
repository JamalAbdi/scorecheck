#!/usr/bin/env bash
set -euo pipefail

NAMESPACE=${NAMESPACE:-scorecheck}
BACKEND_RELEASE=${BACKEND_RELEASE:-scorecheck-backend}
FRONTEND_RELEASE=${FRONTEND_RELEASE:-scorecheck-frontend}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${NAMESPACE}"

helm upgrade --install "${BACKEND_RELEASE}" "${SCRIPT_DIR}/backend-chart" \
  --namespace "${NAMESPACE}" \
  --wait

helm upgrade --install "${FRONTEND_RELEASE}" "${SCRIPT_DIR}/frontend-chart" \
  --namespace "${NAMESPACE}" \
  --wait

echo "Deployed to namespace: ${NAMESPACE}"
