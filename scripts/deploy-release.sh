#!/usr/bin/env bash
# Called under the bootstrap launcher's flock; deploy a pre-downloaded release.
set -Eeuo pipefail
revision=${1:?Usage: deploy-release.sh COMMIT_SHA}
[[ "$revision" =~ ^[a-f0-9]{40}$ ]] || { echo 'Invalid commit SHA' >&2; exit 2; }
todo_home=${TODO_HOME:-/opt/todo}
config=${TODO_CONFIG:-/etc/todo/config.json}
release="$todo_home/releases/$revision"
previous=$(readlink -f "$todo_home/current" 2>/dev/null || true)

compose() {
  local directory=$1
  shift
  docker compose --project-name todo --env-file "$directory/deploy/runtime/compose.env" \
    -f "$directory/deploy/docker-compose.prod.yml" "$@"
}

rollback() {
  local code=$?
  trap - ERR
  echo "Deployment failed; restoring previous release." >&2
  if [[ -n "$previous" && -d "$previous" ]]; then
    # Reuse the previous code/config while refreshing any rotated credentials.
    python3 "$previous/scripts/render-runtime.py" --config "$config" --release "$(basename "$previous")" \
      --output "$previous/deploy/runtime" || echo "Secret refresh unavailable; using previous runtime files." >&2
    if ! compose "$previous" up -d --remove-orphans --wait --wait-timeout 180; then
      echo "ROLLBACK FAILED: operator intervention required." >&2
    else
      echo "Previous release restored." >&2
    fi
  else
    compose "$release" down || true
    echo "First deployment failed; no previous release exists." >&2
  fi
  exit "$code"
}

# Failures during preparation leave running containers untouched.
python3 "$release/scripts/render-runtime.py" --config "$config" --release "$revision" \
  --output "$release/deploy/runtime"
region=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["region"])' "$config")
registry=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["ecr_registry"])' "$config")
aws ecr get-login-password --region "$region" | docker login --username AWS --password-stdin "$registry" >/dev/null
compose "$release" config --quiet
compose "$release" pull

trap rollback ERR
compose "$release" up -d --remove-orphans --wait --wait-timeout 180
curl --fail --silent --show-error --max-time 10 http://127.0.0.1/healthz >/dev/null
curl --fail --silent --show-error --max-time 10 http://127.0.0.1/readyz >/dev/null
curl --fail --silent --show-error --max-time 10 http://127.0.0.1/api/todos >/dev/null
# Switch the pointer only after the app + database + reverse proxy pass checks.
ln -sfn "$release" "$todo_home/current.next"
mv -Tf "$todo_home/current.next" "$todo_home/current"
trap - ERR
echo "Healthy release: $revision"
