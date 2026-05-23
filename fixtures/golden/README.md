# Golden Test Pack · 7 类用户输入样本 (B 自动验收官冻结)

> **冻结**: 2026-05-23 19:15 V1
> **作用**: B 所有评估脚本从这里取输入, 保证可重复 + 可比较
> **详细规格**: `docs/B_AI_GOLDEN_TEST_PACK.md`

| 文件 | 用途 | 用在哪些评估 |
|---|---|---|
| `meeting_mingyuan.txt` | 复杂会议纪要 (明远 6 子目标) | R2 / V3.0 Group 1/2 |
| `qa_10.txt` | 工作台 10 真问题 | R4-P0 工作台问答 |
| `files_20.txt` | 20 文件导入 | R4-P0 文件导入 |
| `weekly_review.txt` | 周复盘 + 历史回指 | R4-P0 战略陪伴 / 历史关联 |
| `task_create.txt` | 任务创建 | R4-P0 / Approval Queue |
| `intelligence_brand.txt` | 外部情报检索 | V3.0 Group 2 / R3 H5 (不覆盖内部) |
| `method_card.txt` | 方法卡 / 系统经验 | R3 H6 (不污染客户事实) |

加新样本规则: 加 `<key>.txt` + 在 `B_AI_GOLDEN_TEST_PACK.md` 加 §, 不删 V1.
