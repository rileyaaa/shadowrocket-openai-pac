#!/usr/bin/env python3
"""Independent upstream-driven v2rayN GUI routing subscription builder.

Reuses only stable, read-only Shadowrocket parsing/allowlist functions. It does
not read the generated Shadowrocket .conf or invoke the legacy build pipeline.
All network sources must be available. Any error preserves last good output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

import build as legacy  # read-only reviewed upstream parsing and allowlist
import v2rayn_core as core
import release_integrity
import upstream_integrity
import routing_conflicts
import ai_services  # reviewed Gemini/Claude feeds; no node binding

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'v2rayN_Johnshall_AI.json'
STATE = ROOT / 'data/v2rayn-sources.json'
BITBROWSER = ROOT / 'data/bitbrowser_domains.txt'
OPENAI_EXTRA = ROOT / 'config/v2rayn/openai-extra.rules'
PROCESSES = ROOT / 'config/v2rayn/verified-processes.txt'


def download(url: str, minimum: int = 50) -> bytes:
    """Fetch independently, sharing the same transport validation as Shadowrocket."""
    return legacy.fetch(url, minimum=minimum, user_agent='v2rayn-johnshall-openai/1.0')


def parse_user_extra(text: str) -> list[tuple[str, str, str]]:
    """Dedicated v2rayN-only user exceptions, never write original review state."""
    results = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('regexp:'):
            pattern = line[7:]
            if len(pattern) > 200 or not pattern.startswith('^') or not pattern.endswith('$'):
                raise ValueError(f'Unbounded regex rule {line}')
            re.compile(pattern)
            results.append(('domain', line, 'proxy'))
        elif line.startswith('full:'):
            field, value = core.as_match('DOMAIN', line[5:])
            results.append((field, value, 'proxy'))
        elif line.startswith('domain:'):
            field, value = core.as_match('DOMAIN-SUFFIX', line[7:])
            results.append((field, value, 'proxy'))
        else:
            raise ValueError(f'Unrecognized v2rayN-only OpenAI exception: {line}')
    if len(results) < 10:
        raise ValueError('OpenAI extras unexpectedly small')
    return results


def atomically_write(path: Path, content: bytes) -> None:
    """Only replace the published file after every validation passed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == content:
        return
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', prefix=f'.{path.name}.',
                                         dir=path.parent, delete=False) as tmp:
            name = tmp.name
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def validate_published_voice(output: bytes, state: dict) -> None:
    """Bind the historical Voice ranges and counters to the published routes."""
    voice = state['voice_rules']
    if any(rule.count(',') != 1 for rule in voice):
        raise ValueError('Malformed published v2rayN Voice baseline rule')
    counts = {**legacy.voice_address_counts(voice), 'voice_prefixes': len(voice)}
    for key, expected in counts.items():
        if type(state['statistics'].get(key)) is not int or state['statistics'][key] != expected:
            raise ValueError('Published v2rayN Voice statistic mismatch: ' + key)
    expected = {core.as_match(*rule.split(',', 1))[1] for rule in voice}
    rows = json.loads(output)
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError('Invalid published v2rayN routing list')
    actual = []
    from route_semantics import require_route_shape
    for row in rows:
        label = row.get('remarks', '')
        if isinstance(label, str) and label.startswith('OpenAI official Voice IPs / '):
            require_route_shape(row, 'ip')
            if row.get('enabled') is not True or row.get('outboundTag') != 'proxy':
                raise ValueError('Published v2rayN Voice layer is disabled or has wrong policy')
            actual.extend(row['ip'])
    if set(actual) != expected or len(actual) != len(voice):
        raise ValueError('Published v2rayN Voice layer does not match historical baseline')


