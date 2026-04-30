# ============================================================================
# GLUE CATALOG MODULE — OUTPUTS
# ============================================================================

output "bronze_database_name" {
  description = "Glue Catalog database name for Bronze layer"
  value       = aws_glue_catalog_database.bronze.name
}

output "silver_database_name" {
  description = "Glue Catalog database name for Silver layer"
  value       = aws_glue_catalog_database.silver.name
}

output "gold_database_name" {
  description = "Glue Catalog database name for Gold layer"
  value       = aws_glue_catalog_database.gold.name
}

output "bronze_crawler_name" {
  description = "Glue Crawler name for Bronze layer"
  value       = aws_glue_crawler.bronze.name
}

output "silver_crawler_name" {
  description = "Glue Crawler name for Silver layer"
  value       = aws_glue_crawler.silver.name
}

output "gold_crawler_name" {
  description = "Glue Crawler name for Gold layer"
  value       = aws_glue_crawler.gold.name
}

output "crawler_role_arn" {
  description = "ARN of the IAM role used by Glue Crawlers"
  value       = aws_iam_role.glue_crawler.arn
}

output "athena_workgroup_name" {
  description = "Athena Workgroup name for Lakehouse queries"
  value       = aws_athena_workgroup.lakehouse.name
}

output "athena_results_s3_path" {
  description = "S3 path where Athena query results are stored"
  value       = "s3://${var.s3_bucket_name}/athena/results/"
}

output "athena_glue_policy_arn" {
  description = "ARN of the IAM policy granting Athena+Glue access to EC2 role"
  value       = aws_iam_policy.athena_glue_access.arn
}
