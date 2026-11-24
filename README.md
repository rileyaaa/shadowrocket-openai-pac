# Shadowrocket + v2rayN · OpenAI / Gemini / Claude 双订阅自动维护

> **2026-10-15 稳定性回退**：撤回依赖官方帮助中心网页的新增自动审批功能，恢复到 `216c431` 的同步与待审核流程。构建不再请求该网页，也不再因其 Cloudflare 验证冻结自动域名更新。官方 Voice、四份社区规则、Johnshall 和 Apple News 继续按原有七来源流程同步；白名单外的新候选仍报告后审核，不直接加入规则。Voice 范围保护、下载完整性、未知格式待审和 Apple News 内嵌校验这四项修复全部保留，节点、手工兜底及每日 11:00 排程保持原样。官方网页仅作为人工查证资料。

## 最高维护原则（2026-11-24 更新）：精准分流、业务完整、最小副作用

> **该走目标代理的业务不漏；不该进入专用层的流量不误伤；更新不破坏其他正常业务。** 三者并重，不以域名数量或全覆盖为唯一目标。本节优先于下方历史记录中的旧“覆盖优先”表述。

1. **证据与最小匹配范围**：经过核实的第一方专属命名空间可以使用 DOMAIN-SUFFIX，以覆盖合理新增的子域；共享供应商仅批准必要的精确主机或可证明的专属子域/模式，不凭社区标签、名称相似、官方防火墙允许清单就扩大代理。已确认的官方 Voice 目的 IP 按原安全保护维护，不扩大到社区 ASN 或全局端口。
2. **完整功能**：聊天、API、登录、上传、WebSocket、Voice 及开发工具的已审核核心入口应保有独立覆盖基线；Google AI Studio、Gemini API/Code Assist、NotebookLM 等已有入口不随社区列表偶然消失。通用 Google 登录、支付、CDN 等共享请求仍优先维持 Johnshall，只有确有必要且已审查副作用的例外才调整。
3. **非目标业务保持原分流**：Shadowrocket 保持双节点及原 Johnshall DIRECT/REJECT/Proxy/FINAL；v2rayN 保持既定本地保护、广告优先与 BitBrowser 专属进程规则。发布检查同时验证目标域名、实际专用层规则集合和普通业务反向隔离；不可仅凭相同 proxy 动作或规则数量判定正确。
4. **共享依赖双向复审**：现有历史批准不自动撤销或扩大。已批准共享依赖独立登记于 config/approved-dependency-review.json；reviewed_at 为历史或有证据的实际复审日期，null 表示尚需按新原则复核。默认半年复审，未处理每 30 天提醒；Telegram 失败或回执未提交则下次重试。到期仅提醒，不直接改路由。新批准或收窄时同步维护证据、范围、影响与测试。
5. **验收边界**：同一共享主机上的两个业务请求可能无法通过域名/IP 区分；静态测试不等于真实客户端、DNS、UDP、进程捕获和 MITM 测试。任何取舍须明确记录并尽可能以实际日志验证。不擅自调整节点、同步排程、广告优先级或现有订阅地址。

原 V1.0 双节点和独立自动/手工兜底架构继续使用。历史审核决策保留，后续以本节为准。基于 [Johnshall 上游](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever) 每日同步。

## 当前仅维护两份客户端订阅（2026-11-23 起）

每天台北时间 **11:00**，一个 GitHub Actions 工作流独立生成、验证并按需一次推送以下两份文件：

| 客户端 | 唯一正式订阅 | 路由方式 |
|---|---|---|
| Shadowrocket | [`Shadowrocket_Johnshall_AI.conf`](Shadowrocket_Johnshall_AI.conf) | OpenAI / Gemini / Claude → `Hinet🇹🇼台湾`；Johnshall Proxy → `Altare🇸🇬新加坡` |
| v2rayN | [`v2rayN_Johnshall_AI.json`](v2rayN_Johnshall_AI.json) | 三家 AI 与 BitBrowser → `proxy`，**不绑定具体节点** |

Shadowrocket Raw 订阅：

```text
https://raw.githubusercontent.com/rileyaaa/shadowrocket-openai-pac/main/Shadowrocket_Johnshall_AI.conf
```

v2rayN Raw 订阅：

```text
https://raw.githubusercontent.com/rileyaaa/shadowrocket-openai-pac/main/v2rayN_Johnshall_AI.json
```

**旧版已停用并删除**：原先单独 OpenAI 的小火箭配置和旧文件名的 v2rayN JSON 均不再更新。客户端必须换到以上地址；单纯刷新旧地址不能自动跳转。

`scripts/build.py` 与 `scripts/notify_telegram.py` 保留为验证过的解析/发送基础库，但每日工作流不再运行旧订阅生成入口。OpenAI Voice 覆盖保护与来源 SHA-256 继续保留独立基线；社区候选审核、半年复审及 Telegram 提醒回执合并两个客户端的有效报告；`rules/openai-auto.list`、`data/sources.json`、`data/review-queue.md` 为基线和审计资料，**不是第三份客户端订阅**。

