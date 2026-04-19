output "endpoint" {
  description = "RDS endpoint (host:port)"
  value       = aws_db_instance.this.endpoint
}

output "address" {
  description = "RDS hostname"
  value       = aws_db_instance.this.address
}

output "port" {
  description = "RDS port"
  value       = aws_db_instance.this.port
}

output "arn" {
  description = "RDS ARN"
  value       = aws_db_instance.this.arn
}

output "resource_id" {
  description = "RDS resource ID"
  value       = aws_db_instance.this.resource_id
}
