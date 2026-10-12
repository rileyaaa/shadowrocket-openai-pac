#!/usr/bin/env python3
"""Build a complete standalone Shadowrocket config using Johnshall as the base.

Downloads, validates and merges upstream sources. Any failed source aborts
without changing the existing published file.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import sys
import urllib.request
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://raw.githubusercontent.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever/release/sr_top500_banlist_ad.conf"
VOICE_URL = "https://openai.com/chatgpt-voice.json"
DOMAIN_SOURCES = {
    "metacubex": ("https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/openai.list", "meta"),
    "acl4ssr": ("https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Ruleset/OpenAi.list", "typed"),
    "blackmatrix7": ("https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/OpenAI/OpenAI.list", "typed"),
}
RULE_TYPES = {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-WILDCARD"}

# Only domains dedicated to OpenAI may override the original Johnshall route.
# OpenAI rule-set providers also include unrelated shared services such as
# stripe.com, auth0.com, sentry.io and launchdarkly.com: NEVER import those.
OPENAI_SPECIFIC_SUFFIXES = frozenset({
    "openai.com", "chatgpt.com", "chatgpt.site", "chat.com",
    "oaistatic.com", "oaistatsig.com", "oaiusercontent.com",
    "sora.com", "crixet.com", "chatgpt.livekit.cloud",
    "openai.com.cdn.cloudflare.net",
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
})
OPENAI_SPECIFIC_WILDCARDS = frozenset({
    "chatgpt-async-webps-prod-*.webpubsub.azure.com",
})
DOMAIN_CHARS = re.compile(r"^[a-z0-9_.*?-]+$")
PROXY_POLICY = re.compile(r",proxy(?=,|\s*$)", flags=re.I)
CONFIG = ROOT / "Shadowrocket_Johnshall_JP_KR.conf"

DNS = """# Route-aware DNS:
# Proxy domain names are resolved remotely by their chosen JP or KR node.
# If Shadowrocket must resolve locally for proxy routing, use Google DoH over KR.
# DIRECT traffic and proxy-server hostname bootstrap use AliDNS encrypted DoH.
# A global fallback cannot vary by rule: use AliDNS rather than silently
# sending DIRECT-domain DNS queries through the Korean proxy.
dns-server = https://dns.google/dns-query#proxy=KR
direct-dns-server = https://dns.alidns.com/dns-query#no-h3
fallback-dns-server = https://dns.alidns.com/dns-query#no-h3
proxy-dns-server = https://dns.alidns.com/dns-query#no-h3
dns-direct-system = false
dns-fallback-system = false
dns-direct-fallback-proxy = false
hijack-dns = 8.8.8.8:53,8.8.4.4:53,1.1.1.1:53,1.0.0.1:53,223.5.5.5:53,223.6.6.6:53
"""
DNS_KEYS = {line.partition("=")[0].strip() for line in DNS.splitlines() if "=" in line and not line.startswith("#")}
# Two exact Shadowrocket node names, no proxy groups or automatic node selection.
SETTINGS_PATH = ROOT / "config/user-settings.json"
SETTING_KEYS = {"jp_node_name", "kr_node_name"}
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
    if data["jp_node_name"].casefold() == data["kr_node_name"].casefold():
        raise ValueError("JP and KR must not point to the same exact node")
    return data


def render_dns(settings: dict[str, str]) -> str:
    # Local DNS for proxy-classified lookups uses the Korean node.
    # Explicit OpenAI rules below force remote resolution by the Japan node.
    encoded = quote(settings["kr_node_name"], safe="")
    return DNS.replace("#proxy=KR", f"#proxy={encoded}")


def fetch(url: str, minimum: int = 50) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "shadowrocket-openai-pac/1.0", "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=75) as response:
        content = response.read(13_000_000)
        if not 200 <= response.status < 300:
            raise ValueError(f"Unexpected HTTP status for {url}: {response.status}")
        if not minimum <= len(content) < 13_000_000:
            raise ValueError(f"Truncated or oversized data from {url}: {len(content)}")
        return content


def domain_rule(kind: str, value: str) -> str:
    kind = kind.upper().strip()
    value = value.lower().strip()
    if kind not in RULE_TYPES or not DOMAIN_CHARS.fullmatch(value):
        raise ValueError(f"Invalid domain rule {kind},{value}")
    if kind != "DOMAIN-WILDCARD" and ("*" in value or "?" in value):
        raise ValueError(f"Unexpected wildcard {kind},{value}")
    return f"{kind},{value}"


def parse_domain_list(source: str, fmt: str) -> list[str]:
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
            # Deliberately exclude over-broad IP-ASN and third-party IP ranges.
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
    if value in OPENAI_SPECIFIC_HOSTS:
        return True
    if kind == "DOMAIN-SUFFIX":
        return value in OPENAI_SPECIFIC_SUFFIXES
    return any(value == suffix or value.endswith("." + suffix)
               for suffix in OPENAI_SPECIFIC_SUFFIXES)


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
    if len(auto_kept) < 10 or len(manual_kept) < 10:
        raise ValueError("Automatic or manual OpenAI rule layer is unexpectedly small")
    return auto_kept, manual_kept


def parse_voice(raw: bytes) -> list[str]:
    doc = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(doc, dict) or not isinstance(doc.get("prefixes"), list):
        raise ValueError("Voice JSON unexpectedly changed its prefixes format")
    results = set()
    for item in doc["prefixes"]:
        if not isinstance(item, dict):
            raise ValueError("Unexpected voice IP entry")
        values = [item[key] for key in ("ipv4Prefix", "ipv6Prefix") if item.get(key)]
        if not values:
            raise ValueError(f"Missing voice prefix in {item}")
        for value in values:
            network = ipaddress.ip_network(value, strict=False)
            if not network.is_global or network.prefixlen == 0:
                raise ValueError(f"Unsafe voice network: {network}")
            results.add(network)
    if not 5 <= len(results) <= 3000:
        raise ValueError(f"Unexpected voice prefix count: {len(results)}")
    networks = sorted(results, key=lambda ip: (ip.version, int(ip.network_address), ip.prefixlen))
    return [f"{'IP-CIDR6' if n.version == 6 else 'IP-CIDR'},{n}" for n in networks]


def parse_manual(path: Path) -> list[str]:
    result = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "AND,((PROTOCOL,UDP),(DST-PORT,3478))":
            result.append(line)
            continue
        parts = line.split(",", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid manual rule {line}")
        result.append(domain_rule(parts[0], parts[1]))
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


def generate(base: str, ips: list[str], domains: list[str], manual: list[str], settings: dict[str, str] | None = None):
    settings = settings if settings is not None else load_settings()
    jp_node = settings["jp_node_name"]
    kr_node = settings["kr_node_name"]
    if len(base.encode()) < 1_000_000 or len(base.splitlines()) < 50_000:
        raise ValueError("Johnshall config is unexpectedly small")
    banner, general, original_rules, tail = split_base(base)
    general_lines = [line for line in general.splitlines()
                     if not ("=" in line and line.partition("=")[0].strip() in DNS_KEYS)]
    changed = []
    converted = 0
    before_ads = 0
    for line in original_rules.splitlines():
        if not line.lstrip().startswith("#") and line.strip():
            if re.search(r",reject(?:,|$)", line, re.I):
                before_ads += 1
            line, count = PROXY_POLICY.subn(lambda _: f",{kr_node}", line)
            converted += count
        changed.append(line)
    if converted < 10000 or before_ads < 20000:
        raise ValueError(f"Original rules unexpectedly changed: proxy={converted}, reject={before_ads}")
    if sum(line.strip().lower() == "final,direct" for line in changed) != 1:
        raise ValueError("Missing/duplicate Johnshall final DIRECT")
    if any(PROXY_POLICY.search(line) for line in changed if line and not line.lstrip().startswith("#")):
        raise ValueError("Unconverted original Proxy rule found")
    # IP rule priority first. This only covers official Voice IPs, NOT all OpenAI.
    jp_ip_rules = [f"{rule},{jp_node},no-resolve" for rule in ips]
    # Prevent client-side resolution for OpenAI domains: the JP proxy sees
    # and resolves the original hostname. DOMAIN-WILDCARD remains unchanged
    # because support for this modifier varies with Shadowrocket versions.
    def jp_domain(rule: str) -> str:
        kind = rule.split(",", 1)[0]
        option = ",force-remote-dns" if kind in {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"} else ""
        return f"{rule},{jp_node}{option}"

    jp_auto_domains = [jp_domain(rule) for rule in domains]
    jp_manual = [jp_domain(rule) for rule in manual]
    result = (
        banner + "# Automatically generated from Johnshall; do not edit output directly.\n"
        + "# Source: rileyaaa/shadowrocket-openai-pac, daily checked by GitHub Actions.\n"
        + f"# {jp_node} = OpenAI, {kr_node} = original Proxy, original REJECT/DIRECT kept.\n\n"
        + "[General]\n" + "\n".join(general_lines) + "\n\n" + render_dns(settings) + "\n"
        + "[Rule]\n"
        + "# [1] Official ChatGPT Voice IP prefixes, automatic\n" + "\n".join(jp_ip_rules) + "\n\n"
        + "# [2] Independent OpenAI auto layer; JP remote DNS\n" + "\n".join(jp_auto_domains) + "\n\n"
        + "# [3] Independent manual OpenAI fallback layer; NOT deduplicated against auto\n"
        + "\n".join(jp_manual) + "\n\n"
        + "# [4] Johnshall complete original rules, Proxy policies mapped to exact KR node\n"
        + "\n".join(changed) + "\n\n" + tail + "\n"
    )
    assert result.count("[Rule]") == 1
    if "[Proxy Group]" in result:
        raise ValueError("Unexpected proxy group in standalone config")
    return result, {"johnshall_lines": len(original_rules.splitlines()), "mapped_proxy_to_kr": converted,
                    "retained_ad_rules": before_ads, "voice_prefixes": len(ips),
                    "automatic_openai_domains": len(domains), "manual_openai_rules": len(manual)}


def write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")


def run():
    args = argparse.ArgumentParser()
    args.add_argument("--upstream-file", type=Path)
    args.add_argument("--voice-file", type=Path)
    args.add_argument("--domain-dir", type=Path)
    opt = args.parse_args()
    settings = load_settings()
    original = opt.upstream_file.read_bytes() if opt.upstream_file else fetch(BASE_URL, 1_000_000)
    voice_raw = opt.voice_file.read_bytes() if opt.voice_file else fetch(VOICE_URL)
    source_data = {"johnshall": (BASE_URL, original), "voice": (VOICE_URL, voice_raw)}
    lists = []
    for name, (url, fmt) in DOMAIN_SOURCES.items():
        raw = (opt.domain_dir / f"{name}.txt").read_bytes() if opt.domain_dir else fetch(url)
        source_data[name] = (url, raw)
        lists.append(parse_domain_list(raw.decode("utf-8-sig"), fmt))
    ips = parse_voice(voice_raw)
    all_auto_domains = list(dict.fromkeys(rule for one in lists for rule in one))
    domains = filter_auto_domains(all_auto_domains)
    manual = parse_manual(ROOT / "config/manual-openai.rules")
    emitted_auto, emitted_manual = compact_openai_rules(domains, manual)
    built, stats = generate(
        original.decode("utf-8-sig"), ips, emitted_auto, emitted_manual, settings=settings
    )
    stats["excluded_shared_auto_domains"] = len(all_auto_domains) - len(domains)
    stats["auto_input_rules"] = len(domains)
    stats["manual_backup_rules"] = len(manual)
    stats["suppressed_redundant_auto_rules"] = len(domains) - len(emitted_auto)
    stats["suppressed_redundant_manual_rules"] = len(manual) - len(emitted_manual)
    stats["cross_layer_duplicate_rules_retained"] = len(
        set(emitted_auto) & set(emitted_manual)
    )
    # Validation has now succeeded, so publish all outputs.
    write_if_changed(CONFIG, built)
    write_if_changed(
        ROOT / "rules/openai-auto-domains.list",
        "# Independent OpenAI automatic domain layer; upstream managed\n"
        + "\n".join(emitted_auto) + "\n",
    )
    write_if_changed(
        ROOT / "rules/openai-manual-fallback.list",
        "# Independent OpenAI manual fallback; optimized against itself ONLY\n"
        + "# Source: config/manual-openai.rules (shared third-party hosts stay commented)\n"
        + "\n".join(emitted_manual) + "\n",
    )
    write_if_changed(ROOT / "rules/openai-voice-ips.list", "# Official ChatGPT Voice IP ranges only\n" + "\n".join(ips) + "\n")
    state = {"sources": {name: {"url": url, "sha256": hashlib.sha256(data).hexdigest()}
                         for name, (url, data) in source_data.items()},
             "settings": settings, "statistics": stats}
    write_if_changed(ROOT / "data/sources.json", json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps(stats, ensure_ascii=False))
    print(f"Saved {CONFIG} ({len(built.encode())} bytes)")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
