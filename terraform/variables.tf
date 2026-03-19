variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name prefix for resources"
  type        = string
  default     = "scorecheck"
}

variable "domain_name" {
  description = "Domain name for the application (e.g. scorecheck.ca)"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3a.small"
}

variable "repository_url" {
  description = "Git repository URL to clone on EC2"
  type        = string
  default     = "https://github.com/JamalAbdi/scorecheck.git"
}

variable "repository_branch" {
  description = "Git branch to deploy on EC2"
  type        = string
  default     = "reduce-costs"
}

variable "use_spot" {
  description = "Use a spot instance to save costs (may be interrupted)"
  type        = bool
  default     = true
}
