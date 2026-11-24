"""Per-source size guards shared by both independently fetched subscriptions."""
from __future__ import annotations

def record_counts(records, domain_lists, rulesets, ruleset_sources):
    for key, rows in domain_lists.items():
        unique = len(set(rows))
        if unique < 10:
            raise ValueError(f'OpenAI source {key}: too few distinct domain rules ({unique})')
        records[key]['rule_count'] = unique
    for key, (url, _) in ruleset_sources.items():
        records[key]['rule_count'] = len(rulesets[url])

def count_deltas(records, old):
    previous = (old or {}).get('sources', {})
    return {key: row['rule_count'] - previous[key]['rule_count']
            for key, row in records.items()
            if type(row.get('rule_count')) is int
            and type(previous.get(key, {}).get('rule_count')) is int
            and row['rule_count'] != previous[key]['rule_count']}

def validate_counts(records, old, domain_names, ruleset_names):
    if old is None:
        return
    previous = old.get('sources')
    if not isinstance(previous, dict):
        raise ValueError('Missing previous upstream source baselines')
    for key in (*domain_names, *ruleset_names):
        after = records[key]['rule_count']
        prior = previous.get(key)
        if not isinstance(prior, dict):
            raise ValueError(f'Missing previous upstream source record: {key}')
        if 'rule_count' not in prior:
            if old.get('schema_version') == 1 and isinstance(prior.get('sha256'), str):
                print(f'::notice::Migrating v1 independent per-source count baseline: {key}={after}')
                continue
            raise ValueError(f'Missing previous upstream rule_count baseline: {key}')
        before = prior['rule_count']
        minimum = .85 if key in ruleset_names else .75
        if type(before) is not int or before <= 0 or not minimum * before <= after <= 1.50 * before:
            raise ValueError(f'UPSTREAM SOURCE ANOMALY: {key}: {before} -> {after}; retain last good subscription')
