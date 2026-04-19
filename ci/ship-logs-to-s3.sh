#!/usr/bin/env bash
# ============================================================================
# ship-logs-to-s3.sh — Sync Docker & Jenkins logs to S3
# Intended to run via cron on the EC2 host:
#   */30 * * * * /opt/serverless-lakehouse-pipeline/ci/ship-logs-to-s3.sh
# ============================================================================
set -euo pipefail

BUCKET="${S3_BUCKET:-lakehouse-assurance-prod-data}"
REGION="${AWS_DEFAULT_REGION:-eu-west-3}"
COMPOSE_DIR="/opt/serverless-lakehouse-pipeline"
DATE=$(date -u +%Y-%m-%d)
TIMESTAMP=$(date -u +%H%M%S)

# --- Docker container logs ---
for container in jenkins spark-master spark-worker-1 spark-worker-2 redis; do
    FULL_NAME=$(docker ps --filter "name=${container}" --format '{{.Names}}' 2>/dev/null | head -1)
    if [[ -n "$FULL_NAME" ]]; then
        docker logs --since 30m "$FULL_NAME" 2>&1 | \
            aws s3 cp - "s3://${BUCKET}/logs/docker/${container}/${DATE}/${TIMESTAMP}.log" \
            --region "$REGION" 2>/dev/null || true
    fi
done

# --- Jenkins build logs (last 24h modified) ---
JENKINS_LOGS="/var/lib/docker/volumes/serverless-lakehouse-pipeline_jenkins_home/_data/jobs"
if [[ -d "$JENKINS_LOGS" ]]; then
    find "$JENKINS_LOGS" -name "log" -mmin -30 -type f 2>/dev/null | while read -r logfile; do
        REL_PATH="${logfile#$JENKINS_LOGS/}"
        aws s3 cp "$logfile" "s3://${BUCKET}/logs/jenkins/${DATE}/${REL_PATH}" \
            --region "$REGION" 2>/dev/null || true
    done
fi

echo "[$(date -u)] Log shipping complete"
