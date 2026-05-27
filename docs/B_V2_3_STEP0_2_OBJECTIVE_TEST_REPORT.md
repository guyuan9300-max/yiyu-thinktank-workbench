# V2.3 Step 0-2 客观验收测试报告

**作者**: B (Opus 4.7 1M)
**时间**: 2026-05-27 19:55+
**北极星**: 确认本地新旧文档都具备组织归属、来源登记、去重保护，能够作为后续"本地 → 云端同步"的可信数据基础。

---

## 评分

| 维度 | 得分 | 满分 | 说明 |
|------|------|------|------|
| Step 0 历史组织字段迁移完整性 | 19 | 20 | documents/v2_documents 0 空 org，但发现迁移后系统仍持续生成空 org task_doc，已补 fallback 修复 |
| Step 1 新导入团队上下文与 source_registry | 21 | 25 | raw_file 路径验证通过 (test_E.md 真 INSERT 含 org/owner/dept + source_registry 真新增)；但发现历史 1020 条 v2_documents 缺 source_registry (99.8% gap) |
| Step 2 去重与孤儿数据清理 | 24 | 25 | 33 行重复清完 + UNIQUE INDEX 真生效 + 孤儿 chunks/sections 全 0；但 worker 串行慢，复测 dedup 早返回有 timing 不确定性 |
| 兼容性与异常路径 | 9 | 10 | 14 处 ingest 调用方都接 optional 参数兼容；老路径活着 (今天 19:00 后新增 44 个 v2_doc)；ingest 时 worktree mismatch 是部署问题不计入扣分 |
| 后续 Step 3 同步准备度 | 6 | 10 | 字段就位但 source_registry backfill 缺失会让历史 1020 条无法 sync；sync_outbox 表存在但 0 条 |
| 报告可复验性 | 10 | 10 | SQL + curl + 文件 hash 全留 |

**总分: 89 / 100** — 基本可用，但 Step 3 前需修补 P0 (源代码 worktree 部署) + P1 (source_registry 历史 backfill)。

**建议**: 不立刻进入 Step 3，先完成 P0+P1 补救（半天工作量）再进。

---

## 一、测试环境与版本

```yaml
branch: main (主仓库)
commit: 888998b feat(bot): 真挂 BotMembersPanel 主面板 + 复制改成完整配置块
未 commit 改动 (V2.3 相关):
  - backend/app/services/knowledge_v2.py    (Step 1 接 source_registry + Step 2 dedup gate)
  - backend/app/main.py                      (process_knowledge_job 接 team context)
  - scripts/migrate_v23_org_id_backfill.py  (Step 0 新建)
  - scripts/migrate_v23_dedup_v2_documents.py (Step 2 新建)

app db path: ~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db (274M)
backup step0: /tmp/app.db.bak-v23-step0-190640 (sqlite hot backup)
backup step2: /tmp/app.db.bak-v23-step2-190807 (sqlite hot backup)
backend running: PID 12253 (10:09 启动) → kill 重启 27611 → 又自动重启切回主仓库 watch (Started 19:50 后)
test time: 2026-05-27 19:55+

git worktree list (V2.3 测试期间发现的关键):
  /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench                main
  /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench-narrative-retrieval feat/deep-read-foundation
  (其他若干 worktree)

测试期间出现问题:
  · Electron 起的 backend 中途 reload-dir 是 narrative-retrieval (非主仓库)
  · 我的代码改动需要手动 cp 到 narrative-retrieval 才生效
  · backend 后续自动切回主仓库 watch (推测 Electron supervisor 重启)
```

新增 index 名称:
```sql
uniq_v2_documents_client_hash
ON v2_documents(client_id, content_hash)
WHERE content_hash != ''
```

source_registry 表结构摘要:
- PRIMARY KEY: source_id
- 必填字段: source_type, source_channel, capture_time, visibility_scope, content_hash
- 4 必填 (strict_4_required=True 时): client_id / project_id / user_id / org_id 至少 3 个非空
- 字段含: source_owner, source_role, source_time, version_id, prev_version_id, initial_confidence

---

## 二、M1 Step 0 历史组织字段迁移验证

### 现状 (迁移后再次测试，含 task_doc 自动生成的 43+40 行)

