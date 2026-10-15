# Terraform (Milestone 5)

Minimal **dev** skeleton for VPC / ECR / EKS. Default DevDeploy path uses **mock AWS adapters** (`AWS_MOCK_MODE=true`) so demos work without credentials or `terraform apply`.

## Layout

```
infrastructure/terraform/
  versions.tf
  variables.tf
  main.tf          # VPC + ECR + EKS module stubs
  outputs.tf
```

## Enable real AWS (optional, costly)

1. Configure AWS credentials (`AWS_PROFILE` or keys) with permission to create VPC/ECR/EKS.
2. Set in `.env`:
   ```
   AWS_MOCK_MODE=false
   AWS_REGION=us-east-1
   ECR_REGISTRY=<account>.dkr.ecr.us-east-1.amazonaws.com
   EKS_CLUSTER_NAME=devdeploy-dev
   ```
3. From this directory:
   ```bash
   terraform init
   terraform plan
   terraform apply   # review costs first
   ```

## Cost / safety notes

- EKS control plane + nodes incur ongoing charges — destroy when idle (`terraform destroy`).
- Prefer a small node group and a single region.
- Never commit `terraform.tfstate` or AWS keys.
- Keep `AWS_MOCK_MODE=true` for local Milestone demos.
