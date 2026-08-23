variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes control plane version"
  type        = string
  default     = "1.31"
}

variable "cluster_role_arn" {
  description = "IAM role ARN for the EKS control plane"
  type        = string
}

variable "node_role_arn" {
  description = "IAM role ARN for the managed node group"
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs (for the cluster's ENIs / public endpoint)"
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnet IDs (worker nodes run here)"
  type        = list(string)
}

variable "node_instance_types" {
  description = "EC2 instance types for the default managed node group"
  type        = list(string)
  default     = ["t3.large"]
}

variable "capacity_type" {
  description = "ON_DEMAND or SPOT"
  type        = string
  default     = "ON_DEMAND"
}

variable "node_disk_size_gb" {
  type    = number
  default = 50
}

variable "desired_size" {
  type    = number
  default = 3
}

variable "min_size" {
  type    = number
  default = 2
}

variable "max_size" {
  type    = number
  default = 6
}

variable "tags" {
  description = "Common tags applied to all resources"
  type        = map(string)
  default     = {}
}
