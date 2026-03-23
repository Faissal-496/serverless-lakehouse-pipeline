# ============================================================================
# GLUE MODULE - INPUT VARIABLES
# ============================================================================

variable "project" {
  type        = string
  description = "Project name"
  default     = "lakehouse"
}

variable "environment" {
  type        = string
  description = "Environment name (dev, staging, prod)"
  default     = "dev"
}

variable "database_name" {
  type        = string
  description = "Name of Glue Catalog database"
  default     = "lakehouse"
}

variable "description" {
  type        = string
  description = "Database description"
  default     = "Lakehouse metadata catalog"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
