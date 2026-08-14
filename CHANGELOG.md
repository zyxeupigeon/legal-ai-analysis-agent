# 变更记录

## 1.7.0 - 2026-08-14

- Upgraded to `portable-agent-1.0` / P3.6 with a one-use direct-image capability challenge and receipt-bound task allocation. Text-only or geometry-only inspection is now a hard BLOCKED condition.
- Added the canonical report renderer. It owns rendering trace events, records failures and retries, and writes only `report.docx`, `render/report.pdf`, and `render/page-*.png`.
- Validation now rejects unmanifested duplicate DOCX/PDF/page images, requires failure observations for failed events, and normalizes URLs that touch CJK punctuation or prose.
- Replaced the plain-text showcase guide with the Markdown showcase guide for clearer GitHub rendering and easier Agent consumption.
- Verified the private GitHub ZIP as a no-Git fresh copy and confirmed live OpenCode/DeepSeek safe-stop behavior when image input is unavailable.


## 1.6.0 - 2026-08-14

- 协议升级为 `portable-agent-0.9`、项目阶段升级为P3.5；每份完整报告新增 `report_diff.json`、`report_diff.md` 和 `report_manifest.json`。
- 自动选择当前项目中同一产品、状态为PASS或PARTIAL且全部产物哈希有效的最近历史报告；首次运行仍生成明确的基线记录。
- 版本差异覆盖逐条主张、分析结论、高时效事实、来源URL，以及来自真实执行轨迹的阶段耗时、失败和重试变化。
- 核心产物按任务相对路径、字节数和SHA-256封存；产物被事后改动、差异/清单顺序错误或运行摘要状态不一致时验收失败。

## 1.5.0 - 2026-08-14

- 协议升级为 `portable-agent-0.8`、项目阶段升级为P3.4；新增Agent无关的 `execution_trace.json` 真实执行轨迹。
- 任务目录分配时自动初始化轨迹；研究、证据、Word、渲染和视觉质检阶段必须由记录器写入真实开始、结束、耗时、失败与重试。
- 新增轨迹封存和敏感认证信息防护；缺失阶段、未闭合事件、无优化建议或疑似密钥内容会被拒绝。
- `process_optimization_report.md` 改由封存轨迹自动生成并绑定SHA-256；轨迹事后改动或报告与轨迹不匹配时验收失败。


## 1.4.0 - 2026-08-14

- 协议升级为 `portable-agent-0.7`，新增逐条 `claim_evidence.json` 证据账本；当前模型/产品版本、价格、运营主体和政策状态必须绑定本轮一级官方来源。
- 输出验收器新增主张来源绑定、分析依赖、未核验事实禁入正文和 profile 禁用事实模式检查。
- Word 数据表首行必须设置跨页重复表头；验收器直接检查 `w:tblHeader`，避免续页失去列含义。
- `START_AGENT.cmd`、预检和文档链路自检改为 Python 入口，不再执行下载的未签名 `.ps1` 文件，避免 Windows MOTW/RemoteSigned 阻断。
- 新增通义法睿真实试用回归 profile，冻结截至 2026-08-14 的无来源 Qwen3.8 误写问题。

## 1.3.0 - 2026-08-12

- 协议更新为 `portable-agent-0.6`，增加报告生成前的 `SESSION_PREFLIGHT_READY` / `SESSION_PREFLIGHT_BLOCKED` 硬闸门。
- 需要使用者确认非低风险修复、安装、授权、登录、重启或关键能力无法在当前会话恢复时，不创建任务目录、不研究、不生成正式报告，只报告阻断信息与操作要求。
- 仅允许无需确认、无需重启的无风险或低风险自动修复；修复后必须重新预检。
- 任务分配器新增必填 `--session-gate READY`，BLOCKED 会话无法创建任务目录。

## 1.2.0 - 2026-08-12

- 基于首次真实报告验收将协议更新为 `portable-agent-0.5`。
- 任务开始时快照协议、Agent入口、任务脚本和内置验收profile；验收时检测任务期间的项目文件改动，禁止通过修改测试配置绕过验收。
- 验收输出增加运行摘要声明状态，明确结构性OK不等于总体PASS。
- 对异常稀疏的末页给出版式告警，提醒检查续表、分页与大面积留白；告警不替代人工逐页视觉检查。
- 修正得理法搜验收profile：正式报告只要求稳定产品标签，不再要求历史“P3.0端到端测试稿”标签。

## 1.1.0 - 2026-08-12

- 协议更新为 `portable-agent-0.4`；每个新会话在处理第一条消息前必须自动执行项目预检并报告结果。
- 完整报告交付时必须明确告知正式报告与过程优化报告的文件名和绝对路径。
- 新增 `process_optimization_report.md` 及固定模板，记录真实执行耗时、工具、失败重试、瓶颈、质量风险和分级优化建议。
- 自动验收器强制检查过程优化报告的存在、结构和生成顺序。
- GitHub仓库继续保持私有，分享方式为手动发送ZIP。
## 1.0.0 - 2026-08-11

- `main`切换为P3.2便携式Agent专用项目，移除冻结网页前端、FastAPI后端、网页启动脚本及对应测试。
- 新增启动器绝对根目录环境绑定和任务目录分配器；根目录、项目副本或任务ID不一致时安全停止。
- 所有任务产物必须写入分配器返回的绝对 `TASK_OUTPUT_DIR`，不再允许用相对路径猜测输出位置。
- 协议更新为 `portable-agent-0.3`，CI改为便携式Agent基线与脚本测试。

## 0.9.0 - 2026-08-11

- 增加 `START_AGENT.cmd -SelfTest`，真实验证DOCX、PDF和逐页PNG链路。
- 分别报告基本启动能力与本地文档链路状态。
- 修复中文路径下PDF渲染器包装器失效问题。
- 统一项目根目录短版使用说明。

## 0.8.0 - 2026-08-11

- 进入可自行试用状态，完成Claude Code和OpenCode主路径验证。
- 增加统一Agent协议、Windows启动器、能力预检、隔离输出和确定性验收。
- 增加成熟开源组件发现、许可证与成熟度核验及近似候选人工判断规则。
