# 项目目录说明

本文件是P2.2工程索引。没有在“当前状态”中明确标为已实现的能力仍为后续占位。

| 路径 | 职责 | 当前状态 |
|---|---|---|
| `apps/web` | Next.js用户界面 | 已实现产品输入、澄清、来源、生态线索、状态和本地任务列表 |
| `services/api` | FastAPI应用接口 | 已实现内存任务、可替换模型/搜索适配层、真实公开检索、身份闸门和澄清接口 |
| `services/worker` | Agent后台任务、报告与入库 | 空占位 |
| `agent/core/v1.1` | 冻结Agent核心发布副本 | 已导入系统提示词、工作流和边界摘要并校验指纹 |
| `agent/prompts` | 非核心结构化提示 | P2.2运行提示在API提供方模块中实现，目录仍作后续版本化占位 |
| `agent/skills` | 锁定版法律报告Skill | 已导入并校验指纹 |
| `agent/tools/contracts` | 工具权限与输入输出契约 | 空占位 |
| `agent/templates/report` | Word模板与版式规则 | 空占位 |
| `agent/policies` | 数据、费用、电脑操作与授权策略 | 空占位 |
| `contracts` | API、事件和数据契约 | 空占位 |
| `database` | 结构、迁移、RLS、测试种子和验证 | 空占位 |
| `evaluations` | 用例、样例、基线和非敏感汇总 | 保留P2.1虚构身份闸门用例，P2.2增加接口契约测试 |
| `tests` | 单元、集成、回归、视觉、安全和迁移测试 | 已加入身份判断、状态机、OpenAI Responses、兼容Chat Completions、Tavily和API集成测试 |
| `assets` | 许可字体、图表和品牌资产 | 空占位 |
| `deployment` | 容器、Railway、Supabase和环境声明 | 空占位 |
| `docs` | 架构、决策、运行、安全和产品说明 | 已加入P2.1冻结说明和P2.2真实身份检索说明 |
| `scripts` | 开发与质检脚本 | 已加入冻结基线校验及Windows、macOS/Linux本地启动脚本 |
| `artifacts/local` | 本地临时报告与渲染产物 | Git忽略 |
| `tmp` | 可删除的任务临时文件 | Git忽略 |

运行数据、用户材料、报告、来源快照、反馈、日志、数据库导出和密钥不得进入Git。
