"""Independent static checks of the actual serialized routing artifacts.

Only explicit hostname/IP/process matches are checked; DNS, opaque geodata,
client capture and rewrite/MITM behavior require real client testing.
"""
from __future__ import annotations
import fnmatch
import ipaddress
import json
import re

CORE_HOSTS = ('chatgpt.com', 'api.openai.com', 'auth.openai.com',
              'files.oaiusercontent.com', 'gemini.google.com',
              'generativelanguage.googleapis.com', 'claude.ai', 'api.anthropic.com')

def domain_match(value, host):
    kind, _, pattern = value.partition(':')
    if kind == 'full':
        return host == pattern
    if kind == 'domain':
        return host == pattern or host.endswith('.' + pattern)
    if kind == 'keyword':
        return pattern in host
    if kind == 'regexp':
        return bool(re.search(pattern, host))
    return False  # Opaque geosite data is not statically evaluated.

def first_domain(rows, host):
    for values, action in rows:
        if any(domain_match(value, host) for value in values):
            return action
    return 'direct'

def require_hosts(rows, action):
    for host in CORE_HOSTS:
        if first_domain(rows, host) != action:
            raise ValueError('Final routing semantic check failed for ' + host)

def verify_shadow(text, settings, voice_rules):
    node = settings['openai_node_name']
    sections = re.split(r'(?m)^\[(Rule|URL Rewrite)\]\s*$', text)
    if len(sections) != 5:
        raise ValueError('Invalid final Shadowrocket section layout')
    body = sections[2]
    active = [x.strip() for x in body.splitlines()
              if x.strip() and not x.lstrip().startswith(('#', ';'))]
    if not active or active[-1].lower() != 'final,direct' or sum(
            x.upper().startswith('FINAL,') for x in active) != 1:
        raise ValueError('Invalid final Shadowrocket fallback')
    marker = '# [3] Johnshall full original rules, Proxy mapped to exact configured node'
    if body.count(marker) != 1:
        raise ValueError('Invalid final Shadowrocket AI layer boundary')
    dedicated = [x.strip().split(',') for x in body.split(marker, 1)[0].splitlines()
                 if x.strip() and not x.lstrip().startswith(('#', ';'))]
    expected_voice = {tuple(rule.split(',', 1)) for rule in voice_rules}
    actual_voice = set()
    domains = []
    mapping = {'DOMAIN': 'full:', 'DOMAIN-SUFFIX': 'domain:', 'DOMAIN-KEYWORD': 'keyword:'}
    for row in dedicated:
        if len(row) < 3 or row[2] != node:
            raise ValueError('Unexpected policy in final Shadowrocket AI layer')
        kind, value = row[:2]
        if kind in ('IP-CIDR', 'IP-CIDR6'):
            if row[3:] != ['no-resolve']:
                raise ValueError('Invalid final Shadowrocket Voice modifiers')
            actual_voice.add((kind, value))
        elif kind in mapping:
            if row[3:] != ['force-remote-dns']:
                raise ValueError('Invalid final Shadowrocket AI DNS modifier')
            domains.append(([mapping[kind] + value], row[2]))
        elif kind == 'DOMAIN-WILDCARD':
            domains.append((['regexp:' + fnmatch.translate(value)], row[2]))
        else:
            raise ValueError('Unsupported final Shadowrocket AI rule')
    if actual_voice != expected_voice or not expected_voice:
        raise ValueError('Final Shadowrocket Voice coverage mismatch')
    require_hosts(domains, node)

def verify_v2(rules, voice_rules, processes):
    if not isinstance(rules, list) or len(rules) < 3:
        raise ValueError('Invalid final v2rayN routing list')
    if rules[0].get('ip') != ['127.0.0.0/8', '::1/128', 'geoip:private'] or rules[0].get('outboundTag') != 'direct':
        raise ValueError('Final v2rayN private network protection changed')
    if rules[1].get('domain') != ['full:localhost', 'domain:localhost.localdomain'] or rules[1].get('outboundTag') != 'direct':
        raise ValueError('Final v2rayN localhost protection changed')
    if rules[-1].get('port') != '0-65535' or rules[-1].get('outboundTag') != 'direct':
        raise ValueError('Final v2rayN fallback changed')
    ranks = ('Johnshall ads and tracking', 'BitBrowser verified process',
             'BitBrowser selected domains', 'OpenAI official Voice IPs',
             'OpenAI reviewed and user extras', 'Gemini approved rules',
             'Claude approved rules', 'Johnshall original order')
    found = set()
    last_rank = -1
    actual_voice = set()
    actual_processes = set()
    domain_rows = []
    explicit_blocks = []
    for i, row in enumerate(rules):
        if row.get('enabled') is not True:
            raise ValueError('Disabled final v2rayN routing rule')
        action = row.get('outboundTag')
        if 'domain' in row:
            domain_rows.append((row['domain'], action))
        if i < 2 or i == len(rules) - 1:
            continue
        remark = row.get('remarks', '')
        rank = next((j for j, name in enumerate(ranks) if remark.startswith(name + ' / ')), -1)
        if rank < 0 or rank < last_rank:
            raise ValueError('Unexpected final v2rayN routing layer order')
        last_rank = rank
        found.add(rank)
        if rank == 0:
            if action != 'block':
                raise ValueError('Unexpected final v2rayN ad policy')
            for value in row.get('ip', []):
                if not value.startswith('geoip:'):
                    explicit_blocks.append(ipaddress.ip_network(value))
        if 1 <= rank <= 6 and action != 'proxy':
            raise ValueError('Unexpected policy in final v2rayN AI/BitBrowser layer')
        if rank == 1:
            actual_processes.update(row.get('process', []))
        if rank == 3:
            actual_voice.update(row.get('ip', []))
    if found != set(range(len(ranks))) or actual_processes != set(processes) or not actual_processes:
        raise ValueError('Missing final v2rayN routing layer or process')
    expected_voice = {str(ipaddress.ip_network(rule.split(',', 1)[1], strict=False)) for rule in voice_rules}
    if actual_voice != expected_voice or not expected_voice:
        raise ValueError('Final v2rayN Voice coverage mismatch')
    for value in actual_voice:
        net = ipaddress.ip_network(value)
        if any(b.version == net.version and b.overlaps(net) for b in explicit_blocks):
            raise ValueError('Final v2rayN Voice IP conflicts with earlier explicit block: ' + value)
    require_hosts(domain_rows, 'proxy')

def verify_release_routes(client, root, state):
    if client == 'shadowrocket_ai':
        settings = json.loads((root / 'config/user-settings.json').read_text(encoding='utf-8'))
        voice = [','.join(x.split(',')[:2]) for x in
                 (root / 'rules/openai-auto.list').read_text(encoding='utf-8').splitlines()
                 if x.startswith(('IP-CIDR,', 'IP-CIDR6,'))]
        verify_shadow((root / 'Shadowrocket_Johnshall_AI.conf').read_text(encoding='utf-8'), settings, voice)
    else:
        from v2rayn_core import load_processes
        processes = load_processes((root / 'config/v2rayn/verified-processes.txt').read_text(encoding='utf-8'))
        verify_v2(json.loads((root / 'v2rayN_Johnshall_AI.json').read_text(encoding='utf-8')),
                  state['voice_rules'], processes)
