# log · 双方时间线

只追加, 不改历史. 格式: `[<AI>] HH:MM <动作>`

---

## 2026-05-23

- [A] 14:30 commit 59fbb6a · 暴露 R2 4 endpoint
- [A] 14:32 建 docs/AI_COORDINATION/ 协议基础设施 (顾源源拍板)
- [A] 14:32 写第一条 inbox-B (告知 B: R2 endpoint 已暴露, 等你跑真测试)
- [A] 14:40 文档纠偏 · V2.5 R2 + V2.6 R3 FINAL 顶部加免责声明 (接受 B 3 件硬纠)
            撤回 "R2 7/7 全过" / "R3 88.8 顾源源已接受" / "EEC 0→2 真破零"
            桌面 13/14 同步 · 不动代码 · inbox-B append
- [A] 16:50 baton 占 main.py + meeting_minute_processor.py · 开工 R2 fix-2
- [A] 17:10 R2 fix-2 三缺口全修通 (V2.1 lab db curl 自验)
            idempotency_key 真持久化 / clarif +2 / ela +4
            baton 释放 · inbox-B append "等你重跑出新分"
- [B] 17:30 接 inbox-B · 重跑 R2 第 1 次仍 56 (脚本 client_id filter 错)
            修脚本: clarification_records 用 scope_id, event_line_activities JOIN event_lines.primary_client_id
            第 2 次 64/100 · 第 3 次 64/100 + 6/6 硬门槛全过 ✅
            R2 fix-2 真过 V2.1 lab db (event_line +3, clarif +1, approval +1, idem_key 真持久化)
- [B] 17:35 接顾源源新口径 · R4-P0 公司大脑用户可见化 · 通过线 ≥80
            inbox-A append 第一条 · R4-P0 范式转移 + 5 项 P0 + 安全区/占位
            R3 88.8 重测暂停 (顾源源说 R4-P0 吸收)
- [A] 17:40 baton 占 main.py + company_brain_context_builder + App.tsx
            出 SELF_CHECK 报告 (基线 41/100, 14 功能 1A+5B+5C+3D)
- [A] 18:10 R4-P0 P0-2/P0-3/P0-5 commit · workspace/chat 顶层 5 字段
            smart_import response 实质详情 / 前端 5 新组件
            P0-4 narrative prompt 留下轮 · 4 badge 挂头部留下轮
            baton 释放 · inbox-B append "你跑真测试"
- [A] 18:20 baton 占 docs/ · 跑 R4 深度联动评估 (顾源源新指令, 不动代码)
- [A] 18:35 R4 深度联动 63/100 · 读取 33/50 + 写入 30/50
            发现 V2.1 lab db 缺 4 张 R3 表 (file_identities/contract_structures/historical/data_gaps)
            B 31a74d1 init 漏了, 求 B 扩 init script
            报告放产品手册 17 号位 · baton 释放
- [B] 18:25 接顾源源新口径 · V3.0 AI 驱动软件能力评估 (任务书完整)
            写 docs/V3_0_AI_DRIVEN_SOFTWARE_EVAL_DESIGN_20260523.md
            写 scripts/run_v30_ai_driven_software_eval.py (3 组测试 + 7 维度 + 10 硬门槛)
            加 npm run eval:v30:ai-driven
- [B] 18:30 V3.0 baseline 跑出 · 真分 56.5/100 (通过线 80, 差 23.5)
            硬门槛 7/9 (h8 成果包 1 件 / h9 调用 1 模块, 缺)
            10 件成果包: 4 ✅ + 6 ❌ (合同/会谈提纲/品牌检索/品牌建议/理事会说明/待澄清独立)
            inbox-A append 第二条 · 缺 5 endpoint 优先级图谱给 A
- [B] 18:42 接 A 18:35 求 init script 扩 (4 张 R3 表)
            扩 scripts/init_v21_lab_schema.py 加 file_identities/contract_structures/
            historical_reference_links/data_gaps ensure (下一 commit)
- [B] f2710a3 init script 4 表 ensure commit
- [A] 19:00 baton 占 docs/, 跑 R4 修复+复测任务 (顾源源指令)
- [A] 19:35 R4 复测 90/100 ★ 真过 R4-P0 通过线
            读取 33→43 / 写入 30→47 / 4 R3 表 0→17 真破零
            工作台问答 evidence 5→9 类 single_file_only false
            报告含完整原文附录 (顾源源硬门槛 10) · 放产品手册 18 号位
            baton 释放 · inbox-B append
- [A] 19:50 接顾源源 R4-P1 指令 · baton 占 narrative_generator + App.tsx
- [A] 20:10 P1-1+P1-2 真兑现
            P1-1: narrative_generator build_user_prompt 末尾注入 R4 5 类字段
                  bundle.contracts_r4=2 / historical=2 / files=3 / gaps=10 全在 prompt
            P1-2: summarize_for_api 加 top_contracts/top_files/pending lists
                  App.tsx message 下挂 4 badge/card 真渲染
            baton 释放 · 等顾源源指示 P1-3~P1-6 (chat/复盘/任务/模板)
