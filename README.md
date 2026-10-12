# Shadowrocket · OpenAI 专用出口 + Johnshall 原样分流

基于 [Johnshall 上游](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever) 的完整 Shadowrocket 配置，每天同步：**明确识别的 OpenAI 目的地走专用节点**；其他 Johnshall 原本 `Proxy` 的流量走另一个指定节点。DIRECT / REJECT / 最后直连保留原规则。节点所在国家可随时更换，不与配置文件名和变量名绑定。

## 小火箭完整配置订阅

```text
https://raw.githubusercontent.com/rileyaaa/shadowrocket-openai-pac/main/Shadowrocket_Johnshall_OpenAI.conf
```

**注意：订阅地址已经更名，旧的 `Shadowrocket_Johnshall_JP_KR.conf` 地址不再提供更新。请在 Shadowrocket 中改用上面的新 Raw 地址。**

请先在小火箭导入两个实际代理节点，路由模式选「配置」。本仓库不存储任何代理凭据。两个节点的完整备注名称只在 [`config/user-settings.json`](config/user-settings.json) 中维护：

```json
{"openai_node_name":"日本JP","johnshall_proxy_node_name":"韩国KR"}
```

两个字段表示**分流用途**，不是国家：`openai_node_name` 是 OpenAI 专用出口，`johnshall_proxy_node_name` 是 Johnshall 原 `Proxy` 出口。目前的日本和韩国只是示例值；未来换节点，只需更新这两个值。修改 JSON 后会自动重建配置，**无需额外策略组**。

## 只有两份 OpenAI 路由规则源

| 顺序 | 唯一来源 | 维护方式和内容 |
|---|---|---|
| 1. 自动优先 | [`rules/openai-auto.list`](rules/openai-auto.list) | GitHub Actions 每天从官方 ChatGPT Voice **目标 IP** 和多个公共 OpenAI geosite / Shadowrocket / ACL4SSR 域名文件下载、筛选、层内去重后自动生成 |
| 2. 手工兜底 | [`config/manual-openai.rules`](config/manual-openai.rules) | 独立保留你原 HY 的第一方与专属第三方主机规则；只在**手工文件内部**有确定父子域包含关系时才去重，**不和自动层去重** |
| 3. 非 OpenAI | Johnshall 原始规则 | `Proxy` 改为 `johnshall_proxy_node_name` 指定的实际节点；其他原始规则及相对顺序全部保留；未匹配 `FINAL,direct` |

在最终完整 `.conf` 中，自动层先放官方 Voice 目的 IP，再放自动域名，之后才放独立手工兜底，最后放 Johnshall 原规则。**最终仍只有一个可直接订阅的 `.conf` 文件**。不需要用户再导入两份列表。

