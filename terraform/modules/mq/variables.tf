# ============================================================================
# AMAZON MQ MODULE - INPUT VARIABLES
# ============================================================================

variable "broker_name" {
  type        = string
  description = "Broker name"
}

variable "engine_version" {
  type        = string
  description = "RabbitMQ engine version"
}

variable "instance_type" {
  type        = string
  description = "Broker instance type"
}

variable "deployment_mode" {
  type        = string
  description = "Deployment mode (SINGLE_INSTANCE or ACTIVE_STANDBY_MULTI_AZ)"
  default     = "SINGLE_INSTANCE"
}

variable "publicly_accessible" {
  type        = bool
  description = "Publicly accessible broker"
  default     = false
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs"
}

variable "security_group_ids" {
  type        = list(string)
  description = "Security group IDs"
}

variable "username" {
  type        = string
  description = "RabbitMQ username"
  sensitive   = true
}

variable "password" {
  type        = string
  description = "RabbitMQ password"
  sensitive   = true
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