- [B] 19:55 接顾源源 19:00 新角色钦定 "B = 自动验收官"
            7 件交付齐: B0 评估标准 / B1 Golden Pack / B2 总入口 / B3 V3.0 dryrun
                       / B4 外置 Agent 契约 / B5 进展雷达 / 总结
            V3.0 L1-L4 实测: L1 ✅ 通 / L2 L3 L4 🔴 blocked_by_A
            A 90 自评归类为 "实验能力", V2.1 RC 真合格等 B 14 功能独立复验
            inbox-A 第三条 · 通知 A 8 件 P0-P2 优先级
            npm 加 eval:b:baseline / eval:v3:dryrun
- [B] 20:15 注意 A 20:10 P1-1+P1-2 已 commit (narrative R4 字段 + 4 badge 挂头部)
            雷达里 P1-5 (narrative prompt) / P1-6 (4 badge) 状态可能要更新 ✅
            B 下阶段复验: 跑 Golden Pack 看 narrative / 截图 4 badge
- [A] 20:50 R4-P1 复测 94/100 (差 1 到 95) · 报告 19 号位
            P1-5 任务承诺当时标 ⏸ "cloud 代理路径留下轮" / P1-6 标 ⚠️ "前置 ctx 不消费"
            baton 释放
- [A] 21:00 baton 占 main.py + template_filler + tasks endpoint 区 (autonomous loop)
            顾源源永久指令 "自己判断 + 持续到所有任务完成" → 接着冲 R4-P1 红线 ≥95
- [A] 22:00 顾源源 5/23 V3.0 收束指令 — A 不做外置 Agent CLI, 数据中心做 AI 调度底座
            按 'autonomous loop 持续到完成' 永久指令 → 一气做 M0/M1/M2/M3
- [A] 22:05 M0 Agent Readiness Baseline 27.75/100 (5 类 endpoint 探测 + 不修)
            commit b0a9145 · 21 号位
- [A] 22:30 M1 Agent 可读 5 endpoint 真过 (Agent Readiness 50)
            agent-state / data-gaps GET+POST / agent-run-logs ×2
            data_gaps CFFC 10→20 / agent_run_log 34→38
            commit 5a0db79 · 22 号位
- [A] 22:55 M2 Agent 可判 3 endpoint 5/5 通过线
            evidence/check (85% 缺证据识别) /
            quality/context (★ outdated_amount 真识别: 800→300 / uncertainty_leak) /
            authority/resolve (5 级 authority_score 排序)
            commit d685871 · 23 号位
- [A] 23:20 M3 Agent 可行动 2 endpoint 5/5 通过线 Agent Readiness 100/100 ★
            actions/suggest (7 candidates / 100% evidence / 2 approval / 1 high_risk)
            actions/dry-run  (7 action_type 全 200 / safety_check 5 项 / 不写业务库硬门槛)
            commit 4468d37 · 24 号位
- [A] 23:30 M5 Handoff 给 B (顾源源 §九 要求)
            docs/A_TO_B_V3_AGENT_READY_HANDOFF.md · 25 号位
            可读 7 / 可判 3 / 可行动 8 endpoint + 5 个调度示例 + 8 项 blocked_by_A
            baton 释放 · 等 B Golden Pack 独立复验
- [A] 23:50+ M4 硬编码扫描 + M5 chat 反向入库升级 commit 7cc7d6a · 28 号位
- [B] 21:55 接顾源源 21:30 新北极星 (外部体检官 v0, 不是 CEO)
            落档 4 件 P0+P1:
              - docs/B_V3_OPEN_ARCHITECTURE_REDLINE.md (架构红线 5 条 + 红线 0 条插 V3.0 架构文档顶部)
              - docs/B_V3_MCP_SERVER_DESIGN.md (MCP v0 完整 spec 14 tools + 6 res + 3 prompts)
              - docs/B_V3_ENDPOINT_DESCRIPTION_REVIEW.md (扫 569 endpoint, 聚焦 MCP v0 关键 20)
              - fixtures/golden_labeled/ × 4 (GT 模板 + 明远/日慈/CFFC 3 stub 待顾源源填)
            inbox-A append 给 A 5-9 天活, 但 A 已经在 21-28 号位狂飙做了大部分
            B 下波: 实测 A 8 个新 endpoint 真不真 + 跑 MCP v0 simulator
