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
  description = "Base URL for the existing glass REST server."
  type        = string
  default     = "http://127.0.0.1:8765"
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
