# ============================================================================
# BOOTSTRAP VARIABLES
# ============================================================================

variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "eu-west-3"
}

variable "state_bucket_name" {
  type        = string
  description = "S3 bucket for Terraform state"
}

variable "lock_table_name" {
  type        = string
  description = "DynamoDB table for state locking"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
