variable "aws_region" {
  description = "AWS region for ECR"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name prefix"
  type        = string
  default     = "scorecheck"
}

variable "image_tag_mutability" {
  description = "ECR tag mutability"
  type        = string
  default     = "MUTABLE"
}

variable "scan_on_push" {
  description = "Enable ECR image scanning on push"
  type        = bool
  default     = true
}
