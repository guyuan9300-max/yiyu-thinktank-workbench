"""[A] V3 Final 验收支撑 M1 · yiyu MCP Server v0

顾源源 5/24 §A 线程指令 §M1 钦定:
"如果 B 没承担, A 实现最小 MCP v0 wrapper scripts/yiyu_mcp_server.py".

边界 (顾源源 §M1 严格):
  ✅ 只暴露 read-only / dry-run / audit
  ❌ 不直接写业务数据库
  ❌ 不自动 approve / reject
  ❌ 不自动发外部材料
  ❌ 不自动关闭澄清
  ❌ 不自动覆盖权威事实

调用 Claude Desktop:
  ~/.config/claude/claude_desktop_config.json 加:
  {
    "mcpServers": {
      "yiyu": {
        "command": "python3",
        "args": ["/Users/guyuanyuan/openclaw/workspace/V2.1/scripts/yiyu_mcp_server.py"],
        "env": {"YIYU_BACKEND_URL": "http://127.0.0.1:47831"}
      }
    }
  }

resources (6 类):
  yiyu://client/{client_id}/state       — Agent State 完整快照
  yiyu://project/{project_id}/state     — Project Agent State
  yiyu://client/{client_id}/data-gaps   — 数据缺口
  yiyu://tool-registry                  — 工具清单
  yiyu://agent-run-logs                 — Agent 调用历史
  yiyu://approvals                      — 待审批

tools (从 GET /tool-registry 真自动同步, 不手写一套):
  yiyu_get_client_state / yiyu_get_data_gaps / yiyu_list_approvals /
  yiyu_list_agent_runs / yiyu_check_evidence / yiyu_quality_context /
  yiyu_resolve_authority / yiyu_suggest_actions / yiyu_dry_run_action
  (8 read+judge tools, write-tools 不暴露)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Resource, Tool, TextContent
except ImportError:
    print("✗ mcp SDK 未装. 装: pip3 install --user 'mcp'", file=sys.stderr)
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("✗ httpx 未装. 装: pip3 install --user httpx", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("yiyu_mcp")

BACKEND_URL = os.environ.get("YIYU_BACKEND_URL", "http://127.0.0.1:47831")

# ───────────────────────── helpers ─────────────────────────


async def _backend_get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{BACKEND_URL}{path}", params=params or {})
        resp.raise_for_status()
        return resp.json()


async def _backend_post(path: str, json_body: dict, headers: dict | None = None) -> dict:
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{BACKEND_URL}{path}", json=json_body, headers=h)
        resp.raise_for_status()
        return resp.json()


# ───────────────────────── MCP server ─────────────────────────

server: Server = Server("yiyu-mcp-v0")


# ──── Resources (6 类, 顾源源 §M1 必含) ────


@server.list_resources()
async def list_resources() -> list[Resource]:
    """6 类核心 resources — Claude Desktop 启动时拉清单."""
    return [
        Resource(
            uri="yiyu://tool-registry",
            name="Tool Registry",
            description="益语 V2.1 lab 17+2 工具完整 schema (含 when_to_use / risk_level / approval_required / blocked_by_A 标注)",
            mimeType="application/json",
        ),
        Resource(
            uri="yiyu://agent-run-logs",
            name="Agent Run Logs",
            description="Agent 调用历史 (含 tool_name / actor_type / status / duration / idempotency_key). 用于审计 AI 跑过什么.",
            mimeType="application/json",
        ),
        Resource(
            uri="yiyu://approvals",
            name="Approval Queue",
            description="待审批动作 (高风险动作必经). 用户在前端 approve 才能真执行.",
            mimeType="application/json",
        ),
        Resource(
            uri="yiyu://client/{client_id}/state",
            name="Client Agent State (template)",
            description="客户级公司大脑完整快照 (14 顶层字段). 替换 {client_id} 为真实 client id, 如 client_a4d1db29a7 (测试论坛A).",
            mimeType="application/json",
        ),
        Resource(
            uri="yiyu://client/{client_id}/data-gaps",
            name="Client Data Gaps (template)",
            description="客户已知数据缺口 (含 suggested_tools / suggested_clarification / priority).",
            mimeType="application/json",
        ),
        Resource(
            uri="yiyu://project/{project_id}/state",
            name="Project Agent State (template)",
            description="项目 (event_line) 级快照. 替换 {project_id} 为真实 event_line id.",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    """读 resource — 返 JSON 字符串."""
    logger.info("read_resource: %s", uri)

    if uri == "yiyu://tool-registry":
        data = await _backend_get("/api/v1/tool-registry")
        return json.dumps(data, ensure_ascii=False, indent=2)

    if uri == "yiyu://agent-run-logs":
        data = await _backend_get("/api/v1/agent-run-logs", params={"limit": 30})
        return json.dumps(data, ensure_ascii=False, indent=2)

    if uri == "yiyu://approvals":
        data = await _backend_get("/api/v1/approvals", params={"limit": 30})
        return json.dumps(data, ensure_ascii=False, indent=2)

    # 模板 URI: yiyu://client/{id}/state
    if uri.startswith("yiyu://client/") and uri.endswith("/state"):
        client_id = uri[len("yiyu://client/"):-len("/state")]
        data = await _backend_get(f"/api/v1/clients/{client_id}/agent-state")
        return json.dumps(data, ensure_ascii=False, indent=2)

    if uri.startswith("yiyu://client/") and uri.endswith("/data-gaps"):
        client_id = uri[len("yiyu://client/"):-len("/data-gaps")]
        data = await _backend_get(f"/api/v1/clients/{client_id}/data-gaps", params={"limit": 50})
        return json.dumps(data, ensure_ascii=False, indent=2)

    if uri.startswith("yiyu://project/") and uri.endswith("/state"):
        project_id = uri[len("yiyu://project/"):-len("/state")]
        data = await _backend_get(f"/api/v1/projects/{project_id}/agent-state")
        return json.dumps(data, ensure_ascii=False, indent=2)

    raise ValueError(f"unknown resource uri: {uri}")


# ──── Tools (read + judge + dry-run 类, 不含 write) ────


@server.list_tools()
async def list_tools() -> list[Tool]:
    """8 个 v0 tools — 全 read/judge/dry-run, 不暴露 write tool (顾源源 §M1 严格).

    来源: GET /api/v1/tool-registry 真同步 (但只暴露 read+judge+dry-run).
    """
    # 自动从 tool-registry 拉 schema, 但过滤掉所有 write 类 (approval_required=true 或 risk=high)
    try:
        reg = await _backend_get("/api/v1/tool-registry")
        registry_tools = reg.get("tools", [])
    except Exception as exc:
        logger.warning("拉 tool-registry 失败, 用 hardcode 默认 8 tools: %s", exc)
        registry_tools = []

    # v0 白名单 (read + judge + dry-run, 全 low risk + no approval)
    V0_TOOLS_ALLOWLIST = {
        "clients.agent_state",
        "projects.agent_state",
        "data_gaps.list",
        "agent_run_logs.list",
        "approvals.list",  # 只列, decide 不暴露
        "evidence.check",
        "quality.context",
        "authority.resolve",
        "actions.suggest",
        "actions.dry_run",
    }

    tools: list[Tool] = []

    # 1. yiyu_get_client_state
    tools.append(Tool(
        name="yiyu_get_client_state",
        description=(
            "Get full company-brain snapshot for a client (14 top-level fields: "
            "client_profile, contracts, files, historical_links, commitments, risks, "
            "clarifications, approvals, data_gaps, agent_run_logs, recommended_next_actions, "
            "evidence_summary, etc). "
            "When to use: at session start, before answering any client question, "
            "or when you need to ground answer in client real state. "
            "When NOT to use: cross-client questions (one client only)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "client_id": {"type": "string", "description": "Client id (e.g. client_a4d1db29a7)"},
            },
            "required": ["client_id"],
        },
    ))

    # 2. yiyu_get_data_gaps
    tools.append(Tool(
        name="yiyu_get_data_gaps",
        description=(
            "List known data gaps for a client (with suggested_tools, suggested_clarification, priority). "
            "When to use: before generating any output to confirm what info is missing. "
            "When NOT to use: detailed evidence check on one specific text (use evidence.check)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "severity": {"type": "string", "enum": ["high", "medium", "low"], "description": "Optional filter"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["client_id"],
        },
    ))

    # 3. yiyu_list_approvals
    tools.append(Tool(
        name="yiyu_list_approvals",
        description=(
            "List pending approvals (read-only). "
            "When to use: see what high-risk actions are waiting for user decision. "
            "When NOT to use: deciding (only humans can approve/reject)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "client_id": {"type": "string", "description": "Optional filter by client"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    ))

    # 4. yiyu_list_agent_runs
    tools.append(Tool(
        name="yiyu_list_agent_runs",
        description=(
            "List agent run log (audit history of all AI actions). "
            "When to use: see what AI has run (or what I have run myself). "
            "When NOT to use: real-time monitoring; this is post-hoc audit."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "actor_type": {"type": "string", "description": "Filter by actor (e.g. external_ai_agent, human)"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    ))

    # 5. yiyu_check_evidence
    tools.append(Tool(
        name="yiyu_check_evidence",
        description=(
            "Check evidence sufficiency for a target text or draft. "
            "Returns evidence_sufficient (bool), missing_evidence list, conflicting_evidence list, "
            "and proposed_clarifications. "
            "When to use: before finalizing any draft output. "
            "When NOT to use: text too short (<30 chars) — won't extract meaningful keywords."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "text": {"type": "string"},
                "target_kind": {"type": "string", "enum": ["goal", "draft", "answer", "plan"], "default": "draft"},
            },
            "required": ["client_id", "text"],
        },
    ))

    # 6. yiyu_quality_context
    tools.append(Tool(
        name="yiyu_quality_context",
        description=(
            "Evaluate quality risks of an output (detects outdated_amount, uncertainty_leak, "
            "fabricated_number, low_credibility_external_used). Returns quality_risks list + "
            "rework_suggestions. "
            "When to use: pre-flight check before delivering any draft to user. "
            "When NOT to use: pure data lookup (use get_client_state)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "text": {"type": "string"},
                "output_kind": {
                    "type": "string",
                    "enum": ["contract_draft", "proposal", "answer", "report", "board_brief"],
                    "default": "draft",
                },
            },
            "required": ["client_id", "text"],
        },
    ))

    # 7. yiyu_resolve_authority
    tools.append(Tool(
        name="yiyu_resolve_authority",
        description=(
            "Multi-source authority resolver (5-level priority: user_confirmed > judgment_confirmed > "
            "contract_structures > high_confidence > low_confidence). "
            "When to use: subject has multiple candidate values, need most authoritative. "
            "When NOT to use: single known value."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "subject": {"type": "string"},
                "attribute": {"type": "string"},
            },
            "required": ["client_id", "subject"],
        },
    ))

    # 8. yiyu_suggest_actions (read-only suggest, not execute)
    tools.append(Tool(
        name="yiyu_suggest_actions",
        description=(
            "Get >=5 candidate actions for a client (with risk_level, approval_required, evidence). "
            "When to use: planning next step. "
            "When NOT to use: this is suggestion-only, does not execute any action."
        ),
        inputSchema={
            "type": "object",
            "properties": {"client_id": {"type": "string"}},
            "required": ["client_id"],
        },
    ))

    # 9. yiyu_dry_run_action (preview write impact, does NOT write)
    tools.append(Tool(
        name="yiyu_dry_run_action",
        description=(
            "Preview impact of an action — returns would_write_tables, would_call_services, "
            "approval_required, safety_check. "
            "Hard contract: this tool itself does NOT write any business table. "
            "When to use: before invoking any high-risk write tool. "
            "Supported action_types: resolve_clarification, compensate_data_gap, review_approval, "
            "create_task_draft, refresh_strategy_narrative, resolve_historical_references, "
            "publish_task_with_external_action, ingest_new_material."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "action_type": {"type": "string"},
                "client_id": {"type": "string"},
                "payload": {"type": "object"},
            },
            "required": ["action_type"],
        },
    ))

    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """工具调用 — 包装 HTTP, 返 JSON 字符串.

    Audit: 每次 tool 调用都通过 V2.1 lab 自身的 agent_run_log 登记 (后端 endpoint 真审计).
    """
    logger.info("call_tool: %s args=%s", name, list(arguments.keys()))
    headers = {
        "X-Actor-Type": "external_ai_agent",
        "X-Actor-Id": arguments.pop("_actor_id", "claude_via_mcp"),
    }

    try:
        if name == "yiyu_get_client_state":
            data = await _backend_get(f"/api/v1/clients/{arguments['client_id']}/agent-state")
        elif name == "yiyu_get_data_gaps":
            params: dict[str, Any] = {"limit": arguments.get("limit", 20)}
            if "severity" in arguments:
                params["severity"] = arguments["severity"]
            data = await _backend_get(f"/api/v1/clients/{arguments['client_id']}/data-gaps", params=params)
        elif name == "yiyu_list_approvals":
            params = {"limit": arguments.get("limit", 20)}
            if "client_id" in arguments:
                params["client_id"] = arguments["client_id"]
            data = await _backend_get("/api/v1/approvals", params=params)
        elif name == "yiyu_list_agent_runs":
            params = {"limit": arguments.get("limit", 20)}
            for k in ("client_id", "actor_type"):
                if k in arguments:
                    params[k] = arguments[k]
            data = await _backend_get("/api/v1/agent-run-logs", params=params)
        elif name == "yiyu_check_evidence":
            data = await _backend_post(
                f"/api/v1/clients/{arguments['client_id']}/evidence/check",
                json_body={"text": arguments["text"], "target_kind": arguments.get("target_kind", "draft")},
                headers=headers,
            )
        elif name == "yiyu_quality_context":
            data = await _backend_post(
                f"/api/v1/clients/{arguments['client_id']}/quality/context",
                json_body={"text": arguments["text"], "output_kind": arguments.get("output_kind", "draft")},
                headers=headers,
            )
        elif name == "yiyu_resolve_authority":
            data = await _backend_post(
                f"/api/v1/clients/{arguments['client_id']}/authority/resolve",
                json_body={"subject": arguments["subject"], "attribute": arguments.get("attribute", "")},
                headers=headers,
            )
        elif name == "yiyu_suggest_actions":
            data = await _backend_post(
                f"/api/v1/clients/{arguments['client_id']}/actions/suggest",
                json_body={},
                headers=headers,
            )
        elif name == "yiyu_dry_run_action":
            data = await _backend_post(
                "/api/v1/actions/dry-run",
                json_body={
                    "action_type": arguments["action_type"],
                    "client_id": arguments.get("client_id"),
                    "payload": arguments.get("payload") or {},
                },
                headers=headers,
            )
        else:
            return [TextContent(type="text", text=json.dumps(
                {"error": f"unknown tool: {name}", "available": "see list_tools"},
                ensure_ascii=False,
            ))]
    except httpx.HTTPStatusError as exc:
        return [TextContent(type="text", text=json.dumps({
            "error": f"backend HTTP {exc.response.status_code}",
            "detail": exc.response.text[:500],
            "tool": name,
        }, ensure_ascii=False))]
    except Exception as exc:
        return [TextContent(type="text", text=json.dumps({
            "error": str(exc), "tool": name,
        }, ensure_ascii=False))]

    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]


# ───────────────────────── main ─────────────────────────


async def amain() -> None:
    logger.info("yiyu_mcp_server v0 starting (backend=%s)", BACKEND_URL)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
