# ============================================================================
# S3 MODULE - INPUT VARIABLES
# ============================================================================

variable "bucket_name" {
  type        = string
  description = "S3 bucket name"
}

variable "environment" {
  type        = string
  description = "Environment name"
}

variable "enable_versioning" {
  type        = bool
  description = "Enable bucket versioning"
  default     = true
}

variable "enable_encryption" {
  type        = bool
  description = "Enable default bucket encryption"
  default     = true
}

variable "kms_key_enabled" {
  type        = bool
  description = "Create and use a customer-managed KMS key for encryption"
  default     = false
}

variable "enable_access_logging" {
  type        = bool
  description = "Enable S3 server access logging"
  default     = false
}

variable "lifecycle_days_to_ia" {
  type        = number
  description = "Days before transitioning to Intelligent-Tiering"
  default     = 30
}

variable "lifecycle_days_to_glacier" {
  type        = number
  description = "Days before transitioning to Glacier"
  default     = 180
}

variable "account_id" {
  type        = string
  description = "AWS account ID (for KMS policies)"
}

variable "tags" {
  type        = map(string)
  description = "Tags"
  default     = {}
}
