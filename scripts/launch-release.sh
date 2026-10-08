#!/usr/bin/env bash
# Installed by EC2 user-data. All deployments, including manual rollback, use this lock.
set -Eeuo pipefail
revision=${1:?Usage: todo-release COMMIT_SHA}
[[ "$revision" =~ ^[a-f0-9]{40}$ ]] || { echo 'Invalid commit SHA' >&2; exit 2; }
exec 9>/var/lock/todo-release.lock
flock -w 900 9
bucket=$(jq -r .artifact_bucket /etc/todo/config.json)
region=$(jq -r .region /etc/todo/config.json)
release="/opt/todo/releases/$revision"

if [[ ! -d "$release/scripts" ]]; then
  temporary=$(mktemp -d /opt/todo/releases/download.XXXXXX)
  aws s3 cp "s3://$bucket/releases/$revision.tar.gz" "$temporary/$revision.tar.gz" --region "$region" --only-show-errors
  aws s3 cp "s3://$bucket/releases/$revision.tar.gz.sha256" "$temporary/$revision.tar.gz.sha256" --region "$region" --only-show-errors
  (cd "$temporary" && sha256sum -c "$revision.tar.gz.sha256")
  mkdir "$temporary/content"
  tar -xzf "$temporary/$revision.tar.gz" -C "$temporary/content"
  mv "$temporary/content" "$release"
fi
bash "$release/scripts/deploy-release.sh" "$revision"
