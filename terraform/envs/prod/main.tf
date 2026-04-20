terraform {
  required_version = ">= 1.3"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      var.tags,
      var.additional_tags,
      {
        Environment = var.environment
        Project     = var.project_name
        Terraform   = "true"
      }
    )
  }
}

# ==========================================================================
# DATA SOURCES
# ==========================================================================

data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ==========================================================================
# LOCALS + GENERATED SECRETS (if not provided)
# ==========================================================================

locals {
  account_id  = data.aws_caller_identity.current.account_id
  environment = var.environment
  region      = var.aws_region
  project     = var.project_name

  name_prefix = "${local.project}-${local.environment}"

  common_tags = merge(
    var.tags,
    {
      Environment = local.environment
      Project     = local.project
      Region      = local.region
      Terraform   = "true"
    },
    var.additional_tags
  )

  airflow_base_url   = var.airflow_base_url != "" ? var.airflow_base_url : "https://${var.airflow_domain}"
  jenkins_public_url = var.jenkins_public_url != "" ? var.jenkins_public_url : "https://${var.jenkins_domain}/"

  rds_master_password = var.rds_master_password != "" ? var.rds_master_password : random_password.rds_master_password.result

  airflow_admin_password       = var.airflow_admin_password != "" ? var.airflow_admin_password : random_password.airflow_admin_password.result
  jenkins_admin_password       = var.jenkins_admin_password != "" ? var.jenkins_admin_password : random_password.jenkins_admin_password.result
  airflow_webserver_secret_key = var.airflow_webserver_secret_key != "" ? var.airflow_webserver_secret_key : random_password.airflow_webserver_secret_key.result
  airflow_fernet_key           = var.airflow_fernet_key != "" ? var.airflow_fernet_key : replace(replace(random_id.airflow_fernet.b64_std, "+", "-"), "/", "_")
}

resource "random_password" "rds_master_password" {
  length           = 32
  special          = true
  override_special = "!$&*+,-.;="
}

resource "random_password" "airflow_admin_password" {
  length           = 32
  special          = true
  override_special = "!$&*+,-.;="
}

resource "random_password" "jenkins_admin_password" {
  length           = 32
  special          = true
  override_special = "!$&*+,-.;="
}

resource "random_password" "airflow_webserver_secret_key" {
  length           = 64
  special          = true
  override_special = "!$&*+,-.;="
}

resource "random_id" "airflow_fernet" {
  byte_length = 32
}

# ==========================================================================
# NETWORKING + SECURITY
# ==========================================================================

module "networking" {
  source = "../../modules/networking"

  name_prefix          = local.name_prefix
  vpc_cidr             = var.vpc_cidr
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  availability_zones   = slice(data.aws_availability_zones.available.names, 0, 2)
  enable_nat_gateway   = var.enable_nat_gateway

  tags = local.common_tags
}

module "security" {
  source = "../../modules/security"

  name_prefix                 = local.name_prefix
  vpc_id                      = module.networking.vpc_id
  allowed_ingress_cidr_blocks = var.allowed_ingress_cidr_blocks
  ssh_cidr_blocks             = var.ssh_cidr_blocks

  tags = local.common_tags
}

# ==========================================================================
# S3 DATA LAKE
# ==========================================================================

module "s3_data_lake" {
  source = "../../modules/s3"

  bucket_name               = var.s3_bucket_name
  environment               = local.environment
  enable_versioning         = var.s3_enable_versioning
  enable_encryption         = var.s3_enable_encryption
  kms_key_enabled           = var.s3_kms_key_enabled
  enable_access_logging     = var.s3_enable_access_logging
  lifecycle_days_to_ia      = var.s3_lifecycle_days_to_ia
  lifecycle_days_to_glacier = var.s3_lifecycle_days_to_glacier
  account_id                = local.account_id

  tags = local.common_tags
}

# ==========================================================================
# RDS POSTGRESQL
# ==========================================================================

module "rds_database" {
  source = "../../modules/rds"

  identifier              = "${local.name_prefix}-postgres"
  instance_class          = var.rds_instance_class
  allocated_storage       = var.rds_allocated_storage
  max_allocated_storage   = var.rds_max_allocated_storage
  backup_retention_period = var.rds_backup_retention_days
  multi_az                = var.rds_multi_az
  engine_version          = var.rds_engine_version
  database_name           = var.rds_database_name
  master_username         = var.rds_master_username
  master_password         = local.rds_master_password
  force_ssl               = var.rds_force_ssl

  publicly_accessible = var.rds_publicly_accessible
  deletion_protection = var.rds_deletion_protection

