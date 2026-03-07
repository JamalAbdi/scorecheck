# Archived Infrastructure

These files are from the old EKS/RDS/ECR-based architecture that has been replaced
with a simpler EC2 + Docker Compose + Caddy setup.

Kept here for reference and for the teardown script (`scripts/teardown-old-infra.sh`)
which references `infra/` Terraform state to destroy old AWS resources.

## Old architecture (~ $100+/month):
- EKS cluster with managed node group
- RDS PostgreSQL
- ALB (Application Load Balancer)
- ECR repositories
- Helm chart deployments
- Sleep/wake cron schedule

## New architecture (~ $4/month):
- Single EC2 spot instance (t3a.nano)
- Docker Compose (backend + frontend + Caddy)
- SQLite (cache-only database)
- Caddy for automatic HTTPS via Let's Encrypt
- Route 53 for DNS

Once you've confirmed the old AWS resources are fully torn down,
this directory can be safely deleted.
