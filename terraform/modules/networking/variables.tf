# ============================================================================
# NETWORKING MODULE - INPUT VARIABLES
# ============================================================================

variable "name_prefix" {
  type        = string
  description = "Prefix for resource naming"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public subnet CIDR blocks"
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "Private subnet CIDR blocks"
}

variable "availability_zones" {
  type        = list(string)
  description = "Availability zones to use"
}

variable "enable_nat_gateway" {
  type        = bool
  description = "Enable NAT gateway for private subnets"
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to resources"
  default     = {}
}
