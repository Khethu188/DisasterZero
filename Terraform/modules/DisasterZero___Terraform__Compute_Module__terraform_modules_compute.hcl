
# ─────────────────────────────────────────────────────────────
# terraform/modules/compute/main.tf
# EC2 App Server, Lambda Recovery Function
# ─────────────────────────────────────────────────────────────

variable "environment" { type = string }
variable "project" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "sg_id" { type = string }
variable "s3_bucket_arn" { type = string }

locals {
  name_prefix = "${var.project}-${var.environment}"
}

# ═══════════════════════════════════════════════════════════════
# EC2: Application Server
# ═══════════════════════════════════════════════════════════════
# Runs the DisasterZero orchestrator + Streamlit dashboard.
# This is also a TARGET for EC2 failure simulation scenarios.

data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = "t3.medium"
  subnet_id              = var.subnet_ids[0]
  vpc_security_group_ids = [var.sg_id]
  iam_instance_profile   = aws_iam_instance_profile.app.name

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = base64encode(<<-EOF
    #!/bin/bash
    set -e

    # System updates
    yum update -y
    yum install -y python3.11 python3.11-pip git docker

    # Start Docker
    systemctl enable docker
    systemctl start docker

    # Install Python dependencies
    pip3.11 install streamlit boto3 requests python-dotenv pandas

    # Clone DisasterZero
    cd /opt
    git clone https://github.com/Khethu188/DisasterZero.git || true
    cd DisasterZero

    # Create systemd service for Streamlit
    cat > /etc/systemd/system/disasterzero-dashboard.service << 'UNIT'
    [Unit]
    Description=DisasterZero Streamlit Dashboard
    After=network.target

    [Service]
    Type=simple
    User=ec2-user
    WorkingDirectory=/opt/DisasterZero
    ExecStart=/usr/bin/python3.11 -m streamlit run dashboard/app.py --server.port=8501 --server.address=0.0.0.0
    Restart=always
    RestartSec=5

    [Install]
    WantedBy=multi-user.target
    UNIT

    systemctl enable disasterzero-dashboard
    systemctl start disasterzero-dashboard

    echo "DisasterZero setup complete" > /var/log/disasterzero-setup.log
  EOF
  )

  tags = {
    Name        = "${local.name_prefix}-app"
    Purpose     = "DisasterZero orchestrator and dashboard"
    Criticality = "HIGH"
    DisasterZero = "target"  # Marks this as a failure simulation target
  }

  lifecycle {
    ignore_changes = [ami]
  }
}

resource "aws_iam_instance_profile" "app" {
  name = "${local.name_prefix}-app-profile"
  role = aws_iam_role.app.name
}

resource "aws_iam_role" "app" {
  name = "${local.name_prefix}-app-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "app" {
  name = "${local.name_prefix}-app-policy"
  role = aws_iam_role.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Access"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject",
          "s3:GetBucketPolicy",
          "s3:PutBucketPolicy",
        ]
        Resource = [
          var.s3_bucket_arn,
          "${var.s3_bucket_arn}/*",
        ]
      },
      {
        Sid    = "EC2Recovery"
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:StartInstances",
          "ec2:StopInstances",
          "ec2:RebootInstances",
          "ec2:DescribeInstanceStatus",
        ]
        Resource = "*"
      },
      {
        Sid    = "DynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:UpdateItem",
        ]
        Resource = "arn:aws:dynamodb:*:*:table/${var.project}-*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Sid    = "SNSPublish"
        Effect = "Allow"
        Action = ["sns:Publish"]
        Resource = "arn:aws:sns:*:*:${var.project}-*"
      },
    ]
  })
}

# ═══════════════════════════════════════════════════════════════
# Lambda: Automated Recovery Function
# ═══════════════════════════════════════════════════════════════
# Triggered by CloudWatch alarms for automated recovery.
# Handles: EC2 restart, S3 policy restore, pipeline re-trigger.

data "archive_file" "recovery_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda.zip"
}

resource "aws_lambda_function" "recovery" {
  function_name    = "${local.name_prefix}-recovery"
  filename         = data.archive_file.recovery_lambda.output_path
  source_code_hash = data.archive_file.recovery_lambda.output_base64sha256
  handler          = "handler.lambda_handler"
  runtime          = "python3.11"
  timeout          = 300
  memory_size      = 256
  role             = aws_iam_role.lambda_recovery.arn

  environment {
    variables = {
      ENVIRONMENT       = var.environment
      PROJECT           = var.project
      S3_BUCKET         = trimprefix(var.s3_bucket_arn, "arn:aws:s3:::")
      INCIDENTS_TABLE   = "${var.project}-${var.environment}-incidents"
      APP_INSTANCE_ID   = aws_instance.app.id
    }
  }

  tags = {
    Name    = "${local.name_prefix}-recovery"
    Purpose = "Automated disaster recovery"
  }
}

resource "aws_iam_role" "lambda_recovery" {
  name = "${local.name_prefix}-lambda-recovery-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "lambda_recovery" {
  name = "${local.name_prefix}-lambda-recovery-policy"
  role = aws_iam_role.lambda_recovery.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EC2Recovery"
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:StartInstances",
          "ec2:StopInstances",
          "ec2:DescribeInstanceStatus",
        ]
        Resource = "*"
      },
      {
        Sid    = "S3Recovery"
        Effect = "Allow"
        Action = [
          "s3:GetBucketPolicy",
          "s3:PutBucketPolicy",
          "s3:DeleteBucketPolicy",
        ]
        Resource = var.s3_bucket_arn
      },
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
        ]
        Resource = "arn:aws:dynamodb:*:*:table/${var.project}-*"
      },
      {
        Sid    = "Logs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Sid    = "SNS"
        Effect = "Allow"
        Action = ["sns:Publish"]
        Resource = "arn:aws:sns:*:*:${var.project}-*"
      },
    ]
  })
}

resource "aws_cloudwatch_log_group" "recovery_lambda" {
  name              = "/aws/lambda/${aws_lambda_function.recovery.function_name}"
  retention_in_days = 30
}

# ── Outputs ──

output "app_instance_id" {
  value = aws_instance.app.id
}

output "app_instance_public_ip" {
  value = aws_instance.app.public_ip
}

output "recovery_lambda_arn" {
  value = aws_lambda_function.recovery.arn
}

output "recovery_lambda_name" {
  value = aws_lambda_function.recovery.function_name
}