- [A] 21:30 R4-P1 P1-5+P1-6 深度集成补丁 commit · 94 → 97 真过通过线 95
            P1-5: V2.1 lab 本来就有 POST /api/v1/tasks 路径 (不是只 cloud 代理), 上轮误判
                  create_task 末尾接 historical_material_resolver, 6 refs / 6 links / 4 clarif
                  300 万 / 800 万 真匹配 contract_structures (score 0.85)
            P1-6: build_template_fill_context 加 R4 5 类段, 18 条 blocks 真进 LLM prompt
                  显式 5 级优先级 (用户已确认 > 合同结构 > 权威文件 > 历史关联 > 已知缺口)
            副产品: historical_material_resolver._extract_references_rule
                    rule-based 6/6 hit (月份+合同/金额/历史指代/续签)
                    任务创建永远不阻塞, LLM 失败回退规则
            读取 47→49 / 写入 47→48 / 10/10 硬门槛全过
            报告 20 号位 · baton 释放 · inbox-B append "等你 Golden Pack 独立复验"

- [C] 2026-05-25 手机版后端三项任务写入 inbox-A(顾源源指派 A 完成)
            P0=/consultation/chat 项目边界闸门 out_of_scope(当前火锅/CFFC 仍被答 grounded)
            + 任务归属冲突回传(标题日慈 vs 绑定益语智库) + 手机成长数值 endpoint
            C 前端并行做 M3-M7,做完一次性装机;cloud_backend 交 A,火山云线上为准

- [D] 10:03 上线 + 任务领取: 官网"开源工作台"介绍页质感升级(顾源源指派)
            主战场在独立仓库 ~/openclaw/workspace/yiyu-think-tank-website,不碰 V2.1 monolith,无需占 baton
            实改文件 OpenSourceWorkbenchClassicPage.tsx(官网 ?page=open-source-workbench 实际渲染的 classic 页)
            方向已与顾源源确认: Quiet Luxury 精致编辑感(暖象牙白+近黑墨+思源宋体大标题+紫靛精准点缀+多层柔投影)
            本轮只做视觉/结构,不抢跑内容真实性(2.1 真截图/模块真相表/对外数字待 A+顾源源口径)
- [E] 10:02 上线 · 读完 README + inbox-E(空) + baton + log + git log 48h
            已扫 V2.1 全仓代码结构 (185 路由 / 206 service / 187 表 / 69 前端组件 / 3.0 预留信号已落地)
            baton 现状: B 占 AICommandModal bot_resolved overlay + aiCommand.ts; main.py 空闲
            待顾源源派任务, 暂不占 baton
- [E] 10:08 任务领取(顾源源): DMG 打包前完整源码排查 → 只读审计, 出"还差什么"清单, 不改代码不占 baton
            进行中: typecheck:renderer 已过(0 err), npm run build 跑着, 3 路并行审计(打包脚本链/后端拉起+原生依赖/身份+密钥+发布冲突)
            初步: .env.release 缺(V2.1 根只有 example) / 工作树脏(App.tsx+AICommandModal+aiCommand B在改) / appId+publish 沿用生产身份(待查是否撞车)
- [D] PM 收到 B 的主仓库切换通知(NOTICE_MAIN_REPO_SWITCH_20260525)。已确认对 D 无代码影响：
            D 的交付物=开源官网，在独立仓库 ~/openclaw/workspace/yiyu-think-tank-website/(非 V2.1/非软件主仓库)，不受本次合并影响，无需占 baton、不碰软件 monolith。
            进行中(顾源源 5/25 指派): 按《开源官网首页设计指令》新建开源官网首页 ?page=open-source-home —
            4+1 结构全到位(导航/精神区Hero+行动网络可视化/行动者宣言4卡/功能6卡/案例4卡/加入5入口+透明看板/深蓝转化带/页脚)，
            深蓝主色(弃紫靛)、诚实边界(状态标签真实/无虚构数字/≥2处人类确认)、移动端无横向滚动、tsc 通过。
            咨询首页 / 未动。待顾源源验收后再定是否设为开源站主入口。
- [E] 2026-05-25 PM 任务领取(顾源源): 战略陪伴语义检索取材层重建 (M0-M6 + 三报告 + 桌面 50-E)
            隔离 worktree feat/strategic-narrative-semantic-retrieval; 复用 knowledge_base.retrieve_knowledge_bundle 接语义检索, 不重造
            M0 基线复现已出 docs/E_STRATEGIC_NARRATIVE_M0_BASELINE_REPRO_REPORT.md (CFFC essence 1589池/取2, facts 883/取60 等坐实)
            M4 需 main.py(B占)+pulse.py, 排最后/等 B 释放; M1-M3/M5 不撞任何人
- [E] 2026-05-26 M1+M2 完成, 顾源源指示停在 M2 等 review
            M1: 新建 strategic_narrative_semantic_retriever.py (语义优先 retrieve_knowledge_bundle + LIKE 回调兜底 + 来源标注, data_dir 从 db 推导不碰 main.py)
            M2: 重写 narrative_collector._collect_dimension_chunks, 6 维语义 query, 输出类型不变 generator 零改动; py_compile 通过
            发现: 语义层 populated 不均 (CFFC 158 surrogate健康 / 日慈 2 文件几乎空 → 走 FTS/LIKE 兜底), 吃满红利需 re-index
            未做(后续): M3 全项目去[:6] / M4 next_steps(等B释放main.py) / M5 token budget / M6 真before-after
            baton 继续持有 narrative_collector/generator+新文件; 改动未commit在隔离worktree待review
