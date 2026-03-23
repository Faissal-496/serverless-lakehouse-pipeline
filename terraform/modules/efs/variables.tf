# ============================================================================
# EFS MODULE - INPUT VARIABLES
# ============================================================================

variable "name_prefix" {
  type        = string
  description = "Prefix for resource naming"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnets for mount targets"
}

variable "security_group_ids" {
  type        = list(string)
  description = "Security groups for mount targets"
}

variable "encrypted" {
  type        = bool
  description = "Enable encryption"
  default     = true
}

variable "performance_mode" {
  type        = string
  description = "EFS performance mode"
  default     = "generalPurpose"
}

variable "throughput_mode" {
  type        = string
  description = "EFS throughput mode"
  default     = "bursting"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
