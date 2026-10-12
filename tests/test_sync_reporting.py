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
