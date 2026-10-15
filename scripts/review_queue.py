#!/usr/bin/env python3
"""Manual rejection expiry and durable Telegram reminders; never grants routes."""
from __future__ import annotations

import argparse
import calendar
from datetime import date, datetime, timedelta
import hashlib
import html
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-WILDCARD", "DOMAIN-KEYWORD"}
IP_TYPES = {"IP-CIDR", "IP-CIDR6", "IP6-CIDR", "IP-ASN"}
STATUS_NAMES = {
    "covered": "已由现有 OpenAI 规则覆盖",
    "official_ip_only": "社区 IP/ASN，仅留档；IP 只取官方 Voice",
    "pending": "待人工审核",
    "cooling": "人工不通过，暂不提醒",
    "due": "已到复审日期，仍未放行",
}


def today() -> date:
    return datetime.now(ZoneInfo("Asia/Taipei")).date()


def parse_date(value) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("日期必须为 YYYY-MM-DD")
    return date.fromisoformat(value)


def add_months(value: date, months: int) -> date:
    year, month = divmod(value.year * 12 + value.month - 1 + months, 12)
    month += 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def default_policy() -> dict:
    return {"version": 1, "default_review_months": 6,
            "reminder_interval_days": 7, "rejected_rules": []}


def empty_delivery() -> dict:
    return {"version": 1, "pending_new": [], "sent": {}}


def bounded_int(value, low: int, high: int, field: str) -> None:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{field} 必须为 {low}～{high} 的整数")


def nonempty_text(value, field: str) -> None:
    if (not isinstance(value, str) or not value.strip() or value != value.strip()
            or len(value) > 2000 or any(ord(c) < 32 for c in value)):
        raise ValueError(f"{field} 必须为非空单行文本（最多 2000 字符，无首尾空格）")


def validate_policy(data: dict, on: date) -> dict:
    expected = {"version", "default_review_months", "reminder_interval_days", "rejected_rules"}
    if not isinstance(data, dict) or set(data) != expected or type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("审核配置字段或 version 不正确")
    bounded_int(data["default_review_months"], 1, 120, "default_review_months")
    bounded_int(data["reminder_interval_days"], 1, 365, "reminder_interval_days")
    if not isinstance(data["rejected_rules"], list):
        raise ValueError("rejected_rules 必须为列表")
    seen = set()
    for item in data["rejected_rules"]:
        required = {"rule", "reason", "reviewed_at"}
        if not isinstance(item, dict) or not required <= set(item) or set(item) - required - {"review_after_months"}:
            raise ValueError("每条拒绝记录需要 rule、reason、reviewed_at，可选 review_after_months")
        nonempty_text(item["rule"], "rule")
        nonempty_text(item["reason"], "reason")
        if item["rule"] in seen:
            raise ValueError("存在重复 rule")
        seen.add(item["rule"])
        reviewed = parse_date(item["reviewed_at"])
        if reviewed > on:
            raise ValueError("reviewed_at 不得晚于台北当前日期")
        months = item.get("review_after_months", data["default_review_months"])
        bounded_int(months, 1, 120, "review_after_months")
        add_months(reviewed, months)  # Validate overflow before using this policy.
    return data


def load_policy(path: Path, on: date) -> tuple[dict, list[str]]:
    try:
        return validate_policy(json.loads(path.read_text(encoding="utf-8")), on), []
    except (OSError, ValueError, TypeError) as exc:
        return default_policy(), [f"人工审核配置无效，暂停拒绝记录的免提醒功能；正常分流同步继续。原因：{type(exc).__name__}"]


def load_delivery(path: Path, on: date) -> dict:
    if not path.exists():
        return empty_delivery()
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or set(data) != {"version", "pending_new", "sent"}
            or type(data["version"]) is not int or data["version"] != 1
            or not isinstance(data["pending_new"], list)
            or any(not isinstance(rule, str) for rule in data["pending_new"])
            or not isinstance(data["sent"], dict)):
        raise ValueError("通知状态格式不正确")
    for rule, item in data["sent"].items():
        if (not isinstance(rule, str) or not isinstance(item, dict)
                or set(item) != {"cycle", "notified_at"}
                or not isinstance(item["cycle"], str)
                or not re.fullmatch(r"[a-f0-9]{64}", item["cycle"])
                or parse_date(item["notified_at"]) > on):
            raise ValueError("通知状态中的日期或审核周期不正确")
    return data


