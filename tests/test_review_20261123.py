"""Review-decision snapshot acceptance for the 2026-11-23 renewal.

No routes are granted by review metadata; this confirms dates, candidate
coverage, and six-calendar-month expiry without relying on wall-clock time.
"""
from datetime import date
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ai_services
import review_queue

REVIEWED = date(2026, 11, 23)
DUE = date(2027, 5, 23)


class ReviewedSnapshotTests(unittest.TestCase):
    def test_openai_20_rejected_records_revalidated_and_renewed(self):
        policy = json.loads((ROOT / 'config/review-decisions.json').read_text(encoding='utf-8'))
        self.assertEqual(len(policy['rejected_rules']), 20)
        self.assertEqual(policy['default_review_months'], 6)
        review_queue.validate_policy(policy, REVIEWED)
        self.assertEqual(
            len({r['rule'] for r in policy['rejected_rules']}), 20)
        for entry in policy['rejected_rules']:
            self.assertEqual(entry['reviewed_at'], REVIEWED.isoformat())
            months = entry.get('review_after_months', policy['default_review_months'])
            self.assertEqual(review_queue.add_months(REVIEWED, months), DUE)
            self.assertTrue(entry['reason'])

    def test_gemini_claude_10_are_cooling_until_next_review(self):
        policy = json.loads((ROOT / 'config/ai-review-decisions.json').read_text(encoding='utf-8'))
        self.assertEqual(len(policy['rejected_rules']), 10)
        self.assertEqual(policy['default_review_months'], 6)
        candidates = [{'service': entry['service'], 'rule': entry['rule'],
                       'sources': ['fixture-review-source']}
                      for entry in policy['rejected_rules']]
        self.assertEqual(sum(r['service'] == 'claude' for r in policy['rejected_rules']), 8)
        self.assertEqual(sum(r['service'] == 'gemini' for r in policy['rejected_rules']), 2)
        self.assertTrue(all(r['reviewed_at'] == REVIEWED.isoformat()
                            for r in policy['rejected_rules']))
        before, counts = ai_services.evaluate_review_policy(candidates, policy, on=REVIEWED)
        self.assertEqual(counts, {'pending': 0, 'cooling': 10, 'due': 0})
        self.assertTrue(all(r['review_due_on'] == DUE.isoformat() for r in before))
        at_due, counts = ai_services.evaluate_review_policy(candidates, policy, on=DUE)
        self.assertEqual(counts, {'pending': 0, 'cooling': 0, 'due': 10})
        self.assertTrue(all(r['status'] == 'due' for r in at_due))

    def test_none_of_8_rejected_claude_suffixes_is_manually_approved(self):
        decisions = json.loads((ROOT / 'config/ai-review-decisions.json').read_text(encoding='utf-8'))
        rejected = {r['rule'] for r in decisions['rejected_rules'] if r['service'] == 'claude'}
        manual = ai_services.load_manual(
            (ROOT / 'config/ai-services.rules').read_text(encoding='utf-8'))
        self.assertFalse(rejected.intersection(manual['claude']))
        self.assertTrue(ai_services.MANDATORY['claude'].issubset(set(manual['claude'])))
        ai_services.check_rejection_conflicts({k: set(v) for k, v in manual.items()}, decisions)

    def test_google_shared_endpoints_remain_not_ai_approved(self):
        decisions = json.loads((ROOT / 'config/ai-review-decisions.json').read_text(encoding='utf-8'))
        refused = {r['rule'] for r in decisions['rejected_rules'] if r['service'] == 'gemini'}
        self.assertEqual(refused, {'DOMAIN-SUFFIX,geller-pa.googleapis.com',
                                   'DOMAIN-SUFFIX,proactivebackend-pa.googleapis.com'})
        manual = ai_services.load_manual(
            (ROOT / 'config/ai-services.rules').read_text(encoding='utf-8'))
        self.assertFalse(refused.intersection(manual['gemini']))


if __name__ == '__main__':
    unittest.main()
