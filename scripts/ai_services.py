#!/usr/bin/env python3
"""Independently reviewed Gemini and Claude routing inputs.

v2fly is the source of community suggestions. MetaCubeX is a generated
comparison source, not an independent ownership attestation. New unfamiliar
shared-provider patterns stay review-only until allowlisted in this module or
in the manually reviewed rules file. Nothing is widened to a provider ASN/IP.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import calendar
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / 'config/ai-services.rules'
REVIEW_POLICY = ROOT / 'config/ai-review-decisions.json'
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
      aicode.googleapis.com aida.googleapis.com
      generativelanguage.googleapis.com
      labstailwind.pa.googleapis.com'''.split()),
    'claude': frozenset('''servd-anthropic-website.b-cdn.net
      http-intake.logs.us5.datadoghq.com o1158394.ingest.us.sentry.io'''.split()),
}
MANDATORY = {
    'gemini': {
        'DOMAIN-SUFFIX,gemini.google.com',
        'DOMAIN,generativelanguage.googleapis.com',
        'DOMAIN,antigravity-cli-auto-updater-974169037036.us-central1.run.app',
        'DOMAIN,antigravity-hub-auto-updater-974169037036.us-central1.run.app',
    },
    'claude': {
        'DOMAIN-SUFFIX,claude.ai', 'DOMAIN-SUFFIX,anthropic.com',
        'DOMAIN-SUFFIX,claude.com', 'DOMAIN-SUFFIX,claudeusercontent.com',
        'DOMAIN-SUFFIX,claudemcpcontent.com',
        'DOMAIN,browser-intake-us5-datadoghq.com',
        'DOMAIN,http-intake.logs.us5.datadoghq.com',
    },
}
VALID_HOST = re.compile(r'(?i)^[a-z0-9-]+(?:\.[a-z0-9-]+)+$')
BLACKLIST = ('doubleclick.net', 'google-analytics.com', 'googletagmanager.com')


def check_hostname(value: str) -> str:
    value = value.strip().lower()
    if not VALID_HOST.fullmatch(value):
        raise ValueError(f'Invalid AI source host {value!r}')
    return value


def parse_feed(text: str, fmt: str, service: str) -> list[tuple[str, str]]:
    if fmt not in ('v2fly', 'meta') or service not in ('gemini', 'claude'):
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


def add_months(day: date, months: int) -> date:
    total = day.year * 12 + day.month - 1 + months
    year, month = divmod(total, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def evaluate_review_policy(candidates: list[dict], policy: dict,
                           *, on: date | None = None) -> tuple[list[dict], dict]:
    """Reject/renew entries remain rejected; expiry only schedules review."""
    on = on or date.today()
    if (not isinstance(policy, dict) or set(policy) != {'version', 'default_review_months',
            'reminder_interval_days', 'rejected_rules'} or
            type(policy['version']) is not int or policy['version'] != 1 or
            type(policy['default_review_months']) is not int or
            not 1 <= policy['default_review_months'] <= 120 or
            type(policy['reminder_interval_days']) is not int or
            not 1 <= policy['reminder_interval_days'] <= 365 or
            not isinstance(policy['rejected_rules'], list)):
        raise ValueError('Invalid independent Gemini/Claude review policy')
    decisions = {}
    for item in policy['rejected_rules']:
        if not isinstance(item, dict) or set(item) != {'service', 'rule', 'reason', 'reviewed_at'}:
            raise ValueError('Malformed AI rejection decision')
        service, rule, reason, stamp = (item[x] for x in
                                        ('service', 'rule', 'reason', 'reviewed_at'))
        if service not in ('gemini', 'claude') or not isinstance(rule, str):
            raise ValueError('Invalid AI rejection rule type')
        kind, separator, host = rule.partition(',')
        if separator != ',' or kind not in ('DOMAIN', 'DOMAIN-SUFFIX'):
            raise ValueError('Invalid AI rejection rule type')
        # Human decisions are security controls: never silently miss a match
        # because an operator used uppercase, extra spaces or a trailing dot.
        if check_hostname(host) != host:
            raise ValueError('Noncanonical AI rejection rule; use lower-case DNS host without trailing dot')
        if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 2000:
            raise ValueError('AI rejection needs meaningful reason')
        try:
            reviewed = date.fromisoformat(stamp)
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid AI review date') from exc
        if reviewed > on:
            raise ValueError('AI rejection date cannot be in future')
        key = (service, rule)
        if key in decisions:
            raise ValueError(f'Duplicate AI rejection: {key}')
        decisions[key] = (item, reviewed)
    output = []
    counts = {'pending': 0, 'cooling': 0, 'due': 0}
    for candidate in candidates:
        item = dict(candidate)
        decision = decisions.get((item['service'], item['rule']))
        if decision is None:
            item.update(status='pending', reviewed_at=None, review_due_on=None)
            counts['pending'] += 1
        else:
            record, reviewed = decision
            due = add_months(reviewed, policy['default_review_months'])
            status = 'due' if on >= due else 'cooling'
            counts[status] += 1
            item.update(status=status, reviewed_at=reviewed.isoformat(),
                        review_due_on=due.isoformat(), reason=record['reason'])
        output.append(item)
    return output, counts


def approved_rule_overlaps(a: str, b: str) -> bool:
    """Whether two exact/suffix host rules can match the same hostname."""
    ak, ah = a.split(',', 1)
    bk, bh = b.split(',', 1)
    if ak == 'DOMAIN' and bk == 'DOMAIN':
        return ah == bh
    if ak == 'DOMAIN-SUFFIX' and bk == 'DOMAIN-SUFFIX':
        return ah == bh or ah.endswith('.' + bh) or bh.endswith('.' + ah)
    suffix, host = (ah, bh) if ak == 'DOMAIN-SUFFIX' else (bh, ah)
    return host == suffix or host.endswith('.' + suffix)


def check_rejection_conflicts(approved: dict[str, set[str]], policy: dict) -> None:
    """Human rejection may never silently lose to a manual/automatic allow."""
    for item in policy['rejected_rules']:
        service, rejected = item['service'], item['rule']
        for allowed in approved[service]:
            if approved_rule_overlaps(allowed, rejected):
                raise ValueError(f'AI approved/rejected rule conflict: {service}: {allowed} vs {rejected}')


def collect(download, *, manual_path: Path = MANUAL,
            review_policy_path: Path = REVIEW_POLICY,
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
    raw_candidates = [
        {'service': service, 'rule': rule, 'sources': sorted(sources),
         'reason': 'Unverified shared host or unapproved domain; not automatically routed'}
        for (service, rule), sources in sorted(candidates.items())
    ]
    policy_bytes = review_policy_path.read_bytes()
    policy = json.loads(policy_bytes.decode('utf-8-sig'))
    review_candidates, review_counts = evaluate_review_policy(raw_candidates, policy)
    check_rejection_conflicts(approved, policy)
    return {
        'rules': {service: sorted(rows) for service, rows in approved.items()},
        'records': records,
        'counts': {'gemini_domains': len(approved['gemini']),
                   'claude_domains': len(approved['claude']), **counts},
        'review_candidates': review_candidates,
        'review_counts': review_counts,
        'review_decisions_sha256': hashlib.sha256(policy_bytes).hexdigest(),
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
        # One-time 2026-11-23 reviewed reduction from 72 to 51 Gemini rules.
        # Shared Google login/CDN/Fonts/Play and generic Code Assist hosts were
        # removed, but two narrow Gemini App helpers remain.  The exact
        # baseline/feed counts and vetted manual set all need to match.
        # Subsequent runs again use the ordinary 75%-150% baseline guards.
        reviewed_gemini_narrowing = (
            key == 'gemini_domains' and before == 72 and after == 51
            and current.get('gemini_v2fly') == 49
            and current.get('gemini_metacubex') == 49
            and set(load_manual(MANUAL.read_text(encoding='utf-8'))['gemini']) == {
                'DOMAIN,jnn-pa.googleapis.com',
                'DOMAIN,waa-pa.clients6.google.com',
            }
        )
        if not reviewed_gemini_narrowing and not .75 * before <= after <= 1.50 * before:
            raise ValueError(f'AI SOURCE ANOMALY: {key}: {before} -> {after}; last good file retained')


def render_review_queue(data: dict) -> str:
    rows = ['# Gemini / Claude 上游待审核及到期复审', '',
            '候选未自动放行。拒绝决策写入 `config/ai-review-decisions.json`，默认六个月复审；'
            '到期仅提醒，不自动批准。', '',
            '| 服务 | 候选规则 | 来源 | 状态 | 上次审核 | 到期复审 |',
            '|---|---|---|---|---|---|']
    labels = {'pending': '待审核', 'cooling': '已拒绝，复审未到期', 'due': '到期复审（未放行）'}
    for item in data['review_candidates']:
        rows.append(f"| {item['service']} | `{item['rule']}` | {', '.join(item['sources'])} | "
                    f"{labels[item['status']]} | {item.get('reviewed_at') or '—'} | "
                    f"{item.get('review_due_on') or '—'} |")
    if not data['review_candidates']:
        rows.append('| — | — | — | 无未审核的新来源项 | — | — |')
    return '\n'.join(rows) + '\n'
