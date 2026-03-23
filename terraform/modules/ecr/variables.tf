# ============================================================================
# ECR MODULE - INPUT VARIABLES
# ============================================================================

variable "repository_names" {
  type        = list(string)
  description = "List of ECR repository names"
}

variable "image_tag_mutability" {
  type        = string
  description = "Tag mutability (MUTABLE or IMMUTABLE)"
  default     = "MUTABLE"
}

variable "scan_on_push" {
  type        = bool
  description = "Enable image scan on push"
  default     = true
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}
