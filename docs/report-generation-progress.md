# 报告生成器 · 进度记录

> 对应执行计划：`docs/报告生成器-Claude-Code执行计划-2026-05-12.md`
> 工作分支：`feature/understanding-depth`（按用户偏好，不另开分支，commits 前缀 `feat(report-gen):`）
> 起步日期：2026-05-12

---

## 核心理念（一句话提醒）

报告骨架由 LLM 根据事件线主题**动态推导**，不写死报告类型枚举。三阶段：

1. **阶段一**：LLM 角色 A（报告主理人）读事件线 → 产出 `ReportBlueprint`（骨架）
2. **阶段二**：LLM 角色 B（章节起草员）按章节并行填充内容 + 信息图
3. **阶段三**：LLM 角色 C（润色员）+ docx renderer → 输出 docx / pdf / md

---

## LLM 模型选型

用户决策（2026-05-12）：**3 角色全部使用豆包 Seed Pro API**，作为灰度测试主力模型，以此能力调教整个软件。

| 角色 | 模型 | 调用频次 | 备注 |
|---|---|---|---|
| A · 报告主理人 | 豆包 Seed 2.0 Pro | 1 次/份 | JSON 结构化输出需 retry 机制 + Pydantic 校验 |
| B · 章节起草员 | 豆包 Seed 2.0 Pro | N 次/份（N=章节数） | 中文写作主力 |
| C · 润色员 | 豆包 Seed 2.0 Pro | 1 次/份（可选） | **降级为"风格统一"**，不做事实交叉验证 |

> ⚠️ 暂不接入 Claude / GPT-4。如豆包结构化输出稳定性 < 70%，再考虑切 Claude Sonnet for A 角色。

---

## 迭代计划（micro-adjusted）

按用户认可的微调拆分：

| 迭代 | 范围 | 预计工作量 | 状态 |
|---|---|---|---|
| **R0.0** | 搬沙箱 3 份原型 + 写本文档 + .gitignore | 15 调用 | 🔄 进行中 |
| **R0.5** | Pydantic 数据契约（Blueprint/SectionPlan/ChartHint）+ 2 张 DB 表 + 1 个空 API skeleton | 30 调用 | 待开始 |
| **R1** | report_context_builder + report_blueprint_drafter（LLM A）+ `POST /reports/draft-blueprint` + 验收 | 50 调用 | 待开始 |
| **R2** | section_drafter（LLM B）+ materialize_charts + 并行调度 + `POST /reports/{id}/draft-sections` | 50 调用 | 待开始 |
| **R3** | report_docx_renderer（基于沙箱 helper）+ markdown 解析 + LibreOffice → PDF（可选）+ `POST /reports/{id}/render` | 40 调用 | 待开始 |
| **R4** | UI 入口（客户工作台"生成报告"按钮 + 进度页 + 主理人审阅 + 报告列表）—— **早期挂入，不等 R3** | 60 调用 | 待开始 |
| **R5** | 多主题样例（3-5 种事件线）+ 使用手册 | 30 调用 | 待开始 |

---

## R0.0 · 已完成动作（2026-05-12）

### 1. 搬沙箱 3 份原型到 `backend/app/services/`

| 项目内文件 | 沙箱来源 | 行数 | 用途 |
|---|---|---|---|
| `report_chart_generator.py` | `outputs/chart_generator.py` | 423 | 5 类信息图 (pie / progress_bar_h / timeline / grouped_bar / risk_bubble) + 跨平台中文字体 helper |
| `report_docx_helpers.py` | `outputs/generate_report.py` | 863 | python-docx helper (add_heading / add_paragraph / add_bullet / add_callout / add_table / add_data_source / add_page_break / add_horizontal_rule) + 战略陪伴 mock build() 作参考样例 |
| `report_docx_renderer.py` | `outputs/generate_internal_report.py` | 658 | add_image_from_bytes（含图嵌入）+ 内部产品复盘 mock build() 作参考样例 |

**沙箱完整路径：**
```
~/Library/Application Support/Claude/local-agent-mode-sessions/
  6fba7711-75f4-4df5-9970-514724252192/
  767f57b9-3575-4f6e-8411-083e6b645e63/
  local_9643d1eb-632e-4b46-864d-d656d13cac1c/
  outputs/
```

**保留沙箱原样，不动文件内容**——R2/R3 阶段会按需拆 helper、加 docstring、对接项目数据契约时再改。这样如果沙箱后续有更新，能 diff 出来。

### 2. `.gitignore` 增加 5 条规则

防 commit 沙箱跑出来的预览产物（PNG/JPG/LibreOffice 锁文件/tmp）：

```
docs/.~lock.*#
docs/0[1-9]_*.png
docs/preview-*.jpg
docs/internal-preview-*.jpg
docs/lu*.tmp
```

### 3. 待决（不阻塞 R0 完成）

- `matplotlib` / `python-docx` 是否已在 `backend/pyproject.toml` 里？跑 `uv run python -c "import matplotlib, docx"` 验证；若缺，加依赖。
- LibreOffice headless 是否在部署机器装好？R3 时再确认，MVP 默认只导 docx，PDF 列 nice-to-have。

---

## 参考样例（沙箱产出）

放在 `docs/` 里的 2 份 mock docx：

- `docs/日慈战略陪伴报告-Q1-2026.docx`（46K, 无图，**对外/甲方风格**）
- `docs/益语智库V2.0-产品开发复盘-Q1-2026.docx`（332K, 含 5 张信息图，**内部/集团风格**）

这两份不是模板，是"证明同一套生成器能输出**结构不同**的报告"的 evidence。R5 阶段会对比新生成的报告与这两份样例。

---

## 已知风险跟踪

| 风险 | 触发条件 | 缓解状态 |
|---|---|---|
| 豆包 structured JSON 输出不稳定 | R1 阶段一调 LLM A 时 | 待 R1 现场测；fallback: Pydantic validate + retry 3 次 |
| 章节并行触 LLM rate limit | R2 章节 ≥4 个并行调用时 | 默认 max_workers=4，可配置降为 2 |
| 大事件线（>50 entries）prompt 超长 | R1 用大事件线测试时 | 阶段一对 entry 摘要化（保留 ID + 标题 + 时间，不传全文）|
| LibreOffice 部署依赖 | R3 PDF 导出 | MVP 仅 docx，PDF 列可选 |
| 报告列表 / 归档 UI 没明确规划 | R4 UI 阶段 | 计划 R4 加入"已生成报告"标签页 |

---

## 下次 checkpoint

R0.0 完成后立即 commit → 报告给用户 → 等 "继续 R0.5" 进入数据契约阶段。
