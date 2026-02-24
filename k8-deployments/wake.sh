#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME=${CLUSTER_NAME:-scorecheck-eks}
NODEGROUP_NAME=${NODEGROUP_NAME:-${CLUSTER_NAME}-node-group}
AWS_REGION=${AWS_REGION:-us-east-1}
NAMESPACE=${NAMESPACE:-scorecheck}
HEALTHCHECK_URL=${HEALTHCHECK_URL:-https://scorecheck.ca/api/health}

echo "Updating kubeconfig for EKS cluster: ${CLUSTER_NAME} (region: ${AWS_REGION})"
aws eks update-kubeconfig --name "${CLUSTER_NAME}" --region "${AWS_REGION}" >/dev/null

echo "Scaling node group '${NODEGROUP_NAME}' up to 1 (wake mode)..."
aws eks update-nodegroup-config \
  --region "${AWS_REGION}" \
  --cluster-name "${CLUSTER_NAME}" \
  --nodegroup-name "${NODEGROUP_NAME}" \
  --scaling-config minSize=1,maxSize=1,desiredSize=1 >/dev/null

echo "Waiting for node group to become active..."
aws eks wait nodegroup-active \
  --region "${AWS_REGION}" \
  --cluster-name "${CLUSTER_NAME}" \
  --nodegroup-name "${NODEGROUP_NAME}"

echo "Waiting for a Kubernetes node to become Ready..."
for _ in {1..30}; do
  if kubectl get nodes --no-headers 2>/dev/null | grep -q ' Ready '; then
    break
  fi
  sleep 10
done

echo "Current pod status in namespace '${NAMESPACE}':"
kubectl -n "${NAMESPACE}" get pods || true

echo "Running post-wake health check: ${HEALTHCHECK_URL}"
healthy=false
for _ in {1..12}; do
  if curl -fsS --max-time 10 "${HEALTHCHECK_URL}" >/dev/null 2>&1; then
    healthy=true
    break
  fi
  sleep 10
done

if [[ "${healthy}" == "true" ]]; then
  echo "Health check passed."
else
  echo "Health check did not pass in time. Service may still be starting or DNS may be stale."
fi

echo "Wake mode applied."
