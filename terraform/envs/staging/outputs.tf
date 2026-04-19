output "alb_dns_name" {
  description = "ALB DNS name (point CNAME to this)"
  value       = module.alb.alb_dns_name
}

output "airflow_url" {
  description = "Airflow public URL"
  value       = "https://${var.airflow_domain}"
}

output "jenkins_url" {
  description = "Jenkins public URL"
  value       = "https://${var.jenkins_domain}"
}

output "ec2_instance_id" {
  description = "EC2 instance ID"
  value       = module.app_instance.instance_ids[0]
}

output "ec2_public_ip" {
  description = "EC2 public IP (SSH only; UIs are behind ALB)"
  value       = module.app_instance.public_ips[0]
}

output "s3_bucket_name" {
  description = "S3 bucket name"
  value       = module.s3_data_lake.bucket_name
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = module.rds_database.endpoint
  sensitive   = true
}
