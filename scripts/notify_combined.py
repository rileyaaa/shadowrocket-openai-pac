#!/usr/bin/env python3
"""One Telegram update for both builders, preserving original review receipts.

Use the unchanged notify_telegram.send retry implementation and the unchanged
review_queue.acknowledge only after Telegram confirmed acceptance.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import notify_telegram as original
import review_queue


def read_json(path: str | None) -> dict | None:
    if not path or not Path(path).is_file():
        return None
    try:
        doc = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'::warning::Unreadable report: {type(exc).__name__}')
        return None
    return doc if isinstance(doc, dict) else None


def emit_message(status: dict, shadow_ai: dict | None, v2: dict | None,
                 *, when: str, event: str, run_url: str,
                 official_docs: dict | None = None) -> str:
    builds = {key: status.get(key, {}).get('exit_code') == 0
              for key in ('shadowrocket_ai', 'v2rayn')}
    published = status.get('publish', {}).get('success', False)
    complete = all(builds.values()) and published
    partial = any(builds.values())
    overall = '成功' if complete else '部分成功' if partial else '失败'
    lines = [f'📡 每日代理规则更新报告', f'🕚 时间：{when}（台北时间）',
             f'🔄 触发：{original.EVENTS.get(event, event)}',
             f'📦 总体状态：{overall}',
             f'📤 GitHub 发布：{status.get("publish", {}).get("state", "未执行")}', '']
    sections = [('shadowrocket_ai', '🚀 Shadowrocket 小火箭（OpenAI + Gemini + Claude）', shadow_ai),
                ('v2rayn', '💻 v2rayN（OpenAI + Gemini + Claude）', v2)]
    for key, title, report in sections:
        build = status.get(key, {})
        success = build.get('exit_code') == 0 and report is not None
        lines += ['━━━━━━━━━━━━━━', title,
                  f'构建：{"✅ 成功" if success else "❌ 失败 / 报告缺失"}']
        if not success:
            lines += [f'原因：{build.get("error", "构建报告不存在，无法确认")[-350:]}',
                      '配置：保留上一次已发布版本']
            continue
        if not published:
            lines += ['发布：❌ 未成功推送 GitHub（仅本地构建成功）']
        else:
            changed_files = status.get('publish', {}).get('changed_files', [])
            output = {'shadowrocket_ai': 'Shadowrocket_Johnshall_AI.conf',
                      'v2rayn': 'v2rayN_Johnshall_AI.json'}[key]
            lines += [f'发布：{"✅ 已更新" if output in changed_files else "✅ 已检查，内容无变化"}']
        lines += [f'配置变化：{"有更新" if report.get("config_changed") else "无变化"}']
        stats = report.get('statistics', {})
        if key == 'shadowrocket_ai':
            for prop, label in [('johnshall_lines', 'Johnshall 原规则'),
                                ('voice_prefixes', 'OpenAI Voice IP'),
                                ('gemini_domains', 'Gemini 审核域名'),
                                ('claude_domains', 'Claude 审核域名'),
                                ('retained_ad_rules', '广告拦截'),
                                ('conf_bytes', '订阅字节数')]:
                if type(stats.get(prop)) is int:
                    lines.append(f'{label}：{stats[prop]}')
            review_counts = report.get('ai_review_counts', {})
            lines.append('AI 审核：待审 {pending} / 暂缓 {cooling} / 到期 {due}'.format(
                pending=review_counts.get('pending', '?'), cooling=review_counts.get('cooling', '?'),
                due=review_counts.get('due', '?')))
        else:
            for prop, label in [('routing_objects', '路由对象'), ('domain_rules', '域名规则'),
                                ('ip_rules', 'IP 规则'), ('process_rules', '进程规则'),
                                ('proxy_rules', '代理规则'), ('direct_rules', '直连规则'),
                                ('block_rules', '拦截规则'), ('json_bytes', 'JSON 字节数'),
                                ('bitbrowser_domains', 'BitBrowser 域名'),
                                ('gemini_domains', 'Gemini 审核域名'),
                                ('claude_domains', 'Claude 审核域名')]:
                if type(stats.get(prop)) is int:
                    lines.append(f'{label}：{stats[prop]}')
            if stats.get('process_rules', 0) == 0:
                lines.append('⚠️ 未配置经确认的进程路径')
    lines += ['', '━━━━━━━━━━━━━━', '🔔 异常与人工审核']
    if shadow_ai and status.get('shadowrocket_ai', {}).get('exit_code') == 0:
        lines += [f'OpenAI 新增待审核：{len(shadow_ai.get("new_excluded_candidates", []))}；'
                  f'到期复审：{len(shadow_ai.get("review_due_candidates", []))}']
        counts = shadow_ai.get('manual_review_counts', {})
        if isinstance(counts, dict):
            lines.append(f'OpenAI 审核：待审 {counts.get("pending", "?")} / '
                         f'到期 {counts.get("due", "?")}')
        for warning in shadow_ai.get('review_warnings', [])[:2]:
            lines.append('⚠️ ' + str(warning)[:140])
    else:
        lines.append('⚠️ Shadowrocket AI 审核报告缺失；不确认提醒送达状态')
    if not published:
        lines.append('⚠️ ' + str(status.get('publish', {}).get('error', 'GitHub 未确认发布'))[:250])
    if shadow_ai and shadow_ai.get('ai_review_candidates'):
        counts = shadow_ai.get('ai_review_counts', {})
        lines.append('⚠️ Gemini/Claude 未批准候选：{}，其中到期复审 {}（不会自动放行）'.format(
            len(shadow_ai['ai_review_candidates']), counts.get('due', 0)))
    docs_status = status.get('official_docs', {})
    if docs_status.get('exit_code', 0) != 0:
        lines.append('⚠️ 本周官方网络文档检查不可用；不影响规则更新：' +
                     str(docs_status.get('error', '未知原因'))[:140])
    elif official_docs and official_docs.get('checked'):
        lines.append('🗓 官方网络文档：' +
                     ('发现变化，待人工核实' if official_docs.get('changed')
                      else '每周检查完成，域名无变化'))
    if v2 and v2.get('warnings'):
        lines.append('⚠️ BitBrowser 进程与 DNS/WebRTC 需 Windows TUN 实测')
    if run_url:
        lines += ['', '🔗 GitHub Actions：' + run_url]
    message = '\n'.join(lines)
    if len(message) > 3900:
        message = message[:3550] + '\n…详见 GitHub Actions 执行摘要。'
        if run_url:
            message += '\n' + run_url
    return message


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--status-file', required=True, type=Path)
    p.add_argument('--review-state-file', type=Path)
    args = p.parse_args()
    status = read_json(str(args.status_file)) or {
        'shadowrocket_ai': {'exit_code': -1, 'error': 'Build status file missing'},
        'v2rayn': {'exit_code': -1, 'error': 'Build status file missing'},
        'publish': {'success': False, 'state': 'not-run'}}
    v2 = read_json(status.get('reports', {}).get('v2rayn'))
    shadow_ai = read_json(status.get('reports', {}).get('shadowrocket_ai'))
    official_docs = read_json(status.get('reports', {}).get('official_docs'))
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    run_url = (f'{os.environ.get("GITHUB_SERVER_URL", "https://github.com")}/'
               f'{repo}/actions/runs/{run_id}') if repo and run_id else ''
    now = datetime.now(ZoneInfo('Asia/Taipei')).strftime('%Y-%m-%d %H:%M:%S')
    message = emit_message(status, shadow_ai, v2, when=now,
                           event=os.environ.get('GITHUB_EVENT_NAME', ''), run_url=run_url,
                           official_docs=official_docs)
    print(message)
    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_path:
        with open(summary_path, 'a', encoding='utf-8') as f:
            f.write('## Shadowrocket + v2rayN 真实构建及发布报告\n\n~~~text\n'
                    + message + '\n~~~\n')
            if shadow_ai:
                for key in ('new_excluded_candidates', 'review_due_candidates'):
                    if shadow_ai.get(key):
                        f.write(f'\n### OpenAI {key}\n\n')
                        for item in shadow_ai[key]:
                            f.write('- ' + str(item.get('rule', '?')) + '\n')
            if official_docs and official_docs.get('changes'):
                f.write('\n### 每周官方文件变化（未自动批准）\n\n')
                for change in official_docs['changes']:
                    f.write(f'- {change["service"]}: +{len(change["added"])} / -{len(change["removed"])} 主机\n')
            if shadow_ai:
                f.write('\n### Gemini / Claude 未批准新候选\n\n')
                for item in shadow_ai.get('ai_review_candidates', []):
                    f.write(f'- {item["service"]}: {item["rule"]} ({", ".join(item["sources"])})\n')
            if v2:
                for warning in v2.get('warnings', []):
                    f.write('\n- ⚠️ ' + str(warning) + '\n')
    token, chat_id = (os.environ.get('TELEGRAM_BOT_TOKEN', '').strip(),
                      os.environ.get('TELEGRAM_CHAT_ID', '').strip())
    if not token or not chat_id:
        print('::error::Missing Telegram secrets; report not sent and receipt not acknowledged')
        return 1
    try:
        original.send(token, chat_id, message)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f'::error::Telegram delivery failed: {type(exc).__name__}; receipts unchanged')
        return 1
    print('Unified Telegram report sent.')
    if (args.review_state_file and shadow_ai
            and status.get('shadowrocket_ai', {}).get('exit_code') == 0
            and status.get('publish', {}).get('success')):
        try:
            review_queue.acknowledge(shadow_ai, args.review_state_file)
        except (OSError, ValueError, TypeError) as exc:
            print(f'::error::Telegram delivered, but review acknowledgement failed: {type(exc).__name__}')
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
