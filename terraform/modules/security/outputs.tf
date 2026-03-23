output "alb_sg_id" {
  description = "ALB security group ID"
  value       = aws_security_group.alb.id
}

output "airflow_sg_id" {
  description = "Airflow security group ID"
  value       = aws_security_group.airflow.id
}

output "jenkins_sg_id" {
  description = "Jenkins security group ID"
  value       = aws_security_group.jenkins.id
}

output "mq_sg_id" {
  description = "Amazon MQ security group ID"
  value       = aws_security_group.mq.id
}

output "rds_sg_id" {
  description = "RDS security group ID"
  value       = aws_security_group.rds.id
}

output "efs_sg_id" {
  description = "EFS security group ID"
  value       = aws_security_group.efs.id
}
