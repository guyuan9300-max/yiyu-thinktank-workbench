import test from "node:test";
import assert from "node:assert/strict";

import {
  hasConsultThreadContextDrift,
  freezeConsultThreadContext,
  refreshConsultThreadContext,
  shouldResetConsultThreadContext,
} from "../../.mobile-core-tests/dist/lib/consult-thread-context.js";

test("freezeConsultThreadContext copies the active context into a stable snapshot", () => {
  const snapshot = freezeConsultThreadContext(
    {
      clientId: "client-1",
      clientName: "测试机构A",
      eventLineId: "event-1",
      eventLineName: "捐赠体系升级",
      taskId: "task-1",
      taskTitle: "准备沟通材料",
      taskContext: "当前周重点任务",
      workspaceContext: "客户工作台：本周推进合作收口",
      eventLineContext: "事件线：捐赠体系升级\n下一步：确认预算",
      taskBoardContext: "任务板：共 3 条，未完成 2 条",
      sourceLabels: ["当前客户：测试机构A", "当前事件线：捐赠体系升级", "当前任务：准备沟通材料"],
      missingEventLineHint: null,
    },
    "2026-04-18T10:00:00.000Z",
  );

  assert.equal(snapshot.clientId, "client-1");
  assert.equal(snapshot.eventLineId, "event-1");
  assert.equal(snapshot.taskId, "task-1");
  assert.equal(snapshot.taskTitle, "准备沟通材料");
  assert.equal(snapshot.workspaceContext, "客户工作台：本周推进合作收口");
  assert.match(snapshot.eventLineContext || "", /下一步：确认预算/);
  assert.equal(snapshot.taskBoardContext, "任务板：共 3 条，未完成 2 条");
  assert.deepEqual(snapshot.sourceLabels, ["当前客户：测试机构A", "当前事件线：捐赠体系升级", "当前任务：准备沟通材料"]);
  assert.equal(snapshot.frozenAt, "2026-04-18T10:00:00.000Z");
  assert.equal(snapshot.snapshotVersion, 1);
  assert.equal(snapshot.snapshotHash.startsWith("ctx_"), true);
});

test("refreshConsultThreadContext bumps the snapshot version and detects drift", () => {
  const initial = freezeConsultThreadContext(
    {
      clientId: "client-1",
      clientName: "测试机构A",
      eventLineId: "event-1",
      eventLineName: "捐赠体系升级",
      taskId: "task-1",
      taskTitle: "准备沟通材料",
      taskContext: "当前周重点任务",
      workspaceContext: "客户工作台：本周推进合作收口",
      eventLineContext: "事件线：捐赠体系升级\n下一步：确认预算",
      taskBoardContext: "任务板：共 3 条，未完成 2 条",
      sourceLabels: ["当前客户：测试机构A", "当前事件线：捐赠体系升级", "当前任务：准备沟通材料"],
      missingEventLineHint: null,
    },
    "2026-04-18T10:00:00.000Z",
  );
  const driftedContext = {
    clientId: "client-1",
    clientName: "测试机构A",
    eventLineId: "event-2",
    eventLineName: "筹资链路梳理",
    taskId: "task-2",
    taskTitle: "确认会前问题",
    taskContext: "新的周任务",
    workspaceContext: "客户工作台：下周聚焦渠道沟通",
    eventLineContext: "事件线：筹资链路梳理\n当前卡点：尚未确认合作边界",
    taskBoardContext: "任务板：共 4 条，未完成 3 条",
    sourceLabels: ["当前客户：测试机构A", "当前事件线：筹资链路梳理", "当前任务：确认会前问题"],
    missingEventLineHint: null,
  };

  assert.equal(hasConsultThreadContextDrift(initial, driftedContext), true);

  const refreshed = refreshConsultThreadContext(
    initial,
    driftedContext,
    "2026-04-18T11:00:00.000Z",
  );

  assert.equal(refreshed.snapshotVersion, 2);
  assert.equal(refreshed.eventLineId, "event-2");
  assert.equal(refreshed.taskId, "task-2");
  assert.notEqual(refreshed.snapshotHash, initial.snapshotHash);
});

test("shouldResetConsultThreadContext only resets once a thread already has messages", () => {
  assert.equal(
    shouldResetConsultThreadContext({ hadMessages: false, nextContextChanged: true }),
    false,
  );
  assert.equal(
    shouldResetConsultThreadContext({ hadMessages: true, nextContextChanged: false }),
    false,
  );
  assert.equal(
    shouldResetConsultThreadContext({ hadMessages: true, nextContextChanged: true }),
    true,
  );
});
