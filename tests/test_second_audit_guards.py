import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import route_semantics as sem
import upstream_integrity as guard

class SecondAuditGuards(unittest.TestCase):
    def test_unique_and_per_source_counts(self):
        with self.assertRaisesRegex(ValueError, 'distinct'):
            guard.record_counts({'a': {}}, {'a': ['DOMAIN,x.test'] * 10}, {}, {})
        with self.assertRaisesRegex(ValueError, 'apple'):
            guard.validate_counts({'a': {'rule_count': 20}, 'apple': {'rule_count': 1}},
                {'sources': {'a': {'rule_count': 20}, 'apple': {'rule_count': 2}}}, ['a'], ['apple'])
        with self.assertRaisesRegex(ValueError, 'a:'):
            guard.validate_counts({'a': {'rule_count': 10}, 'b': {'rule_count': 30}},
                {'sources': {'a': {'rule_count': 20}, 'b': {'rule_count': 30}}}, ['a','b'], [])
    def test_missing_current_source_count_cannot_reset_baseline(self):
        records = {'a': {'rule_count': 20}, 'apple': {'rule_count': 2}}
        old = {'schema_version': 2, 'sources': {
            'a': {'sha256': 'a'*64}, 'apple': {'rule_count': 2}}}
        with self.assertRaisesRegex(ValueError, 'rule_count baseline: a'):
            guard.validate_counts(records, old, ['a'], ['apple'])
        old['schema_version'] = 1
        guard.validate_counts(records, old, ['a'], ['apple'])
        old['sources'].pop('a')
        with self.assertRaisesRegex(ValueError, 'source record: a'):
            guard.validate_counts(records, old, ['a'], ['apple'])
        guard.validate_counts(records, None, ['a'], ['apple'])

    def test_shadow_actual_policy_not_only_hash(self):
        voice = ['IP-CIDR,8.8.8.8/32']
        prefix = '[General]\n[Rule]\nIP-CIDR,8.8.8.8/32,AI,no-resolve\n'
        domains = ''.join('DOMAIN,' + host + ',AI,force-remote-dns\n' for host in sem.CORE_HOSTS)
        tail = '# [3] Johnshall full original rules, Proxy mapped to exact configured node\nFINAL,direct\n[URL Rewrite]\n'
        output = prefix + domains + tail
        sem.verify_shadow(output, {'openai_node_name':'AI'}, voice)
        with self.assertRaisesRegex(ValueError, 'policy'):
            sem.verify_shadow(output.replace('DOMAIN,api.openai.com,AI', 'DOMAIN,api.openai.com,DIRECT'),
                              {'openai_node_name':'AI'}, voice)
    def test_v2_first_match_includes_earlier_blocks(self):
        def row(label, field, values, action):
            return {'remarks':label + ' / ' + action, field:values,'outboundTag':action,'enabled':True}
        rows = [
          row('local','ip',['127.0.0.0/8','::1/128','geoip:private'],'direct'),
          row('local','domain',['full:localhost','domain:localhost.localdomain'],'direct'),
          row('Johnshall ads and tracking','domain',['full:ad.test'],'block'),
          row('BitBrowser verified process','process',['BitBrowser.exe'],'proxy'),
          row('BitBrowser selected domains','domain',['domain:bit.test'],'proxy'),
          row('OpenAI official Voice IPs','ip',['8.8.8.8/32'],'proxy'),
          row('OpenAI reviewed and user extras','domain',['full:'+x for x in sem.CORE_HOSTS],'proxy'),
          row('Gemini approved rules','domain',['domain:gemini.google.com'],'proxy'),
          row('Claude approved rules','domain',['domain:claude.ai'],'proxy'),
          row('Johnshall original order','domain',['domain:test'],'direct'),
          {'port':'0-65535','outboundTag':'direct','enabled':True}]
        sem.verify_v2(rows,['IP-CIDR,8.8.8.8/32'],['BitBrowser.exe'])
        rows[2]['domain'].append('domain:openai.com')
        with self.assertRaisesRegex(ValueError, 'api.openai.com'):
            sem.verify_v2(rows,['IP-CIDR,8.8.8.8/32'],['BitBrowser.exe'])

if __name__ == '__main__':
    unittest.main()
