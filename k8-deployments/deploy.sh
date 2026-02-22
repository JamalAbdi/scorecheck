#!/usr/bin/env bash
set -euo pipefail

NAMESPACE=${NAMESPACE:-scorecheck}
BACKEND_RELEASE=${BACKEND_RELEASE:-scorecheck-backend}
FRONTEND_RELEASE=${FRONTEND_RELEASE:-scorecheck-frontend}
CLUSTER_NAME=${CLUSTER_NAME:-scorecheck-eks}
AWS_REGION=${AWS_REGION:-us-east-1}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure kubeconfig points to the target EKS cluster
echo "Updating kubeconfig for EKS cluster: ${CLUSTER_NAME} (region: ${AWS_REGION})"
aws eks update-kubeconfig --name "${CLUSTER_NAME}" --region "${AWS_REGION}"

kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${NAMESPACE}"

helm upgrade --install "${BACKEND_RELEASE}" "${SCRIPT_DIR}/backend-chart" \
  --namespace "${NAMESPACE}" \
  --wait

helm upgrade --install "${FRONTEND_RELEASE}" "${SCRIPT_DIR}/frontend-chart" \
  --namespace "${NAMESPACE}" \
  --wait

echo "Deployed to namespace: ${NAMESPACE}"
