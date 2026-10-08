#!/usr/bin/env python3
"""Validate production config without AWS, including exact special-character secrets."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runtime', root / 'scripts/render-runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
with tempfile.TemporaryDirectory() as temporary:
    release = Path(temporary)
    (release / 'deploy').mkdir()
    shutil.copy(root / 'deploy/docker-compose.prod.yml', release / 'deploy')
    config = {'region': 'ap-south-1', 'ecr_registry': 'registry.example', 'backend_repository': 'backend',
              'frontend_repository': 'frontend', 'rds_endpoint': 'database.example:3306'}
    password = "fixture-dollar$quote'backslash\\double\""
    app = {'cohere_api_key': '', 'slack_webhook_url': '', 'grafana_admin_password': 'fixture-only-long-password'}
    runtime.render(config, 'a' * 40, release / 'deploy/runtime', {'username': 'todo', 'password': password}, app)
    command = ['docker', 'compose', '--project-name', 'todo-config-check',
               '--env-file', str(release / 'deploy/runtime/compose.env'),
               '-f', str(release / 'deploy/docker-compose.prod.yml')]
    result = subprocess.check_output([*command, 'config', '--format', 'json'], text=True)
    services = json.loads(result)['services']
    assert 'mysql' not in services
    # Canonical config escapes dollar signs for re-reading as Compose YAML/JSON.
    assert services['backend']['environment']['DB_PASSWORD'].replace('$$', '$') == password
    assert services['backend']['image'].endswith(':' + 'a' * 40)
    assert 'GF_SECURITY_ADMIN_PASSWORD' not in services['grafana']['environment']
    assert services['grafana']['environment']['GF_SECURITY_ADMIN_PASSWORD__FILE'] == '/run/secrets/grafana-password'
    if '--runtime' in sys.argv:
        override = release / 'override.json'
        override.write_text(json.dumps({'services': {'backend': {'image': 'todo-backend:local'}}}))
        command += ['-f', str(override)]
        try:
            value = subprocess.check_output([*command, 'run', '--rm', '--no-deps', '-T',
                                             '--entrypoint', 'printenv', 'backend', 'DB_PASSWORD'], text=True)
            assert value.rstrip('\n') == password, 'Container environment changed the fixture secret'
        finally:
            subprocess.run([*command, 'down', '--volumes'], check=True, stdout=subprocess.DEVNULL)
print('Production Compose and raw secret preservation verified without AWS')
