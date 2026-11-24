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
from release_integrity import valid_build_report


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
    publication = status.get('publish', {})
    published = publication.get('success') is True
    changed_files = publication.get('changed_files', [])
    if not isinstance(changed_files, list):
        changed_files = []
    valid = {'shadowrocket_ai': builds['shadowrocket_ai'] and valid_build_report(shadow_ai),
             'v2rayn': builds['v2rayn'] and valid_build_report(v2)}
    complete = all(valid.values()) and published
    partial = published and any(valid.values())
    overall = ('成功' if complete else '部分成功' if partial else
               '待核对' if publication.get('state') == 'pushed_unverified'
               or (published and changed_files) else '失败')
    lines = [f'📡 每日代理规则更新报告', f'🕚 时间：{when}（台北时间）',
             f'🔄 触发：{original.EVENTS.get(event, event)}',
             f'📦 总体状态：{overall}',
             f'📤 GitHub 发布：{status.get("publish", {}).get("state", "未执行")}', '']
    sections = [('shadowrocket_ai', '🚀 Shadowrocket 小火箭（OpenAI + Gemini + Claude）', shadow_ai),
                ('v2rayn', '💻 v2rayN（OpenAI + Gemini + Claude）', v2)]
    for key, title, report in sections:
        build = status.get(key, {})
        success = valid[key]
        output = {'shadowrocket_ai': 'Shadowrocket_Johnshall_AI.conf',
                  'v2rayn': 'v2rayN_Johnshall_AI.json'}[key]
        released = output in changed_files
        lines += ['━━━━━━━━━━━━━━', title,
                  f'构建：{"✅ 成功" if success else "❌ 失败 / 报告不可用"}']
        if not success:
            error = str(build.get('error') or '构建报告缺失或不可信')
            lines.append('原因：' + error[-350:])
            if released and published:
                lines.append('发布：⚠️ GitHub 已确认推送此配置，但构建报告缺失；必须核对内容')
            elif released or publication.get('state') == 'pushed_unverified':
                lines.append('发布：⚠️ 推送已返回成功，远端结果待确认')
            elif build.get('exit_code') != 0:
                lines.append('配置：本次构建失败，保留上一次已发布版本')
            else:
                lines.append('配置：本次没有确认的订阅变更，需检查构建报告')
            continue
        if publication.get('state') == 'pushed_unverified':
            lines.append('发布：⚠️ 推送已返回成功，远端版本尚待确认')
        elif not published:
            lines.append('发布：❌ 未确认 GitHub 发布（本地构建成功）')
        else:
            lines += [f'发布：{"✅ 已更新" if released else "✅ 已检查，内容无变化"}']
        lines += [f'配置变化：{"有更新" if report.get("config_changed") else "无变化"}']
        sources = report.get('changed_sources', [])
        lines.append('变化来源：' + (', '.join(original.NAMES.get(s, s) for s in sources) if sources else '无'))
        stats = report.get('statistics', {})
        if key == 'shadowrocket_ai':
            if report.get('settings_changed'):
                lines.append('节点名称：已更新')
            if report.get('review_decisions_changed'):
                lines.append('人工审核记录文件已变更' + ('，分流配置无变化' if not report.get('config_changed') else ''))
            added, removed = report.get('auto_added', []), report.get('auto_removed', [])
            lines.append(f'OpenAI 自动规则新增 {len(added)} / 删除 {len(removed)}')
            for values, label in ((added, '新增'), (removed, '删除')):
                if values:
                    lines.append(label + '：' + '；'.join(str(x)[:100] for x in values[:3]) + ('…' if len(values) > 3 else ''))
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
    if valid['shadowrocket_ai']:
        lines += [f'OpenAI 新增待审核：{len(shadow_ai.get("new_excluded_candidates", []))}；'
                  f'到期复审：{len(shadow_ai.get("review_due_candidates", []))}']
        new = shadow_ai.get('new_excluded_candidates', [])
        due = shadow_ai.get('review_due_candidates', [])
        for item in new[:4]:
            lines.append('· 新增 ' + str(item.get('rule', '?'))[:120] + ' [' +
                         ', '.join(item.get('sources', []))[:100] + ']')
        for item in due[:4]:
            lines.append('· 复审 ' + str(item.get('rule', '?'))[:120] +
                         f'（上次 {item.get("reviewed_at", "?")}；到期 {item.get("review_due_on", "?")}）')
        if len(new) > 4 or len(due) > 4:
            lines.append('其余审核项请查看本次 Actions 完整摘要。')
        counts = shadow_ai.get('manual_review_counts', {})
        if isinstance(counts, dict):
            lines.append(f'OpenAI 审核：待审 {counts.get("pending", "?")} / '
                         f'到期 {counts.get("due", "?")}')
            if counts.get('due'):
                lines.append(f'未处理到期项每 {shadow_ai.get("review_reminder_interval_days", 7)} 天提醒一次。')
        for warning in shadow_ai.get('review_warnings', [])[:2]:
            lines.append('⚠️ ' + str(warning)[:140])
    else:
        lines.append('⚠️ Shadowrocket AI 审核报告缺失；不确认提醒送达状态')
    if not published:
        lines.append('⚠️ ' + str(publication.get('error', 'GitHub 未确认发布'))[:250])
    shared = status.get('ai_review')
    if shared:
        counts = shared['review_counts']
        alerts = shared['alerts']
        lines.append(f'Gemini/Claude 合并审核：待审 {counts["pending"]} / 暂缓 {counts["cooling"]} / 到期 {counts["due"]}')
        lines.append(f'本次需提醒：{len(alerts)} 条（到期未处理每 {shared["reminder_interval_days"]} 天）')
        for item in alerts[:4]:
            suffix = (f'（上次 {item.get("reviewed_at")}；到期 {item.get("review_due_on")}）'
                      if item['status'] == 'due' else '（新增待审）')
            lines.append('· ' + item['service'] + ' ' + item['rule'][:120] + suffix)
        if len(alerts) > 4:
            lines.append('其余请查看本次 Actions 完整摘要。')
        if shared.get('stale_clients'):
            lines.append('⚠️ 审核候选沿用上次快照：' + ', '.join(shared['stale_clients']))
    elif status.get('ai_review_error'):
        lines.append('⚠️ 合并审核队列更新失败：' + str(status['ai_review_error'])[:140])
    elif not any(valid.values()):
        lines.append('⚠️ 无有效客户端报告；AI 审核快照未刷新')
    docs_status = status.get('official_docs', {})
    if docs_status.get('exit_code', 0) != 0:
        lines.append('⚠️ 本周官方网络文档检查不可用；不影响规则更新：' +
                     str(docs_status.get('error', '未知原因'))[:140])
    elif official_docs and official_docs.get('checked'):
        lines.append('🗓 官方网络文档：' +
                     ('发现变化，待人工核实' if official_docs.get('changed')
                      else '每周检查完成，域名无变化'))
    if valid['v2rayn'] and v2.get('routing_conflicts', {}).get('count'):
        conflicts = v2['routing_conflicts']
        lines.append(f'⚠️ v2rayN：{conflicts["count"]} 条代理规则与前置拦截有交集，未修改优先级。')
        for item in conflicts['examples'][:2]:
            lines.append('· ' + item['proxy_rule'][:100] + ' ← ' + item['earlier_block_rule'][:100])
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
    p.add_argument('--ai-review-state-file', type=Path)
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
                            f.write('- ' + str(item.get('rule', '?')) + ' — ' +
                                     ', '.join(item.get('sources', [])) + '\n')
                            if key == 'review_due_candidates':
                                f.write(f'  上次审核：{item.get("reviewed_at")}；到期：{item.get("review_due_on")}；'
                                        f'此前原因：{item.get("reason")}\n')
            if official_docs and official_docs.get('changes'):
                f.write('\n### 每周官方文件变化（未自动批准）\n\n')
                for change in official_docs['changes']:
                    f.write(f'- {change["service"]}: +{len(change["added"])} / -{len(change["removed"])} 主机；'
                            f'未分类 +{len(change.get("other_added", []))} / -{len(change.get("other_removed", []))}\n')
                    for key in ('added', 'removed', 'other_added', 'other_removed'):
                        for host in change.get(key, []):
                            f.write(f'  - {key}: {host}\n')
            if status.get('ai_review'):
                f.write('\n### Gemini / Claude 合并审核清单\n\n')
                for item in status['ai_review']['review_candidates']:
                    f.write(f'- {item["service"]}: {item["rule"]} ({", ".join(item["sources"])}) '
                            f'— {item["status"]}；上次 {item.get("reviewed_at")}；到期 {item.get("review_due_on")}\n')
            if v2:
                if v2.get('routing_conflicts', {}).get('count'):
                    f.write('\n### v2rayN 前置拦截冲突（仅报告，未改变路由）\n\n')
                    for item in v2['routing_conflicts']['examples']:
                        f.write(f'- {item["proxy_rule"]} ← {item["earlier_block_rule"]}\n')
                    f.write('\n' + v2['routing_conflicts']['limitations'] + '\n')
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
    if (args.review_state_file and valid_build_report(shadow_ai)
            and status.get('shadowrocket_ai', {}).get('exit_code') == 0
            and status.get('publish', {}).get('success')
            and run_url and summary_path):
        try:
            review_queue.acknowledge(shadow_ai, args.review_state_file)
        except (OSError, ValueError, TypeError) as exc:
            print(f'::error::Telegram delivered, but review acknowledgement failed: {type(exc).__name__}')
            return 1
    if (args.ai_review_state_file and status.get('ai_review')
            and status.get('publish', {}).get('success') is True
            and run_url and summary_path):
        try:
            ai_review_delivery.acknowledge(status['ai_review'], args.ai_review_state_file)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            print(f'::error::AI review receipt acknowledgement failed: {type(exc).__name__}')
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
