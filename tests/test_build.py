import json
from pathlib import Path
import sys
import tempfile
import unittest

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

    def test_voice(self):
        doc = json.dumps({"prefixes": [
            {"ipv4Prefix": f"1.1.1.{i}/32"} for i in range(1, 6)
        ]})
        self.assertEqual(len(build.parse_voice(doc.encode())), 5)
        with self.assertRaises(ValueError):
            build.parse_voice(b'{"prefixes":[{"ipv4Prefix":"0.0.0.0/0"}]}')

    def test_manual_full(self):
        rules = build.parse_manual(build.ROOT / "config/manual-openai.rules")
        self.assertGreater(len(rules), 40)
        self.assertIn("DOMAIN-SUFFIX,openai.com", rules)
        self.assertIn("DOMAIN-SUFFIX,prodregistryv2.org", rules)
        self.assertIn("AND,((PROTOCOL,UDP),(DST-PORT,3478))", rules)

    def test_only_two_user_variables(self):
        self.assertEqual(build.load_settings(), {
            "jp_node_name": "日本JP",
            "kr_node_name": "韩国KR",
        })
        self.assertEqual(build.SETTING_KEYS, {"jp_node_name", "kr_node_name"})

    def test_exact_node_name_and_dns_escaping(self):
        settings = {"jp_node_name": "🇯🇵 东京 JP 01", "kr_node_name": "🇰🇷 首尔 KR 02"}
        dns = build.render_dns(settings)
        self.assertIn("#proxy=%F0%9F%87%AF%F0%9F%87%B5%20%E4%B8%9C%E4%BA%AC%20JP%2001", dns)
        self.assertNotIn("#proxy=JP\n", dns)

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
        self.assertIn("DOMAIN-SUFFIX,chatgpt.com,东京日本-1", output)
        self.assertIn("IP-CIDR,8.8.4.0/24,东京日本-1,no-resolve", output)
        self.assertIn("DOMAIN-SUFFIX,openai.com,东京日本-1", output)
        self.assertIn("DOMAIN-SUFFIX,proxy42.example,首尔韩国-2", output)
        self.assertIn("#proxy=%E4%B8%9C%E4%BA%AC%E6%97%A5%E6%9C%AC-1", output)
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
