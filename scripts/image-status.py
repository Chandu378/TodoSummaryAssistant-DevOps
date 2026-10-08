#!/usr/bin/env python3
"""Skip publishing existing immutable SHA tags, but fail on permission/network errors."""
import os
import subprocess

with open(os.environ["GITHUB_OUTPUT"], "a") as output:
    for service in ["backend", "frontend"]:
        result = subprocess.run(
            ["aws", "ecr", "describe-images", "--repository-name", os.environ[service.upper() + "_REPOSITORY"],
             "--image-ids", "imageTag=" + os.environ["RELEASE_SHA"]],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            exists = "true"
        elif "ImageNotFoundException" in result.stderr:
            exists = "false"
        else:
            raise SystemExit(result.stderr)
        output.write(service + "_exists=" + exists + "\n")
