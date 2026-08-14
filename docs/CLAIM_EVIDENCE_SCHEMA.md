# claim_evidence.json 规范

每次正式报告必须在任务目录生成 `claim_evidence.json`。它是可机器验收的内部证据账本，不写入正式 Word 正文。

最小示例：

```json
{
  "schema_version": "1.0",
  "task_id": "product-yyyymmdd",
  "claims": [
    {
      "claim_id": "C001",
      "claim_text": "官方计费页显示合同审查按量价格为4元/页",
      "claim_type": "verified_fact",
      "category": "pricing",
      "source_url": "https://help.aliyun.com/example",
      "source_tier": "A",
      "accessed_at": "2026-08-14",
      "report_location": "企业经营情况/定价",
      "included_in_report": true
    },
    {
      "claim_id": "A001",
      "claim_text": "双轨计费有助于覆盖不同规模客户",
      "claim_type": "analysis",
      "category": "commercial_analysis",
      "based_on_claim_ids": ["C001"],
      "report_location": "洞察总结",
      "included_in_report": true
    }
  ]
}
```

字段规则：

- `claim_type` 只能是 `verified_fact`、`company_claim`、`analysis` 或 `unverified`。
- `verified_fact` 与 `company_claim` 必须填写 HTTP(S) 来源、来源等级和访问日期，且 URL 必须同时出现在 `sources.md`。
- `analysis` 必须用 `based_on_claim_ids` 指向已登记主张。
- `unverified` 必须设置 `included_in_report=false`。
- `current_model_version`、`current_product_version`、`pricing`、`operator`、`policy_status` 只有 `verified_fact + A级一级官方来源` 才能写入正文。
- 证据账本必须覆盖正文中所有会改变结论的数字、日期、当前版本、价格、主体、客户/用户规模、政策状态和企业能力声明；不得只登记少量示例。