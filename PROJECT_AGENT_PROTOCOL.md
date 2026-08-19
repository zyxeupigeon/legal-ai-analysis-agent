# 法律AI产品分析项目 Agent 协议

协议编号：portable-agent-1.1

## 目的

本仓库是一个可由不同本地命令行或图形 Agent 接管的工作目录。使用者在仓库根目录启动已有 Agent；项目不绑定特定厂商、模型、模型 API、浏览器或 MCP。

## 公共信息分析定位

本项目面向从未使用目标法律AI产品、希望先建立基本认识的普通读者，不预设其具备法律、技术、采购或投资专业背景。正式任务只收集免费、公开、无需登录且可追溯的信息，帮助目标读者区分公开事实、企业声明、分析判断与尚未证明事项，形成带来源和证据边界的初步分析报告。

- 产品名称是唯一必填输入；Agent 自主完成公开检索、正文读取、交叉核验、报告撰写和逐页质检。
- 可以记录官网公开披露的 API、MCP、Skills、价格、功能和客户案例，但只能证明“公开材料这样描述”，不能证明相关能力已经过本项目实际使用验证。
- 不注册目标产品账号，不登录目标产品，不购买订阅或内容，不充值，不调用目标产品 API、MCP 或 Skills，不上传文件，不操作目标产品功能，也不使用真实案件或客户材料。
- 不对目标产品的准确率、稳定性、召回率、幻觉率、实际效率或专业效果作实测结论；缺少公开独立证据时明确写“无法从公开资料证明”。
- 报告中的 PASS 只表示本项目的公开信息研究、文档生成和质量检查流程完整通过，不表示目标法律AI产品通过测试或获得推荐。
- 注册、付费、接口调用、产品操作和准确率基准测试均不属于本项目后续完成条件，也不因使用者拥有账号、密钥或预算而自动纳入。
- 分析对象限于目标产品及与其存在明确法律业务协同的同企业产品与能力，具体章节取决于本轮公开证据；完整只指流程和证据链完整，不指固定章节、全量生态或所有问题均有结论。

## 启动和任务目录绑定

1. **新会话的第一项动作必须是项目预检。** 无论使用者第一句话是分析请求、普通问题、问候还是其他内容，Agent 都必须先确认当前工作目录和根目录绑定，完整读取本协议，并运行 `python scripts/check_agent_workspace.py`。该入口不得依赖执行下载的未签名 PowerShell 脚本。在预检完成前，不得实质回答问题、开始研究或调用任务工具。
2. `PREFLIGHT_BASE_OK` 只表示基础目录与本机文档链路检查结束，不等于当前会话能够正常完成项目。Agent 还必须检查原始请求所需的联网检索、网页正文读取、Word生成、PDF/PNG渲染、图片查看和其他关键能力。
3. 自检后必须二选一声明：
   - `SESSION_PREFLIGHT_READY`：当前会话可在无需使用者额外决定、无需重启或重新登录的情况下，直接正常执行原始请求；
   - `SESSION_PREFLIGHT_BLOCKED`：存在会阻止当前会话直接正常执行项目的条件。
