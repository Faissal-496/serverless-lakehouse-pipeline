# ============================================================================
# IAM MODULE - INPUT VARIABLES
# ============================================================================

variable "name_prefix" {
  type        = string
  description = "Prefix for resource names"
}

variable "s3_bucket_arn" {
  type        = string
  description = "ARN of S3 data lake bucket"
}

variable "rds_resource_id" {
  type        = string
  description = "RDS resource ID"
  default     = "" # Optional for advanced policies
}

variable "account_id" {
  type        = string
  description = "AWS account ID"
}

variable "region" {
  type        = string
  description = "AWS region"
}

variable "emr_serverless_application_id" {
  type        = string
  description = "EMR Serverless application ID"
  default     = ""
}

variable "emr_serverless_execution_role_arn" {
  type        = string
  description = "EMR Serverless execution role ARN"
  default     = ""
}

variable "sns_topic_arn" {
  type        = string
  description = "SNS topic ARN for ETL alerts"
  default     = ""
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
