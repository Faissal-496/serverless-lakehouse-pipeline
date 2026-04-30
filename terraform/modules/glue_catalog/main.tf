# ============================================================================
# TERRAFORM MODULE: GLUE CATALOG + ATHENA WORKGROUP
# ============================================================================
#
# Creates:
#   - Glue databases: bronze, silver, gold (3 layers)
#   - IAM Role for Glue Crawlers (Glue service role + S3 read)
#   - Glue Crawlers for each layer (auto-discovers Parquet schemas)
#   - Athena Workgroup with S3 results location + SSE encryption
#   - IAM policy for EC2/Airflow to call Athena + Glue (attached to ec2_role_name)
#
# Usage: query Gold/Silver/Bronze data with SQL via Athena without any Spark.
# ============================================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

locals {
  s3_uri = "s3://${var.s3_bucket_name}"
}

# ============================================================================
# GLUE DATABASES (one per Medallion layer)
# ============================================================================

resource "aws_glue_catalog_database" "bronze" {
  name         = "${var.db_name_prefix}_bronze"
  description  = "Lakehouse Bronze — raw ingested Parquet data (Client, Contrat1, Contrat2)"
  location_uri = "${local.s3_uri}/bronze/"

  tags = var.tags
}

resource "aws_glue_catalog_database" "silver" {
  name         = "${var.db_name_prefix}_silver"
  description  = "Lakehouse Silver — consolidated, joined, business-decoded data"
  location_uri = "${local.s3_uri}/silver/"

  tags = var.tags
}

resource "aws_glue_catalog_database" "gold" {
  name         = "${var.db_name_prefix}_gold"
  description  = "Lakehouse Gold — analytics-ready aggregated tables (KPIs, profiles)"
  location_uri = "${local.s3_uri}/gold/"

  tags = var.tags
}

# ============================================================================
# IAM ROLE FOR GLUE CRAWLERS
# ============================================================================

resource "aws_iam_role" "glue_crawler" {
  name        = "${var.name_prefix}-glue-crawler-role"
  description = "Role assumed by Glue Crawlers to read S3 and update the Catalog"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "GlueAssumeRole"
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
    }]
  })

  tags = var.tags
}

# AWS managed Glue service policy (Glue API + CloudWatch Logs)
resource "aws_iam_role_policy_attachment" "glue_service_managed" {
  role       = aws_iam_role.glue_crawler.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Custom S3 read policy scoped to our bucket only
resource "aws_iam_policy" "crawler_s3_read" {
  name        = "${var.name_prefix}-glue-crawler-s3-policy"
  description = "Allows Glue Crawlers to read Parquet files from the Lakehouse S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3CrawlerReadBucket"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          "arn:aws:s3:::${var.s3_bucket_name}",
          "arn:aws:s3:::${var.s3_bucket_name}/*"
        ]
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "crawler_s3_read" {
  role       = aws_iam_role.glue_crawler.name
  policy_arn = aws_iam_policy.crawler_s3_read.arn
}

# ============================================================================
# GLUE CRAWLERS (one per Medallion layer)
# Each crawler auto-discovers Parquet column types and creates/updates tables.
# ============================================================================

resource "aws_glue_crawler" "bronze" {
  name          = "${var.name_prefix}-bronze-crawler"
  role          = aws_iam_role.glue_crawler.arn
  database_name = aws_glue_catalog_database.bronze.name
  description   = "Discovers schema of Bronze Parquet files (Client, Contrat1, Contrat2)"

  # Optional scheduled run (e.g. daily at 03:00 UTC, after ETL pipeline)
  schedule = var.crawler_schedule

  s3_target {
    path = "${local.s3_uri}/bronze/"
    # exclusions = ["**/_SUCCESS", "**/_committed_*", "**/_started_*"]
  }

  schema_change_policy {
    delete_behavior = "LOG"             # Don't delete tables on schema change — log only
    update_behavior = "UPDATE_IN_DATABASE"
  }

  recrawl_policy {
    recrawl_behavior = "CRAWL_NEW_FOLDERS_ONLY"  # Efficient: only crawl new partitions
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
      Tables     = { AddOrUpdateBehavior = "MergeNewColumns" }
    }
  })

  tags = var.tags
}

