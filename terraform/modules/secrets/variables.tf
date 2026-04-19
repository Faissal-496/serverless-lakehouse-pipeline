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
  default     = ""
}

variable "mq_password" {
  type        = string
  description = "MQ password"
  default     = ""
}

variable "mq_endpoint" {
  type        = string
  description = "MQ endpoint"
  default     = ""
}

variable "airflow_fernet_key" {
  type        = string
  description = "Airflow Fernet key"
}

variable "airflow_webserver_secret_key" {
  type        = string
  description = "Airflow webserver secret key"
}

variable "airflow_admin_user" {
  type        = string
  description = "Airflow admin username"
  default     = ""
}

variable "airflow_admin_password" {
  type        = string
  description = "Airflow admin password"
  default     = ""
}

variable "airflow_admin_email" {
  type        = string
  description = "Airflow admin email"
  default     = ""
}

variable "airflow_base_url" {
  type        = string
  description = "Airflow public base URL"
  default     = ""
}

variable "jenkins_admin_user" {
  type        = string
  description = "Jenkins admin username"
  default     = ""
}

variable "jenkins_admin_password" {
  type        = string
  description = "Jenkins admin password"
  default     = ""
}

variable "jenkins_public_url" {
  type        = string
  description = "Jenkins public URL"
  default     = ""
}

variable "host_repo_path" {
  type        = string
  description = "Host path where the repo is cloned (used by Jenkins Docker agents)"
  default     = ""
}

variable "tags" {
  type        = map(string)
  description = "Tags"
  default     = {}
}
