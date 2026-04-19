# ============================================================================
# TERRAFORM MODULE: APPLICATION LOAD BALANCER
# ============================================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_lb" "this" {
  name               = var.name
  internal           = var.internal
  load_balancer_type = "application"
  security_groups    = var.security_group_ids
  subnets            = var.subnet_ids

  tags = var.tags
}

resource "aws_lb_target_group" "this" {
  for_each = var.target_groups

  name        = each.value.name
  port        = each.value.port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "instance"

  health_check {
    enabled             = true
    interval            = 30
    path                = each.value.health_check_path
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200-399"
  }

  tags = var.tags
}

# HTTP listener: forward when no HTTPS, redirect 301 when HTTPS enabled
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = var.listener_port
  protocol          = "HTTP"

  default_action {
    type = var.enable_https ? "redirect" : "fixed-response"

    # Forward to fixed response if HTTPS is disabled (listener rules handle host routing)
    dynamic "fixed_response" {
      for_each = var.enable_https ? [] : [1]
      content {
        content_type = "text/plain"
        message_body = "Not Found"
        status_code  = "404"
      }
    }

    # Redirect HTTP -> HTTPS (when HTTPS IS enabled)
    dynamic "redirect" {
      for_each = var.enable_https ? [1] : []
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }
}

# HTTPS listener (only when enabled)
resource "aws_lb_listener" "https" {
  count             = var.enable_https ? 1 : 0
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = var.ssl_policy
  certificate_arn   = var.certificate_arn

  default_action {
    type = "fixed-response"

    fixed_response {
      content_type = "text/plain"
      message_body = "Not Found"
      status_code  = "404"
    }
  }

  lifecycle {
    precondition {
      condition     = !var.enable_https || var.certificate_arn != ""
      error_message = "When enable_https is true, certificate_arn must be set."
    }
  }
}

locals {
  forward_listener_arn = var.enable_https ? aws_lb_listener.https[0].arn : aws_lb_listener.http.arn

  attachments = {
    for item in flatten([
      for tg_key, tg in var.target_groups : [
        for instance_id in var.target_instance_ids : {
          key         = "${tg_key}-${instance_id}"
          tg_key      = tg_key
          instance_id = instance_id
          port        = tg.port
        }
      ]
    ]) : item.key => item
  }
}

resource "aws_lb_target_group_attachment" "targets" {
  for_each = local.attachments

  target_group_arn = aws_lb_target_group.this[each.value.tg_key].arn
  target_id        = each.value.instance_id
  port             = each.value.port
}

resource "aws_lb_listener_rule" "host_routes" {
  for_each = var.target_groups

  listener_arn = local.forward_listener_arn
  priority     = each.value.priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this[each.key].arn
  }

  condition {
    host_header {
      values = each.value.host_headers
    }
  }
}
