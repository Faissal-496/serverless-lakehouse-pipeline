# ============================================================================
# S3 MODULE - INPUT VARIABLES
# ============================================================================

variable "bucket_name" {
  type        = string
  description = "Name of S3 bucket"
}

variable "environment" {
  type        = string
  description = "Environment name"
  default     = "dev"
}

variable "enable_versioning" {
  type        = bool
  description = "Enable versioning for data protection"
  default     = true
}

variable "enable_encryption" {
  type        = bool
  description = "Enable server-side encryption"
  default     = true
}

variable "kms_key_enabled" {
  type        = bool
  description = "Use KMS encryption (vs AES-256)"
  default     = false
}

variable "enable_access_logging" {
  type        = bool
  description = "Enable access logging to separate bucket"
  default     = true
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
  description = "AWS account ID"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to resources"
  default     = {}
}
