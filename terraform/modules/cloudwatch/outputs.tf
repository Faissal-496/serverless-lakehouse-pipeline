output "sns_topic_arn" {
  description = "SNS topic ARN for alerts"
  value       = aws_sns_topic.alerts.arn
}

output "dashboard_arn" {
  description = "CloudWatch dashboard ARN"
  value       = aws_cloudwatch_dashboard.main.dashboard_arn
}

output "log_group_arns" {
  description = "Map of log group name to ARN"
  value       = { for name, lg in aws_cloudwatch_log_group.logs : name => lg.arn }
}