def load_published_baseline() -> tuple[bytes | None, dict | None]:
    """Only an intact existing v1/v2 release may be used for the next baseline."""
    has_output, has_state = CONFIG.is_file(), STATE.is_file()
    if not has_output and not has_state:
        return None, None  # genuine first initialization
    if not has_output or not has_state:
        raise ValueError('Incomplete published v2rayN baseline: output/state file missing')
    before = CONFIG.read_bytes()
    old = json.loads(STATE.read_text(encoding='utf-8'))
    if not isinstance(old, dict) or type(old.get('schema_version')) is not int or old['schema_version'] not in (1, 2):
        raise ValueError('Unknown published v2rayN state version')
    for key in ('statistics', 'sources', 'ai_counts', 'inputs_sha256'):
        if not isinstance(old.get(key), dict) or not old[key]:
            raise ValueError('Incomplete published v2rayN baseline: missing ' + key)
    digest = old.get('output_sha256')
    if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('Missing published v2rayN output_sha256')
    if hashlib.sha256(before).hexdigest() != digest:
        raise ValueError('Previous v2rayN output/state digest mismatch')
    voice = old.get('voice_rules')
    if not isinstance(voice, list) or len(voice) < 5 or not all(
            isinstance(rule, str) and rule.startswith(('IP-CIDR,', 'IP-CIDR6,'))
            for rule in voice):
        raise ValueError('Missing published v2rayN voice_rules baseline')
    if len(set(voice)) != len(voice):
        raise ValueError('Duplicate entries in published v2rayN Voice baseline')
    # The previous v1 counted input domains; migrate only known fully approved
    # v1 snapshots, not an unverified/partially filtered input list.
    if old['schema_version'] == 1:
        old_stats = old['statistics']
        expected = old_stats.get('bitbrowser_domains')
        total_approved = (old_stats.get('official_bitbrowser_domains', -1) +
                          old_stats.get('user_requested_bitbrowser_domains', -1))
        if type(expected) is not int or expected != total_approved:
            raise ValueError('Unrecognized v2rayN v1 BitBrowser baseline; manual review required')
    elif type(old['statistics'].get('bitbrowser_effective_domains')) is not int:
        raise ValueError('Missing published v2rayN effective BitBrowser baseline')
    validate_published_voice(before, old)
    return before, old


def selected_bitbrowser_domains(entries: list[tuple[str, str, str]]) -> list[str]:
    """Only previously approved entries are emitted; input count is advisory."""
    # Preserve approved input order so a healthy regeneration is byte-identical.
    # load_bitbrowser_domains has already rejected duplicate hosts.
    return [host for host, confidence, _ in entries
            if confidence in ('official', 'user')]


def safety_check(stats: dict, old: dict | None, *, reviewed_voice=False, reviewed_ads=False) -> None:
    if old is None:
        return
    previous = old.get('statistics')
    if not isinstance(previous, dict):
        raise ValueError('Previous v2rayN statistics missing; refusing baseline reset')
    for key, lo, hi in (
        ('johnshall_lines', .85, 1.50), ('johnshall_proxy_rules', .85, 1.50),
        ('johnshall_block_rules', .85, 1.50), ('voice_prefixes', .70, 2.00),
        ('voice_ipv4_addresses', .70, 2.00), ('voice_ipv6_addresses', .70, 2.00),
        ('auto_domains', .75, 2.00), ('manual_domains', .75, 2.00),
        ('bitbrowser_effective_domains', .75, 2.00), ('domain_rules', .80, 1.50),
        ('ip_rules', .70, 2.00), ('block_rules', .85, 1.50),
    ):
        before = (previous.get('bitbrowser_domains') if key == 'bitbrowser_effective_domains'
                  and old.get('schema_version') == 1 else previous.get(key))
        now = stats.get(key)
        if reviewed_voice and key in ('voice_prefixes', 'voice_ipv4_addresses'):
            continue
        if reviewed_ads and key in ('johnshall_block_rules', 'block_rules'):
            continue
        if reviewed_voice and key == 'ip_rules' and type(before) is int:
            # Subtract only the exactly authorized new Voice entries; preserve
            # the independent guard for every other IP rule.
            before += stats['voice_prefixes'] - previous['voice_prefixes']
        if type(before) is not int or type(now) is not int or before < 0 or now < 0:
            raise ValueError(f'Invalid v2rayN baseline statistic: {key}')
        if before == 0:
            if now != 0:
                raise ValueError(f'Unexpected growth from zero: {key}')
        elif not lo * before <= now <= hi * before:
            raise ValueError(f'V2RAYN UPSTREAM ANOMALY: {key} {before} -> {now}; publication blocked')


def validate_voice_overlap(previous: set[str], current: set[str]) -> None:
    """Shared address-union comparison, independent of CIDR partitioning."""
    try:
        legacy.validate_voice_interval_overlap(previous, current)
    except ValueError as exc:
        raise ValueError('V2RAYN ' + str(exc)) from exc


