"""Regression tests for the four 2026-10-15 audit findings, without network I/O."""
import contextlib
import copy
from datetime import date
import hashlib
import http.client
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build
import notify_telegram
import review_queue


def http_response(body, headers):
    class Socket:
        def makefile(self, *args, **kwargs):
            return io.BytesIO(b"HTTP/1.1 200 OK\r\n" + headers + b"\r\n" + body)
    response = http.client.HTTPResponse(Socket())
    response.begin()
    return response


class DownloadCompletenessTests(unittest.TestCase):
    def test_short_content_length_retries_and_fails(self):
        # This is a real HTTPResponse: read(amt) alone does NOT raise here.
        with patch("build.urllib.request.urlopen", side_effect=lambda *a, **kw:
                   http_response(b"x" * 100, b"Content-Length: 1000\r\n")) as download, \
                patch("build.time.sleep"):
            with self.assertRaisesRegex(ValueError, "Truncated response"):
                build.fetch("https://upstream.example/file", minimum=50)
        self.assertEqual(download.call_count, 2)

    def test_valid_length_and_complete_chunked_response(self):
        for body, headers in (
            (b"x" * 100, b"Content-Length: 100\r\n"),
            (b"64\r\n" + b"x" * 100 + b"\r\n0\r\n\r\n", b"Transfer-Encoding: chunked\r\n"),
            (b"x" * 100, b""),
        ):
            with self.subTest(headers=headers), patch("build.urllib.request.urlopen",
                    return_value=http_response(body, headers)):
                self.assertEqual(build.fetch("https://upstream.example/file"), b"x" * 100)

    def test_truncated_chunked_response_retries_and_fails(self):
        with patch("build.urllib.request.urlopen", side_effect=lambda *a, **kw:
                   http_response(b"64\r\n" + b"x" * 80, b"Transfer-Encoding: chunked\r\n")) as download, \
                patch("build.time.sleep"):
            with self.assertRaises(http.client.IncompleteRead):
                build.fetch("https://upstream.example/file")
        self.assertEqual(download.call_count, 2)


class PipelineHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.apple_url = build.RULESET_SOURCES["apple_news"][0]
        cls.base = (
            "# offline Johnshall fixture\n[General]\nipv6 = false\n[Rule]\n"
            + "".join(f"DOMAIN,proxy{i}.example,Proxy\n" for i in range(10001))
            + "".join(f"DOMAIN,ad{i}.example,Reject\n" for i in range(20001))
            + "# preserve source ordering and comments\n" * 22000
            + "DOMAIN,before.example,Proxy\n"
            + f"RULE-SET,{cls.apple_url},Proxy\n"
            + "DOMAIN,after.example,Proxy\nFINAL,direct\n"
            + "[URL Rewrite]\n^http://example.com https://example.com 302\n"
            + "[MITM]\nhostname = example.com\n" + build.JOHNSHALL_FOOTER + "\n"
        ).encode()
        cls.manual = (build.ROOT / "config/manual-openai.rules").read_bytes()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        (self.root / "config/manual-openai.rules").write_bytes(self.manual)
        review_queue.write_json(self.root / "config/review-decisions.json", review_queue.default_policy())
        self.voice = {"prefixes": [{"ipv4Prefix": f"8.8.4.{i}/32"} for i in range(1, 6)]}
        domains = ["openai.com", "chatgpt.com", "oaistatic.com", "oaiusercontent.com",
                   "oaistatsig.com", "sora.com", "crixet.com", "chat.com",
                   "chatgpt.site", "openai.fm"]
        self.sources = {
            build.BASE_URL: self.base,
            build.VOICE_URL: json.dumps(self.voice).encode(),
            self.apple_url: b"# NAME: AppleNews\n# TOTAL: 2\nDOMAIN,gspe1-ssl.ls.apple.com\nDOMAIN,news-client-search.apple.com\n",
        }
        for name, (url, fmt) in build.DOMAIN_SOURCES.items():
            prefix = {"meta": "+.", "typed": "DOMAIN-SUFFIX,", "v2fly": ""}[fmt]
            self.sources[url] = "\n".join(prefix + domain for domain in domains).encode()
        for patcher in (
            patch.object(build, "ROOT", self.root),
            patch.object(build, "CONFIG", self.root / "Shadowrocket_Johnshall_OpenAI.conf"),
            patch.object(build, "load_settings", return_value={
                "openai_node_name": "OpenAI Test", "johnshall_proxy_node_name": "General Test"}),
            patch.object(build, "fetch", side_effect=lambda url, *a, **kw: self.sources[url]),
            patch.object(sys, "argv", ["build.py", "--report-file", str(self.root / "report.json")]),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_build(self):
        with contextlib.redirect_stdout(io.StringIO()):
            build.run()

    def published_files(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def test_voice_same_count_expansion_preserves_published_files(self):
        self.run_build()
        before = self.published_files()
        for cidr in ("8.0.0.0/8", "8.8.4.0/24", "8.8.4.1/24"):
            voice = copy.deepcopy(self.voice)
            voice["prefixes"][0]["ipv4Prefix"] = cidr
            self.sources[build.VOICE_URL] = json.dumps(voice).encode()
            with self.subTest(cidr=cidr), self.assertRaises(ValueError):
                self.run_build()
            self.assertEqual(self.published_files(), before)

    def test_voice_new_family_and_missing_baseline_require_review(self):
        self.run_build()
        before = self.published_files()
        voice = copy.deepcopy(self.voice)
        voice["prefixes"].append({"ipv6Prefix": "2001:4860:4860::8888/128"})
        self.sources[build.VOICE_URL] = json.dumps(voice).encode()
        with self.assertRaisesRegex(ValueError, "VOICE COVERAGE ANOMALY"):
            self.run_build()
        self.assertEqual(self.published_files(), before)
        self.sources[build.VOICE_URL] = json.dumps(self.voice).encode()
        (self.root / "rules/openai-auto.list").unlink()
        with self.assertRaisesRegex(ValueError, "baseline is missing"):
            self.run_build()

    def test_voice_rotation_is_allowed_and_overlaps_count_once(self):
        self.run_build()
        voice = copy.deepcopy(self.voice)
        voice["prefixes"][0]["ipv4Prefix"] = "8.8.8.8/32"
        self.sources[build.VOICE_URL] = json.dumps(voice).encode()
        self.run_build()
        state = json.loads((self.root / "data/sources.json").read_text())
        self.assertEqual(state["statistics"]["voice_ipv4_addresses"], 5)
        self.assertEqual(build.voice_address_counts([
            "IP-CIDR,8.8.4.0/24", "IP-CIDR,8.8.4.1/32",
            "IP-CIDR6,2001:4860:4860::8888/128",
        ]), {"voice_ipv4_addresses": 256, "voice_ipv6_addresses": 1})

    def test_voice_rejects_wrong_family_and_broad_ipv6(self):
        for entry in ({"ipv4Prefix": "2001:4860:4860::8888/128"},
                      {"ipv6Prefix": "8.8.8.8/32"}, {"ipv6Prefix": "2001:4860::/32"}):
            voice = copy.deepcopy(self.voice)
            voice["prefixes"].append(entry)
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                build.parse_voice(json.dumps(voice).encode())

    def test_unparsed_rules_reach_report_with_source_but_never_config(self):
        self.run_build()
        v2fly_url = build.DOMAIN_SOURCES["v2fly"][0]
        candidates = [r"regexp:^new-openai-\d+\.vendor\.example$", "include:new-vendor", "keyword:openai"]
        self.sources[v2fly_url] += ("\n" + "\n".join(candidates) + "\ndomain:chatgpt.com\n").encode()
        typed_url = build.DOMAIN_SOURCES["acl4ssr"][0]
        self.sources[typed_url] += b"\nIP-ASN,20473,no-resolve\n"
        self.run_build()
        report = json.loads((self.root / "report.json").read_text())
        actual = {item["rule"]: item["sources"] for item in report["new_excluded_candidates"]}
        self.assertEqual(actual, {rule: ["v2fly"] for rule in candidates})
        self.assertEqual(report["manual_review_counts"]["official_ip_only"], 1)
        self.assertIn("IP-ASN,20473,no-resolve", (self.root / "data/review-queue.md").read_text())
        output = build.CONFIG.read_text()
        message = notify_telegram.format_report(report, "push", "test/repo", "")
        for rule in candidates:
            self.assertIn(rule, message)
            self.assertNotIn(rule, output)
        self.assertIn("DOMAIN-SUFFIX,chatgpt.com,OpenAI Test", output)
        review_queue.acknowledge(report, self.root / "data/review-notifications.json")
        self.run_build()
        self.assertEqual(json.loads((self.root / "report.json").read_text())["new_excluded_candidates"], [])

    def test_bad_review_config_warns_without_freezing_route_updates(self):
        self.run_build()
        (self.root / "config/review-decisions.json").write_text("invalid JSON")
        self.sources[self.apple_url] = self.sources[self.apple_url].replace(b"news-client-search", b"news-new-search")
        self.run_build()
        report = json.loads((self.root / "report.json").read_text())
        self.assertTrue(report["config_changed"])
        self.assertTrue(report["review_warnings"])
        self.assertIn("DOMAIN,news-new-search.apple.com,General Test", build.CONFIG.read_text())

    def test_missing_review_config_warns_without_interrupting_sync(self):
        self.run_build()
        before = build.CONFIG.read_bytes()
        (self.root / "config/review-decisions.json").unlink()
        self.run_build()
        report = json.loads((self.root / "report.json").read_text())
        self.assertTrue(report["review_warnings"])
        self.assertTrue(report["review_decisions_changed"])
        self.assertFalse(report["config_changed"])
        self.assertEqual(build.CONFIG.read_bytes(), before)

    def test_manual_rejection_changes_report_but_not_routing(self):
        self.run_build()
        before_config = build.CONFIG.read_bytes()
        before_auto = (self.root / "rules/openai-auto.list").read_bytes()
        source = build.DOMAIN_SOURCES["acl4ssr"][0]
        candidate = "DOMAIN-SUFFIX,auth0.com"
        self.sources[source] += ("\n" + candidate + "\n").encode()
        self.run_build()  # Refresh the published review candidates.
        review_queue.record_rejection(self.root / "config/review-decisions.json",
                                      candidate, "社区共享域名，暂不放行", on=date(2026, 10, 15))
        with patch.object(review_queue, "today", return_value=date(2026, 10, 15)):
            self.run_build()
        report = json.loads((self.root / "report.json").read_text())
        self.assertTrue(report["review_decisions_changed"])
        self.assertFalse(report["config_changed"])
        self.assertEqual(build.CONFIG.read_bytes(), before_config)
        self.assertEqual((self.root / "rules/openai-auto.list").read_bytes(), before_auto)
        text = notify_telegram.format_report(report, "workflow_dispatch", "test/repo", "")
        self.assertIn("人工审核记录文件已变更，分流配置无变化", text)
        self.run_build()
        repeated = json.loads((self.root / "report.json").read_text())
        self.assertFalse(repeated["review_decisions_changed"])

    def test_expiring_rejection_reaches_report_without_changing_routes(self):
        self.run_build()
        before = build.CONFIG.read_bytes()
        candidate = "DOMAIN,unverified.vendor.example"
        typed_url = build.DOMAIN_SOURCES["acl4ssr"][0]
        self.sources[typed_url] += ("\n" + candidate + "\n").encode()
        # Publish the candidate to the review queue before recording a rejection.
        self.run_build()
        review_queue.record_rejection(self.root / "config/review-decisions.json", candidate,
                                      "暂缺依据", on=date(2026, 1, 31))
        with patch.object(review_queue, "today", return_value=date(2026, 7, 30)):
            self.run_build()
        early = json.loads((self.root / "report.json").read_text())
        self.assertEqual(early["review_due_candidates"], [])
        self.assertEqual(early["new_excluded_candidates"], [])
        with patch.object(review_queue, "today", return_value=date(2026, 7, 31)):
            self.run_build()
        due = json.loads((self.root / "report.json").read_text())
        self.assertEqual(due["review_due_candidates"][0]["rule"], candidate)
        message = notify_telegram.format_report(due, "schedule", "test/repo", "")
        self.assertIn("到期复审", message)
        self.assertIn(candidate, message)
        self.assertEqual(build.CONFIG.read_bytes(), before)

    def test_missing_footer_or_mitm_preserves_published_files(self):
        self.run_build()
        before = self.published_files()
        for corrupted in (
            self.base.split(b"[MITM]", 1)[0] + b"[MITM]\n",
            self.base.replace(b"hostname = example.com\n", b""),
        ):
            self.sources[build.BASE_URL] = corrupted
            with self.assertRaises(ValueError):
                self.run_build()
            self.assertEqual(self.published_files(), before)

    def test_external_ruleset_is_inlined_at_same_position_and_hashed(self):
        self.run_build()
        output = build.CONFIG.read_text()
        self.assertNotIn("\nRULE-SET,", output)
        first = output.index("DOMAIN,before.example,General Test")
        middle = output.index("DOMAIN,gspe1-ssl.ls.apple.com,General Test")
        last = output.index("DOMAIN,after.example,General Test")
        self.assertLess(first, middle)
        self.assertLess(middle, last)
        state = json.loads((self.root / "data/sources.json").read_text())
        source = state["sources"]["apple_news"]
        self.assertEqual(source["rule_count"], 2)
        self.assertEqual(source["sha256"], hashlib.sha256(self.sources[self.apple_url]).hexdigest())
        self.assertEqual((self.root / "rules/johnshall-apple-news.list").read_bytes(), self.sources[self.apple_url])
        self.sources[self.apple_url] = self.sources[self.apple_url].replace(b"news-client-search", b"news-new-search")
        self.run_build()
        report = json.loads((self.root / "report.json").read_text())
        self.assertEqual(report["changed_sources"], ["apple_news"])
        self.assertTrue(report["config_changed"])

    def test_external_ruleset_bad_data_and_new_dependencies_block_publication(self):
        self.run_build()
        before = self.published_files()
        original = self.sources[self.apple_url]
        for invalid in (
            b"# TOTAL: 2\nDOMAIN,example.com\n",  # truncated source
            b"# TOTAL: 1\nDOMAIN,example.com\n",  # unexpected 50% shrink
            b"# TOTAL: 2\nDOMAIN,example.com,DIRECT\nDOMAIN,other.example\n",
            b"# TOTAL: 2\nRULE-SET,https://unreviewed.example/list,Proxy\nDOMAIN,other.example\n",
        ):
            self.sources[self.apple_url] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.run_build()
            self.assertEqual(self.published_files(), before)
        self.sources[self.apple_url] = original
        self.sources[build.BASE_URL] = self.base.replace(self.apple_url.encode(), b"https://unreviewed.example/list")
        with self.assertRaisesRegex(ValueError, "Unreviewed or unavailable"):
            self.run_build()
        self.assertEqual(self.published_files(), before)


if __name__ == "__main__":
    unittest.main()
