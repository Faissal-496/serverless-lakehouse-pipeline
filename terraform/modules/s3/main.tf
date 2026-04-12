# ============================================================================
# TERRAFORM MODULE: S3 DATA LAKE STORAGE
# ============================================================================
#
# This module creates enterprise-grade S3 bucket with:
# - Versioning (data protection)
# - Encryption (security)
# - Lifecycle policies (cost optimization)
# - Access logging (audit trail)
# - Intelligent-Tiering (automatic cost optimization)
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
# S3 BUCKET
# ============================================================================

resource "aws_s3_bucket" "data_lake" {
  bucket = var.bucket_name

  tags = merge(
    var.tags,
    {
      Name    = var.bucket_name
      Purpose = "Data Lake Storage"
    }
  )
}

# Block public access (critical for security)
resource "aws_s3_bucket_public_access_block" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ============================================================================
# VERSIONING (Data Protection)
# ============================================================================

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  versioning_configuration {
    status     = var.enable_versioning ? "Enabled" : "Disabled"
    mfa_delete = "Disabled"  # Set to "Enabled" only if MFA protection required
  }
}

# ============================================================================
# ENCRYPTION (Security at Rest)
# ============================================================================

resource "aws_s3_bucket_server_side_encryption_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm      = var.kms_key_enabled ? "aws:kms" : "AES256"
      kms_master_key_id  = var.kms_key_enabled ? aws_kms_key.s3[0].arn : null
    }
    bucket_key_enabled = true  # Reduces KMS API calls + costs
  }
}

# Optional: KMS key for advanced encryption (costs extra)
resource "aws_kms_key" "s3" {
  count = var.kms_key_enabled ? 1 : 0

  description             = "KMS key for ${var.bucket_name} encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM policies"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow S3 to use the key"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = var.tags
}

resource "aws_kms_alias" "s3" {
  count         = var.kms_key_enabled ? 1 : 0
  name          = "alias/${var.bucket_name}"
  target_key_id = aws_kms_key.s3[0].key_id
}

# ============================================================================
# ACCESS LOGGING (Audit Trail)
# ============================================================================

resource "aws_s3_bucket" "logs" {
  count  = var.enable_access_logging ? 1 : 0
  bucket = "${var.bucket_name}-logs"

  tags = merge(
    var.tags,
    {
      Name    = "${var.bucket_name}-logs"
      Purpose = "S3 Access Logs"
    }
  )
}

resource "aws_s3_bucket_public_access_block" "logs" {
  count  = var.enable_access_logging ? 1 : 0
  bucket = aws_s3_bucket.logs[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_logging" "data_lake" {
  count  = var.enable_access_logging ? 1 : 0
  bucket = aws_s3_bucket.data_lake.id

  target_bucket = aws_s3_bucket.logs[0].id
  target_prefix = "access-logs/"
}

# ============================================================================
# LIFECYCLE POLICIES (Cost Optimization)
# ============================================================================
#
# Automatic data migration strategy:
#   New data (0-30 days): Standard (fast, full cost)
#   Warm data (30-180 days): Intelligent-Tiering (cost optimized)
#   Cold data (180+ days): Glacier (archive, low cost)
#

resource "aws_s3_bucket_lifecycle_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  rule {
    id     = "intelligent-tiering"
    status = "Enabled"

    # Apply to all non-noncurrent versions
    filter {
      prefix = ""
    }

    # Transition to Intelligent-Tiering after X days
    transition {
      days          = var.lifecycle_days_to_ia
      storage_class = "INTELLIGENT_TIERING"
    }

    # Transition to Glacier after Y days
    transition {
      days          = var.lifecycle_days_to_glacier
      storage_class = "GLACIER"
    }

    # Optional: Delete very old objects (e.g., after 7 years for compliance)
    # expiration {
    #   days = 2555  # ~7 years
    # }
  }

  # Handle noncurrent (deleted) versions
  rule {
    id     = "delete-noncurrent"
    status = "Enabled"

    filter {
      prefix = ""
    }

    noncurrent_version_expiration {
      noncurrent_days = 90  # Delete old versions after 90 days
    }
  }
}

# ============================================================================
# BUCKET STRUCTURE (Logical Partitioning)
# ============================================================================

# ============================================================================
# OUTPUTS
# ============================================================================

output "bucket_name" {
  value       = aws_s3_bucket.data_lake.id
  description = "S3 bucket name"
}

output "bucket_arn" {
  value       = aws_s3_bucket.data_lake.arn
  description = "S3 bucket ARN"
}

output "bucket_region" {
  value       = aws_s3_bucket.data_lake.region
  description = "S3 bucket region"
}

output "logs_bucket_name" {
  value       = var.enable_access_logging ? aws_s3_bucket.logs[0].id : null
  description = "S3 logs bucket name (if enabled)"
}
