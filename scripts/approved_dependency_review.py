"""Advisory six-month review of retained shared routing exceptions.

The ledger is deliberately separate from route permission and rejection
policies. A due date never changes a route. Only accepted Telegram reports
with full Actions summaries can acknowledge a reminder.
"""
from __future__ import annotations

from datetime import timedelta
import hashlib
import json
from pathlib import Path
import re
import review_queue as review

ROOT = Path(__file__).resolve().parents[1]
POLICY = 'config/approved-dependency-review.json'
STATE = 'data/approved-dependency-notifications.json'


def validate_policy(policy, on):
    if (not isinstance(policy, dict) or set(policy) != {'version', 'groups'}
            or type(policy['version']) is not int or policy['version'] != 1
            or not isinstance(policy['groups'], list)):
        raise ValueError('Invalid approved-dependency review ledger')
    ids = set()
    for item in policy['groups']:
        if (not isinstance(item, dict)
                or set(item) != {'id', 'scope', 'rules', 'reviewed_at', 'evidence', 'note'}
                or not isinstance(item['id'], str) or not re.fullmatch(r'[a-z0-9-]+', item['id'])
                or item['id'] in ids
                or item['scope'] not in ('openai', 'gemini', 'claude', 'v2rayn_openai', 'bitbrowser')
                or not isinstance(item['rules'], list) or not item['rules']
                or len(set(item['rules'])) != len(item['rules'])):
            raise ValueError('Invalid or duplicate dependency review group')
        ids.add(item['id'])
        for key in ('note', 'evidence'):
            review.nonempty_text(item[key], key)
        for rule in item['rules']:
            review.nonempty_text(rule, 'rule')
        if item['reviewed_at'] is not None and review.parse_date(item['reviewed_at']) > on:
            raise ValueError('Future dependency review date')
    return policy


def read_state(path, on):
    if not path.exists():
        return {'version': 1, 'sent': {}}
    state = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(state, dict) or state.get('version') != 1 or not isinstance(state.get('sent'), dict):
        raise ValueError('Invalid dependency reminder state')
    for key, item in state['sent'].items():
        if (not isinstance(item, dict) or set(item) != {'cycle', 'notified_at'}
                or not isinstance(item['cycle'], str) or not re.fullmatch(r'[0-9a-f]{64}', item['cycle'])
                or review.parse_date(item['notified_at']) > on):
            raise ValueError('Invalid dependency reminder receipt: ' + key)
    return state


def evaluate(policy, state, *, on, months=6, interval=30):
    validate_policy(policy, on)
    review.bounded_int(months, 1, 120, 'months')
    review.bounded_int(interval, 1, 365, 'interval')
    groups, alerts = [], []
    for item in policy['groups']:
        due = review.add_months(review.parse_date(item['reviewed_at']), months) if item['reviewed_at'] else None
        pending = due is None or on >= due
        row = {**item, 'due_on': due.isoformat() if due else None,
               'status': 'initial_review' if due is None else 'due' if pending else 'current'}
        groups.append(row)
        if not pending:
            continue
        cycle = hashlib.sha256(json.dumps([item, row['due_on']], ensure_ascii=False,
                               sort_keys=True).encode()).hexdigest()
        receipt = state['sent'].get(item['id'], {})
        if (receipt.get('cycle') != cycle or
                on >= review.parse_date(receipt['notified_at']) + timedelta(days=interval)):
            alerts.append({**row, 'cycle': cycle})
    return {'groups': groups, 'alerts': alerts,
            'due_count': sum(x['status'] != 'current' for x in groups),
            'months': months, 'interval': interval}


def prepare(root=ROOT, *, on=None):
    on = on or review.today()
    policy = validate_policy(json.loads((root / POLICY).read_text(encoding='utf-8')), on)
    try:
        state = read_state(root / STATE, on)
    except (OSError, ValueError, TypeError):
        print('::warning::Invalid dependency receipt state; retry outstanding reminders')
        state = {'version': 1, 'sent': {}}
    cadence, _ = review.load_policy(root / 'config/review-decisions.json', on)
    return evaluate(policy, state, on=on, months=cadence['default_review_months'],
                    interval=cadence['reminder_interval_days'])


def acknowledge(report, path, *, on=None):
    on = on or review.today()
    try:
        state = read_state(path, on)
    except (OSError, ValueError, TypeError):
        state = {'version': 1, 'sent': {}}
    active = {item['id'] for item in report['groups'] if item['status'] != 'current'}
    state['sent'] = {key: value for key, value in state['sent'].items() if key in active}
    for item in report['alerts']:
        state['sent'][item['id']] = {'cycle': item['cycle'], 'notified_at': on.isoformat()}
    review.write_json(path, state)
