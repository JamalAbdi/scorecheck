#!/usr/bin/env bash
set -euo pipefail

DEPLOY_ENV=${ENV:-dev}
CLUSTER_NAME=${CLUSTER_NAME:-scorecheck-eks}
AWS_REGION=${AWS_REGION:-us-east-1}
IMAGE_PULL_SECRET_NAME=${IMAGE_PULL_SECRET_NAME:-ecr-pull-secret}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${DEPLOY_ENV}" in
  prod)
    DEFAULT_NAMESPACE="scorecheck-prod"
    DEFAULT_BACKEND_RELEASE="scorecheck-backend-prod"
    DEFAULT_FRONTEND_RELEASE="scorecheck-frontend-prod"
    BACKEND_VALUES_FILE="${SCRIPT_DIR}/backend-chart/values-prod.yaml"
    FRONTEND_VALUES_FILE="${SCRIPT_DIR}/frontend-chart/values-prod.yaml"
    ;;
  staging)
    DEFAULT_NAMESPACE="scorecheck-staging"
    DEFAULT_BACKEND_RELEASE="scorecheck-backend-staging"
    DEFAULT_FRONTEND_RELEASE="scorecheck-frontend-staging"
    BACKEND_VALUES_FILE="${SCRIPT_DIR}/backend-chart/values-staging.yaml"
    FRONTEND_VALUES_FILE="${SCRIPT_DIR}/frontend-chart/values-staging.yaml"
    ;;
  *)
    DEFAULT_NAMESPACE="scorecheck"
    DEFAULT_BACKEND_RELEASE="scorecheck-backend"
    DEFAULT_FRONTEND_RELEASE="scorecheck-frontend"
    BACKEND_VALUES_FILE="${SCRIPT_DIR}/backend-chart/values.yaml"
    FRONTEND_VALUES_FILE="${SCRIPT_DIR}/frontend-chart/values.yaml"
    ;;
esac

NAMESPACE=${NAMESPACE:-$DEFAULT_NAMESPACE}
BACKEND_RELEASE=${BACKEND_RELEASE:-$DEFAULT_BACKEND_RELEASE}
FRONTEND_RELEASE=${FRONTEND_RELEASE:-$DEFAULT_FRONTEND_RELEASE}

if [[ ! -f "${BACKEND_VALUES_FILE}" ]]; then
  echo "Missing backend values file: ${BACKEND_VALUES_FILE}"
  exit 1
fi

if [[ ! -f "${FRONTEND_VALUES_FILE}" ]]; then
  echo "Missing frontend values file: ${FRONTEND_VALUES_FILE}"
  exit 1
fi

echo "Deploy environment: ${DEPLOY_ENV}"
echo "Namespace: ${NAMESPACE}"
echo "Backend release: ${BACKEND_RELEASE} (values: ${BACKEND_VALUES_FILE})"
echo "Frontend release: ${FRONTEND_RELEASE} (values: ${FRONTEND_VALUES_FILE})"

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
  -f "${BACKEND_VALUES_FILE}" \
  --wait \
  --set image.pullSecrets[0].name="${IMAGE_PULL_SECRET_NAME}"

helm upgrade --install "${FRONTEND_RELEASE}" "${SCRIPT_DIR}/frontend-chart" \
  --namespace "${NAMESPACE}" \
  -f "${FRONTEND_VALUES_FILE}" \
  --wait \
  --set image.pullSecrets[0].name="${IMAGE_PULL_SECRET_NAME}"

kubectl -n "${NAMESPACE}" rollout restart deployment "${BACKEND_RELEASE}"
kubectl -n "${NAMESPACE}" rollout restart deployment "${FRONTEND_RELEASE}"

kubectl -n "${NAMESPACE}" rollout status deployment "${BACKEND_RELEASE}" --timeout=300s
kubectl -n "${NAMESPACE}" rollout status deployment "${FRONTEND_RELEASE}" --timeout=300s

echo "Deployed to namespace: ${NAMESPACE}"