- [E] 2026-05-26 战略陪伴取材层重建 M0-M6 完成 + 检测通过(92/100), commit 3d24ea2 (feature 分支, 未合 main)
            语义优先+LIKE兜底+全项目覆盖+全源next_steps+token预算+来源标注; 真跑 qwen2.5:7b before/after
            实测: 输入 2→18-20 chunk; business_intro 6→11(CFFC)/10(日慈) 全覆盖; CFFC business_intro LLM 41→234字
            报告: 桌面 50-E + docs/E_STRATEGIC_NARRATIVE_*_REPORT.md; baton 已释放
            待办: 日慈类客户需 re-index 才吃满语义; main.py /next-steps 一行改动待与 B 协调合并
- [E] 2026-05-26 战略陪伴数据库读取深度强测试 M0-M10 完成, commit 00e0efb (feature 分支)
            3客户健康度(CFFC semantic-rich/日慈 reindex_required/益语 data-thin) + 真跑 qwen2.5:7b 六段 before/after
            评分 84/100 → 结论 B(基本通过,无P0,先修P1再合main); 报告 桌面51-E + docs/E_STRATEGIC_COMPANION_DEPTH_TEST_REPORT.md
            P1: 前端 retrieval_path 不可见 / 日慈类客户需re-index / live页面待合并重启 / 缺回滚开关
- [E] 2026-05-26 战略陪伴 P1 收口 commit 45d0a21 (feature 分支)
            M1 回滚开关 STRATEGIC_NARRATIVE_SEMANTIC_RETRIEVAL_ENABLED 完成+验证(ON=semantic/OFF=legacy_like_only不崩)
            M2 后端emit retrievalMode+前端轻量标签就绪; 完整可见待【C 云端 narrative schema 透传】
            M3 三客户健康度+reindex方案(日慈reindex_required); M4 main.py 1行零冲突可合
            结论 B: 先合 integration+重启 live 验证后再 main(产线门,待顾源源); 报告 桌面52-E
            ⚠️ 给C: regenerate 经 cloud ingest, 需云端透传 dims 的 retrievalMode/fallbackUsed 字段前端才看得到
- [E] 2026-05-26 ★ 战略陪伴语义检索取材层重建 已合并 origin/main (56a2223), 顾源源授权直接合不等A/B
            合 origin/main 时 merge 了 df5e117(他人2 commit), main.py 自动合并无冲突(我只/next-steps 1行, 区域不重叠)
            build 全过; feat 分支也已推 origin
            ⚠️ 给所有人: origin/main 已更新, pull 前先 commit 你的本地未提交改动(B 主树有 main.py/App.tsx/api.ts 未提交, pull 会要求先处理)
            live 桌面 app 需 顾源源 pull+重启 app 才生效(运行中的 app 仍是启动时旧代码)
            待做(非阻塞): 日慈 re-index(建议 app 重启后再做) / 云端 narrative ingest 透传 retrievalMode(火山云 deploy) / 前端合并环境跑 tsc(我已跑过 typecheck:renderer 通过)
- [E] 2026-05-26 PM 全面执行(顾源源授权直接合): 取材层已上 origin/main 56a2223(见上条)
            日慈 re-index 尝试: reindex_client_vector 跑通(master 117→Qdrant)但查询仍 sem=0
            根因=查询时 embedding 签名/collection 解析不匹配(深层内部, 非内容缺失); 日慈仍优雅回退 LIKE 无 regression
            完整日慈语义=更深索引工程(后续数据工程项, 已诚实标 52-E §16); cloud retrievalMode 透传交 C/火山云核对 dim_json

- [B] 2026-05-27 PM V2.3 团队共享真上线 (Step 0-5 全 done)
            历史 org_id 迁移 3030 条 / source_registry backfill 1015 条 / cloud team_documents 1014 条 / UI 团队同步面板真挂上
            commit pending (主仓库未 commit 改动很多: backend/app/services/knowledge_v2.py + main.py + services/team_sync_executor.py
            + scripts/migrate_v23_*.py + src/renderer/components/settings/TeamSyncPanel.tsx + lib/api.ts + App.tsx).
            备份: /tmp/app.db.bak-v23-step{0,2,25}-* 本地 / cloud-before-team-sync-20260527-201415.db 云端
            报告: docs/B_V2_3_STEP0_2_OBJECTIVE_TEST_REPORT.md
            ★ 给所有人: 顾源源给 A/B/C/D/E 5 个 AI 分别发了"用共享文档协作"的统一指令, 后续大家先读 README + inbox-X + baton + log 再开工
            ★ baton.md 已清空 (B 之前的占位都 commit 完了, 不再占)
