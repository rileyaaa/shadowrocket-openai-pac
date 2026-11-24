# AI 分流定期复审记录 — 2026-11-24

审核日期：2026-11-24（台北）。半年复审日期：2027-05-24。本轮是稳定使用前的策略复审，不修改程序、分流授权、节点、工作流或订阅；仅登记审核结论及时间。官方资料为本次可获取的版本（网页索引可能缓存），没有客户端抓包或出口日志，不能将文档允许访问等同于必须使用指定代理出口。

## 结论

- OpenAI 20 条原拒绝记录：逐条对照现有规则、官方网络说明及此前审核依据，维持暂不纳入共用 AI 专用节点。Statsig 的共享性质由其官方文档进一步确认；ai.com 是独立平台；openai.org 未取得完整范围必要性证据。已有精确主机与用户显式客户端例外不变。
- Claude 8 条原拒绝后缀：对照 Claude Code 生产入口及 Claude Academy，未取得这些后缀整体必须使用 AI 专用出口的新增证据，维持原决定。无法确认每个域的全部用途，不据此认定恶意或非 Anthropic 所有。
- Gemini 2 条原拒绝共享后端：无足以推翻上轮范围判断的新证据，维持原决定。新增候选 gemma.ai：Google 官方确认 Gemma 为开放模型系列；公开域名索引存在文档关联线索，但直接站点无法获取，缺乏 Gemini 整后缀必要性依据；首次登记暂不扩大、六个月后复审，不改变现行回落规则。
- 已批准共享依赖 10 组：本轮完成保留现有例外的策略决定，刷新日期。没有证明所有历史主机必须同出口，也没有证明可以安全移除；缺失实机证据明确写入各组 note，未来获得连接日志可提前复审。保留用户明确批准的 v2rayN 宽范围例外与 BitBrowser 8 个检测域名。
- v2rayN 已知冲突：`domain:r.openai.com` 前置拦截与 `domain:openai.com` 代理存在静态交集。保留有意的广告优先级；不是新增冲突。不修改真实 Telegram 送达回执（最近一次为 2026-11-24）；若无变化，按既有 30 天周期 2026-12-24 再提醒。官方 Voice IP 继续自动更新，官方网络文档仍按原每周周期检查。

## 已批准组复核依据与边界

- **openai-livekit**：本轮官方 LiveKit 防火墙表仍确认两个 TURN 后缀为共享通信基础设施。保留原用户批准的 Voice 兼容例外，不扩大到 livekit.cloud；尚未验证所有租户需同出口，下一次结合语音和其他通信应用日志复核收窄。 依据：https://docs.livekit.io/deploy/admin/firewall/ ; config/manual-openai.rules。
- **openai-shared-suffix**：可获取的官方指南仍列三个通配范围。作为既有覆盖优先例外保留，不把网络放行要求等同于所有租户必须同出口；以后结合实际登录、支持及邮件连接核实是否可收窄。 依据：https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps。
- **openai-shared-exact**：可获取的官方指南仍列出本组 8 个精确主机。保留登录、验证、设备检测及支付等原共享依赖，不扩大到父域；同出口必要性仍须实机验证。 依据：https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps。
- **openai-workos-frontend**：本轮指南未找到该精确主机；不能证明已废弃。复核决定保留历史精确规则，不新增范围；下一次优先用登录链路日志核实是否可删。 依据：config/manual-openai.rules ; scripts/build.py OFFICIAL_CHATGPT_SHARED_RULES ; https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps。
- **openai-telemetry**：官方网络指南继续列出两个 Sentry 主机和 RUM 主机，Codex 反馈源码确认第三个 Sentry 主机。保留原精确匹配；反馈/遥测不是全部核心业务必需，未取得同出口必要性或删除安全性的实机证据，不扩展供应商后缀。 依据：https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps ; https://github.com/openai/codex/blob/main/codex-rs/feedback/src/lib.rs。
- **openai-dedicated-vendor-names**：依据已有审核、精确租户名称及两端发布观察复查保留范围，不把共享 CDN、Azure、Vercel 父域加入规则。未逐个验证在线服务用途或所有子域；自动层 openai.com.cdn.cloudflare.net 后缀、WebPubSub 通配与历史 demo 主机仍是优先实机复核项；本轮不变。 依据：config/manual-openai.rules ; scripts/build.py OPENAI_SPECIFIC_HOSTS / SUFFIXES / WILDCARDS ; data/openai-review-snapshots.json。
- **gemini-shared-google**：官方 Code Assist 说明确认 cloudaicompanion/cloudcode 相关 API；Gemini Notebook Enterprise 2026-11 的主机迁移要求新旧四个域名并存，现有规则已覆盖。保留历史产品级精确匹配，不扩大 Google 通用父域；并非所有历史主机均有逐项官方/同出口证明，继续结合 Workspace、Antigravity 和其他 Google 业务实机复核。 依据：https://knowledge.workspace.google.com/admin/generative-ai/gemini-app/gemini-app-firewall-settings ; https://docs.cloud.google.com/gemini/docs/codeassist/set-up-gemini ; https://docs.cloud.google.com/gemini/enterprise/docs/release-notes ; config/ai-services.rules。
- **claude-shared-vendors**：官方 Claude Code 说明明确两项 Datadog intake 属可选遥测。CDN、Sentry 另两项按已有精确批准保留，未取得删除无影响的实际日志。四项均不扩大到共享供应商父域；可选性与同出口必要性后续继续复核。 依据：https://code.claude.com/docs/en/network-config ; config/ai-services.rules ; scripts/ai_services.py。
- **v2rayn-openai-wide-extras**：Statsig 官方确认共享 SDK 相关域名；无整个五个后缀及 Datadog 裸域均为 OpenAI 必需的证据。本轮复核决定保留用户显式 v2rayN 特批，不视为共用批准；下次优先按连接日志判断收窄或回归 Johnshall，不改变本次路由。 依据：config/v2rayn/openai-extra.rules ; https://docs.statsig.com/infrastructure/statsig_domains ; https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps。
- **bitbrowser-user-domains**：八个明确用户指定域名仍按既有特批保留；IP 查询服务并非 BitBrowser 独占，不新增域名。缺少真实进程和普通应用出口日志，未验证是否可仅依赖专属进程匹配，下一次继续复核。 依据：data/bitbrowser_domains.txt ; https://ip-api.com/docs ; config/v2rayn/verified-processes.txt。

## 公开资料

- https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps
- https://ai.com/company-news/ai-com-launch
- https://docs.statsig.com/infrastructure/statsig_domains
- https://docs.livekit.io/deploy/admin/firewall/
- https://github.com/openai/codex/blob/main/codex-rs/feedback/src/lib.rs
- https://code.claude.com/docs/en/network-config
- https://academy.claude.com/
- https://knowledge.workspace.google.com/admin/generative-ai/gemini-app/gemini-app-firewall-settings
- https://docs.cloud.google.com/gemini/docs/codeassist/set-up-gemini
- https://docs.cloud.google.com/gemini/enterprise/docs/release-notes （2026-11 Notebook 新旧入口迁移）
- https://ai.google.dev/gemma/docs?hl=zh-cn
- https://gemma.ai.cutestat.com/ （第三方索引，仅关联线索，非官方所有权证明；gemma.ai 直接访问未能核实）
- https://ip-api.com/docs

历史 2026-11-23 记录与测试快照保留不改。本次不手工伪造通知回执，由原同步程序生成审核清单和维护实际送达状态。若有新的官方需求、客户端故障或用户提供的日志，可早于下次复审日期处理。
