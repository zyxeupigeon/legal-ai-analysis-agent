# 项目目录说明

本文件是P3.0工程索引；P2.3.4网页应用作为冻结运行路径保留。没有在“当前状态”中明确标为已实现的能力仍为后续占位。

| 路径 | 职责 | 当前状态 |
|---|---|---|
| `PROJECT_AGENT_PROTOCOL.md`及根目录适配文件 | 通用命令行 Agent唯一规范与自动发现入口 | P3.0已实现，已由OpenCode和Claude Code验证 |
| OPEN_SOURCE_DISCOVERY_PROTOCOL.md | 开源项目与元发现工具的候选生成、核验、回退和替换判定协议 | P3.1已实现协议与确定性结果验证 |
| `apps/web` | Next.js用户界面 | 已实现产品输入、澄清、来源、生态线索、状态、Word生成下载和本地任务列表 |
| `services/api` | FastAPI应用接口 | 已实现内存任务、可替换模型/搜索适配层、免密钥测试搜索、身份闸门、报告草稿和Word导出接口 |
| `services/worker` | Agent后台任务、报告与入库 | 空占位 |
| `agent/core/v1.1` | 冻结Agent核心发布副本 | 已导入系统提示词、工作流和边界摘要并校验指纹 |
| `agent/prompts` | 非核心结构化提示 | P2.3.4身份、报告和证据审计提示在API提供方模块中实现，目录仍作后续版本化占位 |
| `agent/skills` | 锁定版法律报告Skill | 已导入并校验指纹 |
| `agent/tools/contracts` | 工具权限与输入输出契约 | 空占位 |
| `agent/templates/report` | Word模板与版式规则 | 代码化最小模板已实现；独立模板文件仍作后续占位 |
| `agent/policies` | 数据、费用、电脑操作与授权策略 | 空占位 |
| `contracts` | API、事件和数据契约 | 空占位 |
| `database` | 结构、迁移、RLS、测试种子和验证 | 空占位 |
| `evaluations` | 用例、样例、基线和非敏感汇总 | 保留身份闸门用例以及检索相关性、查询回退与本地启动配置测试 |
| `tests` | 单元、集成、回归、视觉、安全和迁移测试 | 已加入身份判断、状态机、适配器、引用过滤、Word构建和API下载测试 |
| `assets` | 许可字体、图表和品牌资产 | 空占位 |
| `deployment` | 容器、Railway、Supabase和环境声明 | 空占位 |
| `docs` | 架构、决策、运行、安全和产品说明 | 已加入P2.1、P2.2、P2.3.1至P2.3.4及P3.0实现说明 |
| `scripts` | 开发与质检脚本 | 已加入冻结基线校验、网页应用启动、通用Agent能力预检、Agent启动器、可选组件评估、参考DOCX零依赖提取和开源候选结果验证 |
| `agent_outputs` | P3.0命令行Agent隔离产物 | Git忽略，仅保留目录占位 |
| `artifacts/local` | 本地临时报告与渲染产物 | Git忽略 |
| `tmp` | 可删除的任务临时文件 | Git忽略 |

运行数据、用户材料、报告、来源快照、反馈、日志、数据库导出和密钥不得进入Git。
