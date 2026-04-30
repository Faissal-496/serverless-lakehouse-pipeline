# ============================================================================
# GLUE CATALOG MODULE — INPUT VARIABLES
# ============================================================================

variable "name_prefix" {
  type        = string
  description = "Prefix for IAM role/policy names (e.g. 'lakehouse-assurance-prod')"
}

variable "db_name_prefix" {
  type        = string
  description = "Prefix for Glue database names (e.g. 'lakehouse'). Databases created: <prefix>_bronze, <prefix>_silver, <prefix>_gold"
  default     = "lakehouse"
}

variable "s3_bucket_name" {
  type        = string
  description = "Name of the S3 data lake bucket (without s3:// prefix)"
}

variable "region" {
  type        = string
  description = "AWS region"
  default     = "eu-west-3"
}

variable "account_id" {
  type        = string
  description = "AWS account ID"
}

variable "ec2_role_name" {
  type        = string
  description = "Name of the EC2 IAM role to attach Athena+Glue permissions to (used by Airflow workers)"
}

variable "crawler_schedule" {
  type        = string
  description = "Cron schedule for Glue Crawlers in Glue format (e.g. 'cron(30 3 * * ? *)'). Empty string = no schedule (on-demand only)."
  default     = "cron(30 3 * * ? *)"
}

variable "athena_workgroup_name" {
  type        = string
  description = "Name of the Athena Workgroup"
  default     = "lakehouse"
}

variable "athena_bytes_scanned_cutoff" {
  type        = number
  description = "Max bytes scanned per Athena query before it is cancelled (safety limit). Default: 10 GB."
  default     = 10737418240 # 10 GB
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
  default     = {}
}
