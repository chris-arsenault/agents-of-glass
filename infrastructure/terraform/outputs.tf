output "site_url" {
  description = "Frontend URL."
  value       = module.frontend.url
}

output "frontend_bucket_name" {
  description = "S3 bucket used by the frontend deployment."
  value       = module.frontend.bucket_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution id."
  value       = module.frontend.distribution_id
}
