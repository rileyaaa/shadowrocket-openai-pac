"""Offline tests for upstream guards and post-Actions Telegram reports."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build
import notify_telegram


class SyncReportTests(unittest.TestCase):
    def setUp(self):
        self.stats = {
            "voice_prefixes": 23, "automatic_openai_domains": 20,
            "johnshall_lines": 87212, "mapped_proxy_to_johnshall_node": 30239,
            "retained_ad_rules": 56886, "manual_openai_rules": 22,
        }
        self.baseline = {"statistics": self.stats}

    def test_minor_changes_are_allowed(self):
        stats = {**self.stats, "voice_prefixes": 22, "automatic_openai_domains": 19}
        build.validate_upstream_change(stats, self.baseline)
        build.validate_upstream_change(stats, None)

    def test_anomalous_removals_and_growth_stop_publication(self):
        for key, value in [
            ("voice_prefixes", 12), ("voice_prefixes", 100),
            ("automatic_openai_domains", 12), ("johnshall_lines", 50000),
            ("mapped_proxy_to_johnshall_node", 18000),
            ("retained_ad_rules", 30000),
        ]:
            with self.subTest(key=key, value=value):
                with self.assertRaisesRegex(ValueError, "UPSTREAM ANOMALY"):
                    build.validate_upstream_change({**self.stats, key: value}, self.baseline)

    def test_invalid_prior_statistics_stop_publication(self):
        with self.assertRaises(ValueError):
            build.validate_upstream_change(self.stats, {"statistics": {}})

    def test_report_compares_sources_deltas_and_added_removed_rules(self):
        before = {
            "statistics": self.stats, "settings": {"openai_node_name": "日本JP"},
            "sources": {"johnshall": {"sha256": "old"}, "voice": {"sha256": "same"}},
        }
        current = {
            "statistics": {**self.stats, "voice_prefixes": 24},
            "settings": {"openai_node_name": "日本JP-1"},
            "sources": {"johnshall": {"sha256": "new"}, "voice": {"sha256": "same"}},
        }
        report = build.make_sync_report(
            before, current, "DOMAIN,old.example\n", "DOMAIN,new.example\n", True
        )
        self.assertEqual(report["changed_sources"], ["johnshall"])
        self.assertEqual(report["stat_deltas"]["voice_prefixes"], 1)
        self.assertEqual(report["auto_added"], ["DOMAIN,new.example"])
        self.assertEqual(report["auto_removed"], ["DOMAIN,old.example"])
        self.assertTrue(report["settings_changed"])
        text = notify_telegram.format_report(
            report, "push", "example/repo", "https://example.test/run", when="2026-10-12"
        )
        self.assertIn("代码提交", text)
        self.assertIn("新增：DOMAIN,new.example", text)
        self.assertIn("https://example.test/run", text)

    def test_success_without_changes_still_reports(self):
        state = {"statistics": self.stats, "settings": {}, "sources": {}}
        report = build.make_sync_report(state, state, "DOMAIN,a.test", "DOMAIN,a.test", False)
        text = notify_telegram.format_report(report, "schedule", "", "", when="2026-10-12")
        self.assertIn("检查成功，无变化", text)
        self.assertIn("定时运行", text)

    def test_manual_review_file_change_is_reported_separately_from_routes(self):
        old = {"statistics": self.stats, "settings": {}, "sources": {},
               "review": {"excluded_auto_rules": [], "decisions_sha256": "a" * 64}}
        current = {**old, "review": {"excluded_auto_rules": [], "decisions_sha256": "b" * 64}}
        report = build.make_sync_report(old, current, "", "", False)
        self.assertTrue(report["review_decisions_changed"])
        text = notify_telegram.format_report(report, "workflow_dispatch", "", "")
        self.assertIn("人工审核记录文件已变更，分流配置无变化", text)
        self.assertNotIn("检查成功，无变化", text)
        self.assertFalse(build.make_sync_report(current, current, "", "", False)["review_decisions_changed"])
        initial = {**old, "review": {"excluded_auto_rules": []}}
        self.assertFalse(build.make_sync_report(initial, current, "", "", False)["review_decisions_changed"])

    def test_excluded_rules_are_deduplicated_and_have_provenance(self):
        sources = {
            "metacubex": ["DOMAIN-SUFFIX,chatgpt.com", "DOMAIN,brand-new.vendor.example"],
            "v2fly": ["DOMAIN,brand-new.vendor.example", "DOMAIN-SUFFIX,stripe.com"],
            "acl4ssr": ["DOMAIN-SUFFIX,stripe.com"],
        }
        excluded = build.excluded_auto_rule_sources(
            sources, ["DOMAIN-SUFFIX,chatgpt.com"]
        )
        self.assertEqual(excluded, {
            "DOMAIN,brand-new.vendor.example": ["metacubex", "v2fly"],
            "DOMAIN-SUFFIX,stripe.com": ["acl4ssr", "v2fly"],
        })
        self.assertNotIn("DOMAIN-SUFFIX,chatgpt.com", excluded)

    def test_initial_review_baseline_never_realerts_all_old_rules(self):
        before = {"statistics": self.stats, "sources": {}, "settings": {}}
        after = {**before, "review": {"excluded_auto_rules": [
            "DOMAIN-SUFFIX,stripe.com", "DOMAIN,old-service.example"
        ]}}
        report = build.make_sync_report(before, after, "", "", False)
        self.assertTrue(report["excluded_review_baseline_created"])
        self.assertEqual(report["excluded_review_total"], 2)
        self.assertEqual(report["new_excluded_candidates"], [])
        message = notify_telegram.format_report(
            report, "push", "", "", when="2026-10-12 14:00"
        )
        self.assertIn("基线已建立", message)
        self.assertIn("不计为新增", message)

    def test_future_new_rejected_candidate_is_reported_with_sources(self):
        before = {"statistics": self.stats, "sources": {}, "settings": {},
                  "review": {"excluded_auto_rules": [
                      "DOMAIN-SUFFIX,stripe.com", "DOMAIN,old-service.example"
                  ]}}
        after = {**before, "review": {"excluded_auto_rules": [
            "DOMAIN-SUFFIX,stripe.com", "DOMAIN,new-service.example"
        ]}}
        report = build.make_sync_report(
            before, after, "", "", False,
            excluded_sources={"DOMAIN,new-service.example": ["metacubex", "v2fly"]},
        )
        self.assertFalse(report["excluded_review_baseline_created"])
        self.assertEqual(report["new_excluded_candidates"], [
            {"rule": "DOMAIN,new-service.example", "sources": ["metacubex", "v2fly"]}
        ])
        message = notify_telegram.format_report(
            report, "schedule", "", "", when="2026-10-13 11:30"
        )
        self.assertIn("DOMAIN,new-service.example", message)
        self.assertIn("MetaCubeX", message)
        self.assertIn("v2fly", message)
        self.assertIn("未自动分流", message)
        self.assertNotIn("old-service.example", message)

    def test_review_existing_exclusions_does_not_spam(self):
        state = {"statistics": self.stats, "sources": {}, "settings": {},
                 "review": {"excluded_auto_rules": ["DOMAIN-SUFFIX,stripe.com"]}}
        report = build.make_sync_report(state, state, "", "", False)
        self.assertFalse(report["excluded_review_baseline_created"])
        self.assertFalse(report["new_excluded_candidates"])
        message = notify_telegram.format_report(
            report, "schedule", "", "", when="2026-10-13 11:30"
        )
        self.assertIn("上游新增待审核规则：无", message)

    def test_upstream_download_one_retry_then_success(self):
        class GoodResponse:
            status = 200
            headers = {}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, size):
                return b"valid source content"
        import urllib.error
        with patch(
            "build.urllib.request.urlopen",
            side_effect=[urllib.error.URLError("temporary outage"), GoodResponse()],
        ) as urlopen, patch("build.time.sleep") as sleep:
            self.assertEqual(build.fetch("https://upstream.example/source", minimum=5), b"valid source content")
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_upstream_download_second_failure_is_fatal(self):
        import urllib.error
        with patch(
            "build.urllib.request.urlopen",
            side_effect=urllib.error.URLError("unavailable"),
        ) as urlopen, patch("build.time.sleep") as sleep:
            with self.assertRaises(urllib.error.URLError):
                build.fetch("https://upstream.example/source", minimum=5)
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_upstream_truncated_response_also_retries_once(self):
        class TooShort:
            status = 200
            headers = {}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, size):
                return b"x"
        with patch("build.urllib.request.urlopen", return_value=TooShort()) as urlopen, patch("build.time.sleep") as sleep:
            with self.assertRaisesRegex(ValueError, "Truncated or oversized"):
                build.fetch("https://upstream.example/source", minimum=5)
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_telegram_is_post_payload_with_chat_id(self):
        class Fake:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return b'{"ok": true}'
        with patch("notify_telegram.urllib.request.urlopen", return_value=Fake()) as urlopen:
            notify_telegram.send("example-test-token", "1234", "Hello")
        req = urlopen.call_args.args[0]
        self.assertEqual(json.loads(req.data)["chat_id"], "1234")


if __name__ == "__main__":
    unittest.main()
