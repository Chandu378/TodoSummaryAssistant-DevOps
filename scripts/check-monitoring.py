#!/usr/bin/env python3
"""Wait for all scrape jobs, probe success, restart metrics and the dashboard API."""
import base64
import json
import os
import time
from urllib.request import Request, urlopen

deadline = time.monotonic() + 120
while True:
    try:
        with urlopen("http://localhost:9090/api/v1/targets", timeout=5) as response:
            targets = json.load(response)["data"]["activeTargets"]
        assert len(targets) == 5 and all(target["health"] == "up" for target in targets), "Scrape targets unhealthy"
        for expression in ["probe_success", "todo_container_restarts_total"]:
            from urllib.parse import urlencode
            with urlopen("http://localhost:9090/api/v1/query?" + urlencode({"query": expression}), timeout=5) as response:
                samples = json.load(response)["data"]["result"]
            assert samples, f"Missing metrics: {expression}"
            if expression == "probe_success":
                assert all(sample["value"][1] == "1" for sample in samples), "Readiness probes failed"
        credentials = os.environ.get("GRAFANA_ADMIN_USER", "admin") + ":" + os.environ.get("GRAFANA_ADMIN_PASSWORD", "replace-with-a-grafana-password")
        header = {"Authorization": "Basic " + base64.b64encode(credentials.encode()).decode()}
        with urlopen(Request("http://localhost:3001/api/dashboards/uid/todo-operations", headers=header), timeout=5) as response:
            assert len(json.load(response)["dashboard"]["panels"]) >= 9
        print("All scrape targets, probes, runtime metrics and Grafana dashboard verified")
        break
    except Exception:
        if time.monotonic() >= deadline:
            raise
        time.sleep(5)
