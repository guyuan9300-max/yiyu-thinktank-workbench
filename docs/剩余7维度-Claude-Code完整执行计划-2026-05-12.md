# 数据中心剩余 7 个维度 · Claude Code 完整执行计划

**适用对象：** Claude Code（CLI 兄弟实例，或多个 session 并行）  
**项目根：** `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench`  
**起草日期：** 2026-05-12  
**预计总工作量：** 26-32 个迭代，800-1500 次工具调用，**周期 2-3 个月**

---

## Part 0 · 执行框架（必读）

### 0.1 全局态势

数据中心一共审计出 9 个功能维度。当前状态：

| # | 维度 | 完成度 | 状态 | 责任人 |
|---|---|---|---|---|
| 1 | 理解深度 | 20% → 推进中 | ✅ 已启动 | Cowork（`feature/understanding-depth`） |
| 2 | 主动能力 | 15% → 待启动 | 🟡 计划完成 | Claude Code（`feature/proactive-capability`） |
| 3 | **输入广度** | **30%** | ❌ **本计划覆盖** | Claude Code |
| 4 | **生产能力** | **15%** | ❌ **本计划覆盖** | Claude Code |
| 5 | **长期记忆** | **25%** | ❌ **本计划覆盖** | Claude Code |
| 6 | **真计算能力** | **5%** | ❌ **本计划覆盖** | Claude Code |
| 7 | **协作能力** | **30%** | ❌ **本计划覆盖** | Claude Code |
| 8 | **外部接入** | **25%** | ❌ **本计划覆盖** | Claude Code |
| 9 | **反思自知** | **20%** | ❌ **本计划覆盖** | Claude Code |

本文覆盖 7 个维度（#3 到 #9）。

### 0.2 阅读这份计划之前必读

1. **`docs/客户计算中心-功能差距清单-2026-05-12.md`** — 7 维度的完整审计与具体缺失项
2. **`docs/数据中心-未完成清单-2026-05-12.md`** — 全局未完成清单
3. **`docs/主动能力-Claude-Code执行计划-2026-05-12.md`** — 兄弟线程的工作模式（你按同一套）
4. **`docs/理解深度-执行计划-2026-05-12.md`** — Cowork 的执行模式参考

### 0.3 优先级矩阵（看完直接选切入点）

```
                    高业务价值
                         │
        ┌────────────────┼────────────────┐
        │                │                │
  [输入广度]         [生产能力]      [真计算能力]
   ★★★★            ★★★★          ★★★★★
   (P0 录音)         (P0 PPT/Excel)  (招牌"计算中心")
        │                │                │
        ├────────────────┼────────────────┤
        │                │                │
   [长期记忆]         [协作能力]      [外部接入]
   ★★★              ★★★            ★★
        │                │                │
        └────────────────┼────────────────┘
                         │
                    [反思自知]
                       ★★
                    (依赖前者)
```

**P0（业务硬伤，最先做）：**
1. **输入广度** — 录音/邮件不能进系统是战略陪伴硬伤
2. **生产能力** — 内容生产场景只能输出 Word，是内容业务硬伤

**P1（AI 时代要素）：**
3. **真计算能力** — "计算中心"名实相符的根本
4. **长期记忆** — AI 主理人需要个性化前置
5. **协作能力** — 三角色组织运作前置

**P2（提升 + 完善）：**
6. **外部接入** — AI 世界知识扩展
7. **反思自知** — 元能力，依赖前者

### 0.4 依赖关系图（影响开工顺序）

```
独立可启动（任何顺序都行）：
├── 输入广度（录音 ASR / 邮件 IMAP）
├── 生产能力（PPT / Excel / PDF 生成）
├── 真计算能力（NL→SQL + 统计引擎）
└── 外部接入（搜索 API / 实时信号）

依赖其他线程：
├── 长期记忆 ← 依赖 理解深度 实体抽取
├── 协作能力 ← 依赖 主动能力 通知中心
└── 反思自知 ← 依赖 上面几个维度（它是元能力层）
```

### 0.5 推荐执行顺序

**Wave 1（立即可启动，独立）：**

1. 输入广度（首推 — 录音转写解决战略陪伴最大痛点）
2. 生产能力（同步推 — 内容生产场景立即用得上）
3. 真计算能力（同步推 — 让"计算中心"真名副其实）

**Wave 2（等主动能力 A2/A3 完成后开工）：**

4. 协作能力（依赖 主动能力的通知中心）

**Wave 3（等理解深度迭代 2 完成后开工）：**

5. 长期记忆（依赖 理解深度的实体基础设施）

**Wave 4（最后做，且依赖前者已落地）：**

6. 外部接入（独立但优先级 P2）
7. 反思自知（元能力，需要看前者效果再设计）

### 0.6 工作模式

跟"理解深度"和"主动能力"线程相同的**六步迭代**：

```
① 目标锁定（量化验收 + UI 验证场景）
② 方案确认（停问用户）
③ 实现
④a 代码验证（pytest 通过 + 回归无新红）
④b UI 验证（重启 dev app + 真实操作 + 截图对比）
⑤ 集成与提交（commit + 进度文档 + checkpoint）
```

**强制规则：** 没量化验收不进 ②；没用户确认不进 ③；④a 或 ④b 失败回 ③。

### 0.7 分支策略

每个维度独立分支：

```
feature/input-breadth         （输入广度）
feature/production-capability （生产能力）
feature/long-term-memory      （长期记忆）
feature/real-compute          （真计算能力）
feature/collaboration         （协作能力）
feature/external-access       （外部接入）
feature/self-reflection       （反思自知）
```

**分支起点：** 一律从 `main` 起，**不要**从其他 `feature/*` 起（避免互相依赖），合并时各自走 PR。

### 0.8 与已启动两条线程的协调

**冲突探测脚本（每次开工前跑）：**

```bash
cd /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench
git fetch origin
# 看 Cowork 改了什么
git log --oneline main..feature/understanding-depth 2>/dev/null | head -10
# 看主动能力改了什么
git log --oneline main..feature/proactive-capability 2>/dev/null | head -10
# 看你即将动的文件他们动过没
git diff main..feature/understanding-depth --stat 2>/dev/null | head -20
git diff main..feature/proactive-capability --stat 2>/dev/null | head -20
```

**潜在冲突高发文件：**

| 文件 | 几条线程会动 | 协调办法 |
|---|---|---|
| `backend/app/main.py` startup 区 | 4+ | 统一进 `backend/app/startup_hooks.py` |
| `backend/app/db.py` | 全部 | 只在末尾加 `CREATE TABLE IF NOT EXISTS` |
| `backend/app/models.py` | 全部 | 只加 Pydantic 模型，不动现有 |
| `backend/pyproject.toml` 依赖 | 多 | 新依赖必问用户 |
| `src/renderer/App.tsx` | 4+ | 切分 SidebarNav 改动到独立文件 |
| `src/renderer/components/data_center/DataCenterOpsPanel.tsx` | 多 | 各加独立 tab |

### 0.9 测试与 UI 验证基础设施

**先决条件：** Task #28（dev app 自主重启机制）必须完成。如果还没，先做 Task #28（详见 `docs/understanding-depth-progress.md`）。

**测试运行：**

```bash
cd backend && uv run pytest tests/ --tb=short -v  # 全量
cd backend && uv run pytest tests/test_<新模块>.py -v  # 单测
```

**UI 验证：** 改完 Python 后用 Task #28 提供的菜单项（Cmd+Shift+B）重启 backend，截图对比 before/after。

---

## Part 1 · 输入广度（剩 70%）

### 1.1 现状（来自审计）

**已实现：**
- 图片 OCR（`knowledge_v2.py:1334-1345`，AI 视觉模型）
- PDF OCR
- 网页与链接（`internet_crawler.py` + `link_material_import.py` 走 yt-dlp）
- 飞书妙记入站

**雏形 / 关键缺失：**
- **录音转文字** — 只有 B 站/小红书走 link_material，**直接上传 .m4a/.mp3/.wav 没入口**；移动端 `/mobile/recordings/text-ingest` **只收文本**
- **视频** — 仅 B 站/小红书白名单，YouTube/抖音/本地 mp4 不支持
- **表格数据** — `.xlsx/.pptx` 拆 XML 抽文字，**不保留行列结构**
- **邮件接入** — Gmail/Outlook/企业邮箱 0 代码
- **IM** — 飞书只发不收，企业微信/Slack/钉钉 0 代码
- **Notion / 语雀 / 飞书文档** — 无授权读取
- **手写笔记 / 剪贴板截图 / 二维码** — 全无

### 1.2 子能力拆解（5 个）

| # | 子能力 | 优先级 | 难度 |
|---|---|---|---|
| I1 | 直接上传录音文件（ASR 转写） | ⭐⭐⭐⭐⭐ | 中 |
| I2 | 邮件接入（Gmail/Outlook + IMAP） | ⭐⭐⭐⭐⭐ | 高 |
| I3 | IM 历史拉取（飞书群消息历史 + 企微/钉钉） | ⭐⭐⭐ | 中 |
| I4 | 文档结构化（保留 Excel 行列 / PPT 结构 / Notion 块） | ⭐⭐⭐ | 中 |
| I5 | 视频通用化（YouTube/抖音/本地 mp4） | ⭐⭐ | 中 |

### 1.3 迭代设计

#### 迭代 I0 · 准备工作

