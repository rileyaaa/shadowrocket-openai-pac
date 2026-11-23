#!/usr/bin/env python3
"""Independent, complete Shadowrocket Johnshall + OpenAI + Gemini + Claude.

This is a NEW subscription. The existing build.py/notify_telegram.py and
Shadowrocket_Johnshall_OpenAI.conf are neither modified nor read as build
inputs. Downloads the original seven sources independently, invokes only the
reviewed pure rendering helpers from build.py, then adds audited AI rules
before Johnshall. Publication is atomic and guarded by both old and new data.
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
import ai_services

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
             '# Both services use the EXACT OpenAI Seattle node; changes require review.']
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


def run(argv: list[str] | None = None) -> dict:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--upstream-file', type=Path)
    p.add_argument('--voice-file', type=Path)
    p.add_argument('--domain-dir', type=Path)
    p.add_argument('--ruleset-dir', type=Path)
    p.add_argument('--ai-dir', type=Path, help='Offline fixtures: gemini_v2fly.txt, etc.')
    p.add_argument('--report-file', type=Path)
    args = p.parse_args(argv)

    settings = legacy.load_settings()
    base, voice_raw, fetched, source_lists, unparsed, rulesets = load_sources(args)
    voice = legacy.parse_voice(voice_raw)
    all_auto = list(dict.fromkeys(x for rows in source_lists.values() for x in rows))
    auto = legacy.filter_auto_domains(all_auto)
    manual = legacy.parse_manual(ROOT / 'config/manual-openai.rules')
    emitted_auto, emitted_manual = legacy.compact_openai_rules(auto, manual)
    original, stats = legacy.generate(base.decode('utf-8-sig'), voice, emitted_auto,
                                      emitted_manual, settings=settings, rulesets=rulesets)
    old_legacy = json.loads(ORIGINAL_STATE.read_text(encoding='utf-8')) if ORIGINAL_STATE.exists() else None
    old_auto = ORIGINAL_AUTO.read_text(encoding='utf-8') if ORIGINAL_AUTO.exists() else ''
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
    old = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else None
    if old and old.get('schema_version') != 1:
        raise ValueError('Unsupported prior Shadowrocket AI state version')
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
    state = {'schema_version': 1, 'sources': outputs, 'ai_counts': ai['counts'],
             'statistics': stats, 'manual_ai_sha256': ai['manual_sha256'],
             'review_candidates': ai['review_candidates'],
             'output_sha256': hashlib.sha256(enhanced.encode('utf-8')).hexdigest()}
    output_bytes = enhanced.encode('utf-8')
    changed = not OUTPUT.exists() or OUTPUT.read_bytes() != output_bytes
    report = {'build_success': True, 'config_changed': changed,
              'statistics': {**stats, **ai['counts'], 'conf_bytes': len(output_bytes)},
              'changed_sources': [k for k, value in outputs.items()
                                  if value != (old or {}).get('sources', {}).get(k)],
              'ai_review_candidates': ai['review_candidates'],
              'warnings': ['Shared Google authentication/static hosts may also proxy unrelated Google traffic.',
                           'Gemini/Claude rules depend on host/SNI; genuine client routing still needs testing.']}
    # All downloaded inputs, semantic checks, and both safety baselines were
    # checked before replacing any published artifact.
    v2helpers.atomically_write(OUTPUT, output_bytes)
    v2helpers.atomically_write(STATE, (json.dumps(state, ensure_ascii=False, indent=2,
                                                  sort_keys=True) + '\n').encode('utf-8'))
    v2helpers.atomically_write(REVIEW_QUEUE, ai_services.render_review_queue(ai).encode('utf-8'))
    if args.report_file:
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
