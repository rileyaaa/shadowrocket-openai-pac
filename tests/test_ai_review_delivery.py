"""Offline candidate merging and durable reminder regressions."""
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ai_review_delivery as delivery

def candidate(rule, sources):
    return {'service': 'claude', 'rule': rule, 'sources': sources}

class SharedReviewTests(unittest.TestCase):
    def setUp(self):
        self.now = date(2027, 5, 23)
        self.policy = {'version': 1, 'default_review_months': 6, 'reminder_interval_days': 7,
                       'rejected_rules': [{'service': 'claude', 'rule': 'DOMAIN,old.example',
                                           'reason': 'Review before allowing', 'reviewed_at': '2026-11-23'}]}

    def test_merge_deduplicates_and_retains_failed_client_snapshot(self):
        a = candidate('DOMAIN,a.example', ['v2fly'])
        b = candidate('DOMAIN,a.example', ['meta'])
        c = candidate('DOMAIN,c.example', ['meta'])
        state, report = delivery.merge_reports(delivery.empty_state(), {
            'shadowrocket_ai': {'ai_review_candidates': [a]},
            'v2rayn': {'ai_review_candidates': [b, c]}}, self.policy, on=self.now)
        self.assertEqual(report['review_counts']['pending'], 2)
        self.assertEqual(report['review_candidates'][0]['sources'], ['meta', 'v2fly'])
        state, report = delivery.merge_reports(state, {
            'shadowrocket_ai': {'ai_review_candidates': []}}, self.policy, on=self.now)
        self.assertEqual(report['review_counts']['pending'], 2)
        self.assertEqual(report['stale_clients'], ['v2rayn'])

    def test_due_and_pending_repeat_only_after_configured_interval(self):
        rows = [candidate('DOMAIN,new.example', ['meta']), candidate('DOMAIN,old.example', ['v2fly'])]
        reports = {'v2rayn': {'ai_review_candidates': rows}}
        state, report = delivery.merge_reports(delivery.empty_state(), reports, self.policy, on=self.now)
        self.assertEqual(len(report['alerts']), 2)
        state, report = delivery.merge_reports(state, reports, self.policy, on=self.now)
        self.assertEqual(len(report['alerts']), 2)
        for item in report['alerts']:
            state['sent'][item['key']] = {'cycle': item['cycle'], 'notified_at': self.now.isoformat()}
        state, report = delivery.merge_reports(state, reports, self.policy, on=self.now + timedelta(days=6))
        self.assertEqual(report['alerts'], [])
        state, report = delivery.merge_reports(state, reports, self.policy, on=self.now + timedelta(days=7))
        self.assertEqual([x['rule'] for x in report['alerts']], ['DOMAIN,new.example', 'DOMAIN,old.example'])

if __name__ == '__main__':
    unittest.main()
