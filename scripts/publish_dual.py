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
import openai_review_delivery
import routing_conflicts
import approved_dependency_review
import review_queue
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
        files = []
        ok = {key: (status.get(key, {}).get('exit_code') == 0)
              for key in ('shadowrocket_ai', 'v2rayn')}
        verified_reports = {}
        for key, owned in (('shadowrocket_ai', SHADOW_AI_FILES), ('v2rayn', V2_FILES)):
            if not ok[key]:
                continue
            try:
                verified_reports[key] = validate_release(key, status)
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                status[key] = {'exit_code': 1, 'error': 'Release verification failed: ' + str(exc)}
                ok[key] = False
                print(f'::error::{key}: {status[key]["error"]}')
            else:
                files += owned
        # A workflow_dispatch rejection is a pending local edit until at least
        # one client has actually passed release verification. If neither
        # passed, keep the published policy and both subscriptions untouched.
        if verified_reports:
            files += REVIEW_FILES
        openai_reports = {k: v for k, v in verified_reports.items()
                          if isinstance(v.get('openai_observation'), dict)}
        if openai_reports:
            try:
                status['openai_review'] = openai_review_delivery.prepare(openai_reports)
                files += openai_review_delivery.FILES
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                status['openai_review_error'] = str(exc)
                print('::warning::OpenAI review queue not updated: ' + str(exc))
        # The shared review queue has independent ownership. A missing list
        # in a verified build report is an error, not an absent client.
        # Let the existing candidate validator reject it before writing.
        if verified_reports:
            try:
                status['ai_review'] = ai_review_delivery.prepare(verified_reports)
                files += AI_REVIEW_FILES
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                status['ai_review_error'] = str(exc)
                print('::warning::AI review queue not updated: ' + str(exc))
        if 'v2rayn' in verified_reports:
            try:
                conflict_report = verified_reports['v2rayn'].get('routing_conflicts')
                if not isinstance(conflict_report, dict) or 'pairs' not in conflict_report:
                    raise ValueError('Missing or invalid v2rayN routing conflict report')
                policy, _ = review_queue.load_policy(Path('config/review-decisions.json'), review_queue.today())
                status['routing_review'] = routing_conflicts.prepare(
                    conflict_report, Path(routing_conflicts.STATE), interval=policy['reminder_interval_days'])
                files.append(routing_conflicts.STATE)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                status['routing_review_error'] = str(exc)
                print('::warning::Routing conflict review not updated: ' + str(exc))
        # Existing shared-dependency approvals are reviewed on a separate
        # calendar; this advisory never grants, removes or blocks routes.
        if any(verified_reports.values()):
            try:
                status['approved_dependency_review'] = approved_dependency_review.prepare()
            except (OSError, ValueError, TypeError, KeyError) as exc:
                status['approved_dependency_review_error'] = str(exc)
                print('::warning::Approved dependency review unavailable: ' + str(exc))
        # Official docs remain advisory. A skipped or incomplete report
        # must never stage partially updated advisory files.
        if status.get('official_docs', {}).get('exit_code') == 0:
            from audit_ai_docs import validate_advisory
            try:
                files += validate_advisory(status, DOC_FILES)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                status['official_docs'] = {'exit_code': 1, 'error': str(exc)}
                print('::warning::Official docs advisory not published: ' + str(exc))
        # A previous failed commit or user-staged file must not be carried over.
        git('reset', '--mixed', '--quiet')
        if files:
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
        if not verified_reports and not changed_files:
            status['publish'] = {'success': False, 'state': 'not-published',
                                 'changed_files': [], 'commit': None,
                                 'error': 'Neither client passed release verification; existing subscriptions and pending manual policy retained on remote'}
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
    if status.get('openai_review_error'):
        failed.append('openai_review')
    if status.get('routing_review_error'):
        failed.append('routing_review')
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
