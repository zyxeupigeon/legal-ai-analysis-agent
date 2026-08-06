# Legal AI Analysis Agent

面向法律AI产品公开信息研究、证据核验、分析报告生成、Word质检和知识反馈闭环的独立Agent项目。

## 当前阶段

当前为 **P2.3.4：证据相关性审计与冲突处理**。默认只要求DeepSeek API，免密钥测试搜索负责发现并读取公开信息。报告生成后会逐项审核来源是否直接支持具体主张；只出现企业名但不支持事实的网页会被移除，自动重写后仍不合格即停止。科研机构、监管和开放平台查询被前置，API、MCP、插件、连接器与Skill分别判断，研发年限等冲突口径会保留说明而不强行合并。

任务仍只保存在内存中，Word文件只写入本机 `artifacts/local`，重启API后任务清空。本阶段不包含数据库、部署、多用户、正式对外报告或训练。

## 已冻结基线

- 法律AI分析Agent核心 V1.1
- 工作流与输入输出规范 V1.1
- 知识库与反馈闭环设计 V1.0
- 知识库数据字典与逻辑模型 V1.0
- 技术选型与部署方案 V1.0
- 实施准备与项目目录说明 V1.0

详细版本和兼容状态见 `VERSION_MANIFEST.yaml`，目录职责见 `PROJECT_STRUCTURE.md`。

## 小白启动方法

Windows PowerShell首次使用，在仓库根目录依次执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r services/api/requirements.txt
Set-Location apps\web
npm install
Set-Location ..\..
Copy-Item .env.example .env
```

用记事本或VS Code打开刚生成的 `.env`，只填写这一行：

```text
DEEPSEEK_API_KEY=你的DeepSeek API密钥
```

`.env` 已被Git忽略，真实密钥不得发到聊天、提交到Git或写进前端代码。然后在PowerShell执行：

```powershell
Unblock-File -LiteralPath .\scripts\run_local.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run_local.ps1
```

浏览器打开 `http://localhost:3000`；`http://127.0.0.1:3000`也受本地开发配置支持。关闭程序按 `Ctrl+C`。启动脚本直接调用Node与Next.js入口，避免部分Windows安装路径下npm启动器误把`node.exe`当成脚本读取。

若缺少DeepSeek密钥，页面和健康接口会明确提示“未就绪”。若测试搜索异常、没有结果或无法直接读取结果网页，任务会停止，不会暗中改用模型记忆或虚构答案。切换到Tavily、OpenAI或其他兼容接口的方法见 `services/api/README.md`。

## 开发检查

```powershell
.\.venv\Scripts\python scripts\check_baselines.py
.\.venv\Scripts\python -m pytest -q
Set-Location apps\web
npm run typecheck
npm run build
```

## P2.3.4边界

允许：本地页面、内存API、真实模型调用、公开网页身份核验、最小澄清、同企业AI生态线索识别，以及基于本轮证据生成本地Word测试稿。

禁止：把密钥或用户材料、生成报告提交到Git；访问登录、付费或受限页面；未经同意操作用户电脑；把测试稿作为正式报告；建库、训练、部署和多用户开放。

详细架构见 `docs/architecture/P2_3_4_RELEVANCE_CONFLICTS.md`。此前主张绑定方案仍见 `docs/architecture/P2_3_3_CLAIM_EVIDENCE_LOGIC.md`。
