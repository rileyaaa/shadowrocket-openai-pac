#!/usr/bin/env python3
"""Telegram summary after the successful build and commit step of GitHub Actions."""
from __future__ import annotations
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo
import review_queue

NAMES = {
    "johnshall": "Johnshall", "voice": "OpenAI Voice", "metacubex": "MetaCubeX",
    "v2fly": "v2fly", "acl4ssr": "ACL4SSR", "blackmatrix7": "blackmatrix7",
    "apple_news": "Apple News 内嵌规则",
}
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
    if report.get("review_decisions_changed"):
        # The audit record can change while the actual Shadowrocket route stays identical.
        # A malformed record is still a file change, not a successful approval.
        result = (result + "；人工审核记录文件已变更" if report["config_changed"] or sources
                  else "人工审核记录文件已变更，分流配置无变化")
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
        lines.append(f"未转换原始规则留档：{report['statistics']['unparsed_upstream_rules']:,}")
    if report.get("settings_changed"):
        lines.append("节点名称：已更新")
    added, removed = report["auto_added"], report["auto_removed"]
    lines.extend(["", f"自动规则新增 {len(added)} / 删除 {len(removed)}"])
    if added:
        lines.append("新增：" + "；".join(added[:5]) + ("…" if len(added) > 5 else ""))
    if removed:
        lines.append("删除：" + "；".join(removed[:5]) + ("…" if len(removed) > 5 else ""))
    # Newly rejected domain/rule candidates are REVIEW ONLY.
    candidates = report.get("new_excluded_candidates", [])
    reviewed_total = report.get("excluded_review_total", 0)
    lines.append("")
    if report.get("excluded_review_baseline_created", False) and not candidates:
        lines.append(f"🔎 待审核基线已建立：现有 {reviewed_total} 条旧排除项，不计为新增")
    elif not candidates:
        lines.append(f"🔎 上游新增待审核规则：无（当前排除项 {reviewed_total} 条）")
    else:
        lines.append(f"🔎 上游新增待审核规则：{len(candidates)} 条（含未送达重试，未自动分流）")
        for item in candidates[:4]:
            where = ", ".join(NAMES.get(s, s) for s in item["sources"])
            lines.append(f"· {item['rule'][:160]} [{where or '来源待查'}]")
        if len(candidates) > 4:
            lines.append(f"其余 {len(candidates)-4} 条请查看本次 Actions 摘要")
    due = report.get("review_due_candidates", [])
    if due:
        lines.extend(["", f"⏰ 人工不通过记录到期复审：{len(due)} 条（到期不自动放行）"])
        for item in due[:4]:
            lines.append(f"· {item['rule'][:160]}（上次 {item['reviewed_at']}；到期 {item['review_due_on']}）")
        if len(due) > 4:
            lines.append(f"其余 {len(due)-4} 条请查看本次 Actions 摘要")
        lines.append("仍不通过：更新 reviewed_at 或用 Run workflow 记录；通过需另改允许规则。")
    counts = report.get("manual_review_counts")
    if counts is not None:
        lines.append(f"审核状态：待审 {counts['pending']} / 暂不提醒 {counts['cooling']} / 到期 {counts['due']}")
        lines.append(f"免重复审核：已覆盖 {counts['covered']} / 社区 IP、ASN 留档 {counts['official_ip_only']}")
        if counts["due"]:
            lines.append(f"未处理到期项每 {report['review_reminder_interval_days']} 天提醒一次。")
    for warning in report.get("review_warnings", []):
        lines.append("⚠️ " + warning)
    message = "\n".join(lines)
    if len(message) > 3400:
        message = message[:3300] + "\n…完整清单请查看 Actions 摘要。"
    if run_url:
        message += f"\n\nActions：{run_url}"
    return message


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
    p.add_argument("--review-state-file", type=Path, help="仅在 Telegram 成功后更新送达状态")
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
            candidates = report.get("new_excluded_candidates", [])
            if candidates:
                summary.write("\n### 完整新增待审核规则清单（未自动分流）\n\n")
                for item in candidates:
                    where = ", ".join(NAMES.get(s, s) for s in item["sources"])
                    summary.write(f"- {item['rule']} — {where or '来源待查'}\n")
            due = report.get("review_due_candidates", [])
            if due:
                summary.write("\n### 到期复审完整清单（未自动放行）\n\n")
                for item in due:
                    where = ", ".join(NAMES.get(s, s) for s in item["sources"])
                    summary.write(f"- {item['rule']} — {where}\n"
                                  f"  上次审核：{item['reviewed_at']}；到期：{item['review_due_on']}；"
                                  f"此前原因：{item['reason']}\n")
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
    if args.review_state_file:
        try:
            review_queue.acknowledge(report, args.review_state_file)
        except (OSError, ValueError, TypeError):
            print("::warning::Telegram delivered, but receipt could not be saved; next run may repeat the reminder.")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
