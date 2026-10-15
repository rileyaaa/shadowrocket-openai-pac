"""Adversarial decisions and end-to-end publishing tests, with no network I/O."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build
import notify_telegram
import review_rules as review
import test_hardening as hardening

FIXTURE = (Path(__file__).parent / "fixtures/official-network.html").read_bytes()


class OfficialEvidenceTests(unittest.TestCase):
    def test_only_named_allowlist_supplies_evidence(self):
        extra = b'<ul><li>unrelated.vendor.example</li></ul>'
        scripts = b'<script>"<h2>OpenAI/ChatGPT domains to allowlist</h2><ul><li>evil.example</li></ul>"</script>'
        raw = FIXTURE.replace(b"<h1>", extra + scripts + b"<h1>").replace(
            b"</body>", extra + b'<a href="https://lookalike.openai.com.evil.example">support</a></body>')
        rules = review.parse_official_network(raw)
        self.assertEqual(len(rules), 31)
        self.assertNotIn("DOMAIN,unrelated.vendor.example", rules)
        self.assertNotIn("DOMAIN,evil.example", rules)

    def test_incomplete_ambiguous_or_wrong_article_blocks(self):
        for raw in (
            FIXTURE.replace(review.ARTICLE_TITLE.encode(), b"Different article"),
            FIXTURE.replace(review.ALLOWLIST_HEADING.encode(), b"Other links"),
            FIXTURE.replace(b"</html>", b""),
            FIXTURE.replace(b"</ul>", b""),
            FIXTURE.replace(b"</ul>", b"</ul><ul><li>evil.example</li></ul>"),
            FIXTURE.replace(b"</body>", ("<h2>" + review.ALLOWLIST_HEADING + "</h2></body>").encode()),
            FIXTURE.replace(b"*.chatgpt.com", b"*.com"),
            FIXTURE.replace(b"js.stripe.com", b"https://js.stripe.com/path"),
            FIXTURE.replace(b"js.stripe.com", b"js.stripe.com,PROXY"),
            FIXTURE.replace(b"<p>js.stripe.com</p>", b"<p>one.example</p><p>two.example</p>"),
            FIXTURE.replace(b"*.openai.com", b"*.openai.com.evil.example"),
        ):
            with self.subTest(raw=raw[-80:]), self.assertRaises(ValueError):
                review.parse_official_network(raw)

    def test_large_replacement_at_same_count_cannot_bypass_guard(self):
        rules = review.parse_official_network(FIXTURE)
        old = {"sources": {"official_network": {"rule_count": len(rules), "sha256": review.rules_hash(rules)}}}
        altered = rules.copy()
        for index in range(10):
            altered[index] = f"DOMAIN,new{index}.vendor.example"
        with self.assertRaisesRegex(ValueError, "churn"):
            review.validate_official_change(altered, old, rules)
        review.validate_official_change(rules + ["DOMAIN,new.vendor.example"], old, rules)
        with self.assertRaisesRegex(ValueError, "baseline"):
            review.validate_official_change(rules, old, None)

    def test_official_redirect_cannot_supply_foreign_evidence(self):
        class Response:
            status = 200
            headers = {}
            def geturl(self):
                return "https://help.openai.com.attacker.example/article"
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
        with patch("build.urllib.request.urlopen", return_value=Response()) as fetch, patch("build.time.sleep"):
            with self.assertRaisesRegex(ValueError, "pinned source"):
                build.fetch(review.NETWORK_URL)
        self.assertEqual(fetch.call_count, 2)


class DecisionTests(unittest.TestCase):
    def decide(self, rule, official=(), voice=(), legacy=(), manual=()):
        return review.review_one(rule, list(official), list(voice), list(legacy), list(manual))

    def test_official_exact_host_approved_but_scope_cannot_expand(self):
        exact = "DOMAIN,customer.vendor.example"
        self.assertEqual(self.decide(exact, [exact])["status"], "approved")
        for wider in ("DOMAIN-SUFFIX,customer.vendor.example", "DOMAIN-SUFFIX,vendor.example"):
            self.assertEqual(self.decide(wider, [exact])["status"], "rejected")
        self.assertEqual(self.decide("DOMAIN,sub.customer.vendor.example", [exact])["status"], "pending")

    def test_official_wildcard_covers_only_domain_boundary(self):
        proof = ["DOMAIN-SUFFIX,tenant.vendor.example"]
        for rule in (proof[0], "DOMAIN,media.tenant.vendor.example"):
            self.assertTrue(self.decide(rule, proof)["permit_auto"])
        for rule in ("DOMAIN,eviltenant.vendor.example", "DOMAIN,tenant.vendor.example.evil.test"):
            self.assertFalse(self.decide(rule, proof)["permit_auto"])

    def test_new_whole_domain_and_cloud_platform_wildcards_do_not_auto_pass(self):
        for rule, status in (("DOMAIN-SUFFIX,newvendor.com", "pending"),
                             ("DOMAIN-SUFFIX,blob.core.windows.net", "rejected"),
                             ("DOMAIN-SUFFIX,vercel.app", "rejected")):
            verdict = self.decide(rule, [rule])
            self.assertEqual(verdict["status"], status)
            self.assertFalse(verdict["permit_auto"])
            child = "DOMAIN,unrelated." + rule.split(",")[1]
            self.assertFalse(self.decide(child, [rule])["permit_auto"])
            self.assertTrue(self.decide(child, [rule, child])["permit_auto"])

    def test_three_existing_manual_rules_are_covered_without_widening(self):
        manual = ["DOMAIN,o33249.ingest.sentry.io", "DOMAIN-SUFFIX,intercom.io", "DOMAIN-SUFFIX,intercomcdn.com"]
        for rule in manual:
            self.assertEqual(self.decide(rule, manual=manual)["status"], "covered")
            self.assertFalse(self.decide(rule, manual=manual)["permit_auto"])
            self.assertTrue(self.decide(rule, official=manual, manual=manual)["permit_auto"])
        self.assertEqual(self.decide("DOMAIN-SUFFIX,challenges.cloudflare.com",
                                    manual=["DOMAIN,challenges.cloudflare.com"])["status"], "rejected")

    def test_ip_needs_official_destination_containment(self):
        official = ["IP-CIDR,8.8.4.8/32", "IP-CIDR,8.8.4.9/32"]
        for cidr in ("8.8.4.8/32", "8.8.4.8/31"):
            verdict = self.decide(f"IP-CIDR,{cidr},no-resolve", voice=official)
            self.assertEqual(verdict["status"], "covered")
            self.assertFalse(verdict["permit_auto"])  # emit official prefixes, never community IP copies
        for cidr in ("24.199.123.28/32", "64.23.132.171/32"):
            self.assertEqual(self.decide(f"IP-CIDR,{cidr},no-resolve", voice=official)["status"], "pending")
        for cidr in ("8.8.4.0/24", "8.0.0.0/8", "127.0.0.1/32", "0.0.0.0/0"):
            self.assertEqual(self.decide(f"IP-CIDR,{cidr}", voice=official)["status"], "rejected")
        self.assertEqual(self.decide("IP-CIDR6,8.8.4.8/32", voice=official)["status"], "pending")

    def test_asn_keyword_ports_and_uninterpreted_rules_never_pass(self):
        for rule in ("IP-ASN,20473,no-resolve", "DOMAIN-KEYWORD,openai", "keyword:openai",
                     "DST-PORT,3478", "AND,((PROTOCOL,UDP),(DST-PORT,3478))"):
            self.assertEqual(self.decide(rule)["status"], "rejected")
        for rule in (r"regexp:^.*openai.*$", "include:other", "DOMAIN,new.vendor.example,DIRECT",
                     "IP-CIDR,8.8.4.8/32,PROXY", "DOMAIN-WILDCARD,*.vendor.example"):
            self.assertFalse(self.decide(rule)["permit_auto"])

    def test_community_agreement_and_forged_prior_approval_are_not_proof(self):
        rule = "DOMAIN,new.vendor.example"
        sources = {name: [rule] for name in ("metacubex", "v2fly", "acl4ssr", "blackmatrix7")}
        allowed, audit = review.review_candidates(sources, {}, [], [], [], [], now="day1")
        self.assertEqual(allowed, [])
        self.assertEqual(audit["candidates"][0]["status"], "pending")
        audit["candidates"][0].update(status="approved", permit_auto=True, evidence_rules=[rule])
        allowed, second = review.review_candidates(sources, {}, [], [], [], [], audit, now="day2")
        self.assertEqual(allowed, [])
        self.assertEqual(second["candidates"][0]["status"], "pending")

    def test_all_old_pending_candidates_are_rechecked_and_can_be_approved(self):
        rule = "DOMAIN,new.vendor.example"
        _, first = review.review_candidates({"v2fly": [rule]}, {}, [], [], [], [], now="day1")
        allowed, second = review.review_candidates({}, {}, [rule], [], [], [], first, now="day2")
        self.assertEqual(allowed, [rule])
        self.assertEqual(second["candidates"][0]["status"], "approved")
        self.assertEqual(second["candidates"][0]["first_seen"], "day1")
        self.assertEqual(second["candidates"][0]["decision_changed_at"], "day2")
        _, third = review.review_candidates({}, {}, [rule], [], [], [], second, now="day3")
        self.assertEqual(third["changes"], [])
        self.assertEqual(third["candidates"][0]["decision_changed_at"], "day2")

    def test_removed_official_evidence_revokes_auto_authorization(self):
        rule = "DOMAIN,new.vendor.example"
        _, first = review.review_candidates({"v2fly": [rule]}, {}, [rule], [], [], [])
        allowed, second = review.review_candidates({"v2fly": [rule]}, {}, [], [], [], [], first)
        self.assertEqual(allowed, [])
        self.assertEqual(second["candidates"][0]["status"], "pending")
        with self.assertRaisesRegex(ValueError, "Unauthorised"):
            review.validate_emitted([], [rule], [], [], [])


class AutomaticReviewPipelineTests(unittest.TestCase):
    # Share fixture setup/helpers without re-running the inherited test methods.
    setUpClass = classmethod(hardening.PipelineHardeningTests.setUpClass.__func__)
    setUp = hardening.PipelineHardeningTests.setUp
    run_build = hardening.PipelineHardeningTests.run_build
    published_files = hardening.PipelineHardeningTests.published_files

    def append_official(self, host):
        self.sources[review.NETWORK_URL] = self.sources[review.NETWORK_URL].replace(
            b"</ul>", f"<li>{host}</li></ul>".encode())

    def read_audit(self):
        return json.loads((self.root / "data/openai-review.json").read_text())

    def test_pending_then_approved_then_evidence_removed_in_real_build(self):
        rule = "DOMAIN,new.vendor.example"
        url = build.DOMAIN_SOURCES["acl4ssr"][0]
        self.sources[url] += ("\n" + rule).encode()
        self.run_build()
        self.assertNotIn(rule, build.CONFIG.read_text())
        self.append_official("new.vendor.example")
        self.run_build()
        self.assertIn(rule + ",OpenAI Test,force-remote-dns", build.CONFIG.read_text())
        self.assertIn(rule, (self.root / "rules/openai-auto.list").read_text())
        row = next(row for row in self.read_audit()["candidates"] if row["rule"] == rule)
        self.assertEqual(row["status"], "approved")
        self.assertTrue(row["automatic_coverage"])
        report = json.loads((self.root / "report.json").read_text())
        self.assertIn(rule, report["auto_added"])
        self.sources[review.NETWORK_URL] = FIXTURE
        self.run_build()
        self.assertNotIn(rule, build.CONFIG.read_text())
        self.assertIn(rule, json.loads((self.root / "report.json").read_text())["auto_removed"])

    def test_existing_manual_layer_survives_loss_of_dynamic_evidence(self):
        rule = "DOMAIN,js.stripe.com"
        self.run_build()
        original_manual = (self.root / "config/manual-openai.rules").read_bytes()
        self.assertIn(rule, (self.root / "rules/openai-auto.list").read_text())
        self.sources[review.NETWORK_URL] = FIXTURE.replace(b"<li><p>js.stripe.com</p></li>", b"")
        self.run_build()
        self.assertNotIn(rule, (self.root / "rules/openai-auto.list").read_text())
        self.assertIn(rule + ",OpenAI Test", build.CONFIG.read_text())
        self.assertEqual((self.root / "config/manual-openai.rules").read_bytes(), original_manual)

    def test_bad_or_unavailable_evidence_changes_no_published_file(self):
        self.run_build()
        before = self.published_files()
        for bad in (b"<html>temporary sign-in wall</html>", FIXTURE[:-20]):
            self.sources[review.NETWORK_URL] = bad
            with self.assertRaises(ValueError):
                self.run_build()
            self.assertEqual(self.published_files(), before)
        with patch.object(build, "fetch", side_effect=OSError("network unavailable")):
            with self.assertRaises(OSError):
                self.run_build()
        self.assertEqual(self.published_files(), before)

    def test_every_final_openai_rule_has_an_inventory_record_and_no_unknown_ips(self):
        url = build.DOMAIN_SOURCES["acl4ssr"][0]
        self.sources[url] += b"\nIP-CIDR,24.199.123.28/32,no-resolve\nIP-CIDR,64.23.132.171/32,no-resolve\nIP-ASN,20473,no-resolve\n"
        self.run_build()
        audit = self.read_audit()
        auto = build.active_auto_rules((self.root / "rules/openai-auto.list").read_text())
        expected = {row.removesuffix(",no-resolve") for row in auto}
        actual = {row["rule"] for row in audit["inventory"] if row["layer"] != "manual_fallback"}
        self.assertEqual(actual, expected)
        self.assertEqual(sum(row["layer"] == "manual_fallback" for row in audit["inventory"]), 43)
        output = build.CONFIG.read_text()
        for value in ("24.199.123.28", "64.23.132.171", "IP-ASN,20473"):
            self.assertNotIn(value, output)
        report = json.loads((self.root / "report.json").read_text())
        message = notify_telegram.format_report(report, "push", "test/repo", "https://example.test/run")
        self.assertIn("待证据", message)
        self.assertIn("拒绝 IP-ASN,20473", message)
        self.assertIn("实际发布", message)
        self.assertIn("IP-CIDR,64.23.132.171/32", notify_telegram.review_summary(report))

    def test_equivalent_page_markup_does_not_create_fake_source_changes(self):
        self.run_build()
        before = self.read_audit()
        self.sources[review.NETWORK_URL] = FIXTURE.replace(b"</body>", b"<script>new style version</script></body>")
        self.run_build()
        report = json.loads((self.root / "report.json").read_text())
        self.assertEqual(report["changed_sources"], [])
        self.assertEqual(report["automatic_review"]["changes"], [])
        self.assertEqual(self.read_audit(), before)


if __name__ == "__main__":
    unittest.main()
