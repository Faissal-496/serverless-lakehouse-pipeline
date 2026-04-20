variable "project_name" {
  description = "Project name used as prefix for resources"
  type        = string
  default     = "lakehouse-etl"
}

variable "alert_email" {
  description = "Email address for alarm notifications"
  type        = string
}

variable "s3_bucket" {
  description = "S3 bucket name to monitor"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-3"
}

variable "log_groups" {
  description = "List of CloudWatch log group names to create"
  type        = list(string)
  default = [
    "/lakehouse/etl/jobs",
    "/lakehouse/emr-serverless",
    "/lakehouse/airflow",
    "/lakehouse/jenkins",
  ]
}

variable "log_retention_days" {
  description = "Number of days to retain logs"
  type        = number
  default     = 30
}

variable "tags" {
  type    = map(string)
  default = {}
}
