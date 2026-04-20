# =============================================================================
# CloudWatch Monitoring: Dashboard, Alarms, SNS, Log Groups
# =============================================================================

# --- SNS Topic for alerts ---
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
  tags = var.tags
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# --- CloudWatch Log Groups ---
resource "aws_cloudwatch_log_group" "logs" {
  for_each = toset(var.log_groups)

  name              = each.value
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

# --- CloudWatch Alarms ---
resource "aws_cloudwatch_metric_alarm" "emr_job_failure" {
  alarm_name          = "${var.project_name}-emr-job-failure"
  alarm_description   = "EMR Serverless job failed"
  namespace           = "Lakehouse/ETL"
  metric_name         = "JobFailures"
  statistic           = "Sum"
  period              = 300
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "ec2_cpu_high" {
  alarm_name          = "${var.project_name}-ec2-cpu-high"
  alarm_description   = "EC2 CPU exceeds 85% for 10 minutes"
  namespace           = "AWS/EC2"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  threshold           = 85
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "s3_bucket_size" {
  alarm_name          = "${var.project_name}-s3-bucket-size-high"
  alarm_description   = "S3 bucket exceeds 50GB"
  namespace           = "AWS/S3"
  metric_name         = "BucketSizeBytes"
  statistic           = "Average"
  period              = 86400
  threshold           = 53687091200
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    BucketName  = var.s3_bucket
    StorageType = "StandardStorage"
  }

  tags = var.tags
}

# --- CloudWatch Dashboard ---
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = var.project_name
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "text"
        x = 0, y = 0, width = 24, height = 1
        properties = {
          markdown = "# ${var.project_name} — Monitoring Dashboard"
        }
      },
      {
        type   = "metric"
        x = 0, y = 1, width = 12, height = 6
        properties = {
          title   = "EC2 CPU Utilization"
          metrics = [["AWS/EC2", "CPUUtilization", { stat = "Average", period = 300 }]]
          view    = "timeSeries"
          region  = var.aws_region
          yAxis   = { left = { min = 0, max = 100 } }
        }
      },
      {
        type   = "metric"
        x = 12, y = 1, width = 12, height = 6
        properties = {
          title = "EC2 Network In/Out"
          metrics = [
            ["AWS/EC2", "NetworkIn", { stat = "Average", period = 300 }],
            ["AWS/EC2", "NetworkOut", { stat = "Average", period = 300 }],
          ]
          view   = "timeSeries"
          region = var.aws_region
        }
      },
      {
        type   = "metric"
        x = 0, y = 7, width = 12, height = 6
        properties = {
          title = "S3 Bucket Size"
          metrics = [
            ["AWS/S3", "BucketSizeBytes", "BucketName", var.s3_bucket, "StorageType", "StandardStorage", { stat = "Average", period = 86400 }],
          ]
          view   = "timeSeries"
          region = var.aws_region
        }
      },
      {
        type   = "metric"
        x = 12, y = 7, width = 12, height = 6
        properties = {
          title = "S3 Number of Objects"
          metrics = [
            ["AWS/S3", "NumberOfObjects", "BucketName", var.s3_bucket, "StorageType", "AllStorageTypes", { stat = "Average", period = 86400 }],
          ]
          view   = "timeSeries"
          region = var.aws_region
        }
      },
      {
        type   = "metric"
        x = 0, y = 13, width = 24, height = 6
        properties = {
          title = "ETL Job Metrics"
          metrics = [
            ["Lakehouse/ETL", "JobDuration", { stat = "Average", period = 300 }],
            ["Lakehouse/ETL", "JobFailures", { stat = "Sum", period = 300 }],
            ["Lakehouse/ETL", "RecordsProcessed", { stat = "Sum", period = 300 }],
          ]
          view   = "timeSeries"
          region = var.aws_region
        }
      },
    ]
  })
}
