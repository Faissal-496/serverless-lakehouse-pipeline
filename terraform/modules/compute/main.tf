# ============================================================================
# TERRAFORM MODULE: EC2 COMPUTE CLUSTER
# ============================================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_instance" "this" {
  count                       = var.instance_count
  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = element(var.subnet_ids, count.index % length(var.subnet_ids))
  vpc_security_group_ids      = var.security_group_ids
  associate_public_ip_address = var.associate_public_ip
  key_name                    = var.key_name != "" ? var.key_name : null
  iam_instance_profile        = var.iam_instance_profile != "" ? var.iam_instance_profile : null
  user_data                   = var.user_data != "" ? var.user_data : null

  root_block_device {
    volume_size = var.root_volume_size
    volume_type = var.root_volume_type
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.name}-${count.index + 1}"
      Role = var.role_tag
    }
  )
}
