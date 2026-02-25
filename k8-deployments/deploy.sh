#!/usr/bin/env bash
set -euo pipefail

NAMESPACE=${NAMESPACE:-scorecheck}
BACKEND_RELEASE=${BACKEND_RELEASE:-scorecheck-backend}
FRONTEND_RELEASE=${FRONTEND_RELEASE:-scorecheck-frontend}
CLUSTER_NAME=${CLUSTER_NAME:-scorecheck-eks}
AWS_REGION=${AWS_REGION:-us-east-1}
IMAGE_PULL_SECRET_NAME=${IMAGE_PULL_SECRET_NAME:-ecr-pull-secret}
APISPORTS_SECRET_NAME=${APISPORTS_SECRET_NAME:-apisports-secret}

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

# Optionally create/update API-Sports key secret when APISPORTS_KEY is provided
if [[ -n "${APISPORTS_KEY:-}" ]]; then
  echo "Applying API-Sports secret '${APISPORTS_SECRET_NAME}' in namespace '${NAMESPACE}'"
  kubectl -n "${NAMESPACE}" create secret generic "${APISPORTS_SECRET_NAME}" \
    --from-literal=APISPORTS_KEY="${APISPORTS_KEY}" \
    --dry-run=client -o yaml | kubectl apply -f -
else
  if ! kubectl -n "${NAMESPACE}" get secret "${APISPORTS_SECRET_NAME}" >/dev/null 2>&1; then
    echo "APISPORTS_KEY not provided and secret '${APISPORTS_SECRET_NAME}' not found. Backend will run without API-Sports key."
  fi
fi

# Check for Helm
if ! command -v helm >/dev/null 2>&1; then
  echo "helm not found. Please install helm (https://helm.sh) and re-run this script."
  exit 1
fi

helm upgrade --install "${BACKEND_RELEASE}" "${SCRIPT_DIR}/backend-chart" \
  --namespace "${NAMESPACE}" \
  --wait \
  --set image.pullSecrets[0].name="${IMAGE_PULL_SECRET_NAME}" \
  --set apiSportsSecretName="${APISPORTS_SECRET_NAME}"

helm upgrade --install "${FRONTEND_RELEASE}" "${SCRIPT_DIR}/frontend-chart" \
  --namespace "${NAMESPACE}" \
  --wait \
  --set image.pullSecrets[0].name="${IMAGE_PULL_SECRET_NAME}"

kubectl -n "${NAMESPACE}" rollout restart deployment "${BACKEND_RELEASE}"
kubectl -n "${NAMESPACE}" rollout restart deployment "${FRONTEND_RELEASE}"

kubectl -n "${NAMESPACE}" rollout status deployment "${BACKEND_RELEASE}" --timeout=300s
kubectl -n "${NAMESPACE}" rollout status deployment "${FRONTEND_RELEASE}" --timeout=300s

echo "Deployed to namespace: ${NAMESPACE}"
