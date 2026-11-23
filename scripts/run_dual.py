#!/usr/bin/env python3
"""Independently run original Shadowrocket, AI Shadowrocket and v2rayN builds."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys


def execute(label: str, command: list[str]) -> dict:
    print(f'::group::{label}', flush=True)
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        print(result.stdout[-12000:])
        print(result.stderr[-12000:], file=sys.stderr)
        return {'exit_code': result.returncode,
                'error': result.stderr.strip()[-1500:] if result.returncode else ''}
    except OSError as exc:
        return {'exit_code': 127, 'error': f'{type(exc).__name__}: {exc}'}
    finally:
        print('::endgroup::', flush=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--work-dir', required=True, type=Path)
    args = p.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    legacy_report = args.work_dir / 'shadowrocket-report.json'
    v2_report = args.work_dir / 'v2rayn-report.json'
    ai_report = args.work_dir / 'shadowrocket-ai-report.json'
    original_cases = ('test_build.py', 'test_hardening.py',
                      'test_review_queue.py', 'test_sync_reporting.py')
    original_results = [execute(f'Original test suite {pattern}',
        [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
         '-p', pattern, '-v']) for pattern in original_cases]
    # Independent tests: an original-suite failure cannot block v2rayN.
    status = {}
    failed_original = [result for result in original_results if result['exit_code']]
    if failed_original:
        status['shadowrocket'] = {
            'exit_code': failed_original[0]['exit_code'],
            'error': 'Original Shadowrocket tests failed: ' + failed_original[0]['error']}
    else:
        status['shadowrocket'] = execute('Shadowrocket build',
            [sys.executable, 'scripts/build.py', '--report-file', str(legacy_report)])
    ai_tests = execute('Gemini and Claude source / Shadowrocket AI unit tests',
        [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
         '-p', 'test_ai_*.py', '-v'])
    if ai_tests['exit_code']:
        status['shadowrocket_ai'] = {'exit_code': ai_tests['exit_code'],
            'error': 'AI rules validation tests failed: ' + ai_tests['error']}
    else:
        status['shadowrocket_ai'] = execute('Independent AI-enhanced Shadowrocket build',
            [sys.executable, 'scripts/build_ai_shadowrocket.py', '--report-file', str(ai_report)])
    tests = execute('v2rayN independent unit tests',
                    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_v2rayn.py', '-v'])
    if tests['exit_code'] != 0 or ai_tests['exit_code'] != 0:
        status['v2rayn'] = {'exit_code': tests['exit_code'] or ai_tests['exit_code'],
                            'error': 'v2rayN / shared AI rules tests failed: ' +
                            (tests['error'] or ai_tests['error'])}
    else:
        status['v2rayn'] = execute('v2rayN independent build',
               [sys.executable, 'scripts/build_v2rayn.py', '--report-file', str(v2_report)])
    # Advisory weekly check runs in this SAME existing daily workflow. On
    # other days it skips without network access. Failure never blocks routes.
    docs_report = args.work_dir / 'ai-docs-audit-report.json'
    status['official_docs'] = execute('Weekly official Gemini / Claude doc advisory',
        [sys.executable, 'scripts/audit_ai_docs.py', '--report-file', str(docs_report)])
    status['reports'] = {'shadowrocket': str(legacy_report),
                         'shadowrocket_ai': str(ai_report), 'v2rayn': str(v2_report),
                         'official_docs': str(docs_report)}
    status['publish'] = {'success': False, 'state': 'pending'}
    status_path = args.work_dir / 'dual-status.json'
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Build status: Shadowrocket={status["shadowrocket"]["exit_code"]}, '
          f'Shadowrocket AI={status["shadowrocket_ai"]["exit_code"]}, '
          f'v2rayN={status["v2rayn"]["exit_code"]}; saved {status_path}')
    return 0  # Publish & notification still run; final checker propagates failures.


if __name__ == '__main__':
    raise SystemExit(main())
