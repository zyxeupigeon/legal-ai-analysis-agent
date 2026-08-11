# 法律AI产品分析项目首次试用指南

## 试用前确认

你只需要准备：

1. 已安装并登录的命令行Agent，目前本机已验证Claude Code和OpenCode；
2. 一个明确的法律AI产品名称；
3. 如需模仿特定报告结构，准备对应Word参考报告的完整路径。

项目不要求你另外配置固定模型、固定API、浏览器MCP或插件。Agent仍必须实际具备公开联网检索、网页正文读取、Word生成、PDF/图片渲染及视觉检查能力；缺失关键能力时，正确行为是停止并告诉你缺少什么。

## Windows启动

在文件资源管理器打开项目目录，在地址栏输入 `powershell` 并回车。第一次使用先运行：

```powershell
.\START_AGENT.cmd -SelfTest
```

它会在临时目录生成最小Word，将其转成PDF和逐页PNG，验证后自动清理。看到 `SELF_TEST_OK` 说明本机文档链路可用；若失败，按错误提示安装Word或LibreOffice、Poppler/pdftoppm，或者改用具备等价文档工具的Agent。

自检通过后运行：

```powershell
.\START_AGENT.cmd
```

入口会：

1. 执行项目能力预检；
2. 显示本机检测到的Agent；
3. 自动优先启动Claude Code，其次OpenCode；
4. 避免PowerShell“脚本未签名”错误。

需要指定Agent时运行：

```powershell
.\START_AGENT.cmd -Agent claude
.\START_AGENT.cmd -Agent opencode
```

## 在Agent中输入什么

最小请求：

```text
请完整读取项目协议，然后分析法律AI产品“产品名称”，生成并质检Word报告。
```

带参考报告的请求：

```text
请完整读取项目协议，然后分析法律AI产品“产品名称”。参考报告位于“C:\完整路径\参考报告.docx”，它只用于模仿结构和写法，不能作为目标产品的事实证据。请生成并质检Word报告。
```

产品名称可能对应多个对象时，Agent应先用一个简短问题请你确认；确认前不应生成Word。

## 正常情况下你会看到什么

Agent应先声明预检结果和本次可用能力，然后开展公开研究。完成后，`agent_outputs` 下应出现一个新的独立任务目录，至少包含：

- `report.docx`：可编辑Word报告；
- `sources.md`：来源与主张记录；
- `capability_declaration.md`：本次能力声明；
- `run_summary.md`：运行与验收摘要；
- `render/report.pdf`；
- `render/page-*.png`：逐页检查图片。

运行摘要只有在确定性验收和逐页视觉检查都通过后才能标为PASS。

## 哪些停止属于正常保护

出现以下情况时，Agent停止并不代表项目损坏：

- 没有联网检索或网页正文读取能力；
- 产品名称不能唯一识别；
- 搜索失败或关键页面不可读取；
- 公开来源不能证明运营主体、产品身份或法律AI用途；
- 无法生成Word、PDF或逐页图片；
- 证据冲突尚未被正确并列处理。

此时不要要求Agent“凭经验先写一份”。根据它指出的缺口补足能力或更换Agent后重新运行。

## 结束与查看报告

Agent完成后，按它给出的绝对路径打开 `report.docx`。退出Claude Code或OpenCode通常使用其界面退出命令或按 `Ctrl+C`。项目不会自动上传报告、参考文件、账号信息或密钥。
