import sys
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

    def test_dependency_group_classification(self):
        self.assertEqual(test_groups.group_for('test_v2rayn.SafetyTests.test_no_change_no_commit'), 'shared')
        self.assertEqual(test_groups.group_for('test_release_remediation.PublishedBaselineTests.test_shadow_v2_auxiliary_tamper_is_detected'), 'shadowrocket')
        self.assertEqual(test_groups.group_for('test_release_remediation.PublishedBaselineTests.test_v2_missing_fields'), 'v2rayn')
        self.assertEqual(test_groups.group_for('test_ai_docs.OfficialDocsAuditTests.test_bad_docs_never_publish'), 'docs')

if __name__ == '__main__':
    unittest.main()
