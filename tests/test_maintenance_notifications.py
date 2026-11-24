import sys
import json
import os
import tempfile
from unittest.mock import patch
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import notify_combined as notify
import test_groups

class MaintenanceNotificationTests(unittest.TestCase):
    def test_openai_details_and_review_dates_in_one_message(self):
        status = {'shadowrocket_ai': {'exit_code': 0}, 'v2rayn': {'exit_code': 1},
                  'publish': {'success': True, 'state': 'unchanged'}}
        report = {'build_success': True, 'config_changed': False, 'statistics': {'johnshall_lines': 80000},
                  'changed_sources': ['voice'], 'review_decisions_changed': True,
                  'auto_added': ['IP-CIDR,8.8.8.8/32'], 'auto_removed': [],
                  'new_excluded_candidates': [{'rule': 'DOMAIN,new.example', 'sources': ['v2fly']}],
                  'review_due_candidates': [{'rule': 'DOMAIN,old.example', 'reviewed_at': '2026-01-01',
                                              'review_due_on': '2026-07-01'}]}
        msg = notify.emit_message(status, report, None, when='2026-11-24', event='schedule',
                                  run_url='https://github.com/example/actions/runs/1')
        for value in ('new.example', 'old.example', '2026-07-01', '人工审核记录文件已变更',
                      '8.8.8.8/32', 'OpenAI Voice'):
            self.assertIn(value, msg)

    def test_long_report_does_not_hide_review_alerts_behind_statistics(self):
        header = ['header','time','event','overall','publication']
        details = header + ['statistics ' + 'x'*1000]*8
        alerts = ['🔔 异常与人工审核','OpenAI 本次提醒：3',
                  'Gemini/Claude 本次需提醒：4','前置拦截冲突：2',
                  '已批准共享依赖待复审：8','本次复审提醒：8']
        url = 'https://github.com/example/actions/runs/1'
        result = notify.fit_message(details,alerts,url)
        self.assertLessEqual(len(result),3900)
        for line in header + alerts + [url]:
            self.assertIn(line,result)
        self.assertIn('省略',result)
        # A flood of examples must not hide the category summaries either.
        result = notify.fit_message(details,alerts + ['· '+ 'x'*500]*20,url)
        self.assertLessEqual(len(result),3900)
        for line in alerts + [url]:
            self.assertIn(line,result)

    def test_advisory_failure_does_not_report_unqualified_success(self):
        status = {'shadowrocket_ai': {'exit_code':0}, 'v2rayn': {'exit_code':0},
                  'publish': {'success':True,'state':'unchanged'},
                  'approved_dependency_review_error': 'fixture invalid ledger'}
        report = {'build_success':True,'config_changed':False,'statistics':{'routing_objects':1}}
        msg = notify.emit_message(status,report,report,when='2026-11-24',event='schedule',run_url='')
        self.assertIn('总体状态：订阅成功（共享依赖复审告警）',msg)
        status['official_docs'] = {'exit_code':1}
        msg = notify.emit_message(status,report,report,when='2026-11-24',event='schedule',run_url='')
        self.assertIn('总体状态：订阅成功（文档检查、共享依赖复审告警）',msg)

    def test_actions_summary_has_untruncated_statistics(self):
        status = {'shadowrocket_ai': {'exit_code':0}, 'v2rayn': {'exit_code':0},
                  'publish': {'success':True,'state':'unchanged'}}
        report = {'build_success':True,'config_changed':False,
                  'statistics':{'routing_objects':131,'block_rules':52915},
                  'changed_sources':['fixture-'+'x'*100]*55}
        kwargs = {'when':'2026-11-24','event':'schedule','run_url':'https://github.com/example/actions/runs/1'}
        short = notify.emit_message(status,report,report,**kwargs)
        full = notify.emit_message(status,report,report,limit=None,**kwargs)
        self.assertLessEqual(len(short),3900)
        self.assertGreater(len(full),3900)
        self.assertIn('拦截规则：52915',full)
        self.assertNotIn('部分详情省略',full)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root/'report.json'
            path.write_text(json.dumps(report),encoding='utf-8')
            status['reports'] = {'shadowrocket_ai':str(path),'v2rayn':str(path)}
            state = root/'status.json'
            state.write_text(json.dumps(status),encoding='utf-8')
            summary = root/'summary.md'
            env = {'TELEGRAM_BOT_TOKEN':'fixture','TELEGRAM_CHAT_ID':'fixture',
                   'GITHUB_REPOSITORY':'example/test','GITHUB_RUN_ID':'1',
                   'GITHUB_STEP_SUMMARY':str(summary)}
            with patch.dict(os.environ,env), patch.object(sys,'argv',[
                    'notify_combined.py','--status-file',str(state)]), patch.object(notify.original,'send') as send:
                self.assertEqual(notify.main(),0)
            self.assertLessEqual(len(send.call_args.args[2]),3900)
            self.assertIn('拦截规则：52915',summary.read_text(encoding='utf-8'))
            self.assertNotIn('部分详情省略',summary.read_text(encoding='utf-8'))

    def test_dependency_group_classification(self):
        self.assertEqual(test_groups.group_for('test_v2rayn.SafetyTests.test_no_change_no_commit'), 'shared')
        self.assertEqual(test_groups.group_for('test_release_remediation.PublishedBaselineTests.test_shadow_v2_auxiliary_tamper_is_detected'), 'shadowrocket')
        self.assertEqual(test_groups.group_for('test_release_remediation.PublishedBaselineTests.test_v2_missing_fields'), 'v2rayn')
        self.assertEqual(test_groups.group_for('test_ai_docs.OfficialDocsAuditTests.test_bad_docs_never_publish'), 'docs')

    def test_real_notification_entrypoint_persists_only_delivered_receipts(self):
        import ai_review_delivery as delivery
        import review_queue
        candidate = {'service': 'gemini', 'rule': 'DOMAIN,new.example',
                     'sources': ['fixture']}
        policy = {'version': 1, 'default_review_months': 6,
                  'reminder_interval_days': 7, 'rejected_rules': []}
        state, merged = delivery.merge_reports(delivery.empty_state(), {
            'v2rayn': {'ai_review_candidates': [candidate]}}, policy)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ai_state = root / 'ai.json'
            openai_state = root / 'openai.json'
            status_file = root / 'status.json'
            v2_report = root / 'v2.json'
            summary = root / 'summary.md'
            ai_state.write_text(json.dumps(state), encoding='utf-8')
            openai_state.write_text(json.dumps(review_queue.empty_delivery()), encoding='utf-8')
            v2_report.write_text(json.dumps({'build_success': True, 'config_changed': False,
                'statistics': {'routing_objects': 1}}), encoding='utf-8')
            status_file.write_text(json.dumps({
                'shadowrocket_ai': {'exit_code': 1}, 'v2rayn': {'exit_code': 0},
                'reports': {'v2rayn': str(v2_report)}, 'ai_review': merged,
                'publish': {'success': True, 'state': 'published'}}), encoding='utf-8')
            argv = ['notify_combined.py', '--status-file', str(status_file),
                    '--review-state-file', str(openai_state), '--ai-review-state-file', str(ai_state)]
            env = {'TELEGRAM_BOT_TOKEN': 'fixture', 'TELEGRAM_CHAT_ID': 'fixture',
                   'GITHUB_REPOSITORY': 'example/test', 'GITHUB_RUN_ID': '1',
                   'GITHUB_STEP_SUMMARY': str(summary)}
            with patch.dict(os.environ, env), patch.object(sys, 'argv', argv):
                with patch.object(notify.original, 'send', side_effect=RuntimeError('fixture')):
                    self.assertEqual(notify.main(), 1)
                self.assertEqual(delivery.read_state(ai_state)['sent'], {})
                with patch.object(notify.original, 'send') as send:
                    self.assertEqual(notify.main(), 0)
                    send.assert_called_once()
                self.assertIn('gemini|DOMAIN,new.example', delivery.read_state(ai_state)['sent'])
                self.assertEqual(json.loads(status_file.read_text())['receipt_files'], [str(ai_state)])
                self.assertIn('DOMAIN,new.example', summary.read_text())
                self.assertEqual(json.loads(openai_state.read_text()), review_queue.empty_delivery())

if __name__ == '__main__':
    unittest.main()
