# TTFUND API 字段映射

> 基于 2026-05-20 实时调用验证

---

## FUND_NAV_INFO（基金净值历史）

**Skill ID:** `FUND_NAV_INFO`  
**参数:** `fund_id` (基金代码如 "510300"), `range` (y/3y/6y/n/2n/3n/ln)

**响应结构:**
```json
{
  "success": true,
  "errorCode": 0,
  "data": {
    "nav_history": {
      "items": [
        {
          "FSRQ": "2026-04-20",   // 复权净值日期
          "DWJZ": "4.7681",       // 单位净值
          "JZZZL": "0.61",        // 净值增长率（%）
          "LJJZ": "2.0952",       // 累计净值
          "NAVTYPE": "1",         // 净值类型（1=单位净值）
          "RATE": "--"            // 日收益率（部分品种无数据）
        }
      ]
    }
  }
}
```

**字段映射:**
| API 字段 | 中文含义 | 备注 |
|---------|---------|------|
| FSRQ | 复权净值日期 | YYYY-MM-DD |
| DWJZ | 单位净值 | |
| JZZZL | 净值增长率 | 单位：%，如 "0.61" 表示 0.61% |
| LJJZ | 累计净值 | |
| NAVTYPE | 净值类型 | 1=单位净值 |
| RATE | 日收益率 | "--" 表示无数据 |

---

## FUND_BASE_INFOS（基金基础信息）

**Skill ID:** `FUND_BASE_INFOS`  
**参数:** `fcode` (基金代码)

**响应结构:** `data` 为 list（而非 dict）

---

## 其他接口

| Skill ID | 状态 | 说明 |
|---------|------|------|
| FUND_INDEX_INFO | 待验证 | 需要有效 indexId |
| FUND_MANAGER_INFO | 待验证 | 需要有效基金经理名 |
| FUND_HOLDING_INFO | 待验证 | |
| FUND_CONDITION_SELECT | 待验证 | |
| FUND_HUAAN_GOLD_INFO | 待验证 | |
| FUND_TG_STRATEGY_INFO | 待验证 | |

---

## 调用注意事项

1. **Rate Limit:** ≥1 秒间隔（TTFUND API 限制）
2. **超时:** 建议 30s timeout
3. **错误码:** `errorCode != 0` 时 data 可能为空
4. **字段名:** 大写拼音缩写，解析时注意大小写