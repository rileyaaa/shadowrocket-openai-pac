import sys
from pathlib import Path
from datetime import date, timedelta
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

    def test_all_pairs_and_change_or_monthly_receipts(self):
        result = rc.detect([('domain','domain:r.openai.com','block'),
                            ('domain','full:ads.openai.com','block')],
                           [('domain','domain:openai.com','proxy')], limit=1)
        self.assertEqual(result['count'],2)
        self.assertEqual(len(result['examples']),1)
        self.assertEqual(len(result['pairs']),2)
        on = date(2026,11,24)
        state = {'version':1,'current':[],'delivered':[],'notified_at':None}
        state, report = rc.evaluate(result,state,on=on)
        self.assertTrue(report['alert'])
        state, report = rc.evaluate(result,state,on=on)
        self.assertEqual(len(report['added']),2)  # not acknowledged
        state.update(delivered=report['pairs'], notified_at=on.isoformat())
        self.assertFalse(rc.evaluate(result,state,on=on+timedelta(days=29))[1]['alert'])
        self.assertTrue(rc.evaluate(result,state,on=on+timedelta(days=30))[1]['alert'])
        empty = rc.detect([], [])
        self.assertEqual(len(rc.evaluate(empty,state,on=on)[1]['removed']),2)

if __name__ == '__main__':
    unittest.main()
