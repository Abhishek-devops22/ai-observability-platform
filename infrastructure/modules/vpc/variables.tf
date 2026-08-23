variable "name" {
  description = "Name prefix for VPC resources"
  type        = string
}

variable "cluster_name" {
  description = "EKS cluster name, used for subnet discovery tags"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "Number of availability zones to spread subnets across"
  type        = number
  default     = 3
}

variable "nat_per_az" {
  description = "Deploy one NAT Gateway per AZ (HA, higher cost) instead of a single shared NAT Gateway"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Common tags applied to all resources"
  type        = map(string)
  default     = {}
}
