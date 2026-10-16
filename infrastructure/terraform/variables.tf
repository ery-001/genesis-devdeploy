variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "devdeploy"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "enable_eks" {
  description = "Set true only when you intentionally want a real EKS cluster (costs money)."
  type        = bool
  default     = false
}
