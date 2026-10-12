# Shadowrocket OpenAI JP / KR · Johnshall 每日同步

基于 [Johnshall 原始 Shadowrocket 配置](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever) 自动生成**完整且可订阅的** `.conf` 文件。**唯一的路由改变是 OpenAI 专属流量优先走日本节点：原版需要代理的其他网站仍走韩国，原版直连/广告拦截规则原样保留。** 没有额外策略组，也不是 HY 服务端 ACL。

## 订阅地址

```text
https://raw.githubusercontent.com/rileyaaa/shadowrocket-openai-pac/main/Shadowrocket_Johnshall_JP_KR.conf
```

在小火箭中导入你自己的两个代理节点（节点账号、密码不会存入本公开仓库），然后进入小火箭「配置」导入上述完整配置，选择「配置」路由模式。

## 只改两个节点名称

[编辑 **config/user-settings.json**](config/user-settings.json)：

```json
{
  "jp_node_name": "日本JP",
  "kr_node_name": "韩国KR"
}
```

两个值就是**小火箭里现有节点的真实完整名称**（包括空格、Emoji 和编号），不是节点地址或机场订阅链接。若实际名称不同，请改成完全一致的备注。名称必须唯一、不允许为空。

没有 `[Proxy Group]`，没有额外策略组变量。生成器会直接写入：

```ini
DOMAIN-SUFFIX,chatgpt.com,日本JP
DOMAIN-SUFFIX,telegram.org,韩国KR
FINAL,direct
```

本地查询使用的 Google DoH 如需通过韩国节点发出，会自动引用 URL 编码后的韩国节点名称；OpenAI 域名则尽量交由日本代理服务器远端解析。

**换节点的操作：** 在 GitHub 编辑上述 JSON → Commit changes 到 `main` → GitHub Actions 自动重新生成完整 `.conf` → 手机端刷新配置订阅。以后每天同步 Johnshall 上游也持续使用最新保存的两个节点名。**不要直接编辑生成后的 `.conf`**，它会被下一次同步覆盖。

## 分流与加密 DNS

**逻辑等价于先选择韩国节点运行原 Johnshall 规则，再为 OpenAI 插入日本优先例外：**

