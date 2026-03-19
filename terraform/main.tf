data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# --- Networking (default VPC) ---

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_internet_gateway" "scorecheck" {
  vpc_id = data.aws_vpc.default.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

resource "aws_route_table" "scorecheck_public" {
  vpc_id = data.aws_vpc.default.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.scorecheck.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

resource "aws_route_table_association" "scorecheck_subnet" {
  subnet_id      = data.aws_subnets.default.ids[0]
  route_table_id = aws_route_table.scorecheck_public.id
}

# --- IAM role for SSM access (replaces SSH) ---

resource "aws_iam_role" "scorecheck_ssm" {
  name = "${var.project_name}-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })

  tags = {
    Name = "${var.project_name}-ssm-role"
  }
}

resource "aws_iam_role_policy_attachment" "scorecheck_ssm" {
  role       = aws_iam_role.scorecheck_ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "scorecheck_ssm" {
  name = "${var.project_name}-ssm-profile"
  role = aws_iam_role.scorecheck_ssm.name
}

resource "aws_security_group" "scorecheck" {
  name        = "${var.project_name}-sg"
  description = "Allow HTTP and HTTPS"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-sg"
  }
}

# --- EC2 Instance ---

resource "aws_instance" "scorecheck" {
  count = var.use_spot ? 0 : 1

  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  iam_instance_profile   = aws_iam_instance_profile.scorecheck_ssm.name
  vpc_security_group_ids = [aws_security_group.scorecheck.id]
  subnet_id              = data.aws_subnets.default.ids[0]

  user_data = templatefile("${path.module}/user-data.sh", {
    domain_name       = var.domain_name
    repository_url    = var.repository_url
    repository_branch = var.repository_branch
  })

  user_data_replace_on_change = true

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  tags = {
    Name = "${var.project_name}-server"
  }
}

# --- Spot Instance (cheaper alternative) ---

resource "aws_spot_instance_request" "scorecheck" {
  count = var.use_spot ? 1 : 0

  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  iam_instance_profile   = aws_iam_instance_profile.scorecheck_ssm.name
  vpc_security_group_ids = [aws_security_group.scorecheck.id]
  subnet_id              = data.aws_subnets.default.ids[0]
  wait_for_fulfillment   = true
  spot_type              = "persistent"

  user_data = templatefile("${path.module}/user-data.sh", {
    domain_name       = var.domain_name
    repository_url    = var.repository_url
    repository_branch = var.repository_branch
  })

  user_data_replace_on_change = true

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  tags = {
    Name = "${var.project_name}-server-spot"
  }
}

# --- Elastic IP (stable public IP across spot interruptions) ---

resource "aws_eip" "scorecheck" {
  domain = "vpc"

  tags = {
    Name = "${var.project_name}-eip"
  }
}

resource "aws_eip_association" "scorecheck" {
  instance_id   = var.use_spot ? aws_spot_instance_request.scorecheck[0].spot_instance_id : aws_instance.scorecheck[0].id
  allocation_id = aws_eip.scorecheck.id

  depends_on = [aws_route_table_association.scorecheck_subnet]
}

# --- Route 53 ---

resource "aws_route53_zone" "main" {
  name = var.domain_name

  tags = {
    Name = "${var.project_name}-zone"
  }
}

resource "aws_route53_record" "root" {
  zone_id = aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = 300
  records = [aws_eip.scorecheck.public_ip]
}

resource "aws_route53_record" "www" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "www.${var.domain_name}"
  type    = "CNAME"
  ttl     = 300
  records = [var.domain_name]
}
