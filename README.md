# Shadowrocket OpenAI JP / KR · Johnshall 自动同步

基于 [Johnshall Shadowrocket-ADBlock-Rules-Forever](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever) **原版完整配置** 自动生成 iOS Shadowrocket `.conf`。**不是附加模块，也不是 HY 服务端 ACL。**

## 订阅地址

```text
https://raw.githubusercontent.com/rileyaaa/shadowrocket-openai-pac/main/Shadowrocket_Johnshall_JP_KR.conf
```

在小火箭「配置」页点击 `+` 导入地址，启用该配置；首页「全局路由」选择 **配置**，不要选「代理」。需要先在小火箭中导入你自己的 Hysteria 2/机场节点订阅。此仓库 **不包含任何代理节点或账号**。

配置默认创建 `JP` / `KR` 策略组。你可以在 `config/user-settings.json` **直接填入实际节点的完整名称**，生成器就会明确绑定相应节点；未填写时保留日本/韩国关键词筛选模式。首次导入后仍应在小火箭内确认两组实际指向的节点。JP 组不包含 KR/DIRECT 作为备用，避免 OpenAI 在 JP 故障时被意外切到其他出口。

## 只改一个文件：自定义日本 / 韩国节点名称

以后换节点，**只需要编辑 [`config/user-settings.json`](config/user-settings.json)，不要修改生成出来的 `.conf`**。

仓库当前的默认配置：

```json
{
  "jp_node_name": "",
  "kr_node_name": "",
  "jp_policy_name": "JP",
  "kr_policy_name": "KR"
}
```

- **`jp_node_name`**：填写小火箭节点订阅里**日本节点的完整名称**，包括空格、旗帜 emoji 和编号（必须与客户端一致）。
- **`kr_node_name`**：填写韩国节点的完整名称。
- **`jp_policy_name` / `kr_policy_name`**：策略组显示名称，通常无需更改，保持 `JP`、`KR` 最省心；如需修改，脚本会同步更新全部 JP/KR 分流规则与 Google DoH 的 `#proxy=` 引用。
- 两个节点名保持空字符串 `""`：延续原来的**国家关键词正则筛选**，你可在小火箭中手动选择具体节点。**建议填完整节点名**，减少选错线路的可能。
- 节点名称中如果包含英文逗号 `,`、`=`、`#` 或换行，当前生成器会阻止构建并提示错误，避免产生无效 Shadowrocket 配置。不可把 JP 和 KR 指向同一个节点。

例如，你的订阅节点叫“🇯🇵 东京 A-01”和“🇰🇷 首尔 B-02”，那么改成：

```json
{
  "jp_node_name": "🇯🇵 东京 A-01",
  "kr_node_name": "🇰🇷 首尔 B-02",
  "jp_policy_name": "JP",
  "kr_policy_name": "KR"
}
```

此时生成文件的策略组会变成：

```ini
[Proxy Group]
JP = select,🇯🇵 东京 A-01,policy-select-name=🇯🇵 东京 A-01
KR = select,🇰🇷 首尔 B-02,policy-select-name=🇰🇷 首尔 B-02
```

**如何生效：** 打开上面的配置文件链接 → 点击 GitHub 铅笔编辑 → 修改后 **Commit changes** 到 `main` → GitHub Actions 自动触发构建并提交新的完整 `.conf` → 在 iPhone 小火箭里刷新配置订阅。以后再修改，只重复这一个文件的操作即可，后续每天上游更新也会继续使用你的新节点名称。

仓库是公开的，**只填写节点备注名称，不要写代理订阅链接、密码、token 或服务器凭据**。如果你的机场里存在重名节点，单靠名称可能无法明确区分；请先给节点设置唯一备注或在小火箭中检查实际选中项。

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
- 只有内容实际变更才提交生成的 `.conf`、`rules/*.list` 和 `data/sources.json`；**修改 `config/user-settings.json` 也会立即触发同一工作流**，无须等第二天。
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