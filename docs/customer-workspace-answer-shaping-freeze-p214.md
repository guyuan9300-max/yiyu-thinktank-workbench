# P2.14 客户工作台回答塑形半层冻结清单

## 目标
- 冻结对象不是整个数据中心。
- 冻结的是夹在“资料底座”和“模型生成”之间、负责限制模型读什么和怎么答什么的那半层。
- 语义：
  - 锁住旧限制层，不再演化
  - 不是认可它正确
  - 也不是永久保留
  - 它只是后续整体替换前的隔离带

## 保留的底座
- 文档预处理与沉淀：
  - PDF/DOCX/PPTX 转文本、OCR、清洗、索引
- 统一证据模型与检索底座：
  - `knowledge_v2`
  - `DataCenterSearchResultRecord / EvidenceItem`
  - 工作台资料仓和 page context 生成
- 事实性安全边界：
  - 不编造
  - 不把候选判断写成正式判断
  - 不暴露内部系统标记
- 显式工具路径：
  - `file_search`
  - `official_judgment_registry`

## 冻结边界

### 1. 意图塑形层
- 文件：
  - `backend/app/services/analysis_context.py`
  - `backend/app/services/query_router.py`
  - `backend/app/services/workspace_query_router.py`
  - `backend/app/main.py`
- 冻结内容：
  - `workspace/chat` 主回答链不再被重新拉回 `intro_profile / meeting_summary / status_progress / next_actions`
  - `general` 主链默认只保留 `raw_docs + document_cards`
  - `official_judgment_registry` 仍保留为显式工具路径

### 2. 焦点塑形层
- 文件：
  - `backend/app/services/question_focus.py`
  - `backend/app/services/evidence_selector.py`
- 冻结内容：
  - `question_focus_frame` 仅作为诊断字段存在
  - 不允许再参与证据加权、回答展开、suppression、角色偏好

### 3. 证据裁剪层
- 文件：
  - `backend/app/services/data_center_search.py`
  - `backend/app/services/evidence_selector.py`
  - `backend/app/services/answer_layer.py`
- 冻结内容：
  - 数据源白名单
  - merged evidence pool limit
  - `selected_limit`
  - `max_per_doc`
  - `maxEvidenceItems`
- 当前已冻结的历史限制：
  - `rawEvidence[:40]`
  - `evidenceCards[:30]`
  - `relatedDocuments[:30]`
  - `relatedMeetings[:15]`
  - `relatedTasks[:20]`
  - `officialJudgments[:20]`
  - `candidateJudgments[:20]`
  - `themeClusters[:20]`
  - `bundle citations[:60]`
  - `merged pool limit=120`
  - `selected_limit=24`
  - `max_per_doc=3`
  - `maxEvidenceItems=24`

### 4. 文档打包层
- 文件：
  - `backend/app/services/workspace_data_center_adapter.py`
  - `backend/app/main.py`
- 冻结内容：
  - `evidence_highlights[:36]`
  - 每片段 `limit=1800`
  - 每文档最多 `3` 个片段
  - 最多 `8` 份文档
  - `max_chars=64000`
- 说明：
  - 这是当前 `raw_document_pack` 的历史边界，不是未来目标架构的一部分。

### 5. 回答编排层
- 文件：
  - `backend/app/services/answer_layer.py`
  - `backend/app/services/workspace_data_center_adapter.py`
  - `backend/app/main.py`
- 冻结内容：
  - `AnswerPlan` 主回答开放形态保持不变
  - 不允许恢复任何 intent 特化规则
  - 不允许把下面这些二次总结对象重新喂回主回答 prompt：
    - `keyFacts`
    - `previewSummary`
    - `workTrace`
    - `stateAnswerSections`
    - `answerPresentation`
    - `workspaceAnswerExperience`
    - `contextQuality`
  - 不允许恢复固定结构、边界块、编号模板、`directAnswerSeed` 软引导

### 6. 运行时压缩与回退层
- 文件：
  - `backend/app/services/generation_runtime_policy.py`
  - `backend/app/main.py`
  - `backend/app/services/ai.py`
- 冻结内容：
  - `workspace/chat` 主回答不允许重新挂回：
    - `compact context`
    - `compact retry`
    - `local_only`
    - `compact_first`
    - `probe_after_cooldown`
  - fallback 只允许开放式短文，不允许回到模板型 fallback

### 7. 形态质量门禁层
- 文件：
  - `backend/app/services/data_center_quality.py`
- 冻结内容：
  - 只保留事实性硬失败
  - 不允许恢复：
    - `hasDirectAnswer`
    - `missingRawEvidenceForIntent`
    - `factSlotHit`
    - `evidenceListOnly / evidenceQuoteOnly`
    - intent 绑定的 off-topic 形态约束

## 冻结基线

### CFFC
- 真实运行态：
  - `run_id = analysis_72ddc6763b`
  - `question = 介绍CFFC`
  - `content_len = 1104`
- 供料前列文档：
  - `20260403_131702_# 一、CFFC的核心定位与历史价值.docx`
  - `20260403_130527_# 一、CFFC的核心定位与历史价值.md`
  - `20260403_112825_# 一、CFFC的核心定位与历史价值.md`
  - `20260403_131702_# 一、CFFC的核心定位与历史价值.md`
  - `腾讯基金会项目进展报告-秘书长平台-2025年7月更新-v2_CFFC_20260211.docx`
  - `CFFC工作坊_时间安排与议程草案 2_CFFC_20260211.docx`

### 日慈
- 真实运行态：
  - `run_id = analysis_8a9ea0ea41`
  - `question = 介绍日慈`
  - `content_len = 653`
- 供料前列文档：
  - `日慈基金会·第一年度战略陪伴重点事项清单（讨论稿） (1).docx`
  - `日慈PPT（第一天） 2_日慈_20260211.pptx`
  - `副本日慈PPT——定稿 2_日慈_20260211.pptx`
  - `20250925092627-日慈X益语 陪伴第一次会议（定向会）-转写原文版-1 2_日慈_20260211.docx`
  - `副本日慈PPT——乐乐修改(0109) 2_日慈_20260211.pptx`
  - `20260417_154206_和日慈张真核对战略陪伴的进度.docx`

## 守卫要求
- `workspace/chat` 主回答链不会重新引入：
  - 状态池/会议池/任务池/判断池默认混入
  - 模板 fallback
  - 固定结构
  - 压缩回退
- `question_focus` 不会重新参与主回答塑形
- `raw_document_pack` 的现有限制参数不会继续漂移

## 解释
- 这份冻结清单的作用是把“该拆的半层”边界固定住。
- 后续真正替换时，不会继续在这条旧层上局部打补丁，而是直接用新的主回答链替换。
