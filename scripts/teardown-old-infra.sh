#!/bin/bash
# =============================================================================
# Teardown script for the old EKS/RDS/ECR infrastructure
# Run this AFTER migrating to the new EC2-based architecture
#
# This script tears down resources in the correct order:
#   1. Kubernetes deployments (Helm releases)
#   2. EKS cluster and node groups
#   3. RDS database
#   4. ECR repositories
#   5. Associated networking (VPC, subnets, etc.)
#
# Usage: ./scripts/teardown-old-infra.sh [--dry-run]
# =============================================================================
set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
  echo "=== DRY RUN MODE - No changes will be made ==="
fi

REGION="us-east-1"
CLUSTER_NAME="scorecheck-eks"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run_cmd() {
  echo "  -> $*"
  if [[ "$DRY_RUN" == false ]]; then
    eval "$@"
  fi
}

echo ""
echo "============================================"
echo "  Scorecheck Old Infrastructure Teardown"
echo "============================================"
echo ""
echo "This will destroy the following AWS resources:"
echo "  - EKS cluster: ${CLUSTER_NAME}"
echo "  - RDS PostgreSQL instance"
echo "  - ECR repositories (scorecheck-backend, scorecheck-frontend)"
echo "  - Associated VPC, subnets, security groups, IAM roles"
echo ""

if [[ "$DRY_RUN" == false ]]; then
  read -p "Are you sure you want to proceed? (type 'yes' to confirm): " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

# -------------------------------------------------------
# Step 1: Delete Kubernetes resources
# -------------------------------------------------------
echo ""
echo "=== Step 1: Removing Kubernetes deployments ==="

if aws eks describe-cluster --name "$CLUSTER_NAME" --region "$REGION" &>/dev/null; then
  echo "Updating kubeconfig..."
  run_cmd "aws eks update-kubeconfig --name $CLUSTER_NAME --region $REGION 2>/dev/null || true"

  echo "Deleting Helm releases..."
  run_cmd "helm uninstall scorecheck-backend -n scorecheck-prod 2>/dev/null || true"
  run_cmd "helm uninstall scorecheck-frontend -n scorecheck-prod 2>/dev/null || true"
  run_cmd "helm uninstall scorecheck-backend -n scorecheck-staging 2>/dev/null || true"
  run_cmd "helm uninstall scorecheck-frontend -n scorecheck-staging 2>/dev/null || true"

  echo "Deleting ingress (to release ALB)..."
  run_cmd "kubectl delete ingress --all -n scorecheck-prod 2>/dev/null || true"
  run_cmd "kubectl delete ingress --all -n scorecheck-staging 2>/dev/null || true"

  echo "Waiting 60s for ALB to be released..."
  if [[ "$DRY_RUN" == false ]]; then
    sleep 60
  fi
else
  echo "EKS cluster not found, skipping Kubernetes cleanup."
fi

# -------------------------------------------------------
# Step 2: Destroy RDS via Terraform
# -------------------------------------------------------
echo ""
echo "=== Step 2: Destroying RDS database ==="

INFRA_DIR="$PROJECT_DIR/_archived/old-k8s-eks-infra/infra"
if [[ -d "$INFRA_DIR/db" ]]; then
  echo "Disabling deletion protection first..."
  DB_ID=$(aws rds describe-db-instances --region "$REGION" \
    --query "DBInstances[?starts_with(DBInstanceIdentifier, 'scorecheck')].DBInstanceIdentifier" \
    --output text 2>/dev/null || true)

  if [[ -n "$DB_ID" ]]; then
    run_cmd "aws rds modify-db-instance --db-instance-identifier $DB_ID --no-deletion-protection --apply-immediately --region $REGION 2>/dev/null || true"
    echo "Waiting 30s for modification to apply..."
    if [[ "$DRY_RUN" == false ]]; then
      sleep 30
    fi
  fi

  echo "Running terraform destroy for RDS..."
  run_cmd "cd $INFRA_DIR/db && terraform destroy -auto-approve 2>/dev/null || true"
else
  echo "infra/db directory not found, skipping."
fi

# -------------------------------------------------------
# Step 3: Destroy EKS via Terraform
# -------------------------------------------------------
echo ""
echo "=== Step 3: Destroying EKS cluster ==="

if [[ -d "$INFRA_DIR/eks" ]]; then
  echo "Running terraform destroy for EKS..."
  run_cmd "cd $INFRA_DIR/eks && terraform destroy -auto-approve 2>/dev/null || true"
else
  echo "infra/eks directory not found, skipping."
fi

# -------------------------------------------------------
# Step 4: Destroy ECR repositories
# -------------------------------------------------------
echo ""
echo "=== Step 4: Destroying ECR repositories ==="

if [[ -d "$INFRA_DIR/ecr" ]]; then
  echo "Deleting all images first (required before repo deletion)..."
  for REPO in scorecheck-backend scorecheck-frontend; do
    run_cmd "aws ecr batch-delete-image --repository-name $REPO --region $REGION \
      --image-ids \"\$(aws ecr list-images --repository-name $REPO --region $REGION --query 'imageIds[*]' --output json 2>/dev/null)\" 2>/dev/null || true"
  done

  echo "Running terraform destroy for ECR..."
  run_cmd "cd $INFRA_DIR/ecr && terraform destroy -auto-approve 2>/dev/null || true"
else
  echo "infra/ecr directory not found, skipping."
fi

# -------------------------------------------------------
# Step 5: Clean up any remaining resources
# -------------------------------------------------------
echo ""
echo "=== Step 5: Cleaning up remaining resources ==="

echo "Checking for orphaned load balancers..."
ALBS=$(aws elbv2 describe-load-balancers --region "$REGION" \
  --query "LoadBalancers[?contains(LoadBalancerName, 'scorecheck') || contains(LoadBalancerName, 'k8s-')].LoadBalancerArn" \
  --output text 2>/dev/null || true)

if [[ -n "$ALBS" ]]; then
  for ALB_ARN in $ALBS; do
    echo "Deleting load balancer: $ALB_ARN"
    run_cmd "aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN --region $REGION 2>/dev/null || true"
  done
fi

echo "Removing sleep/wake cron jobs..."
run_cmd "crontab -l 2>/dev/null | grep -v 'scorecheck' | crontab - 2>/dev/null || true"

# -------------------------------------------------------
# Done
# -------------------------------------------------------
echo ""
echo "============================================"
echo "  Teardown complete!"
echo "============================================"
echo ""
echo "Verify in AWS Console that all resources are gone:"
echo "  - EKS:    https://console.aws.amazon.com/eks"
echo "  - RDS:    https://console.aws.amazon.com/rds"
echo "  - ECR:    https://console.aws.amazon.com/ecr"
echo "  - EC2:    https://console.aws.amazon.com/ec2 (check for orphaned ALBs, security groups)"
echo "  - VPC:    https://console.aws.amazon.com/vpc"
echo ""
if [[ "$DRY_RUN" == true ]]; then
  echo "This was a DRY RUN. Re-run without --dry-run to actually destroy resources."
fi