1. 官方 [ChatGPT Voice IP](https://openai.com/chatgpt-voice.json) 自动列表 → `jp_node_name`。
2. MetaCubeX、ACL4SSR、blackmatrix7 自动域名源中，**经过 OpenAI 专属域名白名单筛选**的条目 → `jp_node_name`。
3. [OpenAI 手工兜底](config/manual-openai.rules) 中启用的专属域名 → `jp_node_name`。
4. Johnshall 原本 `Proxy/PROXY` 的所有规则 → `kr_node_name`，完全保留规则相对顺序。
5. Johnshall 原本广告 `Reject`、直连 `direct`、`FINAL,direct` 原样保留。

**为什么过滤自动规则？** 部分所谓 OpenAI 规则源包含 `stripe.com`、`auth0.com`、`intercom.io`、`sentry.io` 等全站共享服务。强制把这些服务全部送日本会改变其他网站的原有出站行为，因此生成器会主动排除它们。你原来 HY 的 25 条共享服务或过宽匹配保留为手工文件中的**注释**，不会生效。包括全局 UDP/3478 也不会强制走日本。

### 自动去重：手工兜底不丢失

手工文件目前保留 **22 条启用的 OpenAI 专属规则**，每天同步的自动源筛选结果也有 22 条。两者大部分重叠：

- 20 条手工规则目前已被自动规则覆盖，保留在手工源文件中，不在最终 `.conf` 中重复输出；
- 另外 2 条手工规则 `DOMAIN,cdn.openaimerge.com` 和 `DOMAIN-WILDCARD,chatgpt-async-webps-prod-*.webpubsub.azure.com` 当前提供额外覆盖；
- 自动源内部还有 3 条被更宽的后缀规则完全覆盖的重复项。

最终只输出 **19 条自动域名 + 2 条手工域名**，而不是重复列出 44 条。自动构建器每天重新判断一次，如果原先覆盖手工规则的上游条目消失，相应的手工规则就会自动补回，避免误删兜底。

去重只处理**同一日本出站**下有确定包含关系的 `DOMAIN`、`DOMAIN-SUFFIX`，不会改变原 Johnshall 的韩国、直连或广告规则。例如 `DOMAIN-SUFFIX,openai.com` 覆盖 `DOMAIN,api.openai.com`，但 `DOMAIN,openai.com` 不覆盖后者，且 `DOMAIN-SUFFIX,openai.com` 不会匹配 `fakeopenai.com`。

### 第三方依赖：只用真正专属的精确主机

OpenAI 官方的网络清单是**允许访问清单**，不等于其中每个第三方域名都是 OpenAI 独占：

- 已启用：`DOMAIN,openai-api.arkoselabs.com`、`DOMAIN,openai.qualtrics.com`、`DOMAIN,cdn.openaimerge.com`、专门的 ChatGPT Web PubSub 主机模式、OpenAI 专用 Azure/Cloudflare 主机；
- 仅作参考、暂不自动走 JP：`cdn.workos.com`、`frontend-apps-multi-region.workos.com`、`challenges.cloudflare.com`、`js.stripe.com`、`*.intercom.io`、通用 LiveKit 域名等。它们即便写成精确的 `DOMAIN,cdn.workos.com`，也可能被非 OpenAI 客户共享。

原则是：第三方服务必须能证明某个**具体主机或子域是 OpenAI 专属**，才加入 JP 的精确 `DOMAIN` 规则；否则沿用 Johnshall 原分流。无法仅凭 SNI/域名确认一个共享主机上的 HTTPS 请求究竟由 ChatGPT 还是其他网站发起；同一个主机按来源网站分别使用 JP/KR 通常需要 HTTPS 请求级识别（涉及解密/MITM），本项目不默认启用这种复杂且可能影响安全和隐私的方式。请勿把公司整段后缀或全局 UDP/3478 强制送 JP。

**限制：** 共享第三方主机可能被 OpenAI 和别的网站同时使用，纯域名/IP 分流无法精确识别它究竟服务哪一个应用。为了优先保持 Johnshall 原始行为，本项目不劫持这些共享域名；部分 OpenAI 登录、语音或其他第三方依赖可能因此仍按照原规则走 KR/DIRECT。官方 Voice IP 清单不是 OpenAI 全业务 IP 清单，未来未知新域名也可能漏判。

### DNS 与节点出口

Shadowrocket 的正常域名代理连接**默认由相应代理出口在远端解析**，因此：

| 请求 | 流量出口与解析责任 |
|---|---|
| OpenAI 专属域名 | 日本节点，`DOMAIN` / `DOMAIN-SUFFIX` 规则追加 `force-remote-dns` |
| Johnshall 原版需要代理的其他域名 | 韩国节点；保留原规则，自行负责代理端 DNS |
| Johnshall DIRECT / FINAL,direct | 不走代理；通过阿里 AliDNS 加密 DoH 本地解析 |
| 本地不得不解析的代理类请求 | 通用 `dns-server` 使用 Google 加密 DoH，经韩国节点转发 |
| 两个代理节点自身的服务器域名 | `proxy-dns-server` 使用阿里 AliDNS DoH，避免代理建立前的 DNS 循环 |
| 异常回退 | `fallback-dns-server` 仍是阿里 DoH，不将直连 DNS 失败的请求意外送往韩国 |

当前生成的关键参数：

```ini
dns-server = https://dns.google/dns-query#proxy=%E9%9F%A9%E5%9B%BDKR
direct-dns-server = https://dns.alidns.com/dns-query#no-h3
fallback-dns-server = https://dns.alidns.com/dns-query#no-h3
proxy-dns-server = https://dns.alidns.com/dns-query#no-h3
dns-direct-system = false
dns-fallback-system = false
dns-direct-fallback-proxy = false
```

节点名称从 `config/user-settings.json` 动态替换为正确的 URL 编码。

#### DNS 举例与 `#no-h3`

- **访问 `api.openai.com`：** 命中 `DOMAIN-SUFFIX,openai.com,日本JP,force-remote-dns`，域名随代理连接交给日本节点，由日本服务器侧完成解析。日本服务器最终使用哪家 DNS，要在服务器上单独确认，不能从本地 `dns-server` 推断。
- **访问 `youtube.com`：** 若原 Johnshall 规则命中普通代理，就直接使用韩国节点，域名通常由韩国端解析。原项目若为直连，依然按其直连。
- **访问 `www.baidu.com`：** 若未命中原代理或拦截规则而落到 `FINAL,direct`，由小火箭通过阿里 DoH 本地解析，随后直连目标。
- **解析节点自身的服务器域名：** 先用 `proxy-dns-server` 的阿里 DoH，避免建立节点连接时反过来依赖自身代理。

`#no-h3` 只表示 **DoH 不升级到 HTTP/3 (QUIC)**，通常仍经 HTTPS/TCP 443 加密传输；不代表明文 DNS，也不决定查询走日本或韩国。节点出口由相应的 `#proxy=` 或业务代理规则决定。

**重要边界：** Google DoH 经韩国只负责确实由小火箭在本地发起的对应查询，**不表示所有韩国代理连接都一定使用 Google 的递归解析器**；日本域名的远端解析同样取决于日本代理服务器自己的 DNS 设置。Shadowrocket 单份通用 `dns-server` / `fallback-dns-server` 不会按每条规则自动更换上游；例如本地代理类查询的 Google DoH 出错时可能回退到阿里，这属于全局回退的限制。要让所有代理端解析最终都使用 Google DoH，需要分别配置并验证日/韩代理服务器；本仓库没有服务器 DNS 的控制权。App 内建 DoH、仅 IP 连接及不可识别的新域名也可能绕过此分流。

### OpenAI 规则覆盖与「完美」的边界

已根据 OpenAI 的[官方 ChatGPT 网络要求](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)核对主站 / API / 鉴权 / 静态资源 / ChatGPT 文件 / ChatGPT 与 Codex WebSocket 的第一方域名：`*.openai.com`、`*.chatgpt.com`、`*.oaistatic.com`、`*.oaiusercontent.com`、`*.oaistatsig.com` 等均有后缀规则；官方 Voice IP 自动表持续同步。除此外还有已列出的专属云服务域名，且新增域名源会先经过筛选。

**目前无法保证 100% 全覆盖。** OpenAI 官方也列出 `cdn.workos.com`、`js.stripe.com`、`*.intercom.io`、`challenges.cloudflare.com` 等多家客户共用的依赖：如果一律 JP，会违背「其他所有服务维持 Johnshall」；如果维持原规则，ChatGPT 的某些登录、支付、支持或语音能力可能仍走 KR/DIRECT。原 HY 列表里的相关规则完整留在 `config/manual-openai.rules` 注释区供以后核查，默认不强制拦截其他网站。也不能通过 OpenAI 云端服务的**出站源 IP** 列表代替客户端连接 OpenAI 时的**目的 IP** 列表。



## 每日更新与失败保护

工作流：[`.github/workflows/sync-upstream.yml`](.github/workflows/sync-upstream.yml)。

- Johnshall 上游计划每天 **07:00（Asia/Taipei；23:00 UTC）** 构建规则（[上游 release.yml](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever/blob/release/.github/workflows/release.yml)）。本仓库安排每天 **08:00（Asia/Taipei；00:00 UTC）** 同步，比上游计划时间晚一小时；GitHub Actions 实际执行仍可能延迟。
- 编辑 `config/user-settings.json` 或 `config/manual-openai.rules` 后自动触发新构建；也可以在 Actions 页手动运行。
- 获取 Johnshall 上游、OpenAI 官方 Voice IP、三份自动域名源，校验后才写出完整配置。
- 只有内容变化才提交新生成文件；某个源下载或校验失败，则保留上一版，不发布不完整配置。
- GitHub 生成文件更新不等于 iPhone 配置已刷新，请在小火箭中更新配置订阅。

本仓库为个人整合项目，保留 Johnshall 上游头部与相关署名，不代表其官方版本。请不要往公开的 JSON 文件填写密码、Token 或订阅地址。
