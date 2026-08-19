# P3.9 视觉能力适配与能力组合协议修改方案

> 状态：**草案待审**（未修改任何正式协议文件）
> 目标：允许"无视觉主模型 + 经批准的视觉适配通道"通过 preflight，解决"只有无视觉模型可作主模型（大量 token）、视觉模型仅用于少量 token 任务"的兼容问题
> 协议版本变更建议：`portable-agent-1.0` → `portable-agent-1.1`（hard gates 语义变化，须升版）

---

## 1. 背景与问题

- 项目核心目标：任意兼容 Agent 可跑，不绑定特定厂商、模型、API。
- 现状矛盾：preflight 要求 `direct_image_inspection` 能力**必须真实存在于当前连续会话内**，探针码禁止从 OCR、PDF 几何、源文件、哈希或**另一个模型**获取。这使"无视觉主模型（负责研究/生成，占绝大多数 token）+ 视觉模型（仅质检，占少量 token）"的组合永远无法通过门禁。
- 协议自身不一致：`PROJECT_AGENT_PROTOCOL.md` 第 51 行明确允许"若 Agent 没有网页检索能力，可要求使用者启用相应工具补足"（搜索能力可外部适配），但视觉能力却禁止外部适配。
- 结论：维持现状反而动摇中立性（"兼容 Agent"被缩窄为"必须自带视觉的 Agent"）；增加受控的视觉适配通道才能让任意模型可跑。

## 2. 修改原则（三条，不改动）

1. **能力真实性**：receipt 声明的每一项能力必须真实存在且可审计，不因适配而变成"自报即可"。
2. **中立性**：适配通道是"实现方式"（与浏览器、搜索服务同级），协议不定死具体脚本或供应商；只定义通道必须满足的条件。
3. **诚信不可外包**：事实核验、来源绑定、目标产品访问等环节永不通过外部通道补足。

## 3. 协议正文修改内容

### 3.1 新增一节「能力适配边界」（放在「最低能力要求」之后）

```markdown
### 能力适配边界

视觉检查、网页检索与正文读取属于可适配能力：若当前会话模型自身不具备，可使用经批准的能力适配通道补足；通道是"实现方式"，与浏览器、搜索服务同级，不是项目硬性依赖。

**可适配能力**：联网检索、网页正文读取、视觉检查（direct image inspection）。
**不可适配能力**（缺失即 BLOCKED，任何通道不得补足）：目标产品注册/登录/付费/API 调用/文件上传；事实核验与来源绑定；对目标产品能力作实测结论。报告过程中任何环节都不得通过外部通道接触目标产品账户、密钥或受限内容。

**经批准的视觉适配通道必须同时满足以下全部条件**，否则不得视为 READY：
1. 真实读取图片字节并输出基于图像内容的描述，不得从文件名、路径、哈希、几何推断或会话内既有知识输出结论；
2. 输出可审计：通道调用记录（图像 SHA-256、通道标识、调用时间、返回原文）必须随执行轨迹保存，可复现复核；
3. 执行者显式登记：探针读码与页面质检必须声明实际执行通道（如 human、qwen3-vl-plus），写入 capability receipt 与任务上下文；
4. 使用者最终确认：页面质检结论必须由使用者人工确认后方可作为 PASS 依据（责任链，见交付要求）。

通道不可用时（API 失效、密钥过期、网络中断、输出不可信）等同视觉能力不可用：必须 BLOCKED 或转人工，不得静默降级为"无质检 PASS"。

报告中任何能力声明必须拆分主模型能力与通道能力：`capability_declaration` 不得把通道能力记为主模型自身能力。

**通道登记流程**：

- 通道登记是**项目维护动作**，由使用者发起并最终确认；运行任务的 Agent 不得在报告任务期间自行登记新通道、修改通道清单或任何门禁相关文件（协议第 65 行禁止报告任务期间修改仓库文件）。
- 新通道登记前，必须由使用者（或使用者指定的独立维护会话）验证其满足上述全部四条件，并记录：通道标识、实现方式（脚本/服务）、版本或调用方式、验证日期与验证者。
- 运行任务的 Agent 遇到使用者希望使用但**未登记**的视觉通道时，必须停止该环节并报告"此通道未登记，按协议不得作为探针或质检通道使用"，给出选项：使用者人工复核，或使用者先完成通道登记后再继续；不得自行放行、不得自行登记。
```

