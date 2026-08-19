# 视觉适配通道登记表

> 本文件登记已批准的视觉适配通道（协议 `portable-agent-1.1`「能力适配边界」）。
> 通道登记是**项目维护动作**：由使用者发起并确认，运行任务的 Agent 不得自行登记或修改本文件。
> 未登记通道不得作为探针读码或页面质检通道使用；遇到未登记通道时，Agent 必须停止该环节并报告。

## 通道清单

### qwen3-vl-plus（DashScope 原生 API）

| 项 | 值 |
|---|---|
| 通道标识 | `qwen3-vl-plus` |
| 实现方式 | `scripts/visual_qa_dashscope.py`（DashScope compatible-mode 原生 API 直传图像；非 Claude Code 图片通道） |
| 模型 | `qwen3-vl-plus` |
| 探针读码调用 | `python scripts\visual_qa_dashscope.py --read-probe <probe.png> --evidence-out <evidence.json>` |
| 页面质检调用 | `python scripts\visual_qa_dashscope.py <render目录或png>` |
| 密钥来源 | 环境变量 `DASHSCOPE_API_KEY`，或 `~/.claude/settings.qwen-vision.json` 的 `env.ANTHROPIC_AUTH_TOKEN`（自动读取，无需手动传入） |
| 四条件符合 | ① 真实读图 ✓（原生 API 上传 base64 图像，输出基于图像内容）② 可审计 ✓（探针模式输出 evidence：图像 SHA-256 / 通道标识 / 时间戳 / 返回原文）③ 执行者登记 ✓（`verify --visual-channel qwen3-vl-plus --visual-channel-evidence <evidence>`）④ 使用者最终确认 ✓（页面质检结论须使用者人工确认后方可作 PASS 依据） |
| 验证状态 | 页面质检：**已验证**（2026-08-19，legora 报告 9 页版面质检全部通过）；探针读码（qwen3-vl-plus）：**判定不可靠**（2026-08-19 实测 `17663` / `172653` / `096347` 均未通过挑战哈希校验）；探针读码（human 人工通道）：**已验证**（2026-08-19 人工读码签发 capability receipt 成功） |
| 验证者 | 使用者 |
| 登记日期 | 2026-08-19 |

## 使用约束

- **探针读码**：固定使用 **human 通道**（`verify --visual-channel human`）。`qwen3-vl-plus` 的探针读码模式（`--read-probe`）实测多次哈希校验失败，判定不可靠，**不得作为探针码来源**；`--read-probe` 保留用于其他读图场景。探针码只能通过 human 通道或未来验证通过的登记通道获取。
- **页面质检**：输出为 AI 辅助结论；PASS 判定前必须使用者人工确认，且视觉检查结果中须注明执行通道。
- **通道不可用**（API 失效 / 密钥过期 / 网络中断 / 输出不可信）等同视觉能力不可用：必须 BLOCKED 或转人工，不得静默降级为"无质检 PASS"。
- **探针码红线**：探针码只能通过本登记通道或使用者人眼获取；不得从 OCR、PDF 几何、源文件、哈希或未登记模型获取。

## 机器可读清单（`session_preflight_gate.py verify` 校验通道登记时读取）

> 本 JSON 块是通道登记的唯一机器可读来源；新增通道时须同步更新此处与上方表格。
> 未在本清单中的通道 ID 会被 verify 拒绝（`human` 始终允许）。

```json
{"channels": ["qwen3-vl-plus"]}
```
