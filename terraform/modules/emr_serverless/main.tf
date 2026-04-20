# =============================================================================
# EMR Serverless Application for Lakehouse ETL
# =============================================================================

# --- IAM Role for EMR Serverless Execution ---
resource "aws_iam_role" "emr_execution" {
  name = "${var.app_name}-emr-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "emr-serverless.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "emr_s3_access" {
  name = "${var.app_name}-emr-s3-access"
  role = aws_iam_role.emr_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3DataAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ]
        Resource = [
          "arn:aws:s3:::${var.s3_bucket}",
          "arn:aws:s3:::${var.s3_bucket}/*",
        ]
      },
      {
        Sid    = "GlueCatalog"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetTables",
          "glue:CreateTable",
          "glue:UpdateTable",
          "glue:GetPartitions",
          "glue:BatchCreatePartition",
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${var.aws_account_id}:*"
      },
    ]
  })
}

# --- EMR Serverless Application ---
resource "aws_emrserverless_application" "lakehouse" {
  name          = var.app_name
  release_label = var.release_label
  type          = "spark"

  initial_capacity {
    initial_capacity_type = "Driver"

    initial_capacity_config {
      worker_count = 1
      worker_configuration {
        cpu    = var.driver_cpu
        memory = var.driver_memory
      }
    }
  }

  initial_capacity {
    initial_capacity_type = "Executor"

    initial_capacity_config {
      worker_count = var.initial_executor_count
      worker_configuration {
        cpu    = var.executor_cpu
        memory = var.executor_memory
      }
    }
  }

  maximum_capacity {
    cpu    = var.max_cpu
    memory = var.max_memory
    disk   = var.max_disk
  }

  auto_start_configuration {
    enabled = true
  }

  auto_stop_configuration {
    enabled             = true
    idle_timeout_minutes = var.idle_timeout_minutes
  }

  tags = var.tags
}
