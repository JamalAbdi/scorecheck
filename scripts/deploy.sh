#!/bin/bash
# =============================================================================
# Deploy scorecheck to EC2 instance via AWS SSM (no SSH required)
#
# Prerequisites:
#   - Terraform has been applied (terraform/ directory)
#   - AWS CLI installed and configured with sufficient permissions
#   - Session Manager plugin installed:
#     https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html
#
# Usage: ./scripts/deploy.sh [--branch <branch>]
# =============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRANCH_OVERRIDE=""

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --branch) BRANCH_OVERRIDE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# Get instance ID and branch from Terraform outputs
cd "$PROJECT_DIR/terraform"

INSTANCE_ID=$(terraform output -raw instance_id 2>/dev/null)
if [[ -z "$INSTANCE_ID" ]]; then
  echo "Error: Could not get instance_id from Terraform. Run 'terraform apply' first."
  exit 1
fi

# Determine branch: CLI arg > terraform variable > default
if [[ -n "$BRANCH_OVERRIDE" ]]; then
  DEPLOY_BRANCH="$BRANCH_OVERRIDE"
else
  DEPLOY_BRANCH="$(terraform output -raw repository_branch 2>/dev/null || true)"
  if [[ -z "$DEPLOY_BRANCH" ]]; then
    # Fall back to reading from variables
    DEPLOY_BRANCH="$(grep 'repository_branch' terraform.tfvars 2>/dev/null | awk -F'"' '{print $2}' || echo "main")"
  fi
fi

AWS_REGION="$(terraform output -raw region 2>/dev/null || aws configure get region || echo "us-east-1")"

echo "Deploying scorecheck..."
echo "  Instance : $INSTANCE_ID"
echo "  Branch   : $DEPLOY_BRANCH"
echo "  Region   : $AWS_REGION"
echo ""

# Wait until SSM agent is online (useful right after terraform apply)
echo "Checking SSM connectivity..."
aws ssm wait command-executed \
  --command-id "$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters '{"commands":["echo ok"]}' \
    --region "$AWS_REGION" \
    --query "Command.CommandId" \
    --output text)" \
  --instance-id "$INSTANCE_ID" \
  --region "$AWS_REGION" 2>/dev/null || true

echo "Sending deploy command via SSM..."
COMMAND_ID=$(aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --comment "scorecheck deploy" \
  --parameters "commands=[
    'set -euo pipefail',
    'cd /home/ec2-user/scorecheck',
    'git fetch origin ${DEPLOY_BRANCH}',
    'git checkout ${DEPLOY_BRANCH}',
    'git pull --ff-only origin ${DEPLOY_BRANCH}',
    'cd docker',
    'DOMAIN=\"\$(grep -oP \"(?<=^)[a-z0-9.-]+\\\\.[a-z]{2,}\" Caddyfile | head -1 || true)\"',
    'docker compose -f docker-compose.prod.yml down 2>/dev/null || true',
    'DOMAIN=\"\$DOMAIN\" docker compose -f docker-compose.prod.yml up -d --build',
    'sleep 10',
    'docker compose -f docker-compose.prod.yml ps'
  ]" \
  --region "$AWS_REGION" \
  --query "Command.CommandId" \
  --output text)

echo "Command ID: $COMMAND_ID"
echo "Waiting for deployment to finish..."

aws ssm wait command-executed \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --region "$AWS_REGION"

# Print output
STATUS=$(aws ssm get-command-invocation \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --region "$AWS_REGION" \
  --query "Status" \
  --output text)

echo ""
aws ssm get-command-invocation \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --region "$AWS_REGION" \
  --query "StandardOutputContent" \
  --output text

if [[ "$STATUS" != "Success" ]]; then
  echo "--- STDERR ---"
  aws ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --region "$AWS_REGION" \
    --query "StandardErrorContent" \
    --output text
  echo "Deployment failed with status: $STATUS"
  exit 1
fi

echo ""
echo "Deployment complete!"
echo "  Connect: aws ssm start-session --instance-id $INSTANCE_ID --region $AWS_REGION"
echo "  App:  https://${PUBLIC_IP} (or your domain once DNS propagates)"