4. 只有无风险或低风险、无需使用者确认且无需重启的修复可以自动执行，例如清理本次临时探针、纠正项目内命令、使用已安装的等效工具或调整当前进程的非安全性编码设置。自动修复后必须重新预检；复检通过才能声明 READY。
5. 出现以下任一情况必须声明 BLOCKED：需要使用者在多种非低风险方案中选择；需要更改执行策略、安全策略、系统配置或文件信任标记；需要安装关键依赖、登录或重新认证、启用浏览器/MCP/插件、扩大权限；需要重启 Agent、终端、电脑或应用；关键能力在当前连续会话中无法立即恢复；或其他会使接下来的对话不能直接正常运行完整项目的情形。
6. BLOCKED 时不得运行任务目录分配器，不得开始事实研究，不得创建 `report.docx`、草稿报告或其他正式报告产物。必须立即告诉使用者：阻断项、影响、为什么不能直接继续、建议操作、风险和是否需要重启；等待使用者处理并开启可用会话后重新自检。
7. 即使已开始任务，若在正式报告生成前发现新的上述阻断条件，也必须停止，不得用降级能力生成冒充完整结果的报告；可以保留已产生的诊断记录，但不得生成正式 Word。
8. 确认当前工作目录是本仓库根目录，即当前目录中同时存在 `START_AGENT.cmd`、`PROJECT_AGENT_PROTOCOL.md` 和 `scripts/create_task_workspace.py`。若环境变量 `LEGAL_AI_PROJECT_ROOT` 存在，其绝对路径必须与当前仓库根目录完全相同；不同时声明 BLOCKED。
9. 完整阅读 `agent/core/v1.2/SYSTEM_PROMPT.md`、`agent/core/v1.2/WORKFLOW.md` 和目标任务涉及的 Skill。涉及寻找、比较、采用或替换开源项目时，还必须完整阅读 `OPEN_SOURCE_DISCOVERY_PROTOCOL.md`。
10. 只有声明 `SESSION_PREFLIGHT_READY` 后，才可在写入任何任务文件前运行：

   `python scripts/create_task_workspace.py --task-id <本次唯一任务ID> --session-gate READY --capability-receipt "<CAPABILITY_RECEIPT>"`

11. 只有看到 `TASK_WORKSPACE_OK` 后才能继续，并且必须把其返回的绝对 `TASK_OUTPUT_DIR` 作为本次唯一写入目录。若闸门不是 READY、任务目录已存在、当前目录不正确或根目录绑定不一致，分配器会失败；此时必须停止并向使用者报告，不得改写到另一位置。

## 最低能力要求

执行完整法律AI产品分析的 Agent 必须能够：

- 读取仓库文件，并只向分配的任务目录写入产物；
- 运行 Python 与当前系统命令；项目预检、启动与自检不得要求执行下载的未签名 `.ps1` 文件；
- 检索公开互联网并读取来源正文，而不只读取搜索摘要；
- 保存来源 URL、访问日期及其支持的具体主张；
- 生成可编辑 `.docx`；
- 将最终 Word 渲染为 PDF 和逐页图片并进行版式检查。

浏览器、MCP、插件和具体搜索服务都只是实现方式，不是项目硬性依赖。若 Agent 没有网页检索与正文读取能力，可以要求使用者启用相应工具；在能力补足前必须停止事实研究。视觉检查能力同样可以通过经批准的适配通道补足（见「能力适配边界」），通道调用记录必须可审计；在视觉通道补足前不得声明 READY 或 PASS。

### 能力适配边界

视觉检查、网页检索与正文读取属于可适配能力：若当前会话模型自身不具备，可使用经批准的能力适配通道补足；通道是"实现方式"，与浏览器、搜索服务同级，不是项目硬性依赖。

**可适配能力**：联网检索、网页正文读取、视觉检查（direct image inspection）。
**不可适配能力**（缺失即 BLOCKED，任何通道不得补足）：目标产品注册、登录、付费、API 调用、文件上传；事实核验与来源绑定；对目标产品能力作实测结论。报告过程中任何环节都不得通过外部通道接触目标产品账户、密钥或受限内容。

**经批准的视觉适配通道必须同时满足以下全部条件**，否则不得视为 READY：

1. 真实读取图片字节并输出基于图像内容的描述，不得从文件名、路径、哈希、几何推断或会话内既有知识输出结论；
2. 输出可审计：通道调用记录（图像 SHA-256、通道标识、调用时间、返回原文）必须随执行轨迹保存，可复现复核；
3. 执行者显式登记：探针读码与页面质检必须声明实际执行通道（如 human、qwen3-vl-plus），写入 capability receipt 与任务上下文；
4. 使用者最终确认：页面质检结论必须由使用者人工确认后方可作为 PASS 依据（见交付要求）。

通道不可用时（API 失效、密钥过期、网络中断、输出不可信）等同视觉能力不可用：必须 BLOCKED 或转人工，不得静默降级为"无质检 PASS"。

