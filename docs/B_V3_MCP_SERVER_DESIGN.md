# B V3 · MCP Server v0 设计 · 外部体检官 (顾源源 5/23 钦定)

> **触发**: 顾源源 5/23 21:30 收窄目标 — 不做 Claude CEO, 先做 Claude 软件体检官
> **v0 边界**: **read-only + dry-run + audit**, 不写 db / 不自动 approve / 不绕过审批
> **目标客户端**: Claude Desktop / Cursor / Cline / Continue (主流 MCP 客户端)
> **冻结**: 2026-05-23 V1
> **B 角色**: 设计 + 模拟版实现; A 角色: 真版 MCP server 实现 (估 3-5 天)

---

## 1 · v0 北极星

```
让 Claude / Codex 通过 MCP 协议接入益语智库, 实现:
  · 读取客户状态 / 工具清单 / 数据缺口 / 运行日志 / 审批队列
  · 对 14 功能进行可追溯的软件体检
  · 输出可人工复核的诊断报告

不要求 v0 做:
  ❌ 自动运营公司
  ❌ 自动跨客户排优先级
  ❌ 自动返工材料
  ❌ 自动决定战略
  ❌ 自动 approve / reject 审批
  ❌ 自动发对外材料
```

通过线 (第 1 轮): 60% 有效判断率. 第 3-5 轮校准后 80-85%.

---

## 2 · MCP server 整体架构

```
┌─────────────────────────┐
│ Claude Desktop / Cursor │  ← MCP client (LLM)
└────────────┬────────────┘
             │ stdio / SSE (MCP protocol)
             ↓
┌─────────────────────────┐
│ yiyu MCP server (Python)│  ← B 设计, A 实现 + 部署
│  - tools (14 个)         │
│  - resources (6 个)      │
│  - prompts (3 个 audit)  │
└────────────┬────────────┘
             │ httpx (HTTP)
             ↓
┌─────────────────────────┐
│ V2.1 backend port 47831 │  ← 现有 FastAPI
└─────────────────────────┘
```

**关键**: MCP server 是 V2.1 backend 的**只读 wrapper**, 不绕过 backend 直接读 db. 这样 A 暴露的所有 endpoint 自动可被 MCP 调用.

---

## 3 · v0 暴露的 14 个 Tools

### 3.1 客户状态 / 工具清单 / 缺口 / 日志 / 审批 (6 个只读 query tools)

| Tool | 含义 | 内部 endpoint | 风险 |
|---|---|---|---|
| `yiyu.list_clients` | 列所有客户 | `GET /api/v1/clients` | low |
| `yiyu.get_client_state` | 获取客户完整状态 (聚合) | `GET /api/v1/clients/{id}/agent-state` ★ **A 待暴露** | low |
| `yiyu.list_tools` | 列 Tool Registry | `GET /api/v1/tool-registry` ★ **A 待暴露** | low |
| `yiyu.list_data_gaps` | 列客户当前缺什么证据 | `GET /api/v1/clients/{id}/data-gaps` ★ **A 待暴露 (V3.0 P0a)** | low |
| `yiyu.list_agent_runs` | 列 AI 调用历史 | `GET /api/v1/agent-run-logs` ★ **A 待暴露** | low |
| `yiyu.list_approvals` | 列待审批 (pending) | `GET /api/v1/approvals` ✅ 已通 | low |

→ **3 个 ★ A 必暴露**: `agent-state` / `tool-registry` / `data-gaps`. 这 3 个是 v0 的灵魂.

### 3.2 功能调用查询 (4 个 read-only 业务 tool)

| Tool | 含义 | 内部 endpoint | 风险 |
|---|---|---|---|
| `yiyu.query_workspace_chat` | 查工作台问答历史 + evidence | `GET /api/v1/clients/{id}/workspace/chat/messages` | low |
| `yiyu.query_file_identities` | 查文件身份 | sqlite3 read-only on V2.1 lab db (临时, A 后续暴露 endpoint) | low |
| `yiyu.query_contract_structures` | 查合同结构 | 同上 | low |
| `yiyu.query_historical_links` | 查历史回指关系 | 同上 | low |

### 3.3 审计型 tools (4 个) — 让 Claude 帮我们检查

| Tool | 含义 | 内部实现 | 风险 |
|---|---|---|---|
| `yiyu.audit_single_file_only` | 扫工作台问答, 找出 single_file_only=true 的 | 跑 GET /workspace/chat/messages + filter | low |
| `yiyu.audit_evidence_completeness` | 看回答是否引用了 ≥ 3 类 evidence | 跑 + filter response.evidenceTypes | low |
| `yiyu.audit_endpoint_coverage` | 跑所有 endpoint smoke, 找哪些 404/403/422 | 复用 B 的 `probe_tool_registry.py` 逻辑 | low |
| `yiyu.audit_hardcoding_smell` | 读 backend/app/services + main.py + prompts, 扫红线 5 条 | grep + 简单规则 | low |

