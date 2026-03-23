variable "name_prefix" {
  type        = string
  description = "Prefix for resource naming"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