报告中任何能力声明必须拆分主模型能力与通道能力：`capability_declaration` 不得把通道能力记为主模型自身能力。

**通道登记流程**：

- 通道登记是**项目维护动作**，由使用者发起并最终确认；运行任务的 Agent 不得在报告任务期间自行登记新通道、修改通道清单或任何门禁相关文件（见「不得违反的规则」）。
- 新通道登记前，必须由使用者（或使用者指定的独立维护会话）验证其满足上述全部四条件，并记录：通道标识、实现方式（脚本/服务）、版本或调用方式、验证日期与验证者；登记记录统一写入 `docs/VISUAL_CHANNEL_REGISTRY.md`。
- 运行任务的 Agent 遇到使用者希望使用但**未登记**的视觉通道时，必须停止该环节并报告"此通道未登记，按协议不得作为探针或质检通道使用"，给出选项：使用者人工复核，或使用者先完成通道登记后再继续；不得自行放行、不得自行登记。

## 不得违反的规则

- 用户必须给出明确的法律AI产品名称；身份不明确时先澄清。
- 仅使用本轮取得的公开、可核验证据；不得用模型记忆补造事实或 URL。
- 企业主体、产品、API、MCP、插件、连接器和 Skill 分层核验，不能互相推定。
- 搜索失败、正文不可读取或证据不足时，降低结论、缩减报告或停止任务。
- 事实、企业自述和分析判断必须分开表达。
- 冲突口径并列说明，不自行挑选或强行合并。
- 不访问登录、付费或受限内容，不使用目标产品账号、登录态、验证码、Cookie、密钥或余额；这类操作属于项目范围外，不以征得同意作为继续分析的分支。对外发送、发布、共享或扩大权限仍须另行取得用户明确同意。
- 不读取、输出、提交或复制 `.env`、认证缓存、令牌和其他密钥。
- 开源项目只有在功能精确匹配、许可证兼容、成熟度证据充分且隔离验证通过后才能作为替换候选；近似项目只能交由用户判断。
- 不得覆盖参考报告、冻结文件、其他任务产物或仓库外文件。
- 报告任务期间不得修改协议、Agent 入口、脚本、模板、验收器、`evaluations` 配置或其他仓库文件。若内置验收配置与正式报告目标冲突，必须停止并报告冲突，不得修改配置、降低阈值或向报告注入测试标签来通过验收。

## 交付要求

报告流程状态采用 PASS、PARTIAL 或 FAIL，只判定公开研究、证据绑定、文档生成和质量检查流程，不评价、测试或推荐目标产品。知识库写入完成或待入库记录已生成属于独立的知识沉淀状态，不得替代或改变报告流程状态。

交付按四层组织：

1. 主交付物：report.docx，供目标读者直接阅读和编辑，是正式报告的唯一主版本；
2. 审计交付物：来源、主张证据、执行轨迹、过程优化、版本差异、产物清单、运行摘要及任务上下文等侧车文件；
3. 渲染交付物：由主交付物生成的 PDF 和页面 PNG，用于逐页质检和便捷查看，不替代主交付物；
4. 对话交付：最终回复中的简明交接信息，至少列出关键文件绝对路径及报告流程状态。

完整任务至少交付：可编辑 Word 报告、来源记录、逐条主张证据账本 `claim_evidence.json`、真实执行轨迹 `execution_trace.json`、能力声明、研究边界和未解决问题、最终Word的PDF与逐页图片、视觉检查结果、运行摘要、任务上下文文件、过程优化报告、版本差异 `report_diff.json` / `report_diff.md`、防篡改产物清单 `report_manifest.json`，以及本次使用的 Agent、模型（若可知）、工具能力和协议编号。

能力声明与视觉质检确认必须满足：

