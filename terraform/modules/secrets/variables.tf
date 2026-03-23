variable "enable" {
  type        = bool
  description = "Enable secrets manager"
  default     = false
}

variable "name_prefix" {
  type        = string
  description = "Prefix for secret names"
}

variable "rds_username" {
  type        = string
  description = "RDS username"
}

variable "rds_password" {
  type        = string
  description = "RDS password"
}

variable "rds_host" {
  type        = string
  description = "RDS host"
}

variable "rds_port" {
  type        = string
  description = "RDS port"
  default     = "5432"
}

variable "rds_db_name" {
  type        = string
  description = "RDS DB name"
}

variable "mq_username" {
  type        = string
  description = "MQ username"
}

variable "mq_password" {
  type        = string
  description = "MQ password"
}

variable "mq_endpoint" {
  type        = string
  description = "MQ endpoint"
}

variable "airflow_fernet_key" {
  type        = string
  description = "Airflow Fernet key"
}

variable "airflow_webserver_secret_key" {
  type        = string
  description = "Airflow webserver secret key"
}

variable "tags" {
  type        = map(string)
  description = "Tags"
  default     = {}
}
