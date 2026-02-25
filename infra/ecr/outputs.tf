output "ecr_repository_urls" {
  description = "ECR repository URLs"
  value = {
    for repo in aws_ecr_repository.repos :
    repo.name => repo.repository_url
  }
}
