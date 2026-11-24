# 上游人工审核清单

本文件自动生成，请修改 `config/review-decisions.json` 记录人工不通过结果。
到期仅提醒重新审核，不会自动放行；首次送达失败会重试。
默认 6 个日历月复审；到期后未处理，每 30 天提醒一次。
已覆盖规则免重复审核；社区 IP/ASN 仅留档，Voice 目的 IP 仅采用官方 JSON。

| 规则 | 来源 | 状态 | 上次审核 | 下次复审 | 原因 / 已有覆盖 |
|---|---|---|---|---|---|
| DOMAIN,browser-intake-datadoghq.com | blackmatrix7, metacubex, v2fly | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | OpenAI 官方清单仅列 rum.browser-intake-datadoghq.com；裸域名未核实为 ChatGPT 必需目标，暂不扩大。 |
| DOMAIN,o33249.ingest.sentry.io | metacubex, v2fly | 已由现有 OpenAI 规则覆盖 | — | — | DOMAIN,o33249.ingest.sentry.io |
| DOMAIN,o33249.ingest.us.sentry.io | metacubex, v2fly | 已由现有 OpenAI 规则覆盖 | — | — | DOMAIN,o33249.ingest.us.sentry.io |
| DOMAIN,static.cloudflareinsights.com | blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | Cloudflare 通用网站分析主机；未列入 OpenAI 官方网络清单，未核实为专用依赖。 |
| DOMAIN-KEYWORD,openai | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | 关键字匹配可命中含 openai 字样的无关第三方域名；现有明确域名规则更精确。 |
| DOMAIN-SUFFIX,ai.com | blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | 2026-11-24 复核：ai.com 自身 2026-02-06 公告确认是独立 AI 平台，不属于 OpenAI/ChatGPT 专属域名；继续拒绝整域进入 OpenAI 专用节点。 |
| DOMAIN-SUFFIX,algolia.net | blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | Algolia 为共享搜索服务；未核实整个域名及所有子域均属于 OpenAI 必需流量。 |
| DOMAIN-SUFFIX,api.statsig.com | blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | Statsig 官方域名文档确认该主机属于通用 SDK/API 服务；OpenAI 指南并未要求其全部子域，继续拒绝共用后缀（v2rayN 用户特批独立保留）。 |
| DOMAIN-SUFFIX,auth0.com | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | Auth0 为共享身份平台；官方所列 auth0.openai.com 已由 openai.com 规则覆盖，不扩大到 auth0.com 全域。 |
| DOMAIN-SUFFIX,challenges.cloudflare.com | acl4ssr | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | 官方列出精确主机 challenges.cloudflare.com，已由手工 DOMAIN 规则覆盖；不扩大到它的全部子域。 |
| DOMAIN-SUFFIX,client-api.arkoselabs.com | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | Arkose 通用 API 域名；已覆盖特定 openai-api.arkoselabs.com，未证明本后缀的全部子域必需。 |
| DOMAIN-SUFFIX,events.statsigapi.net | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | Statsig 官方域名文档确认是共享事件服务；无全后缀 OpenAI 必要性证据，继续拒绝共用后缀（v2rayN 用户特批独立保留）。 |
| DOMAIN-SUFFIX,featuregates.org | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | Statsig 官方域名文档确认是共享特性开关端点；无整个后缀必须经 OpenAI 专用出口的证据。继续拒绝共用后缀，v2rayN 用户特批不变。 |
| DOMAIN-SUFFIX,identrust.com | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | 通用证书相关服务，不是 OpenAI 专用主机；全域代理会引入无关流量。 |
| DOMAIN-SUFFIX,intercom.io | acl4ssr, blackmatrix7 | 已由现有 OpenAI 规则覆盖 | — | — | DOMAIN-SUFFIX,intercom.io |
| DOMAIN-SUFFIX,intercomcdn.com | acl4ssr, blackmatrix7 | 已由现有 OpenAI 规则覆盖 | — | — | DOMAIN-SUFFIX,intercomcdn.com |
| DOMAIN-SUFFIX,launchdarkly.com | blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | LaunchDarkly 是第三方共享功能配置平台；未见官方要求代理其整个域。 |
| DOMAIN-SUFFIX,observeit.net | blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | 第三方共享监控服务，缺乏当前 OpenAI 官方必需域名证据。 |
| DOMAIN-SUFFIX,openai.org | metacubex, v2fly | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | 2026-11-24 复核：可获取的 OpenAI 官方网络指南仍未列此域，未取得所有权及生产连接必要性证据。名称相似不足以批准整个后缀；保留定期复审。 |
| DOMAIN-SUFFIX,openaiapi-site.azureedge.net | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | 精确主机 openaiapi-site.azureedge.net 已有 DOMAIN 规则；全部子域尚无核实依据。 |
| DOMAIN-SUFFIX,openaicom.imgix.net | blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | 精确主机 openaicom.imgix.net 已有 DOMAIN 规则；全部子域尚无核实依据。 |
| DOMAIN-SUFFIX,segment.io | blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | Segment 为第三方共享分析平台；官方未要求该域全部子域的 OpenAI 分流。 |
| DOMAIN-SUFFIX,sentry.io | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | Sentry 为共享错误监控平台；可获取的 OpenAI 指南列出两个特定 ingest 主机，Codex 官方源码另确认一个精确反馈主机，现有精确规则覆盖，不批准整个供应商后缀。 |
| DOMAIN-SUFFIX,stripe.com | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-11-24 | 2027-05-24 | Stripe 是共享支付平台；官方列出的 js.stripe.com 已有精确规则，整域范围过宽。 |
| IP-ASN,20473,no-resolve | blackmatrix7 | 社区 IP/ASN，仅留档；IP 只取官方 Voice | — | — | — |
| IP-CIDR,24.199.123.28/32,no-resolve | blackmatrix7 | 社区 IP/ASN，仅留档；IP 只取官方 Voice | — | — | — |
| IP-CIDR,64.23.132.171/32,no-resolve | blackmatrix7 | 社区 IP/ASN，仅留档；IP 只取官方 Voice | — | — | — |

