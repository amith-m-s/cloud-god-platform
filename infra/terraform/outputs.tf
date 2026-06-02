output "alb_dns_name" {
  value = aws_lb.app.dns_name
}

output "documents_bucket" {
  value = aws_s3_bucket.documents.bucket
}

output "document_jobs_queue_url" {
  value = aws_sqs_queue.document_jobs.url
}
