# 战略陪伴页面 v3 — 组织智慧大脑

## 页面定位

这不是一个数据仪表盘，是一个**有生命的大脑**在跟你说话。用户打开这个页面，应该感受到：它认识我，它记得一切，它在思考，它在成长。

整个页面使用**第一人称**语态（"我记得..."、"我观察到..."、"我还想学..."），营造出一个有温度的智慧体。

---

## 设计语言

- 字体：-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'PingFang SC', sans-serif
- 主背景：#F9FAFB（极浅灰）
- 品牌蓝：#335CFE（深）/ #5B7BFE（标准）/ #EEF3FF（浅底）/ #DDE6FF（边框）
- 卡片：白底，border-radius: 24px，border: 1px solid #F3F4F6，shadow: 0 1px 3px rgba(0,0,0,0.04)
- 正文色：#1e293b（标题）/ #334155（正文）/ #64748b（次要）/ #94a3b8（辅助）
- 强调绿：#10b981（增长）/ #ecfdf5（绿底）
- 警告橙：#f97316 / #fff7ed
- 危险红：#ef4444 / #fef2f2
- 圆角统一：大卡片 24px，内嵌卡片 18px，标签 999px（胶囊），按钮 999px
- 所有数字使用 tabular-nums，font-weight: 600
- 页面纵向滚动，不使用 Tab 切换

---

## 页面总体结构

