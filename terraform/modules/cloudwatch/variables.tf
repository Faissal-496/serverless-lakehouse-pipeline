# ============================================================================
# CLOUDWATCH MODULE - INPUT VARIABLES
# ============================================================================

variable "name_prefix" {
  type        = string
  description = "Prefix for resource names"
}

variable "log_retention_days" {
  type        = number
  description = "Log retention period in days"
  default     = 90
}

variable "alarm_notification_email" {
  type        = string
  description = "Email for alarm notifications"
}

variable "enable_dashboards" {
  type        = bool
  description = "Enable CloudWatch dashboards"
  default     = false
}

variable "aws_region" {
  type        = string
  description = "AWS region (for dashboards)"
  default     = "eu-west-3"
}

variable "rds_instance_identifier" {
  type        = string
  description = "RDS instance identifier for dashboard metrics"
  default     = ""
}

variable "data_quality_alarm_name" {
  type        = string
  description = "CloudWatch alarm name for data quality"
  default     = ""
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
