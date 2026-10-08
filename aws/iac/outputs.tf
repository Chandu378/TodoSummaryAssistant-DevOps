output "github_actions_variables" {
  value = {
    AWS_REGION          = var.region
    AWS_DEPLOY_ROLE_ARN = aws_iam_role.github.arn
    EC2_INSTANCE_ID     = aws_instance.app.id
    DEPLOY_DOCUMENT     = aws_ssm_document.deploy.name
    ECR_REGISTRY        = local.registry
    BACKEND_REPOSITORY  = aws_ecr_repository.backend.name
    FRONTEND_REPOSITORY = aws_ecr_repository.frontend.name
    ARTIFACT_BUCKET     = aws_s3_bucket.artifacts.id
  }
}
output "application_url" {
  value = "http://${aws_eip.app.public_ip}"
}
output "app_secret_arn" {
  value = aws_secretsmanager_secret.app.arn
}
output "rds_secret_arn" {
  value = aws_db_instance.mysql.master_user_secret[0].secret_arn
}
output "rds_endpoint" {
  value = aws_db_instance.mysql.endpoint
}
