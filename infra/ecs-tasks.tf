# REDIS as ECS Service ($0 vs $12/month ElastiCache)
resource "aws_ecs_task_definition" "redis" {
  family                   = "docvault-redis"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"   # Minimal CPU
  memory                   = "512"   # Minimal memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  container_definitions = jsonencode([
    {
      name  = "redis"
      image = "redis:7-alpine"
      
      portMappings = [
        {
          containerPort = 6379
          protocol      = "tcp"
        }
      ]

      command = ["redis-server", "--appendonly", "no", "--maxmemory", "200mb", "--maxmemory-policy", "allkeys-lru"]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.redis.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "redis" {
  name            = "docvault-redis"
  cluster         = aws_ecs_cluster.docvault.id
  task_definition = aws_ecs_task_definition.redis.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.public_1.id, aws_subnet.public_2.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  service_registries {
    registry_arn = aws_service_discovery_service.redis.arn
  }
}

# Service Discovery for Redis (so backend can find it)
resource "aws_service_discovery_private_dns_namespace" "docvault" {
  name        = "docvault.local"
  description = "Service discovery for DocVault"
  vpc         = aws_vpc.docvault.id
}

resource "aws_service_discovery_service" "redis" {
  name = "redis"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.docvault.id
    
    dns_records {
      ttl  = 10
      type = "A"
    }
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

# Backend Task Definition (Updated to use ECS Redis)
resource "aws_ecs_task_definition" "backend" {
  family                   = "docvault-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"   # Reduced for $0
  memory                   = "512"   # Reduced for $0
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "backend"
      image = "${aws_ecr_repository.backend.repository_url}:latest"
      
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "DATABASE_URL"
          value = "postgresql://${aws_db_instance.docvault.username}:${var.db_password}@${aws_db_instance.docvault.endpoint}/${aws_db_instance.docvault.db_name}"
        },
        {
          name  = "REDIS_HOST"
          value = "redis.docvault.local"  # Service discovery
        },
        {
          name  = "REDIS_PORT"
          value = "6379"
        },
        {
          name  = "STORAGE_BACKEND"
          value = "s3"
        },
        {
          name  = "AWS_S3_BUCKET"
          value = aws_s3_bucket.uploads.bucket
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "LLM_PROVIDER"
          value = "groq"
        },
        {
          name  = "LLM_MODEL"
          value = "llama-3.1-8b-instant"
        },
        {
          name  = "EMBEDDING_STUB"
          value = "true"
        }
      ]

      secrets = [
        {
          name      = "GROQ_API_KEY"
          valueFrom = aws_secretsmanager_secret.groq_api_key.arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.backend.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "backend" {
  name            = "docvault-backend"
  cluster         = aws_ecs_cluster.docvault.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.public_1.id, aws_subnet.public_2.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http, aws_ecs_service.redis]
}

# Worker Task Definition
resource "aws_ecs_task_definition" "worker" {
  family                   = "docvault-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"   # Minimal
  memory                   = "512"   # Minimal
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "worker"
      image = "${aws_ecr_repository.worker.repository_url}:latest"
      command = ["python", "-m", "app.worker.worker"]

      environment = [
        {
          name  = "DATABASE_URL"
          value = "postgresql://${aws_db_instance.docvault.username}:${var.db_password}@${aws_db_instance.docvault.endpoint}/${aws_db_instance.docvault.db_name}"
        },
        {
          name  = "REDIS_HOST"
          value = "redis.docvault.local"
        },
        {
          name  = "REDIS_PORT"
          value = "6379"
        },
        {
          name  = "STORAGE_BACKEND"
          value = "s3"
        },
        {
          name  = "AWS_S3_BUCKET"
          value = aws_s3_bucket.uploads.bucket
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "LLM_PROVIDER"
          value = "groq"
        },
        {
          name  = "LLM_MODEL"
          value = "llama-3.1-8b-instant"
        },
        {
          name  = "EMBEDDING_STUB"
          value = "true"
        }
      ]

      secrets = [
        {
          name      = "GROQ_API_KEY"
          valueFrom = aws_secretsmanager_secret.groq_api_key.arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.worker.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "worker" {
  name            = "docvault-worker"
  cluster         = aws_ecs_cluster.docvault.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.public_1.id, aws_subnet.public_2.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  depends_on = [aws_ecs_service.redis]
}

# Frontend Task Definition
resource "aws_ecs_task_definition" "frontend" {
  family                   = "docvault-frontend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"   # Minimal
  memory                   = "512"   # Minimal
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  container_definitions = jsonencode([
    {
      name  = "frontend"
      image = "${aws_ecr_repository.frontend.repository_url}:latest"
      
      portMappings = [
        {
          containerPort = 80
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "BACKEND_URL"
          value = "http://backend.docvault.local:8000"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.frontend.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "frontend" {
  name            = "docvault-frontend"
  cluster         = aws_ecs_cluster.docvault.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.public_1.id, aws_subnet.public_2.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 80
  }

  depends_on = [aws_lb_listener.http]
}