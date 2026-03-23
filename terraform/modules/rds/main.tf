# ============================================================================
# TERRAFORM MODULE: RDS POSTGRESQL DATABASE
# ============================================================================
# 
# This module creates enterprise-grade PostgreSQL on AWS RDS with:
# - Multi-AZ for high availability
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
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

# ============================================================================
# LOCAL VALUES
# ============================================================================

locals {
  postgres_major_version = split(".", var.engine_version)[0]
  parameter_family       = "postgres${local.postgres_major_version}"
}

# ============================================================================
# DB SUBNET GROUP
# ============================================================================

resource "aws_db_subnet_group" "lakehouse" {
  name       = "${var.identifier}-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(
    var.tags,
    {
      Name = "${var.identifier}-subnet-group"
    }
  )
}

# ============================================================================
# RDS DB INSTANCE
# ============================================================================

resource "aws_db_instance" "lakehouse" {
  identifier     = var.identifier
  engine         = "postgres"
  engine_version = var.engine_version
  
  instance_class            = var.instance_class
  allocated_storage          = var.allocated_storage
  max_allocated_storage      = var.max_allocated_storage
  storage_encrypted          = true
  
  # Database Configuration
  db_name  = var.database_name
  username = var.master_username
  password = var.master_password
  
  # Backup Configuration
  backup_retention_period = var.backup_retention_period
  backup_window          = "03:00-04:00"  # UTC, off-peak
  copy_tags_to_snapshot  = true
  
  # High Availability
  multi_az = var.multi_az
  
  # Monitoring
  enabled_cloudwatch_logs_exports = ["postgresql"]
  monitoring_interval              = 60  # Detailed monitoring
  monitoring_role_arn              = aws_iam_role.rds_monitoring.arn
  
  # Maintenance
  maintenance_window       = "sun:04:00-sun:05:00"
  auto_minor_version_upgrade = true
  
  # Security
  publicly_accessible = false  # Do NOT expose to public internet
  vpc_security_group_ids = var.vpc_security_group_ids
  db_subnet_group_name   = aws_db_subnet_group.lakehouse.name
  skip_final_snapshot = false
  final_snapshot_identifier = "${var.identifier}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  
  # Parameters
  parameter_group_name = aws_db_parameter_group.lakehouse.name
  
  # Deletion Protection
  deletion_protection = var.environment == "prod" ? true : false
  
  tags = merge(
    var.tags,
    {
      Name = var.identifier
    }
  )
  
  depends_on = [aws_iam_role_policy.rds_monitoring]
}

# ============================================================================
# RDS PARAMETER GROUP (Optimization)
# ============================================================================

resource "aws_db_parameter_group" "lakehouse" {
  family      = local.parameter_family
  name        = "${var.identifier}-params"
  description = "Parameter group for ${var.identifier}"
  
  # Performance Tuning Parameters
  parameter {
    name  = "log_statement"
    value = var.environment == "prod" ? "ddl" : "all"  # Log more in dev
    apply_method = "immediate"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # Log queries > 1 second
    apply_method = "immediate"
  }

  tags = var.tags
}

# ============================================================================
# IAM ROLE FOR RDS MONITORING
# ============================================================================

resource "aws_iam_role" "rds_monitoring" {
  name = "${var.identifier}-monitoring-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
  
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

resource "aws_iam_role_policy" "rds_monitoring" {
  name = "${var.identifier}-monitoring-policy"
  role = aws_iam_role.rds_monitoring.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# ============================================================================
# OUTPUTS
# ============================================================================

output "endpoint" {
  value       = aws_db_instance.lakehouse.endpoint
  description = "RDS endpoint (host:port)"
  sensitive   = true
}

output "address" {
  value       = aws_db_instance.lakehouse.address
  description = "RDS host address"
  sensitive   = true
}

output "port" {
  value       = aws_db_instance.lakehouse.port
  description = "RDS port"
}

output "database_name" {
  value       = aws_db_instance.lakehouse.db_name
  description = "Database name"
}

output "resource_id" {
  value       = aws_db_instance.lakehouse.resource_id
  description = "RDS resource ID"
}

output "arn" {
  value       = aws_db_instance.lakehouse.arn
  description = "RDS instance ARN"
}
