import test from "node:test";
import assert from "node:assert/strict";

import {
  hasConsultResponseMetadata,
  normalizeConsultationResponseForMobile,
  stripVisibleContextDiagnostics,
} from "../../.mobile-core-tests/dist/lib/consult-response-core.js";

test("normalizeConsultationResponseForMobile marks legacy reply-only responses as limited context", () => {
  const normalized = normalizeConsultationResponseForMobile(
    { reply: "旧协议回答", model: "legacy" },
    { hasClientName: true, hasTaskBoardContext: true },
  );

  assert.equal(hasConsultResponseMetadata({ reply: "旧协议回答", model: "legacy" }), false);
  assert.equal(normalized.answerMode, "limited_context");
  assert.equal(normalized.contextQuality?.level, "thin");
  assert.deepEqual(normalized.contextQuality?.availableSources, ["client_name", "task_board"]);
  assert.ok(normalized.contextQuality?.missingSources?.includes("workspace"));
  assert.ok(
    normalized.missingContext?.some((entry) => entry.type === "consult_contract"),
    "legacy responses must show that metadata is missing",
  );
});

test("normalizeConsultationResponseForMobile can force limited context when backend capability is degraded", () => {
  const normalized = normalizeConsultationResponseForMobile(
    {
      reply: "服务端回答",
      answerMode: "grounded",
      contextQuality: {
        level: "rich",
        availableSources: ["client_name", "workspace"],
        missingSources: [],
        staleSources: [],
      },
      evidence: [{ id: "workspace-1", type: "workspace", title: "工作台" }],
      missingContext: [],
    },
    {
      hasClientName: true,
      hasWorkspaceContext: true,
      forceLimitedContext: true,
      reason: "当前后端未声明 consult v2 能力。",
    },
  );

  assert.equal(normalized.answerMode, "limited_context");
  assert.equal(normalized.contextQuality?.level, "partial");
  assert.deepEqual(normalized.evidence?.map((entry) => entry.title), ["工作台"]);
  assert.ok(
    normalized.missingContext?.some((entry) => entry.type === "backend_capability"),
    "forced fallback should explain capability degradation",
  );
});

test("stripVisibleContextDiagnostics removes mobile-only context diagnostics from foreground reply", () => {
  const cleaned = stripVisibleContextDiagnostics(
    "上下文质量：较完整\n依据\n• 客户：测试机构A\n阶段目标：Q1三个项目复盘\n下一步：补充经营判断\n真正回复内容",
  );

  assert.equal(cleaned, "真正回复内容");
});

test("normalizeConsultationResponseForMobile strips diagnostics while preserving metadata", () => {
  const normalized = normalizeConsultationResponseForMobile({
    reply: "上下文质量：较完整\nBundle v2\n已可用：客户名、任务板\n缺失：最近会议\n请直接推进任务。",
    answerMode: "grounded",
    contextQuality: {
      level: "rich",
      availableSources: [],
      missingSources: [],
      staleSources: [],
    },
    evidence: [],
    missingContext: [],
  });

  assert.equal(normalized.reply, "请直接推进任务。");
  assert.equal(normalized.answerMode, "grounded");
});
