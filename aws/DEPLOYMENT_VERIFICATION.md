# Live AWS deployment verification

Verified on 8 October 2026. This records the initial successful deployment; later successful `main` pushes can advance the active release.

## Deployment evidence

| Item | Verified value |
| --- | --- |
| Region | `us-east-1` |
| Application | [http://184.196.22.243](http://184.196.22.243), restricted to the configured operator/reviewer CIDR |
| EC2 | `i-0e226d976d1e6e227`, `t3.small`, Amazon Linux 2023 |
| Database | `todo-summary-mysql`, RDS MySQL 8.4.9, `db.t3.micro`, private and encrypted |
| Release | `17568c7cb2ba839ac13cb4a6fba90c50aec69f40` |
| CI/CD | [Successful full workflow, including ECR publication and SSM deployment](https://github.com/Chandu378/TodoSummaryAssistant-DevOps/actions/runs/37813644635) |
| Live host verification | SSM command `22ac1530-66c4-4e2b-9507-53857cf6a1fe`: `Success` |
| Infrastructure consistency | `terraform plan -detailed-exitcode`: exit 0, no changes |

Both immutable ECR tags match the release SHA:

| Repository | Image digest |
| --- | --- |
| `todo-summary-backend` | `sha256:321c091c3e406eb1acb5a64d8aed0177a5ec32829b022c6d8770b73566594926` |
| `todo-summary-frontend` | `sha256:322593a07c94e2ef8c3f8d0c8feaf952a2f08accbc89a210f442cce24384e29b` |

## Checks that passed

- Fresh-instance cloud-init completed successfully. Docker Compose 2.39.4, AWS CLI v2, Docker and the SSM agent were available.
- The workflow passed Java/React tests, operations tests, shell checks, Terraform validation and tracked-file credential-pattern checks.
- CI tested real MySQL CRUD through Nginx, exact production secret handling, non-root application users, monitoring configuration, dashboard provisioning and alert-rule behavior.
- GitHub obtained temporary AWS credentials through OIDC, published both images, uploaded the matching configuration bundle/checksum, and deployed through the custom SHA-only SSM document.
- The deployed `/healthz`, `/readyz` and `/api/todos` checks passed. Both application containers were healthy.
- `scripts/smoke-test.py` passed against the public HTTP endpoint from the allowed IP and again on EC2: frontend HTML, database readiness, create, read, update and delete. Each temporary test todo was removed.
- All five Prometheus targets were healthy. Readiness probes succeeded and container restart/uptime metrics were present.
- Authenticated Grafana access verified the provisioned `todo-operations` dashboard.
- All seven live alert rules evaluated successfully: ApplicationDown, HighErrorRate, HighCPU, LowDiskSpace, ContainerRestartLoop, ContainerMetricsStale and HostMetricsDown. Alertmanager was ready.
- The backend and frontend ran as non-root users. Docker, the SSM agent and `todo-metrics.timer` were active.
- Live security groups allowed only HTTP from the configured CIDR and MySQL from the EC2 security group. RDS was not publicly accessible; backups retained seven days and deletion protection was enabled.
- IAM simulation returned `implicitDeny` for the GitHub role retrieving the application secret. The OIDC trust matches this repository's immutable owner/repository IDs and only `main`.

The application uses plain HTTP for this restricted assessment endpoint. The automated browser preview was blocked by the browser URL policy, so browser interaction is not claimed as verified. HTTP/API and host checks passed independently.

## Repeat the checks

From the allowed public IP, at the repository root:

```bash
SMOKE_BASE_URL=http://184.196.22.243 python3 scripts/smoke-test.py
```

On EC2 through an authorized SSM operator session:

```bash
SMOKE_BASE_URL=http://127.0.0.1 python3 /opt/todo/current/scripts/smoke-test.py
sudo python3 /opt/todo/current/scripts/container-metrics.py
sudo bash -c 'GRAFANA_ADMIN_PASSWORD="$(cat /opt/todo/current/deploy/runtime/grafana-password)" python3 /opt/todo/current/scripts/check-monitoring.py'
```

Use the [SSM port-forwarding instructions](aws-setup.md#release-and-access-verification) to access Grafana, Prometheus and Alertmanager. The Grafana password is stored in the `todo-summary/application` secret; it is not in GitHub or this document.

## Remaining scope and running costs

Cohere summarization, application Slack posting and external alert notifications are pending real credentials, as requested. The secret contains empty integration values and a generated Grafana password. No verification check sends an external message.

Live fault-injection rollback, reboot recovery, notification delivery, Multi-AZ failover and snapshot restoration have not been exercised. Repository tests cover rollback behavior and alert expressions; these are not a substitute for recovery drills. The assessment remains a single EC2 / Single-AZ RDS deployment.

AWS resources remain running and can incur charges. See [cleanup](aws-setup.md#assumptions-costs-and-cleanup) after review. Terraform state and operator CIDR settings remain local and ignored by Git; preserve the state securely for later changes or cleanup.