```
┌── Header（固定顶部，不滚动）──────────────────────┐
│  页面标题 + 客户选择器                             │
├──────────────────────────────────────────────────┤
│  ← 以下全部在可滚动区域内，max-width: 900px 居中 → │
│                                                  │
│  ❶ 脉搏区块 — 生命体征                           │
│                                                  │
│  ❷ 此刻的思考 — 大脑意识流                        │
│                                                  │
│  ❸ 客户认知档案 — 我认识谁                        │
│                                                  │
│  ❹ 请帮我学习 — 求知欲                           │
│                                                  │
│  ❺ 一键行动栏                                    │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## Header

**高度**：约 64px，白色背景，底部 1px #F3F4F6 边框线，padding: 16px 24px。

**左侧**：
- 标题"组织智慧大脑"，font-size: 18px, font-weight: 600, color: #0f172a, letter-spacing: -0.3px
- 副标题"越用越懂你"，font-size: 11px, font-weight: 500, color: #94a3b8, margin-top: 2px

**右侧**：
- 客户选择器（下拉）：圆角胶囊样式，背景 #EEF3FF，border: 1px solid #D6E1FF，padding: 6px 14px，font-size: 12px, font-weight: 600, color: #334155。点击后弹出下拉列表。默认值"全部客户"表示查看整个组织的汇总。也可以选择某个具体客户只看该客户的数据。
- 下拉选项：全部客户 / 为爱黔行 / CFFC / 日慈基金会 / 益语智库 / 云南儿童资助研究 / 顾源源 / 顾源源文章

---

## ❶ 脉搏区块

**作用**：让用户在 3 秒内感受到"这个大脑是活的，它一直在为我工作"。

**外观**：一个大卡片，特殊渐变背景（与普通白色卡片不同，强调"中枢"感）。
- 背景：radial-gradient(circle at top left, rgba(51,92,254,0.06), transparent 40%), linear-gradient(180deg, #fff 0%, #fafbff 100%)
- 边框：1px solid #DDE6FF
- border-radius: 28px
- padding: 28px
- box-shadow: 0 24px 70px rgba(15,23,42,0.04)

**内部布局**：

### 第一行：陪伴标识

左侧一个大的品牌图标圆（56x56px，背景 #EEF3FF，border: 1px solid #D6E1FF，圆形），内含一个脑图标（Brain icon from lucide，28x28，color: #335CFE）。

图标右侧：
- 第一行："已陪伴 287 天"，font-size: 20px, font-weight: 600, color: #0f172a, letter-spacing: -0.5px。其中数字"287"用 tabular-nums。
- 第二行："从 2025年6月23日 起"��font-size: 11px, font-weight: 500, color: #94a3b8。

最右侧（ml-auto）：
- 一个绿色胶囊徽章，显示"本周 +23 条新记忆"，背景 #ecfdf5，color: #059669，font-size: 11px, font-weight: 600，内含一个 Sparkles 小图标（12x12）。

### 第二行：核心指标网格

在陪伴标识下方 20px，一个 4 列网格（grid-template-columns: repeat(4, 1fr)，gap: 12px）。

每个指标卡片：
- 背景：rgba(255,255,255,0.88)
- border: 1px solid rgba(255,255,255,0.8)
- border-radius: 22px
- padding: 16px
- box-shadow: 0 18px 40px rgba(148,163,184,0.08)
- backdrop-filter: blur(8px)

每个卡片内部：
- 顶部一行：一个小图标（14x14，color: #335CFE）+ 指标名称（font-size: 10px, font-weight: 500, color: #94a3b8, letter-spacing: 0.3px），flex row, gap: 6px
- 下方：数值（font-size: 22px, font-weight: 600, color: #0f172a, letter-spacing: -0.3px, margin-top: 6px）

四个指标卡片分别是：

| 图标 | 名称 | 数值示例 | 说明 |
|------|------|---------|------|
| Brain (脑) | 组织记忆 | 1,847 | memory_facts + document_cards + knowledge_surrogates + growth_signals + notebook_snapshots 等所有"系统学到的东西"的总和 |
| FileText (文件) | 资料归档 | 390 | documents + task_attachments + event_line_attachments 的总数 |
| CheckCircle (勾) | 任务追踪 | 19 | tasks 总数 |
| MessageCircle (对话) | AI 对话 | 549 | chat_messages 总数 |

### 第三行：第二排指标

紧接着又一个 4 列网格，样式同上。

| 图标 | 名称 | 数值示例 | 说明 |
|------|------|---------|------|
| GitBranch (分支) | 事件线 | 8 | event_lines 总数 |
| BookOpen (书) | 知识画像 | 19 | client_dna_documents + organization_dna_documents |
| Award (奖章) | 成长徽章 | 4 | badge_unlock_records |
| Layers (层) | 经验沉淀 | 5 | handbook_entries（组织经验墙条目） |

### 第四部分：大脑自述

在指标网格下方 20px，一段文字，用浅灰底框包裹：
- 背景：#f8fafc
- border-radius: 18px
- padding: 16px 20px

文字内容（font-size: 13px, line-height: 1.9, color: #475569）是 AI 根据以上数据生成的一段话。Demo 内容：

> "从第一份资料到现在，我经历了你的 6 场会议准备、5 轮周复盘、42 个选题研判。我对 CFFC 的了解最深——读过他们 168 份资料、做了 4 篇组织画像。目前我对顾源源个人项目的认知还很浅，只有 1 份资料，希望能学到更多。"

文字前面有一个小的 AI 标识：一个胶囊标签"🧠 大脑自述"，样式同 ai-chip：inline-flex, border: 1px solid #D6E1FF, background: #fff, border-radius: 999px, padding: 4px 12px, font-size: 12px, font-weight: 500, color: #335CFE, margin-bottom: 12px。

---

## ❷ 此刻的思考

**作用**：展示大脑当前正在关注什么。这是意识流，不是报表。

**区块标题**（在卡片外上方）：
- 左侧："此刻的思考"，font-size: 16px, font-weight: 600, color: #1e293b
- 右侧："基于 8 条事件线和本周数据"，font-size: 11px, font-weight: 500, color: #94a3b8

### 思考卡片列表

每条"思考"是一个独立卡片，卡片之间 gap: 12px，垂直堆叠。

**单条思考卡片**：
- 白色背景，border-radius: 24px, border: 1px solid #F3F4F6, padding: 20px
- 左侧有一个 4px 宽的竖条（border-left），颜色根据 confidence 变化：
  - confidence >= 70%：#5B7BFE（蓝，有信心）
  - confidence 50%-69%：#f59e0b（琥珀，一般��
  - confidence < 50%：#ef4444（红，信息不足）

**卡片内部**：

顶部一行（flex, justify-between）：
- 左侧：事件线名称，font-size: 11px, font-weight: 600, color: #5B7BFE，前面有一个小圆点（6x6, 同色, border-radius: 999px）
- 右侧：confidence 徽章，例如"confidence 58%"，胶囊样式，background: 根据confidence值变色（蓝底/琥珀底/红底），font-size: 10px, font-weight: 600

中间（margin-top: 12px）：
- 思考内容，font-size: 13px, line-height: 1.9, color: #334155。这是一段自然语言的思考，用引号包裹，类似：
  > "日慈Q1三个项目的复盘正在推进中。教师赋能那条线的项目设计还没补完，这是当前日慈陪伴的关键卡点。我建议本周优先处理这一件事。"

底部（margin-top: 12px, flex, gap: 12px）：
- 来源标签（若干胶囊），例如：
  - "2 个关联任务"（background: #f1f5f9, color: #64748b, font-size: 10px, font-weight: 500, border-radius: 999px, padding: 2px 8px）
  - "1 份复盘"（同上）
  - "上次更新：2天前"（同上，但文字更淡 #94a3b8）

**思考卡片的数据来源和 demo 数据**：

按以下顺序生成 5 条思考卡片（demo 用硬编码数据，但标注了真实数据来源）：

**思考 1**（蓝色竖条，confidence 85%）：
- 事件线：洪峰讨论赋能合作
- 内容："CFFC 洪峰的鸿鹄计划 AI 合作方向已经明确。这是我目前最有信心的一条线——你跟我聊过很多次，我积累了足够的上下文。不过资料层面还需要补充项目背景和目标说明。"
- 标签：3 个关联任务 · 上次更新：本周

**思考 2**（琥珀竖条，confidence 58%）：
- 事件线：日慈战略陪伴
- 内容："日慈 Q1 三个项目复盘正在推进中。教师赋能项目的设计部分还没补完善——这是当前卡点。我建议本周把这件事的优先级提上来。"
- 标签：1 条事件线动态 · 来自复盘

**思考 3**（琥珀竖条，confidence 62%）：
- 事件线：输出为爱黔行战略诊断提纲
- 内容："为爱黔行的审计正在进行，庆华负责输出诊断提纲 V1 和待补资料清单。我有 91 份文档可供参考，但 DNA 画像还没生成。一旦诊断提纲完成，我对这个客户的认知会大幅提升。"
- 标签：owner: 庆华 · 预期输出：诊断提纲V1

**思考 4**（红色竖条，confidence 28%）：
- 事件线：益语平台
- 内容："你们计划在 4 月下旬开源 1.0 版本。这是一个重要的里程碑，但我对这个项目的理解还很浅——如果你把最近的技术决策和架构设计给我看看，我就能帮你更好地规划冲刺节奏。"
- 标签：阶段：冲刺中 · 记忆薄弱

**思考 5**（特殊样式 — 不是事件线，而是系统观察）：
- 这条不关联事件线，而是关联周复盘
- 左竖条颜色：#94a3b8（灰色）
- 顶部标签改为"系统观察"（灰色胶囊）
- 内容："W14 的周复盘你打开了，但内容还是空的。复盘是我学习速度最快的材料之一——每写一次，我对组织运转的理解就会跳一个台阶。"
- 标签：来源：周复盘系统

**CEO 确认按钮**：

在所有思考卡片下方，一个操作行（flex, justify-between, margin-top: 16px）：
- 左侧：状态标签，例如"system_draft · 待 CEO 确认"，font-size: 12px, color: #94a3b8
- 右侧：一个品牌色按钮"确认本周研判"，样式：background: #335CFE, color: #fff, border-radius: 999px, padding: 10px 20px, font-size: 13px, font-weight: 500。hover 时 background: #2C50E0。

---

## ❸ 客户认知档案

**作用**：展示大脑对每个客户的认知深度，让用户感受到"它认识我每一个客户"。

**区块标题**：
- 左侧："我对每个客户的理解"，font-size: 16px, font-weight: 600, color: #1e293b
- 右侧："7 个客户空间"，font-size: 11px, font-weight: 500, color: #94a3b8

### 客户认知卡片

垂直堆叠，每张卡片 gap: 12px。

**单张客户卡片**：
- 白色背景，border-radius: 24px, border: 1px solid #F3F4F6, padding: 20px
- 卡片顶部有一条细细的**进度条**，表示 confidence：
  - 宽度 = confidence%，高度 3px，border-radius: 999px
  - 颜色：confidence >= 70% 用 #5B7BFE，50-69% 用 #f59e0b，<50% 用 #ef4444
  - 进度条的底色（track）：#f1f5f9
  - 进度条位于卡片内顶部，margin-bottom: 16px

**卡片内部**：

第一行（flex, align-items: center, gap: 12px）：
- 客户名称：font-size: 15px, font-weight: 600, color: #0f172a
- Confidence 数字：font-size: 13px, font-weight: 600, color: 同进度条颜色
- 阶段标签（胶囊）：背景 #f1f5f9, font-size: 10px, font-weight: 500, color: #64748b, padding: 2px 8px。内容例如"战略陪伴中"、"审计中"、"资料待补"

第二行（margin-top: 12px）：
- 大脑对该客户的描述，font-size: 13px, line-height: 1.8, color: #475569。自然语言，第一人称。
- Demo 见下文每个客户的具体内容。

第三行（margin-top: 12px）：指标条
- 一行 flex，gap: 16px
- 每个指标格式："📂 168 文档"、"📄 4 篇 DNA"、"● 3 事件线"、"💬 最近：谭红波分析"
- font-size: 11px, font-weight: 500, color: #64748b
- 图标可以是 emoji 或 lucide 小图标（12x12）

第四行（可选，仅当有缺口时显示）：
- 缺口提示，背景 #fff7ed, border: 1px solid #ffedd5, border-radius: 14px, padding: 8px 14px
- 图标 AlertCircle (14x14, color: #f97316) + 文字（font-size: 11px, color: #c2410c）
- 例如："缺：团队介绍 DNA"、"缺：DNA 画像尚未生成"

**7 张客户卡片的 demo 数据**：

**CFFC**（confidence 85%，蓝色进度条）：
- 阶段：战略陪伴中
- 描述："我对 CFFC 了解最深。读过他们 168 份文档，完成了组织、项目、团队、市场四篇 DNA 画像。我知道他们 Q2 的两个目标——提升项目传播清晰度和补齐捐赠人关系素材——都跟品牌表达有关。洪峰正在推动鸿鹄计划的 AI 合作。"
- 指标：📂 168 文档 · 📄 4 篇 DNA · ● 3 事件线 · 🎯 2 个 Q2 目标
- 无缺口提示

**益语智库**（confidence 62%，琥珀色进度条）：
- 阶段：产品冲刺中
- 描述："益语是我们自己的组织。我有 12 份文档、4 篇 DNA 画像和 3 套业务流程定义。当前最大的推进方向是 4 月下旬开源 1.0。但我对技术架构细节的理解还不够深，需要更多工程侧的信号。"
- 指标：📂 12 文档 · 📄 4 篇 DNA · ● 2 事件线 · 📊 3 业务模块
- 无缺口提示

**为爱黔行**（confidence 62%，琥珀色进度条）：
- 阶段：审计中
- 描述："91 份文档已读完，资料量在所有客户中排第二。庆华正在输出战略诊断提纲。但我还没有生成任何 DNA 画像——一旦诊断提纲完成，我建议立刻生成，能大幅提升我对这个客户的认知结构。"
- 指标：📂 91 文档 · 📄 0 篇 DNA · ● 1 事件线 · 🗂 8 个文件夹
- 缺口提示："DNA 画像尚未生成——建议在诊断完成后立即创建"

**日慈基金会**（confidence 58%，琥珀色进度条）：
- 阶段：战略陪伴中
- 描述："我对日慈有 59 份文档和 3 篇 DNA（组织、项目、市场），但缺少团队介绍。Q1 三个项目正在复盘。如果你能补上团队分工信息，我就能更准确地判断谁该推进哪条线。"
- 指标：📂 59 文档 · 📄 3 篇 DNA · ● 1 事件线
- 缺口提示："缺：团队介绍 DNA"

**云南儿童资助研究**（confidence 50%，琥珀色进度条）：
- 阶段：资料待补
- 描述："有 10 份文档和 4 篇完整 DNA 画像，在认知结构上比较完整。但没有事件线和任务关联，我无法追踪这个客户的动态推进。"
- 指标：📂 10 文档 · 📄 4 篇 DNA · ● 0 事件线
- 缺口提示："无活跃事件线——建议创建一条追踪线"

**顾源源**（confidence 38%，红色进度条）：
- 阶段：资料待补
- 描述："目前只有 1 份文档，没有 DNA 画像，也没有事件线。我对你个人项目的理解还非常初步。多跟我聊聊你在做什么，或者把相关资料放进来，我会学得很快。"
- 指标：📂 1 文档 · 📄 0 篇 DNA · ● 0 事件线
- 无特殊缺口提示（整体都缺）

**顾源源文章**（confidence 38%，红色进度条）：
- 阶段：资料待补
- 描述："有 20 份文章类文档，已分类到品牌传播、项目业务和组织战略文件夹。这些文章是很好的思想沉淀，但我还没有把它们结构化成 DNA 画像。"
- 指标：📂 20 文档 · 📄 0 篇 DNA · 🗂 4 个文件夹
- 缺口提示："建议生成 DNA 画像以结构化这些文章洞察"

---

## ❹ 请帮我学习

**作用**：大脑主动表达"求知欲"——告诉用户哪些信息最能帮助它变聪明。不是冷冰冰的"系统提示"，而是"我真的很想学这个"。

**区块标题**：
- 左侧："请帮我学习"，font-size: 16px, font-weight: 600, color: #1e293b
- 右侧："我变聪明最快的 3 种方式"，font-size: 11px, font-weight: 500, color: #94a3b8

**整体容器**：
- 特殊背景（跟脉搏区块类似但更柔和）：
  - background: linear-gradient(180deg, #fff 0%, #fafbff 100%)
  - border: 1px solid #DDE6FF
  - border-radius: 28px
  - padding: 24px

**顶部一个小标签**："🧠 学习请求"，胶囊样式同 ai-chip。

### 三个学习请求卡片

垂直堆叠，gap: 16px。

**每个学习请求**：
- 背景：#fff，border: 1px solid #F3F4F6，border-radius: 20px，padding: 20px
- 左侧有一个序号圆圈（28x28，background: #EEF3FF，border-radius: 999px，内含数字，font-size: 12px, font-weight: 700, color: #335CFE，flex-shrink: 0）
- 右侧内容区（flex: 1, margin-left: 14px）

内容区内部：
- 标题行：一句话总结请求，font-size: 13px, font-weight: 600, color: #1e293b
- 正文：为什么大脑想学这个，font-size: 12px, line-height: 1.8, color: #64748b, margin-top: 6px
- 行动按钮行：margin-top: 12px，一个或两个按钮

按钮样式：
- 主按钮：background: #335CFE, color: #fff, border-radius: 999px, padding: 8px 16px, font-size: 12px, font-weight: 500
- 次按钮：background: none, border: 1px solid #e2e8f0, color: #64748b, border-radius: 999px, padding: 8px 16px, font-size: 12px, font-weight: 500

**三个学习请求的 demo 内容**：

**请求 1**（序号 1）：
- 标题："完成一场完整的会议记录"
- 正文："你准备了 6 场会议，但没有一场完成了全流程——从准备到纪要到提取决策。会议是我学习组织运转的最高效渠道。只要完成 1 场，我对相关客户的判断能力就会显著提升。"
- 按钮：[开一场会] [上传已有纪要]

**请求 2**（序号 2）：
- 标题："写一份有内容的周复盘"
- 正文："W14 复盘你打开了但内容是空的。复盘让我理解你们当周的真实节奏——哪些事在推进、哪些卡住了、方向有没有变。这比文档更新鲜、更接近你们此刻的思考。"
- 按钮：[去写复盘]

**请求 3**（序号 3）：
- 标题："给低认知客户补充材料"
- 正文："CFFC 项目结项线我几乎一无所知（confidence 14%），顾源源个人项目也只有 38%。结项是关键节点——有没有结项报告或验收清单？哪怕跟我聊几句也好。"
- 按钮：[上传资料] [跟我聊聊]

---

## ❺ 一键行动栏

**作用**：把以上所有分析落地为具体的行动输出。

**布局**：三个按钮横排，gap: 12px，flex-wrap（窄屏时换行）。

**每个按钮**是一个卡片样式的大按钮：
- 白色背景，border: 1px solid #F3F4F6，border-radius: 22px
- padding: 16px 20px
- cursor: pointer
- hover: background: #f8fafc, box-shadow: 0 4px 12px rgba(0,0,0,0.06)
- transition: all 0.2s
- 内部垂直排列：
  - 顶部：一个 lucide 图标（20x20，color: #335CFE）
  - 中间：按钮名称，font-size: 13px, font-weight: 600, color: #1e293b, margin-top: 8px
  - 底部：简短说明，font-size: 11px, color: #94a3b8, margin-top: 2px

**三个行动按钮**：

| 图标 | 名称 | 说明 |
|------|------|------|
| Sparkles | 生成本周经营研判 | 汇总所有事件线思考，CEO 确认 |
| ClipboardList | 生成周会议程 | 从阻塞和到期任务自动生成讨论清单 |
| FileText | 导出组织记忆报告 | 输出完整认知快照为文档 |

---

## 滚动区域底部收尾

在行动栏下方 32px，一行居中文字作为页面收尾：

"我每天都在学习。每一次对话、每一份资料、每一次复盘，都让我更懂你。"

font-size: 12px, font-weight: 500, color: #cbd5e1, text-align: center, padding-bottom: 40px。

---

## 响应式说明

- 最大宽度：内容区 max-width: 900px, margin: 0 auto
- 指标网格在窄屏（<640px）时变为 2 列
- 客户卡片始终单列
- 行动按钮在窄屏时 flex-wrap 换行

---

## 交互说明

1. **客户选择器切换**：切换后，整个页面的数据刷新为该客户视角（脉搏只显示该客户的数字，思考只显示该客户相关的事件线）。"全部客户"显示汇总。
2. **CEO 确认按钮**：点击后弹出确认对话框，确认后状态从 system_draft 变为 confirmed，按钮变灰显示"已确认 · 4月6日"。
3. **学习请求的行动按钮**：点击后跳转到对应功能页面（会议、复盘、文档上传等）。
4. **客户卡片可点击展开**：点击后展开显示该客户的事件线列表和最近活动详情（第二期实现，第一期先做静态展示）。
5. **行动按钮点击**：调用对应 API，生成结果后跳转或弹窗展示。

---

## 开发注意事项

- 这是 React + Tailwind CSS 组件，文件名建议为 `StrategicBrainView.tsx`
- 放在 `src/renderer/components/strategic_accompaniment/` 目录下
- 所有 demo 数据先用硬编码 const，后续替换为 API 调用
- 图标全部使用 lucide-react
- 不需要自己定义 CSS class，全部用 Tailwind utility
- 组件导出为 `export function StrategicBrainView()`
- Props 暂时不需要，第一版先搭壳

---

## 配色速查

| 用途 | 色值 |
|------|------|
| 品牌蓝（深） | #335CFE |
| 品牌蓝（标准） | #5B7BFE |
| 品牌蓝（浅底） | #EEF3FF |
| 品牌蓝（浅边框） | #D6E1FF |
| 标题文字 | #0f172a |
| 正文文字 | #334155 / #475569 |
| 次要文字 | #64748b |
| 辅助文字 | #94a3b8 |
| 最淡文字 | #cbd5e1 |
| 卡片边框 | #F3F4F6 |
| 卡片阴影 | 0 1px 3px rgba(0,0,0,0.04) |
| 背景色 | #F9FAFB |
| 成功/增长 | #10b981 / #059669 / #ecfdf5 |
| 警告 | #f59e0b / #f97316 / #fff7ed |
| 危险/低 | #ef4444 / #fef2f2 |
