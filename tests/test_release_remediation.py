"""Offline regression probes for the 2026-11-23 remediation follow-up.

Tests intentionally avoid the network and never publish artifacts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build as legacy
import build_ai_shadowrocket as shadow
import build_v2rayn as v2
import notify_combined as notify
import publish_dual as publisher


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PublishedBaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        files = {
            shadow: {'ROOT': self.root,
                     'OUTPUT': self.root / 'Shadowrocket_Johnshall_AI.conf',
                     'STATE': self.root / 'data/ai-shadowrocket-sources.json',
                     'ORIGINAL_STATE': self.root / 'data/sources.json',
                     'ORIGINAL_AUTO': self.root / 'rules/openai-auto.list'},
            v2: {'CONFIG': self.root / 'v2rayN_Johnshall_AI.json',
                 'STATE': self.root / 'data/v2rayn-sources.json'},
        }
        for module, replacements in files.items():
            for key, path in replacements.items():
                ctx = patch.object(module, key, path)
                ctx.start()
                self.addCleanup(ctx.stop)

    def write(self, path: Path, data: bytes):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def install_shadow(self, version=1):
        old_voice = [f'IP-CIDR,8.8.4.{i}/32' for i in range(1, 6)]
        header = '# [1a] OpenAI automatic rules - official Voice destination IPs\n'
        stop = '# [1b] OpenAI automatic rules - public domain rules\n'
        old_output = ('[Rule]\n' + header +
                      ''.join(f'{rule},AI,no-resolve\n' for rule in old_voice) +
                      '\n' + stop + 'DOMAIN-SUFFIX,openai.com,AI,force-remote-dns\n').encode()
        old_auto = ('# Voice\n' +
                    ''.join(f'{rule},no-resolve\n' for rule in old_voice)).encode()
        original = (json.dumps({'sources': {'voice': {'sha256': 'a' * 64}},
                                'statistics': {'voice_ipv4_addresses': 5}}) + '\n').encode()
        metadata = {
            'schema_version': version, 'output_sha256': digest(old_output),
            'ai_counts': {'gemini_domains': 61}, 'statistics': {'johnshall_lines': 84676},
            'sources': {'johnshall': {'sha256': 'b' * 64}},
        }
        if version == 2:
            metadata['voice_auto_sha256'] = digest(old_auto)
            metadata['legacy_state_sha256'] = digest(original)
        self.write(shadow.OUTPUT, old_output)
        self.write(shadow.ORIGINAL_AUTO, old_auto)
        self.write(shadow.ORIGINAL_STATE, original)
        self.write(shadow.STATE, (json.dumps(metadata) + '\n').encode())
        return metadata

    def install_v2(self, version=1):
        output = b'[{"outboundTag":"proxy"}]\n'
        state = {
            'schema_version': version, 'output_sha256': digest(output),
            'statistics': {'bitbrowser_domains': 11,
                           'official_bitbrowser_domains': 3,
                           'user_requested_bitbrowser_domains': 8},
            'sources': {'johnshall': {'sha256': 'a' * 64}},
            'ai_counts': {'gemini_domains': 61},
            'inputs_sha256': {'bitbrowser': 'b' * 64},
            'voice_rules': [f'IP-CIDR,8.8.4.{i}/32' for i in range(1, 6)],
        }
        if version == 2:
            state['statistics']['bitbrowser_effective_domains'] = 11
        self.write(v2.CONFIG, output)
        self.write(v2.STATE, (json.dumps(state) + '\n').encode())
        return state

    def test_genuine_first_initialization_and_verified_v1_migration(self):
        self.assertEqual(shadow.load_published_baseline(), (None, None, ''))
        self.assertEqual(v2.load_published_baseline(), (None, None))
        self.install_shadow(version=1)
        self.install_v2(version=1)
        self.assertEqual(shadow.load_published_baseline()[0]['schema_version'], 1)
        self.assertEqual(v2.load_published_baseline()[1]['schema_version'], 1)

    def test_shadow_missing_auxiliary_or_digest_cannot_reset_baseline(self):
        for missing in (shadow.ORIGINAL_STATE, shadow.ORIGINAL_AUTO, shadow.STATE):
            self.install_shadow()
            missing.unlink()
            with self.subTest(missing=missing), self.assertRaisesRegex(
                    ValueError, 'Incomplete published Shadowrocket baseline'):
                shadow.load_published_baseline()
        meta = self.install_shadow()
        meta.pop('output_sha256')
        self.write(shadow.STATE, (json.dumps(meta) + '\n').encode())
        with self.assertRaisesRegex(ValueError, 'output_sha256'):
            shadow.load_published_baseline()
        meta = self.install_shadow()
        meta['ai_counts'] = {}
        self.write(shadow.STATE, (json.dumps(meta) + '\n').encode())
        with self.assertRaisesRegex(ValueError, 'Incomplete published Shadowrocket state'):
            shadow.load_published_baseline()
        self.install_shadow()
        self.write(shadow.OUTPUT, shadow.OUTPUT.read_bytes() + b'CORRUPTED')
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            shadow.load_published_baseline()

    def test_shadow_v2_auxiliary_tamper_is_detected(self):
        self.install_shadow(version=2)
        shadow.load_published_baseline()
        self.write(shadow.ORIGINAL_AUTO, shadow.ORIGINAL_AUTO.read_bytes() + b'\n# changed')
        with self.assertRaisesRegex(ValueError, 'auxiliary digest mismatch'):
            shadow.load_published_baseline()

    def test_v2_missing_fields_or_corrupted_artifact_cannot_reset_baseline(self):
        state = self.install_v2()
        for key in ('voice_rules', 'output_sha256'):
            broken = dict(state)
            broken.pop(key)
            self.write(v2.STATE, (json.dumps(broken) + '\n').encode())
            with self.subTest(key=key), self.assertRaises(ValueError):
                v2.load_published_baseline()
        self.install_v2()
        self.write(v2.CONFIG, b'broken')
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            v2.load_published_baseline()
        self.install_v2()
        v2.STATE.unlink()
        with self.assertRaisesRegex(ValueError, 'output/state file missing'):
            v2.load_published_baseline()

    def test_v2_requires_valid_v2_effective_count_or_verified_old_shape(self):
        self.install_v2(version=2)
        self.assertEqual(v2.load_published_baseline()[1]['schema_version'], 2)
        state = self.install_v2(version=2)
        state['statistics'].pop('bitbrowser_effective_domains')
        self.write(v2.STATE, (json.dumps(state) + '\n').encode())
        with self.assertRaisesRegex(ValueError, 'effective BitBrowser'):
            v2.load_published_baseline()
        state = self.install_v2(version=1)
        state['statistics']['user_requested_bitbrowser_domains'] = 0
        self.write(v2.STATE, (json.dumps(state) + '\n').encode())
        with self.assertRaisesRegex(ValueError, 'Unrecognized v2rayN v1'):
            v2.load_published_baseline()


class VoiceAndBitBrowserTests(unittest.TestCase):
    def test_equivalent_cidr_splits_have_full_address_coverage(self):
        old = {'IP-CIDR,8.8.8.0/30'}
        same_addresses = {'IP-CIDR,8.8.8.0/31', 'IP-CIDR,8.8.8.2/31'}
        legacy.validate_voice_interval_overlap(old, same_addresses)
        v2.validate_voice_overlap(old, same_addresses)
        with self.assertRaisesRegex(ValueError, 'VOICE COVERAGE ANOMALY'):
            legacy.validate_voice_interval_overlap(old, {'IP-CIDR,9.9.9.0/30'})
        with self.assertRaisesRegex(ValueError, 'VOICE COVERAGE ANOMALY'):
            v2.validate_voice_overlap(old, {'IP-CIDR,9.9.9.0/30'})

    def test_only_approved_bitbrowser_entries_count_as_effective(self):
        original = [(f'domain{i}.example', 'user', 'fixture') for i in range(11)]
        approved = v2.selected_bitbrowser_domains(original)
        self.assertEqual(len(approved), 11)
        after_pending = original + [('unverified.example', 'unverified', 'fixture')]
        self.assertEqual(v2.selected_bitbrowser_domains(after_pending), approved)
        self.assertEqual(v2.selected_bitbrowser_domains(
            [(name, 'unverified', note) for name, _, note in original]), [])
        fields = ('johnshall_lines', 'johnshall_proxy_rules', 'johnshall_block_rules',
                  'voice_prefixes', 'voice_ipv4_addresses', 'voice_ipv6_addresses',
                  'auto_domains', 'manual_domains', 'bitbrowser_effective_domains',
                  'domain_rules', 'ip_rules', 'block_rules')
        good = {name: 1000 for name in fields}
        good['bitbrowser_effective_domains'] = 11
        baseline = {'schema_version': 2, 'statistics': good}
        v2.safety_check(good, baseline)
        failed = dict(good, bitbrowser_effective_domains=0)
        with self.assertRaisesRegex(ValueError, 'UPSTREAM ANOMALY'):
            v2.safety_check(failed, baseline)

    def test_v2_downloader_rejects_http200_content_range(self):
        class Response:
            status = 200
            headers = {'Content-Range': 'bytes 0-49/100', 'Content-Length': '50'}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, n): return b'x' * 50
        with patch.object(v2.urllib.request, 'urlopen', return_value=Response()) as req, \
                patch.object(v2.time, 'sleep'):
            with self.assertRaisesRegex(ValueError, 'partial response'):
                v2.download('https://example.invalid/list', minimum=10)
            self.assertEqual(req.call_count, 2)

    def test_unverified_process_paths_are_not_promoted(self):
        import v2rayn_core as core
        self.assertEqual(core.load_processes('BitBrowser.exe'), ['BitBrowser.exe'])
        self.assertEqual(core.load_processes(r'C:\BitBrowser\resources\BitBrowser.exe'),
                         [r'C:\BitBrowser\resources\BitBrowser.exe'])
        for bad in (r'C:\Program Files\nodejs\node.exe',
                    r'C:\BitBrowser\resources\node.exe',
                    r'C:\OtherApp\BitBrowser.exe'):
            with self.subTest(path=bad), self.assertRaises(ValueError):
                core.load_processes('BitBrowser.exe\n' + bad)


class PublishAndReportTests(unittest.TestCase):
    def status_file(self, root):
        p = Path(root) / 'status.json'
        p.write_text(json.dumps({'shadowrocket_ai': {'exit_code': 0},
                                 'v2rayn': {'exit_code': 0}}))
        return p

    def test_remote_fast_forward_fetches_before_ancestor_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.status_file(tmp)
            calls = []
            def fake_git(*args):
                calls.append(args)
                if args[0] == 'diff':
                    return SimpleNamespace(stdout='Shadowrocket_Johnshall_AI.conf\n')
                if args[0] == 'rev-parse':
                    return SimpleNamespace(stdout=('a' if args[1] == 'HEAD' else 'b') * 40 + '\n')
                if args[0] == 'ls-remote':
                    return SimpleNamespace(stdout='b' * 40 + '\trefs/heads/main\n')
                return SimpleNamespace(stdout='')
            with patch.object(publisher, 'git', side_effect=fake_git), \
                    patch.object(publisher.subprocess, 'run',
                                 return_value=SimpleNamespace(returncode=0, stderr='')):
                publisher.publish(p)
            self.assertTrue(json.loads(p.read_text())['publish']['success'])
            self.assertTrue(any(call[0] == 'fetch' for call in calls))
            self.assertTrue(any(call[0] == 'rev-parse' and call[1] == 'FETCH_HEAD'
                                for call in calls))

    def test_push_success_without_remote_verification_is_not_push_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.status_file(tmp)
            def fake_git(*args):
                if args[0] == 'diff':
                    return SimpleNamespace(stdout='Shadowrocket_Johnshall_AI.conf\n')
                if args[0] == 'rev-parse':
                    return SimpleNamespace(stdout='a' * 40 + '\n')
                if args[0] == 'ls-remote':
                    return SimpleNamespace(stdout='b' * 40 + '\trefs/heads/main\n')
                if args[0] == 'fetch':
                    raise RuntimeError('network temporarily unavailable')
                return SimpleNamespace(stdout='')
            with patch.object(publisher, 'git', side_effect=fake_git):
                publisher.publish(p)
            pub = json.loads(p.read_text())['publish']
            self.assertEqual(pub['state'], 'pushed_unverified')
            self.assertFalse(pub['success'])
            self.assertIn('Push succeeded', pub['error'])

    def test_report_missing_after_published_file_is_not_called_unchanged(self):
        status = {
            'shadowrocket_ai': {'exit_code': 0}, 'v2rayn': {'exit_code': 0},
            'publish': {'success': True, 'state': 'published',
                        'changed_files': ['Shadowrocket_Johnshall_AI.conf']},
        }
        good = {'build_success': True, 'config_changed': False,
                'statistics': {'routing_objects': 132}}
        text = notify.emit_message(status, None, good, when='2026-11-23 11:00',
                                   event='schedule', run_url='')
        self.assertIn('总体状态：部分成功', text)
        self.assertIn('已确认推送此配置', text)
        self.assertNotIn('配置：保留上一次已发布版本', text)
        invalid = dict(good, build_success=False)
        self.assertFalse(notify.valid_build_report(invalid))


if __name__ == '__main__':
    unittest.main()
