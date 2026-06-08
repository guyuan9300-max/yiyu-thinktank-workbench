# 智能填表 · 路径策略(先定策略,再接通)— 2026-06-08

> 排查+1 结论:**填表不是"没接数据中心",而是接了但"权威结构化源稀疏 + 字段未对齐 + 数字/财务类无结构源"**。实证平均填充率 **45.9%**(940/2049字段,client_template_fill_runs)。本档定义"接哪些类型数据 + 用什么计算",作为接通前的策略基线。

## 一、现状真实路径(铁证)
生产入口 `run_client_template_fill`(main.py:17679)→ `_fill_client_template_docx_impl`(17368):
1. docx 解析出字段(177字段表 foundation_standard_schema.json:基金会摸底表,164客观/13主观/83可公网搜)。
2. **按批**对每字段调 `build_template_fill_context`(16786)组装数据中心上下文。
3. 调 `state.ai.generate_template_field_values_batch` —— **LLM 生成式填值**(非确定性查表)。
- 注:`fill_table_evaluator.query_candidate_value`(确定性 glossary优先链)**未接进生产**,是独立评估器。

**build_template_fill_context 当前接的 6+ 源 + 客户覆盖(/13):**
| 源 | 取法 | 覆盖 | 权威 |
|---|---|---|---|
| ① verified字典直命中(P0b) | match_field_to_verified_glossary(走schema别名归一) | **4客户**/411 | 0.95最高 |
| ② 6段叙事(复合字段) | map_field_to_narrative_segment→client_narrative_local_mirror | 6客户/6 | 高 |
| ③ 已确认判断 | judgment_versions status='confirmed' | **2客户/3**(另61条awaiting没用) | 权威 |
| ④ RAG检索证据 | build_retrieval_bundle→retrieve_knowledge_bundle(v2_chunks) | 12客户/1059 | 噪声 |
| ⑤ public hints | v2_documents.preview_text | 12客户 | 弱 |
| ⑥ user_confirmed facts | atomic_facts verification_status='user_confirmed' top8 | **1客户/89** | 低覆盖+非字段定向 |
| ⑦ R4(合同/文件/data_gaps) | contract_structures/file_identities/data_gaps | 多为空 | — |
| ⑧ web补充 | fetch_template_fill_web_sources(is_public_searchable) | 按需 | 公开字段 |

## 二、为什么质量差(实证三短板,非"没接")
- **实证**:为爱黔行(verified字典116)→填充82-96%;CFFC(verified 0/pending 100)→~50%;广州民政局表→0-49%。**填充率强相关 verified字典覆盖**。
- **短板A 权威源稀疏**:最强的 ① verified字典只覆盖4客户、③确认判断2客户、⑥user_confirmed 1客户。多数客户/字段只能落到④RAG文档(噪声)→LLM 易回退【待确认】或填错。系统里有大量数据但卡在"未核验"状态:glossary pending 393(vs verified 411)、judgment awaiting 61(vs confirmed 3)、atomic_facts unverified 1623(vs user_confirmed 89)。**填表门槛只认"已核验",把自己饿死。**
- **短板B 字段未对齐**:⑥atomic_facts 是 dump top8(非按当前字段名定向),且 atomic_facts.attribute 是 LLM 自由抽取(如"职务/成立时间"),与177标准字段名不一一对应→匹配漏。
- **短板C 数字/财务/计数类无结构源**:177字段含 25 amount_or_count + 人数类;这些真值在年报/财报文档里但**没被抽成结构化属性**;query 又对严格类型字段跳过全文检索→这类字段几乎必空。

## 三、应然策略(按字段类型路由数据 + 置信度分层计算)
**原则**:不同字段类型该接不同数据类型;计算从"二值已核验门槛"改为"置信度分层+定向对齐",并补齐缺失结构源。锚定既有 build_template_fill_context,**扩展不另起**。

### 3.1 按字段类型 → 数据源路由(value_type/is_* 已在schema)
| 字段类 | 例 | 第一源 | 兜底链 |
|---|---|---|---|
| 身份登记(客观可公网) | 全称/信用代码/成立时间/法人/登记机关 | verified字典 | →定向atomic_facts(别名对齐)→**web(83个public字段)** |
| 财务/计数(strict) | 净资产/收入/理事人数 | verified字典 | →**新增:年报结构化抽取**(见3.3)→多候选进澄清,**禁RAG全文猜** |
| 治理/制度(yes_no/text) | 是否设党组织/制度健全 | 字典+判断 | →RAG证据(可用) |
| 复合/叙事 | 机构简介/服务内容/团队/里程碑/合作 | **6段叙事** | →RAG证据 |
| 主观/诉求(13) | 发展诉求/政策建议 | — | 标 needs_user_fill 交用户 |

### 3.2 计算改造:置信度分层(替代"只认verified")
- **L1 权威直填**:verified字典 / user_confirmed / confirmed判断 / 合同结构 → 直采,带来源标。
- **L2 候选待审**:pending字典(393条!)/ unverified高置信atomic_facts(confidence≥0.85)→ 填入但标【待确认·来源X·置信N】,不回退空;同时**回写一条 review 队列**让用户一键确认→沉淀成 L1(把"填表"变成"核验飞轮",一次填表把 pending 转 verified)。
- **L3 检索参考**:RAG证据 / web → 仅严格类型外字段,标【参考】。
- **多候选冲突**:同字段多源不一致 → 进澄清(clarification),不硬填。

### 3.3 必补的接通点(接通阶段做)
1. **atomic_facts 定向对齐**:⑥改为按当前 field_label 经 resolve_field_standard_names(schema别名)定向查 atomic_facts.attribute,替代 dump top8。
2. **放宽门槛到 L2**:把 pending字典 + 高置信 unverified facts 纳入(带待确认标 + review回写),立刻盘活 393 pending + 1623 unverified。
3. **数字/财务结构源**:对年报/财报类文档跑一遍"标准字段定向抽取"(177表里的amount_or_count/人数),落 glossary_attributes 或专表;这是当前最大空洞。
4. **判断飞轮**:61条 awaiting_review 判断,提供填表内一键确认入口 → 转 confirmed 可用。

## 四、预期与验证
- 杠杆排序:**短板A放宽门槛(L2)** > 字段对齐(B) > 财务结构源(C)。前两项几乎零新数据、纯计算改造,可立刻把多客户从~50%抬升。
- 验证口径:复跑 client_template_fill_runs(CFFC党建表/广州民政局表/日慈年报),对比 filled_count/field_count;CFFC(pending100)应明显上升=L2生效铁证。
- 风险:L2 降门槛可能引入错填→必须配【待确认】标 + review回写,不能静默当权威。走执行+1 收敛。

---
*依据 [DATA_CENTER_JUDGMENT_20260608.md](./DATA_CENTER_JUDGMENT_20260608.md) J4 深化。接通前需顾源源确认本策略,再走执行+1 定最稳实施路径。*