- 新分支 `feature/input-breadth`（起点 main）
- 跑测试基线
- 新建 `docs/input-breadth-progress.md`
- 审计当前 ASR / 邮件相关代码

#### 迭代 I1 · 录音上传转写（**P0 业务硬伤**）

**一句话目标：** 用户能直接在客户工作台上传 .m4a/.mp3/.wav 文件，系统自动转写文字后进入资料库。

**量化验收：**
1. [ ] 前端：客户工作台拖拽上传支持 `.m4a/.mp3/.wav/.flac/.aac` 五种音频格式
2. [ ] 新建 `backend/app/services/audio_transcription.py`：
   - 选型决策：先用 OpenAI Whisper API（如已有 OpenAI key）或飞书妙记（如已接入），不做本地推理
   - `transcribe_audio(file_path) -> TranscriptionResult` 公共 API
   - 返回结构：`text / segments (with timestamps) / language / duration`
3. [ ] 新建 `audio_transcription_jobs` 表（沿用 `knowledge_jobs` pattern）：状态机 queued/running/done/failed
4. [ ] 接入 `ingest_document_knowledge`：转写文件落地为 `.transcript.md` 走正常 ingest 流程，原始音频归档
5. [ ] 至少 5 个 pytest 测试（mock ASR API）
6. [ ] UI 验证：上传一份 1 分钟测试录音，5-30 秒内看到 transcript 文档出现在客户文件夹

**预算：** 40-55 工具调用

**关键决策点（必问用户）：**
- 用 OpenAI Whisper API（联网 + 隐私顾虑）还是本地 whisper.cpp（成本高 + 慢）？
- 上传文件大小上限（建议 100MB / 60min）

#### 迭代 I2 · 邮件接入（**P0 业务硬伤**）

**一句话目标：** 用户授权 Gmail / Outlook 后，系统能拉取并定期同步指定文件夹的邮件作为客户资料。

**量化验收：**
1. [ ] 新依赖：`google-auth + google-api-python-client`（Gmail）或 `msal + requests`（Microsoft Graph）
2. [ ] 新建 `email_accounts` 表：用户绑定的邮箱账号 + OAuth refresh token + 选定文件夹
3. [ ] 新建 `email_ingest_runs` 表：每次同步的记录
4. [ ] OAuth 流程：renderer 弹出系统浏览器走 OAuth → 后端拿 token → 加密存储
5. [ ] `backend/app/services/email_ingest.py`：定时拉取 + 去重 + 入库
6. [ ] 邮件 → markdown 转换（headers + body，附件单独处理）
7. [ ] 与 主动能力的调度器 整合（注册"每小时拉一次"任务）
8. [ ] 至少 6 个测试（mock IMAP/Graph API）
9. [ ] UI 验证：客户工作台新增"邮箱"页签，绑定一个测试邮箱，5 分钟内能看到最近邮件

**预算：** 60-80 工具调用

**关键决策点：**
- Gmail 还是 Outlook 先做？
- 是否支持 IMAP 通用协议（覆盖企业邮箱）？

**警告（安全）：**
- OAuth token 必须加密存储
- 邮件内容可能含敏感信息，确认权限边界

#### 迭代 I3 · IM 历史拉取（飞书群 + 企微 + 钉钉）

**P1，先做飞书。** 飞书已有 SDK 接入，扩展拉群消息历史相对低成本。

**量化验收：**
1. [ ] 飞书：扩展 `feishu_sync.py` 加群消息历史 API
2. [ ] 新建 `im_messages` 表
3. [ ] 用户能选哪些群作为客户的 IM 来源
4. [ ] 至少 4 个测试

**预算：** 30-40

#### 迭代 I4 · 文档结构化

**P1，让 Excel 不再被当字符串读。**

**量化验收：**
1. [ ] 新依赖：`openpyxl`
2. [ ] `.xlsx` 走专用 parser：保留 sheet 名 / 行列 / 公式 / 表头
3. [ ] 新增 `v2_chunks` 字段 `structure_type: text|table|formula|...`
4. [ ] 表格 chunk 在检索时按行/列粒度匹配
5. [ ] 至少 4 个测试

**预算：** 30-40

#### 迭代 I5 · 视频通用化

**P2。** YouTube/抖音/本地 mp4 走 ffmpeg 抽音轨 + ASR。

**量化验收：**
1. [ ] 新依赖：`ffmpeg-python`
2. [ ] `link_material_import` 移除 B 站/小红书白名单
3. [ ] 本地 mp4 上传走 ffmpeg → 音轨 → I1 的 ASR pipeline
4. [ ] 至少 3 个测试

**预算：** 25-35

---

## Part 2 · 生产能力（剩 85%）

### 2.1 现状

**已实现：**
- Word 报告（`python-docx` + `template_fill.py`）

