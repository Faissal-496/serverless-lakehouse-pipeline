# Advanced CloudWatch Dashboards for Enterprise Data Lake Observability

resource "aws_cloudwatch_dashboard" "operational" {
  count = var.enable_dashboards ? 1 : 0

  dashboard_name = "${var.name_prefix}-operational-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["LakehouseMetrics", "JobSuccess", { stat = "Average", label = "Job Success Rate" }],
            [".", "JobDuration", { stat = "Average", label = "Avg Job Duration" }],
            [".", "RecordsProcessed", { stat = "Sum", label = "Total Records Processed" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Pipeline Health Overview"
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/S3", "NumberOfObjects", { stat = "Average" }],
            [".", "BucketSizeBytes", { stat = "Average" }]
          ]
          period = 3600
          stat   = "Average"
          region = var.aws_region
          title  = "S3 Data Lake Size & Object Count"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/RDS", "CPUUtilization", { dimensions = { DBInstanceIdentifier = var.rds_instance_identifier } }],
            [".", "DatabaseConnections", { dimensions = { DBInstanceIdentifier = var.rds_instance_identifier } }],
            [".", "AvailableMemory", { dimensions = { DBInstanceIdentifier = var.rds_instance_identifier } }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "RDS Database Performance"
        }
      },
      {
        type = "log"
        properties = {
          query  = "fields @timestamp, @message, job_name | stats count() as event_count by job_name"
          region = var.aws_region
          title  = "Jobs Execution Summary"
        }
      }
    ]
  })
}

resource "aws_cloudwatch_dashboard" "data_quality" {
  count = var.enable_dashboards ? 1 : 0

  dashboard_name = "${var.name_prefix}-data-quality-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["LakehouseMetrics", "DataQualityScore", { stat = "Average" }],
            [".", "NullRecordCount", { stat = "Sum" }],
            [".", "DuplicateRecordCount", { stat = "Sum" }]
          ]
          period = 3600
          stat   = "Average"
          region = var.aws_region
          title  = "Data Quality Metrics"
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["LakehouseMetrics", "ValidationPassRate", { stat = "Average" }]
          ]
          period = 3600
          stat   = "Average"
          region = var.aws_region
          title  = "Data Validation Success Rate"
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/CloudWatch", "AlarmStateChange", { dimensions = { AlarmName = var.data_quality_alarm_name } }]
          ]
          period = 60
          region = var.aws_region
          title  = "Data Quality Alerts"
        }
      }
    ]
  })
}

resource "aws_cloudwatch_dashboard" "executive" {
  count = var.enable_dashboards ? 1 : 0

  dashboard_name = "${var.name_prefix}-executive-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/S3", "BucketSizeBytes", { stat = "Average" }]
          ]
          period = 86400
          stat   = "Average"
          region = var.aws_region
          title  = "Data Lake Growth (GB)"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["LakehouseMetrics", "JobSuccess", { stat = "Average" }]
          ]
          period = 86400
          stat   = "Average"
          region = var.aws_region
          title  = "Pipeline Reliability (%)"
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/RDS", "EstimatedCharges", { stat = "Maximum" }]
          ]
          period = 86400
          stat   = "Maximum"
          region = var.aws_region
          title  = "Estimated Monthly Cost (USD)"
        }
      }
    ]
  })
}
