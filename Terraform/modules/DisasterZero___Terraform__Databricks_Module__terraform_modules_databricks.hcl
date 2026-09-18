
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
# Job: Transaction Pipeline
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
      notebook_path = "/Repos/${
