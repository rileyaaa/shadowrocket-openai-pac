"""Run every discovered regression in its dependency group."""
from __future__ import annotations
import argparse
import unittest

GROUPS = ('shared', 'shadowrocket', 'v2rayn', 'docs')
SHADOW_MODULES = {'test_build', 'test_hardening', 'test_review_queue',
                  'test_sync_reporting', 'test_ai_shadowrocket'}
SHARED_V2_PREFIXES = ('test_publish', 'test_publisher', 'test_telegram',
                      'test_single_telegram', 'test_both_success',
                      'test_no_change', 'test_git_push', 'test_only_two', 'test_atomic')

def group_for(test_id: str) -> str:
    parts = test_id.split('.')
    module, name = parts[0], parts[-1]
    if module == 'unittest':
        # Failed imports must never be silently omitted.
        return 'shared'
    if module in SHADOW_MODULES:
        return 'shadowrocket'
    if module == 'test_ai_docs':
        return 'docs'
    if module == 'test_routing_conflicts':
        return 'v2rayn'
    if module == 'test_v2rayn':
        return 'shared' if name.startswith(SHARED_V2_PREFIXES) else 'v2rayn'
    if module == 'test_release_remediation':
        if name.startswith('test_shadow'):
            return 'shadowrocket'
        if name.startswith(('test_v2_', 'test_only_approved_bitbrowser', 'test_unverified_process')):
            return 'v2rayn'
    return 'shared'

def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('group', choices=GROUPS)
    args = p.parse_args()
    tests = [test for test in flatten(unittest.defaultTestLoader.discover('tests'))
             if group_for(test.id()) == args.group]
    if not tests:
        print('No tests discovered for group: ' + args.group)
        return 1
    return 0 if unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(tests)).wasSuccessful() else 1

if __name__ == '__main__':
    raise SystemExit(main())
