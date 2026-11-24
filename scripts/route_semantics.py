"""Independent static checks of the actual serialized routing artifacts.

Only explicit hostname/IP/process matches are checked; DNS, opaque geodata,
client capture and rewrite/MITM behavior require real client testing.
"""
from __future__ import annotations
import fnmatch
import ipaddress
import json
import re

# Business-entry witnesses only: do not infer additional routing permissions
# from this list. Shared login/payment/CDN targets are not automatically AI-only.
CORE_HOSTS = ('chatgpt.com', 'api.openai.com', 'auth.openai.com',
              'ws.chatgpt.com', 'cdn.oaistatic.com', 'files.oaiusercontent.com',
              'sora.com', 'gemini.google.com', 'generativelanguage.googleapis.com',
              'aistudio.google.com', 'ai.studio', 'cloudaicompanion.googleapis.com',
              'notebooklm.google.com', 'antigravity.google.com',
              'claude.ai', 'api.anthropic.com', 'platform.claude.com',
              'downloads.claude.ai', 'bridge.claudeusercontent.com')
# Common non-target DNS witnesses: both real business endpoints and synthetic
# sibling/label-boundary cases. These must never hit an AI/BitBrowser domain
# overlay, even if Johnshall would independently choose the same proxy tag.
PROTECTED_HOSTS = (
    'www.google.com', 'mail.google.com', 'accounts.google.com',
    'drive.google.com', 'docs.google.com', 'calendar.google.com',
    'play.google.com', 'maps.googleapis.com', 'www.youtube.com',
    'oauth2.googleapis.com', 'serviceusage.googleapis.com', 'people.googleapis.com',
    'fonts.googleapis.com', 'fonts.gstatic.com', 'ssl.gstatic.com',
    'lh3.googleusercontent.com', 'storage.googleapis.com', 'cloud.google.com',
    'jnn-pa.googleapis.com', 'waa-pa.clients6.google.com',
    'geller-pa.googleapis.com', 'proactivebackend-pa.googleapis.com',
    'api.stripe.com', 'dashboard.stripe.com', 'auth0.com',
    'tenant.sentry.io', 'o999999.ingest.us.sentry.io',
    'api.datadoghq.com', 'static.cloudflareinsights.com', 'www.cloudflare.com',
    'tenant.workos.com', 'other-project.vercel.app', 'other-tenant.run.app',
    'other-tenant.us-central1.run.app', 'other-account.blob.core.windows.net',
    'other-service.webpubsub.azure.com', 'other-service.azureedge.net',
    'sub.generativelanguage.googleapis.com', 'sub.cloudaicompanion.googleapis.com',
    'sub.challenges.cloudflare.com', 'sub.openaiapi-site.azureedge.net',
    'sub.js.stripe.com', 'notopenai.com', 'openai.com.example',
    'gemini.google.com.example', 'claude.ai.example',
)
# These historical shared suffixes are still explicit v2rayN-only user
# exceptions. Do not silently remove them, or allow them to leak into SR.
SHADOW_ONLY_PROTECTED = ('api.statsig.com', 'events.statsigapi.net',
                         'featuregates.org', 'featureassets.org', 'prodregistryv2.org',
                         'browser-intake-datadoghq.com', 'ip-api.com', 'todetect.net')

def domain_match(value, host):
    kind, _, pattern = value.partition(':')
    if kind == 'full':
        return host == pattern
    if kind == 'domain':
        return host == pattern or host.endswith('.' + pattern)
    if kind == 'keyword':
        return pattern in host
    if kind == 'regexp':
        try:
            return bool(re.search(pattern, host))
        except re.error as exc:
            raise ValueError('Invalid explicit final route regexp') from exc
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

def require_isolation(overlay, baseline, hosts):
    """Prove that protected hosts cannot enter the added domain overlay."""
    # If no overlay rule matches, the baseline is necessarily unchanged for
    # these explicit-domain witnesses. Scanning all ~83k baseline rules twice
    # per host cannot add information. Keep the existing call interface.
    for host in hosts:
        if any(domain_match(value, host) for values, _ in overlay for value in values):
            raise ValueError('Non-target host intercepted by dedicated layer: ' + host)


SHADOW_LAYERS = (
    '# [1a] OpenAI automatic rules - official Voice destination IPs',
    '# [1b] OpenAI automatic rules - public domain rules',
    '# [2] Independent manual OpenAI fallback (no cross-layer dedup)',
    '# GEMINI first-party and exact shared dependencies',
    '# CLAUDE first-party and exact shared dependencies',
)


