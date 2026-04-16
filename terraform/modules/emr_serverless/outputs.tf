output "application_id" {
  value       = aws_emrserverless_application.spark.id
  description = "EMR Serverless application ID"
}

output "application_arn" {
  value       = aws_emrserverless_application.spark.arn
  description = "EMR Serverless application ARN"
}

output "execution_role_arn" {
  value       = aws_iam_role.emr_execution.arn
  description = "ARN of the EMR execution role"
}

output "execution_role_name" {
  value       = aws_iam_role.emr_execution.name
  description = "Name of the EMR execution role"
}
