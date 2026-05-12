# 理解深度优化 · 进度跟踪

**分支：** `feature/understanding-depth`  
**起点：** main @ `793bf44` (2026-05-12)  
**最新提交：** `ddf4a8b` docs commit

---

## 迭代进度总览

| 迭代 | 状态 | 起止 | commit | 验收 |
|---|---|---|---|---|
| 0 准备工作 | ✅ 完成 | 2026-05-12 | `ddf4a8b` | 全 ✅ |
| 1 鲜度衰减 | 🔄 代码完成 / 待真机验证 | 2026-05-12 | (待真机 commit) | 见下 |
| 2 实体基础设施 | ⏳ 待开 | - | - | - |
| 3 实体合并 + UI | ⏳ 待开 | - | - | - |
| 4 chunk 语义分类 | ⏳ 待开 | - | - | - |
| 5 关系三元组 | ⏳ 待开 | - | - | - |
| 6 原子事实 + 矛盾检测 | ⏳ 待开 | - | - | - |
| 7 客户术语库 | ⏳ 待开 | - | - | - |

---

## 迭代 0 · 准备工作

### 已完成
- [x] 建分支 `feature/understanding-depth`
- [x] commit 四份审计/方案/计划文档（`ddf4a8b`）
- [x] dev 模式应用启动（bundle id: `com.yiyu.selfworkbench2.dev`，副屏 F34G4Q）
- [x] computer-use 权限拿到（tier: full）

### 关键发现：执行环境约束

**沙箱限制：** Cowork 沙箱（Ubuntu 22, Python 3.10）**不能直接跑后端 pytest**：
- `.venv` 是 macOS 路径，sandbox 用不了
- `uv` 在线下载 Python 时网络不通
- 重型依赖（pymupdf / fastembed / qdrant-client / yt-dlp）在沙箱安装会很慢甚至失败

**执行分工：**
- **沙箱内做：** 写代码 / 写测试（不跑）/ 静态分析 / grep / 改 schema / 写迁移脚本
- **真机做（通过 Claude Code 或用户）：** pytest 实跑 / ingest 实跑 / UI 验证

**这个约束需要写进每个迭代的"验证"步骤：** 我写完代码后给出 commit + 测试用例，Claude Code/用户在真机跑测试并截图回传 UI 验证结果。

### 关键集成点（后续迭代要改的文件）

| 集成点 | 文件 | 行号 | 说明 |
|---|---|---|---|
| **ingest 主入口** | `backend/app/services/knowledge_v2.py` | 1696 | `ingest_document_knowledge()`，所有新能力的 hook 点 |
| **LLM 服务类** | `backend/app/services/ai.py` | 155 (class) | `AiService` 类，鸭子类型分发；新能力方法加在此 |
| **业务对象 ingest** | `backend/app/services/data_center_ingest.py` | 1074-1742 | task/note/attachment/meeting/weekly_review/event_line 六类 |
| **建表 + 迁移** | `backend/app/db.py` | - | `CREATE TABLE IF NOT EXISTS` 模式 |
| **数据模型** | `backend/app/models.py` | - | Pydantic v2 模型 |
| **路由注册** | `backend/app/main.py` | - | FastAPI 路由 |
| **检索重排** | `backend/app/services/evidence_selector.py` | 387 (rerank) | 鲜度/语义类型权重接入 |
| **运维面板** | `src/renderer/components/data_center/DataCenterOpsPanel.tsx` | - | 实体管理 UI 接入点 |

### 关键现状（freshness 替换的工作量预估）

`memory_foundation.py` 里 freshness 静态赋值共 **20+ 处**（grep 行号：257, 270, 434, 621, 658, 677, 700, 705, 720, 1541, 1588, 1601, 1632, 1661, 1674, 1686, 1699, 1712, 1727, 1740...）。每处都需要：
- 改成 `compute_freshness(doc_type, created_at)` 调用
- 上下文里要拿得到 `doc_type` 和 `created_at`——部分位置可能要新增参数

### 工程约定（用户的 Python 风格规则）

- **PEP 8**，**类型注解** 全员
- **dataclass**（frozen 优先）作为 DTO
- **Protocol** 做鸭子类型
- **pytest** 框架（沙箱不跑，写好交给真机）
- 用 **logging** 不用 print
- **black / ruff / isort** 格式
- 密钥用 `os.environ`

### 待跑（交给 Claude Code 在真机执行）

- [ ] 跑 `cd backend && uv run pytest tests/ --tb=no -q`，记录基线通过/失败计数（请把 summary 行贴回来）
- [ ] 跑 `cd backend && uv run pytest tests/ --collect-only -q 2>&1 | tail -5` 看测试总数

