from datetime import date, timedelta
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import openai_review_delivery as delivery
import review_queue as review
import ai_review_delivery

def observation(rule, common=(), extra=()):
    return {'openai_observation': {'excluded': {rule: ['fixture']} if rule else {},
                                   'common_rules': list(common), 'client_only_rules': list(extra)}}

class OpenAIReviewDeliveryTests(unittest.TestCase):
    def test_v2_only_new_candidate_not_suppressed_by_extra_and_monthly_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review.write_json(root / 'config/review-decisions.json', review.default_policy())
            rule = 'DOMAIN,extra.example'
            now = date(2026, 11, 24)
            with patch.object(delivery.legacy, 'parse_manual', return_value=[]):
                snapshots, result, state = delivery.merge({}, {'v2rayn': observation(rule, extra=[rule])}, root, on=now)
                self.assertEqual(result['counts']['pending'], 1)
                self.assertEqual(len(result['new_candidates']), 1)
                self.assertIn('客户端专属', result['entries'][0]['client_coverage']['v2rayn'])
                path = root / 'data/review-notifications.json'
                review.write_json(path, state)
                review.acknowledge(delivery.receipt_report(result), path, now)
                _, result, _ = delivery.merge(snapshots, {'v2rayn': observation(rule, extra=[rule])}, root, on=now+timedelta(days=29))
                self.assertEqual(result['new_candidates'], [])
                _, result, _ = delivery.merge(snapshots, {'v2rayn': observation(rule, extra=[rule])}, root, on=now+timedelta(days=30))
                self.assertEqual(len(result['new_candidates']), 1)

    def test_corrupt_coverage_snapshot_cannot_poison_future_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = root / delivery.SNAPSHOT
            raw = 'include:unknown'
            good = observation(raw, common=['DOMAIN,api.openai.com'])['openai_observation']
            review.write_json(snapshot, {'version':1, 'snapshots':{'v2rayn':good}})
            self.assertEqual(delivery.read_state(snapshot)['v2rayn'],good)
            for bad in ('DOMAIN,*.example.com','DOMAIN,UPPER.example','INVALID,example.com'):
                row = observation(raw, common=[bad])['openai_observation']
                review.write_json(snapshot, {'version':1,'snapshots':{'v2rayn':row}})
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    delivery.read_state(snapshot)
                with self.assertRaises(ValueError):
                    delivery.merge({}, {'v2rayn':{'openai_observation':row}}, root)
            row = observation(raw)['openai_observation']
            row['excluded'][raw] = []
            with self.assertRaises(ValueError):
                delivery.validate_observation(row)

    def test_exact_wildcard_coverage_matches_manual_rejection_guard(self):
        pattern = 'DOMAIN-WILDCARD,chatgpt-async-webps-prod-*.webpubsub.azure.com'
        host = 'DOMAIN,chatgpt-async-webps-prod-x.webpubsub.azure.com'
        broad = 'DOMAIN-SUFFIX,chatgpt-async-webps-prod-x.webpubsub.azure.com'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review.write_json(root / 'config/review-decisions.json', review.default_policy())
            with patch.object(delivery.legacy, 'parse_manual', return_value=[pattern]):
                _, result, _ = delivery.merge({}, {'v2rayn': observation(host, [pattern])}, root)
                self.assertEqual(result['counts']['covered'], 1)
                self.assertEqual(result['new_candidates'], [])
                self.assertEqual(result['entries'][0]['client_coverage']['v2rayn'], '共用规则覆盖')
                _, result, _ = delivery.merge({}, {'v2rayn': observation(broad, [pattern])}, root)
                self.assertEqual(result['counts']['pending'], 1)
                self.assertEqual(len(result['new_candidates']), 1)
            with patch.object(delivery.legacy, 'parse_manual', return_value=[]):
                _, result, _ = delivery.merge({}, {'v2rayn': observation(host, extra=[pattern])}, root)
                self.assertEqual(result['counts']['pending'], 1)
                self.assertIn('客户端专属例外覆盖', result['entries'][0]['client_coverage']['v2rayn'])

    def test_approved_but_stale_client_not_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review.write_json(root / 'config/review-decisions.json', review.default_policy())
            rule = 'DOMAIN,new.example'
            old = {'v2rayn': observation(rule)['openai_observation']}
            with patch.object(delivery.legacy, 'parse_manual', return_value=[rule]):
                _, result, _ = delivery.merge(old, {'shadowrocket_ai': observation(None, [rule])}, root)
            self.assertEqual(result['counts']['pending'], 0)
            self.assertEqual(len(result['deployment_pending']), 1)
            self.assertEqual(result['new_candidates'], [])

    def test_gemini_stale_approval_waits_for_deployment(self):
        candidate = {'service': 'gemini','rule':'DOMAIN,new.example','sources':['fixture']}
        state = ai_review_delivery.empty_state()
        state['snapshots']['v2rayn'] = [candidate]
        _, result = ai_review_delivery.merge_reports(state, {
            'shadowrocket_ai': {'ai_review_candidates': [],'ai_approved_rules':{'gemini':[candidate['rule']]}}},
            review.default_policy())
        self.assertEqual(result['review_counts']['pending'], 0)
        self.assertEqual(result['deployment_pending'][0]['rule'], candidate['rule'])
        self.assertEqual(result['alerts'], [])

if __name__ == '__main__':
    unittest.main()
