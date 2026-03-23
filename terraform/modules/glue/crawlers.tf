# ============================================================================
# AWS GLUE CRAWLERS - DISABLED FOR AWS FREE TIER COST OPTIMIZATION
# ============================================================================
#
# ⚠️  Crawlers have been disabled to reduce costs
#
# COST ANALYSIS:
# - Each crawler execution: $0.40 per DPU-hour
# - Typical cost: $5-20/month for daily crawls
# - Free tier credit: Only $68 - must be preserved!
#
# ALTERNATIVE APPROACH:
# Use explicit schema management via:
# 1. src/lakehouse/ingestion/schema_registry.py (PySpark StructType)
# 2. config/datasets/*.yaml (metadata)
# 3. Manual SQL DDL if needed
#
# RE-ENABLE CRAWLERS:
# If you need crawlers later for production, uncomment the resources below.
#
# ============================================================================

# ❌ All Glue Crawler resources DISABLED to save costs
# See git history or comments below for original definitions

locals {
  # Crawler feature flag - set to true to enable crawlers in production
  enable_glue_crawlers = false
}

# ============================================================================
# Output for information only (no crawlers deployed)
# ============================================================================

output "glue_database_name" {
  description = "Glue Catalog database name"
  value       = aws_glue_catalog_database.lakehouse.name
}

output "crawlers_enabled" {
  description = "Whether Glue Crawlers are enabled (cost optimization)"
  value       = local.enable_glue_crawlers
}

output "crawler_cost_note" {
  description = "Cost information about Glue Crawlers"
  value       = "Crawlers disabled in dev/test. Cost: $0.40/DPU-hour if re-enabled."
}

