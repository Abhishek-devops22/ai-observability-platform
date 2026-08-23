locals {
  name = "${var.project}-${var.environment}"

  common_tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

module "vpc" {
  source = "../modules/vpc"

  name         = local.name
  cluster_name = local.name
  vpc_cidr     = var.vpc_cidr
  az_count     = var.az_count
  nat_per_az   = var.nat_per_az
  tags         = local.common_tags
}

module "iam" {
  source = "../modules/iam"

  name = local.name
  tags = local.common_tags
}

module "eks" {
  source = "../modules/eks"

  cluster_name        = local.name
  kubernetes_version  = var.kubernetes_version
  cluster_role_arn    = module.iam.cluster_role_arn
  node_role_arn       = module.iam.node_role_arn
  public_subnet_ids   = module.vpc.public_subnet_ids
  private_subnet_ids  = module.vpc.private_subnet_ids
  node_instance_types = var.node_instance_types
  capacity_type       = var.capacity_type
  desired_size        = var.desired_size
  min_size            = var.min_size
  max_size            = var.max_size
  tags                = local.common_tags
}
