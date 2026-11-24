"""Merge OpenAI review observations without widening either client's policy."""
from __future__ import annotations
import json
from pathlib import Path
import build as legacy
import review_queue

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = 'data/openai-review-snapshots.json'
FILES = (SNAPSHOT, 'data/review-queue.md', 'data/review-notifications.json')
CLIENTS = ('shadowrocket_ai', 'v2rayn')

def read_state(path):
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(doc, dict) or doc.get('version') != 1 or not isinstance(doc.get('snapshots'), dict):
        raise ValueError('Invalid OpenAI review snapshots')
    rows = doc['snapshots']
    for client, row in rows.items():
        if client not in CLIENTS or not isinstance(row, dict):
            raise ValueError('Invalid OpenAI client observation')
        if (not isinstance(row.get('excluded'), dict)
                or any(not isinstance(k, str) or not isinstance(v, list)
                       or any(not isinstance(s, str) for s in v)
                       for k, v in row['excluded'].items())):
            raise ValueError('Invalid OpenAI excluded-source map')
        for key in ('common_rules', 'client_only_rules'):
            if not isinstance(row.get(key), list) or any(
                    not isinstance(rule, str) or rule.count(',') != 1 for rule in row[key]):
                raise ValueError('Invalid OpenAI coverage list')
    return rows

def covers(rules, candidate):
    return (candidate.count(',') == 1 and candidate.split(',', 1)[0] in review_queue.DOMAIN_TYPES
            and any(legacy.domain_rule_covers(rule, candidate) for rule in rules))

def merge(snapshots, reports, root=ROOT, *, on=None):
    fresh = [key for key in CLIENTS if key in reports]
    updated = dict(snapshots)
    for key in fresh:
        updated[key] = reports[key]['openai_observation']
    excluded, observed = {}, {}
    for key, row in updated.items():
        for rule, sources in row['excluded'].items():
            excluded.setdefault(rule, set()).update(sources)
            observed.setdefault(rule, set()).add(key)
    excluded = {rule: sorted(src) for rule, src in excluded.items()}
    manual = legacy.parse_manual(root / 'config/manual-openai.rules')
    covered = []
    for rule in excluded:
        current = observed[rule].intersection(fresh)
        if covers(manual, rule) or (
                current and all(covers(updated[c]['common_rules'], rule) for c in current)
        ) or (not current and any(covers(updated[c]['common_rules'], rule) for c in fresh)):
            covered.append(rule)
    previous = sorted({rule for row in snapshots.values() for rule in row['excluded']})
    review, delivery = review_queue.evaluate(excluded, previous, covered,
                    legacy.domain_rule_covers, root, on, repeat_pending=True)
    deployment = []
    for item in review['entries']:
        rule = item['rule']
        item['client_coverage'] = {}
        for client in CLIENTS:
            row = updated.get(client)
            if row is None:
                label = '无有效快照'
            elif covers(row['common_rules'], rule):
                label = '共用规则覆盖'
            elif covers(row['client_only_rules'], rule):
                label = '客户端专属例外覆盖（不等于共用批准）'
            elif rule in row['excluded']:
                label = '未由专用规则覆盖'
            else:
                label = '本来源快照无此候选'
            if client not in fresh:
                label += '；旧快照'
                if item['status'] == 'covered' and row and rule in row['excluded'] and not covers(row['common_rules'], rule):
                    deployment.append({'rule': rule, 'client': client})
                    label += '；共用规则已审核，等待重新构建'
            item['client_coverage'][client] = label
    review['fresh_clients'] = fresh
    review['stale_clients'] = [key for key in CLIENTS if key not in fresh]
    review['deployment_pending'] = deployment
    return updated, review, delivery

def prepare(reports, root=ROOT):
    snapshot = root / SNAPSHOT
    try:
        old = read_state(snapshot)
    except (OSError, ValueError, TypeError):
        old = {}
        print('::warning::Invalid OpenAI review snapshots; fresh observations only')
    updated, review, delivery = merge(old, reports, root)
    text = review_queue.render_queue(review)
    text += '\n> 新候选首次提醒；未处理的待审或到期项按配置间隔再次汇总提醒。\n'
    if review['stale_clients']:
        text += '\n> 未刷新：' + ', '.join(review['stale_clients']) + '；保留上次有效观察（如有）。\n'
    text += '\n| 规则 | Shadowrocket | v2rayN |\n|---|---|---|\n'
    def cell(s):
        return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('|','&#124;').replace(chr(96),'&#96;').replace('\n',' ')
    for item in review['entries']:
        text += '| ' + ' | '.join(cell(x) for x in (item['rule'],
            item['client_coverage']['shadowrocket_ai'], item['client_coverage']['v2rayn'])) + ' |\n'
    from build_v2rayn import atomically_write
    atomically_write(root / FILES[1], text.encode('utf-8'))
    review_queue.write_json(root / FILES[2], delivery)
    review_queue.write_json(snapshot, {'version': 1, 'snapshots': updated})
    return review

def receipt_report(review):
    return {'new_excluded_candidates': review['new_candidates'],
            'review_due_candidates': review['due_candidates']}
