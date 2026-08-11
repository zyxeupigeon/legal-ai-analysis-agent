# Legal AI Analysis Agent

面向法律AI产品公开信息研究、证据核验、Word报告生成和逐页质检的便携式Agent工作目录。

当前版本为P3.2用户试用版。项目不绑定特定Agent、模型、模型API、浏览器或MCP；使用者负责安装并登录一个具备所需能力的命令行或图形Agent。

## Windows首次使用

在项目根目录打开PowerShell，先运行真实文档链路自检：

```powershell
.\START_AGENT.cmd -SelfTest
```

看到 `SELF_TEST_OK` 后启动Agent：

```powershell
.\START_AGENT.cmd
```

当前启动器可识别Claude Code、OpenCode、Codex CLI和Gemini CLI；已完成端到端验证的是Claude Code和OpenCode。

进入Agent后输入：

```text
请完整读取项目协议，然后分析法律AI产品“得理法搜”，生成并质检Word报告。
```

## 输出目录安全

启动器会把当前项目的绝对路径写入 `LEGAL_AI_PROJECT_ROOT`。Agent在写入任何任务文件前必须运行：

```powershell
python scripts/create_task_workspace.py --task-id <本次唯一任务ID>
```

只有返回 `TASK_WORKSPACE_OK` 后才能继续，全部产物必须写入返回的绝对 `TASK_OUTPUT_DIR`。若Agent复用了另一份项目副本、旧会话或错误工作目录，分配器会停止任务，避免报告写到同级旧项目。

## 正常交付物

每个任务目录至少应包含：

- `task_context.json`
- `report.docx`
- `sources.md`
- `capability_declaration.md`
- `run_summary.md`
- `render/report.pdf`
- `render/page-*.png`

只有确定性验收和独立逐页视觉检查均通过时，运行摘要才能写总体PASS。

## 项目边界

- 只研究公开、可核验且无需登录或付费的资料。
- 不把密钥、账号、客户资料、参考报告或运行产物提交到Git。
- 输出是研究测试材料，不构成法律意见。
- 网页应用、FastAPI后端及其运行依赖已从 `main` 移除；历史代码仍可从Git历史和 `archive/p2.3.4-web` 分支取得。

详细步骤见 `docs/USER_TRIAL_GUIDE.md`，唯一业务协议见 `PROJECT_AGENT_PROTOCOL.md`。

## 开发检查

```powershell
python scripts/check_baselines.py
python -m pytest -q
.\START_AGENT.cmd -CheckOnly
.\START_AGENT.cmd -SelfTest
```