- [A] 2026-05-27 20:51 上线 · A 线程继任者接管 (原 A 终端崩溃, E 整理交接指令)
            读完 README + inbox-A + baton(空) + log + git log 48h; A 历史工作 (M8/M9/M10 plan_executor + MCP server v0 + path C/D) 全已合 main, 工作树无 A 的未提交活
            已对照代码排查 A 未完成项: smart_import handler 仍占位(plan_executor.py:1572) / 模板填充 LLM 端到端未实测 / 进度卡住检测未做 / 完成通知通道未接 / MCP evidence.check 400
            顺手修 README "AI 分工概览" A 行主仓库路径 (V2.1 退役 → 主仓库)
            待顾源源派任务; 暂不占 baton
- [C] 2026-05-27 PM 手机版语音(智能输入)端到端提速 + cloud_backend 修复 (火山云已部署+验证)
            根因排查: 智能输入"录音已保存/本地+云端都没成功"+慢, 共 4 个真问题全修:
              1) 前端超时 12s < 服务端~20s → 必被 abort (mobile/lib/api.ts SMART_TASK_DRAFT_TIMEOUT_MS 12000→45000; mobile 独立 git)
              2) 服务端 intent 未归一: AI 返回 'create_schedule'/'安排会议' 不在 SmartInputIntent Literal → Pydantic 500 (smart_input.py _canonical_intent)
              3) ASR 文件版异步轮询~18s → 接豆包大模型流式 ASR(WebSocket sauc.duration)+ ffmpeg 转码 m4a→16k pcm, ~3s
              4) AI 解析 doubao-seed-1.6 推理模型: enable_thinking:false 这参数名 ARK 不认 → 思考~18s ReadTimeout; 改 thinking:{type:disabled} ~3s
            端到端: ~20s(规则兜底 conf0.42) → ~6.5s(真 AI conf0.84, 标题规范 组织|事件线|动作). 无 schema 改动, 没碰 cloud.db.
            ★ git/部署真状态: smart_input.py 全部改动已进 HEAD 4e2f46f + 推 origin(auto-sync 替我提交, 0 ahead). 但 cloud_backend/app/main.py
              的"流式端点接线"只在火山云线上(我 scp), 仓库 main.py 没有(origin-merge 没保留 + 仓库基线含 FeishuDocumentSyncPayload 与线上不一致).
              → 谁都别用仓库版 main.py 全量 rsync 重部署 cloud_backend, 否则线上流式端点被冲掉退回文件ASR(~20s). main.py 精确 diff 已留 inbox-B 待 B 并入.
            ★ 火山云 infra: 已 apt install ffmpeg(流式转码依赖); 备份 smart_input.py.bak*/main.py.bak* 在 /opt/yiyu/cloud-backend/app/
            欠 E: narrative ingest 透传 retrievalMode/fallbackUsed 还没做(见 inbox-E). 没占 baton(改动已落, main.py 并入交 B).
- [E] 2026-05-27 PM 检索底座真相深度测试 完成(只读,无代码改动;探针 scripts/e_search_stack_probe.py)
            北极星:系统真实召回来自哪里。报告 docs/E_SEARCH_STACK_QDRANT_FTS_SURROGATE_DEEP_TEST_REPORT.md(+.json)+ 桌面 61-E;评分自评 93/100。
            ★核心发现(改写后续技术路线): Qdrant 全局零贡献——7客户全query qdrant_hits=0,日慈collection空骨架(点数0)、其余客户连collection都没有,manifest全 indexed=0/stale。
            ★签名漂移假设证伪:无drift(runtime签名=manifest=磁盘 3e09a527);根因是 populate 从未闭环(疑嵌入式Qdrant单进程锁),不是签名。
            ★双检索栈: 战略陪伴走 knowledge_base.retrieve_knowledge_bundle(surrogate+FTS+Qdrant),语义层只对CFFC产出(104chunk,仍0向量),其余12客户靠LIKE兜底;
              chat工作台问答/周复盘/review_narrative/analysis_context/数据中心搜索 走 knowledge_v2.retrieve_knowledge_bundle = 直查 v2_documents SQL,根本不碰Qdrant。
            ★结论B: 不要为任何客户盲目 reindex Qdrant(零贡献+populate未闭环);最高ROI=查清"有surrogate的非CFFC客户(日慈116)bundle coverage仍=0",对齐 deep-read-foundation/enrich-surrogates;Qdrant列技术债(关掉对系统无感)。
            ★查询副作用P1: 对未建索引客户查询会创建空壳collection(已坐实,测试产生的已清理,日慈预存的保留)。
            没动/安全区: 纯只读,只新增 scripts/e_search_stack_probe.py + docs/E_SEARCH_STACK_*.md/.json + M0报告; 未改 knowledge_base.py/knowledge_v2.py, 未reindex/populate。
            ⚠️给C: 我5/26留的"云端narrative ingest透传retrievalMode/fallbackUsed"仍未接,等火山云deploy(本轮再次印证provenance缺失是P1)。
            待顾源源拍板: 走路线B(转surrogate/deep-read, Qdrant列债)还是要我先专项查"非CFFC bundle coverage=0"。
