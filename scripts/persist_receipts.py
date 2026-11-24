#!/usr/bin/env python3
"""Persist only acknowledged review receipts, with a real remote-head check."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
from publish_dual import git, remote_head

ALLOWED = {'data/review-notifications.json', 'data/ai-review-notifications.json',
           'data/routing-conflicts.json'}


def persist(status_path):
    state = json.loads(status_path.read_text(encoding='utf-8'))
    if state.get('publish', {}).get('success') is not True:
        raise ValueError('Refusing receipt write after unverified publication')
    if os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('Refusing receipt write outside main')
    paths = state.get('receipt_files', [])
    if not isinstance(paths, list) or any(not isinstance(p, str) or p not in ALLOWED for p in paths):
        raise ValueError('Unexpected receipt path')
    paths = sorted(set(paths))
    if any(not Path(p).is_file() for p in paths):
        raise ValueError('Acknowledged receipt file missing')
    head = git('rev-parse', 'HEAD').stdout.strip()
    if paths and remote_head() != head:
        raise ValueError('Remote main advanced; retain remote receipts and retry next sync')
    git('reset', '--mixed', '--quiet')
    if paths:
        git('add', '--', *paths)
    changed = git('diff', '--cached', '--name-only').stdout.splitlines()
    if not set(changed) <= set(paths):
        raise ValueError('Unexpected staged path in receipt commit')
    if not changed:
        print('No review receipt changes.')
        return
    if remote_head() != head:
        raise ValueError('Remote main advanced before receipt commit')
    git('config', 'user.name', 'github-actions[bot]')
    git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    git('commit', '-m', 'chore: record delivered review reminders')
    commit = git('rev-parse', 'HEAD').stdout.strip()
    git('push', 'origin', 'HEAD:main')
    if remote_head() != commit:
        raise RuntimeError('Receipt push succeeded but remote head changed; verify next sync')
    print('Published verified review receipt commit ' + commit)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--status-file', required=True, type=Path)
    args = p.parse_args()
    try:
        persist(args.status_file)
        return 0
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print('::error::Review receipt persistence failed: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
