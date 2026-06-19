variable "reports_bucket_name" { type = string }
variable "models_bucket_name" { type = string }
variable "audit_bucket_name" { type = string }
variable "kms_key_arn" { type = string }
variable "tags" { type = map(string); default = {} }

# ── Helper locals ──────────────────────────────────────────────────────────────

locals {
  buckets = {
    reports = var.reports_bucket_name
    models  = var.models_bucket_name
    audit   = var.audit_bucket_name
  }
}

# ── S3 Buckets ─────────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "buckets" {
  for_each = local.buckets
  bucket   = each.value
  tags     = var.tags
}

resource "aws_s3_bucket_versioning" "buckets" {
  for_each = local.buckets
  bucket   = aws_s3_bucket.buckets[each.key].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "buckets" {
  for_each = local.buckets
  bucket   = aws_s3_bucket.buckets[each.key].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "buckets" {
  for_each = local.buckets
  bucket   = aws_s3_bucket.buckets[each.key].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── Lifecycle Rules ────────────────────────────────────────────────────────────

# Reports: move to Glacier after 1 year, expire after 7 years (HIPAA)
resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  bucket = aws_s3_bucket.buckets["reports"].id

  rule {
    id     = "reports-lifecycle"
    status = "Enabled"

    transition {
      days          = 365
      storage_class = "GLACIER"
    }

    expiration {
      days = 2555  # ~7 years
    }
  }
}

# Audit logs: move to Glacier after 90 days, retain 6 years (HIPAA §164.530)
resource "aws_s3_bucket_lifecycle_configuration" "audit" {
  bucket = aws_s3_bucket.buckets["audit"].id

  rule {
    id     = "audit-lifecycle"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 2190  # 6 years
    }
  }
}

# ── Audit Bucket — Object Lock for immutability (HIPAA) ───────────────────────

resource "aws_s3_bucket_object_lock_configuration" "audit" {
  bucket = aws_s3_bucket.buckets["audit"].id

  rule {
    default_retention {
      mode = "GOVERNANCE"
      days = 2190
    }
  }
}

# ── CORS for reports bucket (presigned URLs) ───────────────────────────────────

resource "aws_s3_bucket_cors_configuration" "reports" {
  bucket = aws_s3_bucket.buckets["reports"].id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET"]
    allowed_origins = ["https://app.neuroguard.health", "https://dashboard.neuroguard.health"]
    max_age_seconds = 3600
  }
}

# ── Outputs ────────────────────────────────────────────────────────────────────

output "reports_bucket_name" {
  value = aws_s3_bucket.buckets["reports"].bucket
}

output "models_bucket_name" {
  value = aws_s3_bucket.buckets["models"].bucket
}

output "audit_bucket_name" {
  value = aws_s3_bucket.buckets["audit"].bucket
}