**几乎全军覆没：**
- PowerPoint（无 python-pptx）
- Excel（无 openpyxl）
- PDF 导出（无 reportlab）
- 公众号 / 网站文章
- 图表（无 matplotlib/plotly/echarts）
- 思维导图（无 mermaid/markmap）
- 邮件 / IM 格式输出
- 可分享卡片（朋友圈/小红书 card）
- TTS / 朗读

### 2.2 子能力拆解（5 个）

| # | 子能力 | 优先级 |
|---|---|---|
| P1 | PPT 生成 | ⭐⭐⭐⭐⭐ |
| P2 | Excel 生成 | ⭐⭐⭐⭐⭐ |
| P3 | PDF 导出 | ⭐⭐⭐⭐ |
| P4 | 图表生成（mermaid + plotly） | ⭐⭐⭐ |
| P5 | 公众号 / 网站文章 / 可分享卡片 | ⭐⭐⭐ |

### 2.3 迭代设计

#### 迭代 P0 · 准备工作

- 新分支 `feature/production-capability`
- 设计统一的"输出格式分发"接口 `OutputFormatDispatcher`

#### 迭代 P1 · PPT 生成（**P0 业务硬伤**）

**一句话目标：** AI 能根据客户资料生成符合品牌风格的 .pptx 文件。

**量化验收：**
1. [ ] 新依赖：`python-pptx>=0.6.21`
2. [ ] `backend/app/services/pptx_generator.py`：
   - 接收结构化数据（title / sections / each section: heading + bullets + optional image）
   - 输出 .pptx 文件
3. [ ] 提供至少 3 套品牌模板（极简白 / 商务深蓝 / 学术）
4. [ ] 整合 AI：用户提示 → LLM 生成结构化数据 → pptx_generator → 落地文件
5. [ ] 新建 API `POST /api/v1/generate/pptx`
6. [ ] 客户工作台或对话框加"生成 PPT"按钮
7. [ ] 至少 5 个测试
8. [ ] UI 验证：在客户工作台点"生成 PPT"，输入主题，10-30 秒后得到下载链接，下载打开能看到 5-8 页幻灯片

**预算：** 50-65

**关键决策点：**
- 模板源（自己设计还是用开源模板）？
- 是否支持插入图表（如是，先做 P4 图表生成）？

#### 迭代 P2 · Excel 生成

**一句话目标：** AI 能根据客户数据生成结构化 .xlsx（多 sheet、公式、条件格式）。

**量化验收：**
1. [ ] 新依赖：`openpyxl>=3.1`
2. [ ] `backend/app/services/xlsx_generator.py`
3. [ ] 支持：多 sheet / 表头 / 公式 / 数字格式 / 条件格式
4. [ ] LLM → 结构化数据（dataclass）→ openpyxl 渲染
5. [ ] 至少 5 个测试

**预算：** 40-50

#### 迭代 P3 · PDF 导出

**一句话目标：** Word/PPT/markdown 内容能导出 PDF（带封面、目录、页脚）。

**量化验收：**
1. [ ] 新依赖：`reportlab`（或 `weasyprint`，决策点）
2. [ ] `backend/app/services/pdf_export.py`
3. [ ] 至少 4 个测试

**预算：** 35-45

#### 迭代 P4 · 图表生成

**一句话目标：** AI 回答里能内嵌图表（柱状图/折线图/饼图/雷达图）。

**量化验收：**
1. [ ] 选型：`mermaid`（轻量、文本配置）+ `plotly`（交互、复杂）双轨
2. [ ] `backend/app/services/chart_generator.py`
3. [ ] 嵌入 AI 回答：LLM 输出 ```mermaid``` 块或 ```chart-json``` 块，前端渲染
4. [ ] 至少 4 个测试

**预算：** 35-45

#### 迭代 P5 · 公众号 / 网站文章 / 卡片

**P2。** 模板化输出多种渠道。

**量化验收：**
1. [ ] 提供至少 4 种输出模板：公众号文章 / 网站长文 / 朋友圈卡片 / 小红书卡片
2. [ ] 共用 `OutputFormatDispatcher`
3. [ ] 至少 4 个测试

**预算：** 40-50

---

## Part 3 · 长期记忆（剩 75%）

### 3.1 现状

**已实现：**
- 客户记忆层（`client_profile.py + organization_dna_v2.py`）

**雏形 / 缺失：**
- **没有"我"这一层** — `MemoryScopeType` 无 user/self；`local_memory.py` 目录无 me/
- 团队/组织记忆是 `org_memory.md` 单文件
- 噪音遗忘是写入前过滤，不是衰减
- 错误纠正学习只覆盖单条证据
- 重要信息晋升机制：无
- 个性化检索权重：无
- 用户偏好学习：无 `user_preference / user_style` 字段
- 个人化知识图谱：无
- 使用模式识别：无

