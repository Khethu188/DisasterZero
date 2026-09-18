
# ─────────────────────────────────────────────────────────────
# terraform/outputs.tf
# ─────────────────────────────────────────────────────────────

output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "data_bucket_name" {
  description = "S3 data bucket name"
  value       = module.storage.data_bucket_name
}

output "data_bucket_arn" {
  description = "S3 data bucket ARN"
  value       = module.storage.data_bucket_arn
}

output "app_instance_id" {
  description = "EC2 app server instance ID"
  value       = module.compute.app_instance_id
}

output "recovery_lambda_arn" {
  description = "Recovery Lambda function ARN"
  value       = module.compute.recovery_lambda_arn
}

output "sns_topic_arn" {
  description = "SNS alert topic ARN"
  value       = module.monitoring.sns_topic_arn
}

output "cloudwatch_dashboard_url" {
  description = "CloudWatch dashboard URL"
  value       = module.monitoring.dashboard_url
}

output "databricks_job_id" {
  description = "Databricks pipeline job ID"
  value       = module.databricks.job_id
}

output "terraform_state_bucket" {
  description = "Terraform state bucket"
  value       = "disasterzero-terraform-state"
}