## 原 OpenAI 分流设计与历史决策

以下保留最初 OpenAI 审查边界、保护策略和故障处理的历史依据；客户端文件、每日执行入口及安装操作均以上方最新「两份订阅」为准。

请先在小火箭导入两个实际代理节点，路由模式选「配置」。本仓库不存储任何代理凭据。两个节点的完整备注名称只在 [`config/user-settings.json`](config/user-settings.json) 中维护：

```json
{"openai_node_name":"Hinet🇹🇼台湾","johnshall_proxy_node_name":"Altare🇸🇬新加坡"}
```

两个字段表示**分流用途**，不是国家：`openai_node_name` 是 OpenAI 专用出口，`johnshall_proxy_node_name` 是 Johnshall 原 `Proxy` 出口。目前的台湾 AI 节点和新加坡是已设置的两个节点；未来换节点，只需更新这两个值。修改 JSON 后会自动重建配置，**无需额外策略组**。

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
- **Codex 反馈端点审核（2026-10-21）**：OpenAI 官方 [Codex 源码](https://github.com/openai/codex/blob/main/codex-rs/feedback/src/lib.rs) 的反馈上传 Sentry DSN 明确指向 `o33249.ingest.us.sentry.io`。已审核通过其精确主机规则 `DOMAIN,o33249.ingest.us.sentry.io`，放在独立手工兜底层；不会批准整个 `sentry.io` 或 `ingest.us.sentry.io` 后缀。该地址用于反馈/诊断上传，不代表聊天 API 必须连接它。
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
python scripts/build_ai_shadowrocket.py
python scripts/build_v2rayn.py
```

构建失败时不会提交不完整结果；成功时提交更新的完整 `.conf`、自动列表、数据源校验信息和审核清单。原 Johnshall 的 URL Rewrite、MITM 和广告规则保留。**不要直接编辑生成的 `.conf` 和自动 `.list`**，否则下次同步会覆盖。

## GitHub Actions 成功后 Telegram 推送

**Telegram 没有单独的每日定时任务**：同一 GitHub Actions 每天计划在台北时间 11:00 检查上游。只要通知密钥可用，构建成功、部分成功或失败都会尝试发送**一条包含实际状态**的报告；无变化也会报告。Telegram 发送成功不等于两份订阅均成功更新。构建失败时只发布通过校验的客户端结果，失败的一端保留上一版。

报告记录：触发来源、变化的上游、规则数量与变化量、新增和删除的自动规则示例及 Actions 运行链接。相同摘要也写入 Actions Summary。

在仓库 Settings → Secrets and variables → Actions → New repository secret 创建两条密钥：`TELEGRAM_BOT_TOKEN`（BotFather Token）以及 `TELEGRAM_CHAT_ID`（个人 Telegram Chat ID）。两者均由 GitHub Secrets 注入，不再在当前工作流里写明文 Chat ID。先向自己的机器人发送 /start，确保它可以发消息。即使是私有仓库也不要直接把 Token 或 Chat ID 写入源码。若旧 Token 曾在聊天中暴露，建议撤销旧 Token 并更换为新 Token。

**准备公开仓库时特别注意：旧提交的 Git 历史中已经出现过 Chat ID。改成 Secret 仅保护之后的提交，并不能删除历史记录。若要求 Chat ID 连历史也不可见，应使用经过清理的新公开仓库，保留现有仓库私有；不要误以为改变 Secret 就能抹除旧历史。**

未设置 Secret 时，构建与已完成的发布不受影响，但 Telegram 通知步骤会标记失败（非静默跳过），Actions 总体状态可能显示失败。Telegram 发送暂时失败最多重试 3 次；发送异常不撤回已经发布成功的配置。

## 发布状态与有效覆盖校验

- 已发布的 Shadowrocket、v2rayN 状态采用明确的 v2 格式；已有且完整的 v1 快照可在下一次成功更新时升级。缺少成品、辅助状态、Voice 记录或 SHA-256 时必须停止受影响客户端的发布，不能当作首次初始化。
- OpenAI Voice 重合度按 IPv4/IPv6 实际目的地址区间比较，而不是 CIDR 文本；等价前缀拆分不会误判为新增目的地址。官方网络仍须通过原有规模、安全范围校验。
- Johnshall 的有效代理与广告规则分别做语义校验，拒绝规则大面积重复或新增无法安全解析的活动类型；不会为了去重而修改原始规则顺序。
- 比特浏览器报告中的正式域名数量是**实际发布的 approved（官方 + 用户确认）条数**；未经核实的候选仍记录，但不提升代理规则。额外进程路径只接受 BitBrowser 专属程序，不自动纳入公共 node.exe / chrome.exe。
- 工作流从实际 main 最新版本开始构建，发布前两次检查远端 main；若有并发更新则基于新版本最多完整重建一次，不强推、不合并旧成品。推送后若 GitHub main 恰好被其他提交推进，会先获取远端历史再确认本次发布可达；如果无法验证，通知应区分「推送成功但远端待核对」与「推送失败」。

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
| `reminder_interval_days` | 已到期但未处理时，两次成功提醒之间的间隔，默认 30 天 |
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

在 GitHub **Actions → Sync Johnshall, OpenAI, Gemini, Claude and v2rayN rules → Run workflow**：

1. `reject_rule` 填审核清单中的完整规则；留空时只执行原同步。
2. `reject_reason` 填本次不通过原因。
3. `review_months` 可填 `6` 或 `12`；留空时保留该条已有设置，或者使用全局默认。

程序自动填写当天审核日期；同一规则更新原记录，不重复新增。**新登记的规则必须与当前已发布的 `data/review-queue.md` / `data/sources.json` 待审核基线完全一致**（包括规则类型及参数），不接受拼写错误或未出现过的规则；新上游候选请先完成一次正常同步。已经记录过的规则即使后来从上游消失，仍可更新审核日期。至少一端通过发布验证后，人工记录才随有效产物保存至仓库。若两端均未通过，保留远端已有记录，需要重新运行。新登记不得与已经批准的共用规则完整覆盖范围冲突；社区 IP/ASN 只留档，不登记为新增域名拒绝项。v2rayN 专属例外不等于共用批准。也可以直接编辑 JSON，只更新对应 `reviewed_at` 并提交，下一次复审日期就会重新计算。全局默认月数的变更影响所有未单独指定间隔的记录。

本地操作等价于：

```bash
python scripts/review_queue.py --rule 'DOMAIN-SUFFIX,algolia.net' --reason '仍需更多依据' --months 12
```

审核通过时，按原维护流程修改允许规则或手工规则，并删除对应的不通过记录；**仅删除不通过记录、收到提醒或到期，都不会自动放行**。已有允许规则的审批要求仍然有效。

### 提醒与更新的行为

- 未到复审日期的拒绝项跳过提醒。到期当天或之后第一次成功同步时，原 Telegram 消息会列出复审项、上次审核日期和到期日期；Actions Summary 展示完整清单和此前原因。月底按实际月末计算，例如 8 月 31 日的半年后为次年 2 月末。
- 到期还未处理时，默认每 30 天再提醒一次；更新审核日期后重新进入半年或一年周期。候选从上游消失则暂不提醒，人工记录保留；以后再次出现仍按原决定和日期处理。
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

**2026-10-28 官方 Voice 单 IP 扩容的特批**：上次成功发布的 23 条 IPv4 /32 地址继续存在，官方 `chatgpt-voice.json`（生成时间 2026-10-27T22:28:21.782457+00:00）新增 379 条，达到 402 条。为了不让本次合规扩容持续阻断全部同步，在 `config/reviewed-voice-expansion.json` 固定本次官方原始 JSON 的 SHA-256、新旧官方源指纹、生成时间及精确计数，允许仅这一次经过核实的 **23 → 402 个 IPv4 /32** 变更。批准时还强制要求所有旧 IP 都保留、所有新 IP 都是单个 /32、不能引入 IPv6 或任何较宽网段。只有完整验证通过才临时跳过本次 Voice 条数增长保护；其余 Johnshall、域名、Apple News 的保护全部照常生效。同步成功后新基线会自动成为 402 条，以后的未知大幅扩容、新地址族、宽网段仍会被正常拦截。特批文件不能用于任意 JSON 或单纯放大阈值。

**2026-10-28 Johnshall 广告规则下降的特批**：经核查，官方 [Johnshall release](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever/tree/release) 夜间构建保留了完整配置区段、结束标记和 30,249 条 Proxy 规则，但广告 REJECT 规则从 60,999 条减少到 50,442 条（对比移除 11,612 条、加入 1,055 条）。`config/reviewed-johnshall-ad-decrease.json` 将本次审查绑定到上次成功发布的原始 SHA-256、这次官方 Git blob ID、构建时间、精确 REJECT 条数和 Proxy 条数。仅该 Git 文件可跳过这一次广告条数下降限制；其他 Johnshall 文件、其他来源、未来更大下降均保留原保护。更新采用上游实际规则，不会私自恢复上游已移除的广告域名。

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

---

## v2rayN · Johnshall + OpenAI + BitBrowser

本节为**独立新增**的 Windows v2rayN 路由订阅；不改动原 Shadowrocket 双节点、构建脚本和订阅。

### v2rayN 路由订阅

```text
https://raw.githubusercontent.com/rileyaaa/shadowrocket-openai-pac/main/v2rayN_Johnshall_AI.json
```

导入：Windows v2rayN → 设置 → 路由设置 → 新建规则集 → 别名 `Johnshall + OpenAI + BitBrowser` → 可选地址（Url）填入上述 Raw URL → 从订阅 Url 中导入规则 → 确认 → 保存并选为活动路由；选择您自己的代理节点。此文件是 **v2rayN 原生路由规则数组**，不是 PAC、Clash YAML、节点订阅或完整 Xray/sing-box 配置。`proxy`、`direct`、`block` 是路由动作，不携带任何服务器账号密码或节点名字；所有命中 `proxy` 的连接使用 v2rayN 当前选定的节点，最终未匹配流量 `direct`。**GitHub 每日更新并不保证客户端自动重新获取**；需依客户端版本与设置手动或自动重新导入。

### 独立构建和每日维护

- 原 `scripts/build.py` 和 `scripts/notify_telegram.py` 保持不变，作为解析及发送基础函数库；**不再执行旧配置生成入口**。OpenAI Voice 基线由 Shadowrocket 建置器维护；OpenAI 审核候选与提醒回执由两个通过校验的客户端报告合并维护。
- 新 `scripts/build_v2rayn.py` 独立下载 Johnshall、四份 OpenAI 社区域名源、官方 ChatGPT Voice IP 与 Apple News 内嵌规则集，**不读取已生成 `.conf` 来转换**；读取原项目审核通过的 `config/manual-openai.rules` 与仅用于 v2rayN 的用户显式例外；转换可识别的完整 Johnshall 分流，不以少量 `geosite:cn` 取代源规则。
- 每天台北时间 **11:00（UTC 03:00）** 使用**同一个** `.github/workflows/sync-upstream.yml` 调度两份独立客户端订阅，分别验证，成功的产物合并为**一次 Git 推送**；未改变时不提交。单个构建失败不发布其失败产物，也不阻止另一套成功产物发布。各构建的状态由独立状态文件记录，失败不会伪装成功。
- `scripts/notify_combined.py` 统一复用**未修改**的旧 Telegram API 发送函数和人工审核送达确认逻辑，向原 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID` 发送**一条综合报告**；只有成功发送后才更新审核提醒送达记录，并由工作流单独持久化。Git 推送失败与 Telegram 失败在报告/Actions 状态中独立体现，后者不会撤销已发布文件。
- v2rayN 建置仅写自己的 `data/v2rayn-sources.json`；Shadowrocket AI 建置继续维护 `data/sources.json`、`rules/openai-auto.list` 等 OpenAI 审核和 Voice 基线。下载、规模、来源结构、Voice CIDR、广告数量、转换成功率与独立基线全部校验后才以原子方式更新 JSON。

手动独立运行：

```bash
python scripts/build_v2rayn.py --report-file /tmp/v2rayn-report.json
python -m unittest discover -s tests -p 'test_v2rayn.py' -v
```

### 规则优先级与语义差异

1. 回环 / 私网地址直连；2. Johnshall 原广告、追踪、恶意域名拦截；3. 专用 BitBrowser 进程；4. 用户指定的 BitBrowser 服务与 IP 检测域名；5. 官方 Voice 目的 IP、已审核 OpenAI 和 v2rayN 显式用户例外；6. Johnshall 原始可转换规则，按原顺序首次匹配；7. 最终 direct。

原 `REJECT` / `REJECT-DROP` / `REJECT-NO-DROP` 在 v2rayN 中只能统一表示 `block`，不能复制 Shadowrocket 各种拒绝时的网络行为；原 `no-resolve` 不是通用 Xray 规则字段，DNS 解析策略还需要客户端设置配合。Johnshall **URL Rewrite、MITM 不是路由规则，不会在 v2rayN 自动实现**；这些功能仍以原 Shadowrocket 为准。广告拦截被显式提至进程强制代理之前，故该处相对于 Johnshall 原始跨动作优先级属于有意调整。`DOMAIN-WILDCARD` 使用锚定正则映射，必须对实际目标版本测试。发布前另行扫描已审核 AI/BitBrowser 域名和 Voice IP 与前置拦截规则的可证明交集，仅在报告中提示，不改变用户既定优先级；不透明 geosite/geoip 和任意正则的完整交集仍需实机验证。任何未知 / 不支持的 Johnshall 类型及未审核外部 RULE-SET 都会**阻止 v2rayN 发布**，并保留旧版；不悄悄丢弃。

本项目的 OpenAI 社区来源继续执行原审核逻辑，未知第三方不会从社区列表自动放行。`config/v2rayn/openai-extra.rules` 是本次用户**明确指定**的 v2rayN-only 扩展，其中包含共享的 Statsig、featuregates 等广泛后缀，可能会代理其他应用流量；这些条目**不会改变原 Shadowrocket 审核记录或原规则**。

### BitBrowser：域名、进程、TUN 与检测方法

`data/bitbrowser_domains.txt` 保留官方确认的 `bitbrowser.cn`、`bitbrowser.net`、`bitbrowser.ru`，以及原先明确指定的 IP/指纹检测服务域名。`bitbrowser.com` 目前是独立浏览器隐私检测网站，不在比特指纹浏览器官方域名清单，已从专用域名规则移除；这不影响 `BitBrowser.exe` 的进程代理。其余检测域名仍是用户指定而非官方域名，可能也影响其他软件访问这些检测网站。

- 一般**系统代理模式**：只捕获应用主动使用系统代理的流量，不能保证所有浏览器窗口、UDP/WebRTC 都走 v2rayN。
- Windows **TUN 模式**：可按 v2rayN 的进程字段分流。`config/v2rayn/verified-processes.txt` 初始按第三方实务指南加入有证据的专用子进程 `BitBrowser.exe`，**不使用通用 `chrome.exe`、`msedge.exe`、`firefox.exe`**。不同 BitBrowser 版本可能有不同主程序名、子进程或安装路径。实际使用时打开任务管理器“详细信息”及进程命令行/可执行路径，确认属于 BitBrowser 后才将新的**完整专用路径**加入该文本文件、重新构建并重新导入。单凭 `BitBrowser.exe` 不保证覆盖整个应用。进程规则是否生效还取决于 v2rayN 版本、Xray/sing-box 内核、TUN 开关及进程识别支持。
- BitBrowser **内置独立代理**：如果已配置 SOCKS/HTTP 代理，浏览器可能绕过系统代理或形成双层代理；不要在 TUN 下将核心自身的出口再导回本机代理。保留 `localhost`、`127.0.0.1`、`::1` 及必要私网 Local API 访问，确保本地 `/health`、`/browser/open` 等 API 可用。
- 在实际 Windows 主机上打开 v2rayN TUN 日志，检查 BitBrowser 主程序、专用子进程及普通 Chrome 的匹配路径：BitBrowser 访问 `bitbrowser.cn` 和国内网页应显示 `proxy`，普通 Chrome 访问国内网页仍按 Johnshall；已知广告应 `block`、localhost 应 `direct`。用浏览器查看出口 IPv4/IPv6、DNS 解析（DNS 泄漏测试）、WebRTC 公网候选地址，以及 UDP/QUIC 行为；同时核对 BitBrowser 内置代理出口，避免与 TUN 重复。无 Windows + TUN 实测前，不能声称全流量百分之百覆盖。

官方 v2rayN 格式资料：[自定义路由规则说明](https://github.com/2dust/v2rayN/wiki/Description-of-custom-routing-rules)；BitBrowser 官方域名公告：[官方通知](https://www.bitbrowser.cn/blog/_gftz_btllqyhqzy__)；专用 `BitBrowser.exe` 子进程的社区资料：[指纹浏览器执行文件](https://doc.tkrmw.com/matrix/bitbrowser.html)。

---

## Gemini + Claude 每日自动维护（新增）

现只保留一份 Shadowrocket AI 订阅，覆盖 OpenAI、Gemini、Claude，三者使用 `config/user-settings.json` 中的 `openai_node_name`（当前 `Hinet🇹🇼台湾`）；Johnshall 普通 Proxy 仍使用 `johnshall_proxy_node_name`（当前 `Altare🇸🇬新加坡`）。旧 `scripts/build.py` 的共用函数不变，但不再执行其旧订阅发布入口。

**Shadowrocket 全 AI 配置：**

```text
https://raw.githubusercontent.com/rileyaaa/shadowrocket-openai-pac/main/Shadowrocket_Johnshall_AI.conf
```

旧 OpenAI 专用订阅已停止维护并删除；要让 Gemini / Claude 也走台湾 AI 节点，Shadowrocket 请使用上方唯一的全 AI 配置地址。

**v2rayN 完整路由订阅（文件已更名，必须更新地址）：**

```text
https://raw.githubusercontent.com/rileyaaa/shadowrocket-openai-pac/main/v2rayN_Johnshall_AI.json
```

v2rayN 没有绑定节点。OpenAI / Gemini / Claude / BitBrowser 命中 `proxy`，由 v2rayN 当前活动节点决定出口；`direct` 和 `block` 按原分流语义处理。需要重新从 URL 导入或按客户端能力刷新已有订阅，GitHub 每日更新不代表客户端自动刷新。

### 来源和审核边界

每天台北时间 **11:00（03:00 UTC）**，现有单一 GitHub Actions 排程独立运行：

- Shadowrocket 全 AI：`scripts/build_ai_shadowrocket.py`，重新独立抓取原七来源、维护原 OpenAI 审核/Voice 基线与提醒，并叠加 Gemini / Claude 独立审核层。
- v2rayN：`scripts/build_v2rayn.py`，独立重抓七来源与四个新增 AI 来源；不读取其他生成订阅。

Gemini 社区参考：v2fly `data/google-deepmind` 与 MetaCubeX `geo/geosite/google-gemini.list`；Claude：v2fly `data/anthropic` 与 MetaCubeX `geo/geosite/anthropic.list`。**MetaCubeX 主要是衍生格式，不能当作完全独立的域名归属证据。** 每次记录各来源 SHA-256、数量和变化，在新来源异常缩减、缺失、语法变化时保留上一版有效输出。生成文件由 Action 提交，不直接手改。

`config/ai-services.rules` 只补充经过审查的独立 AI 主机。2026-11-23 起，Gemini 删除会被 Gmail / Google Play / 其他 Google 服务 / 普通网站共用的登录、字体、图片、通用 API/CDN 精确主机；将 `jnn-pa.googleapis.com`、`waa-pa.clients6.google.com` 以及已知被普通 Google Search 使用的 Geller/Proactive 后端交还 Johnshall 原有规则。官方「防火墙允许清单」不是「Gemini 专属流量清单」，Google 共享连接继续按 Johnshall 原始规则处理，即使 Gemini 页面本身走台湾 AI 节点，登录或静态资源也可能走不同出口。主要 Gemini、AI Studio、Code Assist API 仍由经过筛选的上游规则覆盖，实际覆盖情况要用客户端连接日志复核。Claude Code 的精确主机规则保持不变。新增不明域名仍只进入 `data/ai-review-queue.md` 待审，不自动代理。

GitHub Actions 分别记录两套真实构建状态、独立安全发布、失败保留上一版有效配置、无变化不生成 Commit，并最终通过 **一个 Telegram Bot 消息**汇总成功/失败/域名统计。原有人工拒绝与到期复审、Telegram 已送达状态仍按原机制运作。

### AI 专用域名与防直连审查（2026-11-23）

Claude Code 官方网络清单中的可选错误报告精确主机 `browser-intake-us5-datadoghq.com` 已加入两份生成订阅；只匹配这个完整主机，不纳入整个 `datadoghq.com`，也不删除已有 Claude 监控及登录规则。Gemini 继续限定 Google AI 产品及其明确后端，不重新放宽 Google 登录、字体、Play 或普通 API 全域。OpenAI 保留已核实的核心和 Voice 依赖；v2rayN 先前单独批准的 Statsig / 共享供应商例外暂时维持，待实际客户端出口验收后再逐项评估收窄，避免无意放回直连。

**重要：路由订阅不是 Kill Switch。** Shadowrocket、v2rayN 的最后规则仍遵循 Johnshall 的 `FINAL,direct`；当客户端未捕获连接、DNS / IPv6 绕过隧道、应用自行连接或 VPN 断开时，单靠已知域名清单不能保证不会使用本机出口。请按 [AI 出口与防直连验收清单](docs/ai-egress-validation.md) 在实际设备测试，特别验证代理断线时关键 AI 连接会失败而不是退回直连。仓库不能代替手机/Windows 防火墙设置，也没有替你开启系统级拦截。

此订阅覆盖经审核的域名和已知共享依赖，不保证 Chrome / 桌面客户端的所有 DNS、WebSocket、WebRTC、IPv6、UDP 一定经过代理。请使用客户端连接日志和实际出口 IP 验证 Gemini 网页、AI Studio、Claude 网页、Claude Code、登录和文件上传。Shadowrocket 的 URL Rewrite / MITM 与 v2rayN 路由规则功能不同，不承诺完全等价。

### 官方文件每周复审（不阻塞每日生成）

每天同一个 Actions 的 `scripts/run_dual.py` 还会调用 `scripts/audit_ai_docs.py`；仅在**台湾时间周日的定时运行**检查 Google Gemini App 防火墙与 Anthropic Claude Code 的官方网络文档。提取并比较相关主机集合，同时单独记录未分类的可见主机（可能包含导航或正文误报，只供人工观察），变化时写入 `data/ai-docs-review.md`，但**绝不会直接把网页上新出现的主机自动加入代理**。如果官方网页暂时不可访问或被安全验证阻断，保留旧快照，Telegram 会记录警告，不影响任何一套已经验证成功的规则。未修改原有唯一的每天 11:00 调度。非周日的普通推送不会发起官方网页请求。

### Gemini / Claude 人工拒绝及六个月复审

`config/ai-review-decisions.json` 为独立的 AI 审核记录，格式为 `{"version":1,"default_review_months":6,"reminder_interval_days":30,"rejected_rules":[]}`。人工拒绝条目使用 `{"service":"claude","rule":"DOMAIN-SUFFIX,example.test","reason":"依据与拒绝原因","reviewed_at":"2026-11-23"}`（示例不会被自动加入）。建置时会计算六个月后的复审日期，在 `data/ai-review-queue.md` 标识待审、暂缓和到期；到期**不会自动批准**，而是继续由人工查证。两套客户端通过发布校验后合并候选（服务 + 规则去重，合并来源）；失败的一端保留其上次有效候选（如有）并明确标注。新待审项在 Telegram 成功送达且完整 Actions 摘要可用后记录回执，已到期且未处理的记录按 `reminder_interval_days`（默认 30 天）重复提醒。共享通知状态保存在 `data/ai-review-notifications.json`，与订阅路由解耦，不会自动放行任何候选。


### 2026-11-24 第二轮维护改进

- 上游四个 OpenAI 社区域名源及 Apple News 内嵌源各自保存独立规则数量基线；真实异常保留上一版。Voice 与 Johnshall 特批仍绑定来源与历史基线，不放松普通保护。
- 发布前额外检查最终配置的核心域名首个明确匹配动作、AI/Voice 层、v2rayN 本地直连、进程与广告顺序及 FINAL；这是静态验证，不代替 DNS、TUN 或真实客户端测试。
- OpenAI 候选使用 `data/openai-review-snapshots.json` 保存两端观察，合并 `data/review-queue.md`；v2rayN 专属例外仅标记该端覆盖，不改变共用人工批准。已审核但旧端未成功更新的候选单独标记。未处理的待审与到期复审每 30 天再次提醒；首次发现仍即时提醒，送达失败下次重试。
- 每周官方文档检查首次记录全部已知主机、保留通配范围并比较两端已批准规则；星期日错过或失败时，下一次定时同步补查，失败不阻断订阅。未分类主机始终仅供人工观察。
- `data/routing-conflicts.json` 保存所有静态可证明的冲突对及成功提醒回执，新增、消失或范围变化立即提醒，未变化只显示数量、每 30 天复查一次。不可见的 geodata、复杂正则交集及真实 DNS/进程捕获仍需要客户端验证；广告优先级保持不变。

- `tests/test_release_end_to_end.py` 在临时本地 Git bare 仓库内运行两个真实生成器与发布、通知、回执入口；上游及 Telegram 均为离线测试样本，覆盖重复通知、单端失败、远端并发和回执未提交后重试，不接触生产仓库或真实 Bot。


### 2026-11-24 精准分流质量门禁

- 两套订阅的发布前语义检查现在同时核对核心业务入口、实际域名层与审核输入的集合一致性，以及普通 Google、邮件、云服务、支付、监控和其他租户的反向隔离样本。即使 v2rayN 普通层也使用 proxy 标签，核心入口误落普通层或非目标流量误入专用层仍会被检测。此为静态明确域名规则验证，不声称覆盖所有真实设备行为。
- Gemini 六个已有社区入口以相同匹配范围加入人工兜底并列入必需集合；不新开父域或扩大现有分流。
- 已批准共享依赖分组清单按原有半年/30 天机制提醒。旧宽范围例外（LiveKit、Intercom、SendGrid、v2rayN Statsig 等）优先复核，未取得必要性和实际副作用证据前保持原配置。Actions 摘要提供完整清单；通知成功后单独保存 data/approved-dependency-notifications.json 回执。 新增人工共享精确主机、用户指定检测域名或非既有模式的 v2rayN 正则时，需要同步登记复审记录并通过测试；本轮无法重新核实的旧主机单独标为待首次复核，不将历史批准冒充当前官方证据。


### 现有功能维护优化（2026-11-24）

- OpenAI v2fly 解析接受标准行尾注释和属性分隔符，仍保留未知规则为待审，不扩大允许范围。
- 发布门禁逐层核对 Shadowrocket 独立自动/手工规则及 Gemini、Claude 层，避免两层有相同域名时掩盖其中一层缺失；v2rayN 验证局域网、进程、Voice 与最终直连对象不会夹带额外匹配条件。
- 已有冲突检测对精确域名及后缀建立一次索引，保留原匹配语义及输出顺序；反向隔离检查无需重复扫描整个 Johnshall 基线。长 Telegram 报告优先保留异常和审核提醒，详情沿用 Actions 摘要。未新增模块、工作流或路由范围。


### 现有规则解析与审核保护修正（2026-11-24）

- Johnshall 原规则仅替换第三字段的 Proxy 策略，保留域名/关键字、空格、注释和规则顺序；原始广告计数按策略字段识别 REJECT 系列，嵌入列表仍在原位置展开。
- Gemini/Claude v2fly 解析接受显式 domain: 后缀及标准空白分隔的属性/注释；匹配语义及允许列表不变，未知格式仍拒绝。精确/后缀/关键字规则不接受误写的通配符。
- 人工不通过记录表示拒绝该完整匹配范围，而不是否决其中有独立批准证据的所有精确主机。共用 OpenAI、Gemini、Claude 规则若实际完整覆盖被拒绝范围则阻止发布；v2rayN 专属历史例外仍独立，不自动修改审批记录或路由。
- 已迁移的 schema v2 逐来源数量基线缺失时停止发布；只允许明确的 v1 记录迁移与真正首次初始化。保留原有安全阈值及所有特批限制。


### 现有基线与异常隔离维护（2026-11-24）

- v2rayN 历史 Voice 地址及计数必须与已发布 JSON 中实际启用的 Voice 层一致，防止元数据损坏被当作有效历史范围；旧版迁移亦须通过相同核对。
- Johnshall 原普通代理唯一性按 Proxy 条目独立检查，不被 DIRECT 规则数量稀释。BitBrowser 域名按 DNS 大小写不敏感处理，进程名及路径避免大小写重复，拒绝含父目录跳转的所谓专属安装路径。
- 发布校验明确拒绝损坏的路由对象及报告字段；单端验证错误仍只阻止该端发布，另一端继续走原有独立校验。无新分流范围、任务或配置。


### 审核与通知可靠性维护（2026-11-24）

- Gemini/Claude 观察快照先校验候选规则语法及来源，再计算审核状态；损坏的历史快照进入既有恢复路径，不再反复阻塞审核更新。异常的新报告不得写入候选快照。
- 每周官方文档检查拒绝 HTTP 局部响应、长度不符及非法 UTF-8；仍是独立的非阻断性审核提示，不自动改变订阅。Telegram 只在 API 明确返回布尔 true 时确认送达，长消息保留摘要优先级，而 Actions 完整统计不受 Telegram 长度限制。文档或共享依赖复审异常单独显示告警，避免无条件成功提示。


### 人工审核一致性维护（2026-11-24）

- 复用原构建器的批准/拒绝范围判断，在手动登记前识别已被共用规则完整覆盖的候选，避免误登记引发后续构建失败。允许对较宽范围的候选及 v2rayN 专属例外继续独立审核；旧决定续期机制不变。
- OpenAI 历史观察及新报告复用语法验证，保留原始未知社区条目供审核，不把损坏的覆盖字段当作批准证据。两端都未通过验证时不提交待保存的人工记录，避免空路径 `git add`；有效单端仍可独立发布。


### 下载与 Voice 既有校验精简（2026-11-24）

- 两端仍各自请求全部上游并使用独立基线，不读取另一端结果，也不共用下载缓存；仅复用原有 HTTP 完整性、大小、HTTPS URL 与一次重试逻辑，保留各自 User-Agent，避免两份下载器日后行为不一致。共同传输测试归入共同回归组。
- 官方 Voice 目的地址必须是符合原范围限制的公网单播地址；避免 `ipaddress.is_global` 对组播、IPv6 已废弃站点本地地址等特殊地址的分类差异导致误收。不改变当前官方 Voice 地址、域名、节点或分流优先级。


### 现有规则校验与审核代码复用（2026-11-24）

- FINAL 校验只识别 `[Rule]` 中有效规则，按现有解析器处理大小写和字段空白；注释中的 FINAL 不算额外规则，保留上游原文及最后 DIRECT 语义。自动、手工及原始规则顺序均不变。
- OpenAI 与 Gemini/Claude 共用原有精确/后缀覆盖判断和日历月计算，保留各自的批准范围与审核记录。共同域名解析、允许范围、审核和通知传输测试归入共同组；Shadowrocket 专属渲染仍独立。没有增加模块、配置或运行任务。


### 现有审核覆盖与内嵌规则兼容性修正（2026-11-24）

- OpenAI 审核状态与人工拒绝入口使用同一已批准范围判断：通配规则只对可证明完整覆盖的精确主机标为已覆盖，不将后缀或其他通配规则视为已批准；自动/手工层去重保持原保守判断，客户端专属例外不等于共用批准。
- Apple News 规则源在严格验证原有 TOTAL、重复项、无策略及无嵌套依赖要求的前提下，统一处理 UTF-8 BOM、字段空格与规则类型大小写。仅允许原已审核 RULE-SET URL，保持原策略、顺序和字节快照。真实端到端测试覆盖这些等价格式。无新增域名、配置、模块或工作流。


### 现有发布读取与诊断日志兼容性修正（2026-11-24）

- Shadowrocket 发布门禁直接复用已验证的节点配置读取函数，支持相同的 UTF-8 BOM 格式及节点名称限制，防止生成成功后仅因读取方式不同而误拦截；端到端双端发布测试采用该等价编码。
- 双端调度读取子进程诊断日志时以 UTF-8 替换无法解码的字节，保留真实退出码和错误信息，避免单端日志编码异常中断另一端。上游文件、构建报告和订阅产物仍严格解码及验证；未更改分流范围、节点、排程或配置。


### Telegram 日常通知精简

日常 TG 仅显示总体状态、两端实际发布结果及 Actions 链接。仅在有订阅更新、异常、官方文档变化、冲突变化或审核提醒到期时补充相应信息；稳定统计、已通知且尚未到期的候选与冲突不再每日重复展开。完整统计和所有审核明细仍保留在 Actions 执行摘要，原提醒周期、送达回执、独立发布和分流策略不变。
