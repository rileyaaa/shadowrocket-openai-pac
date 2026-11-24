"""Strict no-network checks for AI feed parsing and approval safeguards."""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ai_services as ai

class AIInputTests(unittest.TestCase):
    def test_sources_are_four_live_raw_lists_not_include_alias(self):
        self.assertEqual(set(ai.SOURCES), {'gemini_v2fly','gemini_metacubex','claude_v2fly','claude_metacubex'})
        self.assertTrue(all(url.startswith('https://raw.githubusercontent.com/') for _, _, url in ai.SOURCES.values()))
        self.assertIn('/google-deepmind', ai.SOURCES['gemini_v2fly'][2])
        self.assertNotIn('/google-gemini', ai.SOURCES['gemini_v2fly'][2])

    def test_unknown_feed_syntax_fails_closed(self):
        for kind in ('v2fly', 'meta'):
            with self.assertRaises(ValueError):
                ai.parse_feed('include:other\n'*50,kind,'gemini')
            with self.assertRaises(ValueError):
                ai.parse_feed('regexp:.*\n'*50,kind,'gemini')

    def test_explicit_v2fly_suffix_and_metadata_preserve_scope(self):
        rest = '\n'.join(f'ex{i}.claude.ai' for i in range(12))
        plain = ai.parse_feed('claude.ai\nfull:api.anthropic.com\n'+rest, 'v2fly', 'claude')
        annotated = ai.parse_feed('domain:claude.ai\t@ai # note\nfull:api.anthropic.com\t# note\n'+rest,
                                  'v2fly', 'claude')
        self.assertEqual(plain, annotated)
        self.assertIn(('DOMAIN-SUFFIX','claude.ai'), annotated)
        self.assertIn(('DOMAIN','api.anthropic.com'), annotated)
        with self.assertRaises(ValueError):
            ai.parse_feed('domain:claude.ai\n'+rest, 'meta', 'claude')

    def test_google_shared_host_only_exact(self):
        self.assertTrue(ai.is_approved('gemini','DOMAIN-SUFFIX','generativelanguage.googleapis.com'))
        self.assertEqual(ai.normalize_approved('gemini','DOMAIN-SUFFIX','generativelanguage.googleapis.com'),
                         ('DOMAIN','generativelanguage.googleapis.com'))
        self.assertFalse(ai.is_approved('gemini','DOMAIN-SUFFIX','googleapis.com'))
        self.assertFalse(ai.is_approved('gemini','DOMAIN','unverified.googleapis.com'))
        self.assertTrue(ai.is_approved('gemini','DOMAIN-SUFFIX','new.gemini.google.com'))
        self.assertFalse(ai.is_approved('claude','DOMAIN-SUFFIX','random.sentry.io'))

    def test_manual_rejects_ads_and_overbroad_suffix(self):
        with self.assertRaises(ValueError):
            ai.load_manual('GEMINI,DOMAIN-SUFFIX,googleapis.com\nCLAUDE,DOMAIN,api.anthropic.com')
        with self.assertRaises(ValueError):
            ai.load_manual('GEMINI,DOMAIN,googleads.g.doubleclick.net\nCLAUDE,DOMAIN,api.anthropic.com')
        parsed=ai.load_manual(ai.MANUAL.read_text(encoding='utf-8'))
        self.assertIn('DOMAIN,jules.googleapis.com', parsed['gemini'])
        self.assertIn('DOMAIN,antigravity.google.com', parsed['gemini'])
        self.assertIn('DOMAIN,businessaicode.googleapis.com', parsed['gemini'])
        self.assertIn('DOMAIN,notebooklm.cloud.google.com', parsed['gemini'])
        for shared in ('jnn-pa.googleapis.com', 'waa-pa.clients6.google.com',
                       'geller-pa.googleapis.com', 'proactivebackend-pa.googleapis.com'):
            self.assertNotIn('DOMAIN,' + shared, parsed['gemini'])
            self.assertNotIn(shared, ai.APPROVED_HOSTS['gemini'])
        self.assertNotIn('DOMAIN,accounts.google.com',parsed['gemini'])
        self.assertNotIn('DOMAIN,fonts.gstatic.com',parsed['gemini'])
        self.assertNotIn('DOMAIN,play.google.com',parsed['gemini'])
        for shared_google in ('accounts.google.com', 'www.googleapis.com',
                              'fonts.googleapis.com', 'fonts.gstatic.com',
                              'ssl.gstatic.com', 'play.google.com', 'ogs.google.com'):
            self.assertNotIn('DOMAIN,' + shared_google, parsed['gemini'])
        self.assertIn('DOMAIN,api.anthropic.com',parsed['claude'])
        self.assertIn('DOMAIN,browser-intake-us5-datadoghq.com', parsed['claude'])
        self.assertNotIn('DOMAIN-SUFFIX,datadoghq.com', parsed['claude'])
        self.assertNotIn('DOMAIN-SUFFIX,sentry.io', parsed['claude'])

    def test_gemini_core_is_pinned_against_feed_removal(self):
        pinned = set(ai.load_manual(ai.MANUAL.read_text(encoding='utf-8'))['gemini'])
        self.assertTrue(ai.MANDATORY['gemini'].issubset(pinned))

    def test_claude_core_is_pinned_against_feed_removal(self):
        pinned = set(ai.load_manual(ai.MANUAL.read_text(encoding='utf-8'))['claude'])
        self.assertTrue(ai.MANDATORY['claude'].issubset(pinned))
        self.assertNotIn('DOMAIN-SUFFIX,datadoghq.com', pinned)

    def test_rejected_under_approved_suffix_is_a_blocking_conflict(self):
        approved = {'gemini': {'DOMAIN,antigravity.google.com'},
                    'claude': {'DOMAIN-SUFFIX,claude.ai'}}
        policy = {'rejected_rules': [{'service': 'claude', 'rule': 'DOMAIN,sub.claude.ai'}]}
        with self.assertRaisesRegex(ValueError, 'approved/rejected rule conflict'):
            ai.check_rejection_conflicts(approved, policy)
        policy['rejected_rules'] = [{'service': 'claude', 'rule': 'DOMAIN,unrelated.example'}]
        ai.check_rejection_conflicts(approved, policy)

    def test_rejected_parent_suffix_allows_separately_reviewed_narrow_scope(self):
        approved = {'gemini': set(), 'claude': {'DOMAIN,o1158394.ingest.us.sentry.io'}}
        policy = {'rejected_rules': [{'service': 'claude', 'rule': 'DOMAIN-SUFFIX,sentry.io'}]}
        ai.check_rejection_conflicts(approved, policy)
        policy['rejected_rules'][0]['rule'] = 'DOMAIN,o1158394.ingest.us.sentry.io'
        with self.assertRaisesRegex(ValueError, 'approved/rejected rule conflict'):
            ai.check_rejection_conflicts(approved, policy)

    def test_rejection_hostname_must_be_canonical(self):
        for host in ('API.ANTHROPIC.COM', 'api.anthropic.com.', 'api.anthropic.com '):
            with self.subTest(host=host):
                policy = {'version': 1, 'default_review_months': 6,
                          'reminder_interval_days': 7,
                          'rejected_rules': [{
                              'service': 'claude', 'rule': 'DOMAIN,' + host,
                              'reason': 'Manual security decision',
                              'reviewed_at': '2026-11-23'}]}
                with self.assertRaises(ValueError):
                    ai.evaluate_review_policy([], policy, on=date(2026, 11, 23))

    def test_antigravity_updaters_are_required_but_unrelated_runapp_is_not(self):
        for host in ('antigravity-cli-auto-updater-974169037036.us-central1.run.app',
                     'antigravity-hub-auto-updater-974169037036.us-central1.run.app'):
            self.assertIn('DOMAIN,' + host, ai.MANDATORY['gemini'])
        self.assertFalse(ai.is_approved('gemini', 'DOMAIN',
                                        'another-tenant.us-central1.run.app'))

    def test_two_source_formats_preserve_exact_vs_suffix(self):
        v='full:api.anthropic.com\nclaude.ai\n' + '\n'.join(f'ex{i}.claude.ai' for i in range(11))
        m='api.anthropic.com\n+.claude.ai\n' + '\n'.join(f'+.ex{i}.claude.ai' for i in range(11))
        a=ai.parse_feed(v,'v2fly','claude')
        b=ai.parse_feed(m,'meta','claude')
        self.assertIn(('DOMAIN','api.anthropic.com'),a)
        self.assertIn(('DOMAIN-SUFFIX','claude.ai'),a)
        self.assertIn(('DOMAIN','api.anthropic.com'),b)
        self.assertIn(('DOMAIN-SUFFIX','claude.ai'),b)

    def test_approved_candidate_queue_not_auto_approved(self):
        gem=['gemini.google.com','generativelanguage.googleapis.com','unknown.cloudflare.com']
        gem+= [f'test{i}.gemini.google.com' for i in range(30)]
        cla=['claude.ai','anthropic.com','random.sentry.io'] + [f'c{i}.claude.ai' for i in range(12)]
        blob={'gemini_v2fly': ('\n'.join(gem)).encode(),
              'gemini_metacubex': ('\n'.join('+.'+x for x in gem)).encode(),
              'claude_v2fly': ('\n'.join(cla)).encode(),
              'claude_metacubex': ('\n'.join('+.'+x for x in cla)).encode()}
        data=ai.collect(lambda url, minimum: (_ for _ in ()).throw(RuntimeError('unexpected fetch')),
                        source_overrides=blob)
        self.assertIn('DOMAIN-SUFFIX,claude.ai',data['rules']['claude'])
        self.assertIn('DOMAIN,generativelanguage.googleapis.com',data['rules']['gemini'])
        self.assertFalse(any('cloudflare.com' in v for v in data['rules']['gemini']))
        self.assertTrue(any('cloudflare.com' in q['rule'] for q in data['review_candidates']))
        self.assertTrue(any('sentry.io' in q['rule'] for q in data['review_candidates']))
        self.assertIn('待审核',ai.render_review_queue(data))

    def test_manual_approval_coverage_not_just_overlap(self):
        self.assertTrue(ai.approved_rule_covers('DOMAIN,x.example', 'DOMAIN,x.example'))
        self.assertFalse(ai.approved_rule_covers('DOMAIN,x.example', 'DOMAIN-SUFFIX,x.example'))
        self.assertTrue(ai.approved_rule_covers('DOMAIN-SUFFIX,x.example', 'DOMAIN,y.x.example'))
        self.assertFalse(ai.approved_rule_covers('DOMAIN-SUFFIX,x.example', 'DOMAIN-SUFFIX,example'))
        gem = ['gemini.google.com', 'generativelanguage.googleapis.com', 'unknown.cloudflare.com']
        gem += [f'test{i}.gemini.google.com' for i in range(30)]
        cla = ['claude.ai', 'anthropic.com'] + [f'c{i}.claude.ai' for i in range(12)]
        feeds = {'gemini_v2fly': ('\n'.join(gem)).encode(),
                 'gemini_metacubex': ('\n'.join(gem)).encode(),
                 'claude_v2fly': ('\n'.join(cla)).encode(),
                 'claude_metacubex': ('\n'.join('+.' + x for x in cla)).encode()}
        with tempfile.TemporaryDirectory() as tmp:
            manual = Path(tmp) / 'manual.rules'
            manual.write_text(ai.MANUAL.read_text(encoding='utf-8') +
                              '\nGEMINI,DOMAIN,unknown.cloudflare.com\n', encoding='utf-8')
            result = ai.collect(None, source_overrides=feeds, manual_path=manual)
        self.assertIn('DOMAIN,unknown.cloudflare.com', result['rules']['gemini'])
        self.assertNotIn('DOMAIN,unknown.cloudflare.com', [x['rule'] for x in result['review_candidates']])
        self.assertIn('DOMAIN-SUFFIX,unknown.cloudflare.com', [x['rule'] for x in result['review_candidates']])

    def test_rejected_candidate_six_month_review_remains_rejected(self):
        candidate = {'service': 'claude', 'rule': 'DOMAIN-SUFFIX,antspace.dev',
                     'sources': ['claude_v2fly'], 'reason': 'Unverified'}
        policy = {'version': 1, 'default_review_months': 6,
                  'reminder_interval_days': 7,
                  'rejected_rules': [{'service': 'claude', 'rule': 'DOMAIN-SUFFIX,antspace.dev',
                                      'reason': 'Unconfirmed tenant domain', 'reviewed_at': '2026-01-31'}]}
        records, counts = ai.evaluate_review_policy([candidate], policy, on=date(2026, 7, 30))
        self.assertEqual(records[0]['review_due_on'], '2026-07-31')
        self.assertEqual(records[0]['status'], 'cooling')
        self.assertEqual(counts, {'pending': 0, 'cooling': 1, 'due': 0})
        records, counts = ai.evaluate_review_policy([candidate], policy, on=date(2026, 7, 31))
        self.assertEqual(records[0]['status'], 'due')
        self.assertEqual(counts['due'], 1)
        self.assertIn('到期复审', ai.render_review_queue({'review_candidates': records}))
        policy['rejected_rules'][0]['reviewed_at'] = '2027-01-01'
        with self.assertRaisesRegex(ValueError, 'future'):
            ai.evaluate_review_policy([candidate],policy,on=date(2026,7,31))

    def test_rejection_policy_validation(self):
        p = {'version': 1, 'default_review_months': 6, 'reminder_interval_days': 7,
             'rejected_rules': []}
        rows, counts = ai.evaluate_review_policy([{'service': 'gemini',
            'rule': 'DOMAIN,unknown.googleapis.com', 'sources': ['x']}],p,on=date(2026,11,23))
        self.assertEqual(counts['pending'],1)
        self.assertEqual(rows[0]['status'],'pending')
        p['default_review_months'] = 0
        with self.assertRaises(ValueError):
            ai.evaluate_review_policy([],p)

    def test_one_time_reviewed_gemini_scope_reduction(self):
        before = {'gemini_domains': 72, 'claude_domains': 19,
                  'gemini_v2fly': 49, 'gemini_metacubex': 49,
                  'claude_v2fly': 21, 'claude_metacubex': 21}
        after = dict(before, gemini_domains=51)
        # Old one-time migration exception does not match the new reviewed
        # manual scope. Newly shrinking rules must have a fresh specific review.
        with self.assertRaisesRegex(ValueError, 'AI SOURCE ANOMALY'):
            ai.validate_safety(after, {'ai_counts': before})
        with self.assertRaisesRegex(ValueError, 'AI SOURCE ANOMALY'):
            ai.validate_safety(dict(after, gemini_domains=50), {'ai_counts': before})
        with self.assertRaisesRegex(ValueError, 'AI SOURCE ANOMALY'):
            ai.validate_safety(dict(after, gemini_domains=37), {'ai_counts': after})

    def test_anomaly_fails_publication(self):
        now={'gemini_domains':50,'claude_domains':15}
        now.update({key:49 if key.startswith('gemini') else 21 for key in ai.SOURCES})
        ai.validate_safety(now,None)
        ai.validate_safety(now,{'ai_counts':now})
        bad=now.copy(); bad['gemini_domains']=15
        with self.assertRaisesRegex(ValueError,'AI SOURCE ANOMALY'):
            ai.validate_safety(bad,{'ai_counts':now})

if __name__ == '__main__':
    unittest.main()
