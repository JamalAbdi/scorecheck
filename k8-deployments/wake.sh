#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME=${CLUSTER_NAME:-scorecheck-eks}
NODEGROUP_NAME=${NODEGROUP_NAME:-${CLUSTER_NAME}-node-group}
AWS_REGION=${AWS_REGION:-us-east-1}
NAMESPACE=${NAMESPACE:-scorecheck}
HEALTHCHECK_URL=${HEALTHCHECK_URL:-https://scorecheck.ca/api/health}
INGRESS_NAME=${INGRESS_NAME:-scorecheck-frontend-ingress}
SLEEP_RULE_PRIORITY=${SLEEP_RULE_PRIORITY:-49999}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INGRESS_MANIFEST=${INGRESS_MANIFEST:-"${SCRIPT_DIR}/../infra/eks/frontend-ingress.yaml"}

echo "Updating kubeconfig for EKS cluster: ${CLUSTER_NAME} (region: ${AWS_REGION})"
aws eks update-kubeconfig --name "${CLUSTER_NAME}" --region "${AWS_REGION}" >/dev/null

echo "Restoring ALB routing from ingress manifest..."
kubectl apply -f "${INGRESS_MANIFEST}" >/dev/null

echo "Removing legacy ALB sleep rule (if present)..."
ALB_DNS=$(kubectl -n "${NAMESPACE}" get ingress "${INGRESS_NAME}" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
if [[ -n "${ALB_DNS}" ]]; then
  ALB_ARN=$(aws elbv2 describe-load-balancers --region "${AWS_REGION}" --query "LoadBalancers[?DNSName=='${ALB_DNS}'].LoadBalancerArn | [0]" --output text)
  HTTPS_LISTENER_ARN=$(aws elbv2 describe-listeners --region "${AWS_REGION}" --load-balancer-arn "${ALB_ARN}" --query 'Listeners[?Port==`443`].ListenerArn | [0]' --output text)
  if [[ "${HTTPS_LISTENER_ARN}" != "None" && -n "${HTTPS_LISTENER_ARN}" ]]; then
    SLEEP_RULE_ARN=$(aws elbv2 describe-rules --region "${AWS_REGION}" --listener-arn "${HTTPS_LISTENER_ARN}" --query "Rules[?Priority=='${SLEEP_RULE_PRIORITY}' && Actions[0].Type=='fixed-response'].RuleArn | [0]" --output text)
    if [[ "${SLEEP_RULE_ARN}" != "None" && -n "${SLEEP_RULE_ARN}" ]]; then
      aws elbv2 delete-rule --region "${AWS_REGION}" --rule-arn "${SLEEP_RULE_ARN}" >/dev/null
      echo "Sleep message rule removed."
    else
      echo "No sleep message rule found."
    fi
  fi
fi

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
