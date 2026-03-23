# ============================================================================
# TERRAFORM MODULE: SECRETS MANAGER (OPTIONAL)
# ============================================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_secretsmanager_secret" "rds" {
  count = var.enable ? 1 : 0

  name        = "${var.name_prefix}/rds"
  description = "RDS credentials"

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "rds" {
  count = var.enable ? 1 : 0

  secret_id = aws_secretsmanager_secret.rds[0].id
  secret_string = jsonencode({
    username = var.rds_username
    password = var.rds_password
    host     = var.rds_host
    port     = var.rds_port
    dbname   = var.rds_db_name
  })
}

resource "aws_secretsmanager_secret" "mq" {
  count = var.enable ? 1 : 0

  name        = "${var.name_prefix}/mq"
  description = "RabbitMQ credentials"

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "mq" {
  count = var.enable ? 1 : 0

  secret_id = aws_secretsmanager_secret.mq[0].id
  secret_string = jsonencode({
    username = var.mq_username
    password = var.mq_password
    endpoint = var.mq_endpoint
  })
}

resource "aws_secretsmanager_secret" "airflow" {
  count = var.enable ? 1 : 0

  name        = "${var.name_prefix}/airflow"
  description = "Airflow keys"

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "airflow" {
  count = var.enable ? 1 : 0

  secret_id = aws_secretsmanager_secret.airflow[0].id
  secret_string = jsonencode({
    fernet_key        = var.airflow_fernet_key
    webserver_secret = var.airflow_webserver_secret_key
  })
}

output "rds_secret_arn" {
  value       = var.enable ? aws_secretsmanager_secret.rds[0].arn : null
  description = "RDS secret ARN"
}

output "mq_secret_arn" {
  value       = var.enable ? aws_secretsmanager_secret.mq[0].arn : null
  description = "MQ secret ARN"
}

output "airflow_secret_arn" {
  value       = var.enable ? aws_secretsmanager_secret.airflow[0].arn : null
  description = "Airflow secret ARN"
}
