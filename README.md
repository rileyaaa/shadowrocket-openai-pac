# Shadowrocket OpenAI JP / KR · Johnshall 每日同步

基于 [Johnshall 原始 Shadowrocket 配置](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever) 自动生成**完整且可订阅的** `.conf` 文件，保留原项目广告拦截、直连和 URL Rewrite/MITM 规则，同时加入 OpenAI 专用日本线路。不是 HY 服务端 ACL，也不需要任何 Shadowrocket 策略组。

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

1. 官方 [ChatGPT Voice IP](https://openai.com/chatgpt-voice.json) 自动列表 → `jp_node_name`。
2. MetaCubeX、ACL4SSR、blackmatrix7 的 OpenAI 自动域名 → `jp_node_name`。
3. [完整原 HY 手工兜底](config/manual-openai.rules)（含 Codex、WorkOS、Voice、UDP/3478）→ `jp_node_name`。
4. Johnshall 原本 `Proxy/PROXY` 规则 → `kr_node_name`。
5. Johnshall 原本广告 `REJECT`、直连 `DIRECT`、`FINAL,direct` 原样保留。

原配置约 8 万多行，构建器只替换原 `Proxy` 出站目标，不删除原广告名单。IP 表只覆盖公开的 ChatGPT Voice IP，不能当作 OpenAI 全业务 IP 清单。宽松的 UDP/3478 兜底可能让非 OpenAI 业务走日本节点。未知新 OpenAI 域名仍有漏判风险。

DNS：直连用阿里加密 DoH `https://dns.alidns.com/dns-query`；Google 加密 DoH `https://dns.google/dns-query` 通过日本节点作为备用。禁用自动退回系统 DNS；这不能控制代理服务端自己的 DNS，也不能拦截每个 App 自带的 DoH。

## 每日更新与失败保护

工作流：[`.github/workflows/sync-upstream.yml`](.github/workflows/sync-upstream.yml)。

- 每天 10:30（Asia/Taipei）尝试同步；GitHub Actions 实际执行可能延迟。
- 编辑 `config/user-settings.json` 或 `config/manual-openai.rules` 后自动触发新构建；也可以在 Actions 页手动运行。
- 获取 Johnshall 上游、OpenAI 官方 Voice IP、三份自动域名源，校验后才写出完整配置。
- 只有内容变化才提交新生成文件；某个源下载或校验失败，则保留上一版，不发布不完整配置。
- GitHub 生成文件更新不等于 iPhone 配置已刷新，请在小火箭中更新配置订阅。

本仓库为个人整合项目，保留 Johnshall 上游头部与相关署名，不代表其官方版本。请不要往公开的 JSON 文件填写密码、Token 或订阅地址。
