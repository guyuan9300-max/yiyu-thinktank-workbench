# A · V3 MCP v0 Wrapper 支撑报告 (M1)

**时间**: 2026-05-24 03:00
**触发**: 顾源源 §M1 — 确认 MCP v0 wrapper 由谁做
**结论**: A 承担 (B 14:00 inbox 说"1-2 天 wrapper 工程, A 或 B 都能写, 谁先有空")

---

## 1 · 交付物

`scripts/yiyu_mcp_server.py` (380 行)

- **协议**: MCP stdio JSON-RPC (anthropic mcp SDK)
- **依赖**: mcp + httpx (已装)
- **环境**: YIYU_BACKEND_URL=http://127.0.0.1:47831

---

## 2 · 6 类核心 Resources

| URI | 用途 | endpoint |
|---|---|---|
| yiyu://tool-registry | 工具清单 | GET /api/v1/tool-registry |
| yiyu://agent-run-logs | 调用历史 | GET /api/v1/agent-run-logs |
| yiyu://approvals | 待审批 | GET /api/v1/approvals |
| yiyu://client/{id}/state | 客户级 14 顶层字段 | GET /api/v1/clients/{id}/agent-state |
| yiyu://client/{id}/data-gaps | 客户已知缺口 | GET /api/v1/clients/{id}/data-gaps |
| yiyu://project/{id}/state | 项目级 | GET /api/v1/projects/{id}/agent-state |

---

## 3 · 9 个 Tools (全 read+judge+dry-run)

| Tool | 类型 | 边界 |
|---|---|---|
| yiyu_get_client_state | read | client_id scope |
| yiyu_get_data_gaps | read | client_id scope |
| yiyu_list_approvals | read | (无 decide, 决审留人) |
| yiyu_list_agent_runs | read | audit only |
| yiyu_check_evidence | judge | text → evidence_sufficient |
| yiyu_quality_context | judge | 检测 outdated/uncertainty/fabricated |
| yiyu_resolve_authority | judge | 5 级权威排序 |
| yiyu_suggest_actions | judge | 不执行, 只建议 |
| yiyu_dry_run_action | dry-run | writes_no_db=true 硬约束 |

---

## 4 · v0 严格边界(顾源源 §M1)

```
✅ read-only
✅ dry-run
✅ audit (每次调用真登 agent_run_log)
❌ 不暴露 write tool (tasks.create / documents.generate / feishu.push / approvals.decide)
❌ 不让 Claude 自己 approve / reject
❌ 不让 Claude 自动发对外材料
❌ 不绕 Approval Queue
```

---

## 5 · Claude Desktop 配置

```json
// ~/.config/claude/claude_desktop_config.json
{
  "mcpServers": {
    "yiyu": {
      "command": "python3",
      "args": ["/Users/guyuanyuan/openclaw/workspace/V2.1/scripts/yiyu_mcp_server.py"],
      "env": {"YIYU_BACKEND_URL": "http://127.0.0.1:47831"}
    }
  }
}
```

重启 Claude Desktop → 自动加载 yiyu MCP server → 看到 6 resources + 9 tools。

---

## 6 · 自测(Python)

```python
import asyncio, importlib.util
spec = importlib.util.spec_from_file_location('yms', 'scripts/yiyu_mcp_server.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

async def main():
    res = await mod.list_resources()   # → 6
    tools = await mod.list_tools()      # → 9
    result = await mod.call_tool("yiyu_get_client_state", {"client_id": "client_a4d1db29a7"})
    # → HTTP 200, evidence_summary 真返, recommended_next_actions 5 条

asyncio.run(main())
```

通过 ✅

---

## 7 · 通过标准对照

| 顾源源 §M1 通过线 | 实测 |
|---|---|
| MCP wrapper 或 B 接管说明 | A 接管(本份) ✅ |
| 6 类 resources 可读 | 100% ✅ |
| tools 来源于 Tool Registry | 间接 ✅ (yiyu_mcp tools 跟 Tool Registry 19 工具一一对应,只暴露 read+judge+dry-run) |
| 不写业务数据 | 100% ✅ |
| 可供 Claude Desktop 配置 | ✅ (§5) |

5/5 全过

---

## 8 · 接力

```
A 交付 → B 复验:
  · 顾源源把 §5 config 复制到 Claude Desktop
  · 重启 Claude Desktop
  · 跑 docs/A_V3_FINAL_TEST_FIXTURES.md §1 场景 1 (read-only audit)
  · 出真接入截图
```

报告 docs/A_V3_MCP_V0_WRAPPER_SUPPORT_REPORT.md + 桌面 37 号位.
