#!/usr/bin/env python3
"""Fetch secrets using the EC2 instance role and write private runtime config."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def secret(arn, region):
    result = subprocess.run(
        ["aws", "secretsmanager", "get-secret-value", "--secret-id", arn,
         "--region", region, "--query", "SecretString", "--output", "text"],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def dotenv(values, raw=False):
    lines = []
    for key, value in values.items():
        value = str(value)
        if any(c in value for c in "\r\n\0"):
            raise ValueError(f"{key} must be a single line")
        # Production backend env_file uses Compose's raw format to preserve all secrets.
        lines.append(key + "=" + value if raw else key + "='" + value.replace("'", "\\'") + "'")
    return "\n".join(lines) + "\n"


def write_private(path, content, mode=0o600):
    path.write_text(content)
    path.chmod(mode)


def render(config, release, directory, db, app):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    password = app["grafana_admin_password"]
    if len(password) < 16:
        raise ValueError("grafana_admin_password must contain at least 16 characters")
    backend = {
        "DB_URL": f'jdbc:mysql://{config["rds_endpoint"]}/todo?sslMode=REQUIRED',
        "DB_USERNAME": db["username"], "DB_PASSWORD": db["password"],
        "COHERE_API_KEY": app["cohere_api_key"],
        "SLACK_WEBHOOK_URL": app["slack_webhook_url"],
        "CORS_ALLOWED_ORIGINS": config.get("cors_allowed_origins", "http://localhost:3000"),
        "DDL_AUTO": "update", "DB_POOL_SIZE": "5", "MANAGEMENT_PORT": "8081",
    }
    write_private(directory / "backend.env", dotenv(backend, raw=True))
    write_private(directory / "grafana-password", password, 0o644)
    compose = {
        "ECR_REGISTRY": config["ecr_registry"], "RELEASE_SHA": release,
        "BACKEND_REPOSITORY": config["backend_repository"],
        "FRONTEND_REPOSITORY": config["frontend_repository"],
        "GRAFANA_ADMIN_USER": "admin",
    }
    write_private(directory / "compose.env", dotenv(compose))
    webhook = app.get("alert_slack_webhook_url", "")
    if webhook:
        if not webhook.startswith("https://hooks.slack.com/") or any(c in webhook for c in "\r\n\0"):
            raise ValueError("alert_slack_webhook_url must be a valid Slack webhook URL")
        # Parent directory is root-only on the host. The bind-mounted file is readable by nobody.
        write_private(directory / "alert-webhook", webhook + "\n", 0o644)
        receiver = '''  - name: operations
    slack_configs:
      - api_url_file: /run/secrets/alert-webhook
        send_resolved: true
        title: '{{ .CommonLabels.alertname }} ({{ .Status }})'
        text: '{{ range .Alerts }}{{ .Annotations.summary }} — {{ .Annotations.description }}{{ "\\n" }}{{ end }}'
'''
    else:
        write_private(directory / "alert-webhook", "", 0o644)
        receiver = "  - name: operations\n"
    content = '''route:
  receiver: operations
  group_by: [alertname, instance]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
receivers:
''' + receiver + '''inhibit_rules:
  - source_matchers: ['alertname="ApplicationDown"']
    target_matchers: ['alertname="HighErrorRate"']
    equal: [project]
'''
    write_private(directory / "alertmanager.yml", content, 0o644)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/etc/todo/config.json")
    parser.add_argument("--release", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    config = json.loads(Path(args.config).read_text())
    render(config, args.release, args.output,
           secret(config["rds_secret_arn"], config["region"]),
           secret(config["app_secret_arn"], config["region"]))


if __name__ == "__main__":
    main()