自动域名来源：[v2fly/domain-list-community](https://github.com/v2fly/domain-list-community/blob/master/data/openai)、[MetaCubeX](https://github.com/MetaCubeX/meta-rules-dat)、[ACL4SSR](https://github.com/ACL4SSR/ACL4SSR)、[blackmatrix7](https://github.com/blackmatrix7/ios_rule_script)，以及 [OpenAI 官方 ChatGPT Voice IP](https://openai.com/chatgpt-voice.json)。**不会将 OpenAI 发往外部的“出站源 IP”错误用于客户端访问目标 IP 分流**。

### 手工规则的保留与安全边界

- `DOMAIN-SUFFIX,openai.com` 已覆盖 `api.openai.com`、`auth.openai.com`、`prism.openai.com`，因此手工内部不必重复这些子域。但它**不覆盖** `openai.com.cdn.cloudflare.net`，后者的结尾是 `cloudflare.net`。
- `DOMAIN-SUFFIX,chatgpt.com` 已覆盖 `ws.chatgpt.com`，包括 Codex 使用的 ChatGPT WebSocket 目的域名；`chatgpt.site` 为不同域，必须另留。OpenAI 官方确认 ChatGPT Sites 使用 `*.chatgpt.site` 子域。
- `DOMAIN-WILDCARD,chatgpt-async-webps-prod-*.webpubsub.azure.com` 是 ChatGPT 专用 Azure Web PubSub 主机匹配，不是 `*.azure.com` 或通用云域名。
- `openai-api.arkoselabs.com`、`openai.qualtrics.com`、`cdn.openaimerge.com` 等可明确识别的主机只使用精确 `DOMAIN`。不要无证据扩大为 `DOMAIN-SUFFIX,arkoselabs.com` 等第三方整站。
- 你 HY 原文里的 WorkOS、Stripe、Intercom、Sentry、Statsig / Feature Gates、Cloudflare 验证、Apple 检测等共享依赖仍保留为注释，不默认走 OpenAI 专用节点。**例外：`host.livekit.cloud`、`turn.livekit.cloud` 根据你对 Voice 连通性的明确优先选择，现已启用**，因此可能把其他使用 LiveKit 的应用也转到 OpenAI 出口。官方“允许访问清单”不等于“OpenAI 独占域名清单”。
- `gpt(all, udp/3478)` 会误伤其他应用的 UDP 3478。改为自动更新的官方 Voice 目的 IP，不能把“所有 UDP/3478”直接划为 OpenAI。
- **截至 2026-10，Sora 产品和 API 已停止服务**；`sora.com` 仍按你要求保留为历史兼容规则，不代表该服务仍在线。

第三方共享主机如果确需强制走 OpenAI 专用节点，先确认**具体 OpenAI 专用主机**，并将其加入 `scripts/build.py` 的 `OPENAI_SPECIFIC_HOSTS` 允许列表和手工源；仅凭 `cdn.workos.com` 之类多人共用的主机名做不到“只分 ChatGPT 的那一次请求”。

自动源使用安全的专属域名筛选；对于 `IP-ASN,20473` 或其他社区发布的宽泛服务商 IP / ASN 不强制日本，以免截走无关流量。官方 Voice JSON 只包含语音目的 IP，不能当作整个 OpenAI 的全量 IP 库。**因此不能保证“100% 所有 OpenAI 依赖都只走日本，同时所有非 OpenAI 流量绝不改变”**：共享第三方主机无法用纯域名分流同时满足这两个要求。

## 加密 DNS

- 专属 OpenAI 域名优先远端解析：OpenAI 专用节点；
- Johnshall 原 Proxy 网站由配置中的常规代理节点访问，通常由该节点远端解析；
- DIRECT 使用 `https://dns.alidns.com/dns-query#no-h3` 本地加密解析；
- 小火箭本地需要解析代理类域名时，`dns-server` 使用 Google DoH，经 Johnshall 常规代理节点；
- `proxy-dns-server`（节点服务器域名启动解析）使用阿里 DoH，避免代理依赖循环。

`#no-h3` 仅禁用 DoH 的 HTTP/3 协议升级，**不关闭 HTTPS DNS 加密**。若要指定两个代理服务器自身使用 Google DNS，需要分别配置各自的 HY 服务端，单靠客户端文件做不到。

## 每日同步与测试

Johnshall 上游约在每天 **07:04 台北时间**发布；目前每日自动上游中较晚完成的是 MetaCubeX，近几次约在 **09:09～10:26** 完成。因此本仓库 [GitHub Actions](.github/workflows/sync-upstream.yml) 设为每天 **11:30 台北时间（03:30 UTC）** 合并，预留约一小时以上缓冲。该时间为固定计划，并非根据上游完成事件动态触发；若上游或 GitHub Actions 延迟更久，本仓库下一次运行仍会重试获取。修改节点备注、手工规则或生成脚本也会触发构建；手机端需刷新配置订阅。

```bash
python -m unittest discover -s tests -v
python scripts/build.py
```

构建失败时不会提交不完整结果；成功时只提交更新的完整 `.conf`、自动列表和数据源校验信息。原 Johnshall 的 URL Rewrite、MITM 和广告规则保留。**不要直接编辑生成的 `.conf` 和自动 `.list`**，否则下次同步会覆盖。

## GitHub Actions 成功后 Telegram 推送

**Telegram 没有单独的每日定时任务**：原 Actions 每天 11:30 检查上游，但只在某次 Actions 的测试、生成和提交步骤成功后立即发一次报告。此行为适用于定时、手动、修改配置触发的 Actions。**没有上游变化也会发送检查成功、无变化。** 构建失败不会发送误导性的成功通知。

报告记录：触发来源、变化的上游、规则数量与变化量、新增和删除的自动规则示例及 Actions 运行链接。相同摘要也写入 Actions Summary。

在仓库 Settings → Secrets and variables → Actions → New repository secret 创建两条密钥：`TELEGRAM_BOT_TOKEN`（BotFather Token）以及 `TELEGRAM_CHAT_ID`（个人 Telegram Chat ID）。两者均由 GitHub Secrets 注入，不再在当前工作流里写明文 Chat ID。先向自己的机器人发送 /start，确保它可以发消息。即使是私有仓库也不要直接把 Token 或 Chat ID 写入源码。若旧 Token 曾在聊天中暴露，建议撤销旧 Token 并更换为新 Token。

**准备公开仓库时特别注意：旧提交的 Git 历史中已经出现过 Chat ID。改成 Secret 仅保护之后的提交，并不能删除历史记录。若要求 Chat ID 连历史也不可见，应使用经过清理的新公开仓库，保留现有仓库私有；不要误以为改变 Secret 就能抹除旧历史。**

未设置 Secret 时，Actions 同步正常，摘要照样生成，但 Telegram 步骤会提示未配置并跳过发送。Telegram 发送暂时失败最多重试 3 次；发送异常不影响已经成功发布的配置。

## 上游异常保护

每次与已发布的 data/sources.json 数量对比：Voice IP 下降超过 30% 或增长超过 100%，自动 OpenAI 域名下降超过 25% 或增长超过 100%，Johnshall 规则行数、原 Proxy 映射、广告拦截数量下降超过 15% 或增长超过 50% 时，拒绝本次发布；这些比例是审查阈值，不代表真实上游永远不会出现合理的大变更。

触发保护时构建失败，旧的完整 .conf 保留不变，不会发送“成功”消息。核实合法变更后再调整阈值。原有双层 OpenAI 规则结构和 Johnshall 分流架构不变。

## OpenAI 官方演示域名的补充（2026-10-12）

以下已核对 OpenAI 官方 Developer Showcase，加入独立手工规则层，并保持自动规则层不变：

- `DOMAIN-SUFFIX,openai.fm`：OpenAI 官方语音合成体验站，包含实际跳转的 `www.openai.fm`。
- `DOMAIN,chatkit.world`：官方 ChatKit 演示站，只允许完整主机。
- `DOMAIN,openai-photobooth-demo.vercel.app`：官方图像 Photobooth 演示站。
- `DOMAIN,openai-realtime-solar-system-demo.vercel.app`：官方 Realtime Solar System 演示站。

官方来源：https://developers.openai.com/showcase/openai-fm 、https://developers.openai.com/showcase/chatkit-world 、https://developers.openai.com/showcase/openai-imagegen-demo 、https://developers.openai.com/showcase/solar-system-demo 。

未引入 `DOMAIN-SUFFIX,vercel.app` 等共享平台规则。新域名只加入维护中的独立手工兜底，自动规则仍严格来自官方 Voice 目的 IP 与原四份社区规则；两层规则不会互相去重。

## 上游下载失败重试

全部六个上游下载现在采用最多两次请求（初次失败后延迟 2 秒重试 1 次），包括 HTTP/网络错误与响应截断；两次都失败则停止构建并保留上一次成功发布的 `.conf`。域名解析与规则格式校验仍会失败关闭，不会用损坏数据代替完整配置。

## 上游新增但被排除的域名审查

每次成功构建时，安全白名单继续严格筛选四份社区 OpenAI 规则源。对于未获准进入 OpenAI 自动规则的域名及域名类规则，程序会把完整排序清单保存到 data/sources.json 的 review.excluded_auto_rules 中，作为下一次构建的观察基线。

- 初次启用时先建立旧排除项基线，不把已经存在的规则误报成新增。
- 后续上游出现新的排除项，Actions 成功后原 Telegram 消息会列出新增规则、来源及数量（最多展示前 8 条），Actions Summary 展示完整新增清单。
- 本次没有新的排除项，就报告无新增，不反复提醒旧候选。
- 这些规则只用于人工审核，从未自动加入 .conf、自动列表或手工兜底。共享第三方域名不会因为出现在上游就被直接导向 OpenAI 节点。

没有新增定时任务，继续随每天 11:30、手动和配置修改触发的 GitHub Actions 成功运行后推送。

## LiveKit TURN 路由的明确例外（2026-10-12）

经过使用者明确选择，为尽量覆盖 ChatGPT Voice 相关的 TURN 连接，将 `DOMAIN-SUFFIX,host.livekit.cloud` 与 `DOMAIN-SUFFIX,turn.livekit.cloud` 同时添加到自动允许列表及独立手工兜底。它们是 LiveKit **共享云服务**，并非 OpenAI 独占；其他应用经这些子域进行的 WebRTC/TURN 流量也可能改走 OpenAI 专用节点，可能影响其他应用的延迟、出口地区或 UDP 连接质量。

LiveKit 官方网络说明：`*.host.livekit.cloud` 主要涉及 UDP/3478 TURN，`*.turn.livekit.cloud` 主要涉及 TCP/443 TURN/TLS（https://docs.livekit.io/deploy/admin/firewall/）。本项目没有新增 `DOMAIN-SUFFIX,livekit.cloud`、通用 UDP/3478 或 IP/ASN 一刀切规则。原官方 ChatGPT Voice 目标 IP、其他 OpenAI 分流与 Johnshall 剩余规则不变。

启用后应在 Shadowrocket 里测试 ChatGPT Voice 和可能使用 LiveKit 的其他实时通话软件。如果其他应用出现通话故障、延迟增大或出口误路由，可撤销这两项例外恢复原策略。

