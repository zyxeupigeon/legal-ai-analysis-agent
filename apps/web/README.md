# 本地页面（P2.2.2）

在仓库根目录先启动API，再打开另一个终端：

```bash
cd apps/web
npm install
npm run dev
```

访问 `http://localhost:3000`（也允许 `http://127.0.0.1:3000`）。页面只连接本机API；密钥只由本机API读取，不会进入浏览器代码。页面显示公开来源、身份摘要、歧义候选和同企业AI生态线索。
