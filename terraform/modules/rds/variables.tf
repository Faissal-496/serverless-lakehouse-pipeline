# ============================================================================
# RDS MODULE - INPUT VARIABLES
# ============================================================================

variable "identifier" {
  type        = string
  description = "RDS instance identifier"
}

variable "instance_class" {
  type        = string
  description = "RDS instance class"
}

variable "allocated_storage" {
  type        = number
  description = "Allocated storage"
}

variable "max_allocated_storage" {
  type        = number
  description = "Max allocated storage"
}

variable "backup_retention_period" {
  type        = number
  description = "Backup retention period"
}

variable "multi_az" {
  type        = bool
  description = "Multi-AZ"
}

variable "engine_version" {
  type        = string
  description = "PostgreSQL version"
}

variable "database_name" {
  type        = string
  description = "Database name"
}

variable "master_username" {
  type        = string
  description = "Master username"
}

variable "master_password" {
  type        = string
  description = "Master password"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs"
}

variable "vpc_security_group_ids" {
  type        = list(string)
  description = "Security group IDs"
}

variable "environment" {
  type        = string
  description = "Environment"
}

variable "force_ssl" {
  type        = bool
  description = "Force SSL for PostgreSQL"
  default     = true
}

variable "tags" {
  type        = map(string)
  description = "Tags"
  default     = {}
}
