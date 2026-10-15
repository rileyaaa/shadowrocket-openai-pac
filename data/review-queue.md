# 上游人工审核清单

本文件自动生成，请修改 `config/review-decisions.json` 记录人工不通过结果。
到期仅提醒重新审核，不会自动放行；新增未审核项仅在首次送达前重试。
默认 6 个日历月复审；到期后未处理，每 7 天提醒一次。
已覆盖规则免重复审核；社区 IP/ASN 仅留档，Voice 目的 IP 仅采用官方 JSON。

| 规则 | 来源 | 状态 | 上次审核 | 下次复审 | 原因 / 已有覆盖 |
|---|---|---|---|---|---|
| DOMAIN,browser-intake-datadoghq.com | blackmatrix7, metacubex, v2fly | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | OpenAI 官方清单仅列 rum.browser-intake-datadoghq.com；裸域名未核实为 ChatGPT 必需目标，暂不扩大。 |
| DOMAIN,o33249.ingest.sentry.io | metacubex, v2fly | 已由现有 OpenAI 规则覆盖 | — | — | DOMAIN,o33249.ingest.sentry.io |
| DOMAIN,static.cloudflareinsights.com | blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | Cloudflare 通用网站分析主机；未列入 OpenAI 官方网络清单，未核实为专用依赖。 |
| DOMAIN-KEYWORD,openai | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | 关键字匹配可命中含 openai 字样的无关第三方域名；现有明确域名规则更精确。 |
| DOMAIN-SUFFIX,ai.com | blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | 现有官方网络清单未将 ai.com 全域及子域列为必需目的地址，缺乏扩大分流依据。 |
| DOMAIN-SUFFIX,algolia.net | blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | Algolia 为共享搜索服务；未核实整个域名及所有子域均属于 OpenAI 必需流量。 |
| DOMAIN-SUFFIX,api.statsig.com | blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | Statsig 属共享实验与特性服务；官方清单未要求匹配该主机的全部子域。 |
| DOMAIN-SUFFIX,auth0.com | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | Auth0 为共享身份平台；官方所列 auth0.openai.com 已由 openai.com 规则覆盖，不扩大到 auth0.com 全域。 |
| DOMAIN-SUFFIX,challenges.cloudflare.com | acl4ssr | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | 官方列出精确主机 challenges.cloudflare.com，已由手工 DOMAIN 规则覆盖；不扩大到它的全部子域。 |
| DOMAIN-SUFFIX,client-api.arkoselabs.com | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | Arkose 通用 API 域名；已覆盖特定 openai-api.arkoselabs.com，未证明本后缀的全部子域必需。 |
| DOMAIN-SUFFIX,events.statsigapi.net | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | Statsig 通用事件服务；官方清单未核实该域及全部子域的 OpenAI 必要性。 |
| DOMAIN-SUFFIX,featuregates.org | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | 共享特性开关服务，未见官方 ChatGPT 必需域名证据；保留观察而不全域分流。 |
| DOMAIN-SUFFIX,identrust.com | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | 通用证书相关服务，不是 OpenAI 专用主机；全域代理会引入无关流量。 |
| DOMAIN-SUFFIX,intercom.io | acl4ssr, blackmatrix7 | 已由现有 OpenAI 规则覆盖 | — | — | DOMAIN-SUFFIX,intercom.io |
| DOMAIN-SUFFIX,intercomcdn.com | acl4ssr, blackmatrix7 | 已由现有 OpenAI 规则覆盖 | — | — | DOMAIN-SUFFIX,intercomcdn.com |
| DOMAIN-SUFFIX,launchdarkly.com | blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | LaunchDarkly 是第三方共享功能配置平台；未见官方要求代理其整个域。 |
| DOMAIN-SUFFIX,observeit.net | blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | 第三方共享监控服务，缺乏当前 OpenAI 官方必需域名证据。 |
| DOMAIN-SUFFIX,openaiapi-site.azureedge.net | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | 精确主机 openaiapi-site.azureedge.net 已有 DOMAIN 规则；全部子域尚无核实依据。 |
| DOMAIN-SUFFIX,openaicom.imgix.net | blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | 精确主机 openaicom.imgix.net 已有 DOMAIN 规则；全部子域尚无核实依据。 |
| DOMAIN-SUFFIX,segment.io | blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | Segment 为第三方共享分析平台；官方未要求该域全部子域的 OpenAI 分流。 |
| DOMAIN-SUFFIX,sentry.io | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | Sentry 为共享错误监控平台；官方仅列两个特定 ingest.sentry.io 主机，已有精确规则。 |
| DOMAIN-SUFFIX,stripe.com | acl4ssr, blackmatrix7 | 人工不通过，暂不提醒 | 2026-10-15 | 2027-04-15 | Stripe 是共享支付平台；官方列出的 js.stripe.com 已有精确规则，整域范围过宽。 |
| IP-ASN,20473,no-resolve | blackmatrix7 | 社区 IP/ASN，仅留档；IP 只取官方 Voice | — | — | — |
| IP-CIDR,24.199.123.28/32,no-resolve | blackmatrix7 | 社区 IP/ASN，仅留档；IP 只取官方 Voice | — | — | — |
| IP-CIDR,64.23.132.171/32,no-resolve | blackmatrix7 | 社区 IP/ASN，仅留档；IP 只取官方 Voice | — | — | — |
