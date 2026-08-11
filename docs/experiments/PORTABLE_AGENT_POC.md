# 通用命令行 Agent 项目模式可行性试验

## 假设

使用者下载并解压项目，在项目根目录打开 PowerShell，然后运行自己已经安装并登录的命令行 Agent。项目不指定 Agent 厂商、模型、API 或 MCP；只有满足项目能力要求的 Agent 才能继续执行。

## 原型范围

- 通用规范：PROJECT_AGENT_PROTOCOL.md
- 自动发现适配：AGENTS.md、CLAUDE.md、GEMINI.md
- 本地预检：scripts/check_agent_workspace.ps1
- 隔离输出：agent_outputs/

上述文件不被现有 FastAPI、Next.js、测试或启动脚本引用，因此不改变现有网页应用运行路径。

## 可验证内容

1. 使用者确实可以从项目根目录启动不同 Agent。
2. 支持对应约定的 Agent 可以自动发现入口文件。
3. 所有入口可以汇聚到同一份项目协议，避免维护多套业务提示词。
4. PowerShell 预检可以验证目录、核心规则、Python和输出权限。

## 不能由项目保证的内容

1. 任意 Agent 都会识别任意一种自动发现文件。
2. 任意账户都包含网页搜索、浏览器、Word生成和视觉检查能力。
3. 不同模型会生成完全一致的分析结果。
4. Agent厂商不会改变命令、权限、上下文或计费规则。

## 判定标准

原型务实，但产品承诺应写成“兼容满足能力协议的 Agent”，不能写成“任何 Agent 均可无配置运行”。如果某 Agent 不支持自动发现，使用者仍需在首条指令中要求其读取 PROJECT_AGENT_PROTOCOL.md。
## 2026-08-10实测结果

- OpenCode 1.18.15通过，模型为deepseek/deepseek-chat；自动发现AGENTS.md并返回PREFLIGHT_OK。
- Claude Code 2.1.226通过，服务地址为api.deepseek.com，模型映射为DeepSeek V4；自动发现CLAUDE.md并返回PREFLIGHT_OK。
- Claude首次测试因任务文本禁止临时探针、第二次因非交互Bash白名单过窄而安全停止；放行唯一所需Bash工具后通过。说明权限策略必须允许预检命令，但无需跳过全部权限。
- OpenCode首次输出中文路径乱码；预检脚本随后增加UTF-8输出设置。
- 两个Agent均正确理解：网页检索或正文读取能力不足时停止事实研究，不用模型记忆补造事实或URL。
