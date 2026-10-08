# Monitoring and operations

The stack collects application/host/runtime metrics every 15 seconds and provisions the Grafana operations dashboard automatically. Prometheus evaluates the committed rules, Alertmanager groups/delivers notifications, and Grafana shows metrics and external alert state. Monitoring is running on the assessment EC2 instance; live scrape targets, probes, runtime metrics, dashboard access and alert-rule evaluation passed the [deployment verification](aws/DEPLOYMENT_VERIFICATION.md). External notification delivery remains disabled until an operations webhook is configured.

## Metrics and why they matter

| Signal | Implementation / purpose |
| --- | --- |
| Request rate | Rate of `http_server_requests_seconds_count` for `/api/*`; tracks API traffic and supports error-rate interpretation |
| Error rate | API 5xx / all API requests; ignores health/scrape traffic and client mistakes |
| Latency | Histogram p95 from `http_server_requests_seconds_bucket`; detects slow DB/external dependencies |
| Readiness and scrape health | Blackbox probes `/readyz` (includes DB) and frontend `/healthz`; `up` separately detects inaccessible metrics targets |
| CPU / memory / root disk | Node Exporter idle CPU rate, available RAM and root filesystem available bytes; detects resource pressure before failures |
| Application uptime / JVM heap | Micrometer process uptime and heap usage; explains restarts, JVM pressure and capacity |
| DB connections | Hikari active connections; indicates pool saturation and connection leaks |
| Container restarts / uptime / running | Docker inspect counters, started timestamps and running state exported by the host collector, labeled by service and container ID |
| Alert state | `ALERTS{alertstate="firing"}` and the Alertmanager data source; makes incidents visible in Grafana |

The committed [dashboard JSON](monitoring/grafana-dashboard.json) includes all required request/error/latency, CPU/memory/disk, container restart and uptime panels. Classic HTTP histograms are explicitly enabled in the backend. App/management ports are private to Docker; Nginx exposes only API/static content and main-port health probes.

Container metrics come from `scripts/container-metrics.py`, invoked by `todo-metrics.timer` every 15 seconds on EC2. The script writes a textfile atomically to `/var/lib/todo/node-metrics/docker.prom`, which Node Exporter reads. This avoids mounting the Docker socket or using privileged cAdvisor in a monitoring container. A new container gets a new ID/counter, so planned replacement is not mistaken for a restart loop. Its uptime resets; retired IDs disappear on the next collection. CPU/memory panels report the host; per-container resource accounting is not included. Local runs require the documented collector command; on Docker Desktop host metrics describe the Linux VM.

## Alert thresholds and noise control

| Alert | Trigger | Delay | Response |
| --- | --- | --- | --- |
| ApplicationDown | Backend scrape absent/down or DB-inclusive readiness/frontend probe fails | 2 min | Inspect app/RDS/proxy; restore healthy release if regression |
| HighErrorRate | API 5xx ratio >5% AND >100 requests in 5 min | 5 min | Investigate exception/dependency; check recent deploy |
| HighCPU | Host CPU >85% | 10 min | Inspect JVM/load/credits, then capacity |
| LowDiskSpace | Root disk <15% free | 10 min | Inspect log/image/metric storage and retention |
| ContainerRestartLoop | More than 3 backend/frontend restarts in 15 min | 2 min | Check OOM/exit code; rollback if release-related |
| ContainerMetricsStale | Host Docker collection older than 120 sec or missing | 5 min | Repair timer/export path; distinguish local collector not started |
| HostMetricsDown | Node Exporter missing/down | 5 min | Inspect exporter and scrape configuration |

The outage/CPU and healthy/low-traffic cases have Prometheus rule tests in `monitoring/alert-tests.yml`. Short startup gaps, planned replacement counters, brief CPU spikes, low-volume 5xx events, expected 4xx responses and individual integration request failures should not page. They remain visible in graphs/logs. Tune the thresholds against actual workload after deployment; the small assessment may not reach the error-rate traffic floor, so readiness and direct logs remain essential.

Alertmanager groups related alerts, waits 30 seconds before sending, repeats persistent incidents every four hours, sends recovery messages and inhibits HighErrorRate while ApplicationDown is already firing. Silence planned maintenance with an expiry and recorded reason. Avoid disabling rules indefinitely. A dedicated operations webhook can be set as `alert_slack_webhook_url` in the application secret: production rendering mounts it into Alertmanager without embedding it in YAML/Git. Without that key, rules still evaluate and alerts are visible locally, but **external delivery is disabled**. Test routing with a controlled non-production outage once credentials and a destination are configured; the repository tests do not send messages.

## Critical logs

Backend stdout/stderr: startup/configuration and DB connection failures, unhandled API exceptions, summary-provider/webhook errors and graceful shutdown. Nginx access/error logs: URI, status, proxy timing/errors and client request correlation. Docker state: exit codes, OOM flag and restart counts. EC2: cloud-init/bootstrap, Docker daemon and `todo-metrics.service` logs. Delivery: GitHub build/test output and SSM release/rollback status. AWS: RDS events, authentication/security changes and CloudTrail for IAM/secret/control-plane access.

Use `docker compose logs --tail=100` from the current release, `docker inspect` for process state and `journalctl -u todo-metrics.service` through an authorized SSM session. CI uses bounded diagnostic logs on failure. Docker logging is rotated at 10 MB ×3 files per container; Prometheus retains up to seven days or 2 GB, whichever limit is reached first. The EBS root has a low-disk alert. Keep images for the current and previous healthy releases when reclaiming space.

Do not log credentials, request bodies or secret responses. SQL value logging is disabled. The preserved upstream integration exception handling can include provider response bodies, so restrict log access and review/redact any sensitive provider diagnostics before sharing. This assessment has local logs/metrics only; export selected logs to CloudWatch and metrics to external durable storage before requiring incident evidence to survive an EC2 disk loss.

## Early detection and routine operations

Each push is tested before publishing and every deployment checks the actual frontend-to-backend-to-database path. Use dashboard trends for CPU/memory growth, latency and connection pressure before a threshold fires. Review ECR findings, patch supported base images/dependencies and confirm secret rotation/redeployment behavior. Check restart metrics freshness as well as scrape health so a broken collector is not silently ignored.

After provisioning, verify all five Prometheus targets are healthy, both Blackbox probes succeed, the Grafana dashboard loads, and restart/uptime panels contain runtime samples. Generate only disposable CRUD traffic when checking API metrics. Confirm an alert reaches its intended channel and resolves after recovery. Run rollback, reboot and RDS restore drills, recording recovery time and lost-write exposure. Review alerts after incidents to remove duplicates and strengthen missed signals.

A monitoring stack on the same EC2 host cannot alert when that entire host is down. Add an external application probe and CloudWatch EC2 status/RDS storage/connection/CPU alarms with an independent notification path. These external checks are recommended follow-up setup and are not claimed as provisioned here. Multi-AZ, autoscaling and external log/metric storage are similarly deliberate extensions beyond the small assessment footprint.

Operational recovery commands and their limits are in [FAILURE_AND_ROLLBACK.md](FAILURE_AND_ROLLBACK.md); networking, IAM, port-forwarding and cleanup are in [AWS setup](aws/aws-setup.md).
