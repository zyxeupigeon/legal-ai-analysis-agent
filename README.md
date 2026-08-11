# Legal AI Analysis Agent

面向法律AI产品公开信息研究、证据核验、分析报告生成、Word质检和知识反馈闭环的独立Agent项目。

## 当前阶段

当前为 **P3.0 可自行试用版：通用命令行 Agent 项目模式**。使用者在项目根目录启动自己已有并已登录的命令行 Agent；项目通过统一协议约束研究、证据核验、Word生成和质检，不指定 Agent厂商、模型、模型API、浏览器或MCP。只有满足能力协议的 Agent才能执行完整任务。

**P2.3.4网页应用已冻结保留。** FastAPI、Next.js、DeepSeek/Tavily适配和原有启动方式均未删除，P3.0新增文件不进入网页运行链路。详细设计见 docs/architecture/P3_0_PORTABLE_AGENT_PROJECT.md。

P3.0端到端主路径与失败路径均已通过：双Agent入口与预检通过，Claude Code + DeepSeek V2在不调用原网页/API的情况下完成公开研究、Word生成、8页渲染和独立逐页视觉复核；政府“历经6年”与应用宝“历时8年”口径已并列呈现。能力不足、搜索失败和身份核心证据不足三类注入测试均会安全停止，不使用模型记忆补造事实或生成冒充完成的Word。当前版本可以由使用者自行试用，但报告质量仍取决于所选Agent实际具备的联网、文档生成和视觉检查能力。

涉及开源组件复用时，项目同时复用“寻找项目的方法”：OPEN_SOURCE_DISCOVERY_PROTOCOL.md 规定多源候选发现、成熟度与许可证核验、OpenSSF风险补充、来源失效回退及近似项目仅交由用户判断，并由确定性验证器检查候选结果。

## 已冻结基线

- 法律AI分析Agent核心 V1.1
- 工作流与输入输出规范 V1.1
- 知识库与反馈闭环设计 V1.0
- 知识库数据字典与逻辑模型 V1.0
- 技术选型与部署方案 V1.0
- 实施准备与项目目录说明 V1.0

详细版本和兼容状态见 `VERSION_MANIFEST.yaml`，目录职责见 `PROJECT_STRUCTURE.md`。

## 通用命令行 Agent 启动方法（P3.0）

Windows推荐在项目根目录打开PowerShell后直接运行：

```powershell
.\START_AGENT.cmd
```

该入口不受PowerShell脚本数字签名限制，会执行项目预检、显示可用Agent并自动选择一个启动。当前可显式选择：

```powershell
.\START_AGENT.cmd -Agent claude
.\START_AGENT.cmd -Agent opencode
```

进入Agent后输入：

```text
请完整读取项目协议，然后分析法律AI产品“这里填写产品名称”，生成并质检Word报告。
```

需要提供参考报告时，在同一条消息中附上文件绝对路径。正式产物默认写入 `agent_outputs` 的独立任务目录，Agent应同时生成Word、来源记录、运行摘要及PDF/逐页图片质检文件。

支持自动发现的 Agent会读取根目录入口并遵循 PROJECT_AGENT_PROTOCOL.md。不支持自动发现的 Agent，首条指令应明确要求完整读取该文件。项目不提供通用的 agent 可执行命令，也不把任何账户或密钥打包进仓库。

完整的首次试用步骤、正常现象和失败处理见 `docs/USER_TRIAL_GUIDE.md`。

## 冻结网页应用启动方法（P2.3.4）

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

