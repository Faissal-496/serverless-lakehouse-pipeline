#!/usr/bin/env bash
# =============================================================================
# Setup CloudWatch Dashboard, Alarms, and SNS Alerting for Lakehouse ETL
# Usage: ./scripts/monitoring/setup_cloudwatch.sh
# =============================================================================
set -euo pipefail

AWS_REGION="${AWS_DEFAULT_REGION:-eu-west-3}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-387642999442}"
ALERT_EMAIL="${ALERT_EMAIL:-faissal_496@outlook.com}"
S3_BUCKET="${S3_BUCKET:-lakehouse-assurance-prod-data}"
PROFILE="${AWS_PROFILE:-faissal_3}"

echo "==> Setting up CloudWatch monitoring for Lakehouse ETL"
echo "    Region: ${AWS_REGION}"
echo "    Alert email: ${ALERT_EMAIL}"

# ============================================================================
# 1. Create SNS Topic for alerts
# ============================================================================
echo "==> Creating SNS topic: lakehouse-etl-alerts"
TOPIC_ARN=$(aws sns create-topic \
  --name lakehouse-etl-alerts \
  --region "${AWS_REGION}" \
  --profile "${PROFILE}" \
  --query 'TopicArn' --output text)

echo "    Topic ARN: ${TOPIC_ARN}"

# Subscribe email
aws sns subscribe \
  --topic-arn "${TOPIC_ARN}" \
  --protocol email \
  --notification-endpoint "${ALERT_EMAIL}" \
  --region "${AWS_REGION}" \
  --profile "${PROFILE}" > /dev/null

echo "    Subscribed: ${ALERT_EMAIL} (check inbox to confirm)"

# ============================================================================
# 2. Create CloudWatch Log Groups
# ============================================================================
for LOG_GROUP in /lakehouse/etl/jobs /lakehouse/emr-serverless /lakehouse/airflow /lakehouse/jenkins; do
  aws logs create-log-group \
    --log-group-name "${LOG_GROUP}" \
    --region "${AWS_REGION}" \
    --profile "${PROFILE}" 2>/dev/null || echo "    Log group ${LOG_GROUP} already exists"

  aws logs put-retention-policy \
    --log-group-name "${LOG_GROUP}" \
    --retention-in-days 30 \
    --region "${AWS_REGION}" \
    --profile "${PROFILE}"
done
echo "==> Log groups created with 30-day retention"

# ============================================================================
# 3. Create CloudWatch Alarms
# ============================================================================

# Alarm: EMR Serverless job failure
echo "==> Creating alarm: lakehouse-emr-job-failure"
aws cloudwatch put-metric-alarm \
  --alarm-name "lakehouse-emr-job-failure" \
  --alarm-description "EMR Serverless job failed" \
  --namespace "Lakehouse/ETL" \
  --metric-name "JobFailures" \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --alarm-actions "${TOPIC_ARN}" \
  --treat-missing-data notBreaching \
  --region "${AWS_REGION}" \
  --profile "${PROFILE}"

# Alarm: S3 bucket size monitoring
echo "==> Creating alarm: lakehouse-s3-bucket-size"
aws cloudwatch put-metric-alarm \
  --alarm-name "lakehouse-s3-bucket-size-high" \
  --alarm-description "S3 bucket data exceeds 50GB" \
  --namespace "AWS/S3" \
  --metric-name "BucketSizeBytes" \
  --dimensions "Name=BucketName,Value=${S3_BUCKET}" "Name=StorageType,Value=StandardStorage" \
  --statistic Average \
  --period 86400 \
  --threshold 53687091200 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions "${TOPIC_ARN}" \
  --treat-missing-data notBreaching \
  --region "${AWS_REGION}" \
  --profile "${PROFILE}"

# Alarm: EC2 CPU high
echo "==> Creating alarm: lakehouse-ec2-cpu-high"
aws cloudwatch put-metric-alarm \
  --alarm-name "lakehouse-ec2-cpu-high" \
  --alarm-description "EC2 instance CPU exceeds 85% for 10 minutes" \
  --namespace "AWS/EC2" \
  --metric-name "CPUUtilization" \
  --statistic Average \
  --period 300 \
  --threshold 85 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions "${TOPIC_ARN}" \
  --treat-missing-data notBreaching \
  --region "${AWS_REGION}" \
  --profile "${PROFILE}"

