#!/usr/bin/env python3
"""Stage only validated artifacts, push once, and record real publication status."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess

# Only TWO published client subscriptions. The retired builder remains a pure
# parser library; its OpenAI review metadata is maintained by Shadowrocket AI.
SHADOW_AI_FILES = ('Shadowrocket_Johnshall_AI.conf',
                   'data/ai-shadowrocket-sources.json', 'data/ai-review-queue.md',
                   'rules/johnshall-apple-news.list', 'rules/openai-auto.list',
                   'data/sources.json', 'data/review-queue.md',
                   'data/review-notifications.json')
V2_FILES = ('v2rayN_Johnshall_AI.json', 'data/v2rayn-sources.json')
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
        if os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_REF') != 'refs/heads/main':
            raise RuntimeError('Refusing publish outside refs/heads/main')
        files = list(REVIEW_FILES)
        ok = {key: (status.get(key, {}).get('exit_code') == 0)
              for key in ('shadowrocket_ai', 'v2rayn')}
        if ok['shadowrocket_ai']:
            files += SHADOW_AI_FILES
        if ok['v2rayn']:
            files += V2_FILES
        # Advisory docs snapshot only when both official pages were verified.
        if status.get('official_docs', {}).get('exit_code') == 0:
            files += [f for f in DOC_FILES if Path(f).is_file()]
        # A previous failed commit or user-staged file must not be carried over.
        git('reset', '--mixed', '--quiet')
        git('add', '-A', '--', *files)
        changed_files = git('diff', '--cached', '--name-only').stdout.splitlines()
        allowed = set(files)
        unexpected = sorted(set(changed_files) - allowed)
        if unexpected:
            raise RuntimeError('Unexpected staged publish paths: ' + ', '.join(unexpected))
        if not changed_files:
            status['publish'] = {'success': True, 'state': 'unchanged',
                                 'changed_files': [], 'commit': None}
            write(path, status)
            print('No changes to publish.')
            return
        git('config', 'user.name', 'github-actions[bot]')
        git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
        git('commit', '-m', 'chore: sync two verified AI subscriptions')
        commit = git('rev-parse', 'HEAD').stdout.strip()
        git('push', 'origin', 'HEAD:main')
        remote = git('ls-remote', 'origin', 'refs/heads/main').stdout.split()[0]
        if remote != commit:
            # A concurrent fast-forward can move remote main immediately after
            # our successful push. The new SHA is usually NOT locally present
            # in actions/checkout's shallow clone, so fetch before merge-base.
            try:
                verified = False
                for depth in (128, 512):
                    git('fetch', '--no-tags', f'--depth={depth}',
                        'origin', 'refs/heads/main')
                    fetched = git('rev-parse', 'FETCH_HEAD').stdout.strip()
                    if fetched != remote:
                        remote = git('ls-remote', 'origin', 'refs/heads/main').stdout.split()[0]
                        continue
                    ancestor = subprocess.run(
                        ['git', 'merge-base', '--is-ancestor', commit, 'FETCH_HEAD'],
                        capture_output=True, text=True)
                    if ancestor.returncode == 0:
                        verified = True
                        break
                    if ancestor.returncode not in (1,):
                        raise RuntimeError('Cannot check fetched Git ancestry: ' +
                                           ancestor.stderr.strip()[-200:])
                if not verified:
                    raise RuntimeError('Published commit not verified as ancestor of remote main')
            except (RuntimeError, OSError, IndexError) as exc:
                # Push returned success. Do not misreport it as a failed push.
                status['publish'] = {'success': False,
                                     'state': 'pushed_unverified',
                                     'commit': commit,
                                     'changed_files': changed_files,
                                     'error': 'Push succeeded but remote ancestry could not be confirmed: ' + str(exc)}
                print('::warning::' + status['publish']['error'])
                return
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
    failed = [key for key in ('shadowrocket_ai', 'v2rayn')
              if status.get(key, {}).get('exit_code') != 0]
    if not status.get('publish', {}).get('success'):
        failed.append('publish')
    if failed:
        print(f'::error::Failed tasks: {", ".join(failed)}')
        return 1
    print('Both AI subscriptions validated; publication successful or unchanged.')
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