### 3.4 dry-run write tools (0 个 v0 不暴露)

```
v0 不暴露任何 write tool.
v1 (项目助理阶段) 才暴露 dry-run write:
  - documents.draft (dry-run mode)
  - tasks.create_draft (dry-run mode)
  - approvals.propose (不真创建)
```

**v0 边界**: 即使是 dry-run write 也不要. Claude 只读, 帮我们看清现状.

---

## 4 · v0 暴露的 6 个 Resources

Resources 是 MCP 的"数据快照", Claude 可以 `read_resource(uri)` 拿到.

| Resource URI | 含义 | 内容 |
|---|---|---|
| `yiyu://clients/{id}/state` | 客户聚合状态 | 调 `yiyu.get_client_state`, 返回 markdown 格式 (LLM 友好) |
| `yiyu://tool-registry` | Tool Registry 全量 | 调 `yiyu.list_tools`, 返回 markdown 表格 |
| `yiyu://clients/{id}/data-gaps` | 客户当前缺口 | 调 `yiyu.list_data_gaps`, 返回结构化 list |
| `yiyu://agent-run-logs?limit=50` | 最近 AI 调用 | 50 条 run log markdown |
| `yiyu://approvals?status=pending` | 当前待审批 | pending list |
| `yiyu://schema/db_business_meaning` | V2.1 lab db 16 表业务含义 | 静态 markdown 文件 (B 写) ★ **新需 B 维护** |

→ 最后一个 (`db_business_meaning`) 是关键: **让 Claude 知道 atomic_facts 跟 commitments 关系**, 不靠猜.

---

## 5 · v0 暴露的 3 个审计型 Prompts

Prompts 是 MCP 客户端 (Claude Desktop) 注册的 slash command. 用户可以在 Claude Desktop 输入 `/yiyu_audit_single_file` 触发.

### 5.1 `/yiyu_audit_single_file`

```
请通过 yiyu MCP server 帮我做一次 single_file_only 风险扫描:

1. 调用 yiyu.list_clients 拿到所有客户
2. 对每个客户调用 yiyu.query_workspace_chat (取最近 20 条)
3. 统计 response.singleFileOnly = true 的比例
4. 输出:
   - 哪些客户工作台问答仍 single_file_only > 10%
   - 哪些问题类型最容易 single_file_only
   - 修复建议
```

### 5.2 `/yiyu_audit_evidence_completeness`

```
请通过 yiyu MCP server 检查工作台问答的 evidence 完整度:

1. 调用 yiyu.list_clients
2. 对每个客户, 用 yiyu.query_workspace_chat 取 10 条
3. 统计每条回答的 evidenceTypes (合同 / 会议 / 复盘 / 风险 / ...)
4. 输出:
   - 评分 (满分 100): 平均 evidenceTypes 数 × 引用源数 × (1 - single_file_only 率)
   - 低分回答列表 (evidence < 3 类)
   - 修复建议: 哪些 endpoint 该接 build_company_brain_context
```

### 5.3 `/yiyu_audit_hardcoding_smell`

```
请通过 yiyu MCP server + 文件读取 (filesystem MCP) 扫硬编码风险:

1. 读 backend/app/main.py 找所有 system prompt
2. 扫 prompt 是否包含 "必须第一步 / 第二步 / 第三步 / 如果 X 必须 Y"
3. 读 backend/app/services/*.py 找 if-else 业务分支
4. 输出:
   - hardcoding_smell list (line number + risk level + 修复建议)
   - 违反《开放架构红线》第几条
```

→ 这 3 个 prompt 跑完 = Claude 帮我们做了第 1 轮"软件体检".

---

## 6 · v0 实现技术栈

```
MCP server 框架:
  - Python (anthropic-mcp SDK, 官方支持)
  - 或 TypeScript (@modelcontextprotocol/sdk)

B 推荐: Python (跟 V2.1 backend 同栈, A 容易接)

依赖:
  - mcp (Python anthropic-mcp SDK)
  - httpx (调 V2.1 backend port 47831)
  - sqlite3 (临时直读 V2.1 lab db, A 后续暴露 endpoint 替换)
  - pydantic (schema)
```

