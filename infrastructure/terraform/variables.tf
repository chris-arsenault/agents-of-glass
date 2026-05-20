variable "aws_region" {
  description = "AWS region for project resources."
  type        = string
  default     = "us-east-1"
}

variable "prefix" {
  description = "Ahara-managed resource prefix."
  type        = string
  default     = "agents-of-glass"
}

variable "hostname" {
  description = "Primary hostname for the web UI."
  type        = string
  default     = "agents-of-glass.ahara.io"
}

variable "zone_name" {
  description = "Route53 hosted zone name. Null lets the website module derive it from hostname."
  type        = string
  default     = null
}

variable "aliases" {
  description = "Additional hostnames served by the same CloudFront distribution."
  type        = list(string)
  default     = []
}

variable "api_base_url" {
  description = "Base URL for the hosted Rust viewer API. Null derives it from api_hostname."
  type        = string
  default     = null
}

variable "api_hostname" {
  description = "Primary hostname for the Rust viewer API."
  type        = string
  default     = "api.agents-of-glass.ahara.io"
}

variable "api_listener_priority" {
  description = "Shared ALB listener rule priority for the API hostname."
  type        = number
  default     = 210
}

variable "campaign_bucket_name" {
  description = "S3 bucket that stores the published campaign file mirror."
  type        = string
  default     = "agents-of-glass-campaign-mirror"
}

variable "campaign_prefix" {
  description = "S3 key prefix under the campaign mirror bucket."
  type        = string
  default     = "campaigns"
}

variable "campaign_publisher_principal_arns" {
  description = "AWS principal ARNs allowed to assume the restricted campaign publisher role. Empty defaults to this account root."
  type        = list(string)
  default     = []
}

variable "viewer_api_log_level" {
  description = "Rust tracing filter for the viewer API Lambda."
  type        = string
  default     = "info"
}

variable "s3_cache_ttl_seconds" {
  description = "Warm Lambda in-memory cache TTL for S3 JSON objects."
  type        = number
  default     = 15
}

variable "s3_cache_max_entries" {
  description = "Maximum S3 JSON objects cached per warm Lambda instance."
  type        = number
  default     = 512
}

variable "poll_interval_ms" {
  description = "Dashboard polling interval in milliseconds."
  type        = number
  default     = 120000
}

variable "player_order" {
  description = "Four player ids to pin in the player row."
  type        = list(string)
  default     = ["tev", "sumi", "renno", "kit"]
}