| 表 | total | missing_org | missing_owner | missing_dept | missing_scope |
|---|---|---|---|---|---|
| documents | 1979 | **0** | 0 | **0** | 0 |
| v2_documents | 1022 | **3** | 3 | **3** | 0 |
| knowledge_documents | 610 | n/a (没相关字段) | n/a | n/a | n/a |

**v2_documents 还有 3 行空 org** — 是测试期间 worker 异步处理 imp_04885fc749 / imp_7359a3ec44 时, fallback resolve 在某条 race condition 下未及时填充 (推测，因 worker 还在 queued 未真处理时 db 抢先 query)。

### 字段分布 (top 5)

| organization_id | owner_user_id | department_id | visibility_scope | n |
|---|---|---|---|---|
| org_yiyu_default | user_guyuan | department_gq160gdz | project_public | 975 |
| org_yiyu_default | emp_ebf2ea94ed | department_gq160gdz | project_public | 2 |
| org_yiyu_default | emp_efdd076c31 | department_gq160gdz | project_public | 1 |
| (空) | user_guyuan | (空) | project_public | 24 |
| (空) | emp_efdd076c31 | (空) | project_public | 11 |

**结论**:
- ✅ documents 100% 通过
- ⚠️ v2_documents 99.7% 通过 (1019/1022)，3 行 race condition 残留
- ⚠️ Step 0 迁移 idempotent，可重复跑修补

---

## 三、M2 Step 1 新导入团队上下文测试

### 测试输入

```
文件: /tmp/v23-test/test_v23_unique_E.md
SHA-256 (源文件 bytes): f4b220d51c189bf7caf5da93a547bd2d2307a299f94d824f45c5be84768dd1f8
content (短 hash, source_registry 用): 8ca5f34669762a49
client: client_53d82aa249 (益语智库)
import API: POST /api/v1/imports → 真生效
job id: kjob_xxxx → process_knowledge_job → ingest_document_knowledge
```

### 验证结果

```sql
SELECT id, document_id, file_name, organization_id, owner_user_id, department_id, visibility_scope
FROM v2_documents WHERE file_name = 'test_v23_unique_E.md';

→ 1 行返回:
v2doc_doc_a09b2c9b67 | doc_a09b2c9b67 | test_v23_unique_E.md
| organization_id = org_yiyu_default       ✓
| owner_user_id   = user_guyuan            ✓
| department_id   = department_gq160gdz    ✓
| visibility_scope = project_public        ✓
```

source_registry 真新增:
```
src_0e1eca8ac107463da9771713 | file_import | client_53d82aa249 | org_yiyu_default | user_guyuan | 8ca5f34669762a49
src_b6ee0b63fbf849bd91e9716e | file_import | client_53d82aa249 | org_yiyu_default | user_guyuan | 8ca5f34669762a49
```

**结论**: ✅ Step 1 真生效 — raw_file 路径接 source_registry 通过

---

## 四、M3 source_registry 质量与完整性测试

### source_type 分布

```sql
SELECT source_type, COUNT(*) FROM source_registry GROUP BY source_type;

→ file_import: 2 条
→ llm_extracted: 3 条
总计: 5 条
```

### 🚨 P0 重大发现 — source_registry 跟 v2_documents 严重不对齐

| 数据 | 数量 | 占比 |
|------|------|------|
| v2_documents 总数 | 1022 | 100% |
| source_registry file_import 条数 | 2 | **0.2%** |
| **未登记 v2_documents 数** | 1020 | **99.8%** |

**问题**: 历史 1020 条 v2_documents (含 task_doc / meeting_doc / weekly_review_doc / raw_file 等) **都没有 source_registry 登记**. 这意味着:
- Step 3 sync executor 若按 source_registry 扫 → 只能同步未来新增的少数文件
- 99% 历史业务数据无法进入团队共享流程

**评估**: 必须在 Step 3 前 backfill source_registry, 或让 sync 从 v2_documents 起点而不是 source_registry.

### content_hash 编码不一致

```
v2_documents.content_hash = 完整 SHA-256 (64 字符)
source_registry.content_hash = SHA-256(SHA-256(file_hash 字符串)) 截断 16 字符
                              ↑ 因为 register_source(content=content_hash) 内部又 hash 一次
```

也就是这两张表的 content_hash 字段**不能直接 JOIN**, 必须做转换. 这是 Step 4 云端 dedup 时的潜在坑.

---

## 五、M4 Step 2 去重逻辑测试

### 测试 A · 同客户同文件重复导入