def evaluate(excluded: dict[str, list[str]], previous: list[str] | None,
             active_domains: list[str], covers, root: Path, on: date | None = None) -> tuple[dict, dict]:
    """Classify a snapshot, persisting new alerts until Telegram acknowledges them."""
    on = on or today()
    policy, warnings = load_policy(root / "config/review-decisions.json", on)
    try:
        delivery = load_delivery(root / "data/review-notifications.json", on)
    except (OSError, ValueError, TypeError):
        delivery = empty_delivery()
        warnings.append("通知状态无效，当前未审核项将重新提醒，避免漏报；正常分流同步继续。")
    decisions = {item["rule"]: item for item in policy["rejected_rules"]}
    new_rules = set(excluded) - set(previous) if previous is not None else set()
    queued = set(delivery["pending_new"]) | new_rules
    if warnings:
        queued.update(excluded)  # A broken optional ledger must never silently hide alerts.
    entries, new_candidates, due_candidates = [], [], []
    counts = dict.fromkeys(STATUS_NAMES, 0)
    for rule, sources in sorted(excluded.items()):
        item = {"rule": rule, "sources": sources}
        kind = rule.partition(",")[0].strip().upper()
        covering = next((active for active in active_domains
                         if kind in DOMAIN_TYPES and rule.count(",") == 1 and covers(active, rule)), None)
        decision = decisions.get(rule)  # Exact rule only; never inherit parent rejection.
        if covering:
            item.update(status="covered", covered_by=covering)
        elif kind in IP_TYPES:
            item["status"] = "official_ip_only"
        elif decision:
            months = decision.get("review_after_months", policy["default_review_months"])
            due = add_months(parse_date(decision["reviewed_at"]), months)
            item.update(status="due" if on >= due else "cooling", reason=decision["reason"],
                        reviewed_at=decision["reviewed_at"], review_due_on=due.isoformat(), review_months=months)
            if on >= due:
                cycle = hashlib.sha256(json.dumps(
                    [rule, decision["reviewed_at"], due.isoformat(), decision["reason"]],
                    ensure_ascii=False).encode()).hexdigest()
                last = delivery["sent"].get(rule, {})
                if (last.get("cycle") != cycle or on >= parse_date(last["notified_at"])
                        + timedelta(days=policy["reminder_interval_days"])):
                    due_candidates.append({**item, "cycle": cycle})
        else:
            item["status"] = "pending"
            if rule in queued:
                new_candidates.append({"rule": rule, "sources": sources})
        counts[item["status"]] += 1
        entries.append(item)
    # A vanished candidate stops reminders; the user's rejection record is retained.
    delivery["pending_new"] = [item["rule"] for item in new_candidates]
    delivery["sent"] = {rule: value for rule, value in delivery["sent"].items() if rule in decisions}
    return {
        "entries": entries, "counts": counts, "warnings": warnings,
        "default_review_months": policy["default_review_months"],
        "reminder_interval_days": policy["reminder_interval_days"],
        "new_candidates": new_candidates, "due_candidates": due_candidates,
    }, delivery


def write_json(path: Path, data: dict) -> None:
    content = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)


def acknowledge(report: dict, path: Path, on: date | None = None) -> None:
    """Call only after successful Telegram delivery; a failed push may safely repeat."""
    on = on or today()
    delivery = load_delivery(path, on)
    sent_new = {item["rule"] for item in report.get("new_excluded_candidates", [])}
    delivery["pending_new"] = sorted(set(delivery["pending_new"]) - sent_new)
    for item in report.get("review_due_candidates", []):
        delivery["sent"][item["rule"]] = {"cycle": item["cycle"], "notified_at": on.isoformat()}
    write_json(path, delivery)


def render_queue(review: dict) -> str:
    def cell(value):
        return html.escape(str(value)).replace("|", "&#124;").replace("`", "&#96;").replace("\n", " ")
    rows = ["# 上游人工审核清单", "", "本文件自动生成，请修改 `config/review-decisions.json` 记录人工不通过结果。",
            "到期仅提醒重新审核，不会自动放行；新增未审核项仅在首次送达前重试。",
            f"默认 {review['default_review_months']} 个日历月复审；到期后未处理，每 {review['reminder_interval_days']} 天提醒一次。",
            "已覆盖规则免重复审核；社区 IP/ASN 仅留档，Voice 目的 IP 仅采用官方 JSON。", ""]
    for warning in review["warnings"]:
        rows.append(f"> {cell(warning)}\n")
    rows.extend(["| 规则 | 来源 | 状态 | 上次审核 | 下次复审 | 原因 / 已有覆盖 |",
                 "|---|---|---|---|---|---|"])
    for item in review["entries"]:
        values = [item["rule"], ", ".join(item["sources"]), STATUS_NAMES[item["status"]],
                  item.get("reviewed_at", "—"), item.get("review_due_on", "—"),
                  item.get("reason", item.get("covered_by", "—"))]
        rows.append("| " + " | ".join(cell(value) for value in values) + " |")
    return "\n".join(rows) + "\n"


def record_rejection(path: Path, rule: str, reason: str, months: int | None = None,
                     on: date | None = None) -> None:
    on = on or today()
    data = validate_policy(json.loads(path.read_text(encoding="utf-8")), on)
    existing = next((item for item in data["rejected_rules"] if item["rule"] == rule), {})
    item = {**existing, "rule": rule, "reason": reason, "reviewed_at": on.isoformat()}
    if months is not None:
        item["review_after_months"] = months
    data["rejected_rules"] = sorted(
        [entry for entry in data["rejected_rules"] if entry["rule"] != rule] + [item],
        key=lambda entry: entry["rule"])
    validate_policy(data, on)
    write_json(path, data)


def main() -> None:
    parser = argparse.ArgumentParser(description="记录人工不通过或续期；日期自动使用 Asia/Taipei")
    parser.add_argument("--rule", required=True, help="从审核清单复制完整 rule，精确匹配")
    parser.add_argument("--reason", required=True, help="人工不通过的原因")
    parser.add_argument("--months", type=int, help="复审间隔月数；省略则保留已有覆盖值或使用全局默认")
    args = parser.parse_args()
    record_rejection(ROOT / "config/review-decisions.json", args.rule, args.reason, args.months)
    print("Manual rejection recorded; review date renewed (Asia/Taipei).")


if __name__ == "__main__":
    main()
