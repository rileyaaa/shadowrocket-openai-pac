"""Evidence-bound routing review. Community lists are candidates, never proof.

No LLM, DNS lookup, arbitrary URL fetch, regex execution or source voting grants
authority. Every run uses fresh, narrowly parsed official evidence. Prior review
decisions are history only and cannot authorize a rule on a later run.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import ipaddress
import re

NETWORK_URL = "https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps"
VOICE_URL = "https://openai.com/chatgpt-voice.json"
ARTICLE_TITLE = "Network recommendations for ChatGPT errors on web and apps"
ALLOWLIST_HEADING = "OpenAI/ChatGPT domains to allowlist"
ANCHORS = {f"DOMAIN-SUFFIX,{name}" for name in (
    "openai.com", "chatgpt.com", "oaistatic.com", "oaiusercontent.com")}
# A new whole registrable domain, even in official prose, needs a scope review.
# These roots already have an explicit project decision and live official proof.
REVIEWED_WILDCARD_ROOTS = {
    "openai.com", "chatgpt.com", "oaistatic.com", "oaiusercontent.com",
    "oaistatsig.com", "intercom.io", "intercomcdn.com",
}
# Never infer platform-wide routing from a tenant host or an official wildcard.
SHARED_PLATFORM_ROOTS = {
    "amazonaws.com", "azure.com", "azureedge.net", "azurefd.net",
    "blob.core.windows.net", "webpubsub.azure.com", "cloudfront.net",
    "cloudflare.com", "cloudflare.net", "vercel.app", "livekit.cloud",
    "workos.com", "workoscdn.com", "stripe.com", "sentry.io", "auth0.com",
    "arkoselabs.com", "qualtrics.com", "imgix.net", "sendgrid.net",
    "browser-intake-datadoghq.com",
}
STATUSES = ("approved", "covered", "pending", "rejected", "withdrawn")
REASONS = {
    "broad_match_forbidden": "整 ASN、关键词或全局协议/端口匹配超出允许边界",
    "official_network": "当前官方网络清单明确覆盖，未扩大官方范围",
    "reviewed_policy": "已有受审查的固定范围；不冒充本次官方新证据",
    "unsupported_or_invalid_syntax": "格式未知或无法安全解释，暂不转换为路由",
    "unsafe_ip_scope": "非公网、非目标用途或网段范围过宽",
    "official_voice_destination": "已被当前官方 Voice 目的地址完整覆盖",
    "ip_exceeds_official_destination_scope": "候选网段包含官方未确认的地址",
    "no_official_destination_ip_evidence": "当前官方 Voice 目的地址清单未确认此 IP",
    "shared_platform_scope_forbidden": "整共享平台范围过宽，只能审查具体目标",
    "new_whole_domain_needs_scope_review": "新增整域通配需核验所有权和影响范围",
    "existing_route_coverage": "现有规则已完整覆盖；不作为新自动授权依据",
    "candidate_exceeds_evidence_scope": "候选规则比已确认的主机或子域范围更宽",
    "no_current_official_evidence": "缺少当前官方证据，社区收录次数不构成证明",
    "no_current_source": "当前来源已撤回，历史审批不能继续授权",
    "official_evidence_unavailable": "官方网络证据暂不可读，暂停新增域名授权",
}
HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


def valid_host(host: str) -> bool:
    labels = host.split(".")
    return (len(host) <= 253 and len(labels) >= 2
            and all(HOST_LABEL.fullmatch(label) for label in labels)
            and bool(re.fullmatch(r"[a-z]{2,63}|xn--[a-z0-9-]+", labels[-1])))


def covers(broad: str, narrow: str) -> bool:
    if broad == narrow:
        return True
    a, _, host = broad.partition(",")
    b, _, target = narrow.partition(",")
    return (a == "DOMAIN-SUFFIX" and b in {"DOMAIN", "DOMAIN-SUFFIX"}
            and (target == host or target.endswith("." + host)))


class AllowlistParser(HTMLParser):
    """Read only the one allowlist section, never scripts, links or other lists."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.heading = None
        self.heading_text = []
        self.titles = []
        self.section_count = 0
        self.in_section = False
        self.finished_section = False
        self.list_count = 0
        self.in_list = False
        self.item = None
        self.entries = []
        self.ignored = []
        self.html_closed = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template"}:
            self.ignored.append(tag)
        if self.ignored:
            return
        if tag in {"h1", "h2"}:
            if self.in_section:
                if self.in_list or self.item is not None:
                    raise ValueError("Official allowlist has an unclosed list")
                self.finished_section = True
                self.in_section = False
            self.heading, self.heading_text = tag, []
        if self.in_section and tag == "ul":
            self.list_count += 1
            if self.in_list or self.list_count != 1:
                raise ValueError("Official allowlist list structure changed")
            self.in_list = True
        if self.in_section and tag == "li":
            if not self.in_list or self.item is not None:
                raise ValueError("Official allowlist item structure changed")
            self.item = []
        if self.item is not None and tag in {"p", "div", "br"}:
            self.item.append(" ")

    def handle_endtag(self, tag):
        if self.ignored:
            if tag == self.ignored[-1]:
                self.ignored.pop()
            return
        if tag == self.heading:
            text = " ".join("".join(self.heading_text).split())
            if tag == "h1":
                self.titles.append(text)
            elif text == ALLOWLIST_HEADING:
                self.section_count += 1
                self.in_section = True
            self.heading = None
        if self.in_section and tag == "li":
            if self.item is None:
                raise ValueError("Unexpected official allowlist item closing tag")
            self.entries.append("".join(self.item).strip().lower())
            self.item = None
        if self.item is not None and tag in {"p", "div"}:
            self.item.append(" ")
        if self.in_section and tag == "ul":
            if not self.in_list or self.item is not None:
                raise ValueError("Official allowlist is incomplete")
            self.in_list = False
        if tag == "html":
            self.html_closed = True

    def handle_data(self, text):
        if self.ignored:
            return
        if self.heading:
            self.heading_text.append(text)
        if self.item is not None:
            self.item.append(text)