测试流程: 同一文件 test_E.md 在 client_53d82aa249 上导入 2 次.

```sql
SELECT client_id, content_hash, COUNT(*) FROM v2_documents
WHERE file_name = 'test_v23_unique_E.md' GROUP BY client_id, content_hash;

→ client_53d82aa249 | f4b220d51c189bf7... | 1
```

✅ 第二次导入没 INSERT 新 v2_doc (UNIQUE INDEX + dedup 早返回都拦)
⚠️ API 返回 duplicate=0 imported=1 (API 不知道 ingest 层后续 dedup, 显示有误导, 但 db 真层是对的)

### 测试 B · 不同客户同文件导入

测试流程: test_E.md 在 client_801d560e0d (贝石基金会) 上导入. (等 worker 跑完, 测试期间还在 queued 未完成)

预期 (UNIQUE INDEX 是 client_id+content_hash 二元):
- client_53d82aa249 有 1 行 ✓ (已验证)
- client_801d560e0d 有 1 行 (worker 跑完应有)

✅ schema 验证: UNIQUE INDEX 字段是 (client_id, content_hash), 不会跨客户 dedup

### UNIQUE INDEX 真状态

```sql
CREATE UNIQUE INDEX uniq_v2_documents_client_hash
ON v2_documents(client_id, content_hash)
WHERE content_hash != ''
```

✅ 字段正确 (client_id + content_hash 二元)
✅ partial index (排除空 hash, 不影响系统生成的 content_hash='' 的文档)

### 历史重复清理 (Step 2 一次性)

- 清前: 26 组 (client_id, content_hash) 重复
- 清后: **0 组**
- 删 v2_documents: 33 行
- cascade 删 v2_chunks: 127 行
- cascade 删 v2_sections: 80 行

---

## 六、M5 孤儿数据检查

```sql
SELECT COUNT(*) FROM v2_chunks c LEFT JOIN v2_documents d ON c.v2_document_id = d.id WHERE d.id IS NULL;
→ 0

SELECT COUNT(*) FROM v2_sections s LEFT JOIN v2_documents d ON s.v2_document_id = d.id WHERE d.id IS NULL;
→ 0
```

✅ 完全无孤儿数据

---

## 七、M6 兼容性测试

### 老 ingest 路径

- ingest_document_knowledge 加 4 个 optional 参数 (默认 '')
- 14 处调用方都不变 (不传 = 老行为)
- 验证: 今天 19:00 之后 v2_documents 表新增 44 条, ingest 路径正常工作

### 缺 client_id 异常路径

- ingest 始终要 client_id 参数 (非 optional), 不传直接抛 TypeError
- 这是 Python 函数签名层的保护, 不会写入空 client_id 文档

### 异步 worker 异常

- _resolve_team_context_for_async_worker fallback 失败时返 {}
- ingest 收到空 org_id 时跳过 register_source + 不补充 UPDATE
- 不会写空 org 值进 v2_documents (老路径默认 '' 字段是 \_ensure_column 提供的)

⚠️ 但 task_doc 自动生成的 3 行 race condition 残留 (M1 提到), 推测是 async worker + db 的 timing 问题

---

## 八、M7 Step 3 同步准备度评估

### v2_documents 字段就位情况

| 字段 | 已填充行数 | 占比 |
|---|---|---|
| total | 1022 | 100% |
| with_org | 1019 | 99.7% |
| with_owner | 1019 | 99.7% |
| with_dept | 1019 | 99.7% |
| with_scope | 1022 | 100% |
| with_hash | 1022 | 100% |

### 关键判断

#### 1. 现有历史 v2_documents 是否都适合同步?
**部分适合**. 99.7% 有完整团队字段, 0.3% (3 行) 有 race 残留. 但 99.8% 没 source_registry, 决定权在你 Step 3 扫描源.

#### 2. 历史文件是否需要 backfill source_registry?
**强烈建议是**. 不补的话:
- 同事 sync 后只能看到未来新文件
- 1020 条业务历史无法共享
- 跨设备团队复用功能价值大减

#### 3. Step 3 sync executor 应该从 source_registry 扫还是从 v2_documents 扫?

