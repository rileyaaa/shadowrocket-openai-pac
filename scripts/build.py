#!/usr/bin/env python3
"""Build a complete standalone Shadowrocket config using Johnshall as the base.

Downloads, validates and merges upstream sources. Any failed source aborts
without changing the existing published file.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import ipaddress
import json
from pathlib import Path
import re
import sys
import time
import urllib.request
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://raw.githubusercontent.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever/release/sr_top500_banlist_ad.conf"
VOICE_URL = "https://openai.com/chatgpt-voice.json"
DOMAIN_SOURCES = {
    "metacubex": ("https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/openai.list", "meta"),
    "acl4ssr": ("https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Ruleset/OpenAi.list", "typed"),
    "blackmatrix7": ("https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/OpenAI/OpenAI.list", "typed"),
    "v2fly": ("https://raw.githubusercontent.com/v2fly/domain-list-community/master/data/openai", "v2fly"),
}
# Only reviewed external dependencies may be embedded in the standalone file.
# Unknown/nested remote lists stop publication instead of bypassing validation.
RULESET_SOURCES = {
    "apple_news": (
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/AppleNews/AppleNews.list",
        "rules/johnshall-apple-news.list",
    ),
}
JOHNSHALL_FOOTER = "# Made with Love from https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever"
MAX_DOWNLOAD_BYTES = 13_000_000
# Review gates, not a claim that official ranges can never legitimately grow.
VOICE_MIN_PREFIX = {4: 24, 6: 48}
RULE_TYPES = {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-WILDCARD"}

# Only domains dedicated to OpenAI may override the original Johnshall route.
# OpenAI rule-set providers also include unrelated shared services such as
# stripe.com, auth0.com, sentry.io and launchdarkly.com: NEVER import those.
OPENAI_SPECIFIC_SUFFIXES = frozenset({
    "openai.com", "chatgpt.com", "chatgpt.site", "chat.com",
    "oaistatic.com", "oaistatsig.com", "oaiusercontent.com",
    "sora.com", "crixet.com", "chatgpt.livekit.cloud",
    # Explicitly requested shared LiveKit TURN endpoint exceptions.
    # These may also route OTHER LiveKit customer traffic via OpenAI node.
    "host.livekit.cloud", "turn.livekit.cloud",
    "openai.com.cdn.cloudflare.net",
    "openai.fm",  # Official OpenAI speech demo; includes www.openai.fm
})
OPENAI_SPECIFIC_HOSTS = frozenset({
    "openaiapi-site.azureedge.net",
    "openaiassets.blob.core.windows.net",
    "openaicom-api-bdcpf8c6d2e9atf6.z01.azurefd.net",
    "openaicom.imgix.net",
    "openaicomproductionae4b.blob.core.windows.net",
    "production-openaicom-storage.azureedge.net",
    "cdn.openaimerge.com",
    "openai-api.arkoselabs.com",
    "openai.qualtrics.com",
    "chat.openai.com.cdn.cloudflare.net",
    "chatkit.world",  # Official ChatKit showcase
    "openai-photobooth-demo.vercel.app",  # Exact OpenAI showcase host
    "openai-realtime-solar-system-demo.vercel.app",  # Exact OpenAI showcase host
})
OPENAI_SPECIFIC_WILDCARDS = frozenset({
    "chatgpt-async-webps-prod-*.webpubsub.azure.com",
})

# Shared vendor endpoints that OpenAI explicitly includes in its official
# ChatGPT web/app network guidance. Opt-in for COVERAGE over traffic isolation.
# Their use may also route other companies' client requests to the OpenAI node.
# Keep this exact allowlist separate from automatic OpenAI-only geosite filters.
OFFICIAL_CHATGPT_SHARED_RULES = frozenset({
    "DOMAIN-SUFFIX,ct.sendgrid.net",
    "DOMAIN-SUFFIX,intercom.io",
    "DOMAIN-SUFFIX,intercomcdn.com",
    "DOMAIN,cdn.workos.com",
    "DOMAIN,challenges.cloudflare.com",
    "DOMAIN,forwarder.workos.com",
    "DOMAIN,frontend-apps-multi-region.workos.com",
    "DOMAIN,humb.apple.com",
    "DOMAIN,images.workoscdn.com",
    "DOMAIN,js.stripe.com",
    "DOMAIN,o207216.ingest.sentry.io",
    "DOMAIN,o33249.ingest.sentry.io",
    "DOMAIN,rum.browser-intake-datadoghq.com",
    "DOMAIN,setup.workos.com",
    "DOMAIN,workos.imgix.net",
})
DOMAIN_CHARS = re.compile(r"^[a-z0-9_.*?-]+$")
PROXY_POLICY = re.compile(r",proxy(?=,|\s*$)", flags=re.I)
CONFIG = ROOT / "Shadowrocket_Johnshall_OpenAI.conf"

DNS = """# Route-aware DNS:
# Proxy domain names are resolved remotely by their selected role-based node.
# If Shadowrocket must resolve locally, use Google DoH via Johnshall Proxy.
# DIRECT traffic and proxy-server hostname bootstrap use AliDNS encrypted DoH.
# A global fallback cannot vary by rule: use direct, encrypted AliDNS +
# DNSPod DoH, never the Johnshall Proxy node for DIRECT fallback queries.
dns-server = https://dns.google/dns-query#proxy=JOHNSHALL_PROXY_NODE
direct-dns-server = https://dns.alidns.com/dns-query#no-h3
fallback-dns-server = https://dns.alidns.com/dns-query#no-h3,https://doh.pub/dns-query#no-h3
proxy-dns-server = https://dns.alidns.com/dns-query#no-h3
dns-direct-system = false
dns-fallback-system = false
dns-direct-fallback-proxy = false
hijack-dns = 8.8.8.8:53,8.8.4.4:53,1.1.1.1:53,1.0.0.1:53,223.5.5.5:53,223.6.6.6:53
"""
DNS_KEYS = {line.partition("=")[0].strip() for line in DNS.splitlines() if "=" in line and not line.startswith("#")}
# Two exact Shadowrocket node names, no proxy groups or automatic node selection.
SETTINGS_PATH = ROOT / "config/user-settings.json"
SETTING_KEYS = {"openai_node_name", "johnshall_proxy_node_name"}
RESERVED_POLICIES = {
    "DIRECT", "PROXY", "REJECT", "REJECT-DROP", "REJECT-NO-DROP",
    "FINAL", "PASS", "GLOBAL", "SYSTEM", "NONE",
}


def load_settings(path: Path = SETTINGS_PATH) -> dict[str, str]:
    """Fail safely when the two exact node names are absent or ambiguous."""
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or set(data) != SETTING_KEYS:
        raise ValueError(f"Expected exactly these settings: {sorted(SETTING_KEYS)}")
    for key, value in data.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a nonempty node name")
        if value != value.strip():
            raise ValueError(f"{key} has leading/trailing whitespace")
        if any(ord(char) < 32 or char in ",=#" or char == chr(92) for char in value):
            raise ValueError(f"{key} contains unsafe Shadowrocket syntax characters")
        if value.upper() in RESERVED_POLICIES:
            raise ValueError(f"{key} cannot be a built-in policy")
    if data["openai_node_name"].casefold() == data["johnshall_proxy_node_name"].casefold():
        raise ValueError("OpenAI and Johnshall Proxy must not point to the same exact node")
    return data


def render_dns(settings: dict[str, str]) -> str:
    # Local DNS for proxy-classified lookups uses the Johnshall Proxy node.
    # Explicit OpenAI rules below force remote resolution by the OpenAI node.
    encoded = quote(settings["johnshall_proxy_node_name"], safe="")
    return DNS.replace("#proxy=JOHNSHALL_PROXY_NODE", f"#proxy={encoded}")


def fetch(url: str, minimum: int = 50) -> bytes:
    """Download an upstream; one retry for network, HTTP or truncated responses.

    Both failed attempts abort publication. Never fall back to incomplete data.
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": "shadowrocket-openai-pac/1.0", "Accept": "*/*",
                      "Accept-Encoding": "identity"}
    )
    for attempt in range(2):  # initial request + exactly one retry
        try:
            with urllib.request.urlopen(request, timeout=75) as response:
                if not 200 <= response.status < 300:
                    raise ValueError(f"Unexpected HTTP status for {url}: {response.status}")
                declared = response.headers.get("Content-Length")
                if declared is not None:
                    if not re.fullmatch(r"[0-9]+", declared.strip()):
                        raise ValueError(f"Invalid Content-Length from {url}")
                    declared = int(declared)
                    if not minimum <= declared < MAX_DOWNLOAD_BYTES:
                        raise ValueError(f"Unexpected Content-Length from {url}: {declared}")
                content = response.read(MAX_DOWNLOAD_BYTES)
                # HTTPResponse.read(amt) may return a short body without raising
                # IncompleteRead. Check the advertised length explicitly.
                if declared is not None and len(content) != declared:
                    raise ValueError(f"Truncated response from {url}: {len(content)}/{declared}")
                if not minimum <= len(content) < MAX_DOWNLOAD_BYTES:
                    raise ValueError(f"Truncated or oversized data from {url}: {len(content)}")
                return content
        except (OSError, ValueError, http.client.HTTPException) as exc:
            if attempt:
                raise
            print(
                f"Upstream fetch failed ({type(exc).__name__}); retrying once: {url}",
                file=sys.stderr,
            )
            time.sleep(2)
    raise AssertionError("Unreachable upstream retry state")


def domain_rule(kind: str, value: str) -> str:
    kind = kind.upper().strip()
    value = value.lower().strip()
    if kind not in RULE_TYPES or not DOMAIN_CHARS.fullmatch(value):
        raise ValueError(f"Invalid domain rule {kind},{value}")
    if kind != "DOMAIN-WILDCARD" and ("*" in value or "?" in value):
        raise ValueError(f"Unexpected wildcard {kind},{value}")
    return f"{kind},{value}"


def parse_domain_list(source: str, fmt: str, *, unparsed: list[str] | None = None) -> list[str]:
    rules = []
    for raw in source.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if fmt == "meta":
            if line.startswith(("+.", "*.")):
                rules.append(domain_rule("DOMAIN-SUFFIX", line[2:]))
            else:
                rules.append(domain_rule("DOMAIN", line))
        elif fmt == "typed":
            parts = line.split(",")
            if len(parts) >= 2 and parts[0].strip().upper() in RULE_TYPES:
                rules.append(domain_rule(parts[0], parts[1]))
            elif unparsed is not None:
                # Broad IP/ASN entries and new syntax are review-only.
                unparsed.append(line)
        elif fmt == "v2fly":
            # geosite syntax: bare domain=domain plus subdomains, full:=one
            # exact hostname, regexp:=regex. Never treat metadata as a host.
            entry = line.split(" @", 1)[0].strip()
            if entry.startswith("full:"):
                rules.append(domain_rule("DOMAIN", entry[5:]))
            elif entry.startswith("domain:"):
                rules.append(domain_rule("DOMAIN-SUFFIX", entry[7:]))
            elif entry == r"regexp:^chatgpt-async-webps-prod-\S+-\d+\.webpubsub\.azure\.com$":
                # A known ChatGPT-specific pattern; Shadowrocket supports
                # DOMAIN-WILDCARD but not arbitrary geosite regex syntax.
                rules.append(domain_rule(
                    "DOMAIN-WILDCARD",
                    "chatgpt-async-webps-prod-*.webpubsub.azure.com",
                ))
            elif not entry.startswith("regexp:") and ":" not in entry:
                rules.append(domain_rule("DOMAIN-SUFFIX", entry))
            elif unparsed is not None:
                # Preserve the raw rule and its source for review; never expand
                # unknown regex/include/keyword syntax into routing rules.
                unparsed.append(line)
        else:
            raise ValueError(f"Unexpected source format: {fmt}")
    if not 10 <= len(rules) <= 2000:
        raise ValueError(f"Unexpected domain count: {len(rules)}")
    return list(dict.fromkeys(rules))


def is_openai_specific_rule(rule: str) -> bool:
    """Reject shared third-party services in auto lists to preserve original routing.

    Even when published under 'OpenAI' elsewhere, generic Stripe, Auth0,
    Cloudflare challenges, Statsig and Intercom traffic are NOT all OpenAI.
    Exact third-party hosts may be opted into the manual list intentionally.
    """
    kind, value = rule.split(",", 1)
    if kind == "DOMAIN-KEYWORD":
        return False
    if kind == "DOMAIN-WILDCARD":
        return value in OPENAI_SPECIFIC_WILDCARDS
    if kind == "DOMAIN-SUFFIX":
        # Suffix policy is reserved for confirmed OpenAI-only namespaces.
        # E.g. azureedge.net / qualtrics.com / workos.com are shared,
        # and even an approved exact host must not become a wildcard.
        return value in OPENAI_SPECIFIC_SUFFIXES
    if kind == "DOMAIN":
        return (
            value in OPENAI_SPECIFIC_HOSTS
            or any(
                value == suffix or value.endswith("." + suffix)
                for suffix in OPENAI_SPECIFIC_SUFFIXES
            )
        )
    return False


def filter_auto_domains(rules: list[str]) -> list[str]:
    kept = list(dict.fromkeys(rule for rule in rules if is_openai_specific_rule(rule)))
    if len(kept) < 10:
        raise ValueError(f"Too few OpenAI-only automatic domains: {len(kept)}")
    return kept


def domain_rule_covers(broad_rule: str, narrow_rule: str) -> bool:
    """Whether a same-policy rule makes the narrow domain rule redundant.

    DOMAIN-SUFFIX,example.com covers example.com and sub.example.com;
    DOMAIN,example.com does NOT cover sub.example.com.
    Wildcards are only deduplicated when the rule is exactly identical.
    """
    if broad_rule == narrow_rule:
        return True
    broad_type, broad_host = broad_rule.split(",", 1)
    narrow_type, narrow_host = narrow_rule.split(",", 1)
    return (
        broad_type == "DOMAIN-SUFFIX"
        and narrow_type in {"DOMAIN", "DOMAIN-SUFFIX"}
        and (narrow_host == broad_host or narrow_host.endswith("." + broad_host))
    )


def compact_rules_within_layer(rules: list[str]) -> list[str]:
    """Remove only redundant rules within one self-contained rule layer.

    A DOMAIN-SUFFIX parent supersedes its DOMAIN or DOMAIN-SUFFIX children.
    Do not compare rules across upstream and manual sources: the manual list
    is an independent, always-emitted safety net for future upstream changes.
    """
    candidates = list(dict.fromkeys(rules))
    return [
        rule for rule in candidates
        if not any(
            other != rule and domain_rule_covers(other, rule)
            for other in candidates
        )
    ]


def compact_openai_rules(
    auto: list[str], manual: list[str]
) -> tuple[list[str], list[str]]:
    """Optimize each OpenAI layer independently; never cross-deduplicate.

    The final standalone .conf always contains two separate sections, even
    when the same exact domain occurs in both auto and manual layers.
    """
    auto_kept = compact_rules_within_layer(auto)
    manual_kept = compact_rules_within_layer(manual)
    if not auto_kept or not manual_kept:
        raise ValueError("Automatic or manual OpenAI rule layer is empty")
    return auto_kept, manual_kept


def parse_voice(raw: bytes) -> list[str]:
    doc = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(doc, dict) or not isinstance(doc.get("prefixes"), list):
        raise ValueError("Voice JSON unexpectedly changed its prefixes format")
    results = set()
    for item in doc["prefixes"]:
        if not isinstance(item, dict):
            raise ValueError("Unexpected voice IP entry")
        values = [(version, item[key]) for version, key in ((4, "ipv4Prefix"), (6, "ipv6Prefix")) if item.get(key)]
        if not values:
            raise ValueError(f"Missing voice prefix in {item}")
        for version, value in values:
            if not isinstance(value, str):
                raise ValueError("Voice prefix must be a CIDR string")
            # Never silently widen a host address with an erroneous subnet mask.
            network = ipaddress.ip_network(value, strict=True)
            if (network.version != version or not network.is_global
                    or network.prefixlen < VOICE_MIN_PREFIX[version]):
                raise ValueError(f"Unsafe voice network: {network}")
            results.add(network)
    if not 5 <= len(results) <= 3000:
        raise ValueError(f"Unexpected voice prefix count: {len(results)}")
    networks = sorted(results, key=lambda ip: (ip.version, int(ip.network_address), ip.prefixlen))
    return [f"{'IP-CIDR6' if n.version == 6 else 'IP-CIDR'},{n}" for n in networks]


def voice_address_counts(rules: list[str]) -> dict[str, int]:
    """Count the union of Voice destinations, independently for IPv4 and IPv6."""
    networks = {4: [], 6: []}
    for rule in rules:
        parts = rule.split(",")
        if parts[0] not in {"IP-CIDR", "IP-CIDR6"}:
            continue
        network = ipaddress.ip_network(parts[1], strict=True)
        if (parts[0] == "IP-CIDR6") != (network.version == 6):
            raise ValueError("Voice baseline has an inconsistent address family")
        networks[network.version].append(network)
    return {
        f"voice_ipv{version}_addresses": sum(n.num_addresses for n in ipaddress.collapse_addresses(items))
        for version, items in networks.items()
    }


def validate_voice_coverage(ips: list[str], old_auto: str, *, has_baseline: bool) -> dict[str, int]:
    current = voice_address_counts(ips)
    if not has_baseline:
        return current
    before = voice_address_counts(sorted(active_auto_rules(old_auto)))
    if not any(before.values()):
        raise ValueError("Published Voice baseline is missing; refusing to reset coverage protection")
    for key, after in current.items():
        previous = before[key]
        if ((previous == 0 and after > 0)
                or (previous > 0 and (after * 10 < previous * 7 or after > previous * 2))):
            raise ValueError(
                f"VOICE COVERAGE ANOMALY: {key}: {previous} -> {after}; "
                "review official ranges before changing the published baseline"
            )
    return current


def parse_embedded_ruleset(source: str) -> list[str]:
    """The reviewed Apple News list contains policy-free domain rules only."""
    rules = []
    for raw in source.lstrip("\ufeff").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",")
        if len(parts) != 2 or parts[0] not in RULE_TYPES:
            raise ValueError(f"Unsupported embedded rule (policy/nested lists not allowed): {line}")
        rules.append(domain_rule(*parts))
    declared = re.findall(r"(?m)^#\s*TOTAL:\s*(\d+)\s*$", source)
    if (not 1 <= len(rules) <= 2000 or len(declared) != 1
            or int(declared[0]) != len(rules) or len(set(rules)) != len(rules)):
        raise ValueError("Embedded ruleset count/header is missing, truncated or inconsistent")
    return rules


def inline_ruleset(line: str, rulesets: dict[str, list[str]]) -> list[str]:
    parts = [part.strip() for part in line.split(",")]
    if parts[0].upper() not in {"RULE-SET", "DOMAIN-SET"}:
        return [line]
    known_urls = {url for url, _ in RULESET_SOURCES.values()}
    if (parts[0] != "RULE-SET" or len(parts) != 3
            or parts[1] not in known_urls or parts[1] not in rulesets
            or not rulesets[parts[1]]):
        raise ValueError(f"Unreviewed or unavailable external ruleset: {line}")
    url, policy = parts[1:]
    return ([f"# Embedded verified RULE-SET: {url}"]
            + [f"{rule},{policy}" for rule in rulesets[url]]
            + ["# End embedded RULE-SET"])


def parse_manual(path: Path) -> list[str]:
    result = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid manual rule {line}")
        normalized = domain_rule(parts[0], parts[1])
        if (not is_openai_specific_rule(normalized)
                and normalized not in OFFICIAL_CHATGPT_SHARED_RULES):
            raise ValueError(
                "Manual rule is neither verified OpenAI-specific nor an "
                "explicitly approved official ChatGPT shared dependency: "
                + normalized
            )
        result.append(normalized)
    if len(result) < 20 or "DOMAIN-SUFFIX,openai.com" not in result or "DOMAIN-SUFFIX,chatgpt.com" not in result:
        raise ValueError("Manual OpenAI fallback is incomplete")
    return list(dict.fromkeys(result))


def split_base(source: str):
    source = source.lstrip("\ufeff").replace("\r\n", "\n")
    matches = list(re.finditer(r"(?m)^\[([^\]\n]+)\]\s*$", source))
    sections = [m.group(1) for m in matches]
    if sections != ["General", "Rule", "URL Rewrite", "MITM"]:
        raise ValueError(f"Johnshall section layout changed: {sections}")
    return (source[:matches[0].start()],
            source[matches[0].end():matches[1].start()].strip("\n"),
            source[matches[1].end():matches[2].start()].strip("\n"),
            source[matches[2].start():].strip("\n"))


def generate(base: str, ips: list[str], domains: list[str], manual: list[str], settings: dict[str, str] | None = None,
             rulesets: dict[str, list[str]] | None = None):
    settings = settings if settings is not None else load_settings()
    openai_node = settings["openai_node_name"]
    johnshall_proxy_node = settings["johnshall_proxy_node_name"]
    if len(base.encode()) < 1_000_000 or len(base.splitlines()) < 50_000:
        raise ValueError("Johnshall config is unexpectedly small")
    banner, general, original_rules, tail = split_base(base)
    if not base.rstrip().endswith(JOHNSHALL_FOOTER):
        raise ValueError("Johnshall end marker missing; config may be truncated")
    rewrite, mitm = tail.split("[MITM]", 1)
    if not any(row.strip() and not row.lstrip().startswith(("#", "[")) for row in rewrite.splitlines()):
        raise ValueError("Johnshall URL Rewrite section is empty")
    if not re.search(r"(?m)^hostname\s*=\s*\S[^\r\n]*$", mitm):
        raise ValueError("Johnshall MITM hostname setting is missing")
    general_lines = [line for line in general.splitlines()
                     if not ("=" in line and line.partition("=")[0].strip() in DNS_KEYS)]
    changed = []
    converted = 0
    before_ads = 0
    for line in original_rules.splitlines():
        if not line.lstrip().startswith("#") and line.strip():
            if re.search(r",reject(?:,|$)", line, re.I):
                before_ads += 1
            line, count = PROXY_POLICY.subn(lambda _: f",{johnshall_proxy_node}", line)
            converted += count
            changed.extend(inline_ruleset(line, rulesets or {}))
        else:
            changed.append(line)
    if converted < 10000 or before_ads < 20000:
        raise ValueError(f"Original rules unexpectedly changed: proxy={converted}, reject={before_ads}")
    if sum(line.strip().lower() == "final,direct" for line in changed) != 1:
        raise ValueError("Missing/duplicate Johnshall final DIRECT")
    if any(PROXY_POLICY.search(line) for line in changed if line and not line.lstrip().startswith("#")):
        raise ValueError("Unconverted original Proxy rule found")
    # IP rule priority first. This only covers official Voice IPs, NOT all OpenAI.
    openai_ip_rules = [f"{rule},{openai_node},no-resolve" for rule in ips]
    # Prevent client-side resolution for OpenAI domains: the OpenAI proxy sees
    # and resolves the original hostname. DOMAIN-WILDCARD remains unchanged
    # because support for this modifier varies with Shadowrocket versions.
    def openai_domain(rule: str) -> str:
        kind = rule.split(",", 1)[0]
        option = ",force-remote-dns" if kind in {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"} else ""
        return f"{rule},{openai_node}{option}"

    openai_auto_domains = [openai_domain(rule) for rule in domains]
    openai_manual = [openai_domain(rule) for rule in manual]
    result = (
        banner + "# Automatically generated from Johnshall; do not edit output directly.\n"
        + "# Source: rileyaaa/shadowrocket-openai-pac, daily checked by GitHub Actions.\n"
        + f"# {openai_node} = OpenAI, {johnshall_proxy_node} = original Proxy, original REJECT/DIRECT kept.\n\n"
        + "[General]\n" + "\n".join(general_lines) + "\n\n" + render_dns(settings) + "\n"
        + "[Rule]\n"
        + "# [1a] OpenAI automatic rules - official Voice destination IPs\n" + "\n".join(openai_ip_rules) + "\n\n"
        + "# [1b] OpenAI automatic rules - public domain rules\n" + "\n".join(openai_auto_domains) + "\n\n"
        + "# [2] Independent manual OpenAI fallback (no cross-layer dedup)\n"
        + "\n".join(openai_manual) + "\n\n"
        + "# [3] Johnshall full original rules, Proxy mapped to exact configured node\n"
        + "\n".join(changed) + "\n\n" + tail + "\n"
    )
    assert result.count("[Rule]") == 1
    if "[Proxy Group]" in result:
        raise ValueError("Unexpected proxy group in standalone config")
    return result, {"johnshall_lines": len(original_rules.splitlines()), "mapped_proxy_to_johnshall_node": converted,
                    "retained_ad_rules": before_ads, "voice_prefixes": len(ips),
                    "automatic_openai_domains": len(domains), "manual_openai_rules": len(manual)}


def write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")



UPSTREAM_SIZE_GUARDS = {
    "voice_prefixes": (0.70, 2.00),
    "automatic_openai_domains": (0.75, 2.00),
    "johnshall_lines": (0.85, 1.50),
    "mapped_proxy_to_johnshall_node": (0.85, 1.50),
    "retained_ad_rules": (0.85, 1.50),
}


def validate_upstream_change(stats: dict[str, int], old_state: dict | None) -> None:
    """Compare with the last published snapshot; reject implausible changes."""
    if old_state is None:
        return
    old_stats = old_state.get("statistics")
    if not isinstance(old_stats, dict):
        raise ValueError("Previous source statistics missing")
    anomalies = []
    for key, (minimum, maximum) in UPSTREAM_SIZE_GUARDS.items():
        before, after = old_stats.get(key), stats.get(key)
        if (type(before) is not int or type(after) is not int
                or before <= 0 or after <= 0):
            raise ValueError(f"Invalid baseline/current statistics: {key}")
        if after < before * minimum or after > before * maximum:
            anomalies.append(f"{key}: {before} -> {after}, allowed {minimum:.0%}-{maximum:.0%}")
    if anomalies:
        raise ValueError(
            "UPSTREAM ANOMALY: publication blocked; last good config retained. "
            + "; ".join(anomalies)
        )


def excluded_auto_rule_sources(source_lists: dict[str, list[str]],
                               accepted: list[str],
                               unparsed_sources: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    """Collect rejected community rules with provenance, never as routing rules."""
    allowed = set(accepted)
    excluded: dict[str, set[str]] = {}
    for source_name, rules in source_lists.items():
        for rule in rules:
            if rule not in allowed:
                excluded.setdefault(rule, set()).add(source_name)
    for source_name, rules in (unparsed_sources or {}).items():
        for rule in rules:
            excluded.setdefault(rule, set()).add(source_name)
    return {rule: sorted(names) for rule, names in sorted(excluded.items())}


def active_auto_rules(text: str) -> set[str]:
    return {row.strip() for row in text.splitlines()
            if row.strip() and not row.lstrip().startswith("#")}


def make_sync_report(old_state: dict | None, current: dict, before_auto: str,
                     after_auto: str, config_changed: bool,
                     excluded_sources: dict[str, list[str]] | None = None) -> dict:
    old_state = old_state or {}
    old_sources = old_state.get("sources", {})
    old_stats = old_state.get("statistics", {})
    old_rules, new_rules = active_auto_rules(before_auto), active_auto_rules(after_auto)
    excluded_now = current.get("review", {}).get("excluded_auto_rules", [])
    excluded_before = old_state.get("review", {}).get("excluded_auto_rules")
    if not isinstance(excluded_now, list) or any(
        not isinstance(rule, str) for rule in excluded_now
    ):
        raise ValueError("Invalid excluded-auto-rule review snapshot")
    has_baseline = isinstance(excluded_before, list)
    added_rejected = (
        sorted(set(excluded_now) - set(excluded_before)) if has_baseline else []
    )
    origin = excluded_sources or {}
    return {
        "changed_sources": sorted(
            key for key, source in current["sources"].items()
            if old_sources.get(key, {}).get("sha256") != source["sha256"]
        ),
        "config_changed": config_changed,
        "settings_changed": old_state.get("settings") != current["settings"],
        "statistics": current["statistics"],
        "stat_deltas": {
            k: v - old_stats[k] for k, v in current["statistics"].items()
            if type(v) is int and type(old_stats.get(k)) is int
        },
        "auto_added": sorted(new_rules - old_rules),
        "auto_removed": sorted(old_rules - new_rules),
        "excluded_review_total": len(excluded_now),
        "excluded_review_baseline_created": not has_baseline,
        "new_excluded_candidates": [
            {"rule": rule, "sources": sorted(origin.get(rule, []))}
            for rule in added_rejected
        ],
    }


def run():
    args = argparse.ArgumentParser()
    args.add_argument("--upstream-file", type=Path)
    args.add_argument("--voice-file", type=Path)
    args.add_argument("--domain-dir", type=Path)
    args.add_argument("--ruleset-dir", type=Path, help="Offline snapshots named apple_news.txt, etc.")
    args.add_argument("--report-file", type=Path)
    opt = args.parse_args()
    settings = load_settings()
    original = opt.upstream_file.read_bytes() if opt.upstream_file else fetch(BASE_URL, 1_000_000)
    voice_raw = opt.voice_file.read_bytes() if opt.voice_file else fetch(VOICE_URL)
    source_data = {"johnshall": (BASE_URL, original), "voice": (VOICE_URL, voice_raw)}
    source_lists = {}
    unparsed_sources = {}
    for name, (url, fmt) in DOMAIN_SOURCES.items():
        raw = (opt.domain_dir / f"{name}.txt").read_bytes() if opt.domain_dir else fetch(url)
        source_data[name] = (url, raw)
        unparsed_sources[name] = []
        source_lists[name] = parse_domain_list(raw.decode("utf-8-sig"), fmt, unparsed=unparsed_sources[name])
    rulesets = {}
    for name, (url, _) in RULESET_SOURCES.items():
        raw = (opt.ruleset_dir / f"{name}.txt").read_bytes() if opt.ruleset_dir else fetch(url)
        source_data[name] = (url, raw)
        rulesets[url] = parse_embedded_ruleset(raw.decode("utf-8-sig"))
    ips = parse_voice(voice_raw)
    all_auto_domains = list(dict.fromkeys(rule for one in source_lists.values() for rule in one))
    domains = filter_auto_domains(all_auto_domains)
    excluded_candidates = excluded_auto_rule_sources(source_lists, domains, unparsed_sources)
    manual = parse_manual(ROOT / "config/manual-openai.rules")
    emitted_auto, emitted_manual = compact_openai_rules(domains, manual)
    built, stats = generate(
        original.decode("utf-8-sig"), ips, emitted_auto, emitted_manual, settings=settings, rulesets=rulesets
    )
    stats["excluded_shared_auto_domains"] = len(all_auto_domains) - len(domains)
    stats["auto_input_rules"] = len(domains)
    stats["manual_backup_rules"] = len(manual)
    stats["suppressed_redundant_auto_rules"] = len(domains) - len(emitted_auto)
    stats["suppressed_redundant_manual_rules"] = len(manual) - len(emitted_manual)
    stats["cross_layer_duplicate_rules_retained"] = len(
        set(emitted_auto) & set(emitted_manual)
    )
    stats["auto_total_ip_and_domain_rules"] = len(ips) + len(emitted_auto)
    state_path = ROOT / "data/sources.json"
    old_state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
    auto_path = ROOT / "rules/openai-auto.list"
    old_auto = auto_path.read_text(encoding="utf-8") if auto_path.exists() else ""
    stats.update(validate_voice_coverage(ips, old_auto, has_baseline=old_state is not None))
    stats["unparsed_upstream_rules"] = len({rule for rules in unparsed_sources.values() for rule in rules})
    stats["embedded_ruleset_rules"] = sum(len(rules) for rules in rulesets.values())
    for name, (url, _) in RULESET_SOURCES.items():
        prior = (old_state or {}).get("sources", {}).get(name)
        if prior is not None:
            previous = prior.get("rule_count")
            if (type(previous) is not int or previous <= 0
                    or not previous * 0.85 <= len(rulesets[url]) <= previous * 1.50):
                raise ValueError(f"Embedded ruleset count changed unexpectedly: {name}")
    validate_upstream_change(stats, old_state)

    # Both OpenAI sources remain independent; do not change routing semantics.
    automatic_source = (
        "# OpenAI automatic rules: official Voice destination IPs + public domains\n"
        "# No node name here: route is supplied while merging into .conf\n"
        "# Voice IPs (destination-only); never use OpenAI egress source ranges\n"
        + "\n".join(f"{rule},no-resolve" for rule in ips) + "\n"
        + "# Dedicated first-party and explicitly verified hosted domains\n"
        + "\n".join(emitted_auto) + "\n"
    )
    source_state = {
        "sources": {name: {"url": url, "sha256": hashlib.sha256(data).hexdigest()}
                    for name, (url, data) in source_data.items()},
        "settings": settings, "statistics": stats,
        # Only a review baseline: never feed these rejected rules into .conf.
        "review": {"excluded_auto_rules": list(excluded_candidates)},
    }
    for name, (url, _) in RULESET_SOURCES.items():
        source_state["sources"][name]["rule_count"] = len(rulesets[url])
    changed = not CONFIG.exists() or CONFIG.read_text(encoding="utf-8") != built
    report = make_sync_report(
        old_state, source_state, old_auto, automatic_source, changed,
        excluded_sources=excluded_candidates,
    )
    # All validation is complete before touching generated output files.
    write_if_changed(CONFIG, built)
    write_if_changed(auto_path, automatic_source)
    for name, (_, snapshot_path) in RULESET_SOURCES.items():
        write_if_changed(ROOT / snapshot_path, source_data[name][1].decode("utf-8"))
    write_if_changed(state_path, json.dumps(source_state, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    if opt.report_file:
        write_if_changed(opt.report_file, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(stats, ensure_ascii=False))
    print(f"Saved {CONFIG} ({len(built.encode())} bytes)")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
