#!/usr/bin/env python3
"""Stage only validated artifacts, push once, and record real publication status."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess

from release_integrity import SHADOW_AI_FILES, V2_FILES, validate_release
import ai_review_delivery
REVIEW_FILES = ('config/review-decisions.json',)
AI_REVIEW_FILES = ('data/ai-review-queue.md', 'data/ai-review-notifications.json')
DOC_FILES = ('data/ai-official-docs.json', 'data/ai-docs-review.md')


def git(*args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(['git', *args], text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f'git {args[0]} failed: {result.stderr.strip()[-500:]}')
    return result


def write(path: Path, status: dict) -> None:
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def remote_head() -> str:
    rows = git('ls-remote', '--exit-code', 'origin', 'refs/heads/main').stdout.split()
    if not rows:
        raise RuntimeError('Remote main not found')
    return rows[0]


def publish(path: Path) -> None:
    status = json.loads(path.read_text(encoding='utf-8'))
    try:
        if os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_REF') != 'refs/heads/main':
            raise RuntimeError('Refusing publish outside refs/heads/main')
        build_head = git('rev-parse', 'HEAD').stdout.strip()
        if remote_head() != build_head:
            status['publish'] = {'success': False, 'state': 'stale',
                                 'error': 'main advanced before publication; rebuild from the current remote main'}
            return
        files = list(REVIEW_FILES)
        ok = {key: (status.get(key, {}).get('exit_code') == 0)
              for key in ('shadowrocket_ai', 'v2rayn')}
        verified_reports = {}
        for key, owned in (('shadowrocket_ai', SHADOW_AI_FILES), ('v2rayn', V2_FILES)):
            if not ok[key]:
                continue
            try:
                verified_reports[key] = validate_release(key, status)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                status[key] = {'exit_code': 1, 'error': 'Release verification failed: ' + str(exc)}
                ok[key] = False
                print(f'::error::{key}: {status[key]["error"]}')
            else:
                files += owned
        # The shared review queue has independent ownership.
        review_reports = {k: v for k, v in verified_reports.items()
                          if isinstance(v.get('ai_review_candidates'), list)}
        if review_reports:
            try:
                status['ai_review'] = ai_review_delivery.prepare(review_reports)
                files += AI_REVIEW_FILES
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                status['ai_review_error'] = str(exc)
                print('::warning::AI review queue not updated: ' + str(exc))
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
        # Do not claim an unchanged release against a superseded checkout.
        if remote_head() != build_head:
            status['publish'] = {'success': False, 'state': 'stale',
                                 'error': 'main advanced during release verification; rebuild required'}
            return
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
        try:
            git('push', 'origin', 'HEAD:main')
        except RuntimeError as exc:
            # Retry only a clearly rejected non-fast-forward, not an
            # uncertain push that may already have reached the server.
            if ('non-fast-forward' in str(exc) or 'fetch first' in str(exc)) and remote_head() not in (build_head, commit):
                status['publish'] = {'success': False, 'state': 'stale',
                                     'error': 'main advanced during push; rebuild required'}
                return
            raise
        try:
            remote = remote_head()
        except (RuntimeError, OSError, IndexError) as exc:
            status['publish'] = {'success': False, 'state': 'pushed_unverified',
                                 'commit': commit, 'changed_files': changed_files,
                                 'error': 'Push succeeded but remote head could not be read: ' + str(exc)}
            return
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
                        remote = remote_head()
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
    if status.get('ai_review_error'):
        failed.append('ai_review')
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
