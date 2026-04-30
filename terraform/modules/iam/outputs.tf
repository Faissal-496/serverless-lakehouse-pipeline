# ============================================================================
# IAM MODULE — OUTPUTS
# ============================================================================

output "role_arn" {
  description = "ARN of the Lakehouse ETL IAM role"
  value       = aws_iam_role.lakehouse_etl.arn
}

output "role_name" {
  description = "Name of the Lakehouse ETL IAM role"
  value       = aws_iam_role.lakehouse_etl.name
}

output "instance_profile_name" {
  description = "Name of the EC2 instance profile"
  value       = aws_iam_instance_profile.lakehouse_etl.name
}

output "instance_profile_arn" {
  description = "ARN of the EC2 instance profile"
  value       = aws_iam_instance_profile.lakehouse_etl.arn
}

output "instance_profile_role_name" {
  description = "Name of the IAM role attached to the EC2 instance profile (used by Glue Catalog module)"
  value       = aws_iam_role.lakehouse_etl.name
}
