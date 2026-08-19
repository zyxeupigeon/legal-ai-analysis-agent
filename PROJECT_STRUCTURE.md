# 项目目录说明

当前 `main` 是P3.8公开信息分析语义统一版便携式Agent项目。旧网页应用已从主分支移除，可从Git历史和 `archive/p2.3.4-web` 分支恢复。

| 路径 | 职责 |
|---|---|
| `CONTEXT.md` | 规范领域词表，统一目标读者、项目目的、分析范围、成功标准和交付层级语义 |
| `PROJECT_AGENT_PROTOCOL.md` | 唯一业务协议、能力边界和任务目录绑定规则 |
| `AGENTS.md`、`CLAUDE.md`、`GEMINI.md` | 不同Agent的自动发现入口 |
| `agent/core/v1.2` | 冻结的系统提示词、工作流和任务边界摘要 |
| `agent/skills/legal-report-review-and-verification` | 锁定并校验哈希的法律报告Skill |
| `OPEN_SOURCE_DISCOVERY_PROTOCOL.md` | GitHub成熟组件发现、筛选和替换判定规则 |
| `scripts/start_agent.py` | Agent检测与启动，不执行下载的PowerShell脚本 |
| `scripts/check_agent_workspace.py` | 项目根目录、文件、Python和文档工具预检 |
| `scripts/session_preflight_gate.py` | One-use direct-image capability challenge and session receipt |
| `scripts/render_report.py` | Canonical report.docx to render/report.pdf and page PNG renderer with failure/retry tracing |
| `scripts/create_task_workspace.py` | 创建绑定当前项目副本的唯一绝对任务目录 |
| `scripts/record_execution_event.py` | 记录并封存真实执行阶段、失败重试和优化观察 |
| `scripts/build_process_optimization_report.py` | 从封存轨迹自动生成过程优化报告 |
| `scripts/compare_report_versions.py` | 选择同一产品最近的有效历史基线并生成版本差异 |
| `scripts/build_report_manifest.py` | 生成核心产物大小与SHA-256清单 |
| `docs/REPORT_VERSIONING.md` | 基线选择、差异格式、清单和固定生成顺序 |
| `docs/EXECUTION_TRACE_SCHEMA.md` | 执行轨迹格式、记录命令和安全边界 |
| `scripts/self_test_document_pipeline.py` | DOCX到PDF到PNG的真实链路自检 |
| `scripts/validate_portable_agent_output.py` | 任务输出确定性验收 |
| `scripts/extract_reference_document.py` | 参考DOCX内容提取 |
| `scripts/validate_open_source_discovery.py` | 开源候选结果验证 |
| `evaluations` | P3安全停止、得理法搜与通义法睿回归配置 |
| `tests/unit` | 便携式Agent脚本与协议回归测试 |
| `agent_outputs` | Git忽略的任务产物；每个目录必须由分配器创建 |
| `tmp` | 自检等临时文件；验证后清理 |
| `项目成果展示与使用说明.md` | GitHub-friendly quick display and usage instructions |
| `docs` | 用户指南及历史架构记录 |

运行数据、用户材料、报告、来源快照、日志和密钥不得进入Git。
