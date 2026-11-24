"""Advisory static analysis of earlier BLOCK rules versus reviewed AI routes.

Never changes order or routing policy. Opaque geosite/geoip datasets and
arbitrary regex intersections cannot be proven by this check.
"""
from __future__ import annotations
import ipaddress
import re

def split_domain(value):
    kind, sep, host = value.partition(':')
    return (kind, host) if sep else ('keyword', value)

def is_child(host, suffix):
    return host == suffix or host.endswith('.' + suffix)

def domain_overlap(a, b):
    ak, av = split_domain(a)
    bk, bv = split_domain(b)
    if ak == 'full' and bk == 'full':
        return av == bv
    if ak == 'full' and bk == 'domain':
        return is_child(av, bv)
    if ak == 'domain' and bk == 'full':
        return is_child(bv, av)
    if ak == bk == 'domain':
        return is_child(av, bv) or is_child(bv, av)
    # Keyword matching can prove overlap by matching the concrete hostname;
    # suffix-vs-keyword may also intersect on other descendants.
    if bk == 'keyword' and ak in ('full', 'domain'):
        return bv in av
    if ak == 'keyword' and bk in ('full', 'domain'):
        return av in bv
    if bk == 'regexp' and ak in ('full', 'domain'):
        try:
            return bool(re.search(bv, av))
        except re.error:
            return False
    if ak == 'regexp' and bk in ('full', 'domain'):
        try:
            return bool(re.search(av, bv))
        except re.error:
            return False
    return False

def detect(blocked, reviewed, *, limit=100):
    """Report provable overlaps (one witness per reviewed rule).
    
    Inputs are ordered converted entries (field, value, action).
    For suffixes a collision can cover just a child, not the whole suffix.
    """
    domains = [value for field, value, action in blocked if field == 'domain' and action == 'block']
    ips = []
    for field, value, action in blocked:
        if field == 'ip' and action == 'block' and not value.startswith('geoip:'):
            ips.append((value, ipaddress.ip_network(value, strict=False)))
    hits, total = [], 0
    for field, value, action in dict.fromkeys(reviewed):
        if action != 'proxy':
            continue
        witness = None
        if field == 'domain':
            witness = next((d for d in domains if domain_overlap(value, d)), None)
        elif field == 'ip' and not value.startswith('geoip:'):
            network = ipaddress.ip_network(value, strict=False)
            witness = next((d for d, other in ips if other.version == network.version
                            and other.overlaps(network)), None)
        if witness:
            total += 1
            if len(hits) < limit:
                hits.append({'field': field, 'proxy_rule': value, 'earlier_block_rule': witness})
    return {'count': total, 'examples': hits,
            'limitations': 'Static overlaps only; opaque geosite/geoip, arbitrary regex intersections, DNS and client capture need runtime checks.'}
