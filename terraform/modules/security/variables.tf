# ============================================================================
# SECURITY MODULE - INPUT VARIABLES
# ============================================================================

variable "name_prefix" {
  type        = string
  description = "Prefix for resource naming"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "allowed_ingress_cidr_blocks" {
  type        = list(string)
  description = "CIDR blocks allowed to access public UIs"
  default     = ["0.0.0.0/0"]
}

variable "ssh_cidr_blocks" {
  type        = list(string)
  description = "CIDR blocks allowed to SSH to instances"
  default     = []
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to resources"
  default     = {}
}