部署:
```
# Mac 本地直跑:
python -m yiyu_mcp_server

# Claude Desktop 配置 (~/Library/Application Support/Claude/claude_desktop_config.json):
{
  "mcpServers": {
    "yiyu": {
      "command": "python",
      "args": ["-m", "yiyu_mcp_server"],
      "env": {
        "YIYU_BACKEND_URL": "http://localhost:47831",
        "YIYU_DB_PATH": "/Users/guyuanyuan/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db"
      }
    }
  }
}
```

---

## 7 · v0 文件结构 (A 实现 reference)

```
yiyu_mcp_server/
├── __init__.py
├── __main__.py              # 入口 (python -m yiyu_mcp_server)
├── server.py                # MCP server 主框架
├── config.py                # env 配置
├── tools/
│   ├── __init__.py
│   ├── client_state.py      # yiyu.get_client_state
│   ├── tool_registry.py     # yiyu.list_tools
│   ├── data_gaps.py         # yiyu.list_data_gaps
│   ├── agent_runs.py        # yiyu.list_agent_runs
│   ├── approvals.py         # yiyu.list_approvals
│   ├── workspace_chat.py    # yiyu.query_workspace_chat
│   ├── file_identities.py   # yiyu.query_file_identities (sqlite3 临时)
│   ├── contract_structures.py
│   ├── historical_links.py
│   ├── audit_single_file.py
│   ├── audit_evidence.py
│   ├── audit_endpoint.py
│   └── audit_hardcoding.py
├── resources/
│   ├── client_state.py
│   ├── tool_registry.py
│   ├── data_gaps.py
│   ├── agent_run_logs.py
│   ├── approvals.py
│   └── db_business_meaning.py  # 静态 markdown 资源
├── prompts/
│   ├── audit_single_file.py
│   ├── audit_evidence.py
│   └── audit_hardcoding.py
└── utils/
    ├── http_client.py       # httpx wrapper
    └── sqlite_reader.py     # 临时只读 V2.1 lab db
```

---

## 8 · v0 输出: Markdown 体检报告格式

Claude Desktop 跑完 3 个 audit prompt 后, 应该输出:

```markdown
# 益语智库体检报告 v0.1 (Claude 生成, 待 B/顾源源复核)

> 生成: <iso>
> MCP server commit: <hash>
> 客户端: Claude Desktop / Cursor

## 1 · 客户状态摘要
- 总客户 12 个
- 有活动 (近 7 天) 客户 3 个 (CFFC / 日慈 / 益语智库)
- 平均 atomic_facts: XX / 客户
- 平均 待澄清: XX
- 平均 待审批: XX

## 2 · single_file_only 风险扫描
- 高风险客户: [X, Y]
- 高风险问题类型: "查合同" / "查历史" 类
- 修复建议: workspace.chat 接 build_company_brain_context 时...

## 3 · evidence 完整度
- 平均 evidenceTypes: 4.2 / 5
- 低分回答: 12% (引用 ≤ 2 类)
- ...

## 4 · hardcoding smell
- backend/app/services/narrative_generator.py:L120 — system prompt 含 "必须第一步" → 违反红线规则 2
- backend/app/main.py:L38099 — endpoint 写死 client_id 验证 → 违反红线规则 3
- ...

## 5 · endpoint 覆盖
- 总 endpoint 50+
- 描述够 LLM 理解的: 20%
- 缺 description: 80%
- 缺 example: 90%

## 6 · 综合判断
- 当前 V2.1 RC 状态: ⚠️ 部分通过 (R2 ✅, R4-P1 自评 97 待 B 复验, V3.0 真测 66.5)
- 距离 V3.0 真过 (≥80): 缺 5 endpoint + 1 个 plan_cache + 3 个红线整改
- 建议优先级: ...
```

---

## 9 · v0 验收标准 (第 1 轮)

| 指标 | 目标 | 备注 |
|---|---|---|
| Claude Desktop 连 MCP server | 100% | 配置正确, 出错率 < 5% |
| 读 Tool Registry | 100% | 14 tools 全列出 |
| 读至少 3 客户状态 | ≥ 3 | CFFC / 日慈 / 明远 fallback |
| 跑 14 功能体检 | ≥ 10 / 14 | 至少 10 功能能体检完成 |
| 每个判断带证据 | ≥ 80% | endpoint 来源 / db row 来源 |
| single_file_only 风险标 | ≥ 5 候选 | |
| endpoint description 不清标 | ≥ 5 候选 | |
| hardcoding risk 标 | ≥ 3 候选 | |
| 人工复核后有效判断比例 | ≥ 60% (第 1 轮) | 第 3 轮目标 80% |
| 不能越权写 db | 100% | v0 read-only |

