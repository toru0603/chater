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

# --- CloudFront stage: query API URLs from CloudFormation and deploy ---
if [ "$STAGE" = "cloudfront" ]; then
  echo "Stage=cloudfront: fetching API URLs from CloudFormation"
  PROD_API_URL="$($AWS_VAULT_CMD exec "$PROFILE" --no-session -- aws cloudformation describe-stacks \
    --stack-name ChaterApiStack \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text)"
  DEV_API_URL="$($AWS_VAULT_CMD exec "$PROFILE" --no-session -- aws cloudformation describe-stacks \
    --stack-name ChaterApiStack-dev \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text)"

  if [ -z "$PROD_API_URL" ] || [ -z "$DEV_API_URL" ]; then
    echo "ERROR: Could not fetch prod or dev API URL from CloudFormation. Deploy prod and dev first." >&2
    exit 1
  fi

  echo "Prod API URL: $PROD_API_URL"
  echo "Dev  API URL: $DEV_API_URL"

  $AWS_VAULT_CMD exec "$PROFILE" --no-session -- npx cdk deploy ChaterCloudFrontStack \
    -c stage=cloudfront \
    -c prodApiUrl="$PROD_API_URL" \
    -c devApiUrl="$DEV_API_URL" \
    --require-approval never

  echo "CDK deploy finished. Review output above for CloudFront distribution URL."
  exit 0
fi

# --- Normal stage (prod/dev): deploy API/WebSocket/Dynamo stacks ---

# Deploy ApiStack first to avoid cross-stack export conflicts,
# then deploy all stacks to apply any remaining updates.
echo "Choosing ChaterApiStack target for stage '$STAGE' (prefer stage-specific name)"
CDK_STACK_BASE="ChaterApiStack"
CDK_STACK_STAGE="${CDK_STACK_BASE}-${STAGE}"

# list stacks available for this stage (allow failure)
AVAILABLE_STACKS="$($AWS_VAULT_CMD exec "$PROFILE" --no-session -- npx cdk ls -c stage=$STAGE || true)"
TARGET_STACK=""
if echo "$AVAILABLE_STACKS" | grep -xq "$CDK_STACK_STAGE"; then
  TARGET_STACK="$CDK_STACK_STAGE"
elif echo "$AVAILABLE_STACKS" | grep -xq "$CDK_STACK_BASE"; then
  TARGET_STACK="$CDK_STACK_BASE"
else
  echo "Warning: No $CDK_STACK_BASE or ${CDK_STACK_BASE}-${STAGE} found; will deploy all stacks instead"
fi

if [ -n "$TARGET_STACK" ]; then
  echo "Deploying $TARGET_STACK (removes cross-stack references if any)"
  if ! $AWS_VAULT_CMD exec "$PROFILE" --no-session -- npx cdk deploy "$TARGET_STACK" -c stage=$STAGE --require-approval never; then
    echo "Targeted deploy of $TARGET_STACK failed; continuing with --all"
  fi
else
  echo "Skipping targeted deploy"
fi

echo "Deploying all remaining CDK stacks"
$AWS_VAULT_CMD exec "$PROFILE" --no-session -- npx cdk deploy --all -c stage=$STAGE --require-approval never

echo "CDK deploy finished. Review output above for stack outputs and endpoints."
