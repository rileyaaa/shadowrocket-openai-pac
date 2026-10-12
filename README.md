# Shadowrocket OpenAI JP / KR · Johnshall 自动同步

基于 [Johnshall Shadowrocket-ADBlock-Rules-Forever](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever) **原版完整配置** 自动生成 iOS Shadowrocket `.conf`。**不是附加模块，也不是 HY 服务端 ACL。**

## 订阅地址

```text
https://raw.githubusercontent.com/rileyaaa/shadowrocket-openai-pac/main/Shadowrocket_Johnshall_JP_KR.conf
```

在小火箭「配置」页点击 `+` 导入地址，启用该配置；首页「全局路由」选择 **配置**，不要选「代理」。需要先在小火箭中导入你自己的 Hysteria 2/机场节点订阅。此仓库 **不包含任何代理节点或账号**。

配置自动创建 `JP` / `KR` 策略组，分别从现有节点名称中筛选日本和韩国节点。**首次导入后一定进入策略组，确认 JP 绑定到你的“日本JP”节点、KR 绑定到“韩国KR”节点。** 未命中正则或未选中节点时无法正常代理。JP 不包含 KR/DIRECT，避免被意外切换到韩国或直连。

## 分流优先级

| 优先顺序 | 目标 | 动作 |
|---|---|---|
| 1 | OpenAI 官方 `chatgpt-voice.json` IP，IP-only 连接优先匹配（不限定协议） | `JP` |
| 2 | 自动维护 OpenAI 域名：MetaCubeX GeoSite、ACL4SSR、blackmatrix7 的域名条目 | `JP` |
| 3 | `config/manual-openai.rules`：原 HY ACL **完整手工兜底**，含 ChatGPT、OpenAI API、Sora、Codex、WorkOS、LiveKit 等 | `JP` |
| 4 | 原版 Johnshall 87k 左右规则中的 `Proxy/PROXY` | `KR` |
| 5 | 原版 `Reject` 广告拦截 | `REJECT`，不变 |
| 6 | 原版直连和 `FINAL,direct` | `DIRECT`，不变 |

> 注意：第 4～6 项保持上游规则的**原始相对顺序**，并非所有 `REJECT` 规则都排在 `KR` 规则之前。若同一目标同时匹配多个规则，依照小火箭的实际规则优先级生效。若是新出现且所有 JP 规则都不认识的 OpenAI 域名，仍有漏匹配可能；没有人可以保证掌握尚未公布的全部域名。

**IP 解释：** OpenAI 公开的 `chatgpt-voice.json` 只覆盖 ChatGPT 语音连接服务器，不是所有 OpenAI 产品的全量目标 IP。不会把 Cloudflare、Azure 或其他 AI 公司整段 ASN 误当成 OpenAI。官方 Voice IP 条目使用 `no-resolve`，只有目的地址为该 IP 的连接才匹配，不会为了套用 IP 表而先解析全部域名。手工保留 `AND,((PROTOCOL,UDP),(DST-PORT,3478)),JP` 的宽松兜底，其他应用的 UDP 3478 也可能被导入 JP（偏向宁可多走 JP）。

## DNS（加密、防污染）

- **AliDNS DoH**：`https://dns.alidns.com/dns-query#no-h3`，国内/直连优先。
- **Google DoH**：`https://dns.google/dns-query#proxy=JP`，经日本 JP 的加密备用；如果 JP 分组不可用，备用解析也可能失败。
- 禁止回退到系统 DNS：`dns-direct-system = false`、`dns-fallback-system = false`。
- 对常见明文 53 端口 DNS 做小火箭劫持；但不能强制接管所有 App 自带 DoH/DoT，也**不能修改代理服务器自己用的 DNS**。

## 每天自动同步

工作流：[`Sync Johnshall + OpenAI rules`](.github/workflows/sync-upstream.yml)

- 时间：每天 **10:30（Asia/Taipei，UTC+8）** = 02:30 UTC。GitHub Actions 排程可能延迟；并非上游 push 后立即触发。
- 也支持在仓库 **Actions → Sync Johnshall + OpenAI rules → Run workflow** 手动执行。
- 下载 Johnshall 上游完整 `.conf`、OpenAI 官方 Voice IP JSON、三份自动域名列表。
- 校验格式、原始规则数量、完整广告拦截和默认直连；只将上游 `Proxy` 改成 `KR`，保留原 `Reject`、`DIRECT`、`[URL Rewrite]` 和 `[MITM]`。
- 只有内容实际变更才提交生成的 `.conf`、`rules/*.list` 和 `data/sources.json`。
- **任何源下载失败或校验失败则 Actions 失败，不提交半成品，仓库保留上一份可用配置。**

你在小火箭导入本仓库的 **raw 配置 URL** 后，小火箭端还需要按客户端设置刷新订阅（后台更新时机由 iOS 决定），**GitHub 更新≠已安装到手机的配置立即热更新**。

## 手工调整与测试

新增 OpenAI 域名：编辑 [`config/manual-openai.rules`](config/manual-openai.rules)，每行 `DOMAIN,xxx` 或 `DOMAIN-SUFFIX,xxx`（**不用写 `,JP`**），由生成器追加。生成内容不要直接改 `.conf`，下次同步会覆盖。

本地测试：

```bash
python -m unittest discover -s tests -v
python scripts/build.py
```

要求 Python 3.12+，无第三方依赖。GitHub Actions 默认 `GITHUB_TOKEN` 需要仓库允许工作流写入内容（workflow 中已声明 `contents: write`；若组织策略限制，还需在 Settings → Actions → General 检查）。

**上游版权与来源：** 原始规则来自 Johnshall 项目，生成文件保留其头部、广告规则和相关说明。其他自动源包含 [MetaCubeX](https://github.com/MetaCubeX/meta-rules-dat)、[ACL4SSR](https://github.com/ACL4SSR/ACL4SSR)、[blackmatrix7](https://github.com/blackmatrix7/ios_rule_script) 及 [OpenAI 官方 ChatGPT Voice IP](https://openai.com/chatgpt-voice.json)。本仓库是个人二次整合，不代表这些项目的官方版本。