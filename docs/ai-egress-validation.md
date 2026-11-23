# AI 出口与防直连验收清单（操作指南，不是第三份订阅）

此文档用于验证 **OpenAI / ChatGPT / Codex / Voice、Claude / Claude Code 和 Google AI** 的实际出站情况。仓库只维护 `Shadowrocket_Johnshall_AI.conf` 和 `v2rayN_Johnshall_AI.json` 两个客户端订阅；本指南不会修改用户设备的防火墙、网络代理或账号信息。

## 审查原则

- **OpenAI / Claude**：核心账号、API、登录、模型、文件、WebSocket 与经核实的官方辅助依赖应由 AI 出口承载。共享供应商域名只按必要的精确主机或有明确官方依据的范围纳入，不以整家 CDN / 云平台 / ASN 兜底。
- **Google AI**：只明确选入 Gemini、AI Studio、Code Assist、NotebookLM、Flow、Jules、Opal、Antigravity 等 Google AI 产品及其专用后端；Google 通用登录、字体、图片、Play、Gmail、Drive、YouTube、Google Maps 继续按照原 Johnshall 分流。官方防火墙允许清单不等于独占 AI 域名清单。
- **不改 Johnshall 最终策略**：目前两个客户端订阅最后仍是 `FINAL,direct`，因此「未知服务域名也绝不直连」不是订阅具备的能力。账号安全、地区合规与真实出口隐私是不同概念。

## 静态核对（仓库内的自动化测试）

- Claude Code 新增的官方可选错误上报主机为 **精确** `browser-intake-us5-datadoghq.com`，不得放宽为 `datadoghq.com` 整站。
- Shadowrocket 构建后应有 `DOMAIN,browser-intake-us5-datadoghq.com,Hinet🇹🇼台湾,force-remote-dns`。
- v2rayN 应有 `full:browser-intake-us5-datadoghq.com`、`outboundTag=proxy`，但不写死台湾 AI 节点节点。
- 原有 OpenAI Voice 官方目的 IP、ChatGPT / Codex 域名和 Google AI 边界不因本次变更而移除。
- `BitBrowser.exe` 进程规则与现有 11 条比特浏览器域名保持不变。

## iPhone / Shadowrocket 实际验收

1. 确认实际订阅为 `Shadowrocket_Johnshall_AI.conf`，路由模式采用该配置；代理节点名称必须与 `config/user-settings.json` 的备注完全相符。
2. 在连接日志中逐一核对 `chatgpt.com`、`api.openai.com`、`files.oaiusercontent.com`、`claude.ai`、`api.anthropic.com`、`platform.claude.com`、`gemini.google.com` 是否命中 **台湾 AI 节点**。可选遥测域名没有实际请求时不必人为触发。
3. 核对普通 `mail.google.com`、`drive.google.com` 等未进入 *AI 专用层*；它们是否走新加坡或直连由 Johnshall 自身决定。
4. 检查实际连接记录中的 DNS、IPv4/IPv6、UDP、WebSocket 路径及真实节点出口。对 Voice 的 UDP 3478 使用官方目的 IP 规则核查，不使用全网 UDP 3478 通配规则。
5. **故障验收**：在可控条件下使台湾 AI 节点节点不可达，但保持客户端运行。测试关键 AI 请求是否失败，并从连接日志或网络抓包确定没有通过手机本机出口成功连接。随后恢复节点。仅看到 VPN 图标或「自动重连」不足以证明 Kill Switch；如果 iOS 上无法确认断线阻断，不能把当前分流配置视为零泄漏方案。

## Windows / v2rayN 实际验收

1. 导入 `v2rayN_Johnshall_AI.json` 为**自定义路由规则数组**，选择实际期望的活动节点；本 JSON 不携带服务器信息，也不指定台湾 AI 节点。
2. 检查 TUN 与系统代理捕获方式、DNS 与 IPv6，确认应用 / CLI / 子进程确实被路由。Windows 上的 `BitBrowser.exe` 进程匹配依赖实际内核及进程识别能力；不要添加通用 `chrome.exe`、`node.exe` 或 `firefox.exe`。
3. 核对 `api.anthropic.com`、`claude.ai`、`chatgpt.com`、`api.openai.com` 的有效规则为 `proxy`；确认实际选中的代理出口，不要把 JSON 的 `proxy` 标签当成已经选择台湾 AI 节点的证明。
4. Claude Code 支持 `HTTP_PROXY` / `HTTPS_PROXY`，但**不直接支持 SOCKS 代理**。检查启动时的环境变量和 `NO_PROXY`；后台 agent 的代理环境应通过用户级或托管设置继承，而不能只依赖某次 shell 的临时变量。不要把密码写入仓库。参考 [Claude Code 官方网络配置](https://code.claude.com/docs/en/network-config)。
5. **故障验收**：停用实际代理节点（保留 TUN / 进程捕获），核对关键 AI 请求不能回落到 Windows 本地直连；必要时在 Windows 防火墙设置按程序阻断直连，但先确认不会造成 v2rayN 内核路由环路或阻断代理本身。检查主进程、后台 agent、DNS 和 IPv6，避免只看浏览器出口检测网站。

## 验收结果说明

- **订阅生成测试通过 ≠ 实机无泄漏**。GitHub Actions 没有你的手机、Windows、代理节点和网络环境，无法自动测试断网时的真实行为。
- 任何新的官方主机都要先核实来源、精确作用域和两端是否等价；若尚未验证，就进入人工待审核，不自动扩大 Google / Datadog / Cloudflare 等整站。
- 代理出口和账号地区政策是两回事；网络分流不能保证账号不会受到服务商地区或风控规则影响。
