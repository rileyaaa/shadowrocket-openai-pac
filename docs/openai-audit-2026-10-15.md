# OpenAI 清单审查与自动审核首轮结果（2026-10-15）

审查基线：`216c43125c67ec71688c1df836a5d564643ba81b`。核对 GitHub 最新主分支、生成配置中的全部 OpenAI 段、自动列表、43 条手工规则、官方网络白名单和 Voice 目的 IP。文档为本次审查快照；后续动态结果以 [逐条审核记录](../data/openai-review.json) 和 Actions 为准。

## 结论

- `24.199.123.28/32`、`64.23.132.171/32` 只存在于社区候选及排除记录，没有被其他提交加入当前有效 OpenAI 规则；二者不在本次官方 Voice 地址范围中，继续待证据。
- `IP-ASN,20473` 拒绝。原 25 条排除项中，3 条已覆盖、8 条拒绝、14 条待证据。没有为清空待审队列而放行。
- 23 条 Voice 地址全部与本次官方 JSON 对应，均为 IPv4 `/32`，合计 23 个地址；没有 IPv6、新 IP、全局 UDP/3478 或整 ASN 扩张。
- 43 条手工规则全部保留。21 条由当前官方网络清单直接覆盖；4 个演示入口重新核对官方 Showcase；2 条 LiveKit 共享范围属于用户明确接受的例外；其余 16 条保留既有兼容政策，并明确标注当前固定网络证据的不足。
- 自动域名由 22 条变为 38 条。新增的 16 条均有官方证据且已被原手工层覆盖，故本次没有扩大最终目的范围。两个节点、DNS、手工层及 Johnshall 完整尾部与审查前一致。
- 自动引擎对 71 个社区/官方候选给出 49 条已覆盖、14 条待证据、8 条拒绝、0 条新增范围批准。这里的“已覆盖”是候选条目数，并非最终规则数。

自动层和手工层独立保留，机器库存按层计数。`retained_reviewed_policy_not_current_network_evidence` 表示沿用固定政策而非本次网络证据通过；即便某条另有本次人工核对的产品说明，也不会被伪装成每天自动抓取了该说明。

## 43 条手工域名逐条核对

