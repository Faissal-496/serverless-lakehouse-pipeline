# ============================================================================
# ALB MODULE - INPUT VARIABLES
# ============================================================================

variable "name" {
  type        = string
  description = "ALB name"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs"
}

variable "security_group_ids" {
  type        = list(string)
  description = "Security group IDs"
}

variable "target_instance_ids" {
  type        = list(string)
  description = "EC2 instance IDs to attach"
}

variable "target_groups" {
  type = map(object({
    name              = string
    port              = number
    health_check_path = string
    host_headers      = list(string)
    priority          = number
  }))
  description = "Target groups + host-based routing rules"
}

variable "listener_port" {
  type        = number
  description = "Listener port"
  default     = 80
}

variable "enable_https" {
  type        = bool
  description = "Enable HTTPS listener and HTTP->HTTPS redirect"
  default     = true
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate ARN for HTTPS listener"
  default     = ""
}

variable "ssl_policy" {
  type        = string
  description = "SSL policy for HTTPS listener"
  default     = "ELBSecurityPolicy-2016-08"
}

variable "internal" {
  type        = bool
  description = "Internal ALB"
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