  subnet_ids             = module.networking.private_subnet_ids
  vpc_security_group_ids = [module.security.rds_sg_id]

  environment = local.environment
  tags        = local.common_tags
}

# ==========================================================================
# IAM (EC2 Instance Profile)
# ==========================================================================

module "iam_roles" {
  source = "../../modules/iam"

  name_prefix   = local.name_prefix
  s3_bucket_arn = module.s3_data_lake.bucket_arn
  account_id    = local.account_id
  region        = local.region

  emr_serverless_application_id     = var.emr_serverless_application_id
  emr_serverless_execution_role_arn = var.emr_serverless_execution_role_arn

  tags = local.common_tags
}

# ==========================================================================
# SECRETS MANAGER (RDS + Airflow + Jenkins)
# ==========================================================================

module "secrets" {
  source = "../../modules/secrets"

  enable      = var.enable_secrets_manager
  name_prefix = "lakehouse/${local.environment}"

  rds_username = var.rds_master_username
  rds_password = local.rds_master_password
  rds_host     = module.rds_database.address
  rds_db_name  = var.rds_database_name

  airflow_fernet_key           = local.airflow_fernet_key
  airflow_webserver_secret_key = local.airflow_webserver_secret_key
  airflow_admin_user           = var.airflow_admin_user
  airflow_admin_password       = local.airflow_admin_password
  airflow_admin_email          = var.airflow_admin_email
  airflow_base_url             = local.airflow_base_url

  jenkins_admin_user     = var.jenkins_admin_user
  jenkins_admin_password = local.jenkins_admin_password
  jenkins_public_url     = local.jenkins_public_url
  host_repo_path         = var.host_repo_path

  tags = local.common_tags
}

# ==========================================================================
# EC2 (Docker Compose runtime)
# ==========================================================================

locals {
  app_user_data = templatefile(
    "${path.module}/../../user_data/compose_bootstrap.sh",
    {
      aws_region = var.aws_region

      repo_url       = var.repo_url
      repo_branch    = var.repo_branch
      host_repo_path = var.host_repo_path

      secrets_rds_arn     = var.enable_secrets_manager ? module.secrets.rds_secret_arn : ""
      secrets_airflow_arn = var.enable_secrets_manager ? module.secrets.airflow_secret_arn : ""
      secrets_jenkins_arn = var.enable_secrets_manager ? module.secrets.jenkins_secret_arn : ""

      s3_bucket_name = var.s3_bucket_name
      airflow_domain = var.airflow_domain
      jenkins_domain = var.jenkins_domain
      rds_force_ssl  = var.rds_force_ssl
    }
  )
}

module "app_instance" {
  source = "../../modules/compute"

  name           = "${local.name_prefix}-app"
  role_tag       = "lakehouse-app"
  instance_count = 1
  instance_type  = var.ec2_instance_type
  ami_id         = data.aws_ami.ubuntu.id

  subnet_ids           = module.networking.public_subnet_ids
  security_group_ids   = [module.security.app_sg_id]
  associate_public_ip  = true
  key_name             = var.ec2_key_name
  iam_instance_profile = module.iam_roles.instance_profile_name
  user_data            = local.app_user_data

  root_volume_size = var.ec2_root_volume_size

  tags = local.common_tags
}

# ==========================================================================
# ALB (host-based routing: airflow_domain + jenkins_domain)
# ==========================================================================

locals {
  alb_name_prefix = substr(replace(local.name_prefix, "_", "-"), 0, 20)
  tg_name_prefix  = substr(replace(local.name_prefix, "_", "-"), 0, 16)
}

module "alb" {
  source = "../../modules/alb"

  name               = "${local.alb_name_prefix}-alb"
  vpc_id             = module.networking.vpc_id
  subnet_ids         = module.networking.public_subnet_ids
  security_group_ids = [module.security.alb_sg_id]

  target_instance_ids = module.app_instance.instance_ids

  listener_port   = 80
  enable_https    = var.enable_https
  certificate_arn = var.alb_certificate_arn
  ssl_policy      = var.alb_ssl_policy

  target_groups = {
    airflow = {
      name              = "${local.tg_name_prefix}-airflow-tg"
      port              = 8080
      health_check_path = "/health"
      host_headers      = [var.airflow_domain]
      priority          = 10
    }
    jenkins = {
      name              = "${local.tg_name_prefix}-jenkins-tg"
      port              = 9080
      health_check_path = "/login"
      host_headers      = [var.jenkins_domain]
      priority          = 20
    }
  }

  tags = local.common_tags
}
