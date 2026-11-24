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
