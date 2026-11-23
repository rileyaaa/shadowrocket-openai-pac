#!/usr/bin/env python3
"""Independently run the two builders; never conceal either exit status."""
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
    status = {'shadowrocket': execute('Shadowrocket build',
               [sys.executable, 'scripts/build.py', '--report-file', str(legacy_report)])}
    tests = execute('v2rayN independent unit tests',
                    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_v2rayn.py', '-v'])
    if tests['exit_code'] != 0:
        status['v2rayn'] = {'exit_code': tests['exit_code'],
                            'error': 'v2rayN tests failed: ' + tests['error']}
    else:
        status['v2rayn'] = execute('v2rayN independent build',
               [sys.executable, 'scripts/build_v2rayn.py', '--report-file', str(v2_report)])
    status['reports'] = {'shadowrocket': str(legacy_report), 'v2rayn': str(v2_report)}
    status['publish'] = {'success': False, 'state': 'pending'}
    status_path = args.work_dir / 'dual-status.json'
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Build status: Shadowrocket={status["shadowrocket"]["exit_code"]}, '
          f'v2rayN={status["v2rayn"]["exit_code"]}; saved {status_path}')
    return 0  # Publish & notification still run; final checker propagates failures.


if __name__ == '__main__':
    raise SystemExit(main())
