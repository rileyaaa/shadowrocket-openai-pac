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

Google DoH 备用代理也会自动改成 URL 编码后的日本节点名称。

**换节点的操作：** 在 GitHub 编辑上述 JSON → Commit changes 到 `main` → GitHub Actions 自动重新生成完整 `.conf` → 手机端刷新配置订阅。以后每天同步 Johnshall 上游也持续使用最新保存的两个节点名。**不要直接编辑生成后的 `.conf`**，它会被下一次同步覆盖。

## 分流与加密 DNS

**逻辑等价于先选择韩国节点运行原 Johnshall 规则，再为 OpenAI 插入日本优先例外：**

1. 官方 [ChatGPT Voice IP](https://openai.com/chatgpt-voice.json) 自动列表 → `jp_node_name`。
2. MetaCubeX、ACL4SSR、blackmatrix7 自动域名源中，**经过 OpenAI 专属域名白名单筛选**的条目 → `jp_node_name`。
3. [OpenAI 手工兜底](config/manual-openai.rules) 中启用的专属域名 → `jp_node_name`。
4. Johnshall 原本 `Proxy/PROXY` 的所有规则 → `kr_node_name`，完全保留规则相对顺序。
5. Johnshall 原本广告 `Reject`、直连 `direct`、`FINAL,direct` 原样保留。

**为什么过滤自动规则？** 部分所谓 OpenAI 规则源包含 `stripe.com`、`auth0.com`、`intercom.io`、`sentry.io` 等全站共享服务。强制把这些服务全部送日本会改变其他网站的原有出站行为，因此生成器会主动排除它们。你原来 HY 的 25 条共享服务或过宽匹配保留为手工文件中的**注释**，不会生效。包括全局 UDP/3478 也不会强制走日本。

**限制：** 共享第三方主机可能被 OpenAI 和别的网站同时使用，纯域名/IP 分流无法精确识别它究竟服务哪一个应用。为了优先保持 Johnshall 原始行为，本项目不劫持这些共享域名；部分 OpenAI 登录、语音或其他第三方依赖可能因此仍按照原规则走 KR/DIRECT。官方 Voice IP 清单不是 OpenAI 全业务 IP 清单，未来未知新域名也可能漏判。

DNS：直连用阿里加密 DoH `https://dns.alidns.com/dns-query`；Google 加密 DoH `https://dns.google/dns-query` 经**韩国日常节点**作为备用，不让普通 DNS 查询成为 JP 例外。禁用自动退回系统 DNS；这不能控制代理服务器自己的 DNS，也无法强制拦截全部 App 自带的 DoH。

## 每日更新与失败保护

工作流：[`.github/workflows/sync-upstream.yml`](.github/workflows/sync-upstream.yml)。

- Johnshall 上游计划每天 **07:00（Asia/Taipei；23:00 UTC）** 构建规则（[上游 release.yml](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever/blob/release/.github/workflows/release.yml)）。本仓库安排每天 **08:00（Asia/Taipei；00:00 UTC）** 同步，比上游计划时间晚一小时；GitHub Actions 实际执行仍可能延迟。
- 编辑 `config/user-settings.json` 或 `config/manual-openai.rules` 后自动触发新构建；也可以在 Actions 页手动运行。
- 获取 Johnshall 上游、OpenAI 官方 Voice IP、三份自动域名源，校验后才写出完整配置。
- 只有内容变化才提交新生成文件；某个源下载或校验失败，则保留上一版，不发布不完整配置。
- GitHub 生成文件更新不等于 iPhone 配置已刷新，请在小火箭中更新配置订阅。

本仓库为个人整合项目，保留 Johnshall 上游头部与相关署名，不代表其官方版本。请不要往公开的 JSON 文件填写密码、Token 或订阅地址。
