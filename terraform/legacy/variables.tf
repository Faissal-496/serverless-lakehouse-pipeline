# ============================================================================
# TERRAFORM VARIABLES - ENTERPRISE LAKEHOUSE PLATFORM
# ============================================================================
# 
# This file defines all input variables for the Infrastructure as Code.
# Values are provided via terraform.tfvars or environment variables.
#
# Usage:
#   terraform apply -var-file="terraform.tfvars"
#   TF_VAR_aws_region=eu-west-3 terraform apply
#

variable "aws_region" {
  type        = string
  description = "AWS region for deployment"
  default     = "eu-west-3"
  
  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]$", var.aws_region))
    error_message = "AWS region must be a valid region code (e.g., eu-west-3)."
  }
}

variable "environment" {
  type        = string
  description = "Environment name (dev, staging, prod)"
  default     = "dev"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "project_name" {
  type        = string
  description = "Project name (used for resource naming)"
  default     = "lakehouse-assurance"
}

variable "cost_center" {
  type        = string
  description = "Cost center for billing/chargeback"
  default     = "insurance-analytics"
}

# ============================================================================
# NETWORKING CONFIGURATION
# ============================================================================

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block"
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public subnet CIDR blocks"
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "Private subnet CIDR blocks"
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

variable "enable_nat_gateway" {
  type        = bool
  description = "Enable NAT gateway for private subnets"
  default     = false
}

variable "allowed_ingress_cidr_blocks" {
  type        = list(string)
  description = "CIDR blocks allowed to access public UIs (Jenkins/Airflow)"
  default     = ["0.0.0.0/0"]
}

variable "ssh_cidr_blocks" {
  type        = list(string)
  description = "CIDR blocks allowed to SSH to instances"
  default     = []
}

# ============================================================================
# EC2 COMPUTE CONFIGURATION
# ============================================================================

variable "ec2_instance_type" {
  type        = string
  description = "EC2 instance type for Airflow/Jenkins"
  default     = "t3.micro"
}

variable "ec2_key_name" {
  type        = string
  description = "SSH key pair name (optional)"
  default     = ""
}

variable "airflow_scheduler_count" {
  type        = number
  description = "Number of Airflow schedulers"
  default     = 2
}

variable "airflow_worker_count" {
  type        = number
  description = "Number of Airflow workers"
  default     = 2
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

# ============================================================================
# JENKINS ADMIN (JCasC)
# ============================================================================

variable "jenkins_admin_user" {
  type        = string
  description = "Jenkins admin username"
  sensitive   = true
}

variable "jenkins_admin_password" {
  type        = string
  description = "Jenkins admin password"
  sensitive   = true

  validation {
    condition     = length(var.jenkins_admin_password) >= 12
    error_message = "Jenkins admin password must be at least 12 characters."
  }
}

# ============================================================================
# AMAZON MQ (RABBITMQ)
# ============================================================================

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

# ============================================================================
# ECR (CONTAINER REGISTRY)
# ============================================================================

variable "ecr_repository_names" {
  type        = list(string)
  description = "List of ECR repositories to create"
  default     = [
    "airflow-runtime",
    "spark-runtime",
    "jenkins-agent",
    "lakehouse-base"
  ]
}

# ============================================================================
# AIRFLOW RUNTIME (GITSYNC + IMAGE TAGGING)
# ============================================================================

variable "airflow_ecr_repo" {
  type        = string
  description = "ECR repository name for Airflow runtime image"
  default     = "airflow-runtime"
}

variable "airflow_image_tag" {
  type        = string
  description = "Airflow image tag (Jenkins short SHA)"
  default     = "latest"
}

variable "airflow_dags_repo" {
  type        = string
  description = "Git repository URL for Airflow DAGs (GitSync)"
  default     = "https://github.com/Faissal-496/serverless-lakehouse-pipeline.git"
}

variable "airflow_dags_branch" {
  type        = string
  description = "Git branch for Airflow DAGs (GitSync)"
  default     = "main"
}

variable "airflow_fernet_key" {
  type        = string
  description = "Airflow Fernet key (shared across all nodes)"
  sensitive   = true
}

variable "airflow_webserver_secret_key" {
  type        = string
  description = "Airflow webserver secret key (shared across all nodes)"
  sensitive   = true
}

# ============================================================================
# S3 DATA LAKE CONFIGURATION
# ============================================================================

variable "s3_bucket_name" {
  type        = string
  description = "Name of S3 bucket for data lake (must be globally unique)"
  
  validation {
    condition     = can(regex("^[a-z0-9.-]{3,63}$", var.s3_bucket_name))
    error_message = "S3 bucket name must be 3-63 characters, lowercase letters, numbers, hyphens, and dots only."
  }
}

variable "s3_enable_versioning" {
  type        = bool
  description = "Enable S3 versioning for data protection"
  default     = true
}

variable "s3_enable_encryption" {
  type        = bool
  description = "Enable S3 server-side encryption (AES-256)"
  default     = true
}

variable "s3_kms_key_enabled" {
  type        = bool
  description = "Use KMS encryption instead of AES-256 (costs extra)"
  default     = false
}

variable "s3_lifecycle_days_to_ia" {
  type        = number
  description = "Days before transitioning objects to Intelligent-Tiering"
  default     = 30
}

variable "s3_lifecycle_days_to_glacier" {
  type        = number
  description = "Days before transitioning objects to Glacier (cold archive)"
  default     = 180
}

variable "s3_enable_access_logging" {
  type        = bool
  description = "Enable S3 access logging to separate bucket"
  default     = true
}

# ============================================================================
# RDS POSTGRESQL CONFIGURATION
# ============================================================================

variable "rds_instance_class" {
  type        = string
  description = "RDS instance type (db.t3.micro for dev, db.t3.medium+ for prod)"
  default     = "db.t3.micro"
  
  validation {
    condition     = can(regex("^db\\.(t[234]|m[567]|r[567]|c[567])\\.", var.rds_instance_class))
    error_message = "RDS instance class must be a valid type."
  }
}

variable "rds_allocated_storage" {
  type        = number
  description = "Initial allocated storage for RDS (GB)"
  default     = 20
  
  validation {
    condition     = var.rds_allocated_storage >= 20 && var.rds_allocated_storage <= 65536
    error_message = "RDS storage must be between 20 and 65536 GB."
  }
}

variable "rds_max_allocated_storage" {
  type        = number
  description = "Maximum auto-scaling storage limit for RDS (GB)"
  default     = 200
}

variable "rds_backup_retention_days" {
  type        = number
  description = "Number of days to retain RDS backups (7-35)"
  default     = 7
  
  validation {
    condition     = var.rds_backup_retention_days >= 7 && var.rds_backup_retention_days <= 35
    error_message = "RDS backup retention must be 7-35 days."
  }
}

variable "rds_multi_az" {
  type        = bool
  description = "Enable Multi-AZ deployment for high availability"
  default     = false
}

variable "rds_engine_version" {
  type        = string
  description = "PostgreSQL version"
  default     = "15.3"
}

variable "rds_database_name" {
  type        = string
  description = "Initial database name"
  default     = "lakehouse_prod"
}

variable "rds_master_username" {
  type        = string
  description = "RDS master username"
  default     = "lakehouse_admin"
  sensitive   = true
}

variable "rds_master_password" {
  type        = string
  description = "RDS master password (min 8 chars, must contain uppercase, lowercase, number, special char)"
  sensitive   = true
  
  validation {
    condition     = length(var.rds_master_password) >= 8
    error_message = "RDS password must be at least 8 characters."
  }
}

# ============================================================================
# CLOUDWATCH CONFIGURATION
# ============================================================================

variable "cloudwatch_log_retention_days" {
  type        = number
  description = "Number of days to retain CloudWatch logs"
  default     = 90
}

variable "cloudwatch_alarm_email" {
  type        = string
  description = "Email address for CloudWatch alarm notifications"
}

# ============================================================================
# GLUE CATALOG CONFIGURATION
# ============================================================================

variable "glue_catalog_database_name" {
  type        = string
  description = "AWS Glue Catalog database name"
  default     = "lakehouse"
}

# ============================================================================
# TAGS
# ============================================================================

variable "tags" {
  type        = map(string)
  description = "Common tags to apply to all resources"
  default = {
    Environment = "development"
    ManagedBy   = "Terraform"
    Project     = "lakehouse-assurance"
  }
}

variable "additional_tags" {
  type        = map(string)
  description = "Additional tags specific to this deployment"
  default     = {}
}

# ============================================================================
# ALB HTTPS / TLS
# ============================================================================

variable "alb_certificate_arn" {
  type        = string
  description = "ACM certificate ARN for ALB HTTPS listener"
}

variable "alb_ssl_policy" {
  type        = string
  description = "SSL policy for ALB HTTPS listener"
  default     = "ELBSecurityPolicy-2016-08"
}
