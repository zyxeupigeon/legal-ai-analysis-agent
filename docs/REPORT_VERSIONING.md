# 报告版本管理与差异规范

每次完成正式报告后，Agent必须为当前任务生成 `report_diff.json`、`report_diff.md` 和 `report_manifest.json`。这些文件只存在于Git忽略的任务输出目录，不进入正式Word正文，也不得提交到仓库。

## 固定生成顺序

完成逐页视觉质检后，按以下顺序执行：

```powershell
python scripts/record_execution_event.py finalize "<TASK_OUTPUT_DIR>"
python scripts/build_process_optimization_report.py "<TASK_OUTPUT_DIR>" --subject "<法律AI产品名称>" --agent "<Agent名称>" --model "<模型名称或未记录>" --status <PASS|PARTIAL|FAIL>
python scripts/compare_report_versions.py "<TASK_OUTPUT_DIR>" --subject "<法律AI产品名称>"
python scripts/build_report_manifest.py "<TASK_OUTPUT_DIR>" --subject "<法律AI产品名称>" --status <PASS|PARTIAL|FAIL>
```

随后才可最后写入或更新 `run_summary.md`，并运行 `scripts/validate_portable_agent_output.py`。若报告、来源、证据账本、轨迹、差异文件或渲染页在清单生成后发生变化，必须重新生成差异、清单和运行摘要。

## 历史基线选择

对比器只扫描当前项目副本的 `agent_outputs`，并只选择满足全部条件的最近历史任务：

- 产品名称经NFKC标准化、去除首尾空白并忽略大小写后得到相同 `subject_key`；
- `report_manifest.json` 使用受支持的格式，状态为PASS或PARTIAL；
- 清单内全部核心产物仍存在，大小和SHA-256全部匹配；
- 任务目录仍位于当前项目副本中。

没有合格历史任务时，仍会生成两个差异文件，并明确标记为首次基线。不得因产品文件夹名称相似、任务ID相似或报告正文中偶然出现同名词而错误配对。

## report_diff.json

格式版本为 `1.0`，记录：

- 当前任务、产品名称和不可逆短哈希 `subject_key`；
- 基线是否存在、基线任务ID和完成时间；
- 按 `claim_id` 对比的新增、移除和修改主张；
- `claim_type=analysis` 的分析结论变化；
- 当前模型/产品版本、价格、运营主体和政策状态等高时效事实变化；
- 来源URL新增和移除；
- 当前与基线执行轨迹的总耗时、阶段耗时、尝试、失败和重试差值；
- 下轮复核提醒。

`report_diff.md` 是同一数据的人类可读版本。结构化对比不能替代正文语义和页面视觉的人工检查。

## report_manifest.json

格式版本为 `1.0`。清单记录任务ID、协议、产品、完成时间、最终状态、基线任务ID，以及每个核心产物的任务相对路径、角色、字节数和SHA-256。清单至少覆盖：

- 任务上下文和已封存执行轨迹；
- Word、来源、逐条证据账本和能力声明；
- 过程优化报告；
- 机器可读和人类可读版本差异；
- 最终PDF和全部逐页PNG。

清单不包含自身，也不包含必须最后写入的 `run_summary.md`，从而避免循环哈希。验收器会验证清单、差异文件、运行摘要状态和生成先后顺序；任一不一致都必须失败。

## 安全边界

- 命令行中的产品名称不得包含密钥、认证头、口令或客户端密钥等认证材料。
- 不读取当前项目外的历史报告，不复制网页正文，也不保存登录或付费内容。
- 旧报告清单校验失败时直接跳过，不用未验证的历史内容参与比较。
- 版本差异是研究变化提示，不构成法律意见或自动事实确认。
