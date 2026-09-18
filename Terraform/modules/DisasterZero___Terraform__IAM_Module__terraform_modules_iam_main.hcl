
# ─────────────────────────────────────────────────────────────
# terraform/modules/iam/main.tf
# Cross-service IAM roles and policies
# ─────────────────────────────────────────────────────────────

variable "environment" { type = string }
variable "project" { type = string }
variable "account_id" { type = string }
variable "aws_region" { type = string }
variable "s3_bucket_arn" { type = string }
variable "s3_bucket_name" { type = string }

locals {
  name_prefix = "${var.project}-${var.environment}"
}

# ═══════════════════════════════════════════════════════════════
# Databricks Cross-Account Role
# ═══════════════════════════════════════════════════════════════
# Allows Databricks to access S3 data bucket for the pipeline.

resource "aws_iam_role" "databricks_s3_access" {
  name = "${local.name_prefix}-databricks-s3-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        AWS = "arn:aws:iam::414351767826:root"  # Databricks AWS account
      }
      Action = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "sts:ExternalId" = var.account_id
        }
      }
    }]
  })

  tags = {
    Name    = "${local.name_prefix}-databricks-s3"
    Purpose = "Databricks cross-account S3 access"
  }
}

resource "aws_iam_role_policy" "databricks_s3_access" {
  name = "${local.name_prefix}-databricks-s3-policy"
  role = aws_iam_role.databricks_s3_access.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ListBucket"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation",
        ]
        Resource = var.s3_bucket_arn
      },
      {
        Sid    = "ReadWriteObjects"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:GetObjectVersion",
        ]
        Resource = "${var.s3_bucket_arn}/*"
      },
    ]
  })
}

# ═══════════════════════════════════════════════════════════════
# DisasterZero Orchestrator Role
# ═══════════════════════════════════════════════════════════════
# Used by the orchestrator to inject failures and run recovery.
# This is the "chaos engineering" role — powerful by design.

resource "aws_iam_role" "orchestrator" {
  name = "${local.name_prefix}-orchestrator-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Name    = "${local.name_prefix}-orchestrator"
    Purpose = "DisasterZero failure injection and recovery"
    Warning = "This role can stop instances and modify bucket policies"
  }
}

resource "aws_iam_role_policy" "orchestrator" {
  name = "${local.name_prefix}-orchestrator-policy"
  role = aws_iam_role.orchestrator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EC2FailureInjection"
        Effect = "Allow"
        Action = [
          "ec2:StopInstances",
          "ec2:StartInstances",
          "ec2:RebootInstances",
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceStatus",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "ec2:ResourceTag/Project" = "DisasterZero"
          }
        }
      },
      {
        Sid    = "S3FailureInjection"
        Effect = "Allow"
        Action = [
          "s3:GetBucketPolicy",
          "s3:PutBucketPolicy",
          "s3:DeleteBucketPolicy",
          "s3:ListBucket",
          "s3:GetObject",
          "s3:PutObject",
        ]
        Resource = [
          var.s3_bucket_arn,
          "${var.s3_bucket_arn}/*",
        ]
      },
      {
        Sid    = "DynamoDBIncidents"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:UpdateItem",
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${var.account_id}:table/${var.project}-*"
      },
      {
        Sid    = "CloudWatchMonitoring"
        Effect = "Allow"
        Action = [
          "cloudwatch:DescribeAlarms",
          "cloudwatch:GetMetricData",
          "cloudwatch:PutMetricData",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:GetLogEvents",
        ]
        Resource = "*"
      },
      {
        Sid    = "SNSAlerts"
        Effect = "Allow"
        Action = ["sns:Publish"]
        Resource = "arn:aws:sns:${var.aws_region}:${var.account_id}:${var.project}-*"
      },
    ]
  })
}

# ── Outputs ──

output "databricks_role_arn" {
  value = aws_iam_role.databricks_s3_access.arn
}

output "orchestrator_role_arn" {
  value = aws_iam_role.orchestrator.arn
}