---

## 10 · A 实现时间估 (B 给参考)

```
Day 1 (8h):
  - Python anthropic-mcp SDK 学 (2h)
  - server.py 框架 + 3 个 only-read tool (client_state, tool_registry, approvals) (4h)
  - Claude Desktop config 测试连通 (2h)

Day 2 (8h):
  - 剩 11 tools 实现 (audit / query 类) (6h)
  - 6 resources 实现 (2h)

Day 3 (8h):
  - 3 audit prompts 实现 (3h)
  - db_business_meaning.md 静态资源写 (B 写, A 集成) (1h)
  - 单元测试 + Claude Desktop 实测 (4h)

Day 4 (8h):
  - Bug 修 + 边界 case
  - 部署文档 + README

Day 5 (4h):
  - 顾源源 + B 联合测试
  - 修 Day 5 反馈
```

→ **A 真做 3-5 天**. 不是 1-2 天. 不是 1-2 周.

---

## 11 · B 同步做的事 (不阻塞 A)

```
Day 1-2: B 写
  - 本文档 (设计) ✅
  - scripts/yiyu_mcp_server_simulator.py (模拟版, B 自测流程)
  - docs/B_V3_DB_BUSINESS_MEANING.md (db 16 表业务含义, 喂给 Claude)
  - docs/B_V3_ENDPOINT_DESCRIPTION_REVIEW.md (扫现有 50 endpoint, 给 A 补 description)
  - fixtures/golden_labeled/_GT_TEMPLATE.md (ground truth 模板)

Day 3-5: A 写 MCP server 期间, B 跑模拟版收集数据:
  - 跑 audit_single_file / audit_evidence / audit_hardcoding 的预期输出
  - 给 A 参考
  - 给顾源源参考 (你不用等 A 就可以看模拟体检结果)

Day 5+: A 真版交付后:
  - B 用 Claude Desktop 连真版, 跑 audit
  - 跟模拟版对比, 找差距
  - 出 docs/B_V3_M4_MCP_AUDIT_REPORT.md (第 1 轮体检报告)
  - 顾源源人工复核 → B 标对/错/漏 → A 修 endpoint description → 第 2 轮跑
```

---

## 12 · v0 不做的事 (再次重申, 防 scope creep)

```
v0 红线 (不允许):
  ❌ 写 db (任何表)
  ❌ 调用 POST endpoint 真生成业务数据
  ❌ 自动 approve / reject
  ❌ 自动发对外材料
  ❌ 跨客户读取 (Claude 必须明确说"我要读客户 X 的数据")
  ❌ 替顾源源做决策 (只输出报告, 顾源源拍板)
  ❌ CEO 模式 (每天自主调度)
  ❌ Plan Cache (M5, 等 v0 跑通看数据再设计)
  ❌ 长期组织记忆 (V3.0 P3, 等 v0 + v1 后)

v0 只做:
  ✅ 读 (client_state / tool_registry / data_gaps / agent_runs / approvals)
  ✅ 审计 (single_file / evidence / hardcoding / endpoint coverage)
  ✅ 报告 (markdown 输出, 顾源源复核)
```

---

## 13 · 路线图 (v0 → v1 → v2 → CEO)

```
v0 (本设计, 7-10 天 + 校准 3-5 轮 = 4-6 周): 外部体检官
  Claude 读 + 审计 + 报告. 不写.

v1 (4-6 周后, 1 个月): 项目助理
  Claude 能 dry-run 生成草稿 (合同 / 任务 / 提纲)
  危险动作进 Approval Queue
  + plan_cache 学习

v2 (3-6 月后): 项目经理
  Claude 能 daily brief
  跨任务排优先级
  + L5 质量评估器
  + L6 返工循环

v3 (6-12 月后): CEO
  Claude 每天自主决策
  长期组织记忆
  跨客户排优先级
  + V3.0 P3 全套
```

→ **不要急着冲 CEO**. 每一层稳了再上一层.

---

**Author**: AI B · 2026-05-23 21:35
**冻结**: V1
**关联**:
- 顾源源 5/23 21:30 收窄目标到"外部体检官"
- `docs/B_V3_OPEN_ARCHITECTURE_REDLINE.md` (架构红线, 本设计严格遵守)
- `docs/B_V3_M1_TOOL_REGISTRY_V1.md` (M1 11 工具是本设计 14 tools 的前置)
- `scripts/yiyu_agent_cli.py` (B 本地模拟版, 跟 MCP server 同思想)
- A 实现 issue (B 待开 inbox-A): 3-5 天工程, 不急
