import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build


class BuildTest(unittest.TestCase):
    def test_domains(self):
        data = "+.chatgpt.com\nopenai.com\n" + "\n".join(
            f"host{i}.example.org" for i in range(9)
        )
        self.assertIn("DOMAIN-SUFFIX,chatgpt.com",
                      build.parse_domain_list(data, "meta"))
        typed = "IP-ASN,20473\nDOMAIN-KEYWORD,openai\n" + "\n".join(
            f"DOMAIN-SUFFIX,site{i}.example.org" for i in range(9)
        )
        self.assertFalse(any("IP-ASN" in rule for rule in
                             build.parse_domain_list(typed, "typed")))

    def test_automatic_openai_filter_does_not_override_other_websites(self):
        raw = [
            "DOMAIN-SUFFIX,openai.com",
            "DOMAIN-SUFFIX,chatgpt.com",
            "DOMAIN-SUFFIX,oaistatic.com",
            "DOMAIN-SUFFIX,oaiusercontent.com",
            "DOMAIN-SUFFIX,oaistatsig.com",
            "DOMAIN-SUFFIX,sora.com",
            "DOMAIN-SUFFIX,chat.com",
            "DOMAIN-SUFFIX,crixet.com",
            "DOMAIN-SUFFIX,chatgpt.site",
            "DOMAIN-SUFFIX,chatgpt.livekit.cloud",
            "DOMAIN,openaiassets.blob.core.windows.net",
            "DOMAIN,openaiapi-site.azureedge.net",
            "DOMAIN-SUFFIX,auth0.com",
            "DOMAIN-SUFFIX,stripe.com",
            "DOMAIN-SUFFIX,intercom.io",
            "DOMAIN-SUFFIX,sentry.io",
            "DOMAIN-SUFFIX,statsig.com",
            "DOMAIN-SUFFIX,host.livekit.cloud",
            "DOMAIN-KEYWORD,openai",
            "DOMAIN,static.cloudflareinsights.com",
            "DOMAIN-SUFFIX,algolia.net",
        ]
        result = build.filter_auto_domains(raw)
        self.assertIn("DOMAIN-SUFFIX,chatgpt.com", result)
        self.assertIn("DOMAIN,openaiassets.blob.core.windows.net", result)
        for shared in (
            "DOMAIN-SUFFIX,auth0.com", "DOMAIN-SUFFIX,stripe.com",
            "DOMAIN-SUFFIX,intercom.io", "DOMAIN-SUFFIX,sentry.io",
            "DOMAIN-SUFFIX,statsig.com", "DOMAIN-SUFFIX,host.livekit.cloud",
            "DOMAIN-KEYWORD,openai", "DOMAIN,static.cloudflareinsights.com",
            "DOMAIN-SUFFIX,algolia.net",
        ):
            with self.subTest(shared=shared):
                self.assertNotIn(shared, result)

    def test_verified_openai_showcase_domains_are_precise(self):
        manual = build.parse_manual(build.ROOT / "config/manual-openai.rules")
        for rule in (
            "DOMAIN-SUFFIX,openai.fm",
            "DOMAIN,chatkit.world",
            "DOMAIN,openai-photobooth-demo.vercel.app",
            "DOMAIN,openai-realtime-solar-system-demo.vercel.app",
        ):
            with self.subTest(rule=rule):
                self.assertIn(rule, manual)
                self.assertTrue(build.is_openai_specific_rule(rule))
        self.assertTrue(build.domain_rule_covers(
            "DOMAIN-SUFFIX,openai.fm", "DOMAIN,www.openai.fm"
        ))
        for unrelated in (
            "DOMAIN-SUFFIX,vercel.app",
            "DOMAIN,unrelated-project.vercel.app",
            "DOMAIN-SUFFIX,chatkit.world",
        ):
            with self.subTest(unrelated=unrelated):
                self.assertFalse(build.is_openai_specific_rule(unrelated))

    def test_current_official_openai_first_party_hosts(self):
        # First-party / dedicated hostnames from OpenAI's network guidance
        # and Codex cloud agent documentation as checked 2026-10-12.
        auto = build.filter_auto_domains([
            f"DOMAIN-SUFFIX,{root}" for root in
            ("openai.com", "chatgpt.com", "chatgpt.site", "oaistatic.com",
             "oaiusercontent.com", "oaistatsig.com", "sora.com", "chat.com",
             "crixet.com", "chatgpt.livekit.cloud")
        ] + ["DOMAIN,openaiassets.blob.core.windows.net",
             "DOMAIN,openaiapi-site.azureedge.net"])
        rules = auto + build.parse_manual(build.ROOT / "config/manual-openai.rules")

        def covers(host):
            return any(
                (kind == "DOMAIN" and host == suffix) or
                (kind == "DOMAIN-SUFFIX" and
                 (host == suffix or host.endswith("." + suffix)))
                for kind, suffix in (item.split(",", 1) for item in rules)
                if kind in {"DOMAIN", "DOMAIN-SUFFIX"}
            )

        for host in (
            "api.openai.com", "auth.openai.com", "platform.openai.com",
            "setup.auth.openai.com", "ios.chat.openai.com",
            "ws.chatgpt.com", "codex-cloud-environments.chatgpt.com",
            "files.oaiusercontent.com", "cdn.oaistatic.com",
            "events.oaistatsig.com", "cdn.openaimerge.com",
            "openaiassets.blob.core.windows.net",
        ):
            with self.subTest(host=host):
                self.assertTrue(covers(host), host)

    def test_voice(self):
        doc = json.dumps({"prefixes": [
            {"ipv4Prefix": f"1.1.1.{i}/32"} for i in range(1, 6)
        ]})
        self.assertEqual(len(build.parse_voice(doc.encode())), 5)
        with self.assertRaises(ValueError):
            build.parse_voice(b'{"prefixes":[{"ipv4Prefix":"0.0.0.0/0"}]}')

    def test_voice_dual_ipv4_and_ipv6(self):
        items = [{"ipv4Prefix": f"1.1.1.{i}/32"} for i in range(1, 5)]
        items.append({
            "ipv4Prefix": "8.8.8.8/32",
            "ipv6Prefix": "2001:4860:4860::8888/128",
        })
        data = json.dumps({"prefixes": items}).encode()
        result = build.parse_voice(data)
        self.assertIn("IP-CIDR,8.8.8.8/32", result)
        self.assertIn("IP-CIDR6,2001:4860:4860::8888/128", result)
        self.assertEqual(len(result), 6)

    def test_manual_full(self):
        rules = build.parse_manual(build.ROOT / "config/manual-openai.rules")
        self.assertGreater(len(rules), 20)
        self.assertIn("DOMAIN-SUFFIX,openai.com", rules)
        self.assertIn("DOMAIN-SUFFIX,chatgpt.com", rules)
        self.assertIn("DOMAIN,cdn.openaimerge.com", rules)
        self.assertNotIn("DOMAIN-SUFFIX,prodregistryv2.org", rules)
        self.assertNotIn("DOMAIN-SUFFIX,statsig.com", rules)
        self.assertNotIn("AND,((PROTOCOL,UDP),(DST-PORT,3478))", rules)

    def test_independent_layers_with_internal_dedup_only(self):
        auto = [
            "DOMAIN-SUFFIX,openai.com",
            "DOMAIN,api.openai.com",
            "DOMAIN,openaiapi-site.azureedge.net",
            "DOMAIN-SUFFIX,openaiapi-site.azureedge.net",
            "DOMAIN-SUFFIX,chatgpt.com",
            "DOMAIN,ws.chatgpt.com",
            "DOMAIN-SUFFIX,oaistatic.com",
            "DOMAIN-SUFFIX,oaiusercontent.com",
            "DOMAIN-SUFFIX,oaistatsig.com",
            "DOMAIN-SUFFIX,sora.com",
            "DOMAIN-SUFFIX,chat.com",
            "DOMAIN-SUFFIX,crixet.com",
            "DOMAIN-SUFFIX,chatgpt.site",
        ]
        manual = [
            "DOMAIN-SUFFIX,openai.com",
            "DOMAIN,login.openai.com",  # covered within manual by the parent
            "DOMAIN,openaiapi-site.azureedge.net",
            "DOMAIN,cdn.openaimerge.com",
            "DOMAIN-WILDCARD,chatgpt-async-webps-prod-*.webpubsub.azure.com",
        ]
        compact_auto, compact_manual = build.compact_openai_rules(auto, manual)
        self.assertIn("DOMAIN-SUFFIX,openai.com", compact_auto)
        self.assertIn("DOMAIN-SUFFIX,openai.com", compact_manual)
        self.assertIn("DOMAIN-SUFFIX,openaiapi-site.azureedge.net", compact_auto)
        self.assertIn("DOMAIN,openaiapi-site.azureedge.net", compact_manual)
        self.assertNotIn("DOMAIN,api.openai.com", compact_auto)
        self.assertNotIn("DOMAIN,login.openai.com", compact_manual)
        self.assertNotIn("DOMAIN,openaiapi-site.azureedge.net", compact_auto)
        self.assertEqual(compact_manual, [
            "DOMAIN-SUFFIX,openai.com",
            "DOMAIN,openaiapi-site.azureedge.net",
            "DOMAIN,cdn.openaimerge.com",
            "DOMAIN-WILDCARD,chatgpt-async-webps-prod-*.webpubsub.azure.com",
        ])
        # The manual layer is independent of upstream's additions/deletions.
        upstream_without_openai = [r for r in auto
                                   if r != "DOMAIN-SUFFIX,openai.com"]
        _, manual_after_change = build.compact_openai_rules(
            upstream_without_openai, manual
        )
        self.assertEqual(manual_after_change, compact_manual)
        # Boundary-safe suffix semantics: a.com never matches nota.com.
        self.assertFalse(build.domain_rule_covers(
            "DOMAIN,openai.com", "DOMAIN,login.openai.com"
        ))
        self.assertFalse(build.domain_rule_covers(
            "DOMAIN-SUFFIX,openai.com", "DOMAIN,notopenai.com"
        ))

    def test_manual_exact_third_party_hosts_no_generic_suffix(self):
        active = build.parse_manual(build.ROOT / "config/manual-openai.rules")
        self.assertIn("DOMAIN,openai.qualtrics.com", active)
        self.assertIn("DOMAIN,openai-api.arkoselabs.com", active)
        self.assertIn("DOMAIN,cdn.openaimerge.com", active)
        self.assertIn("DOMAIN-WILDCARD,chatgpt-async-webps-prod-*.webpubsub.azure.com", active)
        for forbidden in ("DOMAIN-SUFFIX,workos.com",
                          "DOMAIN-SUFFIX,intercom.io",
                          "DOMAIN-SUFFIX,statsig.com",
                          "DOMAIN,cdn.workos.com",
                          "DOMAIN,challenges.cloudflare.com",
                          "AND,((PROTOCOL,UDP),(DST-PORT,3478))"):
            self.assertNotIn(forbidden, active)

    def test_shared_vendor_hosts_require_exact_verified_approval(self):
        for unsafe in (
            "DOMAIN-SUFFIX,openaiapi-site.azureedge.net",
            "DOMAIN-SUFFIX,openaicom.imgix.net",
            "DOMAIN-SUFFIX,azureedge.net",
            "DOMAIN-SUFFIX,workos.com",
            "DOMAIN-SUFFIX,stripe.com",
            "DOMAIN,cdn.workos.com",
            "DOMAIN,challenges.cloudflare.com",
            "DOMAIN-WILDCARD,*.workos.com",
            "DOMAIN-KEYWORD,openai",
        ):
            with self.subTest(unsafe=unsafe):
                self.assertFalse(build.is_openai_specific_rule(unsafe))
        for safe in (
            "DOMAIN,openaiapi-site.azureedge.net",
            "DOMAIN,openaicom.imgix.net",
            "DOMAIN,openai.qualtrics.com",
            "DOMAIN,openai-api.arkoselabs.com",
            "DOMAIN-SUFFIX,chatgpt.livekit.cloud",
            "DOMAIN-SUFFIX,openai.com",
        ):
            with self.subTest(safe=safe):
                self.assertTrue(build.is_openai_specific_rule(safe))

        # Shared third-party rules stay commented, and accidentally
        # enabling a broad/shared line aborts generation safely.
        existing = (build.ROOT / "config/manual-openai.rules").read_text(
            encoding="utf-8"
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manual.rules"
            for bad in (
                "DOMAIN-SUFFIX,workos.com",
                "DOMAIN,cdn.workos.com",
                "DOMAIN-SUFFIX,openaiapi-site.azureedge.net",
            ):
                path.write_text(existing + "\n" + bad + "\n", encoding="utf-8")
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    build.parse_manual(path)

    def test_v2fly_geosite_parser(self):
        source = "\n".join((
            "chat.com", "chatgpt.com", "chatgpt.site", "crixet.com",
            "oaistatic.com", "oaistatsig.com", "oaiusercontent.com",
            "openai.com", "sora.com",
            "full:openaiassets.blob.core.windows.net",
            r"regexp:^chatgpt-async-webps-prod-\S+-\d+\.webpubsub\.azure\.com$",
            "full:openai.qualtrics.com @ads",
            "full:browser-intake-datadoghq.com @ads",
        ))
        parsed = build.parse_domain_list(source, "v2fly")
        self.assertIn("DOMAIN-SUFFIX,chatgpt.com", parsed)
        self.assertIn("DOMAIN,openaiassets.blob.core.windows.net", parsed)
        self.assertIn("DOMAIN,openai.qualtrics.com", parsed)
        self.assertIn(
            "DOMAIN-WILDCARD,chatgpt-async-webps-prod-*.webpubsub.azure.com",
            parsed,
        )
        self.assertNotIn("DOMAIN,openaiassets.blob.core.windows.net @ads", parsed)
        filtered = build.filter_auto_domains(parsed)
        self.assertNotIn("DOMAIN,browser-intake-datadoghq.com", filtered)
        self.assertIn("DOMAIN,openai.qualtrics.com", filtered)

    def test_manual_coverage_invariant_and_two_sources(self):
        original = build.parse_manual(build.ROOT / "config/manual-openai.rules")
        compacted = build.compact_rules_within_layer(original)
        # A manual-only rule may disappear ONLY when an emitted manual rule
        # provably covers exactly the same or more hostnames.
        for rule in original:
            with self.subTest(rule=rule):
                self.assertTrue(any(
                    build.domain_rule_covers(kept, rule) for kept in compacted
                ))
        # The two routing inputs are a generated automatic source and
        # the editable manual original; no third list is required.
        code = (build.ROOT / "scripts/build.py").read_text(encoding="utf-8")
        self.assertIn('ROOT / "rules/openai-auto.list"', code)
        self.assertNotIn('ROOT / "rules/openai-auto-domains.list"', code)
        self.assertNotIn('ROOT / "rules/openai-voice-ips.list"', code)
        self.assertNotIn('ROOT / "rules/openai-manual-fallback.list"', code)
        self.assertIn('ROOT / "config/manual-openai.rules"', code)

    def test_every_original_hy_rule_preserved_as_active_or_archived(self):
        # Independent original user HY ACL inventory (excluding geosite:openai).
        # Never drop entries merely because another list overlaps them.
        expected = {
            "DOMAIN-SUFFIX,openai.com",
            "DOMAIN-SUFFIX,oaistatic.com",
            "DOMAIN-SUFFIX,oaiusercontent.com",
            "DOMAIN-SUFFIX,oaistatsig.com",
            "DOMAIN-SUFFIX,sora.com",
            "DOMAIN-SUFFIX,chat.com",
            "DOMAIN-SUFFIX,crixet.com",
            "DOMAIN,openai.com.cdn.cloudflare.net",
            "DOMAIN,openaiapi-site.azureedge.net",
            "DOMAIN,openaiassets.blob.core.windows.net",
            "DOMAIN,openaicom-api-bdcpf8c6d2e9atf6.z01.azurefd.net",
            "DOMAIN,openaicom.imgix.net",
            "DOMAIN,openaicomproductionae4b.blob.core.windows.net",
            "DOMAIN,production-openaicom-storage.azureedge.net",
            "DOMAIN-SUFFIX,chatgpt.com",
            "DOMAIN-SUFFIX,chatgpt.site",
            "DOMAIN-WILDCARD,chatgpt-async-webps-prod-*.webpubsub.azure.com",
            "DOMAIN-SUFFIX,chatgpt.livekit.cloud",
            "DOMAIN-SUFFIX,host.livekit.cloud",
            "DOMAIN-SUFFIX,turn.livekit.cloud",
            "DOMAIN,cdn.openaimerge.com",
            "DOMAIN,cdn.workos.com",
            "DOMAIN,forwarder.workos.com",
            "DOMAIN,setup.workos.com",
            "DOMAIN,images.workoscdn.com",
            "DOMAIN,workos.imgix.net",
            "DOMAIN,challenges.cloudflare.com",
            "DOMAIN,humb.apple.com",
            "DOMAIN-SUFFIX,intercom.io",
            "DOMAIN-SUFFIX,intercomcdn.com",
            "DOMAIN-SUFFIX,ct.sendgrid.net",
            "DOMAIN,js.stripe.com",
            "DOMAIN,o207216.ingest.sentry.io",
            "DOMAIN,o33249.ingest.sentry.io",
            "DOMAIN,browser-intake-datadoghq.com",
            "DOMAIN,rum.browser-intake-datadoghq.com",
            "DOMAIN,openai.qualtrics.com",
            "AND,((PROTOCOL,UDP),(DST-PORT,3478))",
            "DOMAIN-SUFFIX,statsig.com",
            "DOMAIN-SUFFIX,statsigapi.net",
            "DOMAIN-SUFFIX,featuregates.org",
            "DOMAIN-SUFFIX,featureassets.org",
            "DOMAIN-SUFFIX,prodregistryv2.org",
        }
        self.assertEqual(len(expected), 43)
        raw = (build.ROOT / "config/manual-openai.rules").read_text(
            encoding="utf-8"
        ).splitlines()
        active = {line.strip() for line in raw
                  if line.strip().startswith(("DOMAIN", "AND,"))}
        archived = {line.strip()[2:] for line in raw
                    if line.strip().startswith(("# DOMAIN", "# AND,"))}
        self.assertFalse(expected - active - archived)
        self.assertIn("DOMAIN-SUFFIX,openai.com", active)
        self.assertIn("DOMAIN,cdn.workos.com", archived)
        self.assertIn(
            "AND,((PROTOCOL,UDP),(DST-PORT,3478))", archived
        )
        # HY geosite:openai is represented by maintained public sources.
        self.assertIn('"v2fly":', (
            build.ROOT / "scripts/build.py"
        ).read_text(encoding="utf-8"))

    def test_only_two_user_variables(self):
        settings = build.load_settings()
        self.assertEqual(set(settings), build.SETTING_KEYS)
        self.assertEqual(build.SETTING_KEYS, {"openai_node_name", "johnshall_proxy_node_name"})
        for name in settings.values():
            self.assertIsInstance(name, str)
            self.assertTrue(name.strip())
        self.assertNotEqual(
            settings["openai_node_name"].casefold(),
            settings["johnshall_proxy_node_name"].casefold(),
        )
        self.assertEqual(build.CONFIG.name, "Shadowrocket_Johnshall_OpenAI.conf")

    def test_node_names_can_change_without_changing_tests(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "user-settings.json"
            for names in (
                {"openai_node_name": "日本JP-1", "johnshall_proxy_node_name": "韩国KR-1"},
                {"openai_node_name": "美国US", "johnshall_proxy_node_name": "新加坡SG"},
            ):
                path.write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
                with self.subTest(names=names):
                    self.assertEqual(build.load_settings(path), names)

    def test_exact_node_name_and_dns_escaping(self):
        settings = {"openai_node_name": "🛰️ OpenAI 出口", "johnshall_proxy_node_name": "🌐 常规代理出口"}
        dns = build.render_dns(settings)
        self.assertIn("#proxy=" + quote(settings["johnshall_proxy_node_name"], safe=""), dns)
        self.assertNotIn("#proxy=" + quote(settings["openai_node_name"], safe=""), dns)
        self.assertIn("dns-server = https://dns.google/dns-query#proxy=" + quote(settings["johnshall_proxy_node_name"], safe=""), dns)
        self.assertIn("direct-dns-server = https://dns.alidns.com/dns-query#no-h3", dns)
        self.assertIn("fallback-dns-server = https://dns.alidns.com/dns-query#no-h3", dns)
        self.assertIn("proxy-dns-server = https://dns.alidns.com/dns-query#no-h3", dns)

    def test_settings_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "user-settings.json"
            for invalid in [
                {"openai_node_name": ""},
                {"openai_node_name": "PROXY"},
                {"openai_node_name": "日本JP", "johnshall_proxy_node_name": "日本JP"},
                {"openai_node_name": "bad,syntax"},
                {"openai_node_name": "bad\\name"},
                {"openai_node_name": "bad\n[Rule]"},
                {"openai_node_name": "JP", "johnshall_proxy_node_name": "KR", "extra_policy_name": "JP"},
            ]:
                data = dict(build.load_settings())
                data.update(invalid)
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    build.load_settings(path)

    def test_build_uses_nodes_directly_no_groups(self):
        upstream = (
            "# synthetic test config\n"
            "[General]\ndns-server = https://old.example/dns-query\n"
            "[Rule]\n"
            + "".join(f"DOMAIN-SUFFIX,proxy{i}.example,Proxy\n" for i in range(10001))
            + "".join(f"DOMAIN-SUFFIX,ads{i}.example,Reject\n" for i in range(20001))
            + ("# another upstream entry\n" * 22000)
            + "FINAL,direct\n"
            "[URL Rewrite]\nrewrite\n"
            "[MITM]\nhostname=example\n"
        )
        settings = {"openai_node_name": "美国US-1", "johnshall_proxy_node_name": "新加坡SG-2"}
        output, counts = build.generate(
            upstream,
            ["IP-CIDR,8.8.4.0/24"],
            ["DOMAIN-SUFFIX,chatgpt.com"],
            ["DOMAIN-SUFFIX,openai.com", "DOMAIN-SUFFIX,chatgpt.com"],
            settings=settings,
        )
        self.assertNotIn("[Proxy Group]", output)
        # Manual/automatic duplicate is intentional: independent layers.
        same_rule = "DOMAIN-SUFFIX,chatgpt.com,美国US-1,force-remote-dns"
        self.assertEqual(output.count(same_rule), 2)
        self.assertLess(
            output.index("# [1b] OpenAI automatic rules - public domain rules"),
            output.index("# [2] Independent manual OpenAI fallback"),
        )
        self.assertIn("DOMAIN-SUFFIX,chatgpt.com,美国US-1,force-remote-dns", output)
        self.assertIn("IP-CIDR,8.8.4.0/24,美国US-1,no-resolve", output)
        self.assertIn("DOMAIN-SUFFIX,openai.com,美国US-1,force-remote-dns", output)
        self.assertIn("DOMAIN-SUFFIX,proxy42.example,新加坡SG-2", output)
        self.assertNotIn("DOMAIN-SUFFIX,proxy42.example,新加坡SG-2,force-remote-dns", output)
        self.assertIn("#proxy=" + quote("新加坡SG-2", safe=""), output)
        self.assertNotIn(",Proxy\n", output)
        self.assertEqual(counts["mapped_proxy_to_johnshall_node"], 10001)
        self.assertEqual(counts["retained_ad_rules"], 20001)
        self.assertTrue(output.rstrip().endswith("hostname=example"))

    def test_upstream_sections(self):
        banner, general, rules, tail = build.split_base(
            "# banner\n[General]\nipv6 = false\n"
            "[Rule]\nDOMAIN-SUFFIX,telegram.org,Proxy\nFINAL,direct\n"
            "[URL Rewrite]\nrewrite\n[MITM]\nhostname=foo\n"
        )
        self.assertIn("# banner", banner)
        self.assertIn("ipv6", general)
        self.assertIn("telegram.org,Proxy", rules)
        self.assertIn("[MITM]", tail)


if __name__ == "__main__":
    unittest.main()
