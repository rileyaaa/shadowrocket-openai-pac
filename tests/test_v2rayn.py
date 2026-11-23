"""Offline semantic, failure isolation, reporting and publication safety tests."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import v2rayn_core as core
import build_v2rayn as builder
import publish_dual as publish
import notify_combined as notify


class ConversionTests(unittest.TestCase):
    def test_exact_vs_suffix_and_regex(self):
        self.assertEqual(core.as_match('DOMAIN', 'js.stripe.com'), ('domain', 'full:js.stripe.com'))
        self.assertEqual(core.as_match('DOMAIN-SUFFIX', 'chatgpt.com'), ('domain', 'domain:chatgpt.com'))
        self.assertEqual(core.as_match('DOMAIN-KEYWORD', 'hello'), ('domain', 'keyword:hello'))
        field, wildcard = core.as_match('DOMAIN-WILDCARD', 'x-*.webpubsub.azure.com')
        self.assertEqual(field, 'domain')
        self.assertEqual(wildcard, r'regexp:^x\-.*\.webpubsub\.azure\.com$')
        self.assertNotIn('domain:stripe.com', [core.as_match('DOMAIN', 'js.stripe.com')[1]])
        self.assertEqual(core.as_match('DOMAIN', 'browser-intake-us5-datadoghq.com'),
                         ('domain', 'full:browser-intake-us5-datadoghq.com'))
        self.assertNotEqual(core.as_match('DOMAIN', 'browser-intake-us5-datadoghq.com'),
                            ('domain', 'domain:datadoghq.com'))

    def test_chatgpt_webpubsub_pattern_does_not_cross_dns_label(self):
        import re
        field, value = core.as_match(
            'DOMAIN-WILDCARD', 'chatgpt-async-webps-prod-*.webpubsub.azure.com')
        self.assertEqual(field, 'domain')
        regex = re.compile(value.removeprefix('regexp:'))
        self.assertTrue(regex.fullmatch('chatgpt-async-webps-prod-xyz-12.webpubsub.azure.com'))
        for wrong in ('chatgpt-async-webps-prod-x.y.webpubsub.azure.com',
                      'chatgpt-async-webps-prod-.webpubsub.azure.com',
                      'chatgpt-async-webps-prod-x.webpubsub.azure.com.bad.test'):
            self.assertIsNone(regex.fullmatch(wrong))

    def test_ipv4_ipv6_geo_and_no_resolve(self):
        self.assertEqual(core.parse_rule('IP-CIDR,8.8.8.0/24,Proxy,no-resolve'),
                         ('ip', '8.8.8.0/24', 'proxy'))
        self.assertEqual(core.parse_rule('IP-CIDR6,2001:4860::/32,DIRECT'),
                         ('ip', '2001:4860::/32', 'direct'))
        self.assertEqual(core.parse_rule('GEOIP,CN,DIRECT'), ('ip', 'geoip:cn', 'direct'))
        self.assertEqual(core.parse_rule('GEOSITE,cn,Proxy'), ('domain', 'geosite:cn', 'proxy'))
        self.assertEqual(core.parse_rule('IP-CIDR,2001:b28:f23d::/48,PROXY'),
                         ('ip', '2001:b28:f23d::/48', 'proxy'))
        with self.assertRaises(core.UnsupportedRule):
            core.parse_rule('IP-CIDR6,1.1.1.0/24,PROXY')
        with self.assertRaises(core.UnsupportedRule):
            core.parse_rule('DOMAIN,a.com,Proxy,no-resolve')

    def test_original_action_mapping(self):
        for action in ('REJECT', 'REJECT-DROP', 'REJECT-NO-DROP'):
            self.assertEqual(core.parse_rule(f'DOMAIN,ads.example,{action}')[2], 'block')
        self.assertEqual(core.parse_rule('DOMAIN,cn.example,DIRECT')[2], 'direct')
        self.assertEqual(core.parse_rule('DOMAIN,overseas.example,Proxy')[2], 'proxy')
        self.assertEqual(core.parse_rule('FINAL,direct'), ('FINAL', '', 'direct'))
        with self.assertRaises(core.UnsupportedRule):
            core.parse_rule('FINAL,Proxy')
        with self.assertRaises(core.UnsupportedRule):
            core.parse_rule('URL-REGEX,^http://,REJECT')
        with self.assertRaises(core.UnsupportedRule):
            core.parse_rule('RULE-SET,https://unknown.test/list,PROXY')

    def test_merging_only_contiguous_equal_action_and_field(self):
        items = [('domain', 'full:a.com', 'block'), ('domain', 'full:b.com', 'block'),
                 ('domain', 'full:c.com', 'proxy'), ('domain', 'full:d.com', 'block'),
                 ('ip', '8.8.8.8', 'block')]
        objects = core.compact(items, 'Fixture')
        self.assertEqual([o['outboundTag'] for o in objects], ['block', 'proxy', 'block', 'block'])
        self.assertEqual(objects[0]['domain'], ['full:a.com', 'full:b.com'])
        self.assertEqual(objects[-1]['ip'], ['8.8.8.8'])
        self.assertTrue(all(o['enabled'] for o in objects))

    def test_unsupported_and_missing_upstream_guard(self):
        with self.assertRaises(ValueError):
            core.johnshall_entries('DOMAIN,site.com,PROXY\nFINAL,direct\n', {}, lambda x, _: [x])
        source = '\n'.join(['DOMAIN,x.com,PROXY', 'DOMAIN,y.com,REJECT',
                            'URL-REGEX,unknown,PROXY', 'FINAL,direct'])
        with self.assertRaises(core.UnsupportedRule):
            core.johnshall_entries(source, {}, lambda x, _: [x], minimum_lines=1)

    def test_early_final_is_rejected(self):
        source = '\n'.join(['FINAL,direct']
                           + [f'DOMAIN,proxy{i}.example,Proxy' for i in range(10001)]
                           + [f'DOMAIN,ad{i}.example,REJECT' for i in range(20001)])
        with self.assertRaisesRegex(ValueError, 'FINAL must be the last'):
            core.johnshall_entries(source, {}, lambda x, _: [x], minimum_lines=1)

    def test_massively_duplicated_ads_are_not_a_valid_update(self):
        source = '\n'.join([f'DOMAIN,proxy{i}.example,Proxy' for i in range(10001)]
                           + ['DOMAIN,one-ad.example,REJECT'] * 20001
                           + ['FINAL,direct'])
        with self.assertRaisesRegex(ValueError, 'unique coverage collapsed'):
            core.johnshall_entries(source, {}, lambda x, _: [x], minimum_lines=1)

    def test_full_source_sample_and_ads_hoisted(self):
        source = '\n'.join([f'DOMAIN,proxy{i}.example,Proxy' for i in range(10001)]
                           + [f'DOMAIN,ads{i}.example,REJECT' for i in range(20001)]
                           + ['IP-CIDR6,2001:4860::/32,DIRECT', 'FINAL,direct'])
        blocked, normal, stats = core.johnshall_entries(source, {}, lambda x, _: [x], minimum_lines=1)
        self.assertEqual(len(blocked), 20001)
        self.assertEqual(len(normal), 10002)
        self.assertEqual(stats['unsupported_rules'], 0)
        ordered = core.compact(blocked, 'Ads') + core.compact(normal, 'Johnshall')
        self.assertEqual(ordered[0]['outboundTag'], 'block')
        self.assertEqual(ordered[-1]['outboundTag'], 'direct')

    def test_bitbrowser_exact_process_not_chrome(self):
        self.assertEqual(core.load_processes('BitBrowser.exe\n'), ['BitBrowser.exe'])
        self.assertEqual(core.load_processes('C:\\BitBrowser\\resources\\BitBrowser.exe\n'),
                         ['C:\\BitBrowser\\resources\\BitBrowser.exe'])
        with self.assertRaises(ValueError):
            core.load_processes('chrome.exe')
        with self.assertRaises(ValueError):
            core.load_processes('C:\\Program Files\\Google\\Chrome\\chrome.exe')
        with self.assertRaises(ValueError):
            core.load_processes('nonexistent')
        self.assertEqual(core.load_processes('# only a comment'), [])

    def test_bitbrowser_list_status_provenance(self):
        entries = core.load_bitbrowser_domains(builder.BITBROWSER.read_text(encoding='utf-8'))
        self.assertEqual(len(entries), 11)
        self.assertFalse(any(domain == 'bitbrowser.com' for domain, _, _ in entries))
        self.assertEqual(sum(status == 'official' for _, status, _ in entries), 3)
        self.assertEqual(sum(status == 'user' for _, status, _ in entries), 8)
        self.assertEqual(sum(status != 'official' for _, status, _ in entries), 8)
        self.assertEqual(core.load_processes(builder.PROCESSES.read_text(encoding='utf-8')),
                         ['BitBrowser.exe'])
        with self.assertRaises(ValueError):
            core.load_bitbrowser_domains('bitbrowser.cn|official|x|https://example.com')

    def test_openai_explicit_user_extras(self):
        entries = builder.parse_user_extra(builder.OPENAI_EXTRA.read_text(encoding='utf-8'))
        self.assertIn(('domain', 'full:challenges.cloudflare.com', 'proxy'), entries)
        self.assertIn(('domain', 'full:js.stripe.com', 'proxy'), entries)
        self.assertIn(('domain', 'domain:chatgpt.com', 'proxy'), entries)
        self.assertIn(('domain', 'domain:featuregates.org', 'proxy'), entries)
        self.assertTrue(any(x[1].startswith('regexp:^chatgpt-async') for x in entries))
        with self.assertRaises(ValueError):
            builder.parse_user_extra('regexp:bad.*')

    def test_json_schema_round_trip(self):
        rules = [{'remarks': 'ads', 'domain': ['full:ads.example'], 'outboundTag': 'block', 'enabled': True},
                 {'remarks': 'bit', 'process': ['BitBrowser.exe'], 'outboundTag': 'proxy', 'enabled': True},
                 {'remarks': 'fallback', 'port': '0-65535', 'outboundTag': 'direct', 'enabled': True}]
        data = core.json_bytes(rules)
        self.assertEqual(json.loads(data), rules)
        self.assertIsInstance(json.loads(data), list)
        self.assertNotIn(b'outbounds', data)
        # The v2rayN routing subscription must never bind either configured node.
        self.assertNotIn('Hinet🇹🇼台湾'.encode('utf-8'), data)
        self.assertNotIn('Altare🇸🇬新加坡'.encode('utf-8'), data)
        with self.assertRaises(ValueError):
            core.validate_rules([], {})
        with self.assertRaises(ValueError):
            core.validate_rules(rules[:-1], {})

    def test_output_validates_large_counts(self):
        data = core.compact([('domain', 'full:ads.example', 'block')] * 20001, 'ads')
        data += core.compact([('domain', 'full:proxy.example', 'proxy')] * 10001, 'proxy')
        data += [{'remarks': 'FINAL', 'port': '0-65535', 'outboundTag': 'direct', 'enabled': True}]
        stats = core.validate_rules(data, {'johnshall_lines': 50000})
        self.assertGreaterEqual(stats['block_rules'], 20000)
        self.assertGreaterEqual(stats['proxy_rules'], 10000)
        self.assertEqual(stats['routing_objects'], len(data))


class SafetyTests(unittest.TestCase):
    def setUp(self):
        # Unit tests simulate a legitimate main release rather than PR CI.
        env = patch.dict('os.environ', {'GITHUB_REF': 'refs/heads/main'})
        env.start()
        self.addCleanup(env.stop)

    def test_publish_rejects_non_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'status.json'
            path.write_text(json.dumps({'shadowrocket_ai': {'exit_code': 0},
                                        'v2rayn': {'exit_code': 0}}))
            with patch.dict('os.environ', {'GITHUB_ACTIONS': 'true',
                                           'GITHUB_REF': 'refs/heads/test'}):
                with patch.object(publish, 'git') as git:
                    publish.publish(path)
                    git.assert_not_called()
            self.assertIn('Refusing publish outside refs/heads/main',
                          json.loads(path.read_text())['publish']['error'])

    def test_independent_size_guards(self):
        present = {name: 1000 for name in
                   ('johnshall_lines', 'johnshall_proxy_rules', 'johnshall_block_rules',
                    'voice_prefixes', 'voice_ipv4_addresses', 'voice_ipv6_addresses',
                    'auto_domains', 'manual_domains', 'bitbrowser_domains',
                    'domain_rules', 'ip_rules', 'block_rules')}
        builder.safety_check(present, None)
        baseline = {'statistics': deepcopy(present)}
        builder.safety_check(present, baseline)
        altered = deepcopy(present)
        altered['johnshall_block_rules'] = 300
        with self.assertRaisesRegex(ValueError, 'UPSTREAM ANOMALY'):
            builder.safety_check(altered, baseline)
        altered = deepcopy(present)
        altered['voice_ipv4_addresses'] = 2200
        with self.assertRaisesRegex(ValueError, 'UPSTREAM ANOMALY'):
            builder.safety_check(altered, baseline)

    def test_atomic_unchanged_and_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'out.json'
            builder.atomically_write(path, b'[1]\n')
            builder.atomically_write(path, b'[1]\n')
            self.assertEqual(path.read_bytes(), b'[1]\n')
            builder.atomically_write(path, b'[2]\n')
            self.assertEqual(path.read_bytes(), b'[2]\n')

    def test_both_success_both_fail_and_partial_failure_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'status.json'
            for shadow, v2, publish_good in ((0, 0, True), (1, 0, True), (0, 1, True),
                                             (1, 1, True), (0, 0, False)):
                path.write_text(json.dumps({'shadowrocket_ai': {'exit_code': shadow},
                                            'v2rayn': {'exit_code': v2},
                                            'publish': {'success': publish_good}}))
                self.assertEqual(publish.check(path), 0 if (shadow, v2, publish_good) == (0, 0, True) else 1)

    def test_only_two_published_client_artifacts(self):
        self.assertEqual(builder.CONFIG.name, 'v2rayN_Johnshall_AI.json')
        self.assertIn('Shadowrocket_Johnshall_AI.conf', publish.SHADOW_AI_FILES)
        self.assertIn('v2rayN_Johnshall_AI.json', publish.V2_FILES)
        self.assertNotIn('Shadowrocket_Johnshall_OpenAI.conf', publish.SHADOW_AI_FILES)
        self.assertNotIn('v2rayN_Johnshall_OpenAI.json', publish.V2_FILES)

    def test_no_change_no_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'status.json'
            path.write_text(json.dumps({'shadowrocket_ai': {'exit_code': 0},
                                        'v2rayn': {'exit_code': 0}}))
            calls = []
            def fake_git(*args):
                calls.append(args)
                return type('R', (), {'stdout': ''})()
            with patch.object(publish, 'git', side_effect=fake_git):
                publish.publish(path)
            self.assertTrue(json.loads(path.read_text())['publish']['success'])
            self.assertFalse(any(call[0] == 'commit' for call in calls))

    def test_git_push_failure_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'status.json'
            path.write_text(json.dumps({'shadowrocket_ai': {'exit_code': 0},
                                        'v2rayn': {'exit_code': 0}}))
            def fake_git(*args):
                if args[0] == 'push':
                    raise RuntimeError('remote rejected push')
                return type('R', (), {'stdout': 'Shadowrocket_Johnshall_AI.conf\n' if args[0] == 'diff' else '1234\n'})()
            with patch.object(publish, 'git', side_effect=fake_git):
                publish.publish(path)
            status = json.loads(path.read_text())
            self.assertFalse(status['publish']['success'])
            self.assertIn('remote rejected', status['publish']['error'])

    def test_publisher_rejects_unexpected_staged_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'status.json'
            path.write_text(json.dumps({'shadowrocket_ai': {'exit_code': 0},
                                        'v2rayn': {'exit_code': 0}}))
            def fake_git(*args):
                return type('R', (), {'stdout': 'README.md\n' if args[0] == 'diff' else ''})()
            with patch.object(publish, 'git', side_effect=fake_git):
                publish.publish(path)
            result = json.loads(path.read_text())['publish']
            self.assertFalse(result['success'])
            self.assertIn('Unexpected staged publish paths', result['error'])

    def test_telegram_missing_report_is_not_success(self):
        state = {'shadowrocket_ai': {'exit_code': 0},
                 'v2rayn': {'exit_code': 0},
                 'publish': {'success': True, 'state': 'published'}}
        msg = notify.emit_message(state, None, {}, when='2026-11-23 11:00',
                                  event='schedule', run_url='')
        self.assertIn('总体状态：部分成功', msg)

    def test_telegram_missing_secret_does_not_ack(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = Path(tmp) / 's.json'
            status.write_text(json.dumps({'shadowrocket_ai': {'exit_code': 0},
                                          'v2rayn': {'exit_code': 1, 'error': 'download failed'},
                                          'reports': {},
                                          'publish': {'success': True, 'state': 'published'}}))
            with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': '', 'TELEGRAM_CHAT_ID': ''}):
                with patch.object(notify.review_queue, 'acknowledge') as ack:
                    self.assertEqual(notify.main.__name__, 'main')
                    with patch.object(sys, 'argv', ['notify_combined.py', '--status-file', str(status)]):
                        self.assertEqual(notify.main(), 1)
                    ack.assert_not_called()

    def test_single_telegram_message_sent_even_if_v2_fails(self):
        status = {'shadowrocket_ai': {'exit_code': 0},
                  'v2rayn': {'exit_code': 1, 'error': 'upstream incomplete'},
                  'publish': {'success': True, 'state': 'published',
                              'changed_files': ['Shadowrocket_Johnshall_AI.conf']}}
        shadow = {'config_changed': True, 'statistics': {'johnshall_lines': 120000},
                  'new_excluded_candidates': [], 'review_due_candidates': []}
        msg = notify.emit_message(status, shadow, None, when='2026-11-23 11:00:00',
                                  event='schedule', run_url='https://github.com/example/actions/runs/123')
        self.assertIn('Shadowrocket 小火箭', msg)
        self.assertIn('v2rayN', msg)
        self.assertIn('保留上一次已发布版本', msg)
        self.assertIn('upstream incomplete', msg)
        self.assertIn('2026-11-23', msg)
        self.assertEqual(msg.count('📡 每日代理规则更新报告'), 1)


if __name__ == '__main__':
    unittest.main()
