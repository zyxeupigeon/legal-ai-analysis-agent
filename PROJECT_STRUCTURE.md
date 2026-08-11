# 项目目录说明

当前 `main` 是P3.2便携式Agent项目。旧网页应用已从主分支移除，可从Git历史和 `archive/p2.3.4-web` 分支恢复。

| 路径 | 职责 |
|---|---|
| `PROJECT_AGENT_PROTOCOL.md` | 唯一业务协议、能力边界和任务目录绑定规则 |
| `AGENTS.md`、`CLAUDE.md`、`GEMINI.md` | 不同Agent的自动发现入口 |
| `agent/core/v1.1` | 冻结的系统提示词、工作流和任务边界摘要 |
| `agent/skills/legal-report-review-and-verification` | 锁定并校验哈希的法律报告Skill |
| `OPEN_SOURCE_DISCOVERY_PROTOCOL.md` | GitHub成熟组件发现、筛选和替换判定规则 |
| `scripts/start_agent.ps1` | Windows Agent检测与启动 |
| `scripts/check_agent_workspace.ps1` | 项目根目录、文件、Python和文档工具预检 |
| `scripts/create_task_workspace.py` | 创建绑定当前项目副本的唯一绝对任务目录 |
| `scripts/self_test_document_pipeline.ps1` | DOCX到PDF到PNG的真实链路自检 |
| `scripts/validate_portable_agent_output.py` | 任务输出确定性验收 |
| `scripts/extract_reference_document.py` | 参考DOCX内容提取 |
| `scripts/validate_open_source_discovery.py` | 开源候选结果验证 |
| `evaluations` | P3安全停止和得理法搜回归配置 |
| `tests/unit` | 便携式Agent脚本与协议回归测试 |
| `agent_outputs` | Git忽略的任务产物；每个目录必须由分配器创建 |
| `tmp` | 自检等临时文件；验证后清理 |
| `docs` | 用户指南及历史架构记录 |

运行数据、用户材料、报告、来源快照、日志和密钥不得进入Git。
