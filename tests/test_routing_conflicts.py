import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import routing_conflicts as rc

class RoutingConflictTests(unittest.TestCase):
    def test_domain_scope_and_ip_overlap(self):
        blocks = [('domain', 'domain:example.com', 'block'),
                  ('domain', 'full:ads.claude.ai', 'block'),
                  ('ip', '8.8.8.0/24', 'block')]
        routes = [('domain', 'full:api.example.com', 'proxy'),
                  ('domain', 'domain:claude.ai', 'proxy'),
                  ('domain', 'full:notexample.com', 'proxy'),
                  ('ip', '8.8.8.8/32', 'proxy'),
                  ('ip', '9.9.9.9/32', 'proxy')]
        result = rc.detect(blocks, routes)
        self.assertEqual(result['count'], 3)
        self.assertEqual([x['proxy_rule'] for x in result['examples']],
                         ['full:api.example.com', 'domain:claude.ai', '8.8.8.8/32'])

    def test_regex_and_keyword_witnesses(self):
        self.assertTrue(rc.domain_overlap('full:api.example.com', 'regexp:^api\.example\.com$'))
        self.assertTrue(rc.domain_overlap('full:api.example.com', 'keyword:example'))
        self.assertFalse(rc.domain_overlap('full:api.example.com', 'full:other.example.com'))
        self.assertFalse(rc.domain_overlap('full:api.example.com', 'geosite:ads'))

if __name__ == '__main__':
    unittest.main()
