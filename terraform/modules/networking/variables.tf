# ============================================================================
# NETWORKING MODULE - INPUT VARIABLES
# ============================================================================

variable "name_prefix" {
  type        = string
  description = "Prefix for resource naming"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for public subnets (one per AZ)"
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for private subnets (one per AZ)"
}

variable "availability_zones" {
  type        = list(string)
  description = "Availability Zones to use (must be at least as many as subnets)"
}

variable "enable_nat_gateway" {
  type        = bool
  description = "Whether to create a NAT gateway for private subnets"
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to resources"
  default     = {}
}
