variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "name" {
  type    = string
  default = "todo-summary"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,24}$", var.name))
    error_message = "Use 3–25 lowercase letters, digits or hyphens, beginning with a letter."
  }
}

variable "github_repository" {
  type    = string
  default = "Chandu378/TodoSummaryAssistant-DevOps"
  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "Use owner/repository."
  }
}

variable "allowed_http_cidr" {
  type        = string
  description = "Reviewer/operator public IPv4 CIDR, normally a /32. HTTP is restricted because the upstream app has no authentication."
  validation {
    condition     = can(cidrnetmask(var.allowed_http_cidr)) && var.allowed_http_cidr != "0.0.0.0/0"
    error_message = "Provide a restricted IPv4 CIDR rather than 0.0.0.0/0."
  }
}

variable "instance_type" {
  type    = string
  default = "t3.small"
}

variable "db_instance_class" {
  type    = string
  default = "db.t3.micro"
}

variable "db_multi_az" {
  type    = bool
  default = false
}

variable "db_deletion_protection" {
  type    = bool
  default = true
}

variable "existing_github_oidc_provider_arn" {
  type        = string
  default     = ""
  description = "Set to reuse an account's existing token.actions.githubusercontent.com provider."
}

variable "cors_allowed_origins" {
  type    = string
  default = "http://localhost:3000"
}
