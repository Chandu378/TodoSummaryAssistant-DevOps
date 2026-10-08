resource "aws_instance" "app" {
  ami                    = data.aws_ssm_parameter.ami.value
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  user_data = templatefile("${path.module}/user-data.sh.tftpl", {
    runtime_config = jsonencode(local.runtime_config)
    launcher       = file("${path.module}/../../scripts/launch-release.sh")
    metrics_unit   = file("${path.module}/../../deploy/todo-metrics.service")
    metrics_timer  = file("${path.module}/../../deploy/todo-metrics.timer")
  })
  user_data_replace_on_change = true
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    encrypted             = true
    delete_on_termination = true
  }
  depends_on = [aws_route_table_association.public, aws_iam_role_policy.ec2, aws_iam_role_policy_attachment.ssm]
  tags       = { Name = var.name }
}

resource "aws_eip" "app" {
  domain     = "vpc"
  instance   = aws_instance.app.id
  depends_on = [aws_internet_gateway.main]
}

resource "aws_ssm_document" "deploy" {
  name            = "${var.name}-deploy"
  document_type   = "Command"
  document_format = "JSON"
  content = jsonencode({
    schemaVersion = "2.2"
    description   = "Deploy a SHA-tagged Todo release; rollback on failed health checks"
    parameters = {
      Revision = {
        type = "String", description = "Full commit SHA", allowedPattern = "^[a-f0-9]{40}$", interpolationType = "ENV_VAR"
      }
    }
    mainSteps = [{
      action = "aws:runShellScript", name = "deploy"
      inputs = { timeoutSeconds = "900", runCommand = ["set -eu", "cloud-init status --wait", "/usr/local/bin/todo-release \"$SSM_Revision\""] }
    }]
  })
}
