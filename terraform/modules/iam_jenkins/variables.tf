variable "name_prefix" {
  type        = string
  description = "Prefix for resource naming"
}

variable "terraform_state_bucket" {
  type        = string
  description = "S3 bucket name for Terraform remote state"
  default     = "lakehouse-assurance-moto-tfstate"
}

variable "terraform_lock_table" {
  type        = string
  description = "DynamoDB table name for Terraform state locking"
  default     = "lakehouse-assurance-moto-tflocks"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