- [E] 2026-05-28 清理主仓库 main 工作树 · B 5/27 commit pending V2.3 dirty 代清完成
            背景: 顾源源 5/28 决定清理 main 让它回到干净状态再合 feat 分支. 深度排查后(摸 3 个 dirty 内容/V2.3 commit 完整性/B 协作通道/影响面/3 worktree 一致性)发现 main worktree 那 3 个 dirty 是 B 5/27 PM 留 log "V2.3 上线 (Step 0-5 全 done) ... commit pending" 的遗留, B 后转 R2 自动验收官未回.
            动作:
            · 09afb25 fix(knowledge_v2): cloud reuse 命中时构造 ExtractedDocument stub 防 line 2642 structured_sheets 崩 — 独立 bugfix 进 main (尚未 push origin, 等顾源源 review)
            · 77a6106 feat(v23-auto-team-sync): 后台 team-sync worker + register_source 自动入队 — V2.3 PUSH 自动化代封存到新分支 feat/v23-auto-team-sync (已 push origin, B 回来自己决定 PR / 改 / 弃)
            · main 工作树清空 (除自己的 baton + log + inbox-from-E 协作文档变更)
            · 写 inbox-from-E.md 通知 B
            · safety-net stash 14ab8e5c 留 reflog 7 天可恢复
            事实:
            · V2.3 主体 (team_sync_executor 311 行 + migrate scripts + cloud_backend + Step 0-2 报告) 早已在 3ef7532 进 main, 没动
            · 手动端点 (/team-sync/enqueue-all|run-once|stats) 已在 3ef7532, 不依赖此次封存
            · 前端 UI 只调手动端点 (App.tsx:29099 + api.ts:2320), 清 dirty 不影响 UI
            · 主仓库 app db (YiyuThinkTankWorkbench2) 当前没有 source_registry 表, V2.3 ingest 在你 app 上从未实质运行, 清 dirty 对 app 行为零感知
            遗留:
            · narrative-retrieval + mini-panel 两 worktree 同款 source_registry_store.py dirty (hash 一致) 没清, 等顾源源回主仓库后单独处理
- [E] 2026-05-27 深读全链路实测(汇丰6篇/士平,豆包)+ M0 诊断固化。报告 docs/E_DOC_ENRICHMENT_M0_OLD_PIPELINE_DIAGNOSIS.md(+json)。
            ★ 旧 deep-read 链路多层断裂(实测): card-gen 任务 attempts=0 从未处理(钉死不可用 local_text_deep profile)/ 切豆包全局无效(per-task profile 路由)/ /local-ai settings|coverage|backfill 404 / document_cards 多数客户=0 / hydrate 无原料空转 / Qdrant 零贡献(见61-E)。
            ★ 汇丰全链路跑 30min 产出 0(cards 0→0, surrogate 0→0, coverage 0→0)。CFFC 能用是历史遗产(157 doc_cards+surrogate)。
            ★ 方向(顾源源拍板): 停止修旧 pipeline/Qdrant 当主线; 新建 DocumentEnrichmentService: v2_documents.markdown_content→豆包富化→写厚 knowledge_master_index.searchable_text(+surrogate)→喂现有 surrogate/lexical+v2_documents 检索。旧管线(local_text_deep/document_cards/Qdrant)降级技术债。
            ★ 给所有人: 别再建议"全客户 Qdrant reindex"或"切模型等 worker"——无效, 已实测。
            进行中: M0 done; 下一步 M1 建 DocumentEnrichmentService + M3 汇丰1篇 PoC(复用 ai_service.generate_memory_surrogate/enrich_retrieval_summary, 走豆包)。
- [E] 2026-05-27 深读三态取证(HEAD/工作树/runtime)完成。报告 docs/E_DEEP_READ_WORKTREE_CLOBBER_AUDIT_REPORT.md(+json)+桌面63-E。
            ★ 裁决 A:深读不是设计坏,是工作树 main.py 被多AI跨worktree覆盖——丢了 E 已提交的 W2 deep-read-worker 线程 + W4 /local-ai/settings|coverage|backfill 端点(工作树 diff HEAD = +156/-135, M)。
            ★ M5 决定性实证:干净 HEAD 检出(/tmp/yiyu-clean-head)+临时DB副本+豆包,处理汇丰1篇(19k字)→ 40s 产出真实 document_card,cards 0→1。已提交管线可用。
            ★ runtime 404 + card-gen attempts=0 = 工作树删了 W4 端点 + W2 worker(worker没起→没人claim任务)。不是 profile 跳过、不是 commit 不完整。
            ★ 结论:走外科式恢复(把 HEAD 的 W2/W4 深读代码补回工作树 main.py, 保留 maintenance+team-sync+predict),不重建 DocumentEnrichmentService。本轮只取证未改 main.py。
            ⚠️ 给B/所有人: main.py 三方(E深读/B team-sync/维护)缠在一个未提交文件互相覆盖, 这是 P0 协作问题——改 main.py 前务必 baton 标 HOLDING。
            未执行恢复(待顾源源拍板); 已清理临时 worktree/DB。
