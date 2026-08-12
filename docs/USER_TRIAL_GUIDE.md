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

自检会临时生成最小Word，将其转成PDF和逐页PNG，验证后自动清理。看到 `SELF_TEST_OK` 后运行：

```powershell
.\START_AGENT.cmd
```

需要指定Agent时：

```powershell
.\START_AGENT.cmd -Agent claude
.\START_AGENT.cmd -Agent opencode
```

Agent收到每个新会话的第一条消息后，必须先运行项目预检，并在首次回复开头报告结果；预检通过后才会处理你的原始消息。

## 输入什么

```text
请完整读取项目协议，然后分析法律AI产品“产品名称”，生成并质检Word报告。
```

需要参考报告时，在同一条消息中提供绝对路径，并说明它只用于模仿结构和写法，不能作为目标产品的事实证据。

## 如何确认没有写错项目

启动器会显示 `Project root` 和 `Output root`。Agent必须：

1. 确认当前绝对目录与 `LEGAL_AI_PROJECT_ROOT` 相同；
2. 运行 `python scripts/create_task_workspace.py --task-id <唯一任务ID>`；
3. 只向返回的绝对 `TASK_OUTPUT_DIR` 写文件。

如果出现 `TASK_WORKSPACE_FAIL`，不要改用父目录、同级旧项目或历史任务目录；应先纠正工作目录并重新启动Agent。

## 正常结果

分配的任务目录至少应出现：

- `task_context.json`
- `report.docx`
- `sources.md`
- `capability_declaration.md`
- `run_summary.md`
- `process_optimization_report.md`（记录真实耗时、工具、失败重试、瓶颈和下一轮优化建议）
- `render/report.pdf`
- `render/page-*.png`

只有确定性验收、最终逐页视觉检查和过程优化报告都完成时，`run_summary.md`才能写总体PASS。完成后，Agent必须在回复中明确列出 `report.docx` 与 `process_optimization_report.md` 的文件名和绝对路径。

## 正常停止情形

缺少联网或正文读取能力、产品身份不明确、关键证据不足、无法生成Word/PDF/页面图片、无法视觉检查或根目录绑定不一致时，Agent应停止或标为PARTIAL，不得凭模型记忆补写。
