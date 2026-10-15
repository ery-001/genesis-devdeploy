output "vpc_id" {
  value = aws_vpc.main.id
}

output "ecr_repository_url" {
  value = aws_ecr_repository.apps.repository_url
}

output "mock_reminder" {
  value = "Keep AWS_MOCK_MODE=true in DevDeploy unless you have applied this stack and set ECR_REGISTRY/EKS_CLUSTER_NAME."
}
