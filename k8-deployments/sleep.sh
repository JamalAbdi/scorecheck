#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME=${CLUSTER_NAME:-scorecheck-eks}
NODEGROUP_NAME=${NODEGROUP_NAME:-${CLUSTER_NAME}-node-group}
AWS_REGION=${AWS_REGION:-us-east-1}

echo "Updating kubeconfig for EKS cluster: ${CLUSTER_NAME} (region: ${AWS_REGION})"
aws eks update-kubeconfig --name "${CLUSTER_NAME}" --region "${AWS_REGION}" >/dev/null

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
