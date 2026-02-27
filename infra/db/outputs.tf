output "db_instance_id" {
  description = "RDS instance identifier"
  value       = aws_db_instance.this.id
}

output "db_endpoint" {
  description = "RDS endpoint hostname"
  value       = aws_db_instance.this.address
}

output "db_port" {
  description = "RDS PostgreSQL port"
  value       = aws_db_instance.this.port
}

output "db_name" {
  description = "Database name"
  value       = aws_db_instance.this.db_name
}

output "db_username" {
  description = "Database username"
  value       = aws_db_instance.this.username
}

output "db_security_group_id" {
  description = "Security group attached to the RDS instance"
  value       = aws_security_group.db.id
}

output "master_user_secret_arn" {
  description = "Secrets Manager ARN storing the RDS master user credentials"
  value       = try(aws_db_instance.this.master_user_secret[0].secret_arn, null)
}

data "aws_secretsmanager_secret_version" "db_master" {
  count     = length(aws_db_instance.this.master_user_secret) > 0 ? 1 : 0
  secret_id = aws_db_instance.this.master_user_secret[0].secret_arn
}

output "database_url" {
  description = "SQLAlchemy/PostgreSQL connection URL for backend DATABASE_URL"
  value = length(data.aws_secretsmanager_secret_version.db_master) > 0 ? format(
    "postgresql+psycopg://%s:%s@%s:%d/%s",
    jsondecode(data.aws_secretsmanager_secret_version.db_master[0].secret_string)["username"],
    jsondecode(data.aws_secretsmanager_secret_version.db_master[0].secret_string)["password"],
    aws_db_instance.this.address,
    aws_db_instance.this.port,
    var.db_name
  ) : null
  sensitive = true
}
