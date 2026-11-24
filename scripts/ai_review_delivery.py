"""Merge verified Gemini/Claude candidate snapshots; never authorize routes."""
from __future__ import annotations
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import ai_services
import review_queue

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'data/ai-review-notifications.json'
QUEUE = ROOT / 'data/ai-review-queue.md'
POLICY = ROOT / 'config/ai-review-decisions.json'
CLIENTS = ('shadowrocket_ai', 'v2rayn')

def empty_state():
    return {'version': 1, 'snapshots': {}, 'sent': {}}

def validate_candidate_rows(rows):
    """Reject damaged observations before coverage or reminder calculations."""
    if not isinstance(rows, list):
        raise ValueError('Invalid AI candidate list')
    for row in rows:
        if (not isinstance(row, dict) or row.get('service') not in ('gemini', 'claude')
                or not isinstance(row.get('rule'), str)
                or not isinstance(row.get('sources'), list) or not row['sources']
                or any(not isinstance(source, str) or not source.strip()
                       for source in row['sources'])):
            raise ValueError('Invalid AI candidate observation')
        kind, separator, host = row['rule'].partition(',')
        if (not separator or kind not in ('DOMAIN', 'DOMAIN-SUFFIX')
                or ai_services.check_hostname(host) != host):
            raise ValueError('Invalid AI candidate rule')
    return rows


def read_state(path):
    if not path.is_file():
        return empty_state()
    state = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(state, dict) or type(state.get('version')) is not int or state['version'] != 1
            or not isinstance(state.get('snapshots'), dict)
            or not isinstance(state.get('sent'), dict)):
        raise ValueError('Invalid shared AI receipt state')
    for client, rows in state['snapshots'].items():
        if client not in CLIENTS:
            raise ValueError('Invalid AI candidate snapshot client')
        validate_candidate_rows(rows)
    if any(not isinstance(value, dict) for value in state['sent'].values()):
        raise ValueError('Invalid AI receipt record')
    return state

def candidate_key(item):
    return item['service'] + '|' + item['rule']

def merge_reports(state, reports, policy, *, on=None, manual=None):
    on = on or review_queue.today()
    snapshots = dict(state['snapshots'])
    fresh = []
    for client in CLIENTS:
        if client in reports:
            rows = validate_candidate_rows(reports[client].get('ai_review_candidates'))
            # Keep only stable observations, not daily computed review dates.
            snapshots[client] = [{k: item[k] for k in ('service', 'rule', 'sources')}
                                 for item in rows]
            fresh.append(client)
    merged = {}
    for client in CLIENTS:
        for item in snapshots.get(client, []):
            row = merged.setdefault(candidate_key(item),
                {'service': item['service'], 'rule': item['rule'], 'sources': set(), 'clients': set()})
            row['sources'].update(item['sources'])
            row['clients'].add(client)
    candidates = [{**item, 'sources': sorted(item['sources']), 'clients': sorted(item['clients'])}
                  for _, item in sorted(merged.items())]
    manual = manual or {}
    deployment, active = [], []
    for item in candidates:
        allowed = list(manual.get(item['service'], []))
        for client in fresh:
            allowed += reports[client].get('ai_approved_rules', {}).get(item['service'], [])
        if not set(item['clients']).intersection(fresh) and any(
                ai_services.approved_rule_covers(rule, item['rule']) for rule in allowed):
            deployment.append({**item, 'status': 'deployment_pending'})
        else:
            active.append(item)
    entries, counts = ai_services.evaluate_review_policy(active, policy, on=on)
    alerts, sent = [], {}
    for item in entries:
        if item['status'] not in ('pending', 'due'):
            continue
        key = candidate_key(item)
        cycle = hashlib.sha256(json.dumps([key, item['status'], item.get('reviewed_at'),
                item.get('review_due_on'), item.get('reason')], ensure_ascii=False).encode()).hexdigest()
        old = state['sent'].get(key, {})
        notified = None
        if old.get('cycle') == cycle:
            try:
                notified = date.fromisoformat(old['notified_at'])
            except (KeyError, TypeError, ValueError):
                pass
        if notified is not None and notified <= on:
            sent[key] = old
        else:
            notified = None
        if notified is None or on >= notified + timedelta(days=policy['reminder_interval_days']):
            alerts.append({**item, 'key': key, 'cycle': cycle})
    return ({'version': 1, 'snapshots': snapshots, 'sent': sent},
            {'review_candidates': entries + deployment, 'review_counts': counts, 'alerts': alerts,
             'deployment_pending': deployment,
             'fresh_clients': fresh, 'stale_clients': [c for c in CLIENTS if c not in fresh],
             'reminder_interval_days': policy['reminder_interval_days']})

def prepare(reports, *, state_path=STATE, queue_path=QUEUE, policy_path=POLICY):
    try:
        state = read_state(state_path)
    except (OSError, ValueError, TypeError):
        print('::warning::Invalid AI receipt state; restarting reminders')
        state = empty_state()
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    manual = ai_services.load_manual(ai_services.MANUAL.read_text(encoding='utf-8'))
    state, report = merge_reports(state, reports, policy, manual=manual)
    queue = ai_services.render_review_queue(report)
    if report['stale_clients']:
        queue += '\n> 本次未刷新：' + ', '.join(report['stale_clients']) + '；保留其上次有效候选（如有）。\n'
    from build_v2rayn import atomically_write
    atomically_write(queue_path, queue.encode('utf-8'))
    review_queue.write_json(state_path, state)
    return report

def acknowledge(report, path=STATE, *, on=None):
    on = on or review_queue.today()
    state = read_state(path)
    for item in report.get('alerts', []):
        state['sent'][item['key']] = {'cycle': item['cycle'], 'notified_at': on.isoformat()}
    review_queue.write_json(path, state)
