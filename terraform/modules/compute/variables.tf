# ============================================================================
# COMPUTE MODULE - INPUT VARIABLES
# ============================================================================

variable "name" {
  type        = string
  description = "Base name for instances"
}

variable "role_tag" {
  type        = string
  description = "Role tag"
}

variable "instance_count" {
  type        = number
  description = "Number of instances"
  default     = 1
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
  description = "Associate a public IP to the instance"
  default     = false
}

variable "key_name" {
  type        = string
  description = "EC2 key pair name"
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
  default     = 50
}

variable "root_volume_type" {
  type        = string
  description = "Root volume type"
  default     = "gp3"
}

variable "tags" {
  type        = map(string)
  description = "Tags"
  default     = {}
}