### UI 验证场景（迭代 0 阶段）

- [x] dev 模式应用成功启动（已截图）
- [x] 应用界面可见、状态显示"本机模式 / 9 客户"
- [ ] 切到"工作台 → 益语智库客户"作为后续迭代的标准操作页

---

## 后续迭代的 UI 验证场景设计（待每个迭代①步细化）

### 迭代 1（鲜度衰减）
- **场景**：在客户工作台问一个有新旧文档混合的问题
- **入口**：工作台 → 任一客户 → 提问
- **期望**：右侧"当前回答引证"面板，旧文档（半年前）的引证权重明显低于近期文档；可能还需要新增"鲜度"显示字段

### 迭代 2（实体基础设施）
- **场景**：导入一份新文档后，能在客户工作台看到识别出的实体列表
- **入口**：工作台 → 客户 → 导入文档 → 等几秒 → 文档详情或客户实体面板
- **期望**：至少看到 5 类实体（人/公司/项目/产品/竞品/金额/日期）

### 迭代 3（实体合并）
- **场景**：运维面板有"实体管理"页签，能看到自动识别的待审实体
- **入口**：系统设置 → 数据中心运维面板 → 实体管理
- **期望**：列待审实体；点合并按钮后该对实体被合并、提及自动转移

### 迭代 4（语义分类）
- **场景**："当前回答引证"面板每条引证显示语义类型
- **入口**：工作台 → 提问 → 看引证
- **期望**：每条引证带"事实 / 判断 / 观点"标签

### 迭代 5（关系三元组）
- **场景**：问"客户 X 的所有战略目标"得到结构化列表
- **入口**：工作台 → 提问
- **期望**：答案是列表式呈现，每条带来源文档；可能需要新建一个"客户关系图谱"面板

### 迭代 6（矛盾检测）
- **场景**：导入两份预先准备好的矛盾资料（不同预算金额），客户工作台显示告警
- **入口**：工作台 → 客户 → 看顶部告警栏 / inbox
- **期望**：出现"矛盾告警卡"，能展开看冲突双方、能 dismiss

### 迭代 7（客户术语库）
- **场景**：客户工作台有"术语表"页签，能加术语；AI 回答时正确使用术语
- **入口**：工作台 → 客户 → 术语表 tab
- **期望**：加 1 条术语后，AI 在回答涉及该词时按定义解释

---

## 风险登记

| ID | 风险 | 状态 | 缓解 |
|---|---|---|---|
| R-0-1 | 沙箱不能跑后端测试 | 已知接受 | 测试交真机跑 |
| R-0-2 | 重型依赖（fastembed/qdrant）开发周期成本 | 监控中 | 优先复用现有 AiService |
| R-0-3 | dev 模式 bundle id 与打包版不同 | 已解决 | 用 `.dev` 后缀 request_access |
| R-0-4 | git 沙箱 lock 文件警告 | 已知接受 | commit 实际成功，是 sandbox 清理权限问题 |

---

## checkpoint 节点

- ✅ 已 checkpoint：迭代 0 起步（环境/分支/权限确认）
- ✅ 已 checkpoint：迭代 0 完成（commit `ddf4a8b`）
- 🔄 当前：迭代 1 代码完成、等真机验证（pytest + UI）

---

## 迭代 1 详细记录（2026-05-12）

### 改动文件清单

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `backend/app/services/freshness_decay.py` | **新建** | `compute_time_decay` + `compute_effective_freshness` + `HALF_LIFE_BY_TYPE`（8 档）+ `DecayConfig` |
| `backend/tests/test_freshness_decay.py` | **新建** | 19 个 pytest 用例（含 unit mark） |
| `backend/app/models.py:1082` | 字段添加 | `EvidenceItem.createdAt` + `EvidenceItem.docType`，向后兼容默认 None |
| `backend/app/services/evidence_quality.py` | 重写 freshness 块 | 优先 `compute_time_decay(created_at, doc_type)`；fallback 到 year-regex；默认从 0.2 → `NEUTRAL_WHEN_UNKNOWN`（0.5） |
| `backend/app/services/data_center_search.py:_to_evidence_item` | 字段透传 | 把 dict 里的 createdAt/created_at + docType/doc_type/kind 传给 EvidenceItem |

### 沙箱已验证