### 3.2 子能力拆解（4 个）

| # | 子能力 | 优先级 |
|---|---|---|
| M1 | "我"这一层 scope（user / self） | ⭐⭐⭐⭐⭐ |
| M2 | 用户偏好学习（用什么风格、关注什么） | ⭐⭐⭐⭐ |
| M3 | 记忆晋升与衰减机制 | ⭐⭐⭐ |
| M4 | 个性化检索权重 | ⭐⭐⭐ |

### 3.3 迭代设计

**前置依赖：** 理解深度迭代 2（实体基础设施）应已完成（让 M2 可以基于实体抽取偏好）

#### 迭代 M1 · "我"这一层（**P0**）

**量化验收：**
1. [ ] `MemoryScopeType` 扩展 `user / self`（`models.py:49`）
2. [ ] 新建 `user_memory_facts` 表（沿用 `memory_facts` schema 但加 user_id）
3. [ ] `local_memory.py` 目录加 `me/` 子目录管理
4. [ ] 接入 `memory_foundation.upsert_memory_fact`，支持 user scope
5. [ ] 至少 5 个测试

**预算：** 35-45

#### 迭代 M2 · 用户偏好学习

**量化验收：**
1. [ ] 新建 `user_preferences` 表：`{user_id, preference_type, key, value, confidence, learned_from, updated_at}`
2. [ ] 偏好类型至少：`writing_style / focus_area / time_preference / collaboration_style`
3. [ ] 学习信号：每次 AI 回答用户的反馈（thumbs up/down）+ 用户修改回答的 diff
4. [ ] 检索/生成时把偏好注入 LLM prompt
5. [ ] 至少 5 个测试

**预算：** 45-60

#### 迭代 M3 · 记忆晋升与衰减

**量化验收：**
1. [ ] `memory_facts` 加字段 `mention_count / last_mentioned_at`
2. [ ] 高频出现 → confidence 提升 ; 长期不出现 → 标记 archived
3. [ ] 定时任务（依赖主动能力 A1）：每周扫一次做 promotion + decay
4. [ ] 至少 4 个测试

**预算：** 35-45

#### 迭代 M4 · 个性化检索权重

**量化验收：**
1. [ ] `evidence_selector` 引入 user_preference 权重
2. [ ] 用户偏好的资料类型 / 来源 / 风格在检索时加权
3. [ ] 至少 3 个测试

**预算：** 25-35

---

## Part 4 · 真计算能力（剩 95% — **最严重的名实不符**）

### 4.1 现状

**几乎全空：**
- 无 NL→SQL（全代码 0 命中 `text_to_sql / nl_to_sql`）
- 无趋势分析（`_trend_overview_lines` 是 LLM 拼字符串）
- 无对比计算（无 `compare_clients / compare_options / compare_periods`）
- 无模拟计算（`review_simulation` 是硬编码模板）
- 无决策计算（无方案打分）
- 无优化计算（约束求解、线性规划）
- 无风险/收益计算（`_infer_risk_type` 只做关键词分类）

### 4.2 子能力拆解（5 个）

| # | 子能力 | 优先级 |
|---|---|---|
| C1 | NL→SQL（自然语言查数据库） | ⭐⭐⭐⭐⭐ |
| C2 | 基础统计/对比/趋势引擎（Pandas 封装） | ⭐⭐⭐⭐ |
| C3 | What-if 模拟 | ⭐⭐⭐ |
| C4 | 多方案评估/打分/排序 | ⭐⭐⭐ |
| C5 | 时间序列预测（最小集） | ⭐⭐ |

### 4.3 迭代设计

#### 迭代 C1 · NL→SQL（**让"计算中心"名副其实的第一步**）

**一句话目标：** 用户能用自然语言问数据库类问题（"这个客户 3 个月内有几次会议、卡在哪一步"），系统转 SQL 并执行返回结构化结果。

**量化验收：**
1. [ ] 新建 `backend/app/services/nl_to_sql.py`
2. [ ] 准备数据库 schema 描述（含表关系、字段语义）作为 LLM 上下文
3. [ ] LLM 生成 SQL → SQL injection 防护 → 执行 → 返回 dataframe
4. [ ] 限制：只能 SELECT，不允许 INSERT/UPDATE/DELETE
5. [ ] 接入 `workspace_query_router`：识别为"数据查询类"问题 → 走 NL→SQL 路径
6. [ ] 答案带"我用了这条 SQL: ..."解释（透明性）
7. [ ] 至少 8 个测试（典型查询场景）
8. [ ] UI 验证：在工作台问 "我跟这个客户有过几次会议？" → 答案是数字 + SQL 解释

