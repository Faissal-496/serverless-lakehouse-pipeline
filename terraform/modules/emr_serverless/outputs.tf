output "application_id" {
  description = "EMR Serverless application ID"
  value       = aws_emrserverless_application.lakehouse.id
}

output "application_arn" {
  description = "EMR Serverless application ARN"
  value       = aws_emrserverless_application.lakehouse.arn
}

output "execution_role_arn" {
  description = "IAM role ARN for EMR job execution"
  value       = aws_iam_role.emr_execution.arn
}
