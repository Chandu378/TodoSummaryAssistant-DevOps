import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


renderer = module('render-runtime')
collector = module('container-metrics')
CONFIG = {'region': 'ap-south-1', 'ecr_registry': 'registry.example',
          'backend_repository': 'backend', 'frontend_repository': 'frontend',
          'rds_endpoint': 'database.example:3306', 'rds_secret_arn': 'db-secret', 'app_secret_arn': 'app-secret'}
DB = {'username': 'todo', 'password': "test-dollar$quote'backslash\\"}
APP = {'cohere_api_key': 'unused', 'slack_webhook_url': '', 'grafana_admin_password': 'test-only-long-password'}


class RuntimeTests(unittest.TestCase):
    def test_preserves_secret_characters_and_restricts_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'runtime'
            renderer.render(CONFIG, 'a' * 40, directory, DB, APP)
            self.assertIn('DB_PASSWORD=' + DB['password'] + '\n', (directory / 'backend.env').read_text())
            self.assertEqual((directory / 'backend.env').stat().st_mode & 0o777, 0o600)
            self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
            self.assertNotIn(APP['grafana_admin_password'], (directory / 'compose.env').read_text())
            self.assertEqual((directory / 'grafana-password').read_text(), APP['grafana_admin_password'])

    def test_rejects_multiline_secrets(self):
        with self.assertRaises(ValueError):
            renderer.dotenv({'DB_PASSWORD': 'bad\nINJECTED=value'}, raw=True)

    def test_rejects_weak_grafana_password(self):
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(ValueError):
            renderer.render(CONFIG, 'a' * 40, Path(temporary), DB, {**APP, 'grafana_admin_password': 'short'})

    def test_metrics_include_restart_count_running_state_and_uptime(self):
        container = {'Config': {'Labels': {'com.docker.compose.service': 'backend'}},
                     'Id': 'abcdef123456' * 5, 'RestartCount': 4,
                     'State': {'StartedAt': '2026-01-01T00:00:00.123456789Z', 'Running': True}}
        result = collector.metrics([container])
        self.assertIn('todo_container_restarts_total{service="backend",id="abcdef123456"} 4', result)
        self.assertIn('todo_container_running{service="backend",id="abcdef123456"} 1', result)
        self.assertIn('todo_container_start_time_seconds', result)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = Path(self.temporary.name)
        self.bin = self.home / 'bin'
        self.bin.mkdir()
        self.previous = 'a' * 40
        self.candidate = 'b' * 40
        self.log = self.home / 'docker.log'
        self.config = self.home / 'config.json'
        self.config.write_text(json.dumps(CONFIG))
        self.env = {**os.environ, 'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
                    'TODO_HOME': str(self.home), 'TODO_CONFIG': str(self.config), 'TEST_LOG': str(self.log)}
        self.program('aws', '''import sys,json
if 'get-secret-value' in sys.argv:
    print(json.dumps({'username':'todo','password':'unused'} if 'db-secret' in sys.argv else
                     {'cohere_api_key':'unused','slack_webhook_url':'','grafana_admin_password':'test-only-long-password'}))
else:
    print('unused-login-token')
''')
        self.program('docker', '''import os,sys
args=' '.join(sys.argv[1:])
with open(os.environ['TEST_LOG'],'a') as log: log.write(args+'\\n')
if os.environ.get('FAIL_ACTION','') and os.environ['FAIL_ACTION'] in args and 'b'*40 in args: sys.exit(1)
''')
        self.program('curl', '''import os,sys
sys.exit(1 if os.environ.get('FAIL_HEALTH') else 0)
''')
        # Emulate GNU mv for the macOS development host; production and CI use coreutils.
        self.program('mv', '''import os,sys
os.replace(sys.argv[-2],sys.argv[-1])
''')
        for sha in [self.previous, self.candidate]:
            directory = self.home / 'releases' / sha
            (directory / 'scripts').mkdir(parents=True)
            (directory / 'deploy').mkdir()
            shutil.copy(ROOT / 'scripts/render-runtime.py', directory / 'scripts')
            renderer.render(CONFIG, sha, directory / 'deploy/runtime', DB, APP)
        (self.home / 'current').symlink_to(self.home / 'releases' / self.previous)

    def tearDown(self):
        self.temporary.cleanup()

    def program(self, name, text):
        path = self.bin / name
        path.write_text('#!/usr/bin/env python3\n' + text)
        path.chmod(0o755)

    def deploy(self, **changes):
        return subprocess.run(['bash', str(ROOT / 'scripts/deploy-release.sh'), self.candidate],
                              env={**self.env, **changes}, capture_output=True, text=True)

    def test_success_switches_current_after_health_checks(self):
        result = self.deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.home / 'current').resolve().name, self.candidate)

    def test_failed_candidate_restores_previous_release(self):
        result = self.deploy(FAIL_ACTION='up -d')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.home / 'current').resolve().name, self.previous)
        self.assertIn(self.previous, self.log.read_text().splitlines()[-1])
        self.assertIn('Previous release restored', result.stderr)

    def test_first_failure_stops_containers_without_deleting_volumes(self):
        (self.home / 'current').unlink()
        result = self.deploy(FAIL_ACTION='up -d')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.log.read_text().splitlines()[-1].endswith(' down'))
        self.assertNotIn('--volumes', self.log.read_text())

    def test_pull_failure_keeps_running_release_untouched(self):
        result = self.deploy(FAIL_ACTION='pull')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('up -d', self.log.read_text())
        self.assertEqual((self.home / 'current').resolve().name, self.previous)

    def test_proxy_health_failure_restores_previous(self):
        result = self.deploy(FAIL_HEALTH='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Previous release restored', result.stderr)
        self.assertEqual((self.home / 'current').resolve().name, self.previous)


if __name__ == '__main__':
    unittest.main()
