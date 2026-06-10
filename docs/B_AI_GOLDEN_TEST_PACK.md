# B AI Golden Test Pack · 7 类用户输入样本

> **冻结**: 2026-05-23 19:15
> **作用**: 所有 B 评估脚本都从这里取输入, 保证可重复 + 可比较.
> **路径**: `fixtures/golden/*.txt`

每个样本都附:
- 用户输入原文 (`fixtures/golden/<key>.txt`)
- 期望模块调用
- 期望使用 evidence
- 期望生成成果
- 期望进澄清
- 期望进 Approval Queue

---

## 样本 1: 复杂会议纪要 (`fixtures/golden/meeting_mingyuan.txt`)

**用户输入**: 顾源源 5/23 V3.0 钦定的明远公益基金会会议纪要 (含 6 子目标).

**期望调用模块** (≥ 6):
1. meeting-minutes/process (会议摘要)
2. contracts/draft (合同草稿)
3. clients/{id}/strategic-cockpit/meeting-pack (会谈提纲)
4. intelligence/brand-mirror/analyze (品牌检索)
5. clients/{id}/brand-proposition (品牌建议)
6. templates/generate (理事会简版说明)

**期望 evidence**:
- atomic_facts ≥ 5 (会议事实)
- risks ≥ 1 (品牌口径混乱)
- commitments ≥ 2 (下周二行动清单, 下周三会谈)
- clarifications ≥ 3 (预算上限/陈秘书长拍板/试点服务边界)

**期望成果包** (≥ 7 件):
1. 会议摘要
2. 合同草稿 (含待确认条款)
3. 下周三会谈任务草稿
4. 下次会谈提纲
5. 品牌情报检索结果
6. 品牌调整建议
7. 理事会 2 页简版说明

**期望进澄清**:
- 预算是否真不超过 30 万
- 陈秘书长是否为最终拍板人
- 试点期服务边界

**期望进 Approval**:
- 合同草稿进 approval_queue
- 下周三会谈正式任务进 approval_queue
- 对外材料发送进 approval_queue

---

## 样本 2: 20 文件导入 (`fixtures/golden/files_20.txt`)

**用户输入**: 20 个文件标题 + 元信息 (模拟 batch import).
- 4 份合同 (`xxx_合同.docx` / `补充协议_v2.docx`)
- 6 份会议纪要 (`会议纪要_2026_03_15.docx`)
- 4 份方案 (`青年行动者培养计划_v3.docx`)
- 3 份复盘 (`Q1_复盘.md`)
- 3 份附件 (`理事会_2024_年报.pdf`)

**期望调用模块** (≥ 3):
1. workspace/smart-import (导入入库)
2. file_identity_classifier (识别身份)
3. contract_structure_parser (合同结构, 合同类)

**期望 evidence**:
- file_identities +20 (每文件 1)
- contract_structures ≥ 4 (4 份合同全解析)

**期望成果**:
- 每文件 type/role 识别 (准确率 ≥ 95%)
- 4 份合同结构卡片 (甲乙方/项目/金额/期限/责任 ≥ 5/6 字段)
- 低置信文件进 clarification_records

**期望进澄清**:
- 不确定文件身份 (如"复盘.md" 缺日期上下文)

---

## 样本 3: 工作台问答 10 真问题 (`fixtures/golden/qa_10.txt`)

**用户输入**: 10 个真实客户问题 (顾源源 R4-P0 §6.1 钦定):

1. 这个客户当前最重要的项目是什么?
2. 最新预算是多少? 旧版本是多少?
3. 5 月补充协议是哪一份?
4. 这份协议是谁和谁签的?
5. 合同里约定了哪些交付?
6. 最近复盘提到的合作和哪份合同有关?
7. 哪些内容只有用户口述?
8. 当前最大的风险是什么?
9. 哪些问题需要问客户确认?
10. 下一步最应该做什么?

**期望调用模块**:
- workspace/chat (单 endpoint, 内部走 build_company_brain_context)

**期望 response 顶层 5 字段** (A 18:10 P0-2):
- evidenceTypes ≥ 3
- usedTables ≥ 2
- singleFileOnly = false
- uncertaintyItems ≥ 0
- proposedClarifications (针对题 9)

**通过条件**:
- ≥ 9/10 题: evidence_types ≥ 3 + 引用源 ≥ 2 + single_file_only=false
- 题 7 (口述内容): 必须正确区分 source_type = client_internal_doc vs user_oral
- 题 9 (问客户): 必须真生成 proposed_clarifications

---

## 样本 4: 周复盘文本 (`fixtures/golden/weekly_review.txt`)

