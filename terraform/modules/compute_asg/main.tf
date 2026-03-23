# ============================================================================
# TERRAFORM MODULE: EC2 AUTOSCALING GROUP
# ============================================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_launch_template" "this" {
  name_prefix   = "${var.name}-lt-"
  image_id      = var.ami_id
  instance_type = var.instance_type

  vpc_security_group_ids = var.security_group_ids

  user_data = var.user_data != "" ? base64encode(var.user_data) : null

  iam_instance_profile {
    name = var.iam_instance_profile != "" ? var.iam_instance_profile : null
  }

  block_device_mappings {
    device_name = "/dev/sda1"

    ebs {
      volume_size = var.root_volume_size
      volume_type = var.root_volume_type
    }
  }

  tag_specifications {
    resource_type = "instance"

    tags = merge(
      var.tags,
      {
        Name = var.name
        Role = var.role_tag
      }
    )
  }

  tags = var.tags
}

resource "aws_autoscaling_group" "this" {
  name                = "${var.name}-asg"
  desired_capacity    = var.desired_capacity
  min_size            = var.min_size
  max_size            = var.max_size
  vpc_zone_identifier = var.subnet_ids

  launch_template {
    id      = aws_launch_template.this.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = var.name
    propagate_at_launch = true
  }

  tag {
    key                 = "Role"
    value               = var.role_tag
    propagate_at_launch = true
  }

  dynamic "tag" {
    for_each = var.tags
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }
}

output "asg_name" {
  value = aws_autoscaling_group.this.name
}

output "launch_template_id" {
  value = aws_launch_template.this.id
}