**预算：** 60-80（这是大头）

**关键决策点：**
- 用哪个 LLM 生成 SQL（GPT-4 / Claude / 本地）？
- SQL safe-mode 怎么实施（白名单表？ AST 校验？）？

#### 迭代 C2 · 基础统计 / 对比 / 趋势引擎

**一句话目标：** Pandas 包一层，提供常用计算接口给 AI 调用。

**量化验收：**
1. [ ] 新依赖：`pandas>=2.0`
2. [ ] `backend/app/services/compute_engine.py`：
   - `summarize(data, by, metrics)` 分组汇总
   - `compare(a, b, dimensions)` 对比
   - `trend(time_series, window)` 趋势
   - `top_n(data, by, n)` 排序
3. [ ] LLM tool use：AI 能调这些函数
4. [ ] 至少 6 个测试

**预算：** 45-60

#### 迭代 C3 · What-if 模拟

**量化验收：**
1. [ ] 简单模拟框架：用户给变量 → AI 改变量看输出
2. [ ] 限制业务场景：客户预算变化、会议频次变化等
3. [ ] 至少 4 个测试

**预算：** 35-45

#### 迭代 C4 · 多方案评估

**量化验收：**
1. [ ] 用户给 N 个方案 + 评估维度 → 系统打分排序
2. [ ] 默认评估维度：成本/时间/风险/收益
3. [ ] 至少 4 个测试

**预算：** 30-40

#### 迭代 C5 · 时间序列预测（最小集）

**量化验收：**
1. [ ] 用 `statsmodels` 或 `prophet`（决策点）
2. [ ] 给客户的 KPI 数据，预测未来 4 周
3. [ ] 至少 3 个测试

**预算：** 30-40

---

## Part 5 · 协作能力（剩 70%）

### 5.1 现状

**已实现：**
- 任务分配与追踪（task_collaborators 表 + inbox_status 状态机）

**几乎全部缺失：**
- 多人编辑（无 CRDT/OT）
- 资料锁 / 版本冲突（无 optimistic_lock）
- **评论与讨论沉淀**（无 comments 表）
- **@ 提及与通知**（无 mention 表 / 推送）
- 工作交接（无 handover / transfer）
- 代理身份 / 委托（无 delegate / proxy）
- **变更日志 / 审计追溯**（无 audit_log 表）

### 5.2 子能力拆解（5 个）

| # | 子能力 | 优先级 | 依赖 |
|---|---|---|---|
| Co1 | 评论与讨论沉淀 | ⭐⭐⭐⭐ | 主动能力 A2（通知） |
| Co2 | @ 提及（mentions） | ⭐⭐⭐⭐ | 主动能力 A2 |
| Co3 | 审计日志 / 变更追溯 | ⭐⭐⭐⭐⭐ | 独立 |
| Co4 | 工作交接 / 代理委托 | ⭐⭐⭐ | 独立 |
| Co5 | 版本锁 / 冲突检测 | ⭐⭐ | 独立 |

### 5.3 迭代设计

**前置依赖：** 主动能力 A2 通知中心完成（让 Co1/Co2 通知能投递）

#### 迭代 Co1 · 评论与讨论沉淀

**量化验收：**
1. [ ] 新建 `comments` 表：`{id, target_type (document|judgment|task|meeting), target_id, author_id, body_md, thread_id, parent_id, mentioned_user_ids, created_at, updated_at, deleted_at}`
2. [ ] 评论可挂在：文档 / 判断 / 任务 / 会议 / 客户 profile 任一对象上
3. [ ] 评论被 @ → 调通知中心投递
4. [ ] 前端：每种对象的详情页加"评论"区
5. [ ] 至少 6 个测试

**预算：** 50-65

#### 迭代 Co2 · @ 提及（mentions）

**量化验收：**
1. [ ] 在 Co1 的 `mentioned_user_ids` 基础上扩展为通用 mention 解析器
2. [ ] 评论 / 任务备注 / 文档注释 都能 @ 人
3. [ ] 被 @ → 调通知中心 emit critical 通知
4. [ ] 至少 4 个测试

**预算：** 30-40

#### 迭代 Co3 · 审计日志 / 变更追溯（**P0 三角色组织硬需求**）

**量化验收：**
1. [ ] 新建 `audit_log` 表：`{id, actor_id, action_type, target_type, target_id, before_json, after_json, ip, ua, created_at}`
2. [ ] 关键操作埋点：客户创建/删除/修改、文档导入/删除、判断公开化、权限变更、批准/拒绝...
3. [ ] CEO/总监能看完整审计日志（带过滤、导出）
4. [ ] 至少 6 个测试

**预算：** 45-60

#### 迭代 Co4 · 工作交接 / 代理委托

