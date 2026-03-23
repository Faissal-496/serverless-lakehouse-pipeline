# ============================================================================
# TERRAFORM MODULE: AMAZON MQ (RabbitMQ)
# ============================================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_mq_broker" "this" {
  broker_name         = var.broker_name
  engine_type         = "RabbitMQ"
  engine_version      = var.engine_version
  host_instance_type  = var.instance_type
  deployment_mode     = "SINGLE_INSTANCE"
  publicly_accessible = var.publicly_accessible
  auto_minor_version_upgrade = true

  subnet_ids     = length(var.subnet_ids) > 1 ? [var.subnet_ids[0]] : var.subnet_ids
  security_groups = var.security_group_ids

  user {
    username = var.username
    password = var.password
  }

  tags = var.tags
}
