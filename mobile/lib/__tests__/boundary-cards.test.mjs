import test from "node:test";
import assert from "node:assert/strict";

import { buildBoundaryCards } from "../../.mobile-core-tests/dist/lib/boundary-cards.js";

test("buildBoundaryCards renders explicit official empty state when cockpit is not ready", () => {
  const cards = buildBoundaryCards({
    client: { name: "测试机构A" },
    latestOpenQuestions: [{ title: "还缺合作预算口径" }],
    latestConflicts: [{ title: "项目负责人尚未确认" }],
  }, {
    officialLayerStatus: "draft",
    pendingDecisions: [{ title: "是否先做试点" }],
    pendingMaterials: [{ title: "等待会议纪要" }],
    health: [{ summary: "推进速度偏慢" }],
    updatedAt: "2026-04-16T09:00:00.000Z",
  });

  assert.equal(cards[0].kind, "official");
  assert.equal(cards[0].title, "当前暂无已批准判断");
  assert.equal(cards[0].isEmpty, true);
  assert.equal(cards[1].summary, "是否先做试点");
  assert.match(cards[2].summary, /推进速度偏慢/);
  assert.match(cards[3].summary, /还缺合作预算口径/);
});
