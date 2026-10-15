"""Calendar expiry, durable notification delivery, and routing boundaries."""
import contextlib
import copy
from datetime import date
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build
import notify_telegram
import review_queue as review


class ManualReviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.policy_path = self.root / "config/review-decisions.json"
        self.state_path = self.root / "data/review-notifications.json"
        self.rule = "DOMAIN-SUFFIX,vendor.example"
        self.candidates = {self.rule: ["v2fly", "metacubex"]}
        self.policy = review.default_policy()
        self.on = date(2026, 10, 15)
        review.write_json(self.policy_path, self.policy)

    def reject(self, at="2026-04-15", months=None, rule=None):
        item = {"rule": rule or self.rule, "reason": "证据不足，半年后复核", "reviewed_at": at}
        if months is not None:
            item["review_after_months"] = months
        self.policy["rejected_rules"].append(item)
        review.write_json(self.policy_path, self.policy)

    def evaluate(self, on=None, previous=None, active=None):
        result, state = review.evaluate(
            self.candidates, list(self.candidates) if previous is None else previous,
            active or [], build.domain_rule_covers, self.root, on or self.on)
        review.write_json(self.state_path, state)
        return result

    def ack(self, result, on=None):
        review.acknowledge({"new_excluded_candidates": result["new_candidates"],
                            "review_due_candidates": result["due_candidates"]},
                           self.state_path, on or self.on)

    def test_calendar_month_end_and_leap_year(self):
        self.assertEqual(review.add_months(date(2026, 8, 31), 6), date(2027, 2, 28))
        self.assertEqual(review.add_months(date(2027, 8, 31), 6), date(2028, 2, 29))
        self.assertEqual(review.add_months(date(2024, 2, 29), 12), date(2025, 2, 28))

    def test_default_six_months_expiry_is_inclusive(self):
        self.reject()
        early = self.evaluate(date(2026, 10, 14), previous=[])
        self.assertEqual(early["counts"]["cooling"], 1)
        self.assertEqual(early["new_candidates"], [])
        self.assertEqual(early["due_candidates"], [])
        due = self.evaluate()
        self.assertEqual(due["due_candidates"][0]["review_due_on"], "2026-10-15")
        self.assertEqual(due["counts"]["due"], 1)

    def test_twelve_month_override_and_global_default(self):
        self.reject(months=12)
        self.assertEqual(self.evaluate()["counts"]["cooling"], 1)
        self.assertEqual(len(self.evaluate(date(2027, 4, 15))["due_candidates"]), 1)
        self.policy["rejected_rules"][0].pop("review_after_months")
        self.policy["default_review_months"] = 12
        review.write_json(self.policy_path, self.policy)
        self.assertEqual(self.evaluate()["counts"]["cooling"], 1)

    def test_missed_run_is_caught_up_and_failed_delivery_retries(self):
        self.reject()
        late = self.evaluate(date(2026, 11, 3))
        self.assertEqual(len(late["due_candidates"]), 1)
        self.assertEqual(len(self.evaluate(date(2026, 11, 4))["due_candidates"]), 1)
        self.ack(late, date(2026, 11, 4))
        self.assertEqual(self.evaluate(date(2026, 11, 10))["due_candidates"], [])
        self.assertEqual(len(self.evaluate(date(2026, 11, 11))["due_candidates"]), 1)

    def test_re_review_renews_date_and_retains_per_rule_month_override(self):
        self.reject(at="2025-10-15", months=12)
        self.ack(self.evaluate())
        review.record_rejection(self.policy_path, self.rule, "仍缺乏依据", on=self.on)
        updated = json.loads(self.policy_path.read_text())["rejected_rules"]
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]["review_after_months"], 12)
        self.assertEqual(updated[0]["reviewed_at"], "2026-10-15")
        self.assertEqual(self.evaluate()["counts"]["cooling"], 1)
        self.assertEqual(len(self.evaluate(date(2027, 10, 15))["due_candidates"]), 1)

    def test_rejection_never_inherits_to_other_rules_or_subdomains(self):
        self.reject(at="2026-10-01")
        new_rule = "DOMAIN,login.vendor.example"
        self.candidates[new_rule] = ["v2fly"]
        result = self.evaluate(previous=[])
        self.assertEqual([item["rule"] for item in result["new_candidates"]], [new_rule])
        self.assertEqual(result["counts"]["cooling"], 1)

    def test_vanished_candidate_stops_reminding_and_returning_one_keeps_decision(self):
        self.reject()
        self.candidates = {}
        self.assertEqual(self.evaluate()["due_candidates"], [])
        self.assertEqual(len(json.loads(self.policy_path.read_text())["rejected_rules"]), 1)
        self.candidates = {self.rule: ["v2fly"]}
        self.assertEqual(len(self.evaluate(previous=[])["due_candidates"]), 1)

    def test_new_candidate_survives_committed_baseline_until_delivery(self):
        first = self.evaluate(previous=[])
        self.assertEqual(len(first["new_candidates"]), 1)
        self.assertEqual(len(self.evaluate()["new_candidates"]), 1)
        self.ack(first)
        self.assertEqual(self.evaluate()["new_candidates"], [])

    def test_initial_migration_does_not_relabel_old_candidates_as_new(self):
        result, _ = review.evaluate(self.candidates, None, [], build.domain_rule_covers, self.root, self.on)
        self.assertEqual(result["new_candidates"], [])
        self.assertEqual(result["counts"]["pending"], 1)
        self.assertEqual(json.loads(self.policy_path.read_text())["rejected_rules"], [])

    def test_actual_coverage_avoids_review_without_reverse_or_suffix_confusion(self):
        self.candidates = {
            "DOMAIN,o33249.ingest.sentry.io": ["v2fly"],
            "DOMAIN-SUFFIX,intercom.io": ["v2fly"],
            "DOMAIN-SUFFIX,intercomcdn.com": ["v2fly"],
            "DOMAIN-SUFFIX,challenges.cloudflare.com": ["v2fly"],
            "DOMAIN,evilintercom.io": ["v2fly"],
        }
        active = ["DOMAIN,o33249.ingest.sentry.io", "DOMAIN-SUFFIX,intercom.io",
                  "DOMAIN-SUFFIX,intercomcdn.com", "DOMAIN,challenges.cloudflare.com"]
        result = self.evaluate(previous=[], active=active)
        self.assertEqual(result["counts"]["covered"], 3)
        self.assertEqual(len(result["new_candidates"]), 2)

    def test_community_ips_are_audit_only_and_unknown_syntax_stays_reviewable(self):
        self.candidates = {rule: ["acl4ssr"] for rule in (
            "IP-ASN,20473,no-resolve", "IP-CIDR,24.199.123.28/32,no-resolve",
            "IP-CIDR6,2001:4860::/48,no-resolve", "include:new-vendor", "DOMAIN")}
        result = self.evaluate(previous=[], active=["DOMAIN-SUFFIX,openai.com"])
        self.assertEqual(result["counts"]["official_ip_only"], 3)
        self.assertEqual({item["rule"] for item in result["new_candidates"]}, {"include:new-vendor", "DOMAIN"})
        self.assertIn("24.199.123.28", review.render_queue(result))

    def test_invalid_policy_cannot_silence_candidates(self):
        self.reject(at="2026-10-01")
        for invalid in ("bad JSON", json.dumps({**self.policy, "default_review_months": True}),
                        json.dumps({**self.policy, "rejected_rules": self.policy["rejected_rules"] * 2})):
            self.policy_path.write_text(invalid)
            result = self.evaluate()
            self.assertTrue(result["warnings"])
            self.assertEqual(len(result["new_candidates"]), 1)

    def test_future_review_date_and_bad_reminder_interval_are_rejected(self):
        self.reject(at="2026-10-16")
        with self.assertRaises(ValueError):
            review.validate_policy(self.policy, self.on)
        self.policy["rejected_rules"] = []
        for invalid in (0, -7, True, "7"):
            self.policy["reminder_interval_days"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                review.validate_policy(self.policy, self.on)

    def test_corrupt_delivery_state_requeues_and_warns(self):
        self.state_path.parent.mkdir(parents=True)
        self.state_path.write_text("{}")
        result = self.evaluate()
        self.assertTrue(result["warnings"])
        self.assertEqual(len(result["new_candidates"]), 1)
        self.ack(result)
        self.assertEqual(self.evaluate()["new_candidates"], [])

    def test_telegram_failure_never_acknowledges_and_success_does(self):
        self.reject()
        result = self.evaluate()
        report = {
            "changed_sources": [], "config_changed": False, "statistics": {
                key: 1 for key, _ in notify_telegram.COUNT_FIELDS},
            "auto_added": [], "auto_removed": [], "new_excluded_candidates": [],
            "review_due_candidates": result["due_candidates"],
        }
        report_path = self.root / "report.json"
        review.write_json(report_path, report)
        args = ["notify_telegram.py", "--report-file", str(report_path),
                "--review-state-file", str(self.state_path)]
        before = self.state_path.read_bytes()
        with patch.object(sys, "argv", args), patch.dict(os.environ, {
                "TELEGRAM_BOT_TOKEN": "test", "TELEGRAM_CHAT_ID": "test"}, clear=True), \
                patch.object(review, "today", return_value=self.on), \
                contextlib.redirect_stdout(io.StringIO()):
            with patch.object(notify_telegram, "send", side_effect=RuntimeError("failed")):
                self.assertEqual(notify_telegram.main(), 1)
            self.assertEqual(self.state_path.read_bytes(), before)
            with patch.object(notify_telegram, "send"):
                self.assertEqual(notify_telegram.main(), 0)
        self.assertIn(self.rule, json.loads(self.state_path.read_text())["sent"])
        self.assertEqual(self.evaluate()["due_candidates"], [])

    def test_missing_telegram_secrets_never_acknowledge_new_candidates(self):
        result = self.evaluate(previous=[])
        report = {"changed_sources": [], "config_changed": False,
                  "statistics": {key: 1 for key, _ in notify_telegram.COUNT_FIELDS},
                  "auto_added": [], "auto_removed": [],
                  "new_excluded_candidates": result["new_candidates"]}
        report_path = self.root / "report.json"
        review.write_json(report_path, report)
        before = self.state_path.read_bytes()
        with patch.object(sys, "argv", ["notify_telegram.py", "--report-file", str(report_path),
                                       "--review-state-file", str(self.state_path)]), \
                patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(notify_telegram.main(), 1)
        self.assertEqual(self.state_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
