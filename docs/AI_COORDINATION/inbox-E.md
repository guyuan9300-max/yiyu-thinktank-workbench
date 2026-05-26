
---

## [B → 协作 AI 线程] 2026-05-25 PM · ⚠ 仓库已切换至主仓库 main

**关键事件**: V2.1 lab 实验仓库 (`~/openclaw/workspace/V2.1/`) 内容**已合并到主仓库 main**, 同事现在通过 `github.com/guyuan9300-max/yiyu-thinktank-workbench` 拉代码.

### 🚨 你应该立刻知道的 6 件事

1. **工作目录改了**
   - 旧 (废): `~/openclaw/workspace/V2.1/`
   - 新 (主): `~/openclaw/workspace/yiyu-thinktank-workbench/`
   - V2.1 lab push 红线还锁着 (`no_push_v21_lab_red_line`), 不要在 lab 改代码再 push

2. **git main 分支真状态**
   - 当前 HEAD: `2dfbff9 sync: 合并 origin/main 后继续推送选中的本地修改`
   - 包含: V2.1 全部 164 commit + main 原 8 fix + TOS 自动更新 2 commit + B 今天 path C+D 改动
   - 跟 github origin/main 完全同步 (0 偏差)

3. **path C+D 新设计 (顾源源 5/25 PM 钦定)**
   - **path C** · `org_members_v` view: 人 + bot 统一组织视图 (is_bot 字段)
     - bot 跟 admin/employee 一样进组织, 老 mock 黑名单已彻底删
     - `EmployeeRole` 加 `'ai_agent'`
   - **path D** · AI 同事跟人走一套接口 (顾源源洞察"AI 是真同事"):
     - bot 做完自动建 task + auto-done + 自动复盘 entry
     - tasks.owner=bot, collaborator=发起人 → 顾源源日历可见
     - 不再独立 AI 视图, 全部进重点主线/复盘

4. **bot 系统真接好了** (M9 + M10 by A)
   - `plan_executor.py` 接 plan_executor → 真调豆包/qwen 出 markdown → 真写 documents + .docx
   - 文件名中文化, 排版优化 (微软雅黑, H1/H2 字号层级)
   - LLM 解析 step 用本地 qwen2.5:7b (5s, 0 成本, 隐私)

5. **cloud_backend 客户去重 fix** (5/25 PM 真客户问题)
   - POST `/api/v1/clients` 加 name dedup, 防同名 client 重复 INSERT
   - 历史已重复条目用 `scripts/cleanup_duplicate_clients_cloud.py` 清

6. **协作目录路径不变**
   - `docs/AI_COORDINATION/` 在主仓库根, 含 baton.md / inbox-*.md
   - 继续走 inbox 沟通, baton 管 monolithic 文件并行编辑

### 你接下来该做的

- ✅ cd 到主仓库 `~/openclaw/workspace/yiyu-thinktank-workbench/` 干活
- ✅ 走 feature branch + PR (`git checkout -b feat/xxx`)
- ✅ 你的改动会被同事拉到 (push origin main 影响产线)
- ❌ 不要再 cd 到 `~/openclaw/workspace/V2.1/` 改东西 (那是 lab 退役地)
- ❌ 不要在 main 直接 commit (走 PR 流程)

### 跟你工作相关的文档

- `docs/A_M8_M9_M10_PLAN_EXECUTOR_REPORT.md` (A 实现 M8-M10)
- `docs/B_AI_V2_5_R2_REPORT_20260523_084057.md` (B R2 评估)
- `~/Desktop/益语智库 2.0 产品手册/47-B-AI执行内容评估报告-对照原始指令-2026-05-25.md` (最新内容评估)

— B (Opus 4.7 1M), 2026-05-25 PM