**用户输入**:
```
本周和明远基金会的合作有进展, 客户确认了 6 个月试点方向.
预算还没定但客户口头说不超过 30 万.
"青年行动者培养计划" 品牌问题客户也认了, 我们要做品牌建议.
下周三再约一次, 需要我们准备会谈提纲 + 理事会汇报材料.
回顾 5 月初的补充协议, 当时金额是 300 万, 这次试点估计不到这个规模.
内部李老师推进, 但拍板的是陈秘书长.
本周风险: 学校配合度不确定, 教师端试点时间紧.
```

**期望调用模块**:
1. weekly-review (周复盘 endpoint, 待 A 暴露)
2. historical_material_resolver ("5 月初补充协议" 回指 5/18 测试项目A v2 300 万)

**期望成果**:
- 复盘卡 (本周变化 + 历史回指 + 风险 + 下周重点)
- historical_reference_links +1 (5 月补充协议)

---

## 样本 5: 任务创建 (`fixtures/golden/task_create.txt`)

**用户输入**:
```
新建任务: 给明远基金会准备会谈提纲
负责人: 王主任
截止: 下周二
关联客户: 明远公益基金会
关联事件线: 战略陪伴试点
```

**期望调用模块**:
1. tasks/create (任务 endpoint)
2. (R3) historical_material_resolver ("会谈提纲" 关联到客户记忆)
3. (R3) approval_queue (正式发布任务进审批)

**期望 evidence**:
- task_drafts +1
- approval_queue +1 (task.publish action)
- event_line_activities +1 (任务挂到事件线)

---

## 样本 6: 外部情报 (`fixtures/golden/intelligence_brand.txt`)

**用户输入**:
```
帮我查青年行动者培养计划同行案例, 看公益基金会怎么给这种项目做品牌定位.
重点找:
- 类似项目的命名风格
- 是叫"项目"还是"计划" 还是"网络"
- 主视觉关键词
- 受众沟通语气
```

**期望调用模块**:
1. intelligence/brand-mirror/analyze (品牌检索)
2. intelligence/sentiment/refresh (情报刷新)
3. external_evidence_card_writer (外部证据卡)

**期望 evidence**:
- external_evidence_cards +1 (needs_confirm 状态)
- 不覆盖内部 atomic_facts

**硬门槛**: external 不能 supersedes 内部权威 (R4-P0 H5).

---

## 样本 7: 方法卡 / 组织计划 (`fixtures/golden/method_card.txt`)

**用户输入**:
```
方法卡: 给公益客户做战略陪伴的 4 个关键节点
1. 第一次面谈: 听他们讲组织故事, 不评判
2. 第一次方案: 不要急着出完整方案, 先给 1 页"我们理解你"
3. 试点期: 严格 6 个月, 不延长
4. 复盘: 用客户的语言总结, 不用咨询术语

这是适用于公益客户的方法, 不适用于商业客户.
```

**期望调用模块**:
1. method_card/create (方法卡 endpoint)
2. (R3) source_type = system_derived 隔离, 不进 atomic_facts

**期望 evidence**:
- method_cards +1 (system_derived)
- atomic_facts +0 (方法卡不污染客户事实)

**硬门槛**: 方法卡不能写进 client_internal_doc source_type (R3 H6).

---

## 选择哪几个样本测哪类评估

| 评估 | 用哪些样本 |
|---|---|
| R2 | 样本 1 (会议纪要), 跑 meeting-minutes/process |
| R4-P0 工作台问答 | 样本 3 (10 问) |
| R4-P0 文件导入 | 样本 2 (20 文件) |
| R4-P0 战略陪伴 | 样本 1 + 样本 4 (复盘+历史回指) |
| V3.0 内置驱动 | 样本 1 (明远会议纪要) |
| V3.0 外置 Agent | 样本 1 (同输入) |
| V3.0 数据缺口主动 | 样本 1 (缺预算/品牌历史) |

---

## 文件清单

```
fixtures/golden/
├── meeting_mingyuan.txt    样本 1 · 复杂会议纪要 (V3.0 标准输入)
├── files_20.txt            样本 2 · 20 文件导入 (R4-P0 P0-3)
├── qa_10.txt               样本 3 · 工作台 10 真问题 (R4-P0 P0-2)
├── weekly_review.txt       样本 4 · 周复盘 + 历史回指
├── task_create.txt         样本 5 · 任务创建 (R3 关联客户记忆)
├── intelligence_brand.txt  样本 6 · 外部情报 (R3 H5 不覆盖)
├── method_card.txt         样本 7 · 方法卡 (R3 H6 不污染)
└── README.md               (本目录索引, 自动生成)
```

---

**Author**: AI B · 2026-05-23 19:15
**冻结**: V1 (修改要 commit 改 V2, 保留 V1)
**关联**: docs/B_AI_EVAL_STANDARD_V1.md (评估标准)
