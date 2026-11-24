#!/usr/bin/env python3
"""Pure, ordered Shadowrocket -> v2rayN custom-rule conversion.

Rule objects are a v2rayN GUI import format, NOT a full core configuration.
Unsupported source semantics raise rather than silently losing matches.
"""
from __future__ import annotations

from collections import Counter
from pathlib import PureWindowsPath
import ipaddress
import json
import re

VALID_ACTIONS = frozenset({'proxy', 'direct', 'block'})
DOMAIN_TYPES = {'DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD', 'DOMAIN-WILDCARD', 'GEOSITE'}
IP_TYPES = {'IP-CIDR', 'IP-CIDR6', 'GEOIP'}
REJECTIONS = {'REJECT', 'REJECT-DROP', 'REJECT-NO-DROP'}
DOMAIN_NAME = re.compile(r'^[a-z0-9_.*?\-]+(?:\.[a-z0-9_.*?\-]+)*$', re.I)
MAX_ITEMS_PER_OBJECT = 1200


class UnsupportedRule(ValueError):
    """An upstream rule cannot be represented with verified v2rayN semantics."""


def as_match(kind: str, value: str) -> tuple[str, str]:
    kind, value = kind.upper(), value.strip()
    if kind in DOMAIN_TYPES:
        if not value or not DOMAIN_NAME.fullmatch(value):
            raise UnsupportedRule(f'Invalid domain {kind},{value}')
        if kind != 'DOMAIN-WILDCARD' and ('*' in value or '?' in value):
            raise UnsupportedRule(f'Unexpected wildcard in {kind},{value}')
        if kind in ('DOMAIN', 'DOMAIN-SUFFIX') and any(not label for label in value.split('.')):
            raise UnsupportedRule(f'Empty hostname label in {kind},{value}')
        if kind == 'GEOSITE' and not re.fullmatch(r'[a-z0-9_-]+', value, re.I):
            raise UnsupportedRule(f'Invalid geosite tag {value}')
        if kind == 'DOMAIN-WILDCARD':
            if value.lower() == 'chatgpt-async-webps-prod-*.webpubsub.azure.com':
                # The variable component in this known host is exactly one DNS label.
                return 'domain', r'regexp:^chatgpt-async-webps-prod-[^.]+\.webpubsub\.azure\.com$'
            # Generic wildcard semantics are preserved for other rules.
            return 'domain', 'regexp:^' + re.escape(value.lower()).replace(r'\*', '.*').replace(r'\?', '.') + '$'
        return 'domain', {
            'DOMAIN': 'full:', 'DOMAIN-SUFFIX': 'domain:',
            'DOMAIN-KEYWORD': 'keyword:', 'GEOSITE': 'geosite:',
        }[kind] + value.lower()
    if kind in IP_TYPES:
        if kind == 'GEOIP':
            if not re.fullmatch(r'[a-z0-9_-]{2,40}', value, re.I):
                raise UnsupportedRule(f'Invalid GeoIP {value}')
            return 'ip', 'geoip:' + value.lower()
        try:
            net = ipaddress.ip_network(value, strict=False)
        except ValueError as exc:
            raise UnsupportedRule(f'Invalid CIDR {value}') from exc
        # Johnshall sometimes labels IPv6 CIDRs with IP-CIDR rather than
        # IP-CIDR6. The literal CIDR determines actual family; do not widen.
        if kind == 'IP-CIDR6' and net.version != 6:
            raise UnsupportedRule(f'CIDR family mismatch: {kind},{value}')
        return 'ip', str(net)
    raise UnsupportedRule(f'Unsupported rule type: {kind}')