resource "aws_glue_crawler" "silver" {
  name          = "${var.name_prefix}-silver-crawler"
  role          = aws_iam_role.glue_crawler.arn
  database_name = aws_glue_catalog_database.silver.name
  description   = "Discovers schema of Silver Parquet files (Client_contrat_silver)"

  schedule = var.crawler_schedule

  s3_target {
    path = "${local.s3_uri}/silver/"
  }

  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "UPDATE_IN_DATABASE"
  }

  recrawl_policy {
    recrawl_behavior = "CRAWL_NEW_FOLDERS_ONLY"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Tables = { AddOrUpdateBehavior = "MergeNewColumns" }
    }
  })

  tags = var.tags
}

resource "aws_glue_crawler" "gold" {
  name          = "${var.name_prefix}-gold-crawler"
  role          = aws_iam_role.glue_crawler.arn
  database_name = aws_glue_catalog_database.gold.name
  description   = "Discovers schema of Gold Parquet files (client_profile_analysis, contract_analysis)"

  schedule = var.crawler_schedule

  s3_target {
    path = "${local.s3_uri}/gold/"
  }

  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "UPDATE_IN_DATABASE"
  }

  recrawl_policy {
    recrawl_behavior = "CRAWL_NEW_FOLDERS_ONLY"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Tables = { AddOrUpdateBehavior = "MergeNewColumns" }
    }
  })

  tags = var.tags
}

# ============================================================================
# ATHENA WORKGROUP
# ============================================================================

resource "aws_athena_workgroup" "lakehouse" {
  name        = var.athena_workgroup_name
  description = "Lakehouse Analytics — SQL queries on Medallion layers via Glue Catalog"
  state       = "ENABLED"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "${local.s3_uri}/athena/results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }

    engine_version {
      selected_engine_version = "Athena engine version 3"
    }

    # Safety limit: stop queries that would scan more than N bytes
    bytes_scanned_cutoff_per_query = var.athena_bytes_scanned_cutoff
  }

  tags = var.tags
}

# ============================================================================
# IAM POLICY: ATHENA + GLUE ACCESS FOR EC2 ROLE (Airflow workers)
# ============================================================================

resource "aws_iam_policy" "athena_glue_access" {
  name        = "${var.name_prefix}-athena-glue-access-policy"
  description = "Allows EC2/Airflow workers to execute Athena queries and read Glue Catalog"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AthenaQueryExecution"
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:StopQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:GetQueryResultsStream",
          "athena:GetWorkGroup",
          "athena:ListQueryExecutions",
          "athena:BatchGetQueryExecution",
          "athena:GetNamedQuery",
          "athena:ListNamedQueries",
          "athena:CreateNamedQuery",
          "athena:ListWorkGroups",
          "athena:GetDataCatalog",
          "athena:ListDataCatalogs"
        ]
        Resource = [
          "arn:aws:athena:${var.region}:${var.account_id}:workgroup/${var.athena_workgroup_name}",
          "arn:aws:athena:${var.region}:${var.account_id}:workgroup/primary",
          "arn:aws:athena:${var.region}:${var.account_id}:datacatalog/AwsDataCatalog"
        ]
      },
      {
        Sid    = "GlueCatalogRead"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartition",
          "glue:GetPartitions",
          "glue:BatchGetPartition",
          "glue:GetCrawler",
          "glue:GetCrawlers",
          "glue:StartCrawler",
          "glue:GetCrawlerMetrics",
          "glue:GetCatalogImportStatus"
        ]
        Resource = [
          "arn:aws:glue:${var.region}:${var.account_id}:catalog",
          "arn:aws:glue:${var.region}:${var.account_id}:database/*",
          "arn:aws:glue:${var.region}:${var.account_id}:table/*/*",
          "arn:aws:glue:${var.region}:${var.account_id}:crawler/*"
        ]
      },
      {
        Sid    = "S3AthenaResultsAccess"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:GetBucketLocation",
          "s3:ListBucket",
          "s3:AbortMultipartUpload",
          "s3:ListBucketMultipartUploads",
          "s3:ListMultipartUploadParts"
        ]
        Resource = [
          "arn:aws:s3:::${var.s3_bucket_name}",
          "arn:aws:s3:::${var.s3_bucket_name}/athena/*"
        ]
      }
    ]
  })

  tags = var.tags
}

# Attach to the EC2 instance role (used by Airflow workers)
resource "aws_iam_role_policy_attachment" "ec2_athena_glue" {
  role       = var.ec2_role_name
  policy_arn = aws_iam_policy.athena_glue_access.arn
}
