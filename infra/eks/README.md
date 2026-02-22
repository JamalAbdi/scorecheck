# EKS Cluster Terraform Script

This Terraform configuration deploys an Amazon EKS cluster with a managed node group in AWS, including a Route 53 hosted zone for domain management.

## Prerequisites

- AWS CLI configured with appropriate permissions
- Terraform installed (version ~> 1.0)

## Usage

1. Navigate to the `infra/eks` directory:
   ```bash
   cd infra/eks
   ```

2. Update `terraform.tfvars` with your actual domain name:
   ```
   domain_name = "yourdomain.com"
   ```

3. Initialize Terraform:
   ```bash
   terraform init
   ```

4. Review the plan:
   ```bash
   terraform plan
   ```

5. Apply the configuration:
   ```bash
   terraform apply
   ```

6. To destroy the resources:
   ```bash
   terraform destroy
   ```

## Configuration

The default configuration creates:
- A VPC with 3 public subnets
- An EKS cluster (version 1.28)
- A managed node group with 2 t3.medium instances
- A Route 53 hosted zone for the specified domain

You can customize the variables in `terraform.tfvars` or by passing them via command line.

## Outputs

After deployment, the following outputs are available:
- `cluster_endpoint`: The endpoint for the EKS control plane
- `cluster_security_group_id`: Security group ID for the cluster
- `cluster_name`: Name of the EKS cluster
- `cluster_arn`: ARN of the EKS cluster
- `node_group_arn`: ARN of the node group
- `hosted_zone_id`: ID of the Route 53 hosted zone
- `hosted_zone_name_servers`: Name servers for the hosted zone (use these to update your domain registrar)

## Notes

- Ensure your AWS account has the necessary permissions for EKS, VPC, IAM, and Route 53 operations.
- The cluster is created with public subnets; for production, consider using private subnets.
- IAM roles are created automatically with the required policies.
- After creating the hosted zone, update your domain registrar with the provided name servers.