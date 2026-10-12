# 上游规则授权和署名

本项目生成的 `Shadowrocket_Johnshall_OpenAI.conf` 包含对 Johnshall 原有 Shadowrocket 规则文件的修改与再发布。

- 上游项目：https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever
- 上游文件：https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever/blob/release/sr_top500_banlist_ad.conf
- 上游许可：Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)，https://creativecommons.org/licenses/by-sa/4.0/
- 本项目修改：将上游 `Proxy` 路由指向用户选定的普通代理节点；增加 OpenAI 专属路由、官方 Voice 目的 IP、独立手工兜底和 DNS 配置，并进行自动合并发布。

原 Johnshall 的既有 DIRECT、REJECT、URL Rewrite、MITM 及最终直连规则按项目生成逻辑保留。基于该上游修改并公开再发布的衍生配置应遵循 CC BY-SA 4.0 的署名及相同方式共享条件。

本说明不表示 Johnshall 原作者认可或支持本项目；项目中的独立构建脚本与测试文件不因本说明自动使用同一软件许可证。
