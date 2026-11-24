"""Positive coverage, negative isolation, exact scope and review reminders."""
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import route_semantics as sem
import approved_dependency_review as dep
import build
import ai_services as ai


class RoutingQualityTests(unittest.TestCase):
    def test_same_proxy_tag_does_not_hide_non_target_interception(self):
        ordinary = [(['domain:google.com'], 'proxy')]
        with self.assertRaisesRegex(ValueError, 'mail.google.com'):
            sem.require_isolation([(['domain:google.com'], 'proxy')], ordinary, ['mail.google.com'])
        sem.require_isolation([(['domain:gemini.google.com'], 'proxy')], ordinary, ['mail.google.com'])

    def test_exact_host_and_suffix_boundary(self):
        overlay = [(['full:js.stripe.com', 'domain:openai.com'], 'AI')]
        sem.require_isolation(overlay, [], ['sub.js.stripe.com', 'notopenai.com', 'openai.com.example'])
        with self.assertRaisesRegex(ValueError, 'sub.js.stripe.com'):
            sem.require_isolation([(['domain:js.stripe.com'], 'AI')], [], ['sub.js.stripe.com'])

    def test_shadow_negative_check_and_extra_rule_not_in_reviewed_inputs(self):
        voice = ['IP-CIDR,8.8.8.8/32']
        start = '[General]\n[Rule]\nIP-CIDR,8.8.8.8/32,AI,no-resolve\n'
        domains = ''.join('DOMAIN,'+h+',AI,force-remote-dns\n' for h in sem.CORE_HOSTS)
        end = '# [3] Johnshall full original rules, Proxy mapped to exact configured node\nDOMAIN,mail.google.com,Ordinary\nFINAL,direct\n[URL Rewrite]\n'
        expected = {'DOMAIN,'+h for h in sem.CORE_HOSTS}
        settings = {'openai_node_name':'AI'}
        sem.verify_shadow(start+domains+end, settings, voice, expected_domains=expected)
        with self.assertRaisesRegex(ValueError, 'Non-target host'):
            sem.verify_shadow(start+domains+'DOMAIN-SUFFIX,google.com,AI,force-remote-dns\n'+end, settings, voice)
        with self.assertRaisesRegex(ValueError, 'differ from reviewed inputs'):
            sem.verify_shadow(start+domains+'DOMAIN,unknown.example,AI,force-remote-dns\n'+end,
                              settings, voice, expected_domains=expected)

    def test_v2_missing_dedicated_host_cannot_fall_back_to_johnshall_proxy(self):
        def row(label, field, values, action):
            return {'remarks':label+' / '+action,field:values,'outboundTag':action,'enabled':True}
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
          row('Johnshall original order','domain',['domain:openai.com','domain:google.com'],'proxy'),
          {'port':'0-65535','outboundTag':'direct','enabled':True}]
        sem.verify_v2(rows,['IP-CIDR,8.8.8.8/32'],['BitBrowser.exe'])
        rows[6]['domain'].remove('full:api.openai.com')
        with self.assertRaisesRegex(ValueError, 'api.openai.com'):
            sem.verify_v2(rows,['IP-CIDR,8.8.8.8/32'],['BitBrowser.exe'])
        rows[6]['domain'].append('full:api.openai.com')
        rows[7]['domain'].append('domain:google.com')
        with self.assertRaisesRegex(ValueError, 'Non-target host'):
            sem.verify_v2(rows,['IP-CIDR,8.8.8.8/32'],['BitBrowser.exe'])

    def test_current_known_shared_scopes_have_review_records(self):
        policy = json.loads((ROOT / dep.POLICY).read_text(encoding='utf-8'))
        dep.validate_policy(policy, date(2026,11,24))
        tracked = {}
        for item in policy['groups']:
            tracked.setdefault(item['scope'],set()).update(item['rules'])
        self.assertTrue((build.OFFICIAL_CHATGPT_SHARED_RULES | build.OFFICIAL_CODEX_SHARED_RULES
                         | {'DOMAIN-SUFFIX,host.livekit.cloud','DOMAIN-SUFFIX,turn.livekit.cloud',
                            'DOMAIN-SUFFIX,openai.com.cdn.cloudflare.net'}) <= tracked['openai'])
        for service in ('gemini','claude'):
            self.assertTrue({'DOMAIN,'+h for h in ai.APPROVED_HOSTS[service]} <= tracked[service])
        # All extra user-specified rules NOT covered by the common OpenAI
        # allowlist must be tracked separately. Intentional duplicate regex
        # for the already reviewed Azure host is not a separate vendor scope.
        from build_v2rayn import parse_user_extra
        for field, value, action in parse_user_extra((ROOT/'config/v2rayn/openai-extra.rules').read_text(encoding='utf-8')):
            if value.startswith('regexp:'):
                continue
            kind,host = value.split(':',1)
            rule = ('DOMAIN,' if kind=='full' else 'DOMAIN-SUFFIX,')+host
            if not (build.is_openai_specific_rule(rule) or rule in build.OFFICIAL_CHATGPT_SHARED_RULES
                    or rule in build.OFFICIAL_CODEX_SHARED_RULES):
                self.assertIn(value,tracked['v2rayn_openai'])

    def test_due_calendar_and_delivery_cycle(self):
        row = {'id':'shared-test','scope':'openai','rules':['DOMAIN,shared.example'],
               'reviewed_at':'2026-01-31','evidence':'fixture','note':'fixture'}
        policy = {'version':1,'groups':[row]}
        state = {'version':1,'sent':{}}
        due = date(2026,7,31)
        self.assertFalse(dep.evaluate(policy,state,on=due-timedelta(days=1))['alerts'])
        result = dep.evaluate(policy,state,on=due)
        self.assertEqual(result['alerts'][0]['due_on'],'2026-07-31')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'receipts.json'
            self.assertEqual(dep.evaluate(policy,state,on=due)['alerts'],result['alerts'])
            dep.acknowledge(result,path,on=due)
            state=dep.read_state(path,due)
            self.assertEqual(dep.evaluate(policy,state,on=due+timedelta(days=29))['alerts'],[])
            self.assertEqual(len(dep.evaluate(policy,state,on=due+timedelta(days=30))['alerts']),1)
            row['reviewed_at']='2026-08-01'
            self.assertFalse(dep.evaluate(policy,state,on=date(2026,8,1))['alerts'])
            row['reviewed_at']=None
            self.assertEqual(dep.evaluate(policy,state,on=date(2026,8,1))['alerts'][0]['status'],'initial_review')


if __name__ == '__main__':
    unittest.main()