| 规则 | 本次依据与处理 |
|---|---|
| `DOMAIN-SUFFIX,openai.fm` | [官方 Showcase](https://developers.openai.com/showcase/openai-fm)：官方演示入口；沿用已审核的根域兼容范围 |
| `DOMAIN,chatkit.world` | [官方 Showcase](https://developers.openai.com/showcase/chatkit-world)：官方演示入口；仅精确主机 |
| `DOMAIN,openai-photobooth-demo.vercel.app` | [官方 Showcase](https://developers.openai.com/showcase/openai-imagegen-demo)：官方演示入口；仅该租户主机 |
| `DOMAIN,openai-realtime-solar-system-demo.vercel.app` | [官方 Showcase](https://developers.openai.com/showcase/solar-system-demo)：官方演示入口；仅该租户主机 |
| `DOMAIN-SUFFIX,openai.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN-SUFFIX,oaistatic.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN-SUFFIX,oaiusercontent.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN-SUFFIX,oaistatsig.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN-SUFFIX,sora.com` | 保留既有政策：历史兼容范围；保留不表示服务当前可用 |
| `DOMAIN-SUFFIX,chat.com` | 保留既有政策：沿用已审核的兼容入口；当前网络清单未单列此域 |
| `DOMAIN-SUFFIX,crixet.com` | 保留既有政策：官方确认收购 Crixet，但收购说明不等于该旧域全部子域的当前网络证明；保留兼容范围 |
| `DOMAIN,openai.com.cdn.cloudflare.net` | 保留既有政策：既有基础设施精确主机；本次网络清单未列出，不据命名或社区收录推断更多地址 |
| `DOMAIN,openaiapi-site.azureedge.net` | 保留既有政策：既有基础设施精确主机；本次网络清单未列出，不据命名或社区收录推断更多地址 |
| `DOMAIN,openaiassets.blob.core.windows.net` | 保留既有政策：既有基础设施精确主机；本次网络清单未列出，不据命名或社区收录推断更多地址 |
| `DOMAIN,openaicom-api-bdcpf8c6d2e9atf6.z01.azurefd.net` | 保留既有政策：既有基础设施精确主机；本次网络清单未列出，不据命名或社区收录推断更多地址 |
| `DOMAIN,openaicom.imgix.net` | 保留既有政策：既有基础设施精确主机；本次网络清单未列出，不据命名或社区收录推断更多地址 |
| `DOMAIN,openaicomproductionae4b.blob.core.windows.net` | 保留既有政策：既有基础设施精确主机；本次网络清单未列出，不据命名或社区收录推断更多地址 |
| `DOMAIN,production-openaicom-storage.azureedge.net` | 保留既有政策：既有基础设施精确主机；本次网络清单未列出，不据命名或社区收录推断更多地址 |
| `DOMAIN-SUFFIX,chatgpt.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN-SUFFIX,chatgpt.site` | 保留既有政策：沿用 Sites 的既有范围；本次固定网络清单未列出，不用它推断其他站点 |
| `DOMAIN-WILDCARD,chatgpt-async-webps-prod-*.webpubsub.azure.com` | 保留既有政策：既有专用 Azure 模式；不执行新正则，不扩大为 webpubsub.azure.com |
| `DOMAIN-SUFFIX,chatgpt.livekit.cloud` | 保留既有政策：既有 Voice 专用命名空间；不扩大为 livekit.cloud |
| `DOMAIN-SUFFIX,host.livekit.cloud` | 用户已接受的共享 LiveKit 例外；保留，不能据此批准整个云平台 |
| `DOMAIN-SUFFIX,turn.livekit.cloud` | 用户已接受的共享 LiveKit 例外；保留，不能据此批准整个云平台 |
| `DOMAIN,cdn.openaimerge.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN,openai.qualtrics.com` | 保留既有政策：既有基础设施精确主机；本次网络清单未列出，不据命名或社区收录推断更多地址 |
| `DOMAIN,chat.openai.com.cdn.cloudflare.net` | 保留既有政策：既有基础设施精确主机；本次网络清单未列出，不据命名或社区收录推断更多地址 |
| `DOMAIN,openai-api.arkoselabs.com` | 保留既有政策：既有基础设施精确主机；本次网络清单未列出，不据命名或社区收录推断更多地址 |
| `DOMAIN-SUFFIX,ct.sendgrid.net` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN-SUFFIX,intercom.io` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN-SUFFIX,intercomcdn.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN,cdn.workos.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN,challenges.cloudflare.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN,forwarder.workos.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN,frontend-apps-multi-region.workos.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN,humb.apple.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN,images.workoscdn.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN,js.stripe.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN,o207216.ingest.sentry.io` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN,o33249.ingest.sentry.io` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN,rum.browser-intake-datadoghq.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN,setup.workos.com` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |
| `DOMAIN,workos.imgix.net` | 当前[官方网络清单](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)覆盖；保持原精确/后缀范围 |

Crixet 产品关系来源：[OpenAI Introducing Prism](https://openai.com/index/introducing-prism/)。这条资料只支持产品关系，不自动授权任何新域名或 IP。

## 原自动域名 22 条逐条核对

此表检查原自动层是否受到本次扩域影响。实际发布后的 38 条自动域名及 43 条手工规则均在机器库存中逐条列出。

| 原自动规则 | 当前官方网络证据 | 手工层是否完整覆盖 | 处理 |
|---|---|---|---|
| `DOMAIN,openai-api.arkoselabs.com` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |
| `DOMAIN,openai.qualtrics.com` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |
| `DOMAIN,openaiapi-site.azureedge.net` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |
| `DOMAIN,openaiassets.blob.core.windows.net` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |
| `DOMAIN,openaicom-api-bdcpf8c6d2e9atf6.z01.azurefd.net` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |
| `DOMAIN,openaicom.imgix.net` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |
| `DOMAIN,openaicomproductionae4b.blob.core.windows.net` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |
| `DOMAIN,production-openaicom-storage.azureedge.net` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |
| `DOMAIN-SUFFIX,chat.com` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |
| `DOMAIN-SUFFIX,chatgpt.com` | 有 | 是 | 保留原范围 |
| `DOMAIN-SUFFIX,chatgpt.livekit.cloud` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |
| `DOMAIN-SUFFIX,chatgpt.site` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |
| `DOMAIN-SUFFIX,crixet.com` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |
| `DOMAIN-SUFFIX,host.livekit.cloud` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |
| `DOMAIN-SUFFIX,oaistatic.com` | 有 | 是 | 保留原范围 |
| `DOMAIN-SUFFIX,oaistatsig.com` | 有 | 是 | 保留原范围 |
| `DOMAIN-SUFFIX,oaiusercontent.com` | 有 | 是 | 保留原范围 |
| `DOMAIN-SUFFIX,openai.com` | 有 | 是 | 保留原范围 |
| `DOMAIN-SUFFIX,openai.com.cdn.cloudflare.net` | 本次固定清单未覆盖；沿用受审查政策 | 否 | 保留原范围；既有 Cloudflare 别名后缀，不能被精确手工主机视为完全等价，不据此扩域 |
| `DOMAIN-SUFFIX,sora.com` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |
| `DOMAIN-SUFFIX,turn.livekit.cloud` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |
| `DOMAIN-WILDCARD,chatgpt-async-webps-prod-*.webpubsub.azure.com` | 本次固定清单未覆盖；沿用受审查政策 | 是 | 保留原范围 |

## 官方 Voice 全量 23 条

[官方目的 IP JSON](https://openai.com/chatgpt-voice.json)。本次规范化清单和来源 SHA-256 保存在审核 JSON 的 `evidence.voice`；所有地址也逐条列于 `inventory`。

| 前缀 | 结论 |
|---|---|
| `4.151.200.38/32` | 官方目的地址；保持 `/32` |
| `4.155.146.196/32` | 官方目的地址；保持 `/32` |
| `4.197.172.116/32` | 官方目的地址；保持 `/32` |
| `4.217.235.100/32` | 官方目的地址；保持 `/32` |
| `4.245.198.13/32` | 官方目的地址；保持 `/32` |
| `13.71.25.29/32` | 官方目的地址；保持 `/32` |
| `20.74.221.21/32` | 官方目的地址；保持 `/32` |
| `20.162.96.163/32` | 官方目的地址；保持 `/32` |
| `20.168.48.117/32` | 官方目的地址；保持 `/32` |
| `20.184.36.134/32` | 官方目的地址；保持 `/32` |
| `20.203.144.245/32` | 官方目的地址；保持 `/32` |
| `40.118.236.137/32` | 官方目的地址；保持 `/32` |
| `51.4.112.173/32` | 官方目的地址；保持 `/32` |
| `52.143.181.161/32` | 官方目的地址；保持 `/32` |
| `68.155.152.41/32` | 官方目的地址；保持 `/32` |
| `72.146.20.246/32` | 官方目的地址；保持 `/32` |
| `74.248.148.7/32` | 官方目的地址；保持 `/32` |
| `102.37.57.54/32` | 官方目的地址；保持 `/32` |
| `135.220.40.201/32` | 官方目的地址；保持 `/32` |
| `172.203.39.49/32` | 官方目的地址；保持 `/32` |
| `172.207.173.200/32` | 官方目的地址；保持 `/32` |
| `172.214.226.198/32` | 官方目的地址；保持 `/32` |
| `191.233.251.27/32` | 官方目的地址；保持 `/32` |

## 原 25 条待审/排除候选的本次处理

| 候选 | 结论 | 理由 |
|---|---|---|
| `DOMAIN,browser-intake-datadoghq.com` | 待证据 | 缺少当前官方证据，社区收录次数不构成证明 |
| `DOMAIN,o33249.ingest.sentry.io` | 已覆盖 | 当前官方网络清单明确覆盖，未扩大官方范围 |
| `DOMAIN,static.cloudflareinsights.com` | 待证据 | 缺少当前官方证据，社区收录次数不构成证明 |
| `DOMAIN-KEYWORD,openai` | 拒绝 | 整 ASN、关键词或全局协议/端口匹配超出允许边界 |
| `DOMAIN-SUFFIX,ai.com` | 待证据 | 缺少当前官方证据，社区收录次数不构成证明 |
| `DOMAIN-SUFFIX,algolia.net` | 待证据 | 缺少当前官方证据，社区收录次数不构成证明 |
| `DOMAIN-SUFFIX,api.statsig.com` | 待证据 | 缺少当前官方证据，社区收录次数不构成证明 |
| `DOMAIN-SUFFIX,auth0.com` | 拒绝 | 整共享平台范围过宽，只能审查具体目标 |
| `DOMAIN-SUFFIX,challenges.cloudflare.com` | 拒绝 | 候选规则比已确认的主机或子域范围更宽 |
| `DOMAIN-SUFFIX,client-api.arkoselabs.com` | 待证据 | 缺少当前官方证据，社区收录次数不构成证明 |
| `DOMAIN-SUFFIX,events.statsigapi.net` | 待证据 | 缺少当前官方证据，社区收录次数不构成证明 |
| `DOMAIN-SUFFIX,featuregates.org` | 待证据 | 缺少当前官方证据，社区收录次数不构成证明 |
| `DOMAIN-SUFFIX,identrust.com` | 待证据 | 缺少当前官方证据，社区收录次数不构成证明 |
| `DOMAIN-SUFFIX,intercom.io` | 已覆盖 | 当前官方网络清单明确覆盖，未扩大官方范围 |
| `DOMAIN-SUFFIX,intercomcdn.com` | 已覆盖 | 当前官方网络清单明确覆盖，未扩大官方范围 |
| `DOMAIN-SUFFIX,launchdarkly.com` | 待证据 | 缺少当前官方证据，社区收录次数不构成证明 |
| `DOMAIN-SUFFIX,observeit.net` | 待证据 | 缺少当前官方证据，社区收录次数不构成证明 |
| `DOMAIN-SUFFIX,openaiapi-site.azureedge.net` | 拒绝 | 候选规则比已确认的主机或子域范围更宽 |
| `DOMAIN-SUFFIX,openaicom.imgix.net` | 拒绝 | 候选规则比已确认的主机或子域范围更宽 |
| `DOMAIN-SUFFIX,segment.io` | 待证据 | 缺少当前官方证据，社区收录次数不构成证明 |
| `DOMAIN-SUFFIX,sentry.io` | 拒绝 | 整共享平台范围过宽，只能审查具体目标 |
| `DOMAIN-SUFFIX,stripe.com` | 拒绝 | 整共享平台范围过宽，只能审查具体目标 |
| `IP-ASN,20473,no-resolve` | 拒绝 | 整 ASN、关键词或全局协议/端口匹配超出允许边界 |
| `IP-CIDR,24.199.123.28/32,no-resolve` | 待证据 | 当前官方 Voice 目的地址清单未确认此 IP |
| `IP-CIDR,64.23.132.171/32,no-resolve` | 待证据 | 当前官方 Voice 目的地址清单未确认此 IP |

## 验证范围

离线回归覆盖页面段落提取、错误/截断页面、伪装域名、精确主机与整域边界、未知语法、全局端口/ASN、两个待审 IP、Voice 前缀包含关系、旧待审转通过、证据撤回后自动规则退出、手工兜底保留、失败时所有已发布文件不变，以及通知中审批与实际发布的区别。全部 63 项测试通过，并完成八个真实上游的在线构建。

构建层验证不代替手机连接验收：无法仅凭静态规则证明所有未来 OpenAI 请求、隐藏依赖或共享域上的请求都能被正确区分。实际 Voice、登录、上传和 Codex 命中仍需设备连接记录。