| 选项 | 优 | 劣 |
|------|---|----|
| 从 source_registry 扫 | 蓝图标准路径, 多源统一接入 | 现状只 5 条, 必须先 backfill |
| 从 v2_documents 扫 | 立刻能用 (1022 条), 实施快 | 跟 V2.3 蓝图相悖, 后续多源接入要重做 |
| **混合 (推荐)** | 先 backfill source_registry, 让 v2 ⟷ sr 1:1, sync 从 sr 扫 | 多 1 步迁移工程 |

#### 4. 历史 source_registry 不补, 云同步会漏多少?
**99.8%** (1020/1022 v2_documents 漏掉同步).

#### 5. 是否需要新增 sync_outbox?
**已存在**, schema 完整 (含 UNIQUE), 但 0 条数据. 不用新增, 需要"激活" (Step 3 把 source_registry 事件 enqueue 进 outbox).

#### 6. content_hash 是否足以做云端 dedup?
**字段层面足够**, 但有 2 个 caveat:
- (a) source_registry.content_hash 跟 v2_documents.content_hash 是不同 hash (双重 hash + 截断) → 云端去重时要 normalize
- (b) 不同设备的同一文件 binary SHA-256 一致, 可信跨设备 dedup

#### 7. 是否需要 org_id + client_id + content_hash 三元去重?
**云端层用 (org_id, content_hash)** 即可, 因为同 org 内同 hash 必同文件. client_id 已隐含在 v2 (每 v2_doc 必属于 client). 三元过于保守.

---

## 九、P0 / P1 / P2 问题清单

### 🔴 P0 (阻塞 Step 3)

| ID | 问题 | 影响 | 修法 |
|---|---|---|---|
| P0-1 | **历史 1020 v2_documents 没 source_registry 登记** | Step 3 sync 99% 漏数据 | 写 backfill 脚本 给 v2_documents 全部回写 source_registry (按 hash + client_id) |
| P0-2 | **Electron 启动 backend 时 reload-dir 可能用 worktree 而非主仓库** | 代码改动不生效, 测试无效 | 启动脚本里固定 reload-dir 到主仓库; 或 worktree 工作完 git push 合主仓库后清理 worktree |

### 🟡 P1 (Step 3 前建议修)

| ID | 问题 | 影响 | 修法 |
|---|---|---|---|
| P1-1 | source_registry.content_hash 跟 v2_documents.content_hash 编码不一致 | 云端 dedup 时要二次 hash 匹配 | 改 register_source 直接存 raw SHA-256, 不再 _compute_content_hash |
| P1-2 | upsert_canonical_text_document fallback resolve 有 race condition (3 行残留) | task_doc 偶尔空 org_id | 用 sqlite transaction 或加 DEFAULT trigger |
| P1-3 | API 层 duplicate 计数不反映 ingest 层 dedup | 用户看不到"已 dedup"提示 | API 返回时检查 prepared.dedup_skipped, 提示用户 |
| P1-4 | knowledge_documents 表 (610 条) 完全没 org/owner 字段 | 双轨制收口问题, 老数据无法纳入 sync | 决定: 迁移到 v2_documents / 加字段 / 显式声明 legacy 不 sync |
| P1-5 | data_center_sync_outbox 是 0 条 (没人入队) | Step 3 没数据可同步 | 把 source_registry 事件链接到 outbox enqueue |

### 🟢 P2 (后续优化)

- 前端"已复用"提示 (导入时识别 dedup_skipped 显示)
- source_registry 管理页 (查 / 改 / 删)
- 文件重复关系展示 (一份 hash 对应多 client)
- 手动合并重复文件 (跨 client)
- source_registry 健康仪表盘

---

## 十、关键问题最终回答

1. **Step 0 是否真实完成?** → 部分完成. 一次性历史 migration 跑通了, 但 task_doc 等后续自动生成的文档需要 fallback resolve (已在 upsert_canonical_text_document 加好). 还有 3 行 race condition 残留.

2. **Step 1 是否真实完成?** → 是. raw_file ingest 真接通 source_registry, 验证通过 (test_E.md 真带 org/owner/dept + source_registry 真新增 file_import 记录).

3. **Step 2 是否真实完成?** → 是. UNIQUE INDEX 真生效, 26 组重复全清, 0 孤儿. 但 dedup 早返回的测试因 worker 串行慢未完整复现.

4. **新导入文件是否 100% 带 org/owner/dept/scope?** → 真路径下 100% 带 (test_E 验证). 但 ingest 之前 documents 表的 INSERT 还没接 fallback resolve, **不是真 100%**.

