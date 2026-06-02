variable "region" {
  description = "AWS region for all resources"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  default     = "cloud-god-platform"
}

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.40.0.0/16"
}

variable "container_image" {
  description = "Docker image URI for the API container"
  type        = string
  default     = "public.ecr.aws/docker/library/python:3.11-slim"
}

variable "api_desired_count" {
  description = "Desired number of API ECS tasks"
  type        = number
  default     = 2
}

variable "api_min_count" {
  description = "Minimum number of API ECS tasks for auto-scaling"
  type        = number
  default     = 1
}

variable "api_max_count" {
  description = "Maximum number of API ECS tasks for auto-scaling"
  type        = number
  default     = 6
}
