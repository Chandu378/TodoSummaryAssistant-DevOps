#!/usr/bin/env python3
"""SSM deployment dispatcher, usable in CI and from an operator's AWS session."""
import argparse
import json
import re
import subprocess
import time


def aws(region, *args):
    result = subprocess.run(["aws", "--region", region, *args, "--output", "json"],
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--instance", required=True)
    parser.add_argument("--document", required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-f0-9]{40}", args.revision):
        parser.error("revision must be a full lowercase commit SHA")
    command = aws(args.region, "ssm", "send-command", "--instance-ids", args.instance,
                  "--document-name", args.document, "--document-version", "$LATEST",
                  "--parameters", json.dumps({"Revision": [args.revision]}), "--timeout-seconds", "600")
    identifier = command["Command"]["CommandId"]
    print(f"SSM command: {identifier}", flush=True)
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        time.sleep(10)
        try:
            result = aws(args.region, "ssm", "get-command-invocation", "--command-id", identifier,
                         "--instance-id", args.instance)
        except subprocess.CalledProcessError as error:
            if "InvocationDoesNotExist" in error.stderr:
                continue
            raise
        status = result["Status"]
        if status == "Success":
            print(result.get("StandardOutputContent", ""))
            return
        if status not in {"Pending", "InProgress", "Delayed", "Cancelling"}:
            # Scripts never echo secrets, and AWS API command parameters contain only the SHA.
            raise SystemExit(f'SSM deployment failed ({status}): {result.get("StandardErrorContent", "")}')
    raise SystemExit("SSM deployment timed out; check invocation status before retrying")


if __name__ == "__main__":
    main()
