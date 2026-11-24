"""Advisory static analysis of earlier BLOCK rules versus reviewed AI routes.

Never changes order or routing policy. Opaque geosite/geoip datasets and
arbitrary regex intersections cannot be proven by this check.
"""
from __future__ import annotations
from collections import defaultdict
import ipaddress
import re

def split_domain(value):
    kind, sep, host = value.partition(':')
    return (kind, host) if sep else ('keyword', value)

def is_child(host, suffix):
    return host == suffix or host.endswith('.' + suffix)

def domain_overlap(a, b):
    ak, av = split_domain(a)
    bk, bv = split_domain(b)
    if ak == 'full' and bk == 'full':
        return av == bv
    if ak == 'full' and bk == 'domain':
        return is_child(av, bv)
    if ak == 'domain' and bk == 'full':
        return is_child(bv, av)
    if ak == bk == 'domain':
        return is_child(av, bv) or is_child(bv, av)
    # Keyword matching can prove overlap by matching the concrete hostname;
    # suffix-vs-keyword may also intersect on other descendants.
    if bk == 'keyword' and ak in ('full', 'domain'):
        return bv in av
    if ak == 'keyword' and bk in ('full', 'domain'):
        return av in bv
    if bk == 'regexp' and ak in ('full', 'domain'):
        try:
            return bool(re.search(bv, av))
        except re.error:
            return False
    if ak == 'regexp' and bk in ('full', 'domain'):
        try:
            return bool(re.search(av, bv))
        except re.error:
            return False
    return False

def domain_ancestors(host):
    labels = host.split('.')
    return ['.'.join(labels[i:]) for i in range(len(labels))]


def index_domains(domains):
    """Index explicit matches once; keep regex/keyword checks conservative."""
    exact, suffix, descendants = defaultdict(list), defaultdict(list), defaultdict(list)
    patterns = []
    for i, value in enumerate(domains):
        kind, host = split_domain(value)
        if kind in ('full', 'domain'):
            (exact if kind == 'full' else suffix)[host].append(i)
            for parent in domain_ancestors(host):
                descendants[parent].append(i)
        else:
            patterns.append(i)
    return exact, suffix, descendants, patterns


def matching_domains(value, domains, index):
    kind, host = split_domain(value)
    if kind not in ('full', 'domain'):
        # Rare reviewed pattern rules still use the original full scan.
        return (other for other in domains if domain_overlap(value, other))
    exact, suffix, descendants, patterns = index
    matches = set(exact.get(host, ()) if kind == 'full' else descendants.get(host, ()))
    for parent in domain_ancestors(host):
        matches.update(suffix.get(parent, ()))
    matches.update(i for i in patterns if domain_overlap(value, domains[i]))
    # Preserve the previous order, including preview/receipt semantics.
    return (domains[i] for i in sorted(matches))


def detect(blocked, reviewed, *, limit=100):
    """All distinct provable pairs; the preview limit never truncates state."""
    domains = list(dict.fromkeys(value for field, value, action in blocked
                                 if field == 'domain' and action == 'block'))
    index = index_domains(domains)
    ips = [(value, ipaddress.ip_network(value, strict=False))
           for field, value, action in dict.fromkeys(blocked)
           if field == 'ip' and action == 'block' and not value.startswith('geoip:')]
    pairs = []
    for field, value, action in dict.fromkeys(reviewed):
        if action != 'proxy':
            continue
        if field == 'domain':
            witnesses = matching_domains(value, domains, index)
        elif field == 'ip' and not value.startswith('geoip:'):
            network = ipaddress.ip_network(value, strict=False)
            witnesses = (d for d, other in ips if other.version == network.version and other.overlaps(network))
        else:
            continue
        pairs.extend({'field': field, 'proxy_rule': value, 'earlier_block_rule': witness}
                     for witness in witnesses)
    return {'count': len(pairs), 'pairs': pairs, 'examples': pairs[:limit],
            'proxy_rule_count': len({(x['field'], x['proxy_rule']) for x in pairs}),
            'limitations': 'Static overlaps only; opaque geosite/geoip, arbitrary regex intersections, DNS and client capture need runtime checks.'}


STATE = 'data/routing-conflicts.json'


def keys(rows):
    if not isinstance(rows, list):
        raise ValueError('Invalid routing conflict observations')
    result = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'field', 'proxy_rule', 'earlier_block_rule'}
                or row['field'] not in ('domain', 'ip')
                or not all(isinstance(v, str) and v for v in row.values())):
            raise ValueError('Invalid routing conflict pair')
        result.add((row['field'], row['proxy_rule'], row['earlier_block_rule']))
    return result


def rows(values):
    return [dict(zip(('field', 'proxy_rule', 'earlier_block_rule'), v)) for v in sorted(values)]


def read_state(path):
    import json
    if not path.exists():
        return {'version': 1, 'current': [], 'delivered': [], 'notified_at': None}
    old = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(old, dict) or old.get('version') != 1:
        raise ValueError('Invalid routing conflict state')
    keys(old['current'])
    keys(old['delivered'])
    return old


def evaluate(conflicts, state, *, on, interval=30):
    from datetime import date, timedelta
    current = keys(conflicts['pairs'])
    if len(current) != conflicts['count']:
        raise ValueError('Routing conflict pair count mismatch')
    delivered = keys(state['delivered'])
    added, removed = current - delivered, delivered - current
    stamp = state.get('notified_at')
    last = date.fromisoformat(stamp) if stamp else None
    if last is not None and last > on:
        raise ValueError('Future routing conflict receipt date')
    due = bool(current and last and on >= last + timedelta(days=interval))
    alert = bool(added or removed or (current and last is None) or due)
    updated = {**state, 'current': rows(current)}
    return updated, {'count': len(current), 'pairs': rows(current),
        'added': rows(added), 'removed': rows(removed),
        'alert': alert, 'due': due, 'interval': interval,
        'limitations': conflicts['limitations']}


def prepare(conflicts, path, *, on=None, interval=30):
    import review_queue
    on = on or review_queue.today()
    try:
        old = read_state(path)
        state, report = evaluate(conflicts, old, on=on, interval=interval)
    except (OSError, ValueError, KeyError, TypeError):
        print('::warning::Invalid conflict receipt state; restart notification cycle')
        state, report = evaluate(conflicts, {'version': 1, 'current': [],
                         'delivered': [], 'notified_at': None}, on=on, interval=interval)
    review_queue.write_json(path, state)
    return report


def acknowledge(report, path, *, on=None):
    import review_queue
    if not report.get('alert'):
        return
    state = read_state(path)
    if keys(report['pairs']) != keys(state['current']):
        raise ValueError('Conflict observations changed before acknowledgement')
    state['delivered'] = rows(keys(report['pairs']))
    state['notified_at'] = (on or review_queue.today()).isoformat()
    review_queue.write_json(path, state)
