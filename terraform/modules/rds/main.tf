# ============================================================================
# TERRAFORM MODULE: RDS POSTGRESQL DATABASE
# ============================================================================
#
# This module creates enterprise-grade PostgreSQL on AWS RDS with:
# - Automated backups with restoration capability
# - Enhanced monitoring and performance insights
# - Parameter groups for optimization
#

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

locals {
  engine_major_version = tonumber(regex("^([0-9]+)", var.engine_version)[0])
  parameter_family     = "postgres${local.engine_major_version}"
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.identifier}-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(
    var.tags,
    {
      Name = "${var.identifier}-subnet-group"
    }
  )
}

resource "aws_db_parameter_group" "this" {
  name   = "${var.identifier}-params"
  family = local.parameter_family

  dynamic "parameter" {
    for_each = var.force_ssl ? [1] : []
    content {
      name         = "rds.force_ssl"
      value        = "1"
      apply_method = "pending-reboot"
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.identifier}-params"
    }
  )
}

resource "aws_db_instance" "this" {
  identifier = var.identifier

  engine         = "postgres"
  engine_version = var.engine_version

  instance_class        = var.instance_class
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.database_name
  username = var.master_username
  password = var.master_password
  port     = 5432

  multi_az                = var.multi_az
  backup_retention_period = var.backup_retention_period
  copy_tags_to_snapshot   = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = var.vpc_security_group_ids

  parameter_group_name            = aws_db_parameter_group.this.name
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  publicly_accessible       = var.publicly_accessible
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.identifier}-final"

  auto_minor_version_upgrade = true
  apply_immediately          = false

  tags = merge(
    var.tags,
    {
      Name        = var.identifier
      Environment = var.environment
    }
  )
}
