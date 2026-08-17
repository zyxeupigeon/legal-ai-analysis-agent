# Legal AI Analysis Agent

面向首次了解某款法律AI产品的用户，以免费、公开、无需登录的信息完成产品概览、证据核验、Word报告生成和逐页质检的便携式Agent工作目录。

当前版本为P3.7公开信息分析版，GitHub仓库保持私有，通过手动发送ZIP分享。项目不绑定特定Agent、模型、模型API、浏览器或MCP；使用者负责安装并登录一个具备所需能力的命令行或图形Agent。

## 项目定位

输入一个明确的法律AI产品名称，Agent会自主查找免费公开资料，区分已核实事实、企业公开声明和分析判断，并生成适合初次了解该产品的分析报告。

本项目不注册或登录目标产品，不购买、充值、调用目标产品API/MCP/Skills，不上传文件，不操作产品功能，也不测试准确率、稳定性或实际效果。报告可以介绍厂商公开披露的功能和接入方式，但必须明确这不等于本项目已经实际验证。报告PASS只代表公开信息研究和文档质量流程通过。

## Windows首次使用

在项目根目录打开PowerShell，先运行真实文档链路自检。启动器与预检器均使用 Python，不执行下载的未签名 `.ps1` 文件，因此不需要修改 PowerShell 执行策略或文件信任标记：

```powershell
.\START_AGENT.cmd -SelfTest
```

看到 `SELF_TEST_OK` 后启动Agent：

```powershell
.\START_AGENT.cmd
```

当前启动器可识别Claude Code、OpenCode、Codex CLI和Gemini CLI；已完成端到端验证的是Claude Code和OpenCode。

> Portable-agent 1.0 requires a one-use direct-image capability probe before task allocation. A text-only Agent must return `SESSION_PREFLIGHT_BLOCKED` before report generation.

Agent收到新会话的第一条消息后，会先自动执行项目预检和能力闸门。只有回复 `SESSION_PREFLIGHT_READY` 才会继续；若回复 `SESSION_PREFLIGHT_BLOCKED`，不会生成报告，而会说明需要你确认、处理或重启的事项。进入Agent后输入：

```text
请完整读取项目协议，只使用免费、公开、无需登录的信息分析法律AI产品“得理法搜”，不得注册、付费、调用接口或实测产品；生成并质检Word报告。
```

## 输出目录安全

启动器会把当前项目的绝对路径写入 `LEGAL_AI_PROJECT_ROOT`。Agent在写入任何任务文件前必须运行：

```powershell
python scripts/create_task_workspace.py --task-id <本次唯一任务ID> --session-gate READY --capability-receipt "<CAPABILITY_RECEIPT>"
```

只有返回 `TASK_WORKSPACE_OK` 后才能继续，全部产物必须写入返回的绝对 `TASK_OUTPUT_DIR`。若Agent复用了另一份项目副本、旧会话或错误工作目录，分配器会停止任务，避免报告写到同级旧项目。

After the receipt is issued, generate the formal file directly as `report.docx` and run `python scripts/render_report.py "<TASK_OUTPUT_DIR>"`. The canonical renderer records rendering failures and retries and writes only `render/report.pdf` plus `render/page-*.png`.

分配器还会自动初始化 `execution_trace.json`。Agent必须用 `scripts/record_execution_event.py` 记录阶段开始、结束、失败和重试；完成逐页质检后封存轨迹，再用 `scripts/build_process_optimization_report.py` 从真实记录生成优化报告。具体命令见 `docs/EXECUTION_TRACE_SCHEMA.md`。

优化报告完成后，Agent会用 `scripts/compare_report_versions.py` 自动寻找同一产品最近的有效历史报告，生成机器可读和人类可读差异，再用 `scripts/build_report_manifest.py` 封存核心产物的大小和SHA-256。没有历史报告时会建立首次基线；详见 `docs/REPORT_VERSIONING.md`。

## 正常交付物

每个任务目录至少应包含：

- `task_context.json`
- `execution_trace.json`（真实阶段、耗时、失败重试和优化观察的机器可验收轨迹）
- `report.docx`
- `sources.md`
- `claim_evidence.json`（逐条主张、来源和正文位置的机器可验收账本）
- `capability_declaration.md`
- `run_summary.md`
- `process_optimization_report.md`（本次报告生成过程复盘和下一轮优化建议）
- `report_diff.json`、`report_diff.md`（与同一产品最近有效报告的结构化和可读差异；首次运行建立基线）
- `report_manifest.json`（核心产物路径、大小和SHA-256清单）
- `render/report.pdf`
- `render/page-*.png`

只有确定性验收、独立逐页视觉检查、过程优化报告、版本差异和产物清单均完成时，运行摘要才能写总体PASS。验收器输出结构性OK不代表总体PASS；以运行摘要声明的PASS、PARTIAL或FAIL为准。报告任务不得修改项目协议、脚本或验收配置。Agent最终回复必须明确给出正式报告、过程优化报告和人类可读版本差异的文件名及绝对路径。

## 项目边界

- 只研究免费、公开、可核验且无需登录的资料。
- 不注册、登录、付费、充值、调用目标产品API/MCP/Skills、上传材料或实测产品；不对准确率和实际效果作实测结论。
- 不把密钥、账号、客户资料、参考报告或运行产物提交到Git。
- 输出是研究测试材料，不构成法律意见。
- 网页应用、FastAPI后端及其运行依赖已从 `main` 移除；历史代码仍可从Git历史和 `archive/p2.3.4-web` 分支取得。

Quick display and usage guide: [`项目成果展示与使用说明.md`](项目成果展示与使用说明.md).

详细步骤见 `docs/PUBLIC_INFORMATION_GUIDE.md`，版本管理规则见 `docs/REPORT_VERSIONING.md`，唯一业务协议见 `PROJECT_AGENT_PROTOCOL.md`。

## 开发检查

```powershell
python scripts/check_baselines.py
python -m pytest -q
.\START_AGENT.cmd -CheckOnly
.\START_AGENT.cmd -SelfTest
```
