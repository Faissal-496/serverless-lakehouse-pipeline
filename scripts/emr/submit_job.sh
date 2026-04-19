#!/usr/bin/env bash
# =============================================================================
# Submit a Spark job to EMR Serverless
# Usage: ./scripts/emr/submit_job.sh <job_module> [execution_date]
# Example: ./scripts/emr/submit_job.sh lakehouse/jobs/bronze_ingest_job.py 2026-01-15
# =============================================================================
set -euo pipefail

JOB_SCRIPT="${1:?Usage: submit_job.sh <job_script> [execution_date]}"
EXECUTION_DATE="${2:-$(date +%Y-%m-%d)}"

AWS_REGION="${AWS_DEFAULT_REGION:-eu-west-3}"
S3_BUCKET="${S3_BUCKET:-lakehouse-assurance-prod-data}"
EMR_EXECUTION_ROLE_ARN="${EMR_EXECUTION_ROLE_ARN:?Set EMR_EXECUTION_ROLE_ARN}"

# Load app ID
if [[ -f "$(dirname "$0")/../../.emr-app-id" ]]; then
    source "$(dirname "$0")/../../.emr-app-id"
fi
EMR_APP_ID="${EMR_APP_ID:?Set EMR_APP_ID or run create_emr_app.sh first}"

S3_JOB_SCRIPT="s3://${S3_BUCKET}/emr/scripts/${JOB_SCRIPT}"
S3_LOGS="s3://${S3_BUCKET}/logs/emr-serverless/"

echo "==> Submitting job: ${JOB_SCRIPT}"
echo "    App ID: ${EMR_APP_ID}"
echo "    Execution Date: ${EXECUTION_DATE}"

SPARK_SUBMIT_PARAMS=$(cat <<EOF
--conf spark.sql.adaptive.enabled=true
--conf spark.sql.adaptive.coalescePartitions.enabled=true
--conf spark.sql.adaptive.skewJoin.enabled=true
--conf spark.driver.memory=2g
--conf spark.executor.memory=2g
--conf spark.dynamicAllocation.enabled=true
--conf spark.dynamicAllocation.minExecutors=1
--conf spark.dynamicAllocation.maxExecutors=6
--conf spark.sql.shuffle.partitions=16
--conf spark.hadoop.fs.s3a.fast.upload=true
--conf spark.hadoop.fs.s3a.connection.maximum=100
--conf spark.serializer=org.apache.spark.serializer.KryoSerializer
--conf spark.io.compression.codec=snappy
--conf spark.sql.parquet.compression.codec=snappy
--conf spark.sql.sources.partitionOverwriteMode=dynamic
--conf spark.hadoop.fs.s3a.aws.credentials.provider=com.amazonaws.auth.DefaultAWSCredentialsProviderChain
EOF
)

JOB_RUN_ID=$(aws emr-serverless start-job-run \
  --application-id "${EMR_APP_ID}" \
  --execution-role-arn "${EMR_EXECUTION_ROLE_ARN}" \
  --name "lakehouse-$(basename "${JOB_SCRIPT}" .py)-${EXECUTION_DATE}" \
  --job-driver "{
    \"sparkSubmit\": {
      \"entryPoint\": \"${S3_JOB_SCRIPT}\",
      \"entryPointArguments\": [\"--execution_date\", \"${EXECUTION_DATE}\"],
      \"sparkSubmitParameters\": \"${SPARK_SUBMIT_PARAMS}\"
    }
  }" \
  --configuration-overrides "{
    \"monitoringConfiguration\": {
      \"s3MonitoringConfiguration\": {
        \"logUri\": \"${S3_LOGS}\"
      }
    }
  }" \
  --region "${AWS_REGION}" \
  --query 'jobRunId' --output text)

echo "==> Job Run ID: ${JOB_RUN_ID}"
echo "==> Monitor: aws emr-serverless get-job-run --application-id ${EMR_APP_ID} --job-run-id ${JOB_RUN_ID} --region ${AWS_REGION}"

# Wait for completion
echo "==> Waiting for job to complete..."
while true; do
    STATUS=$(aws emr-serverless get-job-run \
      --application-id "${EMR_APP_ID}" \
      --job-run-id "${JOB_RUN_ID}" \
      --region "${AWS_REGION}" \
      --query 'jobRun.state' --output text)
    echo "    Status: ${STATUS}"
    case "${STATUS}" in
        SUCCESS) echo "==> Job completed successfully"; exit 0 ;;
        FAILED|CANCELLED) echo "==> Job ${STATUS}"; exit 1 ;;
        *) sleep 15 ;;
    esac
done