def parse_rule(raw: str) -> tuple[str, str, str] | None:
    """Parse one source rule, including strict modifier handling."""
    stripped = raw.strip()
    if not stripped or stripped.startswith(('#', ';')):
        return None
    parts = [part.strip() for part in stripped.split(',')]
    kind = parts[0].upper()
    if kind == 'FINAL':
        if len(parts) != 2 or parts[1].lower() != 'direct':
            raise UnsupportedRule(f'Unexpected final route: {stripped}')
        return 'FINAL', '', 'direct'
    if len(parts) < 3:
        raise UnsupportedRule(f'Malformed source rule: {stripped}')
    policy = parts[2].upper()
    if policy in REJECTIONS:
        action = 'block'
    elif policy in {'PROXY', 'DIRECT'}:
        action = policy.lower()
    else:
        raise UnsupportedRule(f'Unknown policy {policy}: {stripped}')
    modifiers = [p.lower() for p in parts[3:]]
    if modifiers and (kind not in IP_TYPES or modifiers != ['no-resolve']):
        raise UnsupportedRule(f'Unsupported modifiers: {stripped}')
    field, value = as_match(kind, parts[1])
    return field, value, action


def compact(entries: list[tuple[str, str, str]], prefix: str) -> list[dict]:
    """Merge only contiguous equal-action, equal-field rules: preserves order."""
    result: list[dict] = []
    for field, value, action in entries:
        if field not in ('ip', 'domain', 'process') or action not in VALID_ACTIONS:
            raise ValueError(f'Unexpected converted entry {field},{action}')
        if (result and result[-1]['outboundTag'] == action
                and list(k for k in ('domain', 'ip', 'process') if k in result[-1]) == [field]
                and len(result[-1][field]) < MAX_ITEMS_PER_OBJECT):
            result[-1][field].append(value)
        else:
            result.append({'remarks': f'{prefix} / {action}', 'outboundTag': action,
                           field: [value], 'enabled': True})
    return result


def johnshall_entries(source: str, rulesets: dict[str, list[str]], inline_ruleset,
                       *, minimum_lines: int = 50000) -> tuple[list[tuple], list[tuple], dict]:
    """Convert the full Johnshall [Rule] body; every unsupported rule fails closed.

    Blocks are hoisted (explicit policy choice for BitBrowser ad protection).
    Other Johnshall first-match order is unchanged.
    """
    lines = source.splitlines()
    if len(lines) < minimum_lines:
        raise ValueError(f'Johnshall upstream unexpectedly small: {len(lines)}')
    blocked, ordinary, unsupported = [], [], []
    proxy, ads, finals, embedded = 0, 0, 0, 0
    final_line = None
    last_active_line = None
    for line_number, raw in enumerate(lines, 1):
        try:
            expanded = inline_ruleset(raw, rulesets)
        except ValueError as exc:
            raise UnsupportedRule(f'Johnshall {line_number}: {exc}') from exc
        for item in expanded:
            if item.startswith('# Embedded verified RULE-SET:'):
                embedded += 1
            try:
                entry = parse_rule(item)
                if entry is None:
                    continue
                last_active_line = line_number
                if entry[0] == 'FINAL':
                    finals += 1
                    final_line = line_number
                    continue
                field, value, action = entry
                if action == 'block':
                    blocked.append(entry)
                    ads += 1
                else:
                    ordinary.append(entry)
                    proxy += (action == 'proxy')
            except (UnsupportedRule, ValueError) as exc:
                unsupported.append(f'{line_number}: {str(exc)}')
                if len(unsupported) >= 20:
                    break
        if unsupported:
            break
    if unsupported:
        raise UnsupportedRule('Unsupported Johnshall rules (publication aborted): ' + '; '.join(unsupported))
    # Reject pathological same-count replacement by duplicated rules.
    # The threshold leaves room for natural upstream aliases and duplicates.
    if ads >= 20000 and len(set(blocked)) < ads * .90:
        raise ValueError('Johnshall ad unique coverage collapsed')
    if proxy >= 10000 and (
            len({entry for entry in ordinary if entry[2] == 'proxy'}) < proxy * .90
            or len(set(ordinary)) < len(ordinary) * .90):
        raise ValueError('Johnshall proxy unique coverage collapsed')
    if finals == 1 and final_line != last_active_line:
        raise ValueError('Johnshall FINAL must be the last effective routing rule')
    if finals != 1 or proxy < 10000 or ads < 20000:
        raise ValueError(f'Johnshall guard failed: FINAL={finals} proxy={proxy} block={ads}')
    return blocked, ordinary, {'johnshall_lines': len(lines), 'johnshall_proxy_rules': proxy,
                               'johnshall_block_rules': ads, 'external_lists_embedded': embedded,
                               'unsupported_rules': 0}


