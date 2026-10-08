#!/usr/bin/env python3
"""Exercise frontend proxy + real database CRUD; never call external integrations."""
import json
import os
from urllib.request import Request, urlopen

base = os.environ.get("SMOKE_BASE_URL", "http://localhost:3000").rstrip("/")


def request(path, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    with urlopen(Request(base + path, data=data, method=method,
                         headers={"Content-Type": "application/json"}), timeout=10) as response:
        content = response.read()
        return json.loads(content) if content and response.headers.get_content_type() == "application/json" else content


assert b'<div id="root">' in request("/")
assert request("/readyz")["status"] == "UP"
todo = request("/api/todos", "POST", {"title": "Pipeline smoke test", "description": "Temporary", "completed": False})
try:
    request(f'/api/todos/{todo["id"]}', "PUT", {**todo, "completed": True})
    assert any(item["id"] == todo["id"] and item["completed"] for item in request("/api/todos"))
finally:
    request(f'/api/todos/{todo["id"]}', "DELETE")
assert all(item["id"] != todo["id"] for item in request("/api/todos"))
print("Frontend, database readiness and CRUD smoke checks passed")
