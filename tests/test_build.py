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

    def test_only_two_user_variables(self):
        self.assertEqual(build.load_settings(), {
            "jp_node_name": "日本JP",
            "kr_node_name": "韩国KR",
        })
        self.assertEqual(build.SETTING_KEYS, {"jp_node_name", "kr_node_name"})

    def test_exact_node_name_and_dns_escaping(self):
        settings = {"jp_node_name": "🇯🇵 东京 JP 01", "kr_node_name": "🇰🇷 首尔 KR 02"}
        dns = build.render_dns(settings)
        self.assertIn("#proxy=" + quote(settings["kr_node_name"], safe=""), dns)
        self.assertNotIn("#proxy=" + quote(settings["jp_node_name"], safe=""), dns)
        self.assertIn("dns-server = https://dns.google/dns-query#proxy=" + quote(settings["kr_node_name"], safe=""), dns)
        self.assertIn("direct-dns-server = https://dns.alidns.com/dns-query#no-h3", dns)
        self.assertIn("fallback-dns-server = https://dns.alidns.com/dns-query#no-h3", dns)
        self.assertIn("proxy-dns-server = https://dns.alidns.com/dns-query#no-h3", dns)

    def test_settings_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "user-settings.json"
            for invalid in [
                {"jp_node_name": ""},
                {"jp_node_name": "PROXY"},
                {"jp_node_name": "日本JP", "kr_node_name": "日本JP"},
                {"jp_node_name": "bad,syntax"},
                {"jp_node_name": "bad\\name"},
                {"jp_node_name": "bad\n[Rule]"},
                {"jp_node_name": "JP", "kr_node_name": "KR", "jp_policy_name": "JP"},
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
        settings = {"jp_node_name": "东京日本-1", "kr_node_name": "首尔韩国-2"}
        output, counts = build.generate(
            upstream,
            ["IP-CIDR,8.8.4.0/24"],
            ["DOMAIN-SUFFIX,chatgpt.com"],
            ["DOMAIN-SUFFIX,openai.com"],
            settings=settings,
        )
        self.assertNotIn("[Proxy Group]", output)
        self.assertIn("DOMAIN-SUFFIX,chatgpt.com,东京日本-1,force-remote-dns", output)
        self.assertIn("IP-CIDR,8.8.4.0/24,东京日本-1,no-resolve", output)
        self.assertIn("DOMAIN-SUFFIX,openai.com,东京日本-1,force-remote-dns", output)
        self.assertIn("DOMAIN-SUFFIX,proxy42.example,首尔韩国-2", output)
        self.assertNotIn("DOMAIN-SUFFIX,proxy42.example,首尔韩国-2,force-remote-dns", output)
        self.assertIn("#proxy=" + quote("首尔韩国-2", safe=""), output)
        self.assertNotIn(",Proxy\n", output)
        self.assertEqual(counts["mapped_proxy_to_kr"], 10001)
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