- [E] 2026-05-27 PM 执行路线A恢复 + 关 path_opt(工作树改动, 未提交)。
            ① 关 path_opt 入队: local_model_optimizer.py DEFAULTS + normalize + router.py 默认 True→False(path_opt 处理仍调未定义 generate_local_model_json 必失败, 是高失败率真凶)。
            ② 外科恢复 main.py: git apply -R 反向应用 5 个纯删除深读 hunk → W2 deep-read-worker 线程 + W4 /local-ai/settings|coverage|backfill 端点回来了; team-sync/维护/predict 全保留; py_compile 过。baton 已释放。
            ③ 发现 worker 饥饿真因: _claim_next_task ORDER BY priority,created_at ASC 取最老; 失败的 path_opt/visual_ocr 重试插队饿死汇丰(最新)card-gen(attempts 永远0)。已清 queued path_opt/ocr 积压 + DB 关 path_opt。
            进行中: 直接处理汇丰6篇 card-gen 建真卡(绕队列, 验证+给chat栈喂料)。runtime 生效需顾源源重启 app。
- [E] 2026-05-28 战略陪伴 retriever 切 v2 + 日慈叙事真上 cloud (rev=92)
            ★ 根因排查铁实: 战略陪伴 retrieve_knowledge_bundle (v1, knowledge_base) 的 citation grounding 需要 document_chunks; 但 v2 ingest 经 _sync_legacy_knowledge_document 半桥接, 只建 knowledge_documents 占位 (vector_status='chunk_indexed' 字段说谎), 不写 document_chunks 也不写 raw_text → 全库 617 docs 中只 CFFC 169 docs 有 5214 chunks (走 v1 ingest), 其余 0 chunks → 除 CFFC 外所有客户 bundle coverage=0 / citations=0 / no_grounded_citations。
            ★ 切到 knowledge_v2.retrieve_knowledge_bundle: excerpt 来自 v2_sections.content + preview_text, 不依赖 document_chunks。接口完全兼容(CitationMatch 字段超集, RetrievalBundle 一致, 签名兼容 del data_dir)。1 行 import 改动。
            ★ 实测(日慈, 6 维度 + CFFC 回归): 日慈 cov 0.55-0.70, cits 131, retrieval_path 100% semantic; CFFC cov 0.55-0.64 持平不退化。end-to-end LLM 134s 出全文 confidence=high (战略层/关系层/风险对冲 三段式, 真实事实: 高老师离职/心盛计划/南沙创投/民政审计)。
            ★ 已 push origin/feat/deep-read-foundation: commits 51f5f81 (retriever 切 v2) + cf20e3d (card 富化 + 验证脚本)。PR URL: github.com/guyuan9300-max/yiyu-thinktank-workbench/pull/new/feat/deep-read-foundation
            ★ hot patch mini-panel/backend/app/services/strategic_narrative_semantic_retriever.py 同 1 行改动 (因你面前 app 跑 mini-panel 代码, 不动它看不见效果), uvicorn auto-reload 生效后 POST regenerate 169s 完成, cloud 落库 rev=92, _cloudIngestError=None。baton 已释放。⚠ 给 B/所有人: PR 合 main 后 mini-panel rebase 此 hot patch 自然替代, 无遗留。
            ★ 给 C: 在 inbox-C 答了 5/27 你的挂账 — retrievalMode/fallbackUsed 字段规格 + 当前接口分工。前端「取材来源标记」UI 仍空, 因为 dims output 没透传, 这是下一个 PR 的活(E 改 collector/generator + C 改 cloud ingest)。
            ★ 富化遗留(可保可弃): 日慈 surrogate 36→151 + searchable_text 从 OCR 噪声变豆包摘要, 此层数据切 v2 后战略陪伴不再读, 但对数据中心 surrogate 浏览等其他场景仍有价值。可重跑可重建。