echo "==> Alarms created"

# ============================================================================
# 4. Create CloudWatch Dashboard
# ============================================================================
echo "==> Creating CloudWatch dashboard: lakehouse-etl"

DASHBOARD_BODY=$(cat <<'DASHBOARD_JSON'
{
  "widgets": [
    {
      "type": "text",
      "x": 0, "y": 0, "width": 24, "height": 1,
      "properties": {
        "markdown": "# Lakehouse ETL Pipeline — Monitoring Dashboard"
      }
    },
    {
      "type": "metric",
      "x": 0, "y": 1, "width": 12, "height": 6,
      "properties": {
        "title": "EC2 CPU Utilization",
        "metrics": [
          ["AWS/EC2", "CPUUtilization", {"stat": "Average", "period": 300}]
        ],
        "view": "timeSeries",
        "region": "eu-west-3",
        "yAxis": {"left": {"min": 0, "max": 100}},
        "period": 300
      }
    },
    {
      "type": "metric",
      "x": 12, "y": 1, "width": 12, "height": 6,
      "properties": {
        "title": "EC2 Network In/Out",
        "metrics": [
          ["AWS/EC2", "NetworkIn", {"stat": "Average", "period": 300}],
          ["AWS/EC2", "NetworkOut", {"stat": "Average", "period": 300}]
        ],
        "view": "timeSeries",
        "region": "eu-west-3",
        "period": 300
      }
    },
    {
      "type": "metric",
      "x": 0, "y": 7, "width": 12, "height": 6,
      "properties": {
        "title": "S3 Bucket Size (Bytes)",
        "metrics": [
          ["AWS/S3", "BucketSizeBytes", "BucketName", "lakehouse-assurance-prod-data", "StorageType", "StandardStorage", {"stat": "Average", "period": 86400}]
        ],
        "view": "timeSeries",
        "region": "eu-west-3",
        "period": 86400
      }
    },
    {
      "type": "metric",
      "x": 12, "y": 7, "width": 12, "height": 6,
      "properties": {
        "title": "S3 Number of Objects",
        "metrics": [
          ["AWS/S3", "NumberOfObjects", "BucketName", "lakehouse-assurance-prod-data", "StorageType", "AllStorageTypes", {"stat": "Average", "period": 86400}]
        ],
        "view": "timeSeries",
        "region": "eu-west-3",
        "period": 86400
      }
    },
    {
      "type": "metric",
      "x": 0, "y": 13, "width": 24, "height": 6,
      "properties": {
        "title": "ETL Job Metrics (Custom)",
        "metrics": [
          ["Lakehouse/ETL", "JobDuration", {"stat": "Average", "period": 300}],
          ["Lakehouse/ETL", "JobFailures", {"stat": "Sum", "period": 300}],
          ["Lakehouse/ETL", "RecordsProcessed", {"stat": "Sum", "period": 300}]
        ],
        "view": "timeSeries",
        "region": "eu-west-3",
        "period": 300
      }
    },
    {
      "type": "log",
      "x": 0, "y": 19, "width": 24, "height": 6,
      "properties": {
        "title": "ETL Job Logs (recent errors)",
        "query": "SOURCE '/lakehouse/etl/jobs' | fields @timestamp, @message | filter @message like /ERROR|FAILED|Exception/ | sort @timestamp desc | limit 20",
        "region": "eu-west-3",
        "view": "table"
      }
    }
  ]
}
DASHBOARD_JSON
)

aws cloudwatch put-dashboard \
  --dashboard-name "lakehouse-etl" \
  --dashboard-body "${DASHBOARD_BODY}" \
  --region "${AWS_REGION}" \
  --profile "${PROFILE}"

echo "==> Dashboard created: https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=lakehouse-etl"
echo "==> Done. Check ${ALERT_EMAIL} for SNS subscription confirmation."