def load_bitbrowser_domains(text: str) -> list[tuple[str, str, str]]:
    result = []
    seen = set()
    for line_number, raw in enumerate(text.splitlines(), 1):
        raw = raw.strip()
        if not raw or raw.startswith('#'):
            continue
        fields = [f.strip() for f in raw.split('|')]
        if len(fields) != 4:
            raise ValueError(f'BitBrowser data line {line_number}: expected domain|class|purpose|url')
        name, confidence, purpose, url = fields
        name = name.lower()  # DNS names are case-insensitive, including duplicate checks.
        if confidence not in ('official', 'community', 'user', 'unverified'):
            raise ValueError(f'BitBrowser confidence invalid at line {line_number}')
        if not purpose or not url.startswith('https://') or not DOMAIN_NAME.fullmatch(name) or '*' in name or '?' in name:
            raise ValueError(f'BitBrowser domain invalid at line {line_number}')
        if name in seen:
            raise ValueError(f'Duplicate BitBrowser domain: {name}')
        seen.add(name)
        result.append((name, confidence, purpose))
    if len(result) < 10:
        raise ValueError('BitBrowser domain list is unexpectedly small')
    return result


def load_processes(text: str) -> list[str]:
    """A dedicated BitBrowser.exe name or user-confirmed absolute paths only.

    Generic chrome.exe / firefox.exe are intentionally forbidden.
    """
    results = []
    for raw in text.splitlines():
        value = raw.strip()
        if not value or value.startswith('#'):
            continue
        if value.lower() == 'bitbrowser.exe':
            if 'BitBrowser.exe' not in results:
                results.append('BitBrowser.exe')
            continue
        if ('/' not in value and '\\' not in value) or not value.lower().endswith('.exe'):
            raise ValueError('BitBrowser process must be BitBrowser.exe or a verified absolute .exe path')
        if not re.match(r'^[A-Za-z]:\\', value):
            raise ValueError('BitBrowser process path must be absolute Windows path')
        parts = PureWindowsPath(value).parts
        if '..' in parts:
            raise ValueError('BitBrowser process path must not contain parent-directory traversal')
        if parts[-1].lower() != 'bitbrowser.exe' or not any(
                'bitbrowser' in part.lower() for part in parts[1:-1]):
            raise ValueError('Only a dedicated BitBrowser installation executable may be routed')
        if not any(PureWindowsPath(value) == PureWindowsPath(old) for old in results):
            results.append(value)
    return results


def validate_rules(rules: list[dict], stats: dict) -> dict:
    if not rules or not isinstance(rules, list):
        raise ValueError('Empty routing rules')
    final = rules[-1]
    if final.get('port') != '0-65535' or final.get('outboundTag') != 'direct':
        raise ValueError('Missing explicit final DIRECT fallback')
    counters = Counter()
    for item in rules:
        if not isinstance(item, dict) or item.get('outboundTag') not in VALID_ACTIONS or item.get('enabled') is not True:
            raise ValueError('Invalid rule object')
        fields = [k for k in ('domain', 'ip', 'process') if k in item]
        if len(fields) > 1 or (not fields and item is not final):
            raise ValueError('Invalid condition combination')
        if not fields and item.get('port') != '0-65535':
            raise ValueError('Unexpected catchall')
        for field in fields:
            if not isinstance(item[field], list) or not item[field] or not all(isinstance(s, str) and s for s in item[field]):
                raise ValueError('Empty/invalid matching values')
            counters[field] += len(item[field])
        counters[item['outboundTag']] += sum(len(item[k]) for k in fields) or 1
    if counters['block'] < 20000 or counters['proxy'] < 10000:
        raise ValueError('Suspiciously small block/proxy coverage')
    return {'routing_objects': len(rules), 'domain_rules': counters['domain'],
            'ip_rules': counters['ip'], 'process_rules': counters['process'],
            'proxy_rules': counters['proxy'], 'direct_rules': counters['direct'],
            'block_rules': counters['block'], **stats}


def json_bytes(rules: list[dict]) -> bytes:
    return (json.dumps(rules, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
