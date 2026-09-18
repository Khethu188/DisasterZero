
# ─────────────────────────────────────────────────────────────
# terraform/main.tf
# DisasterZero — Core Infrastructure
# ─────────────────────────────────────────────────────────────
# Provisions all AWS resources that DisasterZero manages,
# tests against, and uses for recovery operations.
# ─────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.40"
    }
  }

  backend "s3" {
    bucket         = "disasterzero-terraform-state"
    key            = "disasterzero/terraform.tfstate"
    region         = "af-south-1"
    dynamodb_table = "disasterzero-terraform-locks"
    encrypt        = true
  }
}

# ─────────────────────────────────────────────────────────────
# Providers
# ─────────────────────────────────────────────────────────────

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "DisasterZero"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "Khethukuthula"
    }
  }
}

provider "databricks" {
  host  = var.databricks_host
  token = var.databricks_token
}

# ─────────────────────────────────────────────────────────────
# Data Sources
# ─────────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ─────────────────────────────────────────────────────────────
# Modules
# ─────────────────────────────────────────────────────────────

module "networking" {
  source      = "./modules/networking"
  environment = var.environment
  project     = var.project_name
}

module "storage" {
  source      = "./modules/storage"
  environment = var.environment
  project     = var.project_name
  account_id  = data.aws_caller_identity.current.account_id
}

module "compute" {
  source        = "./modules/compute"
  environment   = var.environment
  project       = var.project_name
  vpc_id        = module.networking.vpc_id
  subnet_ids    = module.networking.private_subnet_ids
  sg_id         = module.networking.app_security_group_id
  s3_bucket_arn = module.storage.data_bucket_arn
}

module "monitoring" {
  source             = "./modules/monitoring"
  environment        = var.environment
  project            = var.project_name
  alert_email        = var.alert_email
  ec2_instance_id    = module.compute.app_instance_id
  s3_bucket_name     = module.storage.data_bucket_name
  lambda_function_name = module.compute.recovery_lambda_name
}

module "databricks" {
  source               = "./modules/databricks"
  environment          = var.environment
  project              = var.project_name
  databricks_host      = var.databricks_host
  databricks_token     = var.databricks_token
  s3_bucket_name       = module.storage.data_bucket_name
  notification_email   = var.alert_email
}

module "iam" {
  source         = "./modules/iam"
  environment    = var.environment
  project        = var.project_name
  account_id     = data.aws_caller_identity.current.account_id
  aws_region     = var.aws_region
  s3_bucket_arn  = module.storage.data_bucket_arn
  s3_bucket_name = module.storage.data_bucket_name
}

