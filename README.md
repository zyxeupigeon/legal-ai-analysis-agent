# Legal AI Analysis Agent

面向法律AI产品公开信息研究、证据核验、分析报告生成、Word质检和知识反馈闭环的独立Agent项目。

## 当前阶段

当前为 **P2.1：单用户本地最小闭环第一阶段**。已经实现产品名称输入、身份闸门、澄清流程、任务状态机、基础页面和自动化测试。

任务只保存在内存中，重启API后清空。当前不包含数据库、部署、多用户、真实模型调用、公开研究、训练或Word报告生成。

## 已冻结基线

- 法律AI分析Agent核心 V1.1
- 工作流与输入输出规范 V1.1
- 知识库与反馈闭环设计 V1.0
- 知识库数据字典与逻辑模型 V1.0
- 技术选型与部署方案 V1.0
- 实施准备与项目目录说明 V1.0

详细版本和兼容状态见 `VERSION_MANIFEST.yaml`，目录职责见 `PROJECT_STRUCTURE.md`。

## 小白启动方法

首次使用，在仓库根目录依次执行：

```bash
python -m venv .venv
.venv/bin/pip install -r services/api/requirements.txt
cd apps/web
npm install
cd ../..
./scripts/run_local.sh
```

然后浏览器打开 `http://127.0.0.1:3000`。关闭终端中的运行程序可按 `Ctrl+C`。

可用三个虚构名称验证流程：`衡法智研`（明确）、`星云助手`（需要澄清）、`晴空天气`（超出范围）。它们只用于测试，不对应真实企业结论。

## 开发检查

```bash
.venv/bin/python scripts/check_baselines.py
.venv/bin/python -m pytest -q
cd apps/web && npm run typecheck && npm run build
```

## P2.1边界

允许：本地页面、内存API、确定性虚构测试目录、身份澄清和状态测试。

禁止：真实密钥、用户材料、报告、数据库、服务注册、真实模型调用、训练和部署。

详细架构见 `docs/architecture/P2_1_LOCAL_MINIMUM_LOOP.md`。