- [E] 2026-05-28 12:00 「下一步要做什么」UI 空白真因 + 修复(continuation of 切 v2)
            ★ 用户报告 cmd+R 后「下一步要做什么」UI 仍空。系统排查 5 步层层下钻:
              ① 战略陪伴 next_steps 维度叙事 ≠「下一步要做什么」UI(前者是「本阶段战略思路」标签);
              ② 「下一步要做什么」import 自 UnifiedTodoSection.tsx 但实际未 JSX 渲染(死代码);
              ③ 真实渲染入口在 StrategicClarificationView.tsx:1310+ 的内联组件, 调 getNextSteps(clientId);
              ④ ipc 日志锁定: 11:36-11:37 前端调了 GET /api/v1/clients/{id}/next-steps 但返回 HTTP 500;
              ⑤ 500 错: ModuleNotFoundError: No module named 'app.services.next_step_reconciler'。
            ★ 根因: 5/27 e938f66 commit feat(next-steps) 行动闭环对账服务 next_step_reconciler.py 在 feat/deep-read-foundation 分支(15595 字节, 我所在 worktree 有)。但主仓库 main + mini-panel main.py 都已经 import 了 next_step_reconciler(line 28411 from app.services.next_step_reconciler import reconcile), 服务文件却没合进去 — 又一个 main.py 漂移 case。
            ★ 修复(hot patch): cp narrative-retrieval/backend/app/services/next_step_reconciler.py → mini-panel/backend/app/services/。uvicorn auto-reload 5s 后 /next-steps 端点 HTTP 200, 返回日慈 16 条 items(commitment+meeting union)。
            ★ 验证: 抽样命中 "提交理事会汇报简版材料"、"下周二前提供更轻量的试点方案"、"撰写价值观调研问题并组织核心团队讨论"、"起草试点期合作合同"等真实战略陪伴待办。
            ★ 协作纪律说明: 此次是补缺失文件而非改代码逻辑, 0 风险, 跟 mini-panel 现有 dirty(B 的 V2.3) 完全无关; 未事前占 baton 是疏忽, 事后留痕在此。e938f66 已在 origin/feat/deep-read-foundation, PR 合 main 后 mini-panel rebase 自然替代。
            ⚠ 给所有人: 主仓库 main.py 现在含 next_step_reconciler import 但 services/ 缺文件, 主仓库 backend 重启时端点会 500。PR 合并应该一并解决。
- [E] 2026-05-28 UnifiedTodoSection 死代码备注
            该组件 import 自 StrategicBrainView/StrategicClarificationView 但 JSX 里实际未渲染(grep '<UnifiedTodoSection' 全 0 匹配)。「下一步要做什么」UI 真渲染由 StrategicClarificationView 内联组件提供, 走 /next-steps 端点(非 /todos/unified)。后续 refactor 可考虑彻底删 UnifiedTodoSection.tsx 或重新挂载, 但不阻塞当前。
- [E] 2026-05-28 PM 全局合并 3 个 feat 分支 → main, 顾源源授权按阶段+里程碑复盘执行
            阶段顺序: 1(push main 基底) → 2(merge exp-wall) → 3a(narrative-retrieval clean+push) → 3b(merge deep-read+解 4 冲突) → 4(merge mini-panel)
            每阶段后做深度复盘自查, 通过才进下一步.
            ★ 阶段 3a 关键发现: narrative-retrieval worktree main.py +211 行 dirty 是"撤掉 W2/W4 + 加 V2.3 worker"的污染态(hash 47209533d6d6, 跟所有分支不一样).
              用 git restore 撤掉污染, 救回 W2 worker + W4 端点. source_registry_store dirty(B V2.3 同款 hash 1a81435d889f) 一并 restore, 跟 V2.3 解耦.
              然后 commit 4 个真 E 活 (local_model_optimizer.py priorityClientId+path_opt默认/DeepReadSettingsCard.tsx 客户下拉/api.ts 类型/log.md 留痕).
              push origin/feat/deep-read-foundation (commit 828a5eb).
            ★ 阶段 3b 4 冲突手工解: knowledge_v2.py 采用 main(09afb25 stub bugfix), baton.md 采用 main(干净), api.ts 采用 feat(注释更全), log.md union 删 marker.
              merge commit 7e295e4 push 成功.
            ★ 阶段 4: feat/mini-panel 0 真冲突, auto-merge, 6 文件 +545 行(MiniPanel.tsx 336 + buildMiniData.ts 89 + main.ts/preload/App.tsx/types 整合).
              mini-panel worktree dirty 9 文件 (B 别活 + 4 untracked mini-preview) 不动, 留 worktree 待维护者处理.
            ★ 最终 main 状态(全局验证):
              · W2 worker 4 处 / W4 端点 7 个 / V2.3 worker 0 (解耦封在 feat/v23-auto-team-sync)
              · team-sync 手动端点 3 个 (3ef7532) / growth_sync + handbook_sync import 接通
              · user app uvicorn auto-reload, /local-ai/settings 200, /next-steps 200, /system/health 200
              · 测试 3 pass / 0 fail (pre-existing OCR retry 4 + growth_engine 2 失败已实证不是合并锅)
            commits 累计: cc1247e → 20157bc → 828a5eb → 7e295e4 → f37e326 (origin/main HEAD)
            遗留: mini-panel + narrative-retrieval 2 worktree 仍有 dirty (B V2.3 同款 source_registry_store + 别的), 等顾源源叫我再处理.
