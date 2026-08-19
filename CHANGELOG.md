# 变更记录

## 1.12.0 - 2026-08-19

- 报告定位从"信息盘点"升级为"标杆分析式"：报告结构模仿标杆分析报告排版（执行结论 → 原始问题与报告范围 → 当前研究状态 → 分析视角（行业与竞争结构/客户与目标用户/产品画像/演进与商业/安全隐私与专业责任/竞争论点与市场定位）→ 关键洞察 → 战略匹配与机会观察 → 证据强度与无法证明事项 → 主要数据来源一览）；产品身份、功能、价格、生态、隐私等基本信息完整覆盖于对应分析视角之中，不因模仿排版而丢失。
- `PROJECT_AGENT_PROTOCOL.md` 目的部分新增"分析判断层"定位：帮助读者理解目标产品在行业中的位置与商业逻辑；分析判断与事实、企业声明分开表达，标注证据边界与成立条件，不构成对目标产品的测试、推荐或投资、采购建议（"面向从未使用目标产品的普通读者"定位与"不评价、测试或推荐"边界不变）。
- `WORKFLOW.md` 报告结构改为两段式（第一部分产品基本信息必须完整覆盖，第二部分战略分析基于前文事实展开、证据不足可缩减）；`SYSTEM_PROMPT.md` 5.5 与 `SKILL.md` 7.2 同步战略分析层写法。
- 核心规范包版本 `agent_core` 保持 1.3；同步更新三个冻结基线哈希。

## 1.11.0 - 2026-08-19

- 报告写作改为"分析叙事为主、表格为辅"：核心规范（SYSTEM_PROMPT / WORKFLOW / Skill）新增自然段与表格配比要求——每个信息维度先以完整段落陈述事实（可内联来源或主张引用），再形成一段基于前述事实的分析判断；表格只用于时间线、能力/竞品对比矩阵、价格与套餐等结构化并列数据；禁止"字段—公开信息—证据"式三列表铺满正文；正文自然段文字量应明显多于表格（表格字符通常不超过正文三分之一）；执行摘要与初步判断以段落形式给出。
- 依据：与 Claude 原生生成的 Legora V2 标杆报告对比（自然段承载分析、内联证据编号、86 段 / 7927 字 / 表格字符占比 34%），项目报告被证据盘点式三列表主导（63 段 / 4114 字 / 表格字符占比 194%）、分析层不足。
- 核心规范包版本 `agent_core` 1.2 → 1.3（文件路径保持 `agent/core/v1.2` 目录以兼容入口引用）；同步更新三个冻结基线哈希。

## 1.10.0 - 2026-08-19

- 协议升级为 `portable-agent-1.1`、项目阶段升级为 P3.9，新增「能力适配边界」：视觉检查（direct image inspection）与网页检索、正文读取并列，可通过经批准的能力适配通道补足；目标产品访问、事实核验、来源绑定仍为不可适配能力，缺失必须 BLOCKED。
- hard gate 1 探针码来源规则修订：可由会话模型自身视觉、经批准的视觉适配通道或使用者人眼读取，但必须在 capability receipt 中声明 `--visual-channel`；从 OCR、PDF 几何、源文件、哈希或**非声明通道**获取仍被禁止。
- 视觉适配通道必须满足四条件（真实读图、可审计调用记录、执行者登记、使用者最终确认）；通道登记是项目维护动作，运行任务的 Agent 不得自行登记。
- capability receipt 新增 `visual_channel` 与 `visual_channel_evidence_sha256` 字段；非 human 通道必须附带通道调用记录。
- 页面质检结论必须由使用者人工确认（同会话确认即可、记录在案、先于 PASS）方可作为 PASS 依据；能力声明必须拆分主模型能力与通道能力。
- 新增 `scripts/visual_qa_dashscope.py --read-probe` 探针读码模式，输出可核验的通道调用记录（图像 SHA-256、通道标识、时间戳、返回原文）。
- 实测：`qwen3-vl-plus` 读点阵探针码多次哈希校验失败（`17663`/`172653`/`096347` 均未通过），判定探针环节固定使用 human 人工通道（实测签发 receipt 成功）；页面质检通道验证通过（legora 报告 9 页）。
- 端到端验证：`legora-20260819`（protocol 1.1）总体 PASS——human 探针签发一次性凭证 + qwen3-vl-plus 通道页面质检 + 使用者人工确认；`VERSION_MANIFEST.yaml` `validated_hosts` 登记为 `claude_code_deepseek_human_visual_probe_qwen3vl_page_qa`。
- 加固：探针图改为 PyMuPDF 标准字体抗锯齿渲染（原像素矩阵保留为 fallback），提升视觉模型读码率；`verify` 新增两道校验——视觉通道必须在 `docs/VISUAL_CHANNEL_REGISTRY.md` 机器可读清单中登记（human 除外），evidence 内容须与探针图 SHA-256、visual_code、通道 ID 一致，伪造通道或伪造证据将被拒绝。
- 待办：1.1 的 validated_hosts 尚为空白，需完成堵法有效性测试用例后再登记验证记录。

## 1.9.0 - 2026-08-18

- 项目阶段升级为P3.8公开信息分析语义统一版，新增规范词表 `CONTEXT.md`，统一项目协议、Agent 核心规范、使用说明和验收测试中的业务语言。
- 目标读者统一为“从未使用目标法律AI产品、希望先建立基本认识的普通读者”，不预设其具备法律、技术、采购或投资专业背景。
- 项目目的统一为基于免费、公开、无需登录且可追溯的信息形成带证据边界的初步认识，帮助读者区分公开事实、企业声明、分析判断与尚未证明事项。
- 分析范围统一为目标产品及与其存在明确法律业务协同的同企业产品与能力；章节随公开证据充分度缩减，不承诺固定章节全覆盖。
- 报告成功标准统一为报告流程状态 PASS/PARTIAL/FAIL，只判定公开研究、证据绑定、文档生成和质量检查流程，不评价、测试或推荐目标产品；知识库写入完成或待入库记录已生成是独立的知识沉淀状态。
- 交付统一按主交付物、审计交付物、渲染交付物、对话交付四层组织；审计和渲染交付物均不替代主交付物。
- 范围契约测试新增词表统一断言，防止上述措辞回退。
- 同步 Repository Checks 的版本门禁断言至 P3.8，修复因 P3.7 提交未推送而遗留的过时 CI 检查。

## 1.8.0 - 2026-08-17

- 项目阶段升级为P3.7公开信息分析版，目标读者明确为从未接触目标法律AI、希望先了解大致信息的用户。
- 正式报告只使用免费、公开、无需登录的资料；目标产品注册、登录、付费、充值、API/MCP/Skills调用、文件上传和功能实测全部改为项目范围外。
- 报告PASS仅表示公开信息研究、证据绑定、文档生成和逐页质检流程通过，不表示目标产品通过测试或获得推荐。
- 默认报告结构改为产品身份、历程、定位、目标用户、公开功能、价格、接入披露、隐私责任、公共信号、证据边界和初步判断。
- 核心规范升级至v1.2，用户指南改名为 `docs/PUBLIC_INFORMATION_GUIDE.md`，并新增范围契约测试防止后续回退。
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
- 新增通义法睿公开信息报告回归 profile，冻结截至 2026-08-14 的无来源 Qwen3.8 误写问题。

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
