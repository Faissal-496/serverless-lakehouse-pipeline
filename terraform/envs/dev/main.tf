terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
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
        CreatedAt = timestamp()
      }
    )
  }
}

provider "random" {}

# ==========================================================================
# DATA SOURCES
# ==========================================================================

data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

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
# LOCALS
# ==========================================================================

locals {
  account_id  = data.aws_caller_identity.current.account_id
  region      = var.aws_region
  environment = var.environment
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
}

# ==========================================================================
# NETWORKING
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

# ==========================================================================
# SECURITY GROUPS
# ==========================================================================

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

  identifier             = "${local.name_prefix}-postgres"
  instance_class         = var.rds_instance_class
  allocated_storage      = var.rds_allocated_storage
  max_allocated_storage  = var.rds_max_allocated_storage
  backup_retention_period = var.rds_backup_retention_days
  multi_az               = var.rds_multi_az
  engine_version         = var.rds_engine_version
  database_name          = var.rds_database_name
  master_username        = var.rds_master_username
  master_password        = var.rds_master_password
  force_ssl              = var.rds_force_ssl

  subnet_ids            = module.networking.private_subnet_ids
  vpc_security_group_ids = [module.security.rds_sg_id]

  environment = local.environment
  tags        = local.common_tags
}

# ==========================================================================
# AMAZON MQ (RABBITMQ)
# ==========================================================================

module "rabbitmq" {
  source = "../../modules/mq"

  broker_name         = "${local.name_prefix}-rabbitmq"
  engine_version      = var.mq_engine_version
  instance_type       = var.mq_instance_type
  deployment_mode     = var.mq_deployment_mode
  publicly_accessible = false

  subnet_ids         = var.mq_deployment_mode == "ACTIVE_STANDBY_MULTI_AZ" ? module.networking.private_subnet_ids : [module.networking.private_subnet_ids[0]]
  security_group_ids = [module.security.mq_sg_id]

  username = var.mq_username
  password = var.mq_password

  tags = local.common_tags
}

# ==========================================================================
# CLOUDWATCH
# ==========================================================================

module "cloudwatch_logs" {
  source = "../../modules/cloudwatch"

  name_prefix              = local.name_prefix
  log_retention_days       = var.cloudwatch_log_retention_days
  alarm_notification_email = var.cloudwatch_alarm_email
  enable_dashboards        = var.cloudwatch_enable_dashboards
  aws_region               = var.aws_region
  rds_instance_identifier  = "${local.name_prefix}-postgres"

  tags = local.common_tags
}

# ==========================================================================
# IAM
# ==========================================================================

module "iam_roles" {
  source = "../../modules/iam"

  name_prefix     = local.name_prefix
  s3_bucket_arn   = module.s3_data_lake.bucket_arn
  rds_resource_id = module.rds_database.resource_id
  account_id      = local.account_id
  region          = local.region
  emr_serverless_application_id   = var.emr_serverless_application_id
  emr_serverless_execution_role_arn = var.emr_serverless_execution_role_arn

  tags = local.common_tags
}

module "iam_jenkins" {
  source = "../../modules/iam_jenkins"

  name_prefix = local.name_prefix
  tags        = local.common_tags
}

# ==========================================================================
# ECR
# ==========================================================================

module "ecr" {
  source = "../../modules/ecr"

  repository_names = var.ecr_repository_names
  scan_on_push     = true

  tags = local.common_tags
}

# ==========================================================================
# EFS (Jenkins)
# ==========================================================================

module "jenkins_efs" {
  source = "../../modules/efs"

  name_prefix        = "${local.name_prefix}-jenkins"
  subnet_ids         = module.networking.private_subnet_ids
  security_group_ids = [module.security.efs_sg_id]

  tags = local.common_tags
}

# ==========================================================================
# USER DATA (Airflow + Jenkins)
# ==========================================================================

