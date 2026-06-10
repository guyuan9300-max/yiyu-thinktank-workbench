import test from "node:test";
import assert from "node:assert/strict";

import {
  createEmptyCurrentFocus,
  createManualClientEventLineFocus,
  deriveBoundaryState,
  reconcileCurrentFocus,
  restoreCurrentFocus,
  serializeCurrentFocus,
} from "../../.mobile-core-tests/dist/lib/current-focus-core.js";

test("current focus only persists locked client scopes", () => {
  const empty = createEmptyCurrentFocus(new Date(2026, 3, 16, 9, 0, 0));
  assert.equal(serializeCurrentFocus(empty), null);

  const locked = createManualClientEventLineFocus(
    { id: "client-1", name: "测试机构A" },
    { id: "event-1", name: "韶关推进线" },
    empty,
  );
  assert.ok(serializeCurrentFocus(locked));
});

test("browse focus created from task keeps task identity without making it persistable", () => {
  const empty = createEmptyCurrentFocus(new Date(2026, 3, 16, 9, 0, 0));
  const browseFromTask = {
    ...empty,
    clientId: "client-1",
    clientName: "测试机构A",
    eventLineId: "event-1",
    eventLineName: "合作方案推进",
    taskId: "task-1",
    taskTitle: "准备沟通材料",
    source: "from_task",
    lockMode: "browse",
  };
  assert.equal(browseFromTask.taskId, "task-1");
  assert.equal(browseFromTask.taskTitle, "准备沟通材料");
  assert.equal(serializeCurrentFocus(browseFromTask), null);
});

test("restore current focus degrades missing event line to client lock", () => {
  const raw = JSON.stringify({
    clientId: "client-1",
    clientName: "测试机构A",
    eventLineId: "event-gone",
    eventLineName: "旧事件线",
    lockMode: "client_event_line",
    source: "manual",
    weekAnchorDate: "2026-04-13",
  });

  const restored = restoreCurrentFocus(raw, {
    clients: [{ id: "client-1", name: "测试机构A" }],
    eventLines: [],
    now: new Date(2026, 3, 16, 9, 0, 0),
  });

  assert.equal(restored.clientId, "client-1");
  assert.equal(restored.eventLineId, null);
  assert.equal(restored.lockMode, "client");
});

test("reconcile current focus clears missing client entirely", () => {
  const current = {
    clientId: "client-missing",
    clientName: "旧客户",
    eventLineId: null,
    eventLineName: null,
    taskId: "task-1",
    taskTitle: "旧任务",
    weekAnchorDate: "2026-04-13",
    weekLabel: "2026-W16",
    source: "manual",
    lockMode: "client",
    boundaryState: "none",
    updatedAt: "2026-04-16T09:00:00.000Z",
  };

  const next = reconcileCurrentFocus(current, [], []);
  assert.equal(next.clientId, null);
  assert.equal(next.lockMode, "browse");
});

test("reconcile current focus follows an event line when its primary client changes", () => {
  const locked = createManualClientEventLineFocus(
    { id: "client-old", name: "旧客户" },
    { id: "event-1", name: "签约推进线" },
    createEmptyCurrentFocus(new Date(2026, 3, 16, 9, 0, 0)),
  );

  const next = reconcileCurrentFocus(
    locked,
    [
      { id: "client-old", name: "旧客户" },
      { id: "client-new", name: "正式客户" },
    ],
    [
      {
        id: "event-1",
        name: "签约推进线",
        primaryClientId: "client-new",
        primaryClientName: "正式客户",
      },
    ],
  );

  assert.equal(next.clientId, "client-new");
  assert.equal(next.clientName, "正式客户");
  assert.equal(next.eventLineId, "event-1");
  assert.equal(next.lockMode, "client_event_line");
});

test("deriveBoundaryState returns mixed when multiple layers are non-empty", () => {
  const state = deriveBoundaryState([
    { kind: "official", title: "A", summary: "A", sourceType: "manual", updatedAt: null, evidenceCount: 1, isEmpty: false },
    { kind: "risk", title: "B", summary: "B", sourceType: "manual", updatedAt: null, evidenceCount: 1, isEmpty: false },
  ]);
  assert.equal(state, "mixed");
});
