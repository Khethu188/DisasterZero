
# ─────────────────────────────────────────────────────────────
# terraform/modules/monitoring/main.tf
# CloudWatch Alarms, SNS Topics, Dashboard
# ─────────────────────────────────────────────────────────────

variable "environment" { type = string }
variable "project" { type = string }
variable "alert_email" { type = string }
variable "ec2_instance_id" { type = string }
variable "s3_bucket_name" { type = string }
variable "lambda_function_name" { type = string }

locals {
  name_prefix = "${var.project}-${var.environment}"
}

# ═══════════════════════════════════════════════════════════════
# SNS: Alert Topic
# ═══════════════════════════════════════════════════════════════

resource "aws_sns_topic" "alerts" {
  name = "${local.name_prefix}-alerts"

  tags = {
    Name    = "${local.name_prefix}-alerts"
    Purpose = "DisasterZero alarm notifications"
  }
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Connect SNS to Lambda for auto-recovery
resource "aws_sns_topic_subscription" "lambda_recovery" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "lambda"
  endpoint  = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${var.lambda_function_name}"
}

resource "aws_lambda_permission" "sns_invoke" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.alerts.arn
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# ═══════════════════════════════════════════════════════════════
# CloudWatch Alarms
# ═══════════════════════════════════════════════════════════════

# ── EC2 Instance Status Check ──
resource "aws_cloudwatch_metric_alarm" "ec2_status" {
  alarm_name          = "${local.name_prefix}-ec2-status-check"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "EC2 instance status check failed — triggers auto-recovery"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = {
    InstanceId = var.ec2_instance_id
  }

  tags = { Name = "${local.name_prefix}-ec2-status" }
}

# ── EC2 CPU Utilization (anomaly detection) ──
resource "aws_cloudwatch_metric_alarm" "ec2_cpu" {
  alarm_name          = "${local.name_prefix}-ec2-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 90
  alarm_description   = "EC2 CPU above 90% for 15 minutes"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    InstanceId = var.ec2_instance_id
  }

  tags = { Name = "${local.name_prefix}-ec2-cpu" }
}

# ── S3 Bucket Errors ──
resource "aws_cloudwatch_metric_alarm" "s3_errors" {
  alarm_name          = "${local.name_prefix}-s3-access-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "4xxErrors"
  namespace           = "AWS/S3"
  period              = 300
  statistic           = "Sum"
  threshold           = 50
  alarm_description   = "S3 bucket experiencing high 4xx error rate — possible access denial"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    BucketName = var.s3_bucket_name
    FilterId   = "AllMetrics"
  }

  tags = { Name = "${local.name_prefix}-s3-errors" }
}

# ── Lambda Recovery Errors ──
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.name_prefix}-lambda-recovery-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Recovery Lambda function errors detected"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  tags = { Name = "${local.name_prefix}-lambda-errors" }
}

# ── Lambda Duration (recovery taking too long) ──
resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "${local.name_prefix}-lambda-recovery-slow"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Maximum"
  threshold           = 240000  # 4 minutes (out of 5 min timeout)
  alarm_description   = "Recovery Lambda approaching timeout — recovery may be failing"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  tags = { Name = "${local.name_prefix}-lambda-slow" }
}

# ═══════════════════════════════════════════════════════════════
# CloudWatch Dashboard
# ═══════════════════════════════════════════════════════════════

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.name_prefix}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 1
        properties = {
          markdown = "# 🛡️ DisasterZero — Infrastructure Health"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 1
        width  = 8
        height = 6
        properties = {
          title   = "EC2 Instance CPU"
          metrics = [
            ["AWS/EC2", "CPUUtilization", "InstanceId", var.ec2_instance_id]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 1
        width  = 8
        height = 6
        properties = {
          title   = "EC2 Status Checks"
          metrics = [
            ["AWS/EC2", "StatusCheckFailed", "InstanceId", var.ec2_instance_id],
            ["AWS/EC2", "StatusCheckFailed_Instance", "InstanceId", var.ec2_instance_id],
            ["AWS/EC2", "StatusCheckFailed_System", "InstanceId", var.ec2_instance_id]
          ]
          period = 60
          stat   = "Maximum"
          region = data.aws_region.current.name
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 1
        width  = 8
        height = 6
        properties = {
          title   = "S3 Request Errors"
          metrics = [
            ["AWS/S3", "4xxErrors", "BucketName", var.s3_bucket_name, "FilterId", "AllMetrics"],
            ["AWS/S3", "5xxErrors", "BucketName", var.s3_bucket_name, "FilterId", "AllMetrics"]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.name
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 7
        width  = 12
        height = 6
        properties = {
          title   = "Recovery Lambda — Invocations & Errors"
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.lambda_function_name],
            ["AWS/Lambda", "Errors", "FunctionName", var.lambda_function_name],
            ["AWS/Lambda", "Throttles", "FunctionName", var.lambda_function_name]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.name
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 7
        width  = 12
        height = 6
        properties = {
          title   = "Recovery Lambda — Duration"
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", var.lambda_function_name]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          view   = "timeSeries"
        }
      },
      {
        type   = "alarm"
        x      = 0
        y      = 13
        width  = 24
        height = 3
        properties = {
          title  = "Active Alarms"
          alarms = [
            aws_cloudwatch_metric_alarm.ec2_status.arn,
            aws_cloudwatch_metric_alarm.ec2_cpu.arn,
            aws_cloudwatch_metric_alarm.s3_errors.arn,
            aws_cloudwatch_metric_alarm.lambda_errors.arn,
            aws_cloudwatch_metric_alarm.lambda_duration.arn,
          ]
        }
      }
    ]
  })
}

# ── Outputs ──

output "sns_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "dashboard_url" {
  value = "https://${data.aws_region.current.name}.console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.name}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