- 能力声明必须拆分主模型能力与适配通道能力（例如：研究/生成 = deepseek-v4-flash；视觉质检 = qwen3-vl-plus 通道 + 使用者人工确认），不得把通道能力记为主模型自身能力；
- 视觉质检结果必须注明执行通道，并由使用者人工确认后方可作为 PASS 依据；
- 使用者人工确认的执行方式：渲染完成后 Agent 出示渲染页路径与（如有）通道质检结果，使用者在同一会话内给出确认或问题反馈；确认动作（内容、时间）记录进执行轨迹或视觉检查结果，且必须先于 PASS 判定。不要求另开会话；未确认前不得封存 PASS。

过程优化报告固定命名为 `process_optimization_report.md`，必须在正式报告完成质检后、最终回复前由 `scripts/build_process_optimization_report.py` 按照 `docs/PROCESS_OPTIMIZATION_REPORT_TEMPLATE.md` 从已封存轨迹生成。它只记录本次真实执行过程，至少包括：各阶段真实时间、实际工具与来源路径、失败和重试、主要瓶颈、无效或重复步骤、质量风险、可复用做法，以及按“收益/实现成本/风险”排序的下一轮优化建议。不得手工编造耗时，不得包含密钥、认证信息或用户敏感材料。该文件用于改进项目流程，不得混入正式 Word 正文。

### 执行轨迹与优化报告约束

任务目录分配器会自动创建 `execution_trace.json` 并记录任务目录分配事件。Agent必须按照 `docs/EXECUTION_TRACE_SCHEMA.md`，在对象确认、公开检索、证据整理、Word生成、渲染和逐页视觉质检各阶段实际开始前运行 `scripts/record_execution_event.py start`，结束后用返回的事件ID运行 `finish`；失败重试必须用 `--retry-of` 指向失败事件。开始、结束和耗时由脚本记录，不得事后估算或直接改写JSON。

在最终视觉质检结束后，Agent必须记录本轮实际观察到的失败、瓶颈、无效步骤、质量风险和可复用做法（没有发生的类别可以不写），并至少记录一条带优先级、收益、成本、风险和验证方法的 `optimization_recommendation`。随后运行：

```powershell
python scripts/record_execution_event.py finalize "<TASK_OUTPUT_DIR>"
python scripts/build_process_optimization_report.py "<TASK_OUTPUT_DIR>" --subject "<产品名称>" --agent "<Agent名称>" --model "<模型名称或未记录>" --status <PASS|PARTIAL|FAIL>
python scripts/compare_report_versions.py "<TASK_OUTPUT_DIR>" --subject "<产品名称>"
python scripts/build_report_manifest.py "<TASK_OUTPUT_DIR>" --subject "<产品名称>" --status <PASS|PARTIAL|FAIL>
```

封存前存在未闭合事件、缺少必需阶段或缺少优化建议时必须修正记录，不能绕过封存。`process_optimization_report.md` 必须由上述生成器基于封存轨迹生成并包含匹配的轨迹SHA-256；不得手工编造耗时，也不得在生成优化报告后改写轨迹。

随后必须按照 `docs/REPORT_VERSIONING.md` 生成版本差异和清单。同一分析对象只可与当前项目中产品标识相同、状态为PASS或PARTIAL且全部SHA-256校验通过的最近历史任务比较；没有合格历史报告时仍需生成首次基线差异。`report_manifest.json` 必须覆盖正式报告、来源、证据账本、封存轨迹、优化报告、差异文件、最终PDF和全部逐页PNG。清单生成后如上述文件变化，必须重新生成差异、清单和运行摘要。


最终回复必须明确给出正式报告的**文件名和绝对路径**，同时给出过程优化报告及人类可读版本差异 `report_diff.md` 的文件名和绝对路径；不得只说“已生成”“见输出目录”或仅提供相对路径。

## 兼容性原则

仓库根目录的 `AGENTS.md`、`CLAUDE.md` 和 `GEMINI.md` 是自动发现适配文件，不是三套业务规则。本文件是唯一规范来源；适配文件与本文件冲突时以本文件为准。

## 结果判定顺序

Agent不得仅根据自身执行计划或工具返回值宣称任务通过。必须按以下顺序判定：

