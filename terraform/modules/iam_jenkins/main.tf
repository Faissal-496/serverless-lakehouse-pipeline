# ============================================================================
# TERRAFORM MODULE: JENKINS IAM ROLE (INFRA)
# ============================================================================
# NOTE: Jenkins needs broad permissions to run Terraform apply.
# This module attaches AdministratorAccess by design.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_iam_role" "jenkins_infra" {
  name = "${var.name_prefix}-jenkins-infra-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "admin" {
  role       = aws_iam_role.jenkins_infra.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

resource "aws_iam_instance_profile" "jenkins_infra" {
  name = "${var.name_prefix}-jenkins-infra-profile"
  role = aws_iam_role.jenkins_infra.name
}

output "role_name" {
  value = aws_iam_role.jenkins_infra.name
}

output "role_arn" {
  value = aws_iam_role.jenkins_infra.arn
}

output "instance_profile_name" {
  value = aws_iam_instance_profile.jenkins_infra.name
}

output "instance_profile_arn" {
  value = aws_iam_instance_profile.jenkins_infra.arn
}