def verify_shadow_layers(dedicated_body, expected_layers):
    """Keep the two OpenAI layers independently complete, in original order."""
    observed = []
    for line in dedicated_body.splitlines():
        line = line.strip()
        if line in SHADOW_LAYERS:
            observed.append((line, []))
        elif line and not line.startswith(('#', ';')):
            if not observed:
                raise ValueError('Shadowrocket rule before dedicated layer marker')
            parts = line.split(',')
            if len(parts) < 3:
                raise ValueError('Malformed Shadowrocket dedicated layer rule')
            observed[-1][1].append(','.join(parts[:2]))
    if [marker for marker, _ in observed] != list(SHADOW_LAYERS):
        raise ValueError('Shadowrocket dedicated layer order or boundary changed')
    for (marker, actual), expected in zip(observed, expected_layers, strict=True):
        if actual != list(expected):
            raise ValueError('Shadowrocket dedicated layer differs from reviewed inputs: ' + marker)


def reviewed_domain_sets(client, root, report):
    """Use the reviewed inputs plus fresh observations, never an output count.

    Independently check allowlist scope and compare exact serialized domain
    sets. This catches accidental additions, broadened types and omissions.
    """
    import build as legacy
    import ai_services
    import v2rayn_core as core
    from build_v2rayn import parse_user_extra, selected_bitbrowser_domains
    manual = set(legacy.parse_manual(root / 'config/manual-openai.rules'))
    def reviewed_rules(value):
        if not isinstance(value, list) or any(
                not isinstance(rule, str) or rule.count(',') != 1 for rule in value):
            raise ValueError('Malformed reviewed domain rules in build report')
        return set(value)

    openai = reviewed_rules(report['openai_observation']['common_rules'])
    if not all(rule in manual or legacy.is_openai_specific_rule(rule) for rule in openai):
        raise ValueError('Unreviewed common OpenAI scope in build report')
    if not manual <= openai:
        # Shadowrocket compacts within each layer; coverage, not byte-identical
        # redundant children, is the requirement for that manual fallback.
        if not all(any(legacy.domain_rule_covers(active, rule) for active in openai)
                   for rule in manual):
            raise ValueError('Missing reviewed OpenAI manual coverage')
    supplemental = ai_services.load_manual((root / 'config/ai-services.rules').read_text(encoding='utf-8'))
    approved = {}
    for service in ('gemini', 'claude'):
        rules = reviewed_rules(report['ai_approved_rules'][service])
        for rule in rules:
            kind, host = rule.split(',', 1)
            if rule not in supplemental[service] and (
                    not ai_services.is_approved(service, kind, host)
                    or ai_services.normalize_approved(service, kind, host) != (kind, host)):
                raise ValueError('Unreviewed or broadened ' + service + ' scope: ' + rule)
        if not set(supplemental[service]) <= rules:
            raise ValueError('Missing reviewed manual ' + service + ' coverage')
        approved[service] = rules
    if client == 'shadowrocket_ai':
        return openai | approved['gemini'] | approved['claude']
    def converted(rules):
        return {core.as_match(*rule.split(',', 1))[1] for rule in rules}
    extras = parse_user_extra((root / 'config/v2rayn/openai-extra.rules').read_text(encoding='utf-8'))
    bit = core.load_bitbrowser_domains((root / 'data/bitbrowser_domains.txt').read_text(encoding='utf-8'))
    return {
        2: {'domain:' + name for name in selected_bitbrowser_domains(bit)},
        4: converted(openai) | {value for field, value, _ in extras if field == 'domain'},
        5: converted(approved['gemini']),
        6: converted(approved['claude']),
    }


def verify_shadow(text, settings, voice_rules, *, expected_domains=None, expected_layers=None):
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
    dedicated_body = body.split(marker, 1)[0]
    if expected_layers is not None:
        verify_shadow_layers(dedicated_body, expected_layers)
    dedicated = [x.strip().split(',') for x in dedicated_body.splitlines()
                 if x.strip() and not x.lstrip().startswith(('#', ';'))]
    expected_voice = {tuple(rule.split(',', 1)) for rule in voice_rules}
    actual_voice = set()
    actual_domains = set()
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
            actual_domains.add(kind + ',' + value)
            if row[3:] != ['force-remote-dns']:
                raise ValueError('Invalid final Shadowrocket AI DNS modifier')
            domains.append(([mapping[kind] + value], row[2]))
        elif kind == 'DOMAIN-WILDCARD':
            actual_domains.add(kind + ',' + value)
            if row[3:]:
                raise ValueError('Unexpected final Shadowrocket wildcard modifier')
            domains.append((['regexp:' + fnmatch.translate(value)], row[2]))
        else:
            raise ValueError('Unsupported final Shadowrocket AI rule')
    if actual_voice != expected_voice or not expected_voice:
        raise ValueError('Final Shadowrocket Voice coverage mismatch')
    require_hosts(domains, node)
    if expected_domains is not None and actual_domains != expected_domains:
        raise ValueError('Final Shadowrocket domains differ from reviewed inputs')
    require_isolation(domains, [], PROTECTED_HOSTS + SHADOW_ONLY_PROTECTED)


