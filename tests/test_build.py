import json
from pathlib import Path
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
