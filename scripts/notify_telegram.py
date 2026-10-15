#!/usr/bin/env python3
"""Telegram summary after the successful build and commit step of GitHub Actions."""
from __future__ import annotations
import argparse
from datetime import datetime
import html
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

from review_rules import REASONS

NAMES = {
    "johnshall": "Johnshall", "voice": "OpenAI Voice", "metacubex": "MetaCubeX",
    "v2fly": "v2fly", "acl4ssr": "ACL4SSR", "blackmatrix7": "blackmatrix7",
    "apple_news": "Apple News 内嵌规则",
    "official_network": "OpenAI 官方网络清单",
}
DECISIONS = {"approved": "通过", "covered": "已覆盖", "pending": "待证据",
             "rejected": "拒绝", "withdrawn": "已撤回"}
EVENTS = {"push": "代码提交", "schedule": "定时运行", "workflow_dispatch": "手动执行"}
COUNT_FIELDS = (
    ("automatic_openai_domains", "OpenAI 自动域名"),
    ("voice_prefixes", "Voice IP 段"),
    ("manual_openai_rules", "手工兜底规则"),
    ("johnshall_lines", "Johnshall 原规则行"),
    ("mapped_proxy_to_johnshall_node", "普通代理映射规则"),
    ("retained_ad_rules", "广告拦截规则"),
)


def format_report(report: dict, event: str, repo: str, run_url: str,
                  when: str | None = None) -> str:
    if when is None:
        when = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d %H:%M:%S")
    sources = report["changed_sources"]
    result = ("配置已更新" if report["config_changed"] else
              "上游发生变化，最终配置无变化" if sources else "检查成功，无变化")
    lines = [
        "✅ Shadowrocket GitHub Actions 成功",
        f"时间：{when} (UTC+8)", f"触发：{EVENTS.get(event, event)}",
        f"状态：{result}",
        "变化来源：" + (", ".join(NAMES.get(s, s) for s in sources) if sources else "无"),
        "", "📊 规则摘要",
    ]
    for key, label in COUNT_FIELDS:
        count = report["statistics"][key]
        diff = report.get("stat_deltas", {}).get(key)
        lines.append(f"{label}：{count:,}" + (f" ({diff:+d})" if type(diff) is int else ""))
    if "embedded_ruleset_rules" in report["statistics"]:
        lines.append(f"已校验内嵌规则：{report['statistics']['embedded_ruleset_rules']:,}")
    if "unparsed_upstream_rules" in report["statistics"]:
        label = "特殊格式已逐条审核" if "automatic_review" in report else "未支持格式待审核"
        lines.append(f"{label}：{report['statistics']['unparsed_upstream_rules']:,}")
    if report.get("settings_changed"):
        lines.append("节点名称：已更新")
    added, removed = report["auto_added"], report["auto_removed"]
    lines.extend(["", f"自动规则新增 {len(added)} / 删除 {len(removed)}"])
    if added:
        lines.append("新增：" + "；".join(added[:5]) + ("…" if len(added) > 5 else ""))
    if removed:
        lines.append("删除：" + "；".join(removed[:5]) + ("…" if len(removed) > 5 else ""))
    if "automatic_review" in report:
        review = report["automatic_review"]
        lines.extend(["", "🔎 证据审核（每次重新判断）",
                      " / ".join(f"{DECISIONS[key]} {review['counts'].get(key, 0)}"
                                 for key in DECISIONS)])
        lines.append(f"实际发布的自动层变化：+{len(added)} / -{len(removed)}；已覆盖不代表新增分流")
        changes = review["changes"]
        noteworthy = [item for item in changes if item["status"] != "covered"]
        noteworthy.sort(key=lambda item: (not item["rule"].startswith("IP-"), item["status"] != "approved", item["rule"]))
        if review.get("baseline_created"):
            lines.append("首次全量审查，已有候选不冒充本次新增")
        elif not changes:
            lines.append("本次审核结论无变化，旧待审项已复查")
        for item in noteworthy[:8]:
            lines.append(f"· {DECISIONS[item['status']]} {item['rule']}：{REASONS[item['reason']]}")
        if len(noteworthy) > 8:
            lines.append(f"其余 {len(noteworthy)-8} 条结论见 Actions 摘要")
        if repo:
            lines.append(f"逐条审计：https://github.com/{repo}/blob/main/data/openai-review.json")
        if run_url:
            lines.extend(["", f"Actions：{run_url}"])
        return "\n".join(lines)[:3900]
    # Compatibility for reports produced before automatic review was enabled.
    candidates = report.get("new_excluded_candidates", [])
    reviewed_total = report.get("excluded_review_total", 0)
    lines.append("")
    if report.get("excluded_review_baseline_created", False):
        lines.append(f"🔎 待审核基线已建立：现有 {reviewed_total} 条旧排除项，不计为新增")
    elif not candidates:
        lines.append(f"🔎 上游新增待审核规则：无（当前排除项 {reviewed_total} 条）")
    else:
        lines.append(f"🔎 上游新增待审核规则：{len(candidates)} 条（未自动分流）")
        for item in candidates[:8]:
            where = ", ".join(NAMES.get(s, s) for s in item["sources"])
            lines.append(f"· {item['rule']} [{where or '来源待查'}]")
        if len(candidates) > 8:
            lines.append(f"其余 {len(candidates)-8} 条请查看本次 Actions 摘要")
    if run_url:
        lines.extend(["", f"Actions：{run_url}"])
    return "\n".join(lines)[:3900]


