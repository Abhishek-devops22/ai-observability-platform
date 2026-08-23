terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }

  # Local backend by default so `terraform init` works with zero setup.
  # Once infrastructure/backend/ has been applied (creates an S3 bucket +
  # DynamoDB lock table), switch to remote state:
  #   1. Uncomment the `backend "s3" {}` block below.
  #   2. terraform init -backend-config=../backend/backend.hcl -migrate-state
  # backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}
