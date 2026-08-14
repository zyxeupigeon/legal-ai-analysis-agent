# 法律AI产品分析项目首次试用指南

## 需要准备

1. Windows和Python 3；
2. 已安装并登录的兼容Agent，例如Claude Code或OpenCode；
3. 一个明确的法律AI产品名称。

项目不要求固定模型、模型API、浏览器MCP或插件。Agent仍必须实际具备公开检索、网页正文读取、Word生成、PDF/图片渲染和视觉检查能力。

## 第一次启动

在文件资源管理器打开项目根目录，在地址栏输入 `powershell` 并回车。先运行：

```powershell
.\START_AGENT.cmd -SelfTest
```

自检会临时生成最小Word，将其转成PDF和逐页PNG，验证后自动清理。整个启动与预检入口使用 Python，不执行项目中的下载 `.ps1` 文件；不要为本项目修改系统执行策略。看到 `SELF_TEST_OK` 后运行：

```powershell
.\START_AGENT.cmd
```

需要指定Agent时：

```powershell
.\START_AGENT.cmd -Agent claude
.\START_AGENT.cmd -Agent opencode
```

Agent收到每个新会话的第一条消息后，必须先运行项目预检和任务所需能力检查。只有无需你额外决定、无需重启且可以在当前对话直接正常运行时，才回复 `SESSION_PREFLIGHT_READY` 并继续。需要非低风险修复、安装、登录、授权、重启或关键能力无法立即恢复时，必须回复 `SESSION_PREFLIGHT_BLOCKED`，不创建任务目录、不研究、不生成报告，只说明问题和你需要做的操作。

## 输入什么

```text
请完整读取项目协议，然后分析法律AI产品“产品名称”，生成并质检Word报告。
```

需要参考报告时，在同一条消息中提供绝对路径，并说明它只用于模仿结构和写法，不能作为目标产品的事实证据。

## 如何确认没有写错项目

启动器会显示 `Project root` 和 `Output root`。Agent必须：

1. 确认当前绝对目录与 `LEGAL_AI_PROJECT_ROOT` 相同；
2. 运行 `python scripts/create_task_workspace.py --task-id <唯一任务ID> --session-gate READY`；
3. 只向返回的绝对 `TASK_OUTPUT_DIR` 写文件。

如果出现 `TASK_WORKSPACE_FAIL`，不要改用父目录、同级旧项目或历史任务目录；应先纠正工作目录并重新启动Agent。

## 正常结果

分配的任务目录至少应出现：

- `task_context.json`
- `report.docx`
- `sources.md`
- `claim_evidence.json`（逐条主张、来源和正文位置的证据账本）
- `capability_declaration.md`
- `run_summary.md`
- `process_optimization_report.md`（记录真实耗时、工具、失败重试、瓶颈和下一轮优化建议）
- `render/report.pdf`
- `render/page-*.png`

只有确定性验收、最终逐页视觉检查和过程优化报告都完成时，`run_summary.md`才能写总体PASS。验收器的结构性OK不等于总体PASS；报告任务也不得修改协议、脚本或验收配置。完成后，Agent必须在回复中明确列出 `report.docx` 与 `process_optimization_report.md` 的文件名和绝对路径。

## 正常停止情形

若自检发现缺少联网或正文读取能力、无法生成Word/PDF/页面图片、无法视觉检查、根目录绑定不一致，或修复需要你确认、安装、授权、登录或重启，Agent必须在生成报告前停止并报告 BLOCKED，不得凭模型记忆补写或生成PARTIAL报告。进入研究后才出现的证据不足，按协议缩减、停止或如实处理。
