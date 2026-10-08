# Todo Summary Assistant — DevOps assessment

[![CI and EC2 delivery](https://github.com/Chandu378/TodoSummaryAssistant-DevOps/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Chandu378/TodoSummaryAssistant-DevOps/actions/workflows/ci-cd.yml)

The original [Todo Summary Assistant](https://github.com/Praj122/TodoSummaryAssistant) is a Spring Boot/React application that manages todos, summarizes pending tasks using Cohere, and posts the summary to Slack. This repository adds Docker delivery, AWS infrastructure, monitoring and recovery procedures while preserving its CRUD and summary business logic.

**Submission status:** deployed and verified on AWS EC2 with private RDS in `us-east-1`. GitHub builds, tests, publishes SHA-tagged images to ECR and deploys through SSM. Live frontend readiness, RDS-backed CRUD, Prometheus targets, runtime metrics, Grafana provisioning and alert-rule evaluation passed. See the [deployment verification record](aws/DEPLOYMENT_VERIFICATION.md) for evidence and test scope. Cohere/Slack credentials and external alert delivery remain pending. This is a single-instance assessment deployment, with the availability limitations described below.

The [live application](http://184.196.22.243) is accessible only from the configured operator/reviewer public IP range. Use the explicit `http://` URL; HTTPS is not configured for this restricted assessment endpoint.

## Project and runtime

| Component | Runtime | Source |
| --- | --- | --- |
| Backend | Java 17, Spring Boot 3.4.5, Maven wrapper 3.9.9 | `Backend/todo-summary-assistant/` |
| Frontend | Node.js 22 for building, React 19, Nginx for serving | `Frontend/todo/` |
| Database | MySQL 8.4; local container or private AWS RDS | Local Compose / `aws/iac/` |
| Monitoring | Prometheus, Grafana, Node Exporter, Blackbox Exporter, Alertmanager | `monitoring/` |

### Local Docker run

Install Docker Engine/Desktop with **Compose 2.30 or newer** and Git. Allow at least 4 GB RAM for local builds.

```bash
git clone https://github.com/Chandu378/TodoSummaryAssistant-DevOps.git
cd TodoSummaryAssistant-DevOps
cp .env.example .env
# Edit .env: set distinct DB, MySQL root and Grafana passwords.
docker compose up -d --build --wait --wait-timeout 300
python3 scripts/smoke-test.py
```

Open the application at `http://localhost:3000`, Grafana at `http://localhost:3001` (admin / your configured password), Prometheus at `http://localhost:9090`, and Alertmanager at `http://localhost:9093`. The dashboard is automatically provisioned under **Todo → Todo Summary Assistant — Operations**. MySQL is bound only to `127.0.0.1:3306`. The backend and its management port are accessible only within the Docker network.

Node Exporter reports the **Linux Docker host**; on Docker Desktop this is the Linux VM, not macOS. For container restart/uptime panels during local runs, periodically run:

```bash
python3 scripts/container-metrics.py --output deploy/runtime/node-metrics/docker.prom
```

EC2 installs a systemd timer to collect these metrics every 15 seconds automatically. Local alerts are visible without sending notifications. See [monitoring and operations](MONITORING_AND_OPERATIONS.md) for alert delivery.

```bash
docker compose logs --tail=100 backend frontend
docker compose down
# Only for disposable LOCAL test data: docker compose down --volumes
```

Named volumes preserve local MySQL and monitoring data across normal shutdowns. Changing MySQL environment passwords does not change an already initialized database; update the database credentials explicitly or recreate only disposable local volumes.

### Native development

Install JDK 17, Git, Node.js 22/npm and a MySQL 8.4 database. Spring does **not** automatically read `.env` files; export the variables into your shell. One way to get a development database is:

```bash
cp .env.example .env
# Edit the passwords before running.
docker compose up -d mysql
set -a
. ./.env
set +a
export DB_URL=jdbc:mysql://localhost:3306/todo
cd Backend/todo-summary-assistant
./mvnw spring-boot:run
```

For an existing MySQL installation, create the `todo` database and a user with permissions on that database, then set `DB_URL`, `DB_USERNAME` and `DB_PASSWORD`. On macOS, if the wrapper cannot locate Java, set `JAVA_HOME` to your JDK 17 installation.

In another terminal:

```bash
cd Frontend/todo
cp .env.example .env
npm ci
npm start
```

The native backend listens on port 8080, the development frontend on 3000, and management on 8081. Production uses the same-origin Nginx proxy, so the browser never tries to call its own localhost as the backend.

## Configuration

Never put credentials in `application.properties`, Dockerfiles, GitHub variables or frontend settings. `.env` files, Terraform state and private keys are ignored by Git and excluded from Docker build contexts. Real Cohere and Slack credentials are required only for the summarize action; CRUD and health checks run with empty integration values. Neither tests nor smoke checks send a Slack message.

| Variable | Purpose / default |
| --- | --- |
| `DB_URL` | JDBC URL; local Compose points to `mysql:3306/todo`, native development to localhost |
| `DB_USERNAME`, `DB_PASSWORD` | Database credentials; required |
| `MYSQL_DATABASE`, `MYSQL_ROOT_PASSWORD` | Local MySQL initialization only; production has no database container |
| `COHERE_API_KEY` | Backend-only Cohere credential |
| `SLACK_WEBHOOK_URL` | Backend-only application Slack webhook; replaces the upstream `YOUR_WEBHOOK_URL` placeholder |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins for native development; default `http://localhost:3000` |
| `DDL_AUTO` | Hibernate schema mode; `update` retains upstream initialization behavior |
| `DB_POOL_SIZE` | JDBC pool limit, default 5 |
| `MANAGEMENT_PORT` | Internal Actuator port, 8081 in Compose |
| `APP_PORT` | Local frontend host port, default 3000; production uses 80 |
| `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD` | Local Grafana credentials; production uses a mounted password file |
| `REACT_APP_API_BASE_URL` | Public **build-time** frontend setting, default `/api/todos`; native development uses `http://localhost:8080/api/todos` |

AWS deployment variables, secret JSON keys and runtime-only settings are listed in [AWS setup](aws/aws-setup.md). Credentials are fetched through the EC2 instance role into root-owned runtime files. Backend secrets use Compose's raw env-file format, preserving dollar signs, quotes and backslashes. Grafana and alert webhooks are mounted as secret files; secret contents are never Terraform input values.

## Docker design

Both application Dockerfiles have a separate build stage and a smaller runtime stage. Maven/Node build tools and dependency caches do not enter the final image. BuildKit caches speed up dependency installation; npm uses the committed lockfile. The backend runs as UID 10001 on a JRE and the frontend as UID 101 using unprivileged Nginx on port 8080. Compose drops application capabilities, uses a read-only root filesystem with `/tmp` scratch space, caps memory and rotates container logs.

Health checks exercise database readiness, and Java handles graceful termination. Monitoring images use fixed release tags. Application images are published to immutable ECR tags using the full Git commit SHA. Before a broader production rollout, update supported patch versions, review ECR scan findings and pin base images by digest. Docker health status signals a failure; it does not itself restart a still-running process.

## CI/CD stages

The [workflow](.github/workflows/ci-cd.yml) triggers on every branch push, pull requests to `main`, or manual dispatch.

1. **Validate:** build/test Java; install/test/build React; test secret rendering, metrics and rollback; run ShellCheck, Terraform format/validation and tracked-file credential-pattern checks.
2. **Containers:** validate Prometheus/Alertmanager configuration and alert tests; build both images; boot a real MySQL stack; test CRUD through Nginx, non-root users, metrics scraping and Grafana provisioning. Temporary volumes are removed after this CI test.
3. **Publish/deploy:** after the checks pass on `main`, assume the scoped AWS role using GitHub OIDC; publish SHA-tagged images to ECR; upload the matching deployment/monitoring bundle and checksum to private S3; invoke the custom SSM deployment document and wait for the result. This job is gated on `AWS_DEPLOY_ENABLED=true` for the one-time AWS setup.
4. **Health and rollback:** EC2 pulls images before changing running containers, starts the candidate, checks frontend health, database readiness and the API, then updates the current release pointer. Failure after changing containers restores the previous release and fails CI. Reruns reuse existing immutable tags.

There are no manual actions between a configured `main` push and deployment. Actions are pinned to immutable commits. Pull requests cannot obtain production AWS credentials. GitHub workflow concurrency plus a host lock serialize deployments. The AWS job does not require an inbound SSH port.

## AWS architecture and deployment

![AWS delivery and monitoring architecture](aws/architecture-diagram.png)

Use [AWS setup](aws/aws-setup.md) for the Terraform provisioning and one-time GitHub configuration. The network contains an EC2 instance in a public subnet and RDS in two isolated private subnets. RDS accepts MySQL only from the EC2 security group. HTTP is restricted to a reviewer/operator CIDR; admin and monitoring access use SSM. EC2 uses IMDSv2 with a hop limit of one so app containers cannot inherit its role credentials.

The default is a small assessment footprint, **not a promise of free-tier eligibility**: EC2, RDS, EBS, public IPv4, Secrets Manager and storage can incur charges. Multi-AZ is optional and off by default. The instance hosts the monitoring stack too, so an EC2 failure also removes local monitoring. Use external availability checks and CloudWatch for detecting total-host failure. No AWS resources are created by the repository's validation pipeline.

## Changes to the existing app

DevOps enablement only: add Actuator and Micrometer; externalize CORS and integration settings; correct the Slack environment-variable name; use a same-origin/configurable frontend endpoint; add graceful shutdown and database-inclusive readiness; disable SQL data logging. The hardcoded controller CORS annotation is replaced by the environment-driven global configuration. A targeted React lint comment preserves the existing once-on-mount fetch behavior while allowing strict CI builds. H2 is test-only, and observability is explicitly enabled in the operations integration test. Services, entities, CRUD behavior and Cohere/Slack calls are preserved.

Assumptions and limits: the upstream app has no user authentication; this deployment restricts access rather than changing its business logic. HTTP is acceptable for a restricted assessment network; add an HTTPS load balancer, authentication and certificate verification before public use. RDS transport is encrypted with `sslMode=REQUIRED`; full server identity verification is a documented hardening step. The assessment uses the RDS-managed master credential and `ddl-auto=update` to retain automatic schema initialization; production should introduce an application-scoped DB account and reviewed, backward-compatible migrations. Integration API availability depends on the upstream Cohere endpoint and actual credentials and is not claimed as verified here. Docker Compose replacement can cause a brief interruption; this is not a zero-downtime or high-availability design.

## Verification and operations

```bash
(cd Backend/todo-summary-assistant && ./mvnw -B -ntp verify)
(cd Frontend/todo && npm ci && CI=true npm test -- --watchAll=false --runInBand && CI=true npm run build)
python3 -m unittest discover -s tests -v
shellcheck scripts/*.sh
terraform -chdir=aws/iac fmt -check
terraform -chdir=aws/iac init -backend=false
terraform -chdir=aws/iac validate
```

Backend integration tests exercise real HTTP, H2-backed CRUD, main-port readiness and internal Prometheus histograms. CI additionally checks the real MySQL/Docker stack; H2 alone does not prove MySQL compatibility. The pipeline tests first-deployment failure, rollback to a prior release, proxy health failure and failures before changing containers. Prometheus rule tests cover sustained outages/CPU load and suppression of low-volume errors.

See [failure and rollback](FAILURE_AND_ROLLBACK.md) for all six required failure scenarios, and [monitoring and operations](MONITORING_AND_OPERATIONS.md) for metrics, logs and alert noise control.
