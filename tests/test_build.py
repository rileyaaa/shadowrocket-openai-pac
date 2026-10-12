import json
from pathlib import Path
import tempfile
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build

class BuildTest(unittest.TestCase):
    def test_domains(self):
        data = "+.chatgpt.com\nopenai.com\n" + "\n".join("host%d.example.org" % i for i in range(9))
        rules = build.parse_domain_list(data, "meta")
        self.assertIn("DOMAIN-SUFFIX,chatgpt.com", rules)
        self.assertIn("DOMAIN,openai.com", rules)
        typed = "IP-ASN,20473\nDOMAIN-KEYWORD,openai\n" + "\n".join("DOMAIN-SUFFIX,site%d.example.org" % i for i in range(9))
        self.assertFalse(any("IP-ASN" in x for x in build.parse_domain_list(typed, "typed")))

    def test_voice(self):
        doc = json.dumps({"prefixes": [{"ipv4Prefix":"1.1.1.%d/32" % i} for i in range(1,6)]})
        self.assertEqual(len(build.parse_voice(doc.encode())), 5)
        with self.assertRaises(ValueError):
            build.parse_voice(b'{"prefixes":[{"ipv4Prefix":"0.0.0.0/0"}]}')

    def test_manual_full(self):
        rules = build.parse_manual(build.ROOT / "config/manual-openai.rules")
        self.assertGreater(len(rules), 40)
        self.assertIn("DOMAIN-SUFFIX,openai.com", rules)
        self.assertIn("DOMAIN-SUFFIX,prodregistryv2.org", rules)
        self.assertIn("AND,((PROTOCOL,UDP),(DST-PORT,3478))", rules)

    def test_user_settings_load_and_exact_node_selection(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "config.json"
            settings = {
                "jp_node_name": "🇯🇵 日本 JP-01",
                "kr_node_name": "🇰🇷 韩国 KR-02",
                "jp_policy_name": "GPT-JP",
                "kr_policy_name": "DAILY-KR",
            }
            path.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
            loaded = build.load_settings(path)
            groups = build.render_groups(loaded)
            self.assertIn("GPT-JP = select,🇯🇵 日本 JP-01,policy-select-name=🇯🇵 日本 JP-01", groups)
            self.assertIn("DAILY-KR = select,🇰🇷 韩国 KR-02,policy-select-name=🇰🇷 韩国 KR-02", groups)
            self.assertNotIn("policy-regex-filter=", groups)
            self.assertIn("#proxy=GPT-JP", build.render_dns(loaded))
            self.assertNotIn("#proxy=JP", build.render_dns(loaded))

    def test_user_settings_regex_fallback(self):
        settings = build.load_settings()
        groups = build.render_groups(settings)
        self.assertIn("JP = select,policy-regex-filter=", groups)
        self.assertIn("KR = select,policy-regex-filter=", groups)

    def test_user_settings_validation(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "config.json"
            base = build.load_settings()
            for patch in (
                {"jp_policy_name": "DIRECT"},
                {"jp_policy_name": "KR"},
                {"jp_node_name": "bad,inject"},
                {"jp_node_name": "bad\\n[Rule]"},
                {"jp_node_name": "Japan", "kr_node_name": "Japan"},
                {"kr_node_name": "JP"},
            ):
                settings = dict(base, **patch)
                path.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
                with self.subTest(patch=patch), self.assertRaises(ValueError):
                    build.load_settings(path)

    def test_policy_renaming_changes_every_output_reference(self):
        # Build the complete upstream shape with synthetic domains.
        original = (
            "# synthetic Johnshall for testing only\n[General]\n"
            "dns-server = https://old.example/dns-query\n"
            "[Rule]\n"
            + "".join(f"DOMAIN-SUFFIX,proxy{i}.example,Proxy\n" for i in range(10001))
            + "".join(f"DOMAIN-SUFFIX,ads{i}.example,Reject\n" for i in range(20001))
            + ("# extra upstream entry\n" * 22000)
            + "FINAL,direct\n[URL Rewrite]\nrewrite\n[MITM]\nhostname=example\n"
        )
        custom = {
            "jp_node_name": "日本-指定节点A",
            "kr_node_name": "韩国-指定节点B",
            "jp_policy_name": "GPT-JAPAN",
            "kr_policy_name": "DAILY-KOREA",
        }
        out, counts = build.generate(
            original, ["IP-CIDR,8.8.4.0/24"],
            ["DOMAIN-SUFFIX,chatgpt.com"],
            ["DOMAIN-SUFFIX,openai.com"], settings=custom,
        )
        self.assertIn("GPT-JAPAN = select,日本-指定节点A,policy-select-name=日本-指定节点A", out)
        self.assertIn("DAILY-KOREA = select,韩国-指定节点B,policy-select-name=韩国-指定节点B", out)
        self.assertIn("fallback-dns-server = https://dns.google/dns-query#proxy=GPT-JAPAN", out)
        self.assertIn("IP-CIDR,8.8.4.0/24,GPT-JAPAN,no-resolve", out)
        self.assertIn("DOMAIN-SUFFIX,openai.com,GPT-JAPAN", out)
        self.assertIn("DOMAIN-SUFFIX,proxy42.example,DAILY-KOREA", out)
        self.assertNotIn(",Proxy\n", out)
        self.assertEqual(counts["mapped_proxy_to_kr"], 10001)
        self.assertEqual(counts["retained_ad_rules"], 20001)
        self.assertTrue(out.rstrip().endswith("hostname=example"))

    def test_upstream_parser(self):
        banner, g, r, tail = build.split_base(
            "# banner\n[General]\nipv6 = false\n[Rule]\n"
            "DOMAIN-SUFFIX,telegram.org,Proxy\nFINAL,direct\n"
            "[URL Rewrite]\nrewrite\n[MITM]\nhostname=foo\n")
        self.assertIn("# banner",banner)
        self.assertIn("ipv6", g)
        self.assertIn("telegram.org,Proxy", r)
        self.assertIn("[MITM]", tail)
        self.assertEqual(build.PROXY_POLICY.sub(",KR", "DOMAIN-SUFFIX,telegram.org,Proxy"),"DOMAIN-SUFFIX,telegram.org,KR")

if __name__ == "__main__":
    unittest.main()
