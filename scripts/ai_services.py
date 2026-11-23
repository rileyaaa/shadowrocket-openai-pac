#!/usr/bin/env python3
"""Independently reviewed Gemini and Claude routing inputs.

v2fly is the source of community suggestions. MetaCubeX is a generated
comparison source, not an independent ownership attestation. New unfamiliar
shared-provider patterns stay review-only until allowlisted in this module or
in the manually reviewed rules file. Nothing is widened to a provider ASN/IP.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / 'config/ai-services.rules'
SOURCES = {
    'gemini_v2fly': ('gemini', 'v2fly', 'https://raw.githubusercontent.com/v2fly/domain-list-community/master/data/google-deepmind'),
    'gemini_metacubex': ('gemini', 'meta', 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/google-gemini.list'),
    'claude_v2fly': ('claude', 'v2fly', 'https://raw.githubusercontent.com/v2fly/domain-list-community/master/data/anthropic'),
    'claude_metacubex': ('claude', 'meta', 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/anthropic.list'),
}
# These are deliberately narrower than all of google.com and all of
# googleapis.com. More dedicated subdomains within a vetted suffix can be
# taken from the community feeds. Ownership of some Claude-branded community
# domains is uncertain: they are intentionally NOT in this allowlist.
APPROVED_SUFFIXES = {
    'gemini': frozenset('''deepmind.com deepmind.google generativeai.google makersuite.google.com
        ai.studio aistudio.google.com bard.google.com gemini.google gemini.google.com
        gemini.gstatic.com notebook.google notebook.google.com notebooklm.google
        notebooklm.google.com jules.google jules.google.com labs.google labs.google.com
        flow.google flow.google.com opal.google opal.google.com antigravity.google
        antigravity-unleash.goog stitch.withgoogle.com'''.split()),
    'claude': frozenset('''anthropic.com claude.ai claude.com claude.dev
        claudeusercontent.com claudemcpcontent.com claude.app clau.de claude.new
        claude.site'''.split()),
}
# Exact shared vendor endpoints reviewed from current community entries or
# Google Gemini App / Code Assist official network documentation.
# New vendor subdomains are NEVER automatically promoted.
APPROVED_HOSTS = {
    'gemini': frozenset('''ai.google.dev alkalicore-pa.clients6.google.com
      alkalimakersuite-pa.clients6.google.com webchannel-alkalimakersuite-pa.clients6.google.com
      geminiweb-pa.clients.google.com geminiweb-pa.clients6.google.com
      appsgenaiserver-pa.clients.google.com appsgenaiserver-pa.clients6.google.com
      appsgenaiserver-pa.googleapis.com cloudaicompanion.googleapis.com
      cloudcode-pa.googleapis.com daily-cloudcode-pa.googleapis.com
      notebooklm-pa.googleapis.com notebooklm.googleapis.com
      antigravity-pa.googleapis.com antigravity.googleapis.com
      robinfrontend-pa.googleapis.com aisandbox-pa.googleapis.com
      aicode.googleapis.com aida.googleapis.com proactivebackend-pa.googleapis.com
      generativelanguage.googleapis.com geller-pa.googleapis.com
      labstailwind.pa.googleapis.com'''.split()),
    'claude': frozenset('''servd-anthropic-website.b-cdn.net
      http-intake.logs.us5.datadoghq.com o1158394.ingest.us.sentry.io'''.split()),
}
MANDATORY = {
    'gemini': {'DOMAIN-SUFFIX,gemini.google.com', 'DOMAIN,generativelanguage.googleapis.com'},
    'claude': {'DOMAIN-SUFFIX,claude.ai', 'DOMAIN-SUFFIX,anthropic.com'},
}
VALID_HOST = re.compile(r'(?i)^[a-z0-9-]+(?:\.[a-z0-9-]+)+$')
BLACKLIST = ('doubleclick.net', 'google-analytics.com', 'googletagmanager.com')


def check_hostname(value: str) -> str:
    value = value.strip().lower()
    if not VALID_HOST.fullmatch(value):
        raise ValueError(f'Invalid AI source host {value!r}')
    return value


def parse_feed(text: str, fmt: str, service: str) -> list[tuple[str, str]]:
    if fmt not in ('v2fly', 'meta') or service not in SOURCES['gemini_v2fly'][0:1] + ('claude',):
        raise ValueError('Unknown Gemini/Claude feed format or service')
    rows = []
    for line in text.lstrip('\ufeff').splitlines():
        row = line.strip()
        if not row or row.startswith('#'):
            continue
        row = row.split(' #', 1)[0].split(' @', 1)[0].strip()
        if row.startswith('include:') or row.startswith('regexp:') or ':' in row and not row.startswith('full:'):
            raise ValueError(f'Unexpected AI feed syntax (review before publishing): {row}')
        if fmt == 'v2fly':
            kind, name = ('DOMAIN', row[5:]) if row.startswith('full:') else ('DOMAIN-SUFFIX', row)
        else:
            kind, name = ('DOMAIN-SUFFIX', row[2:]) if row.startswith('+.') else ('DOMAIN', row)
        rows.append((kind, check_hostname(name)))
    minimum = 30 if service == 'gemini' else 12
    if not minimum <= len(rows) <= 500 or len(set(rows)) < minimum:
        raise ValueError(f'AI feed incomplete or unexpectedly large: {service}/{fmt}: {len(rows)}')
    return list(dict.fromkeys(rows))


def is_approved(service: str, kind: str, domain: str) -> bool:
    if domain in APPROVED_HOSTS[service]:
        return True
    return any(domain == suffix or domain.endswith('.' + suffix)
               for suffix in APPROVED_SUFFIXES[service])


def normalize_approved(service: str, kind: str, domain: str) -> tuple[str, str]:
    # When the upstream says 'domain:shared.googleapis.com' its broad suffix
    # would catch unrelated nested tenants; preserve only the approved host.
    if domain in APPROVED_HOSTS[service]:
        return ('DOMAIN', domain)
    # Dedicated service domains keep their intended suffix semantics.
    if kind == 'DOMAIN-SUFFIX':
        return kind, domain
    return 'DOMAIN', domain


def load_manual(text: str) -> dict[str, list[str]]:
    parsed = {'gemini': [], 'claude': []}
    for original in text.splitlines():
        line = original.strip()
        if not line or line.startswith('#'):
            continue
        pieces = [part.strip() for part in line.split(',')]
        if len(pieces) != 3:
            raise ValueError(f'Unexpected manual AI rule: {line}')
        service, kind, host = pieces
        service = service.lower()
        kind = kind.upper()
        host = check_hostname(host)
        if service not in parsed or kind not in ('DOMAIN', 'DOMAIN-SUFFIX'):
            raise ValueError(f'Unsupported manual AI rule: {line}')
        if any(host == ad or host.endswith('.' + ad) for ad in BLACKLIST):
            raise ValueError(f'Ad/tracker is not a Gemini/Claude proxy exception: {line}')
        if kind == 'DOMAIN-SUFFIX' and not any(host == s for s in APPROVED_SUFFIXES[service]):
            raise ValueError(f'Overbroad unreviewed manual AI suffix: {line}')
        parsed[service].append(kind + ',' + host)
    if not parsed['gemini'] or not parsed['claude']:
        raise ValueError('Missing manually reviewed Gemini/Claude supplemental rules')
    return {service: list(dict.fromkeys(items)) for service, items in parsed.items()}


def collect(download, *, manual_path: Path = MANUAL,
            source_overrides: dict[str, bytes] | None = None) -> dict:
    """Collect four *current* sources and reviewed manual rules; no old snapshots.

    `download(url, minimum)` must perform HTTPS integrity checking and fail on
    download errors. source_overrides is for fixture-only offline tests.
    """
    approved = {'gemini': set(), 'claude': set()}
    candidates = defaultdict(set)
    records = {}
    counts = {}
    for key, (service, fmt, url) in SOURCES.items():
        raw = (source_overrides[key] if source_overrides is not None
               else download(url, 100))
        if not isinstance(raw, bytes) or not 100 <= len(raw) <= 100_000:
            raise ValueError(f'Invalid Gemini/Claude source bytes: {key}')
        parsed = parse_feed(raw.decode('utf-8-sig'), fmt, service)
        counts[key] = len(parsed)
        records[key] = {'url': url, 'sha256': hashlib.sha256(raw).hexdigest(), 'rule_count': len(parsed)}
        for kind, host in parsed:
            if is_approved(service, kind, host):
                safe_kind, safe_host = normalize_approved(service, kind, host)
                approved[service].add(safe_kind + ',' + safe_host)
            else:
                candidates[(service, kind + ',' + host)].add(key)
    manual = load_manual(manual_path.read_text(encoding='utf-8'))
    for service, extras in manual.items():
        approved[service].update(extras)
    for service in approved:
        if not MANDATORY[service].issubset(approved[service]):
            raise ValueError(f'Missing mandatory approved {service} domain')
        if len(approved[service]) < (25 if service == 'gemini' else 8):
            raise ValueError(f'Approved {service} set unexpectedly small')
    return {
        'rules': {service: sorted(rows) for service, rows in approved.items()},
        'records': records,
        'counts': {'gemini_domains': len(approved['gemini']),
                   'claude_domains': len(approved['claude']), **counts},
        'review_candidates': [
            {'service': service, 'rule': rule, 'sources': sorted(sources),
             'reason': 'Unverified shared host or unapproved domain; not automatically routed'}
            for (service, rule), sources in sorted(candidates.items())
        ],
        'manual_sha256': hashlib.sha256(manual_path.read_bytes()).hexdigest(),
    }


def validate_safety(current: dict, previous: dict | None) -> None:
    if previous is None:
        return
    old = previous.get('ai_counts', {})
    if not isinstance(old, dict) or not old:
        return  # one-time migration from the pre-Gemini/Claude output
    for key in ('gemini_domains', 'claude_domains', *SOURCES):
        before, after = old.get(key), current.get(key)
        if type(before) is not int or type(after) is not int or before < 1:
            raise ValueError(f'Invalid AI safety baseline for {key}')
        if not .75 * before <= after <= 1.50 * before:
            raise ValueError(f'AI SOURCE ANOMALY: {key}: {before} -> {after}; last good file retained')


def render_review_queue(data: dict) -> str:
    rows = ['# Gemini / Claude 上游待审核规则', '',
            '这些规则未获自动批准，不会进入代理；人工核实来源与最小匹配范围后再修改允许列表。', '',
            '| 服务 | 候选规则 | 来源 | 状态 |', '|---|---|---|---|']
    for item in data['review_candidates']:
        rows.append(f"| {item['service']} | `{item['rule']}` | {', '.join(item['sources'])} | 待核实，不自动放行 |")
    if not data['review_candidates']:
        rows.append('| — | — | — | 无未审核的新来源项 |')
    return '\n'.join(rows) + '\n'
