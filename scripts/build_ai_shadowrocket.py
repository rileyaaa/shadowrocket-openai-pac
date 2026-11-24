#!/usr/bin/env python3
"""Maintain the ONLY Shadowrocket subscription: Johnshall + OpenAI/Gemini/Claude.

Uses stable pure parsing/rendering from legacy build.py, without running that
builder or creating its retired .conf. Regenerates OpenAI review metadata,
Voice coverage baseline, and notification state alongside the AI subscription.
Both client subscriptions retain independent safety validation and publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import build as legacy  # read-only, never invoke build.run()
import build_v2rayn as v2helpers  # only atomic writer, independent data fetch is below
import release_integrity
import ai_services
import review_queue

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'Shadowrocket_Johnshall_AI.conf'
STATE = ROOT / 'data/ai-shadowrocket-sources.json'
REVIEW_QUEUE = ROOT / 'data/ai-review-queue.md'
ORIGINAL_STATE = ROOT / 'data/sources.json'
ORIGINAL_AUTO = ROOT / 'rules/openai-auto.list'
JOHNSHALL_MARKER = '# [3] Johnshall full original rules, Proxy mapped to exact configured node\n'


def load_sources(args):
    base = (args.upstream_file.read_bytes() if args.upstream_file
            else legacy.fetch(legacy.BASE_URL, 1_000_000))
    voice_raw = (args.voice_file.read_bytes() if args.voice_file else legacy.fetch(legacy.VOICE_URL))
    source_data = {'johnshall': (legacy.BASE_URL, base),
                   'voice': (legacy.VOICE_URL, voice_raw)}
    parsed_domains = {}
    unparsed = {}
    for name, (url, fmt) in legacy.DOMAIN_SOURCES.items():
        raw = ((args.domain_dir / (name + '.txt')).read_bytes() if args.domain_dir
               else legacy.fetch(url))
        source_data[name] = (url, raw)
        unparsed[name] = []
        parsed_domains[name] = legacy.parse_domain_list(raw.decode('utf-8-sig'), fmt,
                                                       unparsed=unparsed[name])
    rulesets = {}
    for name, (url, _) in legacy.RULESET_SOURCES.items():
        raw = ((args.ruleset_dir / (name + '.txt')).read_bytes() if args.ruleset_dir
               else legacy.fetch(url))
        source_data[name] = (url, raw)
        rulesets[url] = legacy.parse_embedded_ruleset(raw.decode('utf-8-sig'))
    return base, voice_raw, source_data, parsed_domains, unparsed, rulesets


def insert_ai_rules(original: str, additions: dict, node: str) -> str:
    """Inject only into the newly generated AI subscription, not the legacy."""
    if original.count(JOHNSHALL_MARKER) != 1:
        raise ValueError('Original Johnshall insertion anchor changed')
    if not node or '\n' in node or ',' in node:
        raise ValueError('Invalid exact OpenAI node name')
    parts = ['# [2b] Independently reviewed Gemini and Claude enhancements',
             '# Both services use the configured AI node; its name must match the Shadowrocket node.']
    for service in ('gemini', 'claude'):
        rules = additions['rules'][service]
        parts.append('# ' + service.upper() + ' first-party and exact shared dependencies')
        for rule in rules:
            kind = rule.split(',', 1)[0]
            if kind not in ('DOMAIN', 'DOMAIN-SUFFIX'):
                raise ValueError(f'Unexpected AI routing rule {rule}')
            parts.append(f'{rule},{node},force-remote-dns')
    # Place above Johnshall regional/direct rules; prior OpenAI layer untouched.
    return original.replace(JOHNSHALL_MARKER,
                            '\n'.join(parts) + '\n\n' + JOHNSHALL_MARKER, 1)


def prepare_openai_review(voice, auto, emitted_auto, emitted_manual,
                          source_lists, unparsed, fetched, rulesets, settings,
                          stats, old_state, old_auto, changed):
    """Maintain OpenAI review metadata without generating the retired .conf.

    This is the audit-only part of the former build.run(): Voice baseline,
    upstream exclusions, review queue, reminder delivery, Apple News provenance.
    """
    excluded = legacy.excluded_auto_rule_sources(source_lists, auto, unparsed)
    auto_text = (
        "# OpenAI automatic rules: official Voice destination IPs + public domains\n"
        "# No node name here: route is supplied while merging into .conf\n"
        "# Voice IPs (destination-only); never use OpenAI egress source ranges\n"
        + "\n".join(f"{rule},no-resolve" for rule in voice) + "\n"
        + "# Dedicated first-party and explicitly verified hosted domains\n"
        + "\n".join(emitted_auto) + "\n"
    )
    try:
        decisions = (ROOT / 'config/review-decisions.json').read_bytes()
    except OSError:
        decisions = b''
    source_state = {
        'sources': {name: {'url': url, 'sha256': hashlib.sha256(raw).hexdigest()}
                    for name, (url, raw) in fetched.items()},
        'settings': settings, 'statistics': stats,
        'review': {
            'excluded_auto_rules': list(excluded),
            'decisions_sha256': hashlib.sha256(decisions).hexdigest(),
        },
    }
    for name, (url, _) in legacy.RULESET_SOURCES.items():
        source_state['sources'][name]['rule_count'] = len(rulesets[url])
    old_report = legacy.make_sync_report(
        old_state, source_state, old_auto, auto_text, changed,
        excluded_sources=excluded,
    )
    review, delivery = review_queue.evaluate(
        excluded, (old_state or {}).get('review', {}).get('excluded_auto_rules'),
        emitted_auto + emitted_manual, legacy.domain_rule_covers, ROOT,
    )
    return {'source_state': source_state, 'auto_text': auto_text,
            'review': review, 'delivery': delivery, 'report': old_report}



def load_published_baseline() -> tuple[dict | None, dict | None, str]:
    """Require a complete, self-consistent published baseline before any rebuild.

    Existing v1 snapshots are a recognized migration to v2 only if every
    mandatory file and digest is intact. Missing fields are never interpreted
    as a fresh install. An actual fresh install has none of these four files.
    """
    files = (OUTPUT, STATE, ORIGINAL_STATE, ORIGINAL_AUTO)
    existing = [path for path in files if path.is_file()]
    if not existing:
        return None, None, ''
    if len(existing) != len(files):
        missing = [str(path.relative_to(ROOT)) for path in files if not path.is_file()]
        raise ValueError('Incomplete published Shadowrocket baseline: missing ' + ', '.join(missing))
    state = json.loads(STATE.read_text(encoding='utf-8'))
    old_legacy = json.loads(ORIGINAL_STATE.read_text(encoding='utf-8'))
    if not isinstance(state, dict) or state.get('schema_version') not in (1, 2):
        raise ValueError('Unknown published Shadowrocket baseline version')
    required = ('output_sha256', 'ai_counts', 'statistics', 'sources')
    if any(not isinstance(state.get(key), dict) or not state[key] for key in required[1:]):
        raise ValueError('Incomplete published Shadowrocket state: counts/sources/statistics')
    digest = state.get('output_sha256')
    if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('Missing Shadowrocket output_sha256; refusing baseline reset')
    old_output = OUTPUT.read_bytes()
    if hashlib.sha256(old_output).hexdigest() != digest:
        raise ValueError('Previous Shadowrocket output/state digest mismatch')
    if not isinstance(old_legacy, dict) or not isinstance(old_legacy.get('sources'), dict) or not isinstance(old_legacy.get('statistics'), dict):
        raise ValueError('Incomplete Shadowrocket legacy source baseline')
    if not isinstance(old_legacy['sources'].get('voice'), dict) or not old_legacy['sources']['voice'].get('sha256'):
        raise ValueError('Missing Shadowrocket Voice source baseline')
    old_auto_bytes = ORIGINAL_AUTO.read_bytes()
    old_auto = old_auto_bytes.decode('utf-8')
    voice_rules = {','.join(row.split(',')[:2]) for row in legacy.active_auto_rules(old_auto)
                   if row.startswith(('IP-CIDR,', 'IP-CIDR6,'))}
    if not voice_rules:
        raise ValueError('Published Voice baseline is missing')
    # Check the auxiliary baseline against the *published* output, not only
    # its own file. This protects recognized v1 snapshots without a digest
    # of the auxiliary file.
    header = '# [1a] OpenAI automatic rules - official Voice destination IPs\n'
    stop = '# [1b] OpenAI automatic rules - public domain rules\n'
    text = old_output.decode('utf-8')
    if text.count(header) != 1 or text.count(stop) != 1:
        raise ValueError('Published Shadowrocket Voice section is missing')
    segment = text.split(header, 1)[1].split(stop, 1)[0]
    effective = {','.join(row.strip().split(',')[:2]) for row in segment.splitlines()
                 if row.strip().startswith(('IP-CIDR,', 'IP-CIDR6,'))}
    if effective != voice_rules:
        raise ValueError('Published Shadowrocket Voice section does not match auxiliary baseline')
    if state['schema_version'] == 2:
        for key, raw in (('voice_auto_sha256', old_auto_bytes),
                         ('legacy_state_sha256', ORIGINAL_STATE.read_bytes())):
            expected = state.get(key)
            if not isinstance(expected, str) or hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('Shadowrocket published auxiliary digest mismatch: ' + key)
    return state, old_legacy, old_auto



def run(argv: list[str] | None = None) -> dict:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--upstream-file', type=Path)
    p.add_argument('--voice-file', type=Path)
    p.add_argument('--domain-dir', type=Path)
    p.add_argument('--ruleset-dir', type=Path)
    p.add_argument('--ai-dir', type=Path, help='Offline fixtures: gemini_v2fly.txt, etc.')
    p.add_argument('--report-file', type=Path)
    args = p.parse_args(argv)

    old, old_legacy, old_auto = load_published_baseline()
    settings = legacy.load_settings()
    base, voice_raw, fetched, source_lists, unparsed, rulesets = load_sources(args)
    voice = legacy.parse_voice(voice_raw)
    all_auto = list(dict.fromkeys(x for rows in source_lists.values() for x in rows))
    auto = legacy.filter_auto_domains(all_auto)
    manual = legacy.parse_manual(ROOT / 'config/manual-openai.rules')
    emitted_auto, emitted_manual = legacy.compact_openai_rules(auto, manual)
    original, stats = legacy.generate(base.decode('utf-8-sig'), voice, emitted_auto,
                                      emitted_manual, settings=settings, rulesets=rulesets)
    stats.update({
        'excluded_shared_auto_domains': len(all_auto) - len(auto),
        'auto_input_rules': len(auto),
        'manual_backup_rules': len(manual),
        'suppressed_redundant_auto_rules': len(auto) - len(emitted_auto),
        'suppressed_redundant_manual_rules': len(manual) - len(emitted_manual),
        'cross_layer_duplicate_rules_retained': len(set(emitted_auto) & set(emitted_manual)),
        'auto_total_ip_and_domain_rules': len(voice) + len(emitted_auto),
        'unparsed_upstream_rules': len({rule for rows in unparsed.values() for rule in rows}),
        'embedded_ruleset_rules': sum(len(rows) for rows in rulesets.values()),
    })
    stats.update(legacy.voice_address_counts(voice))
    # Retain the original Apple News embedded-list size guard.
    for name, (url, _) in legacy.RULESET_SOURCES.items():
        before = (old_legacy or {}).get('sources', {}).get(name)
        if before is not None:
            count = before.get('rule_count')
            if (type(count) is not int or count <= 0 or
                    not count * .85 <= len(rulesets[url]) <= count * 1.50):
                raise ValueError(f'Embedded ruleset count changed unexpectedly: {name}')
    reviewed_voice = False
    try:
        legacy.validate_voice_coverage(voice, old_auto, has_baseline=old_legacy is not None)
    except ValueError as exc:
        if not str(exc).startswith('VOICE COVERAGE ANOMALY') or not legacy.is_reviewed_voice_expansion(
                voice, old_auto, voice_raw, old_legacy):
            raise
        reviewed_voice = True
    prev_ads = (old_legacy or {}).get('statistics', {}).get('retained_ad_rules')
    reviewed_ad_drop = (type(prev_ads) is int and stats['retained_ad_rules'] < prev_ads * .85
                        and legacy.is_reviewed_johnshall_ad_decrease(base, stats, old_legacy))
    legacy.validate_upstream_change(stats, old_legacy,
                                    reviewed_voice_expansion=reviewed_voice,
                                    reviewed_johnshall_ad_decrease=reviewed_ad_drop)
    if args.ai_dir:
        overrides = {(key): (args.ai_dir / (key + '.txt')).read_bytes()
                     for key in ai_services.SOURCES}
    else:
        overrides = None
    ai = ai_services.collect(legacy.fetch, source_overrides=overrides)
    ai_services.validate_safety(ai['counts'], old)
    enhanced = insert_ai_rules(original, ai, settings['openai_node_name'])
    if (len(enhanced.encode('utf-8')) < 1_000_000 or enhanced.count('[Rule]') != 1
            or enhanced.count('FINAL,direct') != 1 or
            not enhanced.rstrip().endswith(legacy.JOHNSHALL_FOOTER)):
        raise ValueError('Generated AI Shadowrocket configuration failed integrity checks')
    for core in ai_services.MANDATORY['gemini'] | ai_services.MANDATORY['claude']:
        if f'{core},{settings["openai_node_name"]},force-remote-dns' not in enhanced:
            raise ValueError(f'Mandatory Gemini/Claude rule missing in output: {core}')
    outputs = {name: {'url': url, 'sha256': hashlib.sha256(raw).hexdigest()}
               for name, (url, raw) in fetched.items()}
    outputs.update(ai['records'])
    state = {'schema_version': 2, 'sources': outputs, 'ai_counts': ai['counts'],
             'statistics': stats,
             'build_inputs_sha256': release_integrity.build_inputs_fingerprint('shadowrocket_ai'),
             'manual_ai_sha256': ai['manual_sha256'],
             'review_candidates': ai['review_candidates'],
             'review_counts': ai['review_counts'],
             'review_decisions_sha256': ai['review_decisions_sha256'],
             'output_sha256': hashlib.sha256(enhanced.encode('utf-8')).hexdigest()}
    output_bytes = enhanced.encode('utf-8')
    changed = not OUTPUT.exists() or OUTPUT.read_bytes() != output_bytes
    review_meta = prepare_openai_review(
        voice, auto, emitted_auto, emitted_manual, source_lists, unparsed,
        fetched, rulesets, settings, stats, old_legacy, old_auto, changed,
    )
    # Bind the freshly generated auxiliary files to the new schema-v2 state.
    legacy_bytes = (json.dumps(review_meta['source_state'], ensure_ascii=False,
                               sort_keys=True, indent=2) + '\n').encode('utf-8')
    state['voice_auto_sha256'] = hashlib.sha256(review_meta['auto_text'].encode('utf-8')).hexdigest()
    state['legacy_state_sha256'] = hashlib.sha256(legacy_bytes).hexdigest()
    review = review_meta['review']
    original_delta = review_meta['report']
    report = {'build_success': True, 'config_changed': changed,
              'statistics': {**stats, **ai['counts'], 'conf_bytes': len(output_bytes)},
              'changed_sources': [k for k, value in outputs.items()
                                  if value != (old or {}).get('sources', {}).get(k)],
              'ai_review_candidates': ai['review_candidates'],
              'ai_review_counts': ai['review_counts'],
              'auto_added': original_delta['auto_added'],
              'auto_removed': original_delta['auto_removed'],
              'new_excluded_candidates': review['new_candidates'],
              'review_due_candidates': review['due_candidates'],
              'manual_review_counts': review['counts'],
              'review_reminder_interval_days': review['reminder_interval_days'],
              'review_warnings': review['warnings'],
              'review_decisions_changed': original_delta['review_decisions_changed'],
              'settings_changed': original_delta['settings_changed'],
              'stat_deltas': original_delta['stat_deltas'],
              'warnings': ['Shared Google authentication/static hosts may also proxy unrelated Google traffic.',
                           'Gemini/Claude rules depend on host/SNI; genuine client routing still needs testing.']}
    # All downloads, semantic checks and safety guards pass before any writes.
    # No retired Shadowrocket_Johnshall_OpenAI.conf file is ever created.
    v2helpers.atomically_write(OUTPUT, output_bytes)
    v2helpers.atomically_write(STATE, (json.dumps(state, ensure_ascii=False, indent=2,
                                                  sort_keys=True) + '\n').encode('utf-8'))
    v2helpers.atomically_write(REVIEW_QUEUE, ai_services.render_review_queue(ai).encode('utf-8'))
    v2helpers.atomically_write(ORIGINAL_AUTO, review_meta['auto_text'].encode('utf-8'))
    for name, (_, snapshot_path) in legacy.RULESET_SOURCES.items():
        v2helpers.atomically_write(ROOT / snapshot_path, fetched[name][1].decode('utf-8').encode('utf-8'))
    v2helpers.atomically_write(ORIGINAL_STATE, legacy_bytes)
    v2helpers.atomically_write(ROOT / 'data/review-queue.md',
        review_queue.render_queue(review).encode('utf-8'))
    review_queue.write_json(ROOT / 'data/review-notifications.json', review_meta['delivery'])
    if args.report_file:
        report['artifact_sha256'] = release_integrity.artifact_manifest(release_integrity.SHADOW_AI_FILES, ROOT)
        v2helpers.atomically_write(args.report_file,
            (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'build': 'success', 'changed': changed, 'ai_counts': ai['counts'],
                      'conf_bytes': len(output_bytes)}, ensure_ascii=False))
    return report


if __name__ == '__main__':
    try:
        run()
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'Shadowrocket AI build blocked: {exc}', file=sys.stderr)
        raise SystemExit(1)
