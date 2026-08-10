# P3.0 通用命令行 Agent 项目模式验证

## 目标

验证使用者下载并解压项目后，可以在项目根目录通过 PowerShell 启动自己已有并已登录的命令行 Agent，由项目内统一协议约束研究、证据核验、Word生成和质检流程。项目不指定 Agent 厂商、模型、模型 API、浏览器或 MCP。

## 双轨状态

- P2.3.4 网页应用及其 FastAPI、Next.js、DeepSeek/Tavily适配能力冻结保留，不因 P3.0删除或重写。
- P3.0只增加项目根目录 Agent入口、统一能力协议、预检和隔离输出。
- 两条运行路径不互相调用；发现回归缺陷前不修改 P2.3.4业务代码。

## 兼容模型

项目承诺“兼容满足能力协议的 Agent”，不承诺“任何 Agent 均可无配置运行”。使用者仍须安装并登录至少一个命令行 Agent，并用该工具自己的命令启动。Agent可以使用订阅、厂商API或兼容模型服务；凭据属于 Agent运行环境，不写入项目。

## 自动发现

- AGENTS.md：Codex、OpenCode及兼容工具入口。
- CLAUDE.md：Claude Code入口。
- GEMINI.md：Gemini CLI入口。
- PROJECT_AGENT_PROTOCOL.md：唯一规范来源。

不支持上述自动发现约定的 Agent，必须由使用者在首条指令中要求其完整读取 PROJECT_AGENT_PROTOCOL.md。

## 能力闸门

完整研究前必须运行 scripts/check_agent_workspace.ps1，并由 Agent补充声明脚本无法验证的能力：公开互联网检索、来源正文读取、可编辑Word生成、页面渲染和视觉版式检查。

关键能力不足时停止，不得用模型记忆补造事实或假装完成检查。浏览器、MCP、插件和具体搜索服务只是能力实现方式，不是硬性依赖。

## 已完成验证

2026-08-10在同一 Windows项目目录完成：

- OpenCode 1.18.15 + deepseek/deepseek-chat：自动发现 AGENTS.md，读取统一协议，执行预检并返回 PREFLIGHT_OK。
- Claude Code 2.1.226 + api.deepseek.com映射的 DeepSeek V4：自动发现 CLAUDE.md，读取统一协议，在受限 Bash白名单下执行预检并返回 PREFLIGHT_OK。
- 两次验证均未联网研究、未读取 .env、未使用浏览器/MCP、未修改业务文件。
- P2.3.4冻结基线验证通过，后端65项测试通过，前端类型检查和生产构建通过。

## P3.0完成条件

1. 至少两个不同命令行 Agent通过自动发现和本地预检。
2. 至少一个非原网页路径完成真实法律AI产品端到端研究、Word生成和逐页视觉检查。
3. 同一测试对象的关键事实满足P2.3.4证据与冲突规则。
4. 失败场景能够因能力、搜索或证据不足而安全停止。
5. 使用说明不要求固定模型、模型API或MCP。
6. 网页应用回归检查继续通过。

当前已满足第1、5、6项；第2至4项将在下一轮端到端测试完成。
## 首次端到端验收结果

Claude Code + DeepSeek V4已在不调用现有网页/API、不读取旧报告和.env的条件下，独立完成公开检索、11项来源记录、Word生成、PDF及10页PNG渲染。通用结构验收通过，共识别15个唯一来源URL。

总体仍判FAIL：独立复核发现报告未取得已知深圳发改委来源fgw.sz.gov.cn及其“历经6年”口径，只记录应用宝“历时8年”，未满足P2.3.4冲突回归；末尾页面内容密度亦需优化。VERSION_MANIFEST继续标记failed_pending_evidence_and_layout_fix。

P3.0因此证明架构可运行，但尚未达到冻结条件。后续必须由Agent重新研究，并通过scripts/validate_portable_agent_output.py加载evaluations/p3_delifasou_acceptance.json后再进行独立视觉检查。
