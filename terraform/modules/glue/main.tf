# ============================================================================
# TERRAFORM MODULE: AWS GLUE CATALOG
# ============================================================================
# 
# Centralized metadata store for data discovery and governance
#

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ============================================================================
# GLUE DATABASE
# ============================================================================

resource "aws_glue_catalog_database" "lakehouse" {
  name        = var.database_name
  description = var.description
  
  catalog_id = data.aws_caller_identity.current.account_id
}

# ============================================================================
# DATA SOURCE (Current Account)
# ============================================================================

data "aws_caller_identity" "current" {}

# ============================================================================
# OUTPUTS
# ============================================================================

output "database_name" {
  value = aws_glue_catalog_database.lakehouse.name
}

output "database_arn" {
  value = "arn:aws:glue:${data.aws_caller_identity.current.account_id}:catalog:database/${aws_glue_catalog_database.lakehouse.name}"
}
