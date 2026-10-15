# 上游人工审核清单

本文件自动生成，请修改 `config/review-decisions.json` 记录人工不通过结果。
到期仅提醒重新审核，不会自动放行；新增未审核项仅在首次送达前重试。
默认 6 个日历月复审；到期后未处理，每 7 天提醒一次。
已覆盖规则免重复审核；社区 IP/ASN 仅留档，Voice 目的 IP 仅采用官方 JSON。

| 规则 | 来源 | 状态 | 上次审核 | 下次复审 | 原因 / 已有覆盖 |
|---|---|---|---|---|---|
| DOMAIN,browser-intake-datadoghq.com | blackmatrix7, metacubex, v2fly | 待人工审核 | — | — | — |
| DOMAIN,o33249.ingest.sentry.io | metacubex, v2fly | 已由现有 OpenAI 规则覆盖 | — | — | DOMAIN,o33249.ingest.sentry.io |
| DOMAIN,static.cloudflareinsights.com | blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-KEYWORD,openai | acl4ssr, blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,ai.com | blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,algolia.net | blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,api.statsig.com | blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,auth0.com | acl4ssr, blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,challenges.cloudflare.com | acl4ssr | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,client-api.arkoselabs.com | acl4ssr, blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,events.statsigapi.net | acl4ssr, blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,featuregates.org | acl4ssr, blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,identrust.com | acl4ssr, blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,intercom.io | acl4ssr, blackmatrix7 | 已由现有 OpenAI 规则覆盖 | — | — | DOMAIN-SUFFIX,intercom.io |
| DOMAIN-SUFFIX,intercomcdn.com | acl4ssr, blackmatrix7 | 已由现有 OpenAI 规则覆盖 | — | — | DOMAIN-SUFFIX,intercomcdn.com |
| DOMAIN-SUFFIX,launchdarkly.com | blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,observeit.net | blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,openaiapi-site.azureedge.net | acl4ssr, blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,openaicom.imgix.net | blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,segment.io | blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,sentry.io | acl4ssr, blackmatrix7 | 待人工审核 | — | — | — |
| DOMAIN-SUFFIX,stripe.com | acl4ssr, blackmatrix7 | 待人工审核 | — | — | — |
| IP-ASN,20473,no-resolve | blackmatrix7 | 社区 IP/ASN，仅留档；IP 只取官方 Voice | — | — | — |
| IP-CIDR,24.199.123.28/32,no-resolve | blackmatrix7 | 社区 IP/ASN，仅留档；IP 只取官方 Voice | — | — | — |
| IP-CIDR,64.23.132.171/32,no-resolve | blackmatrix7 | 社区 IP/ASN，仅留档；IP 只取官方 Voice | — | — | — |
