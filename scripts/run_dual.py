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
    docs_report = args.work_dir / 'ai-docs-audit-report.json'
    status_path = args.work_dir / 'dual-status.json'
    for path in (v2_report, ai_report, docs_report, status_path):
        path.unlink(missing_ok=True)
    tests = {group: execute('Offline regression: ' + group,
                            [sys.executable, '-B', 'scripts/test_groups.py', group])
             for group in ('shared', 'shadowrocket', 'v2rayn', 'docs')}
    status = {'tests': tests}
    for key, group, script, report in (
        ('shadowrocket_ai', 'shadowrocket', 'build_ai_shadowrocket.py', ai_report),
        ('v2rayn', 'v2rayn', 'build_v2rayn.py', v2_report),
    ):
        failure = next((tests[name] for name in ('shared', group) if tests[name]['exit_code']), None)
        if failure:
            status[key] = {'exit_code': failure['exit_code'],
                           'error': 'Relevant offline regression failed: ' + failure['error']}
        else:
            status[key] = execute('Independent build: ' + key,
                                  [sys.executable, 'scripts/' + script, '--report-file', str(report)])
    if tests['docs']['exit_code']:
        status['official_docs'] = {'exit_code': tests['docs']['exit_code'],
                                   'error': 'Official documentation regression failed: ' + tests['docs']['error']}
    else:
        status['official_docs'] = execute('Weekly official Gemini / Claude doc advisory',
            [sys.executable, 'scripts/audit_ai_docs.py', '--report-file', str(docs_report),
             '--shadow-report', str(ai_report), '--v2-report', str(v2_report)])
    status['reports'] = {'shadowrocket_ai': str(ai_report),
                         'v2rayn': str(v2_report), 'official_docs': str(docs_report)}
    status['publish'] = {'success': False, 'state': 'pending'}
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Build status: Shadowrocket AI={status["shadowrocket_ai"]["exit_code"]}, '
          f'v2rayN={status["v2rayn"]["exit_code"]}; saved {status_path}')
    return 0  # Publish & notification still run; final checker propagates failures.


if __name__ == '__main__':
    raise SystemExit(main())
