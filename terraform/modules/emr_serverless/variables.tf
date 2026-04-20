variable "app_name" {
  description = "EMR Serverless application name"
  type        = string
  default     = "lakehouse-etl"
}

variable "release_label" {
  description = "EMR release label"
  type        = string
  default     = "emr-7.0.0"
}

variable "s3_bucket" {
  description = "S3 bucket for data and logs"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-3"
}

variable "aws_account_id" {
  description = "AWS account ID"
  type        = string
}

variable "driver_cpu" {
  type    = string
  default = "2 vCPU"
}

variable "driver_memory" {
  type    = string
  default = "4 GB"
}

variable "executor_cpu" {
  type    = string
  default = "2 vCPU"
}

variable "executor_memory" {
  type    = string
  default = "4 GB"
}

variable "initial_executor_count" {
  type    = number
  default = 2
}

variable "max_cpu" {
  type    = string
  default = "16 vCPU"
}

variable "max_memory" {
  type    = string
  default = "32 GB"
}

variable "max_disk" {
  type    = string
  default = "200 GB"
}

variable "idle_timeout_minutes" {
  type    = number
  default = 10
}

variable "tags" {
  type    = map(string)
  default = {}
}
