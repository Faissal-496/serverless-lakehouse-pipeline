variable "name_prefix" {
  type        = string
  description = "Prefix for resource names"
}

variable "release_label" {
  type        = string
  description = "EMR release label (must include Spark 3.5)"
  default     = "emr-7.1.0"
}

variable "initial_driver_count" {
  type        = number
  description = "Pre-initialized driver workers"
  default     = 1
}

variable "initial_executor_count" {
  type        = number
  description = "Pre-initialized executor workers"
  default     = 2
}

variable "driver_cpu" {
  type        = string
  default     = "2 vCPU"
}

variable "driver_memory" {
  type        = string
  default     = "4 GB"
}

variable "executor_cpu" {
  type        = string
  default     = "4 vCPU"
}

variable "executor_memory" {
  type        = string
  default     = "8 GB"
}

variable "max_cpu" {
  type        = string
  description = "Maximum total vCPUs for the application"
  default     = "40 vCPU"
}

variable "max_memory" {
  type        = string
  description = "Maximum total memory for the application"
  default     = "100 GB"
}

variable "idle_timeout_minutes" {
  type        = number
  description = "Minutes of idle time before auto-stop"
  default     = 10
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for EMR networking"
}

variable "security_group_ids" {
  type        = list(string)
  description = "Security group IDs for EMR networking"
}

variable "s3_bucket_arn" {
  type        = string
  description = "ARN of the data lake S3 bucket"
}

variable "region" {
  type        = string
  description = "AWS region"
}

variable "account_id" {
  type        = string
  description = "AWS account ID"
}

variable "tags" {
  type        = map(string)
  default     = {}
}
