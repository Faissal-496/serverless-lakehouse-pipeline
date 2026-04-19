#!/usr/bin/env bash
# =============================================================================
# Setup IAM role for EMR Serverless execution
# Usage: ./scripts/emr/setup_emr_iam.sh
# =============================================================================
set -euo pipefail

AWS_REGION="${AWS_DEFAULT_REGION:-eu-west-3}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-387642999442}"
ROLE_NAME="lakehouse-emr-serverless-execution-role"
POLICY_NAME="lakehouse-emr-serverless-policy"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Creating EMR Serverless execution role: ${ROLE_NAME}"

# Trust policy for EMR Serverless
aws iam create-role \
  --role-name "${ROLE_NAME}" \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Service": "emr-serverless.amazonaws.com"
        },
        "Action": "sts:AssumeRole"
      }
    ]
  }' \
  --region "${AWS_REGION}" || echo "Role already exists"

echo "==> Attaching policy"
aws iam put-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-name "${POLICY_NAME}" \
  --policy-document "file://${SCRIPT_DIR}/emr-execution-role-policy.json" \
  --region "${AWS_REGION}"

ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"
echo "==> Done. Role ARN: ${ROLE_ARN}"
echo "    Set EMR_EXECUTION_ROLE_ARN=${ROLE_ARN} in your .env"
