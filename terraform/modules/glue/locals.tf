# ============================================================================
# GLUE MODULE - LOCAL VALUES
# ============================================================================

locals {
  # Construct name prefix from variables
  name_prefix = var.environment != "" ? "${var.project}-${var.environment}" : var.project

  # Common tags for all resources
  common_tags = merge(
    var.tags,
    {
      ManagedBy   = "Terraform"
      Module      = "Glue"
    }
  )
}
