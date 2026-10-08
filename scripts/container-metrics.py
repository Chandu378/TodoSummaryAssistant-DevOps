#!/usr/bin/env python3
"""Export Docker runtime counters without mounting the Docker socket in monitoring."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import time


def metrics(containers):
    lines = ["# TYPE todo_container_restarts_total counter",
             "# TYPE todo_container_start_time_seconds gauge",
             "# TYPE todo_container_running gauge"]
    for container in containers:
        service = container["Config"]["Labels"].get("com.docker.compose.service", "unknown")
        # JSON string encoding is compatible with Prometheus label quoting.
        labels = 'service=' + json.dumps(service) + ',id=' + json.dumps(container["Id"][:12])
        state = container["State"]
        started = state["StartedAt"]
        if not started.startswith("0001"):
            # Docker has nanoseconds; truncate to Python's supported microseconds.
            stamp = datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp()
            lines.append(f"todo_container_start_time_seconds{{{labels}}} {stamp}")
        lines.append(f'todo_container_restarts_total{{{labels}}} {container["RestartCount"]}')
        lines.append(f'todo_container_running{{{labels}}} {int(state["Running"])}')
    lines += ["# TYPE todo_container_metrics_collected_seconds gauge",
              f"todo_container_metrics_collected_seconds {time.time()}"]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/var/lib/todo/node-metrics/docker.prom"))
    args = parser.parse_args()
    ids = subprocess.check_output(
        ["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=todo"], text=True
    ).split()
    containers = json.loads(subprocess.check_output(["docker", "inspect", *ids], text=True)) if ids else []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".prom.tmp")
    temporary.write_text(metrics(containers))
    temporary.chmod(0o644)
    temporary.replace(args.output)


if __name__ == "__main__":
    main()
