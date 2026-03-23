output "s3_bucket_name" {
  value       = module.s3_data_lake.bucket_name
  description = "S3 data lake bucket name"
}

output "rds_endpoint" {
  value       = module.rds_database.endpoint
  description = "RDS endpoint"
  sensitive   = true
}

output "rabbitmq_endpoints" {
  value       = module.rabbitmq.endpoints
  description = "Amazon MQ endpoints"
}

output "jenkins_alb_dns_name" {
  value       = module.jenkins_alb.alb_dns_name
  description = "Jenkins ALB DNS name"
}

output "airflow_alb_dns_name" {
  value       = module.airflow_alb.alb_dns_name
  description = "Airflow ALB DNS name"
}

output "ecr_repository_urls" {
  value       = module.ecr.repository_urls
  description = "ECR repository URLs"
}

output "airflow_scheduler_private_ips" {
  value       = module.airflow_schedulers.private_ips
  description = "Airflow scheduler private IPs"
}

output "airflow_worker_asg_name" {
  value       = module.airflow_workers.asg_name
  description = "Airflow worker ASG name"
}

output "secrets_rds_arn" {
  value       = module.secrets.rds_secret_arn
  description = "RDS secret ARN"
}

output "secrets_mq_arn" {
  value       = module.secrets.mq_secret_arn
  description = "MQ secret ARN"
}

output "secrets_airflow_arn" {
  value       = module.secrets.airflow_secret_arn
  description = "Airflow secret ARN"
}