> 新候选首次提醒；未处理的待审或到期项按配置间隔再次汇总提醒。

| 规则 | Shadowrocket | v2rayN |
|---|---|---|
| DOMAIN,browser-intake-datadoghq.com | 未由专用规则覆盖 | 客户端专属例外覆盖（不等于共用批准） |
| DOMAIN,o33249.ingest.sentry.io | 共用规则覆盖 | 共用规则覆盖 |
| DOMAIN,o33249.ingest.us.sentry.io | 共用规则覆盖 | 共用规则覆盖 |
| DOMAIN,static.cloudflareinsights.com | 未由专用规则覆盖 | 未由专用规则覆盖 |
| DOMAIN-KEYWORD,openai | 未由专用规则覆盖 | 未由专用规则覆盖 |
| DOMAIN-SUFFIX,ai.com | 未由专用规则覆盖 | 未由专用规则覆盖 |
| DOMAIN-SUFFIX,algolia.net | 未由专用规则覆盖 | 未由专用规则覆盖 |
| DOMAIN-SUFFIX,api.statsig.com | 未由专用规则覆盖 | 客户端专属例外覆盖（不等于共用批准） |
| DOMAIN-SUFFIX,auth0.com | 未由专用规则覆盖 | 未由专用规则覆盖 |
| DOMAIN-SUFFIX,challenges.cloudflare.com | 未由专用规则覆盖 | 未由专用规则覆盖 |
| DOMAIN-SUFFIX,client-api.arkoselabs.com | 未由专用规则覆盖 | 未由专用规则覆盖 |
| DOMAIN-SUFFIX,events.statsigapi.net | 未由专用规则覆盖 | 客户端专属例外覆盖（不等于共用批准） |
| DOMAIN-SUFFIX,featuregates.org | 未由专用规则覆盖 | 客户端专属例外覆盖（不等于共用批准） |
| DOMAIN-SUFFIX,identrust.com | 未由专用规则覆盖 | 未由专用规则覆盖 |
| DOMAIN-SUFFIX,intercom.io | 共用规则覆盖 | 共用规则覆盖 |
| DOMAIN-SUFFIX,intercomcdn.com | 共用规则覆盖 | 共用规则覆盖 |
| DOMAIN-SUFFIX,launchdarkly.com | 未由专用规则覆盖 | 未由专用规则覆盖 |
| DOMAIN-SUFFIX,observeit.net | 未由专用规则覆盖 | 未由专用规则覆盖 |
| DOMAIN-SUFFIX,openai.org | 未由专用规则覆盖 | 未由专用规则覆盖 |
| DOMAIN-SUFFIX,openaiapi-site.azureedge.net | 未由专用规则覆盖 | 未由专用规则覆盖 |
| DOMAIN-SUFFIX,openaicom.imgix.net | 未由专用规则覆盖 | 未由专用规则覆盖 |
| DOMAIN-SUFFIX,segment.io | 未由专用规则覆盖 | 未由专用规则覆盖 |
| DOMAIN-SUFFIX,sentry.io | 未由专用规则覆盖 | 未由专用规则覆盖 |
| DOMAIN-SUFFIX,stripe.com | 未由专用规则覆盖 | 未由专用规则覆盖 |
| IP-ASN,20473,no-resolve | 未由专用规则覆盖 | 未由专用规则覆盖 |
| IP-CIDR,24.199.123.28/32,no-resolve | 未由专用规则覆盖 | 未由专用规则覆盖 |
| IP-CIDR,64.23.132.171/32,no-resolve | 未由专用规则覆盖 | 未由专用规则覆盖 |
