# Shadowrocket · OpenAI 专用出口 + Johnshall 原样分流

> **2026-10-15 稳定性回退**：撤回依赖官方帮助中心网页的新增自动审批功能，恢复到 `216c431` 的同步与待审核流程。构建不再请求该网页，也不再因其 Cloudflare 验证冻结自动域名更新。官方 Voice、四份社区规则、Johnshall 和 Apple News 继续按原有七来源流程同步；白名单外的新候选仍报告后审核，不直接加入规则。Voice 范围保护、下载完整性、未知格式待审和 Apple News 内嵌校验这四项修复全部保留，节点、手工兜底及每日 11:00 排程保持原样。官方网页仅作为人工查证资料。

## V1.0 稳定基线：最高优先级与验收原则

> **第一目标：尽最大可能让所有 OpenAI、ChatGPT、Codex、语音、登录验证及相关依赖流量走你指定的 OpenAI 节点。**

此原则是本项目后续规则设计、上游更新、审查、测试和故障排查的**最高优先级**。在不改变用户明确指定的两个节点名称的前提下：

1. **覆盖优先**：官方明确使用的 OpenAI / ChatGPT / Codex 服务，以及 API、登录验证、WebSocket、语音、文件上传、静态资源等网络依赖，优先路由至 `openai_node_name` 指定节点。已确认的官方共享第三方依赖也纳入手工兜底，而不是仅因为其他产品同样使用该域名就排除。
2. **不以节点性能决定收录**：节点延迟、地区、线路质量和出口优化由用户负责，不作为取消或拒绝 OpenAI 相关分流规则的理由。
3. **保持分流边界可验证**：当官方确认的是某个精确主机，就使用精确主机；当官方明确给出通配子域或语音目的 IP 范围，再按相应范围覆盖。共享目标被纳入后，其他使用同一目标的应用也可能走 OpenAI 专用节点，这是覆盖优先所接受的副作用。没有依据时不扩大为整个供应商域名、所有 IP/ASN 或全局 UDP 端口规则。
4. **其余流量保留 Johnshall**：未被 OpenAI 专用层匹配的连接继续遵循 Johnshall 原有的 `Proxy` / `DIRECT` / `REJECT` 与最终直连规则，不新增无关策略组，不擅自改变两个实际节点名称。
5. **持续审查而非冻结域名**：定期同步官方 Voice 目的 IP 和上游域名源；上游新增却被筛选排除的候选规则报告给用户审核。OpenAI 推出新主机、修改基础设施或存在纯域名规则无法辨别的共享请求时，结合官方资料与 Shadowrocket 连接日志继续补齐。

**版本定位**：截至 2026-10-12，现有双节点架构、两层 OpenAI 规则、自动更新、异常保护、测试及成功后 Telegram 报告构成 **V1.0 稳定基线**，可以长期按此架构使用。所谓“终版”指**核心架构和上述分流优先级定版**，不表示域名清单从此不更新，更不能宣称静态规则已数学保证未来所有 OpenAI 连接 100% 命中指定节点。实际设备上的登录、Voice、Codex 和上传行为仍应以 Shadowrocket 连接记录验收。

基于 [Johnshall 上游](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever) 的完整 Shadowrocket 配置，每天同步：**尽最大可能将 OpenAI 本身及官方确认的共享网络依赖送至 OpenAI 专用节点**；其他 Johnshall 原本 `Proxy` 的流量走另一个指定节点。DIRECT / REJECT / 最后直连保留原规则。节点所在国家可随时更换，不与配置文件名和变量名绑定。

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
| 2. 手工兜底 | [`config/manual-openai.rules`](config/manual-openai.rules) | 独立保留第一方、专属第三方及官方确认的共享网络依赖规则；只在**手工文件内部**有确定父子域包含关系时才去重，**不和自动层去重** |
| 3. 非 OpenAI | Johnshall 原始规则 | `Proxy` 改为 `johnshall_proxy_node_name` 指定的实际节点；其他原始规则及相对顺序全部保留；未匹配 `FINAL,direct` |

在最终完整 `.conf` 中，自动层先放官方 Voice 目的 IP，再放自动域名，之后才放独立手工兜底，最后放 Johnshall 原规则。**最终仍只有一个可直接订阅的 `.conf` 文件**。不需要用户再导入两份列表。

