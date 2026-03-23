# ============================================================================
# TERRAFORM MODULE: CLOUDWATCH LOGGING
# ============================================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ============================================================================
# LOG GROUPS
# ============================================================================

resource "aws_cloudwatch_log_group" "spark" {
  name              = "/aws/lakehouse/spark"
  retention_in_days = var.log_retention_days
  
  tags = merge(
    var.tags,
    {
      Name    = "Spark ETL Logs"
      Service = "spark"
    }
  )
}

resource "aws_cloudwatch_log_group" "airflow" {
  name              = "/aws/lakehouse/airflow"
  retention_in_days = var.log_retention_days
  
  tags = merge(
    var.tags,
    {
      Name    = "Airflow Orchestration Logs"
      Service = "airflow"
    }
  )
}

# ============================================================================
# SNS TOPIC FOR ALERTS
# ============================================================================

resource "aws_sns_topic" "alerts" {
  name = "${var.name_prefix}-alerts"
  
  tags = merge(
    var.tags,
    {
      Name = "Lakehouse Alerts"
    }
  )
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alarm_notification_email
}

# ============================================================================
# OUTPUTS
# ============================================================================

output "spark_log_group_name" {
  value = aws_cloudwatch_log_group.spark.name
}

output "airflow_log_group_name" {
  value = aws_cloudwatch_log_group.airflow.name
}

output "alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}
