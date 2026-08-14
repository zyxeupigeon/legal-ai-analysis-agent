# execution_trace.json 规范

每个已通过会话预检并创建任务目录的正式报告任务，都必须在任务目录维护 execution_trace.json。它记录报告生成过程中的真实阶段时间、工具、产物、失败、重试和优化观察，不进入正式 Word 正文，也不得包含密钥、认证信息或用户敏感材料。

## 自动初始化

运行以下命令后，任务分配器会同时创建 task_context.json 和 execution_trace.json，并自动写入 workspace_allocation 成功事件：

```powershell
python scripts/create_task_workspace.py --task-id <唯一任务ID> --session-gate READY
```

不要手工新建、复制或修改轨迹文件。

## 阶段事件

正式报告必须成功覆盖以下阶段：

| stage | 含义 |
|---|---|
| workspace_allocation | 任务目录分配，由分配器自动记录 |
| target_scoping | 分析对象识别与研究范围 |
| research | 公开检索与网页正文读取 |
| evidence_analysis | 来源、冲突和主张证据整理 |
| report_generation | Word报告生成 |
| rendering | 最终Word转PDF和逐页PNG |
| visual_qa | 独立逐页视觉检查 |

修复可使用 remediation，其他确有必要的动作可使用 other。

在阶段实际开始前运行：

```powershell
python scripts/record_execution_event.py start "<TASK_OUTPUT_DIR>" --stage research --action "读取公开来源正文" --tool "当前实际使用的工具"
```

命令返回 event_id。阶段结束后必须用该ID闭合：

```powershell
python scripts/record_execution_event.py finish "<TASK_OUTPUT_DIR>" --event-id E0002 --status succeeded --artifact sources.md
```

status 可为 succeeded、failed、blocked 或 skipped。失败后重试时，新事件必须添加 --retry-of <失败事件ID>。开始、结束和耗时由脚本记录，Agent不得事后估算或直接改写时间。

## 过程观察

发生失败、瓶颈、无效步骤、质量风险或发现可复用做法时，使用 observe 记录。每次任务至少要记录一条 optimization_recommendation，并填写优先级、预期收益、成本、风险和验证方法：

```powershell
python scripts/record_execution_event.py observe "<TASK_OUTPUT_DIR>" --stage visual_qa --kind optimization_recommendation --summary "下一轮建议" --impact "本轮观察到的影响" --priority P1 --expected-benefit "预期收益" --implementation-cost "低/中/高" --risk "风险或副作用" --validation-method "下一轮如何验证"
```

## 封存与优化报告

完成最终Word、渲染和逐页视觉质检后，先封存轨迹：

```powershell
python scripts/record_execution_event.py finalize "<TASK_OUTPUT_DIR>"
```

封存会拒绝未闭合事件、缺失的必需阶段和缺失的优化建议。封存后轨迹不可再通过记录器修改。

随后由项目脚本生成优化报告：

```powershell
python scripts/build_process_optimization_report.py "<TASK_OUTPUT_DIR>" --subject "<法律AI产品名称>" --agent "<Agent名称>" --model "<模型名称或未记录>" --status PASS
```

生成器会把轨迹SHA-256写入 process_optimization_report.md。最终验收器会重新计算哈希；轨迹被事后改动、优化报告早于轨迹，或二者不匹配时，验收失败。

## 安全边界

- 只记录任务执行事实，不记录提示词全文、网页正文全文或用户材料全文。
- action、tool、note和观察字段不得写入令牌、API密钥、密码、Authorization头或其他认证信息。
- artifacts只使用任务目录内的相对路径，不使用绝对路径或 ..。
- execution_trace.json属于运行产物，受Git忽略规则保护，不得提交到仓库。
