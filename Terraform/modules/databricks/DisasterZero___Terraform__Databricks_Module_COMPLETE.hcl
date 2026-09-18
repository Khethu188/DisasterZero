
# ─────────────────────────────────────────────────────────────
# terraform/modules/databricks/main.tf
# Databricks Workspace Resources — Job, Cluster, Secrets
# ─────────────────────────────────────────────────────────────

variable "environment" { type = string }
variable "project" { type = string }
variable "databricks_host" { type = string }
variable "databricks_token" { type = string }
variable "s3_bucket_name" { type = string }
variable "notification_email" { type = string }

locals {
  name_prefix = "${var.project}-${var.environment}"
}

# ═══════════════════════════════════════════════════════════════
# Cluster Policy
# ═══════════════════════════════════════════════════════════════

resource "databricks_cluster_policy" "pipeline" {
  name = "${local.name_prefix}-pipeline-policy"

  definition = jsonencode({
    "spark_version" : {
      "type" : "allowlist",
      "values" : ["14.3.x-scala2.12", "15.0.x-scala2.12"]
    },
    "node_type_id" : {
      "type" : "allowlist",
      "values" : ["i3.xlarge", "i3.2xlarge", "m5.xlarge"]
    },
    "num_workers" : {
      "type" : "range",
      "minValue" : 1,
      "maxValue" : 4
    },
    "autotermination_minutes" : {
      "type" : "range",
      "minValue" : 10,
      "maxValue" : 60
    },
    "custom_tags.Project" : {
      "type" : "fixed",
      "value" : "DisasterZero"
    },
    "custom_tags.Environment" : {
      "type" : "fixed",
      "value" : var.environment
    }
  })
}

# ═══════════════════════════════════════════════════════════════
# Job: Transaction Pipeline (Full DAG)
# ═══════════════════════════════════════════════════════════════