### 3.2 hard gate 1 修改（探针码来源规则）

**原文（1.0）：**

> 1. Before declaring `SESSION_PREFLIGHT_READY`, run `python scripts/session_preflight_gate.py prepare`. Open the emitted `PROBE_IMAGE` with the same direct image-view capability that will be used for final report pages. Do not obtain the code from OCR, PDF geometry, source files, hashes, or another model.

**新文（1.1）：**

> 1. Before declaring `SESSION_PREFLIGHT_READY`, run `python scripts/session_preflight_gate.py prepare`. Read the emitted `PROBE_IMAGE` with the direct image-view capability this session will use for final report pages: the session model's own vision, an approved visual adapter channel (see 能力适配边界), or the user's own eyes. The actual reader must be named in the capability receipt (`--visual-channel`). Do not obtain the code from OCR, PDF geometry, source files, hashes, or from any model/tool that is not the declared visual channel. When the code comes from an approved adapter channel, its call record (probe image SHA-256, channel id, timestamp, raw output) must be kept with the execution trace and verifiable.

### 3.3 hard gate 3 修改（能力缺失判定）

**原文（1.0）：**

> 3. If direct image inspection, full-page reading, permissions, or any other required capability is unavailable in the current continuous session, declare `SESSION_PREFLIGHT_BLOCKED`. ...

**新文（1.1）：**

> 3. If direct image inspection (including every approved visual adapter channel), full-page reading, permissions, or any other required capability is unavailable in the current continuous session, declare `SESSION_PREFLIGHT_BLOCKED`. A channel that fails, is unreachable, or cannot be verified does not count as available; do not silently downgrade to an uninspected PASS. ...

### 3.4 「最低能力要求」与第 51 行同步

第 51 行补一句视觉适配的并列说明：

```markdown
浏览器、MCP、插件和具体搜索服务都只是实现方式，不是项目硬性依赖。若 Agent 没有网页检索与正文读取能力，可以要求使用者启用相应工具；在能力补足前必须停止事实研究。视觉检查能力同样可以通过经批准的适配通道补足（见「能力适配边界」），通道调用记录必须可审计；在视觉通道补足前不得声明 READY 或 PASS。
```

### 3.5 交付要求补充（能力声明拆分 + 责任链）

在交付要求「完整任务至少交付」的 `能力声明` 处补充：

```markdown
- 能力声明必须拆分主模型能力与适配通道能力（例如：研究/生成 = deepseek-v4-flash；视觉质检 = qwen3-vl-plus 通道 + 使用者人工确认），不得把通道能力记为主模型自身能力；
- 视觉质检结果必须注明执行通道，并由使用者人工确认后方可作为 PASS 依据；
- 使用者人工确认的执行方式：渲染完成后 Agent 出示渲染页路径与（如有）通道质检结果，使用者在**同一会话内**给出确认或问题反馈；确认动作（内容、时间）记录进执行轨迹或视觉检查结果，且必须先于 PASS 判定。不要求另开会话；未确认前不得封存 PASS。
```

### 3.6 结果判定顺序第 3 条同步（视觉检查记录通道）

原文："独立查看最终版全部页面，记录裁切、重叠、缺字、表格越界、异常空白和分页问题，并完成必要修复。"

补充为："独立查看最终版全部页面（查看方式可为会话视觉、经批准的适配通道或使用者复核，须在视觉检查结果中注明实际执行者），记录裁切、重叠、缺字、表格越界、异常空白和分页问题，并完成必要修复。"

## 4. 六条堵法 → 条款落点对照

| 漏洞 | 堵法 | 落点 |
|---|---|---|
| 声称外接变成万能钥匙 | 通道调用记录可核验、探针码可回溯到真实看图 | 3.1 条件 1-2 + 3.2 证据链 + 5.2 脚本字段 |
| 白名单被蹭（OCR/任意模型混入） | 通道条件写死：真实读图、可审计、登记执行者、使用者确认 | 3.1 四条条件 |
| 责任链悬空 | 使用者最终确认硬性化 | 3.1 条件 4 + 3.5 |
| 能力声明失真 | 主模型能力与通道能力拆分记录 | 3.5 |
| 安全停止测试失去靶子 | 不可适配能力清单，缺失仍强制停止 | 3.1 不可适配能力段 |
| 通道故障静默降级 | 通道不可用 = 能力不可用 = BLOCKED/转人工 | 3.1 末段 + 3.3 |

