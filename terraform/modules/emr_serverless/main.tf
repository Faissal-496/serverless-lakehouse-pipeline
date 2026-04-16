# EMR Serverless application and execution role.
# The application provides a managed Spark runtime.
# The execution role defines what the Spark jobs are allowed to access.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# EMR Serverless application (Spark 3.5)
resource "aws_emrserverless_application" "spark" {
  name          = "${var.name_prefix}-spark"
  release_label = var.release_label
  type          = "SPARK"

  initial_capacity {
    initial_capacity_type = "Driver"

    initial_capacity_config {
      worker_count = var.initial_driver_count
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
  }

  auto_start_configuration {
    enabled = true
  }

  auto_stop_configuration {
    enabled              = true
    idle_timeout_minutes = var.idle_timeout_minutes
  }

  network_configuration {
    subnet_ids         = var.subnet_ids
    security_group_ids = var.security_group_ids
  }

  tags = var.tags
}

# IAM role assumed by EMR Serverless when running Spark jobs.
resource "aws_iam_role" "emr_execution" {
  name = "${var.name_prefix}-emr-exec-role"

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

# S3 access for data lake prefixes
resource "aws_iam_role_policy" "emr_s3" {
  name = "${var.name_prefix}-emr-s3"
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
          "s3:ListBucket"
        ]
        Resource = [
          var.s3_bucket_arn,
          "${var.s3_bucket_arn}/*"
        ]
      }
    ]
  })
}

# Glue catalog access so Spark can register tables
resource "aws_iam_role_policy" "emr_glue" {
  name = "${var.name_prefix}-emr-glue"
  role = aws_iam_role.emr_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GlueAccess"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetPartitions",
          "glue:CreateTable",
          "glue:UpdateTable",
          "glue:CreatePartition",
          "glue:BatchCreatePartition"
        ]
        Resource = [
          "arn:aws:glue:${var.region}:${var.account_id}:catalog",
          "arn:aws:glue:${var.region}:${var.account_id}:database/*",
          "arn:aws:glue:${var.region}:${var.account_id}:table/*/*"
        ]
      }
    ]
  })
}

# CloudWatch logs for Spark driver and executor output
resource "aws_iam_role_policy" "emr_logs" {
  name = "${var.name_prefix}-emr-logs"
  role = aws_iam_role.emr_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/emr-serverless/*"
      }
    ]
  })
}
