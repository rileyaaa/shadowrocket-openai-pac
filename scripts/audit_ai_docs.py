#!/usr/bin/env python3
"""Weekly *advisory* comparison of official Gemini/Claude network documents.

Never auto-approves domains and never blocks the daily rule builders. Cloudflare
or anti-bot failures leave the last reviewed snapshot untouched and raise a
warning in the single combined Telegram report instead of freezing releases.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'data/ai-official-docs.json'
REVIEW = ROOT / 'data/ai-docs-review.md'
SOURCES = {
    'gemini_app_firewall': ('https://knowledge.workspace.google.com/admin/generative-ai/gemini-app/gemini-app-firewall-settings', 'gemini'),
    'claude_code_network': ('https://code.claude.com/docs/en/network-config', 'claude'),
}
HOST = re.compile(r'(?i)(?<![a-z0-9-])(?:\*\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,63}(?![a-z0-9-])')
ALLOWED_TAILS = {
    'gemini': ('google.com', 'googleapis.com', 'googleusercontent.com', 'gstatic.com',
               'google.dev', 'google', 'deepmind.com', 'withgoogle.com', 'google.ai',
               'clients6.google.com', 'ai.studio', 'goog', 'run.app'),
    'claude': ('anthropic.com', 'claude.ai', 'claude.com', 'claudeusercontent.com',
               'datadoghq.com', 'sentry.io', 'b-cdn.net', 'googleapis.com', 'claudemcpcontent.com'),
}

class ExtractText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.ignore = 0
    def handle_starttag(self, tag: str, attrs):
        if tag in ('style', 'script'):
            self.ignore += 1
    def handle_endtag(self, tag: str):
        if tag in ('style', 'script') and self.ignore:
            self.ignore -= 1
    def handle_data(self, data: str):
        if not self.ignore:
            self.parts.append(data)


ADVISORY_EXACT_HOSTS = {
    'claude': frozenset({'browser-intake-us5-datadoghq.com'}),
    'gemini': frozenset(),
}


def observed_hosts(content: str) -> set[str]:
    parser = ExtractText()
    parser.feed(content)
    return {h.lower() for h in HOST.findall(' '.join(parser.parts))}


def extract_hosts(content: str, service: str) -> list[str]:
    hosts = {h for h in observed_hosts(content) if
             h.removeprefix('*.') in ADVISORY_EXACT_HOSTS[service] or
             any(h.removeprefix('*.') == end or h.removeprefix('*.').endswith('.' + end)
                 for end in ALLOWED_TAILS[service])}
    limit = 10 if service == 'gemini' else 3
    if not limit <= len(hosts) <= 300:
        raise ValueError(f'Official {service} doc parse incomplete or unexpectedly large: {len(hosts)}')
    if service == 'claude' and not {'claude.ai', 'claude.com'}.issubset({h.removeprefix('*.') for h in hosts}):
        raise ValueError('Official Claude network document missing key first-party hostnames')
    return sorted(hosts)


def fetch_doc(url: str) -> str:
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; AI domain change audit)',
                                     'Accept-Encoding': 'identity'})
    with urlopen(request, timeout=22) as response:
        if response.status != 200 or response.headers.get('Content-Range'):
            raise ValueError(f'Official page returned partial/non-200 HTTP {response.status}')
        declared = response.headers.get('Content-Length')
        if declared is not None:
            if not re.fullmatch(r'[0-9]+', declared.strip()):
                raise ValueError('Invalid official page Content-Length')
            declared = int(declared)
            if not 1000 <= declared <= 2_500_000:
                raise ValueError('Official page incomplete or oversized')
        body = response.read(2_500_001)
        if not 1000 <= len(body) <= 2_500_000:
            raise ValueError('Official page incomplete or oversized')
        if declared is not None and len(body) != declared:
            raise ValueError('Official page truncated')
        return body.decode('utf-8')


def scheduled_due(on, event, old):
    if event != 'schedule':
        return False
    sunday = on - timedelta(days=(on.weekday()+1) % 7)
    stamp = (old or {}).get('checked_on')
    if stamp is None:
        return True
    last = date.fromisoformat(stamp)
    if last > on:
        raise ValueError('Future official documentation baseline date')
    return last < sunday


def coverage_for(service, hosts, approved):
    import ai_services
    result = {}
    for client, rules in approved.items():
        uncovered = []
        for host in hosts:
            candidate = ('DOMAIN-SUFFIX,' + host[2:]) if host.startswith('*.') else 'DOMAIN,' + host
            if not any(ai_services.approved_rule_covers(rule, candidate)
                       for rule in rules.get(service, [])):
                uncovered.append(host)
        result[client] = uncovered
    return result


def validate_advisory(status, paths):
    from release_integrity import digest, ROOT
    report_path = status.get('reports', {}).get('official_docs')
    if not report_path:
        return []  # no advisory run
    report = json.loads(Path(report_path).read_text(encoding='utf-8'))
    if not isinstance(report, dict):
        raise ValueError('Invalid official docs advisory report')
    if report.get('checked') is False:
        return []
    manifest = report.get('artifact_sha256')
    if report.get('checked') is not True or not isinstance(manifest, dict) or set(manifest) != set(paths):
        raise ValueError('Missing official docs advisory manifest')
    for name in paths:
        if digest(ROOT / name) != manifest[name]:
            raise ValueError('Official docs advisory digest mismatch: ' + name)
    return list(paths)


def run(argv: list[str] | None = None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--force',action='store_true')
    p.add_argument('--report-file',type=Path)
    p.add_argument('--source-dir',type=Path,help='offline fixtures for tests and review')
    p.add_argument('--shadow-report', type=Path)
    p.add_argument('--v2-report', type=Path)
    args=p.parse_args(argv)
    on = datetime.now(ZoneInfo('Asia/Taipei')).date()
    old=json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else None
    weekly = scheduled_due(on, os.environ.get('GITHUB_EVENT_NAME'), old)
    if not (args.force or weekly):
        report={'checked': False, 'changed': False, 'detail': 'No weekly audit due (catch-up follows failed/missed Sunday)'}
        if args.report_file:
            args.report_file.write_text(json.dumps(report,ensure_ascii=False)+'\n',encoding='utf-8')
        print('Official AI documentation audit skipped; not weekly schedule')
        return report
    from release_integrity import validate_release
    approved = {}
    for client, path in (('shadowrocket_ai', args.shadow_report), ('v2rayn', args.v2_report)):
        if path and path.is_file():
            try:
                approved[client] = validate_release(client, {'reports': {client: str(path)}})['ai_approved_rules']
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                print(f'::warning::Docs coverage unavailable for {client}: {type(exc).__name__}')
    current={}
    comparisons=[]
    for key,(url,service) in SOURCES.items():
        html=((args.source_dir / (key+'.html')).read_text(encoding='utf-8')
              if args.source_dir else fetch_doc(url))
        hosts=extract_hosts(html,service)
        # Unrecognized visible hostnames are advisory-only, potentially
        # navigation/text false positives. Never silently filter them out.
        other=sorted(observed_hosts(html)-set(hosts))
        if len(other)>500:
            raise ValueError('Too many unclassified official-document hostnames')
        signature=hashlib.sha256(json.dumps([hosts,other]).encode()).hexdigest()
        coverage = coverage_for(service, hosts, approved)
        current[key]={'url':url,'sha256':signature,'hosts':hosts,'other_hosts':other,
                      'uncovered_by_client':coverage}
        previous_record=(old or {}).get('sources',{}).get(key,{})
        previous=previous_record.get('hosts',[])
        if previous:
            added=sorted(set(hosts)-set(previous))
            removed=sorted(set(previous)-set(hosts))
            before_other=previous_record.get('other_hosts',[])
            other_added=sorted(set(other)-set(before_other))
            other_removed=sorted(set(before_other)-set(other))
            if added or removed or other_added or other_removed or coverage != previous_record.get('uncovered_by_client'):
                comparisons.append({'service':service,'source':key,'added':added,'removed':removed,
                                    'other_added':other_added,'other_removed':other_removed,
                                    'uncovered_by_client':coverage})
        else:
            comparisons.append({'service':service,'source':key,'added':hosts,'removed':[],
                                'other_added':other,'other_removed':[],
                                'uncovered_by_client':coverage,'initial_baseline':True})
    # Never overwrite unresolved advisory findings from earlier weeks.
    data={'schema_version':1,'checked_on':on.isoformat(),'sources':current}
    from build_v2rayn import atomically_write
    state_bytes=(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode()
    if comparisons or not REVIEW.exists():
        previous_review = REVIEW.read_text(encoding='utf-8') if REVIEW.exists() else (
            '# Gemini / Claude 官方網路文件變更待審\n\n'
            '此處保留歷次尚未清理的觀察紀錄；任何候選都不會自動加入代理。\n')
        date_stamp = datetime.now(ZoneInfo('Asia/Taipei')).strftime('%Y-%m-%d')
        lines = [f'## {date_stamp} — 官方文件變更', '']
        for item in comparisons:
            lines += [f"### {item['service']} — {item['source']}"]
            lines += [f'- 新增：`{x}`' for x in item['added']]
            lines += [f'- 移除：`{x}`' for x in item['removed']]
            lines += [f'- 未分类主机新增（仅观察）：`{x}`' for x in item.get('other_added', [])]
            lines += [f'- 未分类主机移除：`{x}`' for x in item.get('other_removed', [])]
            for client in ('shadowrocket_ai', 'v2rayn'):
                coverage = item.get('uncovered_by_client', {})
                if client not in coverage:
                    lines.append(f'- {client}：覆盖状态待核对（无有效建置报告）')
                else:
                    lines.append(f'- {client}：{len(coverage[client])} 项未由当前审核规则完整覆盖，仅供人工确认')
                    lines += [f'  - {host}' for host in coverage[client]]
        review_text = previous_review.rstrip() + '\n\n' + '\n'.join(lines) + '\n'
        atomically_write(REVIEW, review_text.encode('utf-8'))
    if not STATE.exists() or STATE.read_bytes()!=state_bytes:
        atomically_write(STATE,state_bytes)
    report={'checked':True,'changed':bool(comparisons),'changes':comparisons,
            'sources':list(SOURCES),'initial_baseline':old is None,
            'artifact_sha256': {'data/ai-official-docs.json': hashlib.sha256(STATE.read_bytes()).hexdigest(),
                                'data/ai-docs-review.md': hashlib.sha256(REVIEW.read_bytes()).hexdigest()}}
    if args.report_file:
        args.report_file.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return report

if __name__ == '__main__':
    try:
        run()
    except (OSError,ValueError,UnicodeError) as exc:
        print(f'Official AI docs advisory audit unavailable: {type(exc).__name__}: {exc}',file=sys.stderr)
        raise SystemExit(1)