def review_summary(report: dict) -> str:
    review = report.get("automatic_review")
    if review is None:
        return ""
    def cell(value):
        return html.escape(str(value)).replace("|", "&#124;").replace("`", "&#96;").replace("\n", " ")
    rows = ["\n### 全量自动审核结果\n", f"核验时间：{review['checked_at']}\n",
            "审批结论与实际路由覆盖分别记录。自动层和手工层保持独立。\n",
            "| 规则 | 结论 | 理由 | 自动覆盖 / 手工覆盖 | 当前来源 |",
            "|---|---|---|---|---|"]
    for item in review["candidates"]:
        rows.append("| " + " | ".join(cell(value) for value in (
            item["rule"], DECISIONS[item["status"]], REASONS[item["reason"]],
            f"{'是' if item['automatic_coverage'] else '否'} / {'是' if item['manual_coverage'] else '否'}",
            ", ".join(item["active_sources"]) or "来源已撤回")) + " |")
    return "\n".join(rows) + "\n"


def send(bot_token: str, chat_id: str, text: str) -> None:
    data = json.dumps({"chat_id": chat_id, "text": text,
                       "disable_web_page_preview": True}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    # The bot token is part of the URL; never log request or exception URLs.
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                if not json.loads(response.read().decode("utf-8")).get("ok"):
                    raise RuntimeError("Telegram API returned no success")
                return
        except urllib.error.HTTPError as exc:
            if attempt == 2 or exc.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(f"Telegram HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError("Telegram connection failed after retries") from None
        time.sleep(2 ** attempt)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--report-file", type=Path, required=True)
    args = p.parse_args()
    report = json.loads(args.report_file.read_text(encoding="utf-8"))
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    run_url = f"{server}/{repo}/actions/runs/{run_id}" if repo and run_id else ""
    message = format_report(report, os.environ.get("GITHUB_EVENT_NAME", ""), repo, run_url)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## Shadowrocket 同步成功摘要\n\n~~~text\n" + message + "\n~~~\n")
            summary.write(review_summary(report))
            candidates = report.get("new_excluded_candidates", []) if "automatic_review" not in report else []
            if candidates:
                summary.write("\n### 完整新增待审核规则清单（未自动分流）\n\n")
                for item in candidates:
                    where = ", ".join(NAMES.get(s, s) for s in item["sources"])
                    summary.write(f"- {item['rule']} — {where or '来源待查'}\n")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("::warning::Missing Telegram Actions Secret(s): TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID; report not sent.")
        return 1
    try:
        send(token, chat_id, message)
    except (RuntimeError, ValueError):
        print("::warning::Telegram message not sent; check Secret, chat ID, and /start.")
        return 1
    print("Telegram report sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
