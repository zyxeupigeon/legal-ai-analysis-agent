# 开源项目发现与复用协议

协议编号：open-source-discovery-0.1

## 适用范围

当任务涉及寻找、比较、采用或替换开源实现时，运行中的 Agent 必须遵循本协议。
协议同时覆盖两类对象：

1. 实现目标功能的开源项目；
2. 用于发现、聚合、评价其他开源项目的元发现工具。

元发现工具与普通候选项目接受相同的许可证、维护状态、采用证据、安全性和真实运行审查。

## 不得违反的原则

- 先把目标拆成可独立验收的小功能，再搜索候选。
- 不得仅依据 Star、Fork、搜索排名、项目自述或单一聚合分数决定替换。
- 只有功能精确匹配、许可证兼容、未归档、维护与采用证据充分、隔离样本验证通过的候选，才能标记为可替换候选。
- 仅近似匹配的项目必须标记为仅供用户判断，不得自动替换。
- 没有许可证、许可证不兼容、已归档、无法复现或关键证据不足的项目必须拒绝或降级。
- OpenSSF Scorecard 等评分只能提供风险信号，不得独立决定采用。
- 任何搜索源、API、MCP 或聚合服务均不得成为硬依赖；单一来源失败时继续其他来源。
- 所有外部访问仍受 PROJECT_AGENT_PROTOCOL.md 的登录、付费、权限和密钥边界约束。

## 推荐发现顺序

1. GitHub 原生仓库搜索、代码搜索、Topic、Collections 和已知组织；
2. 领域 Awesome 清单、sindresorhus/awesome 和可用的清单索引；
3. 项目依赖清单、包管理器反向依赖和生态数据；
4. ecosyste-ms/awesome、ecosyste-ms/repos 等可选公共数据源；
5. OpenSSF Scorecard、OSV、发布记录和仓库活动用于风险补充；
6. 阅读 README、许可证、变更记录、发布页、关键代码与测试；
7. 在隔离目录运行最小真实样本，不得直接改写当前项目。

顺序允许根据 Agent 能力调整，但不得跳过功能匹配、许可证和真实样本验证。

## 结果文件

每轮发现必须在 agent_outputs 下的本轮目录生成 open_source_candidates.json，包含：

- protocol_version：固定为 open-source-discovery-0.1；
- task：被拆分验证的小功能；
- generated_at：生成时间；
- sources：每个发现或评价来源的名称、类型、状态和证据 URL；
- candidates：候选仓库、功能匹配度、建议、许可证、成熟度证据、风险信号和隔离验证；
- decision：exact_candidate_found、near_candidates_only、no_suitable_candidate 或 discovery_blocked；
- chosen_repository：仅在存在通过验收的精确候选时填写。

运行以下命令做确定性检查：

    python scripts/validate_open_source_discovery.py agent_outputs/<本轮目录>/open_source_candidates.json

## 候选判定

### 精确匹配

只有同时满足以下条件才可使用 recommendation=replace_candidate：

- functional_fit=exact；
- validation.status=passed；
- license.status=compatible；
- maturity.archived=false；
- maturity.adoption_evidence 非空；
- 至少提供一个可核验的候选证据 URL。

否则应拒绝，不得包装成精确替代。

### 近似匹配

functional_fit=near 时必须使用 recommendation=user_review_only，并明确列出：

- 已覆盖的能力；
- 缺失或不同的能力；
- 引入成本和风险；
- 仓库与验证证据链接。

### 来源阻塞

单个来源收费、登录受限、超时、返回冲突数据或不可访问时，将该来源记为 blocked 或 failed，
然后继续其他来源。只有所有必要发现来源均不可用、Agent 无法形成可核验候选集时，才使用
decision=discovery_blocked。

## 与主协议的关系

本文件只增加开源项目发现和复用规则。法律 AI 产品研究、证据绑定、报告生成、Word 渲染
和安全停止仍以 PROJECT_AGENT_PROTOCOL.md 及冻结核心文件为准。
