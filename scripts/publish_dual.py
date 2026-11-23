#!/usr/bin/env python3
"""Stage only validated artifacts, push once, and record real publication status."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess

SHADOW_FILES = ('Shadowrocket_Johnshall_OpenAI.conf', 'rules', 'data/sources.json',
                'data/review-queue.md', 'data/review-notifications.json')
SHADOW_AI_FILES = ('Shadowrocket_Johnshall_AI.conf', 'data/ai-shadowrocket-sources.json',
                   'data/ai-review-queue.md')
V2_FILES = ('v2rayN_Johnshall_OpenAI.json', 'data/v2rayn-sources.json')
REVIEW_FILES = ('config/review-decisions.json',)
DOC_FILES = ('data/ai-official-docs.json', 'data/ai-docs-review.md')


def git(*args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(['git', *args], text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f'git {args[0]} failed: {result.stderr.strip()[-500:]}')
    return result


def write(path: Path, status: dict) -> None:
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def publish(path: Path) -> None:
    status = json.loads(path.read_text(encoding='utf-8'))
    try:
        files = list(REVIEW_FILES)
        ok = {key: (status.get(key, {}).get('exit_code') == 0)
              for key in ('shadowrocket', 'shadowrocket_ai', 'v2rayn')}
        if ok['shadowrocket']:
            files += SHADOW_FILES
        if ok['shadowrocket_ai']:
            files += SHADOW_AI_FILES
        if ok['v2rayn']:
            files += V2_FILES
        # Advisory docs snapshot only when both official pages were verified.
        if status.get('official_docs', {}).get('exit_code') == 0:
            files += [f for f in DOC_FILES if Path(f).is_file()]
        git('add', '-A', '--', *files)
        changed_files = git('diff', '--cached', '--name-only').stdout.splitlines()
        if not changed_files:
            status['publish'] = {'success': True, 'state': 'unchanged',
                                 'changed_files': [], 'commit': None}
            write(path, status)
            print('No changes to publish.')
            return
        git('config', 'user.name', 'github-actions[bot]')
        git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
        git('commit', '-m', 'chore: sync validated Shadowrocket and AI-enhanced v2rayN routes')
        commit = git('rev-parse', 'HEAD').stdout.strip()
        git('push', 'origin', 'HEAD:main')
        remote = git('ls-remote', 'origin', 'refs/heads/main').stdout.split()[0]
        if remote != commit:
            raise RuntimeError('Git push verification mismatch: remote main is not the published commit')
        status['publish'] = {'success': True, 'state': 'published',
                             'commit': commit, 'changed_files': changed_files}
        print(f'Published commit {commit}: {changed_files}')
    except (RuntimeError, OSError, IndexError) as exc:
        status['publish'] = {'success': False, 'state': 'failed',
                             'error': str(exc)}
        print(f'::error::Publication failed: {exc}')
    finally:
        write(path, status)


def check(path: Path) -> int:
    if not path.exists():
        print('::error::No build status was produced.')
        return 1
    status = json.loads(path.read_text(encoding='utf-8'))
    failed = [key for key in ('shadowrocket', 'v2rayn', 'shadowrocket_ai')
              if (key in status or key != 'shadowrocket_ai') and
              status.get(key, {}).get('exit_code') != 0]
    if not status.get('publish', {}).get('success'):
        failed.append('publish')
    if failed:
        print(f'::error::Failed tasks: {", ".join(failed)}')
        return 1
    print('All present builds validated; publication successful or unchanged.')
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--status-file', required=True, type=Path)
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    if args.check:
        return check(args.status_file)
    publish(args.status_file)
    return 0  # Report failures after Telegram via --check.


if __name__ == '__main__':
    raise SystemExit(main())