def require_route_shape(row, field):
    # Conditions in a v2rayN routing object are combined, not alternative.
    # A stray port/network/domain predicate can silently narrow an otherwise
    # correct Voice, local-network, process or fallback match.
    if (not isinstance(row, dict) or
            set(row) - {'remarks', 'outboundTag', 'enabled', field} or
            not {'outboundTag', 'enabled', field} <= set(row)):
        raise ValueError('Unexpected condition in final v2rayN ' + field + ' rule')
    if field != 'port' and (not isinstance(row[field], list) or not row[field] or
                            not all(isinstance(value, str) and value for value in row[field])):
        raise ValueError('Invalid matching values in final v2rayN ' + field + ' rule')


def verify_v2(rules, voice_rules, processes, *, expected_domains=None):
    if (not isinstance(rules, list) or len(rules) < 3
            or not all(isinstance(row, dict) for row in rules)):
        raise ValueError('Invalid final v2rayN routing list')
    require_route_shape(rules[0], 'ip')
    require_route_shape(rules[1], 'domain')
    require_route_shape(rules[-1], 'port')
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
    overlay = []
    actual_domains = {2: set(), 4: set(), 5: set(), 6: set()}
    explicit_blocks = []
    for i, row in enumerate(rules):
        if row.get('enabled') is not True:
            raise ValueError('Disabled final v2rayN routing rule')
        action = row.get('outboundTag')
        if i < 2 or i == len(rules) - 1:
            if 'domain' in row:
                domain_rows.append((row['domain'], action))
            continue
        remark = row.get('remarks', '')
        if not isinstance(remark, str):
            raise ValueError('Invalid final v2rayN layer label')
        rank = next((j for j, name in enumerate(ranks) if remark.startswith(name + ' / ')), -1)
        if rank < 0 or rank < last_rank:
            raise ValueError('Unexpected final v2rayN routing layer order')
        last_rank = rank
        found.add(rank)
        if rank in actual_domains:
            require_route_shape(row, 'domain')
            overlay.append((row['domain'], action))
            actual_domains[rank].update(row['domain'])
        elif rank == 1:
            require_route_shape(row, 'process')
        elif rank == 3:
            require_route_shape(row, 'ip')
        else:
            require_route_shape(row, 'domain' if 'domain' in row else 'ip')
            if rank == 7 and action not in ('proxy', 'direct'):
                raise ValueError('Unexpected policy in final v2rayN ordinary layer')
        if 'domain' in row:
            domain_rows.append((row['domain'], action))
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
    # A core host must match a reviewed AI layer, not merely a generic
    # Johnshall proxy rule or a BitBrowser rule.
    ai_rows = [(sorted(actual_domains[i]), 'proxy') for i in (4, 5, 6)]
    require_hosts(ai_rows, 'proxy')
    require_hosts(domain_rows, 'proxy')
    if expected_domains is not None and actual_domains != expected_domains:
        raise ValueError('Final v2rayN domains differ from reviewed inputs')
    require_isolation(overlay, [], PROTECTED_HOSTS)


def verify_release_routes(client, root, state, report):
    expected = reviewed_domain_sets(client, root, report)
    if client == 'shadowrocket_ai':
        settings = json.loads((root / 'config/user-settings.json').read_text(encoding='utf-8'))
        import build as legacy
        auto_rows = [x.strip() for x in
                     (root / 'rules/openai-auto.list').read_text(encoding='utf-8').splitlines()
                     if x.strip() and not x.lstrip().startswith(('#', ';'))]
        voice = [','.join(x.split(',')[:2]) for x in auto_rows
                 if x.startswith(('IP-CIDR,', 'IP-CIDR6,'))]
        auto = [x for x in auto_rows if not x.startswith(('IP-CIDR,', 'IP-CIDR6,'))]
        manual = legacy.compact_rules_within_layer(
            legacy.parse_manual(root / 'config/manual-openai.rules'))
        layers = [voice, auto, manual, report['ai_approved_rules']['gemini'],
                  report['ai_approved_rules']['claude']]
        verify_shadow((root / 'Shadowrocket_Johnshall_AI.conf').read_text(encoding='utf-8'), settings, voice,
                      expected_domains=expected, expected_layers=layers)
    else:
        from v2rayn_core import load_processes
        processes = load_processes((root / 'config/v2rayn/verified-processes.txt').read_text(encoding='utf-8'))
        verify_v2(json.loads((root / 'v2rayN_Johnshall_AI.json').read_text(encoding='utf-8')),
                  state['voice_rules'], processes, expected_domains=expected)
