
# ─────────────────────────────────────────────────────────────
# terraform/modules/storage/main.tf
# S3 Buckets, DynamoDB Tables
# ─────────────────────────────────────────────────────────────

variable "environment" { type = string }
variable "project" { type = string }
variable "account_id" { type = string }

locals {
  name_prefix = "${var.project}-${var.environment}"
  bucket_name = "${var.project}-data-${var.environment}-${var.account_id}"
}

# ═══════════════════════════════════════════════════════════════
# S3: Primary Data Bucket
# ═══════════════════════════════════════════════════════════════
# This is the bucket DisasterZero tests against:
#   - Raw transaction data lands here
#   - Databricks reads from here
#   - S3 access denial scenarios target this bucket's policy

resource "aws_s3_bucket" "data" {
  bucket = local.bucket_name

  tags = {
    Name        = "${local.name_prefix}-data"
    Purpose     = "Transaction data lake — DisasterZero target"
    Criticality = "HIGH"
  }
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "archive-old-data"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  rule {
    id     = "cleanup-quarantine"
    status = "Enabled"

    filter {
      prefix = "quarantine/"
    }

    expiration {
      days = 60
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket = aws_s3_bucket.data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Folder structure
resource "aws_s3_object" "raw_folder" {
  bucket  = aws_s3_bucket.data.id
  key     = "raw/transactions/"
  content = ""
}

resource "aws_s3_object" "processed_folder" {
  bucket  = aws_s3_bucket.data.id
  key     = "processed/"
  content = ""
}

resource "aws_s3_object" "quarantine_folder" {
  bucket  = aws_s3_bucket.data.id
  key     = "quarantine/"
  content = ""
}

resource "aws_s3_object" "reports_folder" {
  bucket  = aws_s3_bucket.data.id
  key     = "reports/"
  content = ""
}

resource "aws_s3_object" "backups_folder" {
  bucket  = aws_s3_bucket.data.id
  key     = "backups/"
  content = ""
}

# ═══════════════════════════════════════════════════════════════
# S3: Reports Bucket
# ═══════════════════════════════════════════════════════════════

resource "aws_s3_bucket" "reports" {
  bucket = "${var.project}-reports-${var.environment}-${var.account_id}"

  tags = {
    Name    = "${local.name_prefix}-reports"
    Purpose = "Recovery reports and audit logs"
  }
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket = aws_s3_bucket.reports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ═══════════════════════════════════════════════════════════════
# DynamoDB: Incident Tracking
# ═══════════════════════════════════════════════════════════════

resource "aws_dynamodb_table" "incidents" {
  name         = "${local.name_prefix}-incidents"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "incident_id"
  range_key    = "created_at"

  attribute {
    name = "incident_id"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  attribute {
    name = "failure_type"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  global_secondary_index {
    name            = "failure-type-index"
    hash_key        = "failure_type"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name    = "${local.name_prefix}-incidents"
    Purpose = "Incident tracking and recovery audit trail"
  }
}

# ═══════════════════════════════════════════════════════════════
# DynamoDB: Terraform State Locks
# ═══════════════════════════════════════════════════════════════

resource "aws_dynamodb_table" "terraform_locks" {
  name         = "${var.project}-terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Name    = "${var.project}-terraform-locks"
    Purpose = "Terraform state locking"
  }
}

# ── Outputs ──

output "data_bucket_name" {
  value = aws_s3_bucket.data.bucket
}

output "data_bucket_arn" {
  value = aws_s3_bucket.data.arn
}

output "reports_bucket_name" {
  value = aws_s3_bucket.reports.bucket
}

output "incidents_table_name" {
  value = aws_dynamodb_table.incidents.name
}

