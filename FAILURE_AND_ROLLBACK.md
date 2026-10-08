# Failure and rollback scenarios

All procedures refer to the supplied EC2/SSM deployment after AWS provisioning. The application and monitoring run on one EC2 instance, with application data in private RDS. This implementation has automated health-gated rollback; it does not claim that live AWS recovery drills have already been performed.

## 1. A faulty version is deployed: how do you roll back?

If deployment health checks fail after containers change, the release script automatically brings back the previous healthy release and fails the SSM command/CI job. Failures while fetching secrets, validating configuration or pulling images leave the existing containers untouched. On the first-ever failed release there is no previous version; the candidate is stopped without deleting volumes. The current pointer only advances after frontend, DB readiness and API checks pass. If automatic rollback fails, the script reports `ROLLBACK FAILED` and an operator must intervene.

For a faulty version that passes health checks but later exhibits incorrect behavior, select the **full commit SHA of a previously successful release** and use an authorized operator AWS session:

```bash
python3 scripts/dispatch-deploy.py \
  --region ap-south-1 \
  --instance YOUR_INSTANCE_ID \
  --document todo-summary-deploy \
  --revision PREVIOUS_FULL_COMMIT_SHA
```

This uses the same checksum-verified S3 bundle, immutable ECR image tags, host lock and health checks as CI. It fetches current secret values rather than reverting credentials. The prior version's Compose and monitoring files are restored along with both application images. Monitoring data volumes are preserved. Follow with a source revert and normal CI deployment so the next push does not reintroduce the faulty version. Keep both successful release images and bundles; do not prune them during an incident.

The app currently retains upstream `ddl-auto=update`. Image rollback **does not undo database changes**. Destructive/incompatible schema changes can make the prior image unusable. Introduce versioned, reviewed expand/contract migrations before shipping such changes. If data was damaged, isolate writes, snapshot the damaged DB for investigation, restore a point-in-time copy and validate it before switching the endpoint; restoring can discard writes after the recovery point.

## 2. The application crashes after deployment: what happens?

Docker's `unless-stopped` policy restarts an exited process and brings containers back after host reboot. Java exits on OOM, allowing restart; memory caps limit the impact on monitoring. Runtime counters expose repeated restarts, application/blackbox checks detect loss of availability, and alerts fire after sustained failure. A healthy-state failure during the deployment window triggers automatic rollback.

After the deployment window, health and restart alerts require an operator to diagnose the issue and invoke rollback if the release caused it. Docker **does not restart a process merely because it is marked unhealthy**, and there is no late automatic rollback loop. A running but hung application, exhausted database or unrelated dependency outage must be addressed explicitly. Inspect container exit/OOM state, rotated logs, JVM memory, connection pool and RDS events. Do not repeatedly restart every container when the shared database is the problem. Liveness excludes RDS; readiness includes it.

## 3. CI/CD is unavailable: can you still deploy?

Yes. For an already built and published release, an authorized AWS operator can run the same `dispatch-deploy.py` command. On the host via SSM, `sudo /usr/local/bin/todo-release FULL_SHA` is equivalent and uses the same lock. Neither requires GitHub availability because artifacts and images live in AWS. The operator needs permission for the custom SSM document/target and command polling; only the instance role retrieves runtime secrets.

For a new release, run all normal validation tests locally, build both Dockerfiles for `linux/amd64`, authenticate Docker to ECR using your temporary AWS role, tag/push both with the new full SHA, create `git archive --format=tar HEAD deploy monitoring scripts | gzip > SHA.tar.gz`, generate `sha256sum SHA.tar.gz > SHA.tar.gz.sha256`, and upload both to the configured S3 `releases/` prefix. Then dispatch that SHA. Check that the working tree is clean so images and the archived commit match. Do not overwrite immutable tags or bypass tests to save time. If AWS/SSM itself is unavailable, this manual path is unavailable too; restore the control plane or wait, rather than opening emergency world-accessible SSH.

## 4. Secrets are leaked: what steps do you take?

Treat the credential as compromised immediately. Disable the affected Cohere key/Slack webhook, rotate the DB/Grafana credential as applicable, and revoke exposed AWS sessions/keys or GitHub tokens. Identify the scope and time of exposure, investigate CloudTrail/provider logs, restrict access and preserve evidence. Removing a file from the latest commit does not invalidate a leaked secret or remove it from history.

Update AWS Secrets Manager and redeploy the current healthy SHA to refresh runtime values. For an existing Grafana database, also rotate the actual admin account through its settings; its environment password only initializes a new database. Verify dependent functionality without printing secrets. Coordinate repository-history cleanup if a secret was committed, then scan all refs, CI logs, Docker layers, release artifacts and copies. Close the original exposure and add a focused prevention check. The repository's pattern scan is a guardrail, not proof that arbitrary secrets cannot leak. OIDC and instance roles avoid storing long-lived AWS keys in this design.

## 5. EC2 fails: how do you recover?

If only the OS/service is unhealthy, inspect EC2 status and SSM/cloud-init/Docker logs, recover/reboot the instance if appropriate, and confirm container health after restart. If the instance or EBS disk cannot be recovered, replace it through Terraform with the same network/IAM/bootstrap configuration, reassociate the Elastic IP, update GitHub's `EC2_INSTANCE_ID` variable and deploy the last healthy SHA through SSM. RDS application data stays independent of EC2. ECR/S3 retain release material.

Before replacement, record the healthy release SHA outside the failed machine (successful GitHub run/deployment record). EC2 bootstrap does not automatically reconstruct the previous release pointer, so an explicit SSM redeploy is required. The default EBS volume is deleted on termination; monitoring history and local logs are lost unless backed up off-instance. For stronger recovery, add an ASG/AMI strategy and external log/metrics storage. EC2 failure also removes local Prometheus/Alertmanager, so external uptime checks and CloudWatch EC2 status alarms are needed to detect total-host failure. Document and measure the recovery time during a real drill; no RTO is guaranteed by these files.

## 6. RDS becomes unavailable: impact and recovery

CRUD and summarization cannot load/save todos. Readiness becomes unhealthy; the frontend can still serve its static shell but API requests fail. Blackbox/ApplicationDown alerts detect sustained DB-inclusive readiness failure. Liveness remains healthy so a DB outage does not cause an automatic application restart storm. Docker's readiness status is diagnostic; Nginx is not a load balancer that removes unhealthy instances from service.

Check RDS events, status, storage, connections, security groups and credentials. Fix connectivity/credentials or capacity before restoring from backup. If Multi-AZ is enabled, RDS manages infrastructure failover and the existing endpoint is retained; the connection pool must reconnect and an interruption is still possible. The assessment defaults to Single-AZ to reduce cost, so it has no standby failover promise.

Terraform enables seven-day automated backups, encrypted storage, deletion protection and a final snapshot. For data corruption or unrecoverable failure, restore a snapshot or point-in-time backup **to a new instance**, validate schema/data and security group restrictions, then update infrastructure/configuration to the new endpoint/managed secret and redeploy. Keep the former instance or forensic snapshot until investigation is complete. Record the chosen recovery point, lost-write risk and validation result. Periodically test restoration; a retained backup alone does not prove it can meet recovery objectives.
