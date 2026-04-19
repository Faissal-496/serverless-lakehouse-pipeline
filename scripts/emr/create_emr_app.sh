#!/usr/bin/env bash
# =============================================================================
# Create / update EMR Serverless application for Lakehouse ETL
# Usage: ./scripts/emr/create_emr_app.sh
# =============================================================================
set -euo pipefail

AWS_REGION="${AWS_DEFAULT_REGION:-eu-west-3}"
APP_NAME="lakehouse-etl"
RELEASE_LABEL="emr-7.0.0"
S3_BUCKET="${S3_BUCKET:-lakehouse-assurance-prod-data}"

echo "==> Creating EMR Serverless application: ${APP_NAME}"

APP_ID=$(aws emr-serverless create-application \
  --name "${APP_NAME}" \
  --release-label "${RELEASE_LABEL}" \
  --type SPARK \
  --region "${AWS_REGION}" \
  --initial-capacity '{
    "DRIVER": {
      "workerCount": 1,
      "workerConfiguration": {
        "cpu": "2vCPU",
        "memory": "4GB"
      }
    },
    "EXECUTOR": {
      "workerCount": 2,
      "workerConfiguration": {
        "cpu": "2vCPU",
        "memory": "4GB"
      }
    }
  }' \
  --maximum-capacity '{
    "cpu": "16vCPU",
    "memory": "32GB",
    "disk": "200GB"
  }' \
  --auto-start-configuration '{"enabled": true}' \
  --auto-stop-configuration '{"enabled": true, "idleTimeoutMinutes": 10}' \
  --query 'applicationId' --output text)

echo "==> EMR Serverless Application ID: ${APP_ID}"

# Store the app ID for later use
echo "EMR_APP_ID=${APP_ID}" > "$(dirname "$0")/../../.emr-app-id"

echo "==> Uploading job scripts to S3"
aws s3 cp src/lakehouse/ "s3://${S3_BUCKET}/emr/scripts/lakehouse/" --recursive \
  --exclude "__pycache__/*" --exclude "*.pyc" \
  --region "${AWS_REGION}"

echo "==> Done. Application ${APP_ID} is ready."
echo "    To submit a job, use: scripts/emr/submit_job.sh <job_script>"