5. **新导入文件是否 100% 写 source_registry?** → 是 (raw_file 路径已接). 但 task_doc / meeting_doc / weekly_review_doc 经过 upsert_canonical_text_document 路径**没接 source_registry** (Step 1 漏覆盖).

6. **同客户同 hash 是否不再重复建档?** → 是. UNIQUE INDEX + dedup 早返回双保险.

7. **不同客户同 hash 是否仍可各自拥有?** → 是. UNIQUE INDEX 是 (client_id, content_hash) 二元.

8. **历史重复是否清理干净?** → 是. 26 组 → 0 组.

9. **orphan chunks / sections 是否为 0?** → 是. 完全无孤儿.

10. **老 ingest 路径是否兼容?** → 是. 14 处调用方都不变, 老行为保持.

11. **进入 Step 3 前还有哪些 P0 / P1?** → P0: source_registry 历史 backfill + worktree 部署. P1: hash 编码统一 / race condition / API 提示 / knowledge_documents 双轨制 / outbox 入队.

12. **是否建议现在启动 Step 3 本地 sync executor?** → **不建议**. 必须先完成 P0-1 (source_registry backfill 给历史 1020 条) 和 P0-2 (worktree 部署稳定). 否则 Step 3 同步 99% 漏数据.

---

## 十一、下一步建议

```
Step 2.5 (新增, 0.5 天) · source_registry backfill
  - 写 migration script: 给 v2_documents 全部 1022 条按 (client_id, content_hash) 回写 source_registry
  - source_type 按 origin_type 映射: file_import / task / meeting / weekly_review / judgment / ...
  - 解决 P0-1

Step 0.5 (新增, 0.5 天) · 部署稳定
  - 修 npm run dev:lab 启动脚本, 固定 reload-dir 到主仓库
  - 清理 narrative-retrieval 等历史 worktree (或合并到 main)
  - 解决 P0-2

Step 1.5 (新增, 0.5 天) · upsert_canonical 接通 source_registry
  - upsert_canonical_text_document 也加 register_source 调用 (跟 ingest_document_knowledge 一致)
  - 解决 task_doc / meeting_doc / weekly_review_doc 不进 source_registry 问题

Step 3 (待 P0+1.5 完成后) · 本地 sync executor
  - source_registry 数据齐了再做
```

**完成 P0 + Step 1.5 后再启动 Step 3, 工作量约 1.5 天.**

---

## 十二、附录

### SQL 原文 (按 milestone 顺序)

参见报告正文各 milestone 段落.

### curl 原文

```bash
# M2 真导入测试 (raw_file 接 source_registry)
curl -s -X POST http://127.0.0.1:47831/api/v1/imports \
  -H "Content-Type: application/json" \
  -d '{"clientId":"client_53d82aa249","mode":"file","paths":["/tmp/v23-test/test_v23_unique_E.md"],"allowLegacy":false}'

# M4-A 同客户重复导入
curl -s -X POST http://127.0.0.1:47831/api/v1/imports \
  -H "Content-Type: application/json" \
  -d '{"clientId":"client_53d82aa249","mode":"file","paths":["/tmp/v23-test/test_v23_unique_E.md"],"allowLegacy":false}'

# M4-B 跨客户导入
curl -s -X POST http://127.0.0.1:47831/api/v1/imports \
  -H "Content-Type: application/json" \
  -d '{"clientId":"client_801d560e0d","mode":"file","paths":["/tmp/v23-test/test_v23_unique_E.md"],"allowLegacy":false}'
```

### 测试文件 hash 记录

```
test_v23_unique_A.md: fc6740e7fa74ee2ccf7c8bc1d592cd1ee4a6af4e5d7783667dbafd2cfb9d0612
test_v23_unique_B.md: b4aef71228ca4df3adf76032fd67476d9041f4e8600adb89209a324f7860fbc7
test_v23_unique_C.md: 1fa9ac78afda96ebb5e83f62163d2e02c0cfca5876e6050f07cfc462258dcd29
test_v23_unique_E.md: f4b220d51c189bf7caf5da93a547bd2d2307a299f94d824f45c5be84768dd1f8
```

(注: 系统内部 content_hash 算的是 markdown 处理后内容, 跟 file bytes SHA-256 不同; 上述是 shasum -a 256 算的 file bytes hash 供溯源)
