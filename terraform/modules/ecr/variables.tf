variable "repository_names" {
  description = "List of ECR repository names to create"
  type        = list(string)
  default = [
    "lakehouse/airflow",
    "lakehouse/jenkins",
    "lakehouse/spark-base",
    "lakehouse/spark-master",
    "lakehouse/spark-worker",
  ]
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
