terraform {
  required_version = ">= 1.14"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    region       = "us-east-1"
    key          = "projects/agents-of-glass.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "AgentsOfGlass"
      ManagedBy = "Terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

module "ctx" {
  source = "git::https://github.com/chris-arsenault/ahara-tf-patterns.git//modules/platform-context"
}

data "aws_ssm_parameter" "db_username" {
  name = "/ahara/db/${var.prefix}/username"
}

data "aws_ssm_parameter" "db_password" {
  name = "/ahara/db/${var.prefix}/password"
}

data "aws_ssm_parameter" "db_database" {
  name = "/ahara/db/${var.prefix}/database"
}

locals {
  api_base_url = coalesce(var.api_base_url, "https://${var.api_hostname}")
  campaign_publisher_principal_arns = length(var.campaign_publisher_principal_arns) > 0 ? var.campaign_publisher_principal_arns : [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
  ]
}

resource "aws_s3_bucket" "campaign_mirror" {
  bucket = var.campaign_bucket_name
}

resource "aws_s3_bucket_public_access_block" "campaign_mirror" {
  bucket                  = aws_s3_bucket.campaign_mirror.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "campaign_mirror" {
  bucket = aws_s3_bucket.campaign_mirror.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_iam_policy_document" "campaign_publisher_assume" {
  statement {
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = local.campaign_publisher_principal_arns
    }

    actions = ["sts:AssumeRole"]
  }
}

data "aws_iam_policy_document" "campaign_publisher" {
  statement {
    sid    = "ListCampaignMirror"
    effect = "Allow"

    actions = [
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads",
    ]

    resources = [aws_s3_bucket.campaign_mirror.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${var.campaign_prefix}/*"]
    }
  }

  statement {
    sid    = "WriteCampaignMirror"
    effect = "Allow"

    actions = [
      "s3:AbortMultipartUpload",
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:ListMultipartUploadParts",
      "s3:PutObject",
    ]

    resources = ["${aws_s3_bucket.campaign_mirror.arn}/${var.campaign_prefix}/*"]
  }
}

resource "aws_iam_role" "campaign_publisher" {
  name               = "${var.prefix}-campaign-publisher"
  assume_role_policy = data.aws_iam_policy_document.campaign_publisher_assume.json
}

resource "aws_iam_role_policy" "campaign_publisher" {
  name   = "${var.prefix}-campaign-publisher"
  role   = aws_iam_role.campaign_publisher.id
  policy = data.aws_iam_policy_document.campaign_publisher.json
}

data "aws_iam_policy_document" "viewer_api_lambda" {
  statement {
    sid    = "ListCampaignMirror"
    effect = "Allow"

    actions = ["s3:ListBucket"]

    resources = [aws_s3_bucket.campaign_mirror.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${var.campaign_prefix}/*"]
    }
  }

  statement {
    sid    = "GetCampaignMirrorObjects"
    effect = "Allow"

    actions = ["s3:GetObject"]

    resources = [
      "${aws_s3_bucket.campaign_mirror.arn}/${var.campaign_prefix}/*",
    ]
  }
}

module "api" {
  source = "git::https://github.com/chris-arsenault/ahara-tf-patterns.git//modules/alb-api"

  prefix    = var.prefix
  hostname  = var.api_hostname
  zone_name = var.zone_name
  vpc       = module.ctx.vpc
  alb       = module.ctx.alb

  environment = {
    DB_HOST              = module.ctx.rds.address
    DB_PORT              = module.ctx.rds.port
    DB_USERNAME          = nonsensitive(data.aws_ssm_parameter.db_username.value)
    DB_PASSWORD          = nonsensitive(data.aws_ssm_parameter.db_password.value)
    DB_NAME              = nonsensitive(data.aws_ssm_parameter.db_database.value)
    DB_SSLMODE           = "require"
    CAMPAIGN_BUCKET      = aws_s3_bucket.campaign_mirror.bucket
    CAMPAIGN_PREFIX      = var.campaign_prefix
    RUST_LOG             = var.viewer_api_log_level
    S3_CACHE_TTL_SECONDS = tostring(var.s3_cache_ttl_seconds)
    S3_CACHE_MAX_ENTRIES = tostring(var.s3_cache_max_entries)
  }

  iam_policy = [data.aws_iam_policy_document.viewer_api_lambda.json]

  lambdas = {
    viewer-api = {
      binary = "${path.root}/../../backend/target/lambda/viewer-api/bootstrap"
      routes = [
        {
          priority      = var.api_listener_priority
          paths         = ["/*"]
          authenticated = false
        }
      ]
    }
  }
}

module "frontend" {
  source = "git::https://github.com/chris-arsenault/ahara-tf-patterns.git//modules/website"

  prefix         = var.prefix
  hostname       = var.hostname
  zone_name      = var.zone_name
  aliases        = var.aliases
  site_directory = "${path.root}/../../frontend/dist"

  runtime_config = {
    apiBaseUrl     = local.api_base_url
    pollIntervalMs = tostring(var.poll_interval_ms)
    playerOrder    = join(",", var.player_order)
  }
}
