import test from "node:test";
import assert from "node:assert/strict";

import {
  buildConsultContextOptions,
  buildTaskContextSummary,
  resolveConsultContextFromFocus,
} from "../../.mobile-core-tests/dist/lib/consult-context.js";

const tasks = [
  {
    id: "task-a",
    title: "跟进测试机构A会前材料",
    clientId: "client-rita",
    clientName: "测试机构A",
  },
  {
    id: "task-b",
    title: "和元饼吃饭",
    clientId: "client-rita",
    clientName: "测试机构A",
  },
  {
    id: "task-c",
    title: "输出益语智库策略诊断提纲",
    clientId: "client-yiyu",
    clientName: "益语智库",
  },
];

test("buildTaskContextSummary scopes tasks to the selected client", () => {
  assert.equal(
    buildTaskContextSummary(tasks, { clientId: "client-rita" }),
    "任务板：跟进测试机构A会前材料、和元饼吃饭",
  );
});

test("buildTaskContextSummary falls back to all tasks for all context", () => {
  assert.equal(
    buildTaskContextSummary(tasks, { limit: 2 }),
    "任务板：跟进测试机构A会前材料、和元饼吃饭",
  );
});

test("resolveConsultContextFromFocus prefers event line over client", () => {
  const options = buildConsultContextOptions([
    ...tasks,
    {
      id: "task-d",
      title: "测试机构A韶关推进线同步",
      clientId: "client-rita",
      clientName: "测试机构A",
      eventLineId: "event-shaoguan",
      eventLineName: "韶关推进线",
    },
  ]);

  const selected = resolveConsultContextFromFocus(options, {
    clientId: "client-rita",
    clientName: "测试机构A",
    eventLineId: "event-shaoguan",
    eventLineName: "韶关推进线",
    weekAnchorDate: "2026-04-13",
    weekLabel: "2026-W16",
    source: "manual",
    lockMode: "client_event_line",
    boundaryState: "none",
    updatedAt: "2026-04-16T09:00:00.000Z",
  });

  assert.equal(selected.scope, "event_line");
  assert.equal(selected.eventLineId, "event-shaoguan");
});

test("resolveConsultContextFromFocus synthesizes focus-backed context when task board options lag behind", () => {
  const selected = resolveConsultContextFromFocus([
    {
      id: "all",
      label: "全部",
      scope: "all",
      clientId: null,
      clientName: null,
      eventLineId: null,
      eventLineName: null,
    },
  ], {
    clientId: "client-rita",
    clientName: "测试机构A",
    eventLineId: "event-shaoguan",
    eventLineName: "韶关推进线",
    weekAnchorDate: "2026-04-13",
    weekLabel: "2026-W16",
    source: "manual",
    lockMode: "client_event_line",
    boundaryState: "none",
    updatedAt: "2026-04-16T09:00:00.000Z",
  });

  assert.equal(selected.scope, "event_line");
  assert.equal(selected.clientName, "测试机构A");
  assert.equal(selected.eventLineName, "韶关推进线");
});
