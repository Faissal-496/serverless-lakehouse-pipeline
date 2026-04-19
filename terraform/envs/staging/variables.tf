variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "eu-west-3"
}

variable "environment" {
  type        = string
  description = "Environment name"
  default     = "staging"
}

variable "project_name" {
  type        = string
  description = "Project name"
  default     = "serverless-lakehouse"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply"
  default     = {}
}

variable "additional_tags" {
  type        = map(string)
  description = "Additional tags to apply"
  default     = {}
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR"
  default     = "10.10.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public subnet CIDRs"
  default     = ["10.10.1.0/24", "10.10.2.0/24"]
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "Private subnet CIDRs (used for RDS)"
  default     = ["10.10.11.0/24", "10.10.12.0/24"]
}

variable "enable_nat_gateway" {
  type        = bool
  description = "Enable NAT gateway for private subnets"
  default     = false
}

variable "allowed_ingress_cidr_blocks" {
  type        = list(string)
  description = "CIDR blocks allowed to access public endpoints (ALB)"
  default     = ["0.0.0.0/0"]
}

variable "ssh_cidr_blocks" {
  type        = list(string)
  description = "CIDR blocks allowed to SSH to the EC2 instance (use /32)"
  default     = []
}

variable "ec2_instance_type" {
  type        = string
  description = "EC2 instance type"
  default     = "t3.large"
}

variable "ec2_key_name" {
  type        = string
  description = "EC2 key pair name (for SSH)"
  default     = ""
}

variable "ec2_root_volume_size" {
  type        = number
  description = "Root volume size (GB)"
  default     = 50
}

variable "repo_url" {
  type        = string
  description = "Git repository URL to clone on EC2"
  default     = "https://github.com/Faissal-496/serverless-lakehouse-pipeline.git"
}

variable "repo_branch" {
  type        = string
  description = "Git branch to checkout on EC2"
  default     = "migration_prod"
}

variable "host_repo_path" {
  type        = string
  description = "Host path where the repo will be cloned (also mounted into Jenkins agents)"
  default     = "/opt/serverless-lakehouse-pipeline"
}

variable "airflow_domain" {
  type        = string
  description = "Public hostname for Airflow (ALB host-based routing)"
  default     = "airflow-staging.octaa.tech"
}

variable "jenkins_domain" {
  type        = string
  description = "Public hostname for Jenkins (ALB host-based routing)"
  default     = "jenkins-staging.octaa.tech"
}

variable "enable_https" {
  type        = bool
  description = "Enable HTTPS listener on ALB and redirect HTTP->HTTPS"
  default     = true
}

variable "alb_certificate_arn" {
  type        = string
  description = "ACM certificate ARN for HTTPS listener (must cover airflow_domain + jenkins_domain)"
  default     = ""
}

variable "alb_ssl_policy" {
  type        = string
  description = "ALB SSL policy"
  default     = "ELBSecurityPolicy-2016-08"
}

variable "s3_bucket_name" {
  type        = string
  description = "S3 bucket name for the data lake"
}

variable "s3_enable_versioning" {
  type        = bool
  description = "Enable S3 versioning"
  default     = true
}

variable "s3_enable_encryption" {
  type        = bool
  description = "Enable S3 default encryption"
  default     = true
}

variable "s3_kms_key_enabled" {
  type        = bool
  description = "Use a customer-managed KMS key for S3 encryption"
  default     = false
}

variable "s3_enable_access_logging" {
  type        = bool
  description = "Enable S3 access logs bucket"
  default     = false
}

variable "s3_lifecycle_days_to_ia" {
  type        = number
  description = "Days before transitioning to Intelligent-Tiering"
  default     = 30
}

variable "s3_lifecycle_days_to_glacier" {
  type        = number
  description = "Days before transitioning to Glacier"
  default     = 180
}

variable "rds_instance_class" {
  type        = string
  description = "RDS instance class"
  default     = "db.t3.medium"
}

variable "rds_allocated_storage" {
  type        = number
  description = "RDS allocated storage (GB)"
  default     = 20
}

variable "rds_max_allocated_storage" {
  type        = number
  description = "RDS max allocated storage (GB)"
  default     = 200
}

variable "rds_backup_retention_days" {
  type        = number
  description = "RDS backup retention (days)"
  default     = 3
}

variable "rds_multi_az" {
  type        = bool
  description = "Enable Multi-AZ for RDS"
  default     = false
}

variable "rds_force_ssl" {
  type        = bool
  description = "Force SSL on RDS PostgreSQL"
  default     = true
}

variable "rds_engine_version" {
  type        = string
  description = "PostgreSQL engine version"
  default     = "15.3"
}

variable "rds_database_name" {
  type        = string
  description = "Database name"
  default     = "lakehouse_staging"
}

variable "rds_master_username" {
  type        = string
  description = "Master username"
  default     = "lakehouse_admin"
}

variable "rds_master_password" {
  type        = string
  description = "Master password (leave empty to auto-generate)"
  sensitive   = true
  default     = ""
}

variable "rds_publicly_accessible" {
  type        = bool
  description = "Whether the DB should have a public endpoint"
  default     = false
}

variable "rds_deletion_protection" {
  type        = bool
  description = "Enable deletion protection"
  default     = false
}

variable "enable_secrets_manager" {
  type        = bool
  description = "Store secrets in AWS Secrets Manager and let EC2 bootstrap fetch them"
  default     = true
}

variable "airflow_admin_user" {
  type        = string
  description = "Airflow admin user"
  default     = "admin"
}

variable "airflow_admin_password" {
  type        = string
  description = "Airflow admin password (leave empty to auto-generate)"
  sensitive   = true
  default     = ""
}

variable "airflow_admin_email" {
  type        = string
  description = "Airflow admin email"
  default     = "admin@example.com"
}

variable "airflow_fernet_key" {
  type        = string
  description = "Airflow Fernet key (leave empty to auto-generate)"
  sensitive   = true
  default     = ""
}

variable "airflow_webserver_secret_key" {
  type        = string
  description = "Airflow webserver secret key (leave empty to auto-generate)"
  sensitive   = true
  default     = ""
}

variable "airflow_base_url" {
  type        = string
  description = "Airflow public base URL (leave empty to derive from airflow_domain)"
  default     = ""
}

variable "jenkins_admin_user" {
  type        = string
  description = "Jenkins admin user"
  default     = "admin"
}

variable "jenkins_admin_password" {
  type        = string
  description = "Jenkins admin password (leave empty to auto-generate)"
  sensitive   = true
  default     = ""
}

variable "jenkins_public_url" {
  type        = string
  description = "Jenkins public URL (leave empty to derive from jenkins_domain)"
  default     = ""
}
