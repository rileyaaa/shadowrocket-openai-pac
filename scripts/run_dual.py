#!/usr/bin/env python3
"""Independently run only the AI Shadowrocket and v2rayN subscription builds."""
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
    v2_report = args.work_dir / 'v2rayn-report.json'
    ai_report = args.work_dir / 'shadowrocket-ai-report.json'
    original_cases = ('test_build.py', 'test_hardening.py',
                      'test_review_queue.py', 'test_sync_reporting.py')
    original_results = [execute(f'Original test suite {pattern}',
        [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
         '-p', pattern, '-v']) for pattern in original_cases]
    # Continue testing the legacy parser that AI builders use as a library.
    # Its tests protect Shadowrocket AI but do not prevent v2rayN publishing.
    status = {}
    failed_original = [result for result in original_results if result['exit_code']]
    ai_source_tests = execute('Shared Gemini and Claude source tests',
        [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
         '-p', 'test_ai_services.py', '-v'])
    shadow_tests = execute('Shadowrocket-specific routing tests',
        [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
         '-p', 'test_ai_shadowrocket.py', '-v'])
    if ai_source_tests['exit_code'] or shadow_tests['exit_code'] or failed_original:
        failure = next(result for result in (ai_source_tests, shadow_tests, *failed_original)
                       if result['exit_code'])
        status['shadowrocket_ai'] = {'exit_code': failure['exit_code'],
            'error': 'Shadowrocket legacy parser / AI rules tests failed: ' + failure['error']}
    else:
        status['shadowrocket_ai'] = execute('Independent AI-enhanced Shadowrocket build',
            [sys.executable, 'scripts/build_ai_shadowrocket.py', '--report-file', str(ai_report)])
    tests = execute('v2rayN independent unit tests',
                    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_v2rayn.py', '-v'])
    if tests['exit_code'] != 0 or ai_source_tests['exit_code'] != 0:
        status['v2rayn'] = {'exit_code': tests['exit_code'] or ai_source_tests['exit_code'],
                            'error': 'v2rayN / shared AI rules tests failed: ' +
                            (tests['error'] or ai_source_tests['error'])}
    else:
        status['v2rayn'] = execute('v2rayN independent build',
               [sys.executable, 'scripts/build_v2rayn.py', '--report-file', str(v2_report)])
    # Advisory weekly check runs in this SAME existing daily workflow. On
    # other days it skips without network access. Failure never blocks routes.
    docs_report = args.work_dir / 'ai-docs-audit-report.json'
    status['official_docs'] = execute('Weekly official Gemini / Claude doc advisory',
        [sys.executable, 'scripts/audit_ai_docs.py', '--report-file', str(docs_report)])
    status['reports'] = {'shadowrocket_ai': str(ai_report),
                         'v2rayn': str(v2_report), 'official_docs': str(docs_report)}
    status['publish'] = {'success': False, 'state': 'pending'}
    status_path = args.work_dir / 'dual-status.json'
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Build status: Shadowrocket AI={status["shadowrocket_ai"]["exit_code"]}, '
          f'v2rayN={status["v2rayn"]["exit_code"]}; saved {status_path}')
    return 0  # Publish & notification still run; final checker propagates failures.


if __name__ == '__main__':
    raise SystemExit(main())