def run(argv: list[str] | None = None) -> dict:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report-file', type=Path)
    p.add_argument('--upstream-file', type=Path)
    p.add_argument('--voice-file', type=Path)
    p.add_argument('--domain-dir', type=Path)
    p.add_argument('--ruleset-dir', type=Path)
    p.add_argument('--ai-dir', type=Path, help='Offline Gemini/Claude fixtures')
    args = p.parse_args(argv)

    before, old = load_published_baseline()
    original = args.upstream_file.read_bytes() if args.upstream_file else download(legacy.BASE_URL, 1_000_000)
    voice_raw = args.voice_file.read_bytes() if args.voice_file else download(legacy.VOICE_URL)
    fetched = {'johnshall': (legacy.BASE_URL, original),
               'voice': (legacy.VOICE_URL, voice_raw)}
    sources = {}
    unparsed_sources = {}
    for name, (url, fmt) in legacy.DOMAIN_SOURCES.items():
        raw = (args.domain_dir / f'{name}.txt').read_bytes() if args.domain_dir else download(url)
        fetched[name] = (url, raw)
        unparsed = []
        sources[name] = legacy.parse_domain_list(raw.decode('utf-8-sig'), fmt, unparsed=unparsed)
        unparsed_sources[name] = unparsed
        # Only an audited subset is promoted. Unknown third-party items stay
        # out; untranslated supported-source syntax remains review-only.
    rulesets = {}
    for name, (url, _) in legacy.RULESET_SOURCES.items():
        raw = (args.ruleset_dir / f'{name}.txt').read_bytes() if args.ruleset_dir else download(url)
        fetched[name] = (url, raw)
        rulesets[url] = legacy.parse_embedded_ruleset(raw.decode('utf-8-sig'))

    voice = legacy.parse_voice(voice_raw)
    auto = legacy.filter_auto_domains(list(dict.fromkeys(
        line for item in sources.values() for line in item)))
    manual = legacy.parse_manual(ROOT / 'config/manual-openai.rules')
    all_openai = list(dict.fromkeys(auto + manual))
    legacy.check_openai_rejections(all_openai, ROOT)
    voice_entries = [(*core.as_match(*rule.split(',', 1)), 'proxy') for rule in voice]
    openai_entries = [(*core.as_match(*rule.split(',', 1)), 'proxy') for rule in all_openai]
    extra = parse_user_extra(OPENAI_EXTRA.read_text(encoding='utf-8'))
    bitbrowser = core.load_bitbrowser_domains(BITBROWSER.read_text(encoding='utf-8'))
    effective_bitbrowser = selected_bitbrowser_domains(bitbrowser)
    if not effective_bitbrowser:
        raise ValueError('All approved BitBrowser domains removed; explicit review required')
    bit_entries = [(*core.as_match('DOMAIN-SUFFIX', name), 'proxy')
                   for name in effective_bitbrowser]
    processes = core.load_processes(PROCESSES.read_text(encoding='utf-8'))
    proc_entries = [('process', path, 'proxy') for path in processes]
    if 'BitBrowser.exe' not in processes:
        raise ValueError('Required BitBrowser.exe process proxy is absent')
    overrides = ({key: (args.ai_dir / (key + '.txt')).read_bytes() for key in ai_services.SOURCES}
                 if args.ai_dir else None)
    ai = ai_services.collect(download, source_overrides=overrides)
    ai_entries = {
        service: [(*core.as_match(*rule.split(',', 1)), 'proxy')
                  for rule in ai['rules'][service]]
        for service in ('gemini', 'claude')
    }

    base = original.decode('utf-8-sig')
    if len(original) < 1_000_000 or len(base.splitlines()) < 50_000:
        raise ValueError('Johnshall upstream truncated')
    if not base.rstrip().endswith(legacy.JOHNSHALL_FOOTER):
        raise ValueError('Johnshall footer changed or is missing')
    _, _, base_rules, tail = legacy.split_base(base)
    rewrite, mitm = tail.split('[MITM]', 1)
    if not any(s.strip() and not s.lstrip().startswith(('#', '[')) for s in rewrite.splitlines()):
        raise ValueError('Johnshall URL Rewrite section missing')
    if not re.search(r'(?m)^hostname\s*=\s*\S', mitm):
        raise ValueError('Johnshall MITM section missing')
    blocked, ordinary, johnshall_stats = core.johnshall_entries(base_rules, rulesets, legacy.inline_ruleset)
    # Explicit rule precedence. Ads are intentionally hoisted so a browser
    # process cannot bypass ad blocking. Local traffic always stays local.
    local = [
        {'remarks': 'Protect loopback & LAN IPs', 'outboundTag': 'direct',
         'ip': ['127.0.0.0/8', '::1/128', 'geoip:private'], 'enabled': True},
        {'remarks': 'Protect localhost', 'outboundTag': 'direct',
         'domain': ['full:localhost', 'domain:localhost.localdomain'], 'enabled': True},
    ]
    rules = (local + core.compact(blocked, 'Johnshall ads and tracking')
             + core.compact(proc_entries, 'BitBrowser verified process')
             + core.compact(bit_entries, 'BitBrowser selected domains')
             + core.compact(voice_entries, 'OpenAI official Voice IPs')
             + core.compact(openai_entries + extra, 'OpenAI reviewed and user extras')
             + core.compact(ai_entries['gemini'], 'Gemini approved rules')
             + core.compact(ai_entries['claude'], 'Claude approved rules')
             + core.compact(ordinary, 'Johnshall original order')
             + [{'remarks': 'Johnshall FINAL direct', 'outboundTag': 'direct',
                 'port': '0-65535', 'enabled': True}])
    conflicts = routing_conflicts.detect(blocked, bit_entries + voice_entries + openai_entries + extra
                                         + ai_entries['gemini'] + ai_entries['claude'])
    voice_counts = legacy.voice_address_counts(voice)
    original_stats = {**johnshall_stats, **voice_counts, 'voice_prefixes': len(voice),
                      'auto_domains': len(auto), 'manual_domains': len(manual),
                      'openai_user_extras': len(extra),
                      'bitbrowser_domains': len(effective_bitbrowser),
                      'bitbrowser_effective_domains': len(effective_bitbrowser),
                      'bitbrowser_input_domains': len(bitbrowser),
                      'bitbrowser_candidate_domains': sum(c in ('community', 'unverified') for _, c, _ in bitbrowser),
                      'official_bitbrowser_domains': sum(c == 'official' for _, c, _ in bitbrowser),
                      'user_requested_bitbrowser_domains': sum(c == 'user' for _, c, _ in bitbrowser),
                      'unverified_bitbrowser_domains': sum(c in ('community', 'unverified') for _, c, _ in bitbrowser),
                      'unparsed_community_rules_review_only': sum(len(x) for x in unparsed_sources.values()),
                      **ai['counts'], 'ai_review_candidates': len(ai['review_candidates'])}
    stats = core.validate_rules(rules, original_stats)
    output = core.json_bytes(rules)
    if len(output) < 500_000 or len(output) > 13_000_000:
        raise ValueError(f'Unexpected v2rayN output size: {len(output)} bytes')
    # Serialize/read back before publication: no incomplete or invalid JSON.
    if json.loads(output) != rules:
        raise AssertionError('JSON serialization round-trip failed')
    stats['json_bytes'] = len(output)
    # Accept only the same exact, reviewed source bytes and prior baseline.
    # The legacy authorization's count fields are adapted, not relaxed.
    previous_voice_rows = (old or {}).get('voice_rules', [])
    reviewed_voice = False
    reviewed_ads = False
    if old:
        prev = old['statistics']
        if (stats['voice_ipv4_addresses'] > 2 * prev['voice_ipv4_addresses']
                or stats['voice_prefixes'] > 2 * prev['voice_prefixes']):
            reviewed_voice = legacy.is_reviewed_voice_expansion(
                voice, '\n'.join(previous_voice_rows), voice_raw, old)
        if stats['johnshall_block_rules'] < .85 * prev['johnshall_block_rules']:
            old_legacy = {**old, 'statistics': {**prev,
                'retained_ad_rules': prev['johnshall_block_rules'],
                'mapped_proxy_to_johnshall_node': prev['johnshall_proxy_rules']}}
            new_legacy = {'retained_ad_rules': stats['johnshall_block_rules'],
                          'mapped_proxy_to_johnshall_node': stats['johnshall_proxy_rules']}
            reviewed_ads = legacy.is_reviewed_johnshall_ad_decrease(original, new_legacy, old_legacy)
    safety_check(stats, old, reviewed_voice=reviewed_voice, reviewed_ads=reviewed_ads)
    # Independent v2rayN voice baseline (not read from Shadowrocket output).
    # Existing state without this field gets one migration baseline.
    previous_voice = set(old.get('voice_rules', [])) if old else set()
    current_voice = set(voice)
    validate_voice_overlap(previous_voice, current_voice)
    ai_services.validate_safety(ai['counts'], old)
    next_sources = {name: {'url': url, 'sha256': hashlib.sha256(raw).hexdigest()}
                    for name, (url, raw) in fetched.items()}
    upstream_integrity.record_counts(next_sources, sources, rulesets, legacy.RULESET_SOURCES)
    upstream_integrity.validate_counts(next_sources, old, legacy.DOMAIN_SOURCES, legacy.RULESET_SOURCES)
    next_sources.update(ai['records'])
    state = {'schema_version': 2, 'output_sha256': hashlib.sha256(output).hexdigest(),
             'voice_rules': sorted(current_voice),
             'sources': next_sources, 'statistics': stats,
             'build_inputs_sha256': release_integrity.build_inputs_fingerprint('v2rayn'),
             'ai_counts': ai['counts'],
             'inputs_sha256': {
                 'manual_openai': hashlib.sha256((ROOT / 'config/manual-openai.rules').read_bytes()).hexdigest(),
                 'bitbrowser': hashlib.sha256(BITBROWSER.read_bytes()).hexdigest(),
                 'extra_openai': hashlib.sha256(OPENAI_EXTRA.read_bytes()).hexdigest(),
                 'verified_processes': hashlib.sha256(PROCESSES.read_bytes()).hexdigest(),
                 'manual_ai': ai['manual_sha256'],
                 'ai_review_decisions': ai['review_decisions_sha256'],
             }}
    changed = before != output
    source_changes = [name for name, value in next_sources.items()
                      if value != (old or {}).get('sources', {}).get(name)]
    report = {'build_success': True, 'config_changed': changed,
              'statistics': stats, 'changed_sources': source_changes,
              'source_count_deltas': upstream_integrity.count_deltas(next_sources, old),
              'stat_deltas': {k: val - old['statistics'][k] for k,val in stats.items()
                              if old and type(val) is int and type(old['statistics'].get(k)) is int},
              'ai_review_candidates': ai['review_candidates'],
              'ai_approved_rules': ai['rules'],
              'openai_observation': {'excluded': legacy.excluded_auto_rule_sources(sources, auto, unparsed_sources),
                  'common_rules': all_openai,
                  'client_only_rules': [('DOMAIN,' + value[5:]) if value.startswith('full:') else ('DOMAIN-SUFFIX,' + value[7:])
                                        for field, value, action in extra if value.startswith(('full:', 'domain:'))]},
              'ai_review_counts': ai['review_counts'],
              'routing_conflicts': conflicts,
              'warnings': [
                  'URL Rewrite and MITM are not v2rayN routing rules and cannot be carried over.',
                  'REJECT variants map to block; no-resolve is not a portable Xray routing modifier.',
                  'Ad-block rules are intentionally prioritized ahead of Johnshall routing and BitBrowser.',
                  'BitBrowser process interception requires user-verified executable path and Windows TUN.',
                  'Browser-internal proxies, DNS, WebRTC and IPv6 need client-side testing.',
                  'Gemini/Claude shared providers use exact host rules; new community-only candidates remain review-only.',
                  f'{sum(len(x) for x in unparsed_sources.values())} non-domain community source entries remain review-only, never auto-approved.',
              ]}
    # Mutate only v2rayN-owned artifacts, after all validations.
    atomically_write(CONFIG, output)
    atomically_write(STATE, (json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    if args.report_file:
        report['artifact_sha256'] = release_integrity.artifact_manifest(release_integrity.V2_FILES, ROOT)
        atomically_write(args.report_file, (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'build': 'success', 'changed': changed, 'statistics': stats}, ensure_ascii=False))
    return report


if __name__ == '__main__':
    try:
        run()
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        print(f'v2rayN build blocked: {exc}', file=sys.stderr)
        raise SystemExit(1)
