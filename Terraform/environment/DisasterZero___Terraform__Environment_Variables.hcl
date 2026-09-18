
# ─────────────────────────────────────────────────────────────
# terraform/environments/dev.tfvars
# Development environment configuration
# ─────────────────────────────────────────────────────────────

project_name = "disasterzero"
environment  = "dev"
aws_region   = "af-south-1"

# Databricks (set via TF_VAR_ env vars for security)
# databricks_host  = "https://your-workspace.cloud.databricks.com"
# databricks_token = "dapi..."

alert_email = "Khethukuthula.sabela@outlook.com"
vpc_cidr    = "10.0.0.0/16"

enable_deletion_protection = false

