output "instance_ids" {
  description = "Instance IDs"
  value       = aws_instance.this[*].id
}

output "private_ips" {
  description = "Private IPs"
  value       = aws_instance.this[*].private_ip
}

output "public_ips" {
  description = "Public IPs"
  value       = aws_instance.this[*].public_ip
}
