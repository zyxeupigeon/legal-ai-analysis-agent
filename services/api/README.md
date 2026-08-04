# 本地API（P2.2）

本服务实现产品名称输入、真实公开信息检索、身份闸门、歧义澄清、运营主体核验、同企业AI生态线索识别和内存任务状态。没有数据库、正式报告、训练、多用户或部署能力。

默认组合是 `deepseek + tavily`：DeepSeek负责按照统一JSON契约进行判断，Tavily负责公开网页搜索。缺少任一密钥时返回明确的503错误，不回退到测试数据。`fixture` 只供自动化测试显式使用。

可选模式：

| `LEGAL_AGENT_IDENTITY_PROVIDER` | 模型 | 搜索 | 必填配置 |
|---|---|---|---|
| `deepseek`（默认） | DeepSeek Chat Completions | Tavily | `DEEPSEEK_API_KEY`、`TAVILY_API_KEY` |
| `compatible` | 其他兼容OpenAI Chat Completions的模型 | Tavily | `MODEL_API_KEY`、`MODEL_API_BASE_URL`、`MODEL_CLASSIFIER`、`TAVILY_API_KEY`；`MODEL_PROVIDER_LABEL`可选 |
| `openai` | OpenAI Responses API | OpenAI内置网页检索 | `OPENAI_API_KEY`，并把 `MODEL_CLASSIFIER` 改成可用的OpenAI模型 |
| `fixture` | 虚构测试 | 无 | 仅自动化测试使用 |

“兼容接口”只表示请求格式兼容；不同服务对JSON模式的支持仍可能不同。无法满足统一结果契约时，系统会报错并停止，不保存伪结论。

## 启动

Windows推荐在仓库根目录配置未跟踪的 `.env` 后执行 `powershell -ExecutionPolicy Bypass -File .\scripts\run_local.ps1`。macOS/Linux可执行 `./scripts/run_local.sh`。也可手动启动API：

```bash
.venv/bin/uvicorn services.api.app.main:app --env-file .env --reload --port 8000
```

接口文档：`http://127.0.0.1:8000/docs`。服务重启后任务会清空。
