output "alb_dns_name" {
  description = "DNS name of the load balancer"
  value       = aws_lb.docvault.dns_name
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.docvault.endpoint
  sensitive   = true
}

output "s3_bucket_name" {
  description = "S3 bucket for uploads"
  value       = aws_s3_bucket.uploads.bucket
}

output "cost_estimate" {
  description = "Estimated monthly cost"
  value       = "~$0-5/month with AWS Free Tier + GitHub Student Pack"
}