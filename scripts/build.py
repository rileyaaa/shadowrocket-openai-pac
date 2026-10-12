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

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://raw.githubusercontent.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever/release/sr_top500_banlist_ad.conf"
VOICE_URL = "https://openai.com/chatgpt-voice.json"
DOMAIN_SOURCES = {
    "metacubex": ("https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/openai.list", "meta"),
    "acl4ssr": ("https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Ruleset/OpenAi.list", "typed"),
    "blackmatrix7": ("https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/OpenAI/OpenAI.list", "typed"),
}
RULE_TYPES = {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-WILDCARD"}
DOMAIN_CHARS = re.compile(r"^[a-z0-9_.*?-]+$")
PROXY_POLICY = re.compile(r",proxy(?=,|\s*$)", flags=re.I)
CONFIG = ROOT / "Shadowrocket_Johnshall_JP_KR.conf"

DNS = """# Encrypted AliDNS first; Google DNS over JP as fallback
dns-server = https://dns.alidns.com/dns-query#no-h3
direct-dns-server = https://dns.alidns.com/dns-query#no-h3
fallback-dns-server = https://dns.google/dns-query#proxy=JP
proxy-dns-server = https://dns.alidns.com/dns-query#no-h3
dns-direct-system = false
dns-fallback-system = false
dns-direct-fallback-proxy = false
hijack-dns = 8.8.8.8:53,8.8.4.4:53,1.1.1.1:53,1.0.0.1:53,223.5.5.5:53,223.6.6.6:53
"""
DNS_KEYS = {line.partition("=")[0].strip() for line in DNS.splitlines() if "=" in line and not line.startswith("#")}
GROUPS = """[Proxy Group]
# Import the HY/airport subscription separately; choose actual Japanese/Korean nodes.
# JP has NO KR/DIRECT failover. Check group selection after first import.
JP = select,policy-regex-filter=(?i)(日本|东京|東京|大阪|Japan|Tokyo|Osaka|JP)
KR = select,policy-regex-filter=(?i)(韩国|韓國|首尔|首爾|Korea|Seoul|KR)
"""


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


def parse_voice(raw: bytes) -> list[str]:
    doc = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(doc, dict) or not isinstance(doc.get("prefixes"), list):
        raise ValueError("Voice JSON unexpectedly changed its prefixes format")
    results = set()
    for item in doc["prefixes"]:
        if not isinstance(item, dict):
            raise ValueError("Unexpected voice IP entry")
        value = item.get("ipv4Prefix") or item.get("ipv6Prefix")
        if not value:
            raise ValueError(f"Missing voice prefix in {item}")
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
    if len(result) < 40 or "DOMAIN-SUFFIX,openai.com" not in result or "DOMAIN-SUFFIX,chatgpt.com" not in result:
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


def generate(base: str, ips: list[str], domains: list[str], manual: list[str]):
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
            line, count = PROXY_POLICY.subn(",KR", line)
            converted += count
        changed.append(line)
    if converted < 10000 or before_ads < 20000:
        raise ValueError(f"Original rules unexpectedly changed: proxy={converted}, reject={before_ads}")
    if sum(line.strip().lower() == "final,direct" for line in changed) != 1:
        raise ValueError("Missing/duplicate Johnshall final DIRECT")
    if any(PROXY_POLICY.search(line) for line in changed if line and not line.lstrip().startswith("#")):
        raise ValueError("Unconverted original Proxy rule found")
    # IP rule priority first. This only covers official voice IPs, NOT all of OpenAI.
    jp_ip_rules = [f"{rule},JP,no-resolve" for rule in ips]
    jp_auto_domains = [f"{rule},JP" for rule in domains]
    jp_manual = [f"{rule},JP" for rule in manual]
    result = (
        banner + "# Automatically generated from Johnshall; do not edit output directly.\n"
        + "# Source: rileyaaa/shadowrocket-openai-pac, daily checked by GitHub Actions.\n"
        + "# JP = OpenAI, KR = other original Proxy, original REJECT/DIRECT kept.\n\n"
        + "[General]\n" + "\n".join(general_lines) + "\n\n" + DNS + "\n"
        + GROUPS + "\n"
        + "[Rule]\n"
        + "# [1] Official ChatGPT Voice IP prefixes, automatic\n" + "\n".join(jp_ip_rules) + "\n\n"
        + "# [2] OpenAI automatically maintained domain rules\n" + "\n".join(jp_auto_domains) + "\n\n"
        + "# [3] Complete custom HY ACL fallback, including broad UDP/3478\n"
        + "\n".join(jp_manual) + "\n\n"
        + "# [4] Johnshall complete original rules, Proxy policies mapped to KR\n"
        + "\n".join(changed) + "\n\n" + tail + "\n"
    )
    assert result.count("[Rule]") == 1
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
    original = opt.upstream_file.read_bytes() if opt.upstream_file else fetch(BASE_URL, 1_000_000)
    voice_raw = opt.voice_file.read_bytes() if opt.voice_file else fetch(VOICE_URL)
    source_data = {"johnshall": (BASE_URL, original), "voice": (VOICE_URL, voice_raw)}
    lists = []
    for name, (url, fmt) in DOMAIN_SOURCES.items():
        raw = (opt.domain_dir / f"{name}.txt").read_bytes() if opt.domain_dir else fetch(url)
        source_data[name] = (url, raw)
        lists.append(parse_domain_list(raw.decode("utf-8-sig"), fmt))
    ips = parse_voice(voice_raw)
    domains = list(dict.fromkeys(rule for one in lists for rule in one))
    manual = parse_manual(ROOT / "config/manual-openai.rules")
    built, stats = generate(original.decode("utf-8-sig"), ips, domains, manual)
    # Validation has now succeeded, so publish all outputs.
    write_if_changed(CONFIG, built)
    write_if_changed(ROOT / "rules/openai-auto-domains.list", "# Automatically synced from three domain sources\n" + "\n".join(domains) + "\n")
    write_if_changed(ROOT / "rules/openai-voice-ips.list", "# Official ChatGPT Voice IP ranges only\n" + "\n".join(ips) + "\n")
    state = {"sources": {name: {"url": url, "sha256": hashlib.sha256(data).hexdigest()}
                         for name, (url, data) in source_data.items()}, "statistics": stats}
    write_if_changed(ROOT / "data/sources.json", json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps(stats, ensure_ascii=False))
    print(f"Saved {CONFIG} ({len(built.encode())} bytes)")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
