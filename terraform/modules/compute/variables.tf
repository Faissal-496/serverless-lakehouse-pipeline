# ============================================================================
# COMPUTE MODULE - INPUT VARIABLES
# ============================================================================

variable "name" {
  type        = string
  description = "Base name for instances"
}

variable "role_tag" {
  type        = string
  description = "Role tag for instances"
}

variable "instance_count" {
  type        = number
  description = "Number of instances"
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type"
}

variable "ami_id" {
  type        = string
  description = "AMI ID"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs"
}

variable "security_group_ids" {
  type        = list(string)
  description = "Security group IDs"
}

variable "associate_public_ip" {
  type        = bool
  description = "Associate public IP"
  default     = true
}

variable "key_name" {
  type        = string
  description = "SSH key name"
  default     = ""
}

variable "iam_instance_profile" {
  type        = string
  description = "IAM instance profile name"
  default     = ""
}

variable "user_data" {
  type        = string
  description = "User data script"
  default     = ""
}

variable "root_volume_size" {
  type        = number
  description = "Root volume size (GB)"
  default     = 20
}

variable "root_volume_type" {
  type        = string
  description = "Root volume type"
  default     = "gp3"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
