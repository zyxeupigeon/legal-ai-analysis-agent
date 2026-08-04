# 本地API（P2.2.1）

本服务实现产品名称输入、真实公开信息检索、身份闸门、歧义澄清、运营主体核验、同企业AI生态线索识别和内存任务状态。没有数据库、正式报告、训练、多用户或部署能力。

默认组合是 `deepseek + bing_rss_test`：只需要配置 `DEEPSEEK_API_KEY`。免密钥搜索通过Bing中国公开RSS发现结果，再直接读取结果网页；只有成功读取的网页才会交给模型。该入口没有稳定性承诺，只用于P2.2.1本地测试。搜索异常或网页不可读时返回明确错误，不回退到模型记忆或虚构数据。

可选模式：

| `LEGAL_AGENT_IDENTITY_PROVIDER` | 模型 | 必填配置 |
|---|---|---|
| `deepseek`（默认） | DeepSeek Chat Completions | `DEEPSEEK_API_KEY` |
| `compatible` | 其他兼容OpenAI Chat Completions的模型 | `MODEL_API_KEY`、`MODEL_API_BASE_URL`、`MODEL_CLASSIFIER`；`MODEL_PROVIDER_LABEL`可选 |
| `openai` | OpenAI Responses API与内置网页检索 | `OPENAI_API_KEY`，并把 `MODEL_CLASSIFIER` 改成可用的OpenAI模型 |
| `fixture` | 虚构自动化测试 | 无，不能用于真实结论 |

外部搜索模式由 `LEGAL_AGENT_SEARCH_PROVIDER` 选择：`bing_rss_test` 是默认免密钥测试入口；`tavily` 是可选搜索API，需要另填 `TAVILY_API_KEY`。OpenAI模式使用自己的内置检索，不读取该设置。

“兼容接口”只表示请求格式兼容；不同服务对JSON模式的支持仍可能不同。无法满足统一结果契约时，系统会报错并停止，不保存伪结论。`bing_rss_test`不得用于正式报告、生产服务或可用性承诺。

## 启动

Windows推荐在仓库根目录配置未跟踪的 `.env` 后执行 `powershell -ExecutionPolicy Bypass -File .\scripts\run_local.ps1`。macOS/Linux可执行 `./scripts/run_local.sh`。也可手动启动API：

```bash
.venv/bin/uvicorn services.api.app.main:app --env-file .env --reload --port 8000
```

接口文档：`http://127.0.0.1:8000/docs`。服务重启后任务会清空。
