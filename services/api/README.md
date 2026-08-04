# 本地API（P2.2）

本服务实现产品名称输入、真实公开信息检索、身份闸门、歧义澄清、运营主体核验、同企业AI生态线索识别和内存任务状态。没有数据库、正式报告、训练、多用户或部署能力。

默认使用 `openai` 提供方，读取 `OPENAI_API_KEY` 并通过Responses API启用网页检索。缺少密钥时返回明确的503错误，不回退到测试数据。`fixture` 提供方只供自动化测试显式使用。

## 启动

推荐在仓库根目录配置未跟踪的 `.env` 后执行 `./scripts/run_local.sh`。也可手动启动：

```bash
.venv/bin/uvicorn services.api.app.main:app --env-file .env --reload --port 8000
```

接口文档：`http://127.0.0.1:8000/docs`。服务重启后任务会清空。
