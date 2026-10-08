#!/usr/bin/env python3
"""One-time configuration after Terraform apply; deliberately leaves deployment disabled."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
values = json.loads(subprocess.check_output(
    ['terraform', '-chdir=' + str(root / 'aws/iac'), 'output', '-json', 'github_actions_variables'], text=True))
repository = subprocess.check_output(['gh', 'repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner'], text=True).strip()
for name, value in values.items():
    subprocess.run(['gh', 'variable', 'set', name, '--repo', repository, '--body', str(value)], check=True)
print('AWS variables set. Populate the application secret, then set AWS_DEPLOY_ENABLED=true.')
