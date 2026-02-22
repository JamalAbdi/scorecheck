#!/usr/bin/env bash
set -euo pipefail

NAMESPACE=${NAMESPACE:-scorecheck}
BACKEND_RELEASE=${BACKEND_RELEASE:-scorecheck-backend}
FRONTEND_RELEASE=${FRONTEND_RELEASE:-scorecheck-frontend}
CLUSTER_NAME=${CLUSTER_NAME:-scorecheck-eks}
AWS_REGION=${AWS_REGION:-us-east-1}
IMAGE_PULL_SECRET_NAME=${IMAGE_PULL_SECRET_NAME:-ecr-pull-secret}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure kubeconfig points to the target EKS cluster
echo "Updating kubeconfig for EKS cluster: ${CLUSTER_NAME} (region: ${AWS_REGION})"
aws eks update-kubeconfig --name "${CLUSTER_NAME}" --region "${AWS_REGION}"

# Ensure namespace exists
kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${NAMESPACE}"

# Ensure ECR image pull secret exists in the namespace
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if ! kubectl -n "${NAMESPACE}" get secret "${IMAGE_PULL_SECRET_NAME}" >/dev/null 2>&1; then
  echo "Creating image pull secret '${IMAGE_PULL_SECRET_NAME}' in namespace '${NAMESPACE}'"
  kubectl create secret docker-registry "${IMAGE_PULL_SECRET_NAME}" \
    --docker-server="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com" \
    --docker-username=AWS \
    --docker-password="$(aws ecr get-login-password --region "${AWS_REGION}")" \
    --docker-email="none" -n "${NAMESPACE}"
fi

# Check for Helm
if ! command -v helm >/dev/null 2>&1; then
  echo "helm not found. Please install helm (https://helm.sh) and re-run this script."
  exit 1
fi

helm upgrade --install "${BACKEND_RELEASE}" "${SCRIPT_DIR}/backend-chart" \
  --namespace "${NAMESPACE}" \
  --wait \
  --set image.pullSecrets[0].name="${IMAGE_PULL_SECRET_NAME}"

helm upgrade --install "${FRONTEND_RELEASE}" "${SCRIPT_DIR}/frontend-chart" \
  --namespace "${NAMESPACE}" \
  --wait \
  --set image.pullSecrets[0].name="${IMAGE_PULL_SECRET_NAME}"

echo "Deployed to namespace: ${NAMESPACE}"
