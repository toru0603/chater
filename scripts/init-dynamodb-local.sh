#!/usr/bin/env bash
# Create DynamoDB Local tables required by the application.
# Run once after starting the DynamoDB Local container.
set -euo pipefail

ENDPOINT="${DYNAMODB_ENDPOINT:-http://localhost:8001}"

echo "Creating tables in DynamoDB Local at ${ENDPOINT} ..."

AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local \
aws dynamodb create-table \
  --table-name "ChaterConnections" \
  --attribute-definitions \
    AttributeName=connectionId,AttributeType=S \
    AttributeName=roomCode,AttributeType=S \
  --key-schema \
    AttributeName=connectionId,KeyType=HASH \
  --global-secondary-indexes '[{
    "IndexName": "RoomCodeIndex",
    "KeySchema": [{"AttributeName":"roomCode","KeyType":"HASH"}],
    "Projection": {"ProjectionType":"ALL"}
  }]' \
  --billing-mode PAY_PER_REQUEST \
  --endpoint-url "${ENDPOINT}" \
  --region ap-northeast-1 \
  2>&1 | grep -v "^$" || true

AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local \
aws dynamodb create-table \
  --table-name "ChaterUsers" \
  --attribute-definitions \
    AttributeName=username,AttributeType=S \
  --key-schema \
    AttributeName=username,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --endpoint-url "${ENDPOINT}" \
  --region ap-northeast-1 \
  2>&1 | grep -v "^$" || true

echo "Done."
