#!/usr/bin/env bash
set -euo pipefail

# Automated CDK bootstrap + deploy using aws-vault (pass backend recommended)
# Usage: AWS_VAULT_BACKEND=pass AWS_REGION=ap-northeast-1 ./scripts/deploy-cdk-with-aws-vault.sh [PROFILE]
# Default PROFILE: chater-deploy

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Required for pinentry-curses to find the terminal
export GPG_TTY=$(tty)
# Prefer wrapper if present, otherwise system aws-vault
if [ -x "$ROOT_DIR/scripts/aws-vault.sh" ]; then
  AWS_VAULT_CMD="$ROOT_DIR/scripts/aws-vault.sh"
elif command -v aws-vault >/dev/null 2>&1; then
  AWS_VAULT_CMD="aws-vault"
else
  echo "ERROR: aws-vault not found. Install aws-vault or add scripts/aws-vault.sh wrapper." >&2
  exit 1
fi

PROFILE="${1:-chater-deploy}"
STAGE="${2:-${DEPLOY_STAGE:-prod}}"
export AWS_VAULT_BACKEND="${AWS_VAULT_BACKEND:-pass}"
AWS_REGION="${AWS_REGION:-ap-northeast-1}"
CDK_DIR="$ROOT_DIR/infra/cdk"

echo "Using aws-vault command: $AWS_VAULT_CMD"
echo "Profile: $PROFILE, Stage: $STAGE, Backend: $AWS_VAULT_BACKEND, Region: $AWS_REGION"

# Ensure dependencies are installed in infra/cdk
cd "$CDK_DIR"
if [ -f package-lock.json ] || [ -f yarn.lock ]; then
  echo "Installing Node dependencies (npm ci)"
  npm ci --no-audit --no-fund
else
  echo "Installing Node dependencies (npm install)"
  npm install --no-audit --no-fund
fi

# Validate aws-vault can run a simple aws command
echo "Checking AWS credentials via aws sts get-caller-identity"
ACCOUNT="$($AWS_VAULT_CMD exec "$PROFILE" --no-session -- aws sts get-caller-identity --query Account --output text)"
if [ -z "$ACCOUNT" ]; then
  echo "ERROR: failed to determine AWS account. Check aws-vault profile and backend." >&2
  exit 1
fi

echo "Detected AWS account: $ACCOUNT"

# Bootstrap (creates CDK assets bucket and roles)
echo "Bootstrapping CDK into aws://$ACCOUNT/$AWS_REGION"
$AWS_VAULT_CMD exec "$PROFILE" --no-session -- npx cdk bootstrap aws://$ACCOUNT/$AWS_REGION -c stage=$STAGE --require-approval never

# Deploy ApiStack first to avoid cross-stack export conflicts,
# then deploy all stacks to apply any remaining updates.
echo "Deploying ChaterApiStack first (removes cross-stack references if any)"
$AWS_VAULT_CMD exec "$PROFILE" --no-session -- npx cdk deploy ChaterApiStack -c stage=$STAGE --require-approval never

echo "Deploying all remaining CDK stacks"
$AWS_VAULT_CMD exec "$PROFILE" --no-session -- npx cdk deploy --all -c stage=$STAGE --require-approval never

echo "CDK deploy finished. Review output above for stack outputs and endpoints."
