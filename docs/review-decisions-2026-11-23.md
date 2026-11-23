# AI 分流人工审核记录 — 2026-11-23

审核日期：**2026-11-23（台北）**。下次定期复审：**2027-05-23**（6 个日历月）。

## 审核范围与决定

| 范围 | 数量 | 处理 |
|---|---:|---|
| OpenAI 已拒绝候选 | 20 | 逐条对照当前官方网络建议及此前的精确匹配依据；保持原路由政策并刷新 reviewed_at |
| Gemini 已拒绝共享端点 | 2 | Geller、Proactive 仍与普通 Google 产品共用，继续回落 Johnshall，刷新 reviewed_at |
| Claude 原待审候选 | 8 | 有些候选存在基础设施或实验环境线索，但没有足以放行**整个后缀及子域**的生产必要性证明；本轮明确暂不放行并登记六个月后复审 |

没有新增 AI 代理域名、代理节点或第三方整域规则。**“暂不放行”是本项目的分流范围决定，不等于认定该域名恶意，也不代表它一定不属于 Anthropic。** 新的官方网络要求或真实连接日志可触发提前复审，不必机械等到到期日。

## Claude 的 8 条逐项判断

| 候选后缀 | 复核重点 | 决定 |
|---|---|---|
| `ant.dev` | Claude 登录/CSP 的公开故障记录及非官方客户端分析出现 `*.ant.dev`，偏向开发/预览用途；尚无整域生产必需证明 | 暂不放行 |
| `anthropic.team` | 有解析至 Anthropic 网络的记录，但整个后缀的正式用途未确认 | 暂不放行 |
| `antspace.dev` | 同址/网络关联不等于每个子域都用于 Claude 生产业务 | 暂不放行 |
| `chatbotclaude.com` | 出现与 Anthropic 网络相关解析，亦有域名迁移演示内容；未取得正式服务入口依据 | 暂不放行 |
| `claudeacademy.com` | Anthropic 当前官方学院使用 `academy.claude.com`；另一个域名曾出现与 Claude 学院无关的金融培训网页记录 | 暂不放行 |
| `claudemcpclient.com` | 官方 Claude Code 文档列出的是 `mcp-proxy.anthropic.com` 等端点；该社区域名必要性未确认 | 暂不放行 |
| `claudepages.dev` | 同址/社区列表不足以证明全部子域均属生产流量 | 暂不放行 |
| `claudestudio.com` | 同址/社区列表不足以证明全部子域均属生产流量 | 暂不放行 |

这里保留了候选存在的证据和不确定性，不根据域名名称直接认定官方产品。特别是：IP 地址属于 Anthropic ASN 或与官方主机共享同一地址，只是**关联线索**，不是域名控制权和完整功能必要性的充分证据。

## OpenAI 已审核记录的复核重点

- 共有 20 条早前人工不通过记录。本次参考当前 OpenAI 官方 ChatGPT 网络允许清单，并核对域名匹配粒度：官方列出确切主机时，不自动扩大到共享供应商的整个后缀。
- `ai.com` 已是与 OpenAI 不同的独立 AI 平台，确认继续拒绝作为 OpenAI 专用后缀。
- `openai.org` 仍没有可证明所有子域均为 ChatGPT/API 必需连接的官方依据，保留人工复核而非自动代理。
- Statsig、Cloudflare、Stripe、Auth0、Sentry、Algolia、Datadog 等共享服务或未证明的宽后缀不予批量批准；当前已经核实的精确 OpenAI 主机继续按原规则路由。
- 本轮 20 条均保留“暂不放行”决定，只把 `reviewed_at` 更新为今天，所有记录的复审周期沿用六个月。

## Gemini 已审核记录

`geller-pa.googleapis.com` 和 `proactivebackend-pa.googleapis.com` 不再进入 Gemini 专属规则。现有证据表明这些后端并非 AI 独占；Google 的 Gemini 防火墙允许清单也不能直接等同于 AI 专用分流清单。保留原 Johnshall 匹配及六个月复审。

## 未作日期更新的其他项目

- OpenAI 队列中已由明确规则覆盖的项目不属于拒绝决定，没有独立的六个月审核到期日期。
- 社区 ASN/IP 候选继续仅留档，Voice 目的 IP 以官方实时来源自动更新；它们不应被写入域名拒绝审核记录。
- 当前 BitBrowser 专用进程和已批准域名保持不变，本次没有发现其独立人工审核候选；它不使用 `review-decisions.json` 的日期机制。

## 证据入口（2026-11-23 复核）

- [OpenAI 官方 ChatGPT 网络建议](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)
- [Anthropic Claude Code 企业网络要求](https://code.claude.com/docs/en/network-config)
- [Anthropic 官方 Claude Academy](https://academy.claude.com/help)
- [Google Gemini App 防火墙说明](https://knowledge.workspace.google.com/admin/generative-ai/gemini-app/gemini-app-firewall-settings)
- [ai.com 自身 2026-02-06 新平台声明](https://ai.com/company-news/ai-com-launch)
- [Anthropic 自有 ASN 地址中出现部分候选解析](https://bgp.he.net/net/160.79.104.0/23)（只作关联证据，不作域名完整归属证明）
- [社区域名清单](https://github.com/v2fly/domain-list-community/blob/master/data/anthropic)（仅用于提出候选）

**真正改变发布行为的唯一文件为两份人工审核决定 JSON。** 日志、复审日期和状态由现有生成器生成；订阅规则不因更新审核日期而自动扩大。 
