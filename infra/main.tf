terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# VPC - Single public subnet design for $0 (no NAT Gateway)
resource "aws_vpc" "docvault" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "docvault-vpc"
  }
}

resource "aws_internet_gateway" "docvault" {
  vpc_id = aws_vpc.docvault.id
  tags = {
    Name = "docvault-igw"
  }
}

# Public Subnet (ONLY - no private subnets, no NAT Gateway)
resource "aws_subnet" "public_1" {
  vpc_id                  = aws_vpc.docvault.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true  # Required for ECS tasks to get public IPs

  tags = {
    Name = "docvault-public-1"
  }
}

resource "aws_subnet" "public_2" {
  vpc_id                  = aws_vpc.docvault.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "${var.aws_region}b"
  map_public_ip_on_launch = true

  tags = {
    Name = "docvault-public-2"
  }
}

# Route Table (Public only)
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.docvault.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.docvault.id
  }

  tags = {
    Name = "docvault-public-rt"
  }
}

resource "aws_route_table_association" "public_1" {
  subnet_id      = aws_subnet.public_1.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_2" {
  subnet_id      = aws_subnet.public_2.id
  route_table_id = aws_route_table.public.id
}

# FREE Gateway VPC Endpoint for S3 (saves data transfer costs)
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.docvault.id
  service_name = "com.amazonaws.${var.aws_region}.s3"
  route_table_ids = [aws_route_table.public.id]

  tags = {
    Name = "docvault-s3-endpoint"
  }
}

# Security Groups (Lock down despite public subnet)
resource "aws_security_group" "alb" {
  name_prefix = "docvault-alb-"
  vpc_id      = aws_vpc.docvault.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs" {
  name_prefix = "docvault-ecs-"
  vpc_id      = aws_vpc.docvault.id

  # Only ALB can access these tasks
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # Redis port - only from ECS tasks
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    self            = true  # Only resources in this SG
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "rds" {
  name_prefix = "docvault-rds-"
  vpc_id      = aws_vpc.docvault.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  tags = {
    Name = "docvault-rds-sg"
  }
}

# RDS PostgreSQL (Free Tier: db.t3.micro)
resource "aws_db_subnet_group" "docvault" {
  name       = "docvault-db-subnet"
  subnet_ids = [aws_subnet.public_1.id, aws_subnet.public_2.id]  # Public subnets OK with SG protection

  tags = {
    Name = "docvault-db-subnet"
  }
}

resource "aws_db_instance" "docvault" {
  identifier             = "docvault-db"
  engine                 = "postgres"
  engine_version         = "14"
  instance_class         = "db.t3.micro"  # FREE TIER
  allocated_storage      = 20
  max_allocated_storage  = 20  # Prevent autoscaling charges
  storage_type           = "gp2"
  storage_encrypted      = true

  db_name  = "docvault"
  username = "docvault"
  password = var.db_password

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.docvault.name

  publicly_accessible    = false  # Still private despite public subnet
  skip_final_snapshot    = true
  deletion_protection    = false
  backup_retention_period = 1  # Free

  tags = {
    Name = "docvault-postgres"
  }
}

# S3 Bucket with FREE Gateway Endpoint
resource "aws_s3_bucket" "uploads" {
  bucket = "docvault-uploads-${random_id.bucket_suffix.hex}"
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ECR Repositories
resource "aws_ecr_repository" "backend" {
  name                 = "docvault-backend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "aws_ecr_repository" "worker" {
  name                 = "docvault-worker"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "aws_ecr_repository" "frontend" {
  name                 = "docvault-frontend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "aws_ecr_repository" "redis" {
  name                 = "docvault-redis"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

# ECS Cluster
resource "aws_ecs_cluster" "docvault" {
  name = "docvault-cluster"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "docvault" {
  cluster_name = aws_ecs_cluster.docvault.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]
  
  default_capacity_provider_strategy {
    base              = 1
    weight            = 1
    capacity_provider = "FARGATE_SPOT"  # 70% cheaper!
  }
}

# IAM Roles
resource "aws_iam_role" "ecs_execution" {
  name = "docvault-ecs-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_s3_secrets" {
  name = "docvault-ecs-s3-secrets"
  role = aws_iam_role.ecs_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.uploads.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.groq_api_key.arn
      }
    ]
  })
}

resource "aws_iam_role" "ecs_task" {
  name = "docvault-ecs-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

# Secrets Manager (Free Tier: 30 days rotation)
resource "aws_secretsmanager_secret" "groq_api_key" {
  name                    = "docvault/groq-api-key"
  description             = "Groq API Key for DocVault"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "groq_api_key" {
  secret_id     = aws_secretsmanager_secret.groq_api_key.id
  secret_string = var.groq_api_key
}

# CloudWatch Log Groups (Low retention = low cost)
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/docvault-backend"
  retention_in_days = 1  # Minimal retention for $0
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/docvault-worker"
  retention_in_days = 1
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/docvault-frontend"
  retention_in_days = 1
}

resource "aws_cloudwatch_log_group" "redis" {
  name              = "/ecs/docvault-redis"
  retention_in_days = 1
}

# Application Load Balancer
resource "aws_lb" "docvault" {
  name               = "docvault-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [aws_subnet.public_1.id, aws_subnet.public_2.id]

  enable_deletion_protection = false
}

# Target Groups
resource "aws_lb_target_group" "backend" {
  name        = "docvault-backend-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.docvault.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/api/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 3
  }
}

resource "aws_lb_target_group" "frontend" {
  name        = "docvault-frontend-tg"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = aws_vpc.docvault.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 3
  }
}

resource "aws_lb_target_group" "redis" {
  name        = "docvault-redis-tg"
  port        = 6379
  protocol    = "TCP"
  vpc_id      = aws_vpc.docvault.id
  target_type = "ip"

  health_check {
    enabled = true  # TCP health check
    protocol = "TCP"
  }
}

# Listeners
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.docvault.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }
}