"""Release proof and provenance regression tests."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import release_integrity as ri
import publish_dual as publish
import run_dual

class ReleaseIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_child_log_encoding_does_not_break_independent_execution(self):
        # Use real subprocesses: no mocking away the decoding boundary.
        failed = run_dual.execute('invalid diagnostic bytes', [
            sys.executable, '-c',
            "import sys; sys.stdout.buffer.write(b'log\\xff'); "
            "sys.stderr.buffer.write(b'error\\xfe'); sys.exit(7)"])
        self.assertEqual(failed['exit_code'], 7)
        self.assertEqual(failed['error'], 'error\ufffd')
        following = run_dual.execute('other client', [
            sys.executable, '-c', "print('independent child')"])
        self.assertEqual(following, {'exit_code': 0, 'error': ''})

    def test_fingerprint_changes_with_local_input_not_output(self):
        a = ri.build_inputs_fingerprint('shadowrocket_ai', self.root)
        self.write('config/user-settings.json', b'new node')
        b = ri.build_inputs_fingerprint('shadowrocket_ai', self.root)
        self.assertNotEqual(a, b)
        self.write('Shadowrocket_Johnshall_AI.conf', b'generated file')
        self.assertEqual(b, ri.build_inputs_fingerprint('shadowrocket_ai', self.root))

    def test_missing_report_and_corrupted_artifact_rejected(self):
        client = 'v2rayn'
        output, state = ri.V2_FILES
        body = b'[{"outboundTag":"direct"}]\n'
        self.write(output, body)
        stats = {'json_bytes': len(body), 'routing_objects': 1}
        self.write(state, json.dumps({'schema_version': 2, 'statistics': stats,
                    'output_sha256': ri.digest(self.root / output),
                    'build_inputs_sha256': ri.build_inputs_fingerprint(client, self.root)}).encode())
        report = {'build_success': True, 'config_changed': True, 'statistics': stats,
                  'artifact_sha256': ri.artifact_manifest(ri.V2_FILES, self.root)}
        path = self.write('report.json', json.dumps(report).encode())
        status = {'reports': {client: str(path)}}
        # Hash-only fixture is intentionally not a complete subscription.
        with patch('route_semantics.verify_release_routes'):
            self.assertEqual(ri.validate_release(client, status, self.root), report)
        self.write(output, b'broken')
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            ri.validate_release(client, status, self.root)
        with self.assertRaisesRegex(ValueError, 'Missing fresh build report'):
            ri.validate_release(client, {}, self.root)

    def test_bad_client_report_does_not_stage_its_artifacts(self):
        status = self.write('status.json', json.dumps({
            'shadowrocket_ai': {'exit_code': 0}, 'v2rayn': {'exit_code': 0}}).encode())
        calls = []
        def git(*args):
            calls.append(args)
            return SimpleNamespace(stdout='')
        def validate(key, _status):
            if key == 'shadowrocket_ai':
                raise ValueError('invalid manifest')
            return {}
        with patch.dict('os.environ', {'GITHUB_REF': 'refs/heads/main'}), \
                patch.object(publish, 'remote_head', return_value=''), \
                patch.object(publish, 'git', side_effect=git), \
                patch.object(publish, 'validate_release', side_effect=validate):
            publish.publish(status)
        result = json.loads(status.read_text())
        self.assertNotEqual(result['shadowrocket_ai']['exit_code'], 0)
        self.assertEqual(result['v2rayn']['exit_code'], 0)
        staged = next(args for args in calls if args[0] == 'add')
        self.assertIn('v2rayN_Johnshall_AI.json', staged)
        self.assertNotIn('Shadowrocket_Johnshall_AI.conf', staged)
        self.assertEqual(publish.check(status), 1)

    def test_malformed_client_report_does_not_prevent_other_client_publication(self):
        status = self.write('malformed.json', json.dumps({
            'shadowrocket_ai': {'exit_code': 0}, 'v2rayn': {'exit_code': 0}}).encode())
        calls = []
        def git(*args):
            calls.append(args)
            return SimpleNamespace(stdout='')
        def validate(key, _status):
            if key == 'v2rayn':
                raise AttributeError('malformed report field')
            return {}
        with patch.dict('os.environ', {'GITHUB_REF': 'refs/heads/main'}), \
                patch.object(publish, 'remote_head', return_value=''), \
                patch.object(publish, 'git', side_effect=git), \
                patch.object(publish, 'validate_release', side_effect=validate):
            publish.publish(status)
        result = json.loads(status.read_text())
        self.assertEqual(result['shadowrocket_ai']['exit_code'], 0)
        self.assertEqual(result['v2rayn']['exit_code'], 1)
        staged = next(args for args in calls if args[0] == 'add')
        self.assertIn('Shadowrocket_Johnshall_AI.conf', staged)
        self.assertNotIn('v2rayN_Johnshall_AI.json', staged)
        self.assertEqual(publish.check(status), 1)

    def test_no_valid_client_never_commits_pending_manual_rejection(self):
        for shadow_code, v2_code in ((1,1),(0,0)):
            status = self.write('all-failed.json', json.dumps({
                'shadowrocket_ai': {'exit_code':shadow_code},
                'v2rayn': {'exit_code':v2_code}}).encode())
            calls = []
            def git(*args):
                calls.append(args)
                return SimpleNamespace(stdout='')
            with patch.dict('os.environ', {'GITHUB_REF':'refs/heads/main'}), \
                    patch.object(publish,'remote_head',return_value=''), \
                    patch.object(publish,'git',side_effect=git), \
                    patch.object(publish,'validate_release',side_effect=ValueError('bad release')):
                publish.publish(status)
            result = json.loads(status.read_text())
            self.assertFalse(result['publish']['success'])
            self.assertEqual(result['publish']['state'],'not-published')
            self.assertFalse(any(a[0] in ('add','commit','push') for a in calls))
            self.assertEqual(publish.check(status),1)

    def test_stale_checkout_rejected_before_staging(self):
        status = self.write('stale.json', b'{"shadowrocket_ai":{"exit_code":0},"v2rayn":{"exit_code":0}}')
        with patch.dict('os.environ', {'GITHUB_REF': 'refs/heads/main'}), \
                patch.object(publish, 'git', return_value=SimpleNamespace(stdout='old')) as git, \
                patch.object(publish, 'remote_head', return_value='new'):
            publish.publish(status)
        self.assertEqual(json.loads(status.read_text())['publish']['state'], 'stale')
        git.assert_called_once_with('rev-parse', 'HEAD')

    def test_remote_advanced_before_unchanged_report(self):
        status = self.write('stale2.json', b'{"shadowrocket_ai":{"exit_code":0},"v2rayn":{"exit_code":0}}')
        with patch.dict('os.environ', {'GITHUB_REF': 'refs/heads/main'}), \
                patch.object(publish, 'git', side_effect=lambda *a: SimpleNamespace(stdout='old' if a[0]=='rev-parse' else '')), \
                patch.object(publish, 'validate_release', return_value={}), \
                patch.object(publish, 'remote_head', side_effect=['old','new']):
            publish.publish(status)
        self.assertEqual(json.loads(status.read_text())['publish']['state'], 'stale')

if __name__ == '__main__':
    unittest.main()