自动域名来源：[v2fly/domain-list-community](https://github.com/v2fly/domain-list-community/blob/master/data/openai)、[MetaCubeX](https://github.com/MetaCubeX/meta-rules-dat)、[ACL4SSR](https://github.com/ACL4SSR/ACL4SSR)、[blackmatrix7](https://github.com/blackmatrix7/ios_rule_script)，以及 [OpenAI 官方 ChatGPT Voice IP](https://openai.com/chatgpt-voice.json)。**不会将 OpenAI 发往外部的“出站源 IP”错误用于客户端访问目标 IP 分流**。

### 手工规则的保留与安全边界

- `DOMAIN-SUFFIX,openai.com` 已覆盖 `api.openai.com`、`auth.openai.com`、`prism.openai.com`，因此手工内部不必重复这些子域。但它**不覆盖** `openai.com.cdn.cloudflare.net`，后者的结尾是 `cloudflare.net`。
- `DOMAIN-SUFFIX,chatgpt.com` 已覆盖 `ws.chatgpt.com`，包括 Codex 使用的 ChatGPT WebSocket 目的域名；`chatgpt.site` 为不同域，必须另留。OpenAI 官方确认 ChatGPT Sites 使用 `*.chatgpt.site` 子域。
- `DOMAIN-WILDCARD,chatgpt-async-webps-prod-*.webpubsub.azure.com` 是 ChatGPT 专用 Azure Web PubSub 主机匹配，不是 `*.azure.com` 或通用云域名。
- `openai-api.arkoselabs.com`、`openai.qualtrics.com`、`cdn.openaimerge.com` 等可明确识别的主机只使用精确 `DOMAIN`。不要无证据扩大为 `DOMAIN-SUFFIX,arkoselabs.com` 等第三方整站。
- **OpenAI 覆盖优先**：官方 ChatGPT 网络清单明确列出的 WorkOS、Cloudflare 验证、Intercom、SendGrid、Sentry、Apple 相关检测等共享依赖，现已按完整主机或官方通配子域纳入手工规则；Voice 所需 LiveKit 规则也继续生效。其他使用这些共享主机的应用也可能转到 OpenAI 节点。这是覆盖优先的取舍，不表示它们为 OpenAI 独占域名。
- `gpt(all, udp/3478)` 会误伤其他应用的 UDP 3478。改为自动更新的官方 Voice 目的 IP，不能把“所有 UDP/3478”直接划为 OpenAI。
- **截至 2026-10，Sora 产品和 API 已停止服务**；`sora.com` 仍按你要求保留为历史兼容规则，不代表该服务仍在线。

官方 ChatGPT 指南明确列出的共享依赖已经作为白名单例外强制走 OpenAI 专用节点，不再要求其是 OpenAI 独占域名。其他社区新增但未获官方确认的第三方主机仍需人工审核；单靠域名分流无法区分同一共享域名上的 ChatGPT 请求与其他应用请求。

自动源使用安全的专属域名筛选；对于 `IP-ASN,20473` 或其他社区发布的宽泛服务商 IP / ASN 不强制日本，以免截走无关流量。官方 Voice JSON 只包含语音目的 IP，不能当作整个 OpenAI 的全量 IP 库。**因此不能保证“100% 所有 OpenAI 依赖都只走日本，同时所有非 OpenAI 流量绝不改变”**：共享第三方主机无法用纯域名分流同时满足这两个要求。

## 加密 DNS

- 专属 OpenAI 域名优先远端解析：OpenAI 专用节点；
- Johnshall 原 Proxy 网站由配置中的常规代理节点访问，通常由该节点远端解析；
- DIRECT 使用 `https://dns.alidns.com/dns-query#no-h3` 本地加密解析；
- `fallback-dns-server` 使用阿里 AliDNS 与腾讯 DNSPod 两个加密 DoH 地址，按 Shadowrocket 支持的逗号分隔语法提供备用解析；两者均附加 `#no-h3`，并保持 `dns-fallback-system = false`，不回退系统 DNS；
- 小火箭本地需要解析代理类域名时，`dns-server` 使用 Google DoH，经 Johnshall 常规代理节点；
- `proxy-dns-server`（节点服务器域名启动解析）使用阿里 DoH，避免代理依赖循环。

`#no-h3` 仅禁用 DoH 的 HTTP/3 协议升级，**不关闭 HTTPS DNS 加密**。若要指定两个代理服务器自身使用 Google DNS，需要分别配置各自的 HY 服务端，单靠客户端文件做不到。

## 每日同步与测试

Johnshall 上游约在每天 **07:04 台北时间**发布；截至 2026-10-12 核查，规律性自动来源中较晚完成的是 MetaCubeX，近几次约在 **09:09～10:27** 完成，最近观察到的最晚一次为 **2026-10-06 10:26:49（台北时间）**。因此本仓库 [GitHub Actions](.github/workflows/sync-upstream.yml) 改为每天 **11:00 台北时间（03:00 UTC）** 合并，比该次最晚完成时间晚约 **33 分钟**。该时间为固定计划，并非根据上游完成事件动态触发；若上游或 GitHub Actions 延迟更久，可能无法在当天获取最新版本，但下一次运行仍会重新获取。修改节点备注、手工规则或生成脚本也会触发构建；手机端需刷新配置订阅。

```bash
python -m unittest discover -s tests -v
python scripts/build.py
```

构建失败时不会提交不完整结果；成功时提交更新的完整 `.conf`、自动列表、数据源校验信息和审核清单。原 Johnshall 的 URL Rewrite、MITM 和广告规则保留。**不要直接编辑生成的 `.conf` 和自动 `.list`**，否则下次同步会覆盖。

## GitHub Actions 成功后 Telegram 推送

**Telegram 没有单独的每日定时任务**：原 Actions 每天 11:00 检查上游，但只在某次 Actions 的测试、生成和提交步骤成功后立即发一次报告。此行为适用于定时、手动、修改配置触发的 Actions。**没有上游变化也会发送检查成功、无变化。** 构建失败不会发送误导性的成功通知。

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

全部七个上游下载（含构建时内嵌的 Apple News 规则）采用最多两次请求：初次失败后延迟 2 秒重试 1 次。响应提供 `Content-Length` 时，必须与实际接收字节数一致；分块传输不完整、HTTP/网络错误及大小异常同样触发重试。两次都失败则停止构建并保留上一次成功发布的 `.conf`。Johnshall 文件还必须保留预期结尾标记、非空 URL Rewrite 及 MITM hostname，避免末尾缺失却仍满足规则条数检查。

## 人工不通过记录与定期复审

继续使用现有人工审核：固定允许规则照常更新，白名单之外的候选不自动放行。无需 AI API，也不抓取带 Cloudflare 验证的帮助中心网页。完整来源记录仍保留在 `data/sources.json` 的 `review.excluded_auto_rules`；[人工审核清单](data/review-queue.md) 展示每条候选的来源、状态、上次审核和下次复审日期。

[config/review-decisions.json](config/review-decisions.json) 是人工不通过记录表，只影响提醒，不是第三份分流规则或额外 IP 可信清单。新建时为空，旧排除项不冒充人工已审核结果。字段如下：

| 字段 | 含义 |
|---|---|
| `default_review_months` | 默认复审间隔，初始 6 个日历月，可改为 12 |
| `reminder_interval_days` | 已到期但未处理时，两次成功提醒之间的间隔，初始 7 天 |
| `rejected_rules[].rule` | 完整规则，精确匹配；拒绝父域规则不自动拒绝子域或不同写法 |
| `reason` | 人工不通过的原因 |
| `reviewed_at` | 上次人工审核日期，格式 `YYYY-MM-DD`，按台北日期计算 |
| `review_after_months` | 可选的单条复审间隔；未填写时使用全局默认 |

例如，人工确实审核不通过后，可以加入下面这样的记录（仅为填写示例，未预置到实际记录表）：

```json
{
  "rule": "DOMAIN-SUFFIX,algolia.net",
  "reason": "暂缺可核实的 OpenAI 使用依据，后续重新核对",
  "reviewed_at": "2026-10-15",
  "review_after_months": 6
}
```

### 记录不通过结果或续期

在 GitHub **Actions → Sync Johnshall and OpenAI rules → Run workflow**：

1. `reject_rule` 填审核清单中的完整规则；留空时只执行原同步。
2. `reject_reason` 填本次不通过原因。
3. `review_months` 可填 `6` 或 `12`；留空时保留该条已有设置，或者使用全局默认。

程序自动填写当天审核日期；同一规则更新原记录，不重复新增。**新登记的规则必须与当前已发布的 `data/review-queue.md` / `data/sources.json` 待审核基线完全一致**（包括规则类型及参数），不接受拼写错误或未出现过的规则；新上游候选请先完成一次正常同步。已经记录过的规则即使后来从上游消失，仍可更新审核日期。同步成功后保存至仓库。如本次同步失败，人工记录尚未提交，需要重新运行。也可以直接编辑 JSON，只更新对应 `reviewed_at` 并提交，下一次复审日期就会重新计算。全局默认月数的变更影响所有未单独指定间隔的记录。

本地操作等价于：

```bash
python scripts/review_queue.py --rule 'DOMAIN-SUFFIX,algolia.net' --reason '仍需更多依据' --months 12
```

审核通过时，按原维护流程修改允许规则或手工规则，并删除对应的不通过记录；**仅删除不通过记录、收到提醒或到期，都不会自动放行**。已有允许规则的审批要求仍然有效。

### 提醒与更新的行为

- 未到复审日期的拒绝项跳过提醒。到期当天或之后第一次成功同步时，原 Telegram 消息会列出复审项、上次审核日期和到期日期；Actions Summary 展示完整清单和此前原因。月底按实际月末计算，例如 8 月 31 日的半年后为次年 2 月末。
- 到期还未处理时，默认每 7 天再提醒一次；更新审核日期后重新进入半年或一年周期。候选从上游消失则暂不提醒，人工记录保留；以后再次出现仍按原决定和日期处理。
- 新的未审核项随原通知报告；发送失败时保持待送达，下一次成功同步重试。已送达的新候选不每天重复报“新增”，仍保留在审核清单中。
- 只有 Telegram 返回成功才记录送达日期；发送失败、缺少 Secret 都不会提前消耗提醒。送达状态保存在 `data/review-notifications.json`，通知后另行提交；若发送成功但回执提交失败，下次可能重复提醒，避免静默漏报。
- 人工审核记录文件变更由 `data/sources.json` 中的审查指纹识别，Telegram 会单独提示「人工审核记录文件已变更，分流配置无变化」，不会再错误地显示「检查成功，无变化」；初次建立审查指纹不会误报成新审核决定。
- 初次启用沿用已有排除项基线，不把旧候选报成新增。实际已被自动或手工 OpenAI 规则覆盖的候选免重复审核，但不会删除独立手工兜底规则。
- **OpenAI 专用层的 IP 只采用官方 `https://openai.com/chatgpt-voice.json` 的语音目的地址。** 社区 IP/ASN 只保留来源记录，不进入人工域名复审提醒或任何新增 OpenAI IP 列表。官方数据仍执行格式、范围和覆盖变化检查；它是 Voice 目的 IP 来源，不代替其他 OpenAI 业务的域名规则，也不改变 Johnshall 原有 IP 规则。
- 未识别的 `regexp:`、`include:`、`keyword:` 等非 IP 规则继续进入人工审核，不静默丢弃。审核 JSON 或通知状态格式错误会在报告中警告并暂停相应免提醒，不阻塞正常分流更新；上游内容本身的完整性与范围校验仍照常阻止异常发布。

没有新增定时任务，继续随每天 11:00、手动和配置修改触发的 GitHub Actions 成功运行后推送。

## 2026-10-15 审查修复与发布保护

**Voice 地址覆盖范围**：除了原有条数变化检查，还分别统计 IPv4、IPv6 网段并集覆盖的地址数，重叠地址只计一次。与上一次发布的 `rules/openai-auto.list` 比较，覆盖地址数下降超过 30% 或增长超过 100% 时停止发布；首次增加原来没有的地址族也需要审核。拒绝 IPv4 中宽于 `/24`、IPv6 中宽于 `/48` 的网段，以及地址族不一致、带主机位的非规范 CIDR，避免把单 IP 的错误掩码静默扩成大网段。这些是审查门槛，并非断言官方不可能合法调整网段。

触发保护时，应先核对官方原始 Voice JSON、上次发布快照及具体地址差异；确认合法后，在受审查的提交中调整相应阈值或更新已核验的基线，再重新构建。不要通过删除基线、关闭校验或把所有未知条目自动放行来恢复更新。

**Apple News 远程依赖**：Johnshall 中原来的 Apple News `RULE-SET` 已改为构建时下载、核对 `# TOTAL` 与实际条数、校验规则格式，再于原位置内嵌。原策略继续使用 Johnshall 指定节点，原有规则顺序保持不变；手机仅刷新完整 `.conf` 即可，不再单独拉取该规则集。原始快照保存为 `rules/johnshall-apple-news.list`，URL、SHA-256、条数写入 `data/sources.json`，源变化进入现有 Actions / Telegram 摘要。这不是新增的 OpenAI 规则层。

内嵌规则源条数比上次下降超过 15% 或增长超过 50% 时停止发布；规则自带策略、嵌套远程引用、未知新 `RULE-SET` / `DOMAIN-SET`、缺失或不一致的条数声明也会阻止发布，等待审核。下载和全部校验成功前，不修改已发布文件。

本次修复不改变两个节点变量、OpenAI 自动与手工两层优先级、每日 11:00 排程及成功后通知机制。GitHub 定时触发仍可能延迟；手机端 DNS、Voice 和连接命中需另以实际连接记录验收。

## LiveKit TURN 路由的明确例外（2026-10-12）

经过使用者明确选择，为尽量覆盖 ChatGPT Voice 相关的 TURN 连接，将 `DOMAIN-SUFFIX,host.livekit.cloud` 与 `DOMAIN-SUFFIX,turn.livekit.cloud` 同时添加到自动允许列表及独立手工兜底。它们是 LiveKit **共享云服务**，并非 OpenAI 独占；其他应用经这些子域进行的 WebRTC/TURN 流量也可能改走 OpenAI 专用节点，可能影响其他应用的延迟、出口地区或 UDP 连接质量。

LiveKit 官方网络说明：`*.host.livekit.cloud` 主要涉及 UDP/3478 TURN，`*.turn.livekit.cloud` 主要涉及 TCP/443 TURN/TLS（https://docs.livekit.io/deploy/admin/firewall/）。本项目没有新增 `DOMAIN-SUFFIX,livekit.cloud`、通用 UDP/3478 或 IP/ASN 一刀切规则。原官方 ChatGPT Voice 目标 IP、其他 OpenAI 分流与 Johnshall 剩余规则不变。

启用后应在 Shadowrocket 里测试 ChatGPT Voice 和可能使用 LiveKit 的其他实时通话软件。如果发现其他应用也经这两个共享子域使用 LiveKit，这属于覆盖优先时已接受的分流范围；仅在证实业务功能受到影响且需要重新界定覆盖范围时才按连接日志复核，不因延迟或节点地区不同直接取消 OpenAI 相关规则。


## OpenAI 连接覆盖优先：官方网络依赖（2026-10-12）

目标是让 OpenAI 网页、iOS、Codex、语音、登录和文件相关连接尽可能通过 openai_node_name 指定的节点；不因节点延迟或共享第三方域名而排除官方明确要求的访问目标。核对来源：

https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps

已将官方所列的共享第三方目标加入 config/manual-openai.rules，精确主机保持 DOMAIN，官方通配子域（ct.sendgrid.net、intercom.io、intercomcdn.com）使用 DOMAIN-SUFFIX。它们不属于 OpenAI 独占服务，可能连带让其他网站的对应主机流量走 OpenAI 出口。

包含 WorkOS 身份验证组件、Cloudflare 验证、Intercom 支持资源、SendGrid、Stripe 脚本、Sentry 与 Datadog 监控、Apple 检测。自动上游仍只采纳 OpenAI 专属域名，官方共享依赖由独立手工兜底承接；Voice 官方目的 IP、原 Johnshall 规则和两节点变量都未改变。

安全边界：不引入 DOMAIN-SUFFIX,workos.com、DOMAIN-SUFFIX,stripe.com、DOMAIN-SUFFIX,cloudflare.com 等未获官方明确要求的整个供应商域名，也不使用 DOMAIN-KEYWORD,openai。静态域名和官方 Voice 目的 IP 不可能预知所有未来服务或隐藏直连目标，因此无法数学保证 100% 的 OpenAI 流量；新增目标应结合已建立的待审核规则报告及 Shadowrocket 连接日志查证。