locals {
  airflow_user_data_common = {
    aws_region                   = var.aws_region
    environment                  = var.environment
    airflow_ecr_repo             = var.airflow_ecr_repo
    airflow_image_tag            = var.airflow_image_tag
    airflow_dags_repo            = var.airflow_dags_repo
    airflow_dags_branch          = var.airflow_dags_branch
    rds_endpoint                 = module.rds_database.endpoint
    rds_db_name                  = var.rds_database_name
    rds_username                 = var.rds_master_username
    rds_password                 = var.rds_master_password
    rabbitmq_endpoint            = element(module.rabbitmq.endpoints, 0)
    rabbitmq_username            = var.mq_username
    rabbitmq_password            = var.mq_password
    airflow_fernet_key           = var.airflow_fernet_key
    airflow_webserver_secret_key = var.airflow_webserver_secret_key
    enable_secrets_manager       = var.enable_secrets_manager
    secrets_rds_arn              = module.secrets.rds_secret_arn
    secrets_mq_arn               = module.secrets.mq_secret_arn
    secrets_airflow_arn          = module.secrets.airflow_secret_arn
    s3_bucket_name               = var.s3_bucket_name
    rds_force_ssl                = var.rds_force_ssl
  }

  airflow_scheduler_user_data = templatefile(
    "${path.module}/../../user_data/airflow.sh",
    merge(
      local.airflow_user_data_common,
      {
        airflow_role          = "scheduler"
        airflow_enable_flower = "true"
      }
    )
  )

  airflow_worker_user_data = templatefile(
    "${path.module}/../../user_data/airflow.sh",
    merge(
      local.airflow_user_data_common,
      {
        airflow_role          = "worker"
        airflow_enable_flower = "false"
      }
    )
  )

  jenkins_casc_b64           = base64encode(file("${path.module}/../../../ci/jenkins/jenkins.yaml"))
  jenkins_plugins_b64        = base64encode(file("${path.module}/../../../ci/jenkins/plugins.txt"))
  jenkins_admin_user_b64     = base64encode(var.jenkins_admin_user)
  jenkins_admin_password_b64 = base64encode(var.jenkins_admin_password)
  jenkins_controller_user_data = templatefile(
    "${path.module}/../../user_data/jenkins_controller.sh",
    {
      efs_id                    = module.jenkins_efs.file_system_id
      jenkins_casc_b64          = local.jenkins_casc_b64
      jenkins_plugins_b64       = local.jenkins_plugins_b64
      jenkins_admin_user_b64    = local.jenkins_admin_user_b64
      jenkins_admin_password_b64 = local.jenkins_admin_password_b64
    }
  )
  jenkins_agent_user_data = file("${path.module}/../../user_data/jenkins_agent.sh")
}

# ==========================================================================
# COMPUTE: AIRFLOW + JENKINS
# ==========================================================================

module "airflow_schedulers" {
  source = "../../modules/compute"

  name           = "${local.name_prefix}-airflow-scheduler"
  role_tag       = "airflow-scheduler"
  instance_count = var.airflow_scheduler_count
  instance_type  = var.ec2_instance_type
  ami_id         = data.aws_ami.ubuntu.id

  subnet_ids          = module.networking.private_subnet_ids
  security_group_ids  = [module.security.airflow_sg_id]
  associate_public_ip = false
  key_name            = var.ec2_key_name
  iam_instance_profile = module.iam_roles.instance_profile_name
  user_data           = local.airflow_scheduler_user_data

  tags = local.common_tags
}

module "airflow_workers" {
  source = "../../modules/compute_asg"

  name              = "${local.name_prefix}-airflow-worker"
  role_tag          = "airflow-worker"
  instance_type     = var.ec2_instance_type
  ami_id            = data.aws_ami.ubuntu.id
  subnet_ids        = module.networking.private_subnet_ids
  security_group_ids = [module.security.airflow_sg_id]
  iam_instance_profile = module.iam_roles.instance_profile_name
  user_data         = local.airflow_worker_user_data

