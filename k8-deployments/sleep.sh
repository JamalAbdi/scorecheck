#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME=${CLUSTER_NAME:-scorecheck-eks}
NODEGROUP_NAME=${NODEGROUP_NAME:-${CLUSTER_NAME}-node-group}
AWS_REGION=${AWS_REGION:-us-east-1}
NAMESPACE=${NAMESPACE:-scorecheck}
INGRESS_NAME=${INGRESS_NAME:-scorecheck-frontend-ingress}
SLEEP_MESSAGE_HTML=${SLEEP_MESSAGE_HTML:-"<html><body><h3>This app is sleeping midnight to 8am EST.</h3></body></html>"}

echo "Updating kubeconfig for EKS cluster: ${CLUSTER_NAME} (region: ${AWS_REGION})"
aws eks update-kubeconfig --name "${CLUSTER_NAME}" --region "${AWS_REGION}" >/dev/null

echo "Configuring ALB sleep message..."
ALB_DNS=$(kubectl -n "${NAMESPACE}" get ingress "${INGRESS_NAME}" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
if [[ -n "${ALB_DNS}" ]]; then
  ALB_ARN=$(aws elbv2 describe-load-balancers --region "${AWS_REGION}" --query "LoadBalancers[?DNSName=='${ALB_DNS}'].LoadBalancerArn | [0]" --output text)
  HTTPS_LISTENER_ARN=$(aws elbv2 describe-listeners --region "${AWS_REGION}" --load-balancer-arn "${ALB_ARN}" --query 'Listeners[?Port==`443`].ListenerArn | [0]' --output text)
  if [[ "${HTTPS_LISTENER_ARN}" != "None" && -n "${HTTPS_LISTENER_ARN}" ]]; then
    FORWARD_RULES=$(aws elbv2 describe-rules --region "${AWS_REGION}" --listener-arn "${HTTPS_LISTENER_ARN}" --query "Rules[?Priority!='default' && Actions[0].Type=='forward'].RuleArn" --output text)
    for RULE_ARN in ${FORWARD_RULES}; do
      aws elbv2 modify-rule \
        --region "${AWS_REGION}" \
        --rule-arn "${RULE_ARN}" \
        --actions "Type=fixed-response,FixedResponseConfig={StatusCode=503,ContentType=text/html,MessageBody=\"${SLEEP_MESSAGE_HTML}\"}" >/dev/null
      echo "Sleep message enabled on ${RULE_ARN}."
    done
  else
    echo "No HTTPS listener found; skipping sleep message rule."
  fi
else
  echo "Could not find ALB DNS from ingress; skipping sleep message rule."
fi

echo "Scaling node group '${NODEGROUP_NAME}' down to 0 (sleep mode)..."
aws eks update-nodegroup-config \
  --region "${AWS_REGION}" \
  --cluster-name "${CLUSTER_NAME}" \
  --nodegroup-name "${NODEGROUP_NAME}" \
  --scaling-config minSize=0,maxSize=1,desiredSize=0 >/dev/null

echo "Waiting for node group update to complete..."
aws eks wait nodegroup-active \
  --region "${AWS_REGION}" \
  --cluster-name "${CLUSTER_NAME}" \
  --nodegroup-name "${NODEGROUP_NAME}"

echo "Sleep mode applied. Cluster workloads will be unschedulable until wake."