**量化验收：**
1. [ ] 新建 `delegations` 表：A 把 B 的权限临时委托给 C
2. [ ] 新建"工作交接"流程：A 离职 → 把 A 的客户/任务/文档批量转给 B
3. [ ] 至少 4 个测试

**预算：** 35-45

#### 迭代 Co5 · 版本锁 / 冲突检测（最小集）

**量化验收：**
1. [ ] 关键资源（如 client_profile）加 version 字段（乐观锁）
2. [ ] 修改时检查 version 不匹配则拒绝
3. [ ] 前端提示"该资料已被他人修改，请刷新"
4. [ ] 至少 3 个测试

**预算：** 30-40

---

## Part 6 · 外部接入（剩 75%）

### 6.1 现状

**已实现：**
- RSS 订阅（`topic_source_fetcher.py`）
- 飞书 API

**缺失：**
- 专业 Web 搜索 API（无 Tavily/Serper/Brave）
- 行业数据库（无 Wind/同花顺/天眼查）
- 公开数据集（无政府开放数据）
- 实时信息（无股价/汇率/新闻/天气）
- CRM/ERP（无 Salesforce/Hubspot）
- Playwright/Selenium（JS 渲染站点拿不到）

### 6.2 子能力拆解（5 个）

| # | 子能力 | 优先级 |
|---|---|---|
| E1 | 专业 Web 搜索 API（Tavily 或 Serper） | ⭐⭐⭐⭐ |
| E2 | 实时信息流（天气 / 股价 / 节假日 / 汇率） | ⭐⭐⭐ |
| E3 | 客户公开信息定时追踪 | ⭐⭐⭐ |
| E4 | Playwright 接入（JS 渲染站点） | ⭐⭐ |
| E5 | CRM 接入（Salesforce / Hubspot） | ⭐⭐ |

### 6.3 迭代设计

#### 迭代 E1 · 专业 Web 搜索 API

**量化验收：**
1. [ ] 选型：Tavily（专为 AI 优化）或 Serper（成本低）— **必问用户**
2. [ ] `backend/app/services/web_search.py` 替代现有 `internet_crawler.py` 的 Bing RSS hack
3. [ ] LLM 能直接调 web_search 函数（tool use）
4. [ ] 至少 5 个测试（mock API 响应）

**预算：** 35-45

#### 迭代 E2 · 实时信息流

**量化验收：**
1. [ ] 接入：和风天气 / 雪球（股价）/ exchangerate-api / Wikipedia 节假日 API
2. [ ] 缓存机制：常用查询 30 分钟缓存
3. [ ] LLM tool use
4. [ ] 至少 4 个测试

**预算：** 30-40

#### 迭代 E3 · 客户公开信息定时追踪

**量化验收：**
1. [ ] 每个客户能配置"追踪列表"（公司官网/新闻源/微博账号）
2. [ ] 定时任务（依赖主动能力 A1）：每天扫一遍发现更新
3. [ ] 更新 → 调主动能力 A5 评估价值 → 通知中心
4. [ ] 至少 4 个测试

**预算：** 35-45

#### 迭代 E4 · Playwright 接入

**量化验收：**
1. [ ] 新依赖：`playwright`
2. [ ] 关键场景：金融数据网站、企业官网（JS 渲染）
3. [ ] 至少 3 个测试

**预算：** 35-50（playwright 装机本身耗时）

#### 迭代 E5 · CRM 接入（P2，按需）

**量化验收：**
1. [ ] OAuth 接入 Salesforce / Hubspot
2. [ ] 同步联系人 / 商机到客户工作台
3. [ ] 至少 3 个测试

**预算：** 50-65

---

## Part 7 · 反思自知（剩 80%）

### 7.1 现状

**雏形：**
- `query_router.py` 输出 confidence 数值
- `answer_layer.py` 有 `missingContext`
- `digital_asset_center.py` 有"还缺这份资料"模板

**缺失：**
- 推理过程展示（无 chain_of_thought）
- 错误事后分析（无错答归因）
- 元认知（无能力清单 / 边界声明）

### 7.2 子能力拆解（4 个）

| # | 子能力 | 优先级 | 依赖 |
|---|---|---|---|
| R1 | 可信度声明（UI 可见） | ⭐⭐⭐⭐ | 独立 |
| R2 | 盲区图谱 | ⭐⭐⭐ | 理解深度（实体覆盖率） |
| R3 | 推理链可视化 | ⭐⭐ | 独立 |
| R4 | 错误事后分析 | ⭐⭐⭐ | Co1 评论 + Co3 审计 |

### 7.3 迭代设计

**前置依赖：** 理解深度迭代 5+6（关系+矛盾）应有进展（让 R2 盲区图谱有素材）

#### 迭代 R1 · 可信度声明

