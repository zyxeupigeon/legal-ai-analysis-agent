# 项目目录说明

本文件是P1工程骨架索引。目录存在不表示对应能力已经实现。

| 路径 | 未来职责 | P1状态 |
|---|---|---|
| `apps/web` | Next.js用户界面 | 空占位 |
| `services/api` | FastAPI应用接口 | 空占位 |
| `services/worker` | Agent后台任务、报告与入库 | 空占位 |
| `agent/core/v1.1` | 冻结Agent核心发布副本 | 待P2导入并校验指纹 |
| `agent/prompts` | 非核心结构化提示 | 空占位 |
| `agent/skills` | 锁定版法律报告Skill | 待P2导入并校验指纹 |
| `agent/tools/contracts` | 工具权限与输入输出契约 | 空占位 |
| `agent/templates/report` | Word模板与版式规则 | 空占位 |
| `agent/policies` | 数据、费用、电脑操作与授权策略 | 空占位 |
| `contracts` | API、事件和数据契约 | 空占位 |
| `database` | 结构、迁移、RLS、测试种子和验证 | 空占位 |
| `evaluations` | 用例、样例、基线和非敏感汇总 | 空占位 |
| `tests` | 单元、集成、回归、视觉、安全和迁移测试 | 空占位 |
| `assets` | 许可字体、图表和品牌资产 | 空占位 |
| `deployment` | 容器、Railway、Supabase和环境声明 | 空占位 |
| `docs` | 架构、决策、运行、安全和产品说明 | 仅P1基线说明 |
| `scripts` | 以后使用的开发与质检脚本 | 空占位 |
| `artifacts/local` | 本地临时报告与渲染产物 | Git忽略 |
| `tmp` | 可删除的任务临时文件 | Git忽略 |

运行数据、用户材料、报告、来源快照、反馈、日志、数据库导出和密钥不得进入Git。