- ✅ 5 个文件 `py_compile` 通过
- ✅ `freshness_decay` 模块独立手工断言 6/6 全过（90 天 = 0.5、10 年触底 = 0.05、background 一年 = 0.975、ISO Z 解析、user_pinned = 1.0、effective = 0.45）

### 待真机验证（交给 Claude Code）

详见后文 [Claude Code 任务清单 · 迭代 1](#claude-code-任务清单--迭代-1)。

### 已知缺口（迭代 1 未覆盖、留待后续）

| ID | 缺口 | 影响 | 建议时机 |
|---|---|---|---|
| G-1-1 | `_citation_to_evidence_item` 未传 createdAt | 知识 chunk 引证走 year-regex fallback | 迭代 4 顺手解决（CitationMatch 增加 created_at） |
| G-1-2 | `main.py` 里 8 个 EvidenceItem 构造点未传 createdAt | 向后兼容默认 None，走 fallback | 渐进迁移，无紧迫性 |
| G-1-3 | `memory_foundation.py` 的 20+ 静态 freshness 写入未改 | 这是 intrinsic confidence，保留合理 | 不计划改 |
| G-1-4 | `compute_effective_freshness` 暂未在主重排链路使用 | 框架就绪、调用方择时接入 | 业务方需要时叠加 |

---

## Claude Code 任务清单 · 迭代 1

请在 `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench` 下，分支
`feature/understanding-depth` 上执行：

### 1. Commit 迭代 0 进度文档（之前沙箱锁文件阻塞）

```bash
cd /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench
# 如有 lock 残留：
rm -f .git/index.lock .git/HEAD.lock .git/*.lock 2>/dev/null
git add docs/understanding-depth-progress.md
git status --short
git commit -m "docs(understanding/0): 进度跟踪文档 + 迭代 0 基线建立"
```

### 2. 跑迭代 1 的新测试

```bash
cd backend
uv run pytest tests/test_freshness_decay.py -v --tb=short
```

**期望：** 19 个测试全部通过。如果有失败，请把失败的测试名 + 报错信息回报。

### 3. 跑回归测试（确认现有测试无新红）

```bash
cd backend
uv run pytest tests/ --tb=no -q 2>&1 | tail -10
```

**期望：** 与迭代 0 基线相同的通过数（先跑过基线吗？如果没有，这次的结果就是新基线）。回报 "N passed, M failed in Xs"。

### 4. 如果上面两步都 OK，commit 迭代 1

```bash
git add backend/app/services/freshness_decay.py \
        backend/tests/test_freshness_decay.py \
        backend/app/models.py \
        backend/app/services/evidence_quality.py \
        backend/app/services/data_center_search.py \
        docs/understanding-depth-progress.md
git commit -m "feat(understanding/1): 鲜度真实衰减

- 新增 freshness_decay 模块（指数衰减 + 8 档半衰期）
- EvidenceItem 增加 createdAt/docType 字段（向后兼容）
- evidence_quality 优先用真实 created_at；fallback 保留 year-regex
- data_center_search._to_evidence_item 传 createdAt/docType
- 19 个新测试

已知缺口：_citation_to_evidence_item 待迭代 4 一起解决"
```

### 5. UI 验证（dev 模式应该已经热重载，无需重启）

请进 dev 应用，按以下步骤：

1. 切到"工作台 → 益语智库"客户
2. 在底部输入框问一个会拉到历史资料的问题，例如：
   - "益语智库历史上有过哪些战略调整？"
   - "顾源源过去发表过哪些有代表性的文章？"
3. 等回答出现，**截图**右侧"当前回答引证"面板
4. 把截图回传给 Cowork（你可以直接传图，或者描述引证的排序变化）

**期望：** 引证排序时间感知更强。但因为 `_citation_to_evidence_item`（处理知识 chunk 引证）暂未带 createdAt，纯 chunk 类引证仍走 year-regex fallback——所以 UI 上能看到的差异主要发生在用 `_to_evidence_item` 路径的资料类型上。

**失败标志：** Python 控制台报 `pydantic.ValidationError`、`TypeError`、`ImportError` 等；或 dev 应用启动失败。

### 6. 回报

请按下面格式回报，我（Cowork Claude）会据此决定是否进入迭代 2：

```
- ✅ / ❌ 迭代 0 进度文档已 commit
- 测试: pytest test_freshness_decay 通过 N/19
- 回归: 全量测试结果 (e.g., "152 passed, 3 failed")
- ✅ / ❌ 迭代 1 已 commit（commit hash）
- ✅ / ❌ dev 应用启动正常（无控制台报错）
- UI 引证面板观察：（描述或截图）
- 任何意外问题
```
