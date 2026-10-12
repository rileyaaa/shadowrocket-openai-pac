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
- 你 HY 原文里的 WorkOS、Stripe、Intercom、Sentry、LiveKit 通用域名、Statsig / Feature Gates、Cloudflare 验证、Apple 检测等**仍完整保存在手工源文件的注释区**，未丢失；但它们是共享服务，不能仅凭域名断定某次连接属于 OpenAI，因此**不默认强制日本**。官方“允许访问清单”不等于“OpenAI 独占域名清单”。
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
