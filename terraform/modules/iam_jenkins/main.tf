# ============================================================================
# TERRAFORM MODULE: JENKINS IAM ROLE (INFRA)
# ============================================================================
# Jenkins needs permissions to: manage Terraform state (S3 + DynamoDB),
# push to ECR, manage EC2/EFS/RDS/MQ resources, and read Secrets Manager.
# This scoped policy replaces the previous AdministratorAccess.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

data "aws_caller_identity" "current" {}

resource "aws_iam_role" "jenkins_infra" {
  name = "${var.name_prefix}-jenkins-infra-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "jenkins_infra" {
  name = "${var.name_prefix}-jenkins-infra-policy"
  role = aws_iam_role.jenkins_infra.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Terraform state management (S3 + DynamoDB)
      {
        Sid    = "TerraformState"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ]
        Resource = [
          "arn:aws:s3:::${var.terraform_state_bucket}",
          "arn:aws:s3:::${var.terraform_state_bucket}/*",
        ]
      },
      {
        Sid    = "TerraformLock"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem",
        ]
        Resource = "arn:aws:dynamodb:*:${data.aws_caller_identity.current.account_id}:table/${var.terraform_lock_table}"
      },
      # ECR push / pull
      {
        Sid    = "ECR"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:CreateRepository",
          "ecr:DescribeRepositories",
          "ecr:ListImages",
        ]
        Resource = "*"
      },
      # Infrastructure provisioning (EC2, VPC, ELB, RDS, MQ, EFS, etc.)
      {
        Sid    = "InfraProvisioning"
        Effect = "Allow"
        Action = [
          "ec2:*",
          "elasticloadbalancing:*",
          "rds:*",
          "mq:*",
          "efs:*",
          "s3:*",
          "glue:*",
          "secretsmanager:*",
          "logs:*",
          "cloudwatch:*",
          "sns:*",
          "emr-serverless:*",
        ]
        Resource = "*"
      },
      # IAM role/policy management (scoped to the project prefix)
      {
        Sid    = "IAMScoped"
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:GetRole",
          "iam:PassRole",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:GetRolePolicy",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:CreateInstanceProfile",
          "iam:DeleteInstanceProfile",
          "iam:GetInstanceProfile",
          "iam:AddRoleToInstanceProfile",
          "iam:RemoveRoleFromInstanceProfile",
          "iam:ListInstanceProfilesForRole",
          "iam:TagRole",
          "iam:UntagRole",
        ]
        Resource = [
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.name_prefix}-*",
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:instance-profile/${var.name_prefix}-*",
        ]
      },
      # STS for caller identity (used by Terraform)
      {
        Sid      = "STS"
        Effect   = "Allow"
        Action   = ["sts:GetCallerIdentity"]
        Resource = "*"
      },
    ]
  })
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
