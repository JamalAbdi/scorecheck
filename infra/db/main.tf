locals {
  name_prefix = "${var.project_name}-${var.environment}"

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_db_subnet_group" "this" {
  name       = "${local.name_prefix}-db-subnets"
  subnet_ids = var.subnet_ids

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-db-subnet-group"
  })
}

resource "aws_security_group" "db" {
  name        = "${local.name_prefix}-db-sg"
  description = "Allow PostgreSQL access from EKS"
  vpc_id      = var.vpc_id

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-db-sg"
  })
}

resource "aws_vpc_security_group_ingress_rule" "from_sgs" {
  for_each = toset(var.allowed_security_group_ids)

  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = each.value
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  description                  = "PostgreSQL from allowed security group"
}

resource "aws_vpc_security_group_ingress_rule" "from_cidrs" {
  for_each = toset(var.allowed_cidr_blocks)

  security_group_id = aws_security_group.db.id
  cidr_ipv4         = each.value
  from_port         = 5432
  to_port           = 5432
  ip_protocol       = "tcp"
  description       = "PostgreSQL from allowed CIDR"
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.db.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Allow all outbound traffic"
}

resource "aws_db_instance" "this" {
  identifier                 = "${local.name_prefix}-postgres"
  engine                     = "postgres"
  engine_version             = var.engine_version
  instance_class             = var.instance_class
  allocated_storage          = var.allocated_storage
  max_allocated_storage      = var.max_allocated_storage
  db_name                    = var.db_name
  username                   = var.db_username
  manage_master_user_password = true
  port                       = 5432
  db_subnet_group_name       = aws_db_subnet_group.this.name
  vpc_security_group_ids     = [aws_security_group.db.id]
  publicly_accessible        = var.publicly_accessible
  multi_az                   = var.multi_az
  deletion_protection        = var.deletion_protection
  backup_retention_period    = var.backup_retention_period
  skip_final_snapshot        = var.skip_final_snapshot
  storage_encrypted          = var.storage_encrypted
  auto_minor_version_upgrade = true
  apply_immediately          = true

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-postgres"
  })
}
