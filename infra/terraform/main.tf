terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
  }

  backend "s3" {
    bucket         = "neuroguard-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "neuroguard-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "NeuroGuard"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Compliance  = "HIPAA"
    }
  }
}

# ── Variables ─────────────────────────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "neuroguard-prod"
}

variable "db_password" {
  description = "PostgreSQL master password"
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "Primary domain for the application"
  type        = string
  default     = "neuroguard.health"
}

# ── Networking ─────────────────────────────────────────────────────────────────

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = { Name = "neuroguard-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "neuroguard-igw" }
}

# Public subnets (ALB / NAT gateways)
resource "aws_subnet" "public" {
  count                   = 3
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.${count.index}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name                                        = "neuroguard-public-${count.index + 1}"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/elb"                    = "1"
  }
}

# Private subnets (EKS nodes, RDS, ElastiCache)
resource "aws_subnet" "private" {
  count             = 3
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 10}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name                                        = "neuroguard-private-${count.index + 1}"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/internal-elb"           = "1"
  }
}

resource "aws_eip" "nat" {
  count  = 3
  domain = "vpc"
  tags   = { Name = "neuroguard-nat-eip-${count.index + 1}" }
}

resource "aws_nat_gateway" "main" {
  count         = 3
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = { Name = "neuroguard-nat-${count.index + 1}" }
}

resource "aws_route_table" "private" {
  count  = 3
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }

  tags = { Name = "neuroguard-rt-private-${count.index + 1}" }
}

resource "aws_route_table_association" "private" {
  count          = 3
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

data "aws_availability_zones" "available" {
  state = "available"
}

# ── KMS Keys ──────────────────────────────────────────────────────────────────

resource "aws_kms_key" "phi" {
  description             = "NeuroGuard PHI encryption key (HIPAA)"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow EKS service account"
        Effect = "Allow"
        Principal = { AWS = aws_iam_role.neuroguard_app.arn }
        Action = ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
        Resource = "*"
      }
    ]
  })

  tags = { Name = "neuroguard-phi-key" }
}

resource "aws_kms_alias" "phi" {
  name          = "alias/neuroguard-phi"
  target_key_id = aws_kms_key.phi.key_id
}

data "aws_caller_identity" "current" {}

# ── EKS Cluster ───────────────────────────────────────────────────────────────

module "eks" {
  source = "./modules/eks"

  cluster_name    = var.cluster_name
  cluster_version = "1.30"
  vpc_id          = aws_vpc.main.id
  subnet_ids      = aws_subnet.private[*].id

  node_groups = {
    general = {
      instance_types = ["m6i.xlarge"]
      min_size       = 3
      max_size       = 12
      desired_size   = 6
      capacity_type  = "ON_DEMAND"
      disk_size      = 100
      labels = {
        role = "general"
      }
    }
    ml_inference = {
      instance_types = ["c6i.2xlarge"]
      min_size       = 2
      max_size       = 8
      desired_size   = 3
      capacity_type  = "SPOT"
      disk_size      = 100
      labels = {
        role        = "ml-inference"
        "ml/gpu"    = "false"
      }
      taints = [{
        key    = "ml-inference"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }
  }

  tags = { Environment = var.environment }
}

# ── RDS PostgreSQL ─────────────────────────────────────────────────────────────

module "rds" {
  source = "./modules/rds"

  identifier        = "neuroguard-postgres"
  engine_version    = "16.2"
  instance_class    = "db.r6g.xlarge"
  allocated_storage = 100
  max_storage       = 500

  db_name  = "neuroguard"
  username = "neuroguard_app"
  password = var.db_password

  vpc_id             = aws_vpc.main.id
  subnet_ids         = aws_subnet.private[*].id
  kms_key_id         = aws_kms_key.phi.arn

  multi_az               = true
  backup_retention_days  = 35  # HIPAA requires 6-year audit logs; RDS backups 35 days
  deletion_protection    = true
  storage_encrypted      = true
  performance_insights   = true

  tags = { Environment = var.environment }
}

# ── ElastiCache Redis ──────────────────────────────────────────────────────────

module "elasticache" {
  source = "./modules/elasticache"

  cluster_id        = "neuroguard-redis"
  node_type         = "cache.r6g.large"
  num_cache_nodes   = 3
  engine_version    = "7.1"
  at_rest_encrypted = true
  transit_encrypted = true
  kms_key_id        = aws_kms_key.phi.arn

  vpc_id     = aws_vpc.main.id
  subnet_ids = aws_subnet.private[*].id

  tags = { Environment = var.environment }
}

# ── S3 Buckets ─────────────────────────────────────────────────────────────────

module "s3" {
  source = "./modules/s3"

  reports_bucket_name = "neuroguard-reports-${var.environment}"
  models_bucket_name  = "neuroguard-models-${var.environment}"
  audit_bucket_name   = "neuroguard-audit-${var.environment}"
  kms_key_arn         = aws_kms_key.phi.arn

  tags = { Environment = var.environment }
}

# ── IAM — IRSA for EKS pods ────────────────────────────────────────────────────

data "aws_iam_openid_connect_provider" "eks" {
  url = module.eks.cluster_oidc_issuer_url
}

resource "aws_iam_role" "neuroguard_app" {
  name = "neuroguard-app-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = data.aws_iam_openid_connect_provider.eks.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${replace(data.aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:neuroguard:neuroguard-app"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "neuroguard_app" {
  name = "neuroguard-app-policy"
  role = aws_iam_role.neuroguard_app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::neuroguard-reports-${var.environment}/*",
          "arn:aws:s3:::neuroguard-reports-${var.environment}",
          "arn:aws:s3:::neuroguard-models-${var.environment}/*",
          "arn:aws:s3:::neuroguard-models-${var.environment}"
        ]
      },
      {
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
        Resource = aws_kms_key.phi.arn
      },
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:neuroguard/*"
      },
      {
        Effect = "Allow"
        Action = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = "*"
        Condition = {
          StringLike = {
            "ses:FromAddress" = "*@neuroguard.health"
          }
        }
      }
    ]
  })
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "eks_cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = module.eks.cluster_endpoint
  sensitive   = true
}

output "rds_endpoint" {
  description = "PostgreSQL RDS endpoint"
  value       = module.rds.endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = module.elasticache.endpoint
  sensitive   = true
}

output "reports_bucket" {
  description = "S3 bucket for PDF reports"
  value       = module.s3.reports_bucket_name
}

output "models_bucket" {
  description = "S3 bucket for ML models"
  value       = module.s3.models_bucket_name
}

output "kms_key_arn" {
  description = "KMS key ARN for PHI encryption"
  value       = aws_kms_key.phi.arn
  sensitive   = true
}
