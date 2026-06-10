import test from "node:test";
import assert from "node:assert/strict";

import {
  shouldSkipCloudTaskSweep,
  shouldWarnLargeSweep,
} from "../../.mobile-core-tests/dist/lib/cloud-sweep-policy.js";

test("shouldSkipCloudTaskSweep: 本地有任务、云端返回 0 条 → 跳过删除(防清空)", () => {
  assert.equal(shouldSkipCloudTaskSweep(5, 0), true);
  assert.equal(shouldSkipCloudTaskSweep(1, 0), true);
});

test("shouldSkipCloudTaskSweep: 本地为空时云端 0 条是正常的 → 不跳过", () => {
  assert.equal(shouldSkipCloudTaskSweep(0, 0), false);
});

test("shouldSkipCloudTaskSweep: 云端有返回 → 不跳过(正常 sweep)", () => {
  assert.equal(shouldSkipCloudTaskSweep(5, 3), false);
  assert.equal(shouldSkipCloudTaskSweep(5, 5), false);
  assert.equal(shouldSkipCloudTaskSweep(0, 3), false);
});

test("shouldWarnLargeSweep: 删除占比高且超过 5 条 → 告警", () => {
  assert.equal(shouldWarnLargeSweep(6, 10), true); // 6 > 5 且 6 >= 10×0.5
  assert.equal(shouldWarnLargeSweep(10, 10), true);
  assert.equal(shouldWarnLargeSweep(50, 100), true);
});

test("shouldWarnLargeSweep: 删除量小(≤5 条)→ 不告警(避免噪音)", () => {
  assert.equal(shouldWarnLargeSweep(5, 10), false);
  assert.equal(shouldWarnLargeSweep(3, 4), false);
  assert.equal(shouldWarnLargeSweep(0, 10), false);
});

test("shouldWarnLargeSweep: 删除占比低(<半数)→ 不告警", () => {
  assert.equal(shouldWarnLargeSweep(6, 20), false); // 6 < 10
  assert.equal(shouldWarnLargeSweep(10, 100), false);
});

test("shouldWarnLargeSweep: 本地为空时不告警(除零保护)", () => {
  assert.equal(shouldWarnLargeSweep(6, 0), false);
});
