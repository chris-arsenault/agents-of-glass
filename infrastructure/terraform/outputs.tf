output "site_url" {
  description = "Frontend URL."
  value       = module.frontend.url
}

output "frontend_bucket_name" {
  description = "S3 bucket used by the frontend deployment."
  value       = module.frontend.bucket_name
}

output "api_url" {
  description = "Hosted Rust viewer API URL."
  value       = "https://${module.api.hostname}"
}

output "campaign_mirror_bucket_name" {
  description = "S3 bucket used for the campaign file mirror."
  value       = aws_s3_bucket.campaign_mirror.bucket
}

output "campaign_publisher_role_arn" {
  description = "Restricted IAM role used by the local campaign mirror publisher."
  value       = aws_iam_role.campaign_publisher.arn
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution id."
  value       = module.frontend.distribution_id
}
