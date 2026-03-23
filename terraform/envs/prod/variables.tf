variable "aws_region" {
  type        = string
  description = "AWS region for deployment"
  default     = "eu-west-3"
}

variable "environment" {
  type        = string
  description = "Environment name (dev, staging, prod)"
  default     = "prod"
}

variable "project_name" {
  type        = string
  description = "Project name"
  default     = "lakehouse-assurance"
}

variable "cost_center" {
  type        = string
  description = "Cost center"
  default     = "insurance-analytics"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR"
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public subnet CIDRs"
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "Private subnet CIDRs"
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

variable "enable_nat_gateway" {
  type        = bool
  description = "Enable NAT gateway"
  default     = true
}

variable "allowed_ingress_cidr_blocks" {
  type        = list(string)
  description = "CIDR blocks allowed to access public UIs"
  default     = ["0.0.0.0/0"]
}

variable "ssh_cidr_blocks" {
  type        = list(string)
  description = "CIDR blocks allowed to SSH"
  default     = []
}

variable "ec2_instance_type" {
  type        = string
  description = "EC2 instance type"
  default     = "t3.micro"
}

variable "ec2_key_name" {
  type        = string
  description = "SSH key pair name"
  default     = ""
}

variable "airflow_scheduler_count" {
  type        = number
  description = "Number of Airflow schedulers"
  default     = 2
}

variable "airflow_worker_desired" {
  type        = number
  description = "Desired Airflow worker count"
  default     = 2
}

variable "airflow_worker_min" {
  type        = number
  description = "Minimum Airflow workers"
  default     = 1
}

variable "airflow_worker_max" {
  type        = number
  description = "Maximum Airflow workers"
  default     = 4
}

variable "jenkins_controller_count" {
  type        = number
  description = "Number of Jenkins controllers"
  default     = 2
}

variable "jenkins_agent_count" {
  type        = number
  description = "Number of Jenkins agents"
  default     = 4
}

variable "jenkins_admin_user" {
  type        = string
  description = "Jenkins admin username"
  sensitive   = true
}

variable "jenkins_admin_password" {
  type        = string
  description = "Jenkins admin password"
  sensitive   = true
}

variable "mq_engine_version" {
  type        = string
  description = "RabbitMQ engine version"
  default     = "3.11.20"
}

variable "mq_instance_type" {
  type        = string
  description = "Amazon MQ instance type"
  default     = "mq.t3.micro"
}

variable "mq_deployment_mode" {
  type        = string
  description = "Amazon MQ deployment mode"
  default     = "SINGLE_INSTANCE"
}

variable "mq_username" {
  type        = string
  description = "RabbitMQ username"
  sensitive   = true
}

variable "mq_password" {
  type        = string
  description = "RabbitMQ password"
  sensitive   = true
}

variable "ecr_repository_names" {
  type        = list(string)
  description = "ECR repositories"
  default     = [
    "airflow-runtime",
    "spark-runtime",
    "jenkins-agent",
    "lakehouse-base"
  ]
}

variable "airflow_ecr_repo" {
  type        = string
  description = "ECR repo for Airflow image"
  default     = "airflow-runtime"
}

variable "airflow_image_tag" {
  type        = string
  description = "Airflow image tag (short SHA)"
  default     = "latest"
}

variable "airflow_dags_repo" {
  type        = string
  description = "Git repo for DAGs"
  default     = "https://github.com/Faissal-496/serverless-lakehouse-pipeline.git"
}

variable "airflow_dags_branch" {
  type        = string
  description = "Git branch for DAGs"
  default     = "main"
}

variable "airflow_fernet_key" {
  type        = string
  description = "Airflow Fernet key"
  sensitive   = true
}

variable "airflow_webserver_secret_key" {
  type        = string
  description = "Airflow webserver secret key"
  sensitive   = true
}

variable "s3_bucket_name" {
  type        = string
  description = "S3 bucket name"
}

variable "s3_enable_versioning" {
  type        = bool
  description = "Enable S3 versioning"
  default     = true
}

variable "s3_enable_encryption" {
  type        = bool
  description = "Enable S3 encryption"
  default     = true
}

variable "s3_kms_key_enabled" {
  type        = bool
  description = "Use KMS encryption"
  default     = false
}

variable "s3_lifecycle_days_to_ia" {
  type        = number
  description = "Days to Intelligent-Tiering"
  default     = 30
}

variable "s3_lifecycle_days_to_glacier" {
  type        = number
  description = "Days to Glacier"
  default     = 180
}

variable "s3_enable_access_logging" {
  type        = bool
  description = "Enable S3 access logging"
  default     = true
}

variable "rds_instance_class" {
  type        = string
  description = "RDS instance class"
  default     = "db.t3.micro"
}

variable "rds_allocated_storage" {
  type        = number
  description = "RDS allocated storage"
  default     = 20
}

variable "rds_max_allocated_storage" {
  type        = number
  description = "RDS max storage"
  default     = 200
}

variable "rds_backup_retention_days" {
  type        = number
  description = "RDS backup retention days"
  default     = 7
}

variable "rds_multi_az" {
  type        = bool
  description = "Enable RDS Multi-AZ"
  default     = false
}

variable "rds_force_ssl" {
  type        = bool
  description = "Force SSL for PostgreSQL"
  default     = true
}

variable "rds_engine_version" {
  type        = string
  description = "PostgreSQL version"
  default     = "15.3"
}

variable "rds_database_name" {
  type        = string
  description = "RDS database name"
  default     = "lakehouse_prod"
}

variable "rds_master_username" {
  type        = string
  description = "RDS master username"
  sensitive   = true
}

variable "rds_master_password" {
  type        = string
  description = "RDS master password"
  sensitive   = true
}

variable "cloudwatch_log_retention_days" {
  type        = number
  description = "CloudWatch log retention days"
  default     = 90
}

variable "cloudwatch_alarm_email" {
  type        = string
  description = "CloudWatch alarm email"
}

variable "cloudwatch_enable_dashboards" {
  type        = bool
  description = "Enable CloudWatch dashboards"
  default     = false
}

variable "enable_secrets_manager" {
  type        = bool
  description = "Enable AWS Secrets Manager"
  default     = false
}

variable "glue_catalog_database_name" {
  type        = string
  description = "Glue Catalog database name"
  default     = "lakehouse"
}

variable "emr_serverless_application_id" {
  type        = string
  description = "EMR Serverless application ID"
  default     = ""
}

variable "emr_serverless_execution_role_arn" {
  type        = string
  description = "EMR Serverless execution role ARN"
  default     = ""
}

variable "alb_certificate_arn" {
  type        = string
  description = "ACM certificate ARN"
}

variable "alb_ssl_policy" {
  type        = string
  description = "ALB SSL policy"
  default     = "ELBSecurityPolicy-2016-08"
}

variable "tags" {
  type        = map(string)
  description = "Common tags"
  default = {
    Environment = "development"
    ManagedBy   = "Terraform"
    Project     = "lakehouse-assurance"
  }
}

variable "additional_tags" {
  type        = map(string)
  description = "Additional tags"
  default     = {}
}