resource "databricks_job" "transaction_pipeline" {
  name = "${local.name_prefix}-transaction-pipeline"

  # ── Task 1: Schema Setup ──
  task {
    task_key = "setup_schema"

    notebook_task {
      notebook_path = "/Repos/${var.project}/databricks/notebooks/setup_schema"
      source        = "GIT"
    }

    new_cluster {
      spark_version = "14.3.x-scala2.12"
      node_type_id  = "i3.xlarge"
      num_workers   = 1

      spark_conf = {
        "spark.databricks.delta.optimizeWrite.enabled" = "true"
      }

      custom_tags = {
        Project     = "DisasterZero"
        Environment = var.environment
        Task        = "setup"
      }
    }

    timeout_seconds = 300
    max_retries     = 1
  }

  # ── Task 2: Data Generation ──
  task {
    task_key = "generate_data"

    depends_on {
      task_key = "setup_schema"
    }

    notebook_task {
      notebook_path = "/Repos/${var.project}/databricks/notebooks/generate_sample_data"
      source        = "GIT"
    }

    new_cluster {
      spark_version = "14.3.x-scala2.12"
      node_type_id  = "i3.xlarge"
      num_workers   = 1

      custom_tags = {
        Project     = "DisasterZero"
        Environment = var.environment
        Task        = "generate"
      }
    }

    timeout_seconds = 600
    max_retries     = 1
  }

  # ── Task 3: Bronze Ingestion ──
  task {
    task_key = "ingest_bronze"

    depends_on {
      task_key = "generate_data"
    }

    notebook_task {
      notebook_path = "/Repos/${var.project}/databricks/notebooks/01_ingest_bronze"
      source        = "GIT"

      base_parameters = {
        "source_path" = "s3://${var.s3_bucket_name}/raw/transactions/"
      }
    }

    new_cluster {
      spark_version = "14.3.x-scala2.12"
      node_type_id  = "i3.xlarge"
      num_workers   = 2

      spark_conf = {
        "spark.databricks.delta.optimizeWrite.enabled" = "true"
        "spark.databricks.delta.autoCompact.enabled"   = "true"
      }

      custom_tags = {
        Project     = "DisasterZero"
        Environment = var.environment
        Task        = "ingest"
      }
    }

    timeout_seconds = 900
    max_retries     = 2
  }

  # ── Task 4: Silver Transformation ──
  task {
    task_key = "transform_silver"

    depends_on {
      task_key = "ingest_bronze"
    }

    notebook_task {
      notebook_path = "/Repos/${var.project}/databricks/notebooks/02_transform_silver"
      source        = "GIT"
    }

    new_cluster {
      spark_version = "14.3.x-scala2.12"
      node_type_id  = "i3.xlarge"
      num_workers   = 2

      custom_tags = {
        Project     = "DisasterZero"
        Environment = var.environment
        Task        = "transform"
      }
    }

    timeout_seconds = 900
    max_retries     = 1
  }

  # ── Task 5: Gold Analytics ──
  task {
    task_key = "build_gold"

    depends_on {
      task_key = "transform_silver"
    }

    notebook_task {
      notebook_path = "/Repos/${var.project}/databricks/notebooks/03_analytics_gold"
      source        = "GIT"
    }

    new_cluster {
      spark_version = "14.3.x-scala2.12"
      node_type_id  = "i3.xlarge"
      num_workers   = 2

      custom_tags = {
        Project     = "DisasterZero"
        Environment = var.environment
        Task        = "analytics"
      }
    }

    timeout_seconds = 900
    max_retries     = 1
  }

  # ── Task 6: Quality Gate (DataTrust) ──
  task {
    task_key = "quality_gate"

    depends_on {
      task_key = "build_gold"
    }

    notebook_task {
      notebook_path = "/Repos/${var.project}/databricks/notebooks/setup_quality_audit"
      source        = "GIT"
    }

    new_cluster {
      spark_version = "14.3.x-scala2.12"
      node_type_id  = "i3.xlarge"
      num_workers   = 1

      custom_tags = {
        Project     = "DisasterZero"
        Environment = var.environment
        Task        = "quality_gate"
      }
    }

    timeout_seconds = 600
    max_retries     = 0  # No retry — quality gate failure is intentional signal
  }

  # ── Schedule ──
  schedule {
    quartz_cron_expression = "0 0 */4 * * ?"  # Every 4 hours
    timezone_id            = "Africa/Johannesburg"
  }

  # ── Email Notifications ──
  email_notifications {
    on_failure = [var.notification_email]
    on_start   = []
    on_success = []
  }

  # ── Job Settings ──
  max_concurrent_runs = 1
  timeout_seconds     = 3600  # 1 hour total

  tags = {
    Project     = "DisasterZero"
    Environment = var.environment
    Pipeline    = "transaction-processing"
  }
}

# ═══════════════════════════════════════════════════════════════
# Secrets Scope
# ═══════════════════════════════════════════════════════════════

resource "databricks_secret_scope" "disasterzero" {
  name = "${local.name_prefix}-secrets"
}

resource "databricks_secret" "aws_access_key" {
  scope        = databricks_secret_scope.disasterzero.name
  key          = "aws-access-key-id"
  string_value = "PLACEHOLDER"  # Set via CLI after apply

  lifecycle {
    ignore_changes = [string_value]
  }
}

resource "databricks_secret" "aws_secret_key" {
  scope        = databricks_secret_scope.disasterzero.name
  key          = "aws-secret-access-key"
  string_value = "PLACEHOLDER"  # Set via CLI after apply

  lifecycle {
    ignore_changes = [string_value]
  }
}

resource "databricks_secret" "s3_bucket" {
  scope        = databricks_secret_scope.disasterzero.name
  key          = "s3-bucket-name"
  string_value = var.s3_bucket_name
}

# ═══════════════════════════════════════════════════════════════
# Git Repo Integration
# ═══════════════════════════════════════════════════════════════

resource "databricks_repo" "disasterzero" {
  url    = "https://github.com/Khethu188/DisasterZero.git"
  path   = "/Repos/${var.project}"
  branch = var.environment == "prod" ? "main" : var.environment
}

# ── Outputs ──

output "job_id" {
  value = databricks_job.transaction_pipeline.id
}

output "job_url" {
  value = "${var.databricks_host}/#job/${databricks_job.transaction_pipeline.id}"
}

output "secret_scope" {
  value = databricks_secret_scope.disasterzero.name
}

output "repo_path" {
  value = databricks_repo.disasterzero.path
}