1. 在分配的绝对任务目录生成Word、来源记录、`claim_evidence.json` 和运行摘要草稿。高风险动态事实（当前模型/产品版本、价格、运营主体、政策状态）必须逐条绑定本轮实际读取的一级官方来源；未核验事实不得进入正文。
2. 从最终Word重新生成PDF与逐页图片。
3. 独立查看最终版全部页面（查看方式可为会话视觉、经批准的适配通道或使用者复核，须在视觉检查结果中注明实际执行者），记录裁切、重叠、缺字、表格越界、异常空白和分页问题，并完成必要修复。所有数据表的首行必须设置为跨页重复表头；跨页后失去列含义不得通过验收。
4. 闭合所有执行事件、记录至少一条优化建议并封存 `execution_trace.json`，再由项目生成器创建与轨迹SHA-256绑定的 `process_optimization_report.md`。
5. 生成 `report_diff.json` 和 `report_diff.md`；若存在同一对象且清单有效的最近历史任务，自动比较主张、分析结论、高时效事实、来源和执行效率，否则建立首次基线。
6. 生成 `report_manifest.json`，封存核心产物的任务相对路径、大小和SHA-256；清单必须晚于其覆盖的差异及报告产物。
7. 最后更新运行摘要，使其修改时间晚于最终Word、全部渲染页、过程优化报告和产物清单，并使PASS、PARTIAL或FAIL与清单一致。
8. 运行项目提供的确定性输出验收器；有测试对象配置时必须加载对应profile。验收器的结构性 `OK` 不等同于总体 `PASS`，最终状态以运行摘要中如实声明的 PASS、PARTIAL 或 FAIL 为准。
9. 只有确定性验收、独立视觉检查、过程优化报告、版本差异和产物清单均完成，运行摘要才可写总体PASS；否则必须写FAIL或PARTIAL并列出缺口。

## Portable-agent 1.1 hard gates

1. Before declaring `SESSION_PREFLIGHT_READY`, run `python scripts/session_preflight_gate.py prepare`. Read the emitted `PROBE_IMAGE` with the direct image-view capability this session will use for final report pages: the session model's own vision, an approved visual adapter channel (see 能力适配边界), or the user's own eyes. The actual reader must be named in the capability receipt (`--visual-channel`). Do not obtain the code from OCR, PDF geometry, source files, hashes, or from any model/tool that is not the declared visual channel. When the code comes from an approved adapter channel, its call record (probe image SHA-256, channel id, timestamp, raw output) must be kept with the execution trace and verifiable.
2. After direct image inspection and real tests of internet search plus full-page reading, run `python scripts/session_preflight_gate.py verify --challenge-id <CHALLENGE_ID> --visual-code <SIX_DIGIT_CODE> --internet-search READY --page-reading READY --word-generation READY --pdf-png-rendering READY`. A successful command emits a one-use `CAPABILITY_RECEIPT`.
3. If direct image inspection (including every approved visual adapter channel), full-page reading, permissions, or any other required capability is unavailable in the current continuous session, declare `SESSION_PREFLIGHT_BLOCKED`. A channel that fails, is unreachable, or cannot be verified does not count as available; do not silently downgrade to an uninspected PASS. Target-product authentication is outside this project and is never a READY requirement. Geometry-only PDF checks are not a substitute for direct final-page inspection and must not be used to declare READY or PASS.
4. Task allocation requires the one-use capability receipt. A receipt from another project copy, an expired receipt, or a consumed receipt must be rejected.
5. Generate the editable report directly as `<TASK_OUTPUT_DIR>/report.docx`. Render it only with `python scripts/render_report.py "<TASK_OUTPUT_DIR>"`; this command owns the rendering execution event, records failures, links retries, and writes only `render/report.pdf` plus `render/page-*.png`.
6. Every failed or blocked execution attempt must be closed immediately with its real status before retrying. A finalized trace containing a failed or blocked event must include a `failure` observation, so the process optimization report cannot state that no failure occurred.
7. Do not leave alternate `.docx`, `.pdf`, or root-level `page-*.png` copies in the task directory. The manifest and final validator reject unmanifested formal duplicates.
