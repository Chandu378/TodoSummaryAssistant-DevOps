#!/usr/bin/env python3
"""Conservative credential-pattern check of tracked text, in addition to .gitignore."""
from pathlib import Path
import re
import subprocess

patterns = [
    re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(r"https://hooks\.slack\.com/services/[A-Z0-9]+/[A-Z0-9]+/[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
failed = []
for filename in subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0"):
    if not filename:
        continue
    path = Path(filename)
    if path.name in {".env", "terraform.tfvars"} or ".tfstate" in path.name:
        failed.append(filename)
    try:
        text = path.read_text()
    except (UnicodeDecodeError, FileNotFoundError):
        continue
    if any(pattern.search(text) for pattern in patterns):
        failed.append(filename)
if failed:
    raise SystemExit("Possible credentials/config committed in: " + ", ".join(sorted(set(failed))))
print("Tracked-file credential-pattern checks passed (not a complete security audit)")
