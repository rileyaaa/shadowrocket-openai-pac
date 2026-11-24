"""Real offline builders, semantic verification, local Git pushes and receipts.

No public upstream or Telegram request is made. All Git remotes are disposable
local repositories; the real notification transport receives a fake response.
"""
from datetime import date
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build
import ai_services

NOTIFY = '''
import json, os, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, "scripts")
import notify_combined
class Response:
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps({"ok": os.environ.get("FIXTURE_TELEGRAM_FAIL") != "1"}).encode()
def send_fixture(request, timeout=20):
    payload = json.loads(request.data.decode())
    if payload["chat_id"] != "fixture": raise AssertionError("Unexpected chat")
    Path(os.environ["FIXTURE_MESSAGE"]).write_text(payload["text"], encoding="utf-8")
    return Response()
with patch("notify_telegram.urllib.request.urlopen", side_effect=send_fixture):
    raise SystemExit(notify_combined.main())
'''

class ReleaseEndToEndTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.work = self.tmp / 'work'
        self.remote = self.tmp / 'remote.git'
        self.fixtures = self.tmp / 'fixtures'
        self.fixtures.mkdir()
        self.work.mkdir()
        self.env = {**os.environ, 'GITHUB_ACTIONS':'true', 'GITHUB_REF':'refs/heads/main',
                    'GITHUB_EVENT_NAME':'push', 'GITHUB_REPOSITORY':'fixture/local',
                    'GITHUB_RUN_ID':'1', 'GITHUB_SERVER_URL':'https://github.com',
                    'PYTHONDONTWRITEBYTECODE':'1', 'TELEGRAM_BOT_TOKEN':'fixture',
                    'TELEGRAM_CHAT_ID':'fixture', 'GITHUB_STEP_SUMMARY':str(self.tmp/'summary.md'),
                    'FIXTURE_MESSAGE':str(self.tmp/'telegram.txt'), 'FIXTURE_TELEGRAM_FAIL':'0'}
        shutil.copytree(ROOT/'scripts', self.work/'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT/'config', self.work/'config')
        (self.work/'data').mkdir()
        shutil.copyfile(ROOT/'data/bitbrowser_domains.txt', self.work/'data/bitbrowser_domains.txt')
        policy = {'version':1,'default_review_months':6,'reminder_interval_days':30,'rejected_rules':[]}
        for name in ('review-decisions.json','ai-review-decisions.json'):
            self.write_json(self.work/'config'/name, policy)
        settings_path = self.work/'config/user-settings.json'
        # The builder already accepts UTF-8 BOM in the two user settings.
        # Exercise the same real release validator, not just the loader.
        settings_path.write_text(json.dumps({'openai_node_name':'Fixture AI',
            'johnshall_proxy_node_name':'Fixture Ordinary'})+'\n', encoding='utf-8-sig')
        self.command('git','init','--bare',str(self.remote))
        self.command('git','init','-b','main')
        self.command('git','config','user.name','Fixture')
        self.command('git','config','user.email','fixture@example.test')
        self.command('git','add','.')
        self.command('git','commit','-m','initial fixtures')
        self.command('git','remote','add','origin',str(self.remote))
        self.command('git','push','origin','main:main')
        self.make_sources()

    def command(self,*args,cwd=None,ok=True,env=None):
        p = subprocess.run(args,cwd=cwd or self.work,env={**self.env, **(env or {})},
                           text=True,capture_output=True,timeout=120)
        if ok:
            self.assertEqual(p.returncode,0,p.stdout[-3000:]+'\n'+p.stderr[-3000:])
        return p

    def write_json(self,path,obj):
        path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    def read_json(self,path):
        return json.loads(path.read_text(encoding='utf-8'))

    def remote_text(self,path):
        return self.command('git','--git-dir='+str(self.remote),'show','refs/heads/main:'+path).stdout

    def make_sources(self):
        p=self.fixtures
        apple=build.RULESET_SOURCES['apple_news'][0]
        base=('# local Johnshall fixture\n[General]\nipv6 = false\n[Rule]\n'
              + ''.join(f'DOMAIN,proxy{i}.example,Proxy\n' for i in range(10001))
              + ''.join(f'DOMAIN,ad{i}.example,Reject\n' for i in range(20001))
              + 'DOMAIN,r.openai.com,Reject\n'
              + '# preserve original fixture ordering and comments\n'*22000
              + f'rule-set , {apple} , Proxy\n final , DIRECT \n# FINAL,direct is the fallback\n'
              + '[URL Rewrite]\n^http://example.com https://example.com 302\n'
              + '[MITM]\nhostname = example.com\n'+build.JOHNSHALL_FOOTER+'\n')
        (p/'upstream.conf').write_text(base,encoding='utf-8')
        self.write_json(p/'voice.json',{'prefixes':[{'ipv4Prefix':f'8.8.4.{i}/32'} for i in range(1,6)]})
        (p/'apple_news.txt').write_text('\ufeff# TOTAL: 2\n domain , gspe1-ssl.ls.apple.com \nDOMAIN,news-client-search.apple.com\n',encoding='utf-8')
        domains=['openai.com','chatgpt.com','oaistatic.com','oaiusercontent.com','oaistatsig.com',
                 'sora.com','crixet.com','chat.com','chatgpt.site','openai.fm','fixture-vendor.example']
        for name,(_,fmt) in build.DOMAIN_SOURCES.items():
            prefix={'meta':'+.','typed':'DOMAIN-SUFFIX,','v2fly':''}[fmt]
            (p/(name+'.txt')).write_text('\n'.join(prefix+x for x in domains)+'\n',encoding='utf-8')
        gem=['gemini.google.com','generativelanguage.googleapis.com','fixture-ai.example']
        gem += [f'test{i}.gemini.google.com' for i in range(30)]
        cla=['claude.ai','anthropic.com','fixture-claude.example']+[f'c{i}.claude.ai' for i in range(12)]
        for key,(service,fmt,_) in ai_services.SOURCES.items():
            prefix='+.' if fmt=='meta' else ''
            (p/(key+'.txt')).write_text('\n'.join(prefix+x for x in (gem if service=='gemini' else cla))+'\n',encoding='utf-8')
        (p/'gemini_app_firewall.html').write_text('<p>'+' '.join(
            ['gemini.google.com','generativelanguage.googleapis.com','accounts.google.com',
             'ssl.gstatic.com','www.googleapis.com','lh3.googleusercontent.com',
             'play.google.com','fonts.googleapis.com','www.google.com','ai.studio','*.fixture-ai.example'])+'</p>',encoding='utf-8')
        (p/'claude_code_network.html').write_text('<p>claude.ai claude.com *.api.anthropic.com fixture-doc.example</p>',encoding='utf-8')

    def build_pair(self,label,*,shadow_bad=False,v2_extra=False,docs=False):
        d=self.tmp/label
        d.mkdir()
        v2fixtures=d/'v2'
        shutil.copytree(self.fixtures,v2fixtures)
        if v2_extra:
            with (v2fixtures/'v2fly.txt').open('a',encoding='utf-8') as f:
                f.write('v2-only-new.example\n')
        bad=d/'bad'
        if shadow_bad:
            bad.mkdir()
            (bad/'apple_news.txt').write_text('# TOTAL: 1\nDOMAIN,gspe1-ssl.ls.apple.com\n',encoding='utf-8')
        reports={}
        status={}
        for key,script,fixture in (
                ('shadowrocket_ai','build_ai_shadowrocket.py',self.fixtures),
                ('v2rayn','build_v2rayn.py',v2fixtures)):
            report=d/(key+'.json')
            reports[key]=str(report)
            ruleset=bad if shadow_bad and key=='shadowrocket_ai' else fixture
            run=self.command(sys.executable,'-B','scripts/'+script,
                '--upstream-file',str(fixture/'upstream.conf'),'--voice-file',str(fixture/'voice.json'),
                '--domain-dir',str(fixture),'--ruleset-dir',str(ruleset),'--ai-dir',str(fixture),
                '--report-file',str(report),ok=False)
            if shadow_bad and key=='shadowrocket_ai':
                self.assertNotEqual(run.returncode,0)
                self.assertFalse(report.exists())
            else:
                self.assertEqual(run.returncode,0,run.stdout[-2000:]+run.stderr[-2000:])
            status[key]={'exit_code':run.returncode,'error':run.stderr[-500:]}
        if docs:
            report=d/'docs.json'
            self.command(sys.executable,'-B','scripts/audit_ai_docs.py','--force',
                '--source-dir',str(self.fixtures),'--report-file',str(report),
                '--shadow-report',reports['shadowrocket_ai'],'--v2-report',reports['v2rayn'])
            self.assertTrue(self.read_json(report)['initial_baseline'])
            reports['official_docs']=str(report)
            status['official_docs']={'exit_code':0}
        status['reports']=reports
        path=d/'status.json'
        self.write_json(path,status)
        return path

    def publish(self,path):
        self.command(sys.executable,'-B','scripts/publish_dual.py','--status-file',str(path))
        return self.read_json(path)

    def notify(self,path,fail=False):
        p=self.command(sys.executable,'-B','-c',NOTIFY,'--status-file',str(path),
            '--review-state-file','data/review-notifications.json',
            '--ai-review-state-file','data/ai-review-notifications.json',
            '--conflict-state-file','data/routing-conflicts.json',
            '--dependency-state-file','data/approved-dependency-notifications.json',ok=not fail,
            env={'FIXTURE_TELEGRAM_FAIL':'1' if fail else '0'})
        if fail:
            self.assertEqual(p.returncode,1)
        return (self.tmp/'telegram.txt').read_text(encoding='utf-8')

    def receipts(self,path,ok=True):
        return self.command(sys.executable,'-B','scripts/persist_receipts.py','--status-file',str(path),ok=ok)

    def test_missing_review_data_warns_without_discarding_verified_subscriptions(self):
        path = self.build_pair('missing-review-data')
        pending = self.read_json(path)
        shadow_report = Path(pending['reports']['shadowrocket_ai'])
        report = self.read_json(shadow_report)
        del report['ai_review_candidates']
        self.write_json(shadow_report, report)
        v2_report = Path(pending['reports']['v2rayn'])
        report = self.read_json(v2_report)
        report['routing_conflicts'] = None
        self.write_json(v2_report, report)

        status = self.publish(path)
        self.assertTrue(status['publish']['success'])
        self.assertEqual(status['shadowrocket_ai']['exit_code'], 0)
        self.assertEqual(status['v2rayn']['exit_code'], 0)
        for name in ('Shadowrocket_Johnshall_AI.conf', 'v2rayN_Johnshall_AI.json'):
            self.assertIn(name, status['publish']['changed_files'])
        self.assertIn('Invalid AI candidate list', status['ai_review_error'])
        self.assertIn('Missing or invalid', status['routing_review_error'])
        self.assertNotIn('data/ai-review-notifications.json', status['publish']['changed_files'])
        self.assertNotIn('data/routing-conflicts.json', status['publish']['changed_files'])
        message = self.notify(path)
        self.assertIn('部分成功', message)
        self.assertIn('合并审核队列更新失败', message)
        self.assertIn('冲突审核状态更新失败', message)
        self.assertIn('冲突审核状态更新失败', (self.tmp/'summary.md').read_text(encoding='utf-8'))
        check = self.command(sys.executable, '-B', 'scripts/publish_dual.py',
                             '--status-file', str(path), '--check', ok=False)
        self.assertEqual(check.returncode, 1)

    def test_build_publish_notify_replay_partial_and_concurrent_receipt(self):
        first=self.build_pair('first',docs=True)
        status=self.publish(first)
        self.assertTrue(status['publish']['success'])
        self.assertIn('v2rayN_Johnshall_AI.json',status['publish']['changed_files'])
        self.assertIn('data/ai-official-docs.json',status['publish']['changed_files'])
        shadow=self.remote_text('Shadowrocket_Johnshall_AI.conf')
        self.assertIn('DOMAIN-SUFFIX,openai.com,Fixture AI',shadow)
        self.assertEqual(status['routing_review']['count'],1)
        self.assertEqual(len(status['openai_review']['new_candidates']),1)
        self.assertTrue(status['approved_dependency_review']['alerts'])
        self.notify(first,fail=True)
        self.assertNotEqual(self.command('git','--git-dir='+str(self.remote),'cat-file','-e',
                           'refs/heads/main:data/approved-dependency-notifications.json',ok=False).returncode,0)
        self.assertEqual(json.loads(self.remote_text('data/review-notifications.json'))['sent'],{})
        self.notify(first)
        self.receipts(first)
        self.assertIn('DOMAIN-SUFFIX,fixture-vendor.example',
                      json.loads(self.remote_text('data/review-notifications.json'))['sent'])
        self.assertEqual(len(json.loads(self.remote_text('data/routing-conflicts.json'))['delivered']),1)
        self.assertTrue(json.loads(self.remote_text('data/ai-review-notifications.json'))['sent'])
        self.assertTrue(json.loads(self.remote_text('data/approved-dependency-notifications.json'))['sent'])

        repeat=self.build_pair('repeat')
        status=self.publish(repeat)
        self.assertEqual(status['publish']['state'],'unchanged')
        self.assertFalse(status['routing_review']['alert'])
        self.assertEqual(status['openai_review']['new_candidates'],[])
        self.assertEqual(status['ai_review']['alerts'],[])
        self.assertEqual(status['approved_dependency_review']['alerts'],[])
        self.notify(repeat)
        self.receipts(repeat)

        partial=self.build_pair('partial',shadow_bad=True,v2_extra=True)
        status=self.publish(partial)
        self.assertTrue(status['publish']['success'])
        self.assertNotEqual(status['shadowrocket_ai']['exit_code'],0)
        self.assertEqual(self.remote_text('Shadowrocket_Johnshall_AI.conf'),shadow)
        self.assertEqual(status['openai_review']['fresh_clients'],['v2rayn'])
        new='DOMAIN-SUFFIX,v2-only-new.example'
        self.assertEqual([x['rule'] for x in status['openai_review']['new_candidates']],[new])
        self.assertIn('部分成功',self.notify(partial))

        # Another local clone advances main after Telegram success. The
        # receipt push must not overwrite it or consume the unpushed alert.
        peer=self.tmp/'peer'
        self.command('git','clone','--branch','main',str(self.remote),str(peer))
        self.command('git','config','user.name','Peer',cwd=peer)
        self.command('git','config','user.email','peer@example.test',cwd=peer)
        (peer/'peer-note.txt').write_text('concurrent update\n',encoding='utf-8')
        self.command('git','add','peer-note.txt',cwd=peer)
        self.command('git','commit','-m','concurrent update',cwd=peer)
        self.command('git','push','origin','HEAD:main',cwd=peer)
        self.assertNotEqual(self.receipts(partial,ok=False).returncode,0)
        self.assertNotIn(new,json.loads(self.remote_text('data/review-notifications.json'))['sent'])
        self.assertEqual(self.publish(partial)['publish']['state'],'stale')
        self.assertEqual(self.remote_text('peer-note.txt'),'concurrent update\n')
        self.command('git','fetch','origin','refs/heads/main')
        self.command('git','reset','--hard','FETCH_HEAD')
        recovery=self.build_pair('recovery',v2_extra=True)
        status=self.publish(recovery)
        self.assertTrue(status['publish']['success'])
        self.assertEqual([x['rule'] for x in status['openai_review']['new_candidates']],[new])
        self.notify(recovery)
        self.receipts(recovery)
        self.assertIn(new,json.loads(self.remote_text('data/review-notifications.json'))['sent'])

if __name__=='__main__':
    unittest.main()
