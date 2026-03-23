variable "name" {
  type        = string
  description = "Base name for instances"
}

variable "role_tag" {
  type        = string
  description = "Role tag"
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

variable "iam_instance_profile" {
  type        = string
  description = "IAM instance profile name"
  default     = ""
}

variable "user_data" {
  type        = string
  description = "User data"
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

variable "desired_capacity" {
  type        = number
  description = "Desired capacity"
  default     = 2
}

variable "min_size" {
  type        = number
  description = "Min size"
  default     = 1
}

variable "max_size" {
  type        = number
  description = "Max size"
  default     = 4
}

variable "tags" {
  type        = map(string)
  description = "Tags"
  default     = {}
}
