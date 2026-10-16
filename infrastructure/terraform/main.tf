locals {
  name = "${var.project_name}-${var.environment}"
}

# --- VPC (skeleton) ---
resource "aws_vpc" "main" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_hostnames = true
  tags = {
    Name = "${local.name}-vpc"
  }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.42.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true
  tags = { Name = "${local.name}-public-a" }
}

# --- ECR ---
resource "aws_ecr_repository" "apps" {
  name                 = "${local.name}-apps"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
  tags = { Name = "${local.name}-ecr" }
}

# --- EKS (opt-in) ---
# When var.enable_eks is true, wire terraform-aws-modules/eks/aws (or equivalent)
# against aws_vpc.main / aws_subnet.public_a. Left unset by default to avoid cost.