**量化验收：**
1. [ ] 现有 `confidence` 数值在 UI 上显示为"高 / 中 / 低 / 不确定"
2. [ ] 低置信度回答自动加 "我不太确定，建议核对" 前缀
3. [ ] 至少 3 个测试

**预算：** 20-30

#### 迭代 R2 · 盲区图谱

**量化验收：**
1. [ ] 新建 `blind_spots` 表：系统识别出的"该客户在 X 维度上资料不足"
2. [ ] 每次回答时如触发盲区 → 主动提示用户补资料
3. [ ] 客户工作台加"盲区"页签
4. [ ] 至少 4 个测试

**预算：** 35-45

#### 迭代 R3 · 推理链可视化

**量化验收：**
1. [ ] AI 回答时输出推理步骤（已有 retrieval_summary）
2. [ ] UI 加"看推理过程"展开按钮
3. [ ] 至少 3 个测试

**预算：** 25-35

#### 迭代 R4 · 错误事后分析

**量化验收：**
1. [ ] 用户能对回答标记"答错了"，并说明原因
2. [ ] 系统记录到 `answer_errors` 表
3. [ ] 定期（依赖主动能力 A1）汇总 → 找出高频错答模式
4. [ ] 至少 4 个测试

**预算：** 30-40

---

## Part 8 · 总工作量估算

| 维度 | 迭代数 | 工具调用预算 |
|---|---|---|
| 输入广度 | 5 | 185-235 |
| 生产能力 | 5 | 200-265 |
| 长期记忆 | 4 | 140-185 |
| 真计算能力 | 5 | 200-260 |
| 协作能力 | 5 | 190-250 |
| 外部接入 | 5 | 185-245 |
| 反思自知 | 4 | 110-150 |
| **合计** | **33** | **1210-1590** |

**估算时长：** 按每天 100-200 次工具调用 = **2-4 个月单线程**，或 **3-6 周多并行**

---

## Part 9 · 推荐切入顺序

如果 Claude Code 只能单线程做：

```
第 1 周  迭代 I1 录音转写（业务硬伤）
第 2-3 周 迭代 I2 邮件接入（业务硬伤）
第 4 周  迭代 P1 PPT 生成（业务硬伤）
第 5 周  迭代 C1 NL→SQL（让计算中心名副其实）
第 6 周  迭代 Co3 审计日志（三角色组织硬需求）
第 7-8 周 迭代 P2 Excel + 迭代 P3 PDF
第 9 周  迭代 M1 "我"这一层
第 10-12 周 剩余 P1/P2 项
```

如果多 Claude Code session 并行：

- Session A：输入广度（I1-I5）
- Session B：生产能力（P1-P5）
- Session C：真计算能力（C1-C5）
- 三个并行，各自分支，互不打架

---

## Part 10 · 第一步动作

1. **看完本计划全文**（约 30 分钟）
2. **看 4 份依赖文档**（约 1 小时）：
   - `docs/客户计算中心-功能差距清单-2026-05-12.md`
   - `docs/数据中心-未完成清单-2026-05-12.md`
   - `docs/主动能力-Claude-Code执行计划-2026-05-12.md`（工作模式参考）
   - `docs/理解深度-执行计划-2026-05-12.md`（兄弟线程模式）
3. **确认 Task #28 状态**（dev app 自主重启机制）—— 没完成不要开工
4. **跟用户确认从哪个维度切入**：
   - 推荐起手：输入广度 I1（录音转写）—— 业务价值最高、相对独立
   - 备选：生产能力 P1（PPT）—— 短平快、立竿见影
5. **进入选定维度的迭代 X0 准备工作**
6. **第一次 checkpoint** 之前不要写大段代码

---

## Part 11 · 沟通规范

- 每次 checkpoint 用结构化 markdown
- 任何架构选型 / 新依赖 / 业务规则 → 必问用户
- 不要硬猜 → "我建议这样，请确认"
- 如果某个迭代的方案文档你看了之后觉得不合理，**告诉用户你的反对意见**，让他重新决策——不要硬着头皮做

---

## Part 12 · 风险登记

| ID | 风险 | 缓解 |
|---|---|---|
| R-G-1 | 新依赖装不上 / 与现有冲突 | 必问用户，先做 dry-run |
| R-G-2 | 多分支 merge 冲突 | 各维度独立分支，merge 时用户参与 |
| R-G-3 | LLM 成本失控（C1 NL→SQL 尤其） | 必问用户预算，加日预算上限 |
| R-G-4 | 外部 API key 缺失 | E1 之前必问用户准备 |
| R-G-5 | 测试基线大量已红 | 接受 baseline，只关心 delta |
| R-G-6 | UI 改动大面积破坏现有 UX | 严格只加不改、独立 tab、feature flag |

完。
