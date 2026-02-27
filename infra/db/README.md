# Scorecheck RDS PostgreSQL (AWS)

This Terraform stack provisions a PostgreSQL RDS instance for production use with the Scorecheck backend on EKS.

## What this creates

- RDS PostgreSQL instance
- DB subnet group
- Security group allowing PostgreSQL access from configured EKS security groups/CIDRs

## Prerequisites

- AWS credentials configured for the target account
- Terraform >= 1.0
- Existing VPC and subnets (typically the same network used by EKS)

## Configure variables

Copy the example file and fill values:

```bash
cd infra/db
cp terraform.tfvars.example terraform.tfvars
```

Set:

- `vpc_id` and `subnet_ids` from your EKS network
- `allowed_security_group_ids` to your EKS node/cluster SG

Master DB credentials are managed by AWS Secrets Manager via RDS (`manage_master_user_password = true`), so no DB password is required in Terraform variables.

## Deploy

```bash
cd infra/db
terraform init
terraform plan
terraform apply
```

## Use DATABASE_URL in Kubernetes

Get the generated database URL:

```bash
terraform output -raw database_url
```

Create/update a Kubernetes secret in the namespace where backend is deployed:

```bash
kubectl -n default create secret generic scorecheck-backend-db \
  --from-literal=DATABASE_URL="$(terraform output -raw database_url)" \
  --dry-run=client -o yaml | kubectl apply -f -
```

## Namespace-specific deployment examples

Use separate namespaces and release names for production and staging so they do not collide.

### Production

```bash
kubectl create namespace scorecheck-prod --dry-run=client -o yaml | kubectl apply -f -

kubectl -n scorecheck-prod create secret generic scorecheck-backend-db \
  --from-literal=DATABASE_URL="$(terraform output -raw database_url)" \
  --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install scorecheck-backend-prod ./k8-deployments/backend-chart \
  -n scorecheck-prod \
  -f k8-deployments/backend-chart/values-prod.yaml

helm upgrade --install scorecheck-frontend-prod ./k8-deployments/frontend-chart \
  -n scorecheck-prod \
  -f k8-deployments/frontend-chart/values-prod.yaml
```

### Staging

```bash
kubectl create namespace scorecheck-staging --dry-run=client -o yaml | kubectl apply -f -

kubectl -n scorecheck-staging create secret generic scorecheck-backend-db \
  --from-literal=DATABASE_URL="$(terraform output -raw database_url)" \
  --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install scorecheck-backend-staging ./k8-deployments/backend-chart \
  -n scorecheck-staging \
  -f k8-deployments/backend-chart/values-staging.yaml

helm upgrade --install scorecheck-frontend-staging ./k8-deployments/frontend-chart \
  -n scorecheck-staging \
  -f k8-deployments/frontend-chart/values-staging.yaml
```

Then set Helm values for backend chart:

- `database.existingSecretName=scorecheck-backend-db`
- `database.existingSecretKey=DATABASE_URL`

Example:

```bash
helm upgrade --install backend ./k8-deployments/backend-chart \
  --set database.existingSecretName=scorecheck-backend-db \
  --set database.existingSecretKey=DATABASE_URL
```

## Notes

- The connection string uses `postgresql+psycopg://...` for SQLAlchemy 2.x.
- RDS master password is stored in Secrets Manager and surfaced through Terraform output `database_url` (sensitive).
- Keep `publicly_accessible=false` for production.
- Prefer private subnets for RDS.