  desired_capacity  = var.airflow_worker_desired
  min_size          = var.airflow_worker_min
  max_size          = var.airflow_worker_max

  tags = local.common_tags
}

module "jenkins_controllers" {
  source = "../../modules/compute"

  name           = "${local.name_prefix}-jenkins-controller"
  role_tag       = "jenkins-controller"
  instance_count = var.jenkins_controller_count
  instance_type  = var.ec2_instance_type
  ami_id         = data.aws_ami.ubuntu.id

  subnet_ids          = module.networking.private_subnet_ids
  security_group_ids  = [module.security.jenkins_sg_id]
  associate_public_ip = false
  key_name            = var.ec2_key_name
  iam_instance_profile = module.iam_jenkins.instance_profile_name
  user_data           = local.jenkins_controller_user_data

  tags = local.common_tags
}

module "jenkins_agents" {
  source = "../../modules/compute"

  name           = "${local.name_prefix}-jenkins-agent"
  role_tag       = "jenkins-agent"
  instance_count = var.jenkins_agent_count
  instance_type  = var.ec2_instance_type
  ami_id         = data.aws_ami.ubuntu.id

  subnet_ids          = module.networking.private_subnet_ids
  security_group_ids  = [module.security.jenkins_sg_id]
  associate_public_ip = false
  key_name            = var.ec2_key_name
  iam_instance_profile = module.iam_jenkins.instance_profile_name
  user_data           = local.jenkins_agent_user_data

  tags = local.common_tags
}

# ==========================================================================
# ALB
# ==========================================================================

module "jenkins_alb" {
  source = "../../modules/alb"

  name                = "${substr(local.name_prefix, 0, 16)}-jenkins-alb"
  target_group_name   = "${substr(local.name_prefix, 0, 16)}-jenkins-tg"
  vpc_id              = module.networking.vpc_id
  subnet_ids          = module.networking.public_subnet_ids
  security_group_ids  = [module.security.alb_sg_id]
  target_instance_ids = module.jenkins_controllers.instance_ids
  target_port         = 8080
  listener_port       = 80
  health_check_path   = "/login"
  enable_https        = true
  certificate_arn     = var.alb_certificate_arn
  ssl_policy          = var.alb_ssl_policy

  tags = local.common_tags
}

module "airflow_alb" {
  source = "../../modules/alb"

  name                = "${substr(local.name_prefix, 0, 16)}-airflow-alb"
  target_group_name   = "${substr(local.name_prefix, 0, 16)}-airflow-tg"
  vpc_id              = module.networking.vpc_id
  subnet_ids          = module.networking.public_subnet_ids
  security_group_ids  = [module.security.alb_sg_id]
  target_instance_ids = module.airflow_schedulers.instance_ids
  target_port         = 8080
  listener_port       = 80
  health_check_path   = "/health"
  enable_https        = true
  certificate_arn     = var.alb_certificate_arn
  ssl_policy          = var.alb_ssl_policy

  tags = local.common_tags
}

# ==========================================================================
# GLUE CATALOG
# ==========================================================================

module "glue_catalog" {
  source = "../../modules/glue"

  database_name = var.glue_catalog_database_name
  description   = "Lakehouse metadata catalog for ${var.project_name}"

  tags = local.common_tags
}

# ==========================================================================
# SECRETS MANAGER (OPTIONAL)
# ==========================================================================

module "secrets" {
  source = "../../modules/secrets"

  enable                     = var.enable_secrets_manager
  name_prefix                = "lakehouse/${local.environment}"
  rds_username               = var.rds_master_username
  rds_password               = var.rds_master_password
  rds_host                   = module.rds_database.address
  rds_db_name                = var.rds_database_name
  mq_username                = var.mq_username
  mq_password                = var.mq_password
  mq_endpoint                = element(module.rabbitmq.endpoints, 0)
  airflow_fernet_key         = var.airflow_fernet_key
  airflow_webserver_secret_key = var.airflow_webserver_secret_key

  tags = local.common_tags
}
