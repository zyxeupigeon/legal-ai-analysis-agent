# Legal AI Analysis Agent

面向法律AI产品公开信息研究、证据核验、分析报告生成、Word质检和知识反馈闭环的独立Agent项目。

## 当前阶段

当前为 **P2.2：单用户本地真实身份检索**。模型与公开网页搜索已经解耦：默认使用DeepSeek进行结构化判断、Tavily提供公开搜索证据，也保留OpenAI原生网页检索，并提供OpenAI兼容接口入口。系统已实现产品身份辨析、运营主体核验、歧义候选、越界终止，以及同企业相关AI产品、API和MCP等线索识别。

任务仍只保存在内存中，重启API后清空。本阶段不包含数据库、部署、多用户、正式报告生成或训练。

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

用记事本或VS Code打开刚生成的 `.env`，填写这两行：

```text
DEEPSEEK_API_KEY=你的DeepSeek API密钥
TAVILY_API_KEY=你的Tavily API密钥
```

`.env` 已被Git忽略，真实密钥不得发到聊天、提交到Git或写进前端代码。然后在PowerShell执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_local.ps1
```

浏览器打开 `http://127.0.0.1:3000`。关闭程序按 `Ctrl+C`。

若缺少任一必要密钥，页面和健康接口会明确提示“未就绪”，不会暗中改用虚构答案。自动化测试使用显式虚构模式，不消耗API费用。切换到OpenAI或其他兼容接口的方法见 `services/api/README.md`。

## 开发检查

```powershell
.\.venv\Scripts\python scripts\check_baselines.py
.\.venv\Scripts\python -m pytest -q
Set-Location apps\web
npm run typecheck
npm run build
```

## P2.2边界

允许：本地页面、内存API、真实模型调用、公开网页身份核验、最小澄清和同企业AI生态线索识别。

禁止：把密钥或用户材料提交到Git、访问登录/付费/受限页面、操作用户电脑、生成正式报告、建库、训练、部署和多用户开放。

详细架构见 `docs/architecture/P2_2_REAL_IDENTITY_RESEARCH.md`。P2.1冻结实现说明仍保留在 `docs/architecture/P2_1_LOCAL_MINIMUM_LOOP.md`。
