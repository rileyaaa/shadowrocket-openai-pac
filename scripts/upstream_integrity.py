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
    previous = (old or {}).get('sources', {})
    for key in (*domain_names, *ruleset_names):
        after = records[key]['rule_count']
        prior = previous.get(key)
        if prior is None or 'rule_count' not in prior:
            # The old schema did not store this count. Establish one baseline
            # from a fully parsed feed; all existing aggregate guards still run.
            if old is not None:
                print(f'::notice::Initial independent per-source count baseline: {key}={after}')
            continue
        before = prior['rule_count']
        minimum = .85 if key in ruleset_names else .75
        if type(before) is not int or before <= 0 or not minimum * before <= after <= 1.50 * before:
            raise ValueError(f'UPSTREAM SOURCE ANOMALY: {key}: {before} -> {after}; retain last good subscription')