def parse_official_network(raw: bytes) -> list[str]:
    parser = AllowlistParser()
    parser.feed(raw.decode("utf-8-sig"))
    parser.close()
    if (parser.titles != [ARTICLE_TITLE] or parser.section_count != 1
            or not parser.finished_section or not parser.html_closed
            or parser.in_list or parser.item is not None or parser.list_count != 1):
        raise ValueError("Official network article identity/section/completeness changed")
    rules = []
    for entry in parser.entries:
        wildcard = entry.startswith("*.")
        host = entry[2:] if wildcard else entry
        if not valid_host(host):
            raise ValueError(f"Invalid official allowlist hostname: {entry}")
        rules.append(f"{'DOMAIN-SUFFIX' if wildcard else 'DOMAIN'},{host}")
    if not 20 <= len(rules) <= 200 or len(set(rules)) != len(rules) or not ANCHORS <= set(rules):
        raise ValueError("Official allowlist count/anchors changed or list is incomplete")
    return sorted(rules)


def rules_hash(rules: list[str]) -> str:
    return hashlib.sha256(("\n".join(sorted(rules)) + "\n").encode()).hexdigest()


def validate_official_change(rules: list[str], old_state: dict | None,
                            previous_rules: list[str] | None = None) -> None:
    previous = (old_state or {}).get("sources", {}).get("official_network")
    if previous is None:  # migration: still subject to anchors and absolute limits
        return
    count = previous.get("rule_count")
    if (type(count) is not int or count <= 0
            or not count * 0.75 <= len(rules) <= count * 1.50):
        raise ValueError("Official allowlist count changed unexpectedly; review required")
    if (not isinstance(previous_rules, list) or len(previous_rules) != count
            or rules_hash(previous_rules) != previous.get("sha256")):
        raise ValueError("Official allowlist evidence baseline is missing or inconsistent")
    if len(set(rules) ^ set(previous_rules)) > max(5, len(previous_rules) // 4):
        raise ValueError("Official allowlist churn is too large; review required")


def canonical(rule: str) -> str | None:
    parts = [part.strip() for part in rule.split(",")]
    if parts[0] in {"DOMAIN", "DOMAIN-SUFFIX"}:
        if len(parts) != 2 or not valid_host(parts[1]):
            return None
        return ",".join(parts)
    if parts[0] in {"IP-CIDR", "IP-CIDR6"}:
        if len(parts) not in {2, 3} or (len(parts) == 3 and parts[2] != "no-resolve"):
            return None
        try:
            net = ipaddress.ip_network(parts[1], strict=True)
        except ValueError:
            return None
        if (parts[0] == "IP-CIDR6") != (net.version == 6):
            return None
        return f"{parts[0]},{net}"
    return None


def admissible_proof(official: list[str], candidate: str) -> list[str]:
    """An overbroad official entry cannot indirectly bless arbitrary children."""
    proof = []
    for item in official:
        kind, host = item.split(",", 1)
        if kind == "DOMAIN-SUFFIX" and (
                host in SHARED_PLATFORM_ROOTS
                or (len(host.split(".")) == 2 and host not in REVIEWED_WILDCARD_ROOTS)):
            continue
        if covers(item, candidate):
            proof.append(item)
    return proof


def review_one(rule: str, official: list[str], voice: list[str],
               legacy: list[str], manual: list[str]) -> dict:
    def verdict(status, reason, evidence=(), permitted=False):
        return {"status": status, "reason": reason,
                "evidence_rules": sorted(evidence), "permit_auto": permitted}

    kind = rule.split(",", 1)[0].upper()
    if kind in {"DOMAIN-KEYWORD", "IP-ASN", "DST-PORT", "SRC-PORT", "PROTOCOL",
                "AND", "OR", "NOT", "FINAL", "MATCH", "GEOIP", "SRC-IP"} or rule.startswith("keyword:"):
        return verdict("rejected", "broad_match_forbidden")
    # Only the already-reviewed literal wildcard can pass; do not execute regex.
    if rule in legacy:
        proof = admissible_proof(official, rule)
        return verdict("covered", "official_network" if proof else "reviewed_policy",
                       proof or [rule], True)
    normalized = canonical(rule)
    if normalized is None:
        return verdict("pending", "unsupported_or_invalid_syntax")
    kind, host = normalized.split(",", 1)
    if kind.startswith("IP-"):
        network = ipaddress.ip_network(host)
        if not network.is_global or network.prefixlen < {4: 24, 6: 48}[network.version]:
            return verdict("rejected", "unsafe_ip_scope")
        networks = [(item, ipaddress.ip_network(item.split(",")[1])) for item in voice]
        same = [(item, net) for item, net in networks if net.version == network.version]
        union = list(ipaddress.collapse_addresses(net for _, net in same))
        if any(network.subnet_of(net) for net in union):
            return verdict("covered", "official_voice_destination",
                           [item for item, net in same if network.overlaps(net)])
        if any(network.overlaps(net) for _, net in same):
            return verdict("rejected", "ip_exceeds_official_destination_scope")
        return verdict("pending", "no_official_destination_ip_evidence")
    if kind == "DOMAIN-SUFFIX" and host in SHARED_PLATFORM_ROOTS:
        return verdict("rejected", "shared_platform_scope_forbidden")
    if (kind == "DOMAIN-SUFFIX" and len(host.split(".")) == 2
            and host not in REVIEWED_WILDCARD_ROOTS and normalized in official):
        return verdict("pending", "new_whole_domain_needs_scope_review", [normalized])
    proof = admissible_proof(official, normalized)
    if proof:
        already = [item for item in manual + legacy if covers(item, normalized)]
        return verdict("covered" if already else "approved", "official_network", proof, True)
    already = [item for item in manual + legacy if covers(item, normalized)]
    if already:
        # Manual coverage is not new evidence and does not grant automatic trust.
        return verdict("covered", "existing_route_coverage", already)
    narrower = [item for item in official + manual + legacy
                if covers(normalized, item) and normalized != item]
    if narrower:
        return verdict("rejected", "candidate_exceeds_evidence_scope", narrower)
    return verdict("pending", "no_current_official_evidence")


def review_candidates(source_lists: dict[str, list[str]], unparsed: dict[str, list[str]],
                      official: list[str], voice: list[str], legacy: list[str],
                      manual: list[str], previous: dict | None = None,
                      initial_exclusions: list[str] = (), now: str | None = None,
                      official_available: bool = True) -> tuple[list[str], dict]:
    if not official_available and official:
        raise ValueError("Unavailable evidence must not authorize new candidates")
    now = now or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    origins: dict[str, set[str]] = {}
    for source, rules in list(source_lists.items()) + list(unparsed.items()) + [("official_network", official)]:
        for rule in rules:
            origins.setdefault(rule, set()).add(source)
    old_rows = (previous or {}).get("candidates", [])
    if not isinstance(old_rows, list) or len(old_rows) > 10000:
        raise ValueError("Invalid or oversized review history")
    old = {row["rule"]: row for row in old_rows}
    candidates = sorted(set(origins) | set(old) | set(initial_exclusions))
    if len(candidates) > 10000:
        raise ValueError("Candidate review limit exceeded")
    rows, allowed = [], list(legacy)
    changes = []
    for rule in candidates:
        decision = review_one(rule, official, voice, legacy, manual)
        if not official_available and decision["reason"] == "no_current_official_evidence":
            decision["reason"] = "official_evidence_unavailable"
        active = sorted(origins.get(rule, ()))
        # Removed upstream entries do not survive because an old report approved
        # them. Old pending/rejected entries remain visible and are re-evaluated.
        if official_available and not active and decision["status"] in {"approved", "covered"}:
            decision = {"status": "withdrawn", "reason": "no_current_source",
                        "evidence_rules": [], "permit_auto": False}
        prior = old.get(rule, {})
        changed = any(prior.get(key) != value for key, value in decision.items())
        row = {"rule": rule, **decision, "active_sources": active,
               "sources": sorted(set(active) | set(prior.get("sources", []))),
               "first_seen": prior.get("first_seen", now),
               "decision_changed_at": now if changed else prior["decision_changed_at"]}
        rows.append(row)
        if changed:
            changes.append({"rule": rule, "before": prior.get("status"), **decision})
        if decision["permit_auto"] and active and normalized_domain(rule):
            allowed.append(rule)
    return list(dict.fromkeys(allowed)), {
        "schema_version": 1, "candidates": rows,
        "counts": {status: sum(row["status"] == status for row in rows) for status in STATUSES},
        "changes": changes,
    }


def normalized_domain(rule: str) -> bool:
    return canonical(rule) is not None and rule.startswith(("DOMAIN,", "DOMAIN-SUFFIX,"))


def inventory(ips: list[str], auto: list[str], manual: list[str], official: list[str]) -> list[dict]:
    """Audit EVERY emitted rule, with no invented evidence for legacy exceptions."""
    rows = []
    for layer, rules in (("official_voice", ips), ("automatic_domains", auto), ("manual_fallback", manual)):
        for rule in rules:
            proof = admissible_proof(official, rule)
            if layer == "official_voice":
                basis, evidence = "official_voice_destination", [rule]
            elif proof:
                basis, evidence = "official_network", proof
            elif rule in {"DOMAIN-SUFFIX,host.livekit.cloud", "DOMAIN-SUFFIX,turn.livekit.cloud"}:
                basis, evidence = "user_approved_shared_exception", []
            else:
                basis, evidence = "retained_reviewed_policy_not_current_network_evidence", []
            rows.append({"layer": layer, "rule": rule, "basis": basis,
                         "evidence_rules": evidence})
    return rows


def validate_emitted(ips: list[str], auto: list[str], manual: list[str],
                     official: list[str], legacy: list[str]) -> None:
    # Defense in depth: audit the final automatic layer, not just candidate votes.
    for rule in auto:
        decision = review_one(rule, official, ips, legacy, manual)
        if not decision["permit_auto"]:
            raise ValueError(f"Unauthorised automatic rule in final output: {rule}")
