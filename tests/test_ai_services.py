"""Strict no-network checks for AI feed parsing and approval safeguards."""
from __future__ import annotations
import json
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
        self.assertIn('DOMAIN,accounts.google.com',parsed['gemini'])
        self.assertIn('DOMAIN,api.anthropic.com',parsed['claude'])

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
