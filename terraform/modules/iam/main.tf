# ============================================================================
# TERRAFORM MODULE: IAM ROLES AND POLICIES
# ============================================================================
#
# Least-privilege access for ETL jobs, Spark, and Airflow
#

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ============================================================================
# IAM ROLE FOR ETL JOBS (SPARK + AIRFLOW)
# ============================================================================

resource "aws_iam_role" "lakehouse_etl" {
  name = "${var.name_prefix}-etl-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = [
            "ec2.amazonaws.com",       # For EC2 instances
            "ecs-tasks.amazonaws.com", # For ECS tasks
            "lambda.amazonaws.com"     # For future Lambda jobs
          ]
        }
      },
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.account_id}:root"
        }

        Condition = {
          StringEquals = {
            "sts:ExternalId" = "lakehouse-etl"
          }
        }
      }
    ]
  })

  tags = var.tags
}

# ============================================================================
# S3 BUCKET ACCESS
# ============================================================================

resource "aws_iam_policy" "s3_access" {
  name = "${var.name_prefix}-s3-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3DataLakeFullAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetObjectVersion",
          "s3:PutObjectAcl"
        ]
        Resource = [
          var.s3_bucket_arn,
          "${var.s3_bucket_arn}/*"
        ]
      },
      {
        Sid    = "S3ListAllBuckets"
        Effect = "Allow"
        Action = [
          "s3:ListAllMyBuckets",
          "s3:GetBucketVersioning"
        ]
        Resource = "*"
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "s3_access" {
  role       = aws_iam_role.lakehouse_etl.name
  policy_arn = aws_iam_policy.s3_access.arn
}

# ============================================================================
# CLOUDWATCH LOGS ACCESS
# ============================================================================

resource "aws_iam_policy" "cloudwatch_logs" {
  name = "${var.name_prefix}-cloudwatch-logs-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CreateLogGroups"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/lakehouse/*"
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "cloudwatch_logs" {
  role       = aws_iam_role.lakehouse_etl.name
  policy_arn = aws_iam_policy.cloudwatch_logs.arn
}

# ============================================================================
# SECRETS MANAGER ACCESS
# ============================================================================

resource "aws_iam_policy" "secrets_manager" {
  name = "${var.name_prefix}-secrets-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GetSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          "arn:aws:secretsmanager:${var.region}:${var.account_id}:secret:lakehouse/*"
        ]
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "secrets_manager" {
  role       = aws_iam_role.lakehouse_etl.name
  policy_arn = aws_iam_policy.secrets_manager.arn
}

# ============================================================================
# GLUE CATALOG ACCESS
# ============================================================================

resource "aws_iam_policy" "glue_catalog" {
  name = "${var.name_prefix}-glue-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GlueCatalogAccess"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetPartitions",
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

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "glue_catalog" {
  role       = aws_iam_role.lakehouse_etl.name
  policy_arn = aws_iam_policy.glue_catalog.arn
}

# ============================================================================
# ECR ACCESS (Jenkins agents + runtime image pulls)
# ============================================================================

resource "aws_iam_policy" "ecr_access" {
  name = "${var.name_prefix}-ecr-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRAuthToken"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Sid    = "ECRReadWrite"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage"
        ]
        Resource = [
          "arn:aws:ecr:${var.region}:${var.account_id}:repository/*"
        ]
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ecr_access" {
  role       = aws_iam_role.lakehouse_etl.name
  policy_arn = aws_iam_policy.ecr_access.arn
}

# ============================================================================
# EMR SERVERLESS ACCESS (OPTIONAL)
# ============================================================================

resource "aws_iam_policy" "emr_serverless" {
  count = var.emr_serverless_application_id != "" && var.emr_serverless_execution_role_arn != "" ? 1 : 0

  name = "${var.name_prefix}-emr-serverless-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EmrServerlessAccess"
        Effect = "Allow"
        Action = [
          "emr-serverless:StartJobRun",
          "emr-serverless:GetJobRun",
          "emr-serverless:CancelJobRun",
          "emr-serverless:ListJobRuns",
          "emr-serverless:GetApplication",
          "emr-serverless:StartApplication",
          "emr-serverless:StopApplication"
        ]
        Resource = "arn:aws:emr-serverless:${var.region}:${var.account_id}:*"
      },
      {
        Sid    = "PassEmrExecutionRole"
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = var.emr_serverless_execution_role_arn
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "emr_serverless" {
  count = var.emr_serverless_application_id != "" && var.emr_serverless_execution_role_arn != "" ? 1 : 0

  role       = aws_iam_role.lakehouse_etl.name
  policy_arn = aws_iam_policy.emr_serverless[0].arn
}

# ============================================================================
# SNS ALERTING ACCESS
# ============================================================================

resource "aws_iam_policy" "sns_alerts" {
  count = var.sns_topic_arn != "" ? 1 : 0

  name = "${var.name_prefix}-sns-alerts-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "SNSPublishAlerts"
        Effect   = "Allow"
        Action   = "sns:Publish"
        Resource = var.sns_topic_arn
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "sns_alerts" {
  count = var.sns_topic_arn != "" ? 1 : 0

  role       = aws_iam_role.lakehouse_etl.name
  policy_arn = aws_iam_policy.sns_alerts[0].arn
}

# ============================================================================
# INSTANCE PROFILE (for EC2 instances)
# ============================================================================

resource "aws_iam_instance_profile" "lakehouse_etl" {
  name = "${var.name_prefix}-etl-profile"
  role = aws_iam_role.lakehouse_etl.name
}

# ============================================================================
# OUTPUTS
# ============================================================================

output "lakehouse_etl_role_arn" {
  value = aws_iam_role.lakehouse_etl.arn
}

output "lakehouse_etl_role_name" {
  value = aws_iam_role.lakehouse_etl.name
}

output "instance_profile_arn" {
  value = aws_iam_instance_profile.lakehouse_etl.arn
}

output "instance_profile_name" {
  value = aws_iam_instance_profile.lakehouse_etl.name
}