## 5. 联动文件与脚本改动

### 5.1 文档

| 文件 | 改动 |
|---|---|
| `PROJECT_AGENT_PROTOCOL.md` | 见第 3 节；协议编号改 `portable-agent-1.1` |
| `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` | 同步 preflight 描述："inspect its PNG with the same direct image-view capability intended for final report pages" → 允许"经批准的视觉适配通道或使用者复核"，并注明通道须登记 |
| `VERSION_MANIFEST.yaml` | `protocol_version: "1.1"`、`protocol_id: portable-agent-1.1`、`capability_receipt` 描述更新为"one_use_visual_probe_with_declared_visual_channel" |
| `CHANGELOG.md` | 记录本变更（协议 1.1：视觉能力适配通道） |
| `docs/architecture/P3_0_PORTABLE_AGENT_PROJECT.md` | 若其中引用 hard gates 原文，需同步 |

### 5.2 脚本

| 文件 | 改动 |
|---|---|
| `scripts/session_preflight_gate.py` | `PROTOCOL_ID` → `portable-agent-1.1`；`verify` 新增参数 `--visual-channel <id>`（必填，如 `human` / 通道模型标识）与可选 `--visual-channel-evidence <path>`（通道调用记录 JSON，receipt 存其 SHA-256）；receipt 新增字段 `visual_channel`、`visual_channel_evidence_sha256` |
| `scripts/create_task_workspace.py` | `PROTOCOL_ID` → `portable-agent-1.1`；`task_context.json` 的 `session_capabilities` 旁写入 `visual_channel` |
| `scripts/visual_qa_dashscope.py` | 新增"探针读码"模式（输出 6 位数字 + 图像 SHA-256 + 时间戳，形成通道调用记录），供 3.2 证据链使用；保持"页面质检"模式不变 |
| 其他引用 `PROTOCOL_ID` 的脚本 | 统一升版（`execution_trace_lib.py`、`record_execution_event.py` 等如硬编码则同步） |

### 5.3 新增文档

- `docs/architecture/P3_9_VISION_ADAPTER_PROTOCOL.md`：本方案定稿后转为设计说明，记录 1.1 的适配边界与证据链要求。

## 6. 实施顺序

1. 你审阅本方案并确认（可逐条修订）。
2. 先改 `PROJECT_AGENT_PROTOCOL.md`（3.1-3.6），再同步 `AGENTS.md` / `CLAUDE.md` / `GEMINI.md`。
3. 改脚本（5.2），先升 `PROTOCOL_ID` 并加 `visual_channel` 字段，跑通 `session_preflight_gate.py` 的 prepare/verify 自测。
4. 给 `visual_qa_dashscope.py` 加探针读码模式并实测（用一张探针图验证输出 6 位码 + 证据记录）。
5. 更新 `VERSION_MANIFEST.yaml` 与 `CHANGELOG.md`。
6. 跑现有测试套件（`tests/`）与 `START_AGENT.cmd -SelfTest`，确认无回归。
7. 设计并执行"适配版失败场景安全停止"测试（见第 7 节）。

## 7. 验证方案（堵法有效性测试用例）

参照交接文档"失败场景安全停止专项测试"方法论，新增以下用例：

1. **伪造探针码**：会话未调用任何通道/未给使用者看图，直接编造 6 位码 → 必须 verify 失败、receipt 不得签发、无 task workspace。
2. **冒充通道**：会话声明 `--visual-channel qwen3-vl-plus` 但无通道调用记录（evidence 缺失或哈希对不上）→ receipt 应拒绝或执行轨迹审计时暴露；设计上要求 receipt 记录 evidence 哈希，create_task_workspace 校验字段完整性。
3. **谎称降级**：通道不可用时会话试图跳过质检直接写 PASS → 按 3.3 必须 BLOCKED/FAIL 并列出缺口。
4. **通道真实可用**：用 `visual_qa_dashscope.py` 探针读码模式读一张探针图 → 数字正确、evidence 完整、verify 通过、receipt 含 `visual_channel`。
5. **不可适配能力缺失**：移除目标产品访问之外的能力缺失注入（如强制声明无页面读取）→ 仍必须安全停止。

以上用例中 1-3 应产出 BLOCKED/FAIL 记录且无虚假 PASS；4 应产出合规 receipt；5 确认"不可适配能力缺失仍停止"未因适配条款而失效。
