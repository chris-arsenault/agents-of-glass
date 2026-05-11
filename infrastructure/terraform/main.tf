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

module "frontend" {
  source = "git::https://github.com/chris-arsenault/ahara-tf-patterns.git//modules/website"

  prefix         = var.prefix
  hostname       = var.hostname
  zone_name      = var.zone_name
  aliases        = var.aliases
  site_directory = "${path.root}/../../frontend/dist"

  runtime_config = {
    apiBaseUrl        = var.api_base_url
    defaultCampaignId = var.default_campaign_id
    pollIntervalMs    = var.poll_interval_ms
    playerOrder       = var.player_order
  }
}
