#!/usr/bin/env python3
"""Weekly *advisory* comparison of official Gemini/Claude network documents.

Never auto-approves domains and never blocks the daily rule builders. Cloudflare
or anti-bot failures leave the last reviewed snapshot untouched and raise a
warning in the single combined Telegram report instead of freezing releases.
"""
from __future__ import annotations

import argparse
from datetime import datetime
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
HOST = re.compile(r'(?i)(?<![a-z0-9-])[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,63}(?![a-z0-9-])')
ALLOWED_TAILS = {
    'gemini': ('google.com', 'googleapis.com', 'googleusercontent.com', 'gstatic.com',
               'google.dev', 'google', 'deepmind.com', 'withgoogle.com', 'google.ai',
               'clients6.google.com', 'ai.studio', 'goog'),
    'claude': ('anthropic.com', 'claude.ai', 'claude.com', 'claudeusercontent.com',
               'datadoghq.com', 'sentry.io', 'b-cdn.net', 'googleapis.com'),
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


def extract_hosts(content: str, service: str) -> list[str]:
    parser = ExtractText()
    parser.feed(content)
    text = ' '.join(parser.parts)
    hosts = {h.lower() for h in HOST.findall(text) if
             any(h.lower() == end or h.lower().endswith('.' + end)
                 for end in ALLOWED_TAILS[service])}
    limit = 10 if service == 'gemini' else 3
    if not limit <= len(hosts) <= 300:
        raise ValueError(f'Official {service} doc parse incomplete or unexpectedly large: {len(hosts)}')
    if service == 'claude' and not {'claude.ai', 'claude.com'}.issubset(hosts):
        raise ValueError('Official Claude network document missing key first-party hostnames')
    return sorted(hosts)


def fetch_doc(url: str) -> str:
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; AI domain change audit)',
                                     'Accept-Encoding': 'identity'})
    with urlopen(request, timeout=22) as response:
        if response.status != 200:
            raise ValueError(f'Official page returned HTTP {response.status}')
        body = response.read(2_500_001)
        if not 1000 <= len(body) <= 2_500_000:
            raise ValueError('Official page incomplete or oversized')
        return body.decode('utf-8', errors='replace')


def run(argv: list[str] | None = None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--force',action='store_true')
    p.add_argument('--report-file',type=Path)
    p.add_argument('--source-dir',type=Path,help='offline fixtures for tests and review')
    args=p.parse_args(argv)
    weekly = (datetime.now(ZoneInfo('Asia/Taipei')).weekday() == 6 and
              os.environ.get('GITHUB_EVENT_NAME') == 'schedule')
    if not (args.force or weekly):
        report={'checked': False, 'changed': False, 'detail': 'Not scheduled (Sunday Taiwan 11:00 only)'}
        if args.report_file:
            args.report_file.write_text(json.dumps(report,ensure_ascii=False)+'\n',encoding='utf-8')
        print('Official AI documentation audit skipped; not weekly schedule')
        return report
    old=json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else None
    current={}
    comparisons=[]
    for key,(url,service) in SOURCES.items():
        html=((args.source_dir / (key+'.html')).read_text(encoding='utf-8')
              if args.source_dir else fetch_doc(url))
        hosts=extract_hosts(html,service)
        signature=hashlib.sha256('\n'.join(hosts).encode()).hexdigest()
        current[key]={'url':url,'sha256':signature,'hosts':hosts}
        previous=(old or {}).get('sources',{}).get(key,{}).get('hosts',[])
        if previous:
            added=sorted(set(hosts)-set(previous))
            removed=sorted(set(previous)-set(hosts))
            if added or removed:
                comparisons.append({'service':service,'source':key,'added':added,'removed':removed})
    # Never overwrite unresolved advisory findings from earlier weeks.
    data={'schema_version':1,'sources':current}
    from build_v2rayn import atomically_write
    state_bytes=(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode()
    if comparisons:
        previous_review = REVIEW.read_text(encoding='utf-8') if REVIEW.exists() else (
            '# Gemini / Claude 官方網路文件變更待審\n\n'
            '此處保留歷次尚未清理的觀察紀錄；任何候選都不會自動加入代理。\n')
        date_stamp = datetime.now(ZoneInfo('Asia/Taipei')).strftime('%Y-%m-%d')
        lines = [f'## {date_stamp} — 官方文件變更', '']
        for item in comparisons:
            lines += [f"### {item['service']} — {item['source']}"]
            lines += [f'- 新增：`{x}`' for x in item['added']]
            lines += [f'- 移除：`{x}`' for x in item['removed']]
        review_text = previous_review.rstrip() + '\n\n' + '\n'.join(lines) + '\n'
        atomically_write(REVIEW, review_text.encode('utf-8'))
    if not STATE.exists() or STATE.read_bytes()!=state_bytes:
        atomically_write(STATE,state_bytes)
    report={'checked':True,'changed':bool(comparisons),'changes':comparisons,
            'sources':list(SOURCES),'initial_baseline':old is None}
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
