output "broker_id" {
  description = "Broker ID"
  value       = aws_mq_broker.this.id
}

output "broker_arn" {
  description = "Broker ARN"
  value       = aws_mq_broker.this.arn
}

output "endpoints" {
  description = "Broker endpoints"
  value       = aws_mq_broker.this.instances[0].endpoints
}
