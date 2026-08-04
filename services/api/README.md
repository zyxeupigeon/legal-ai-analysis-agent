# 本地API（P2.1）

本服务只实现产品名称输入、身份闸门、澄清和内存任务状态。没有数据库、真实模型、公开研究、报告生成、多用户或部署能力。

## 启动

在仓库根目录执行：

```bash
python -m venv .venv
.venv/bin/pip install -r services/api/requirements.txt
.venv/bin/uvicorn services.api.app.main:app --reload --port 8000
```

接口文档地址：`http://127.0.0.1:8000/docs`。

服务重启后任务会清空。`衡法智研`、`星云助手`、`晴空天气`均为自动化测试使用的虚构名称。
