import test from "node:test";
import assert from "node:assert/strict";

import {
  buildProjectOptions,
  filterEventLinesForSelection,
  findAutoMatchedClient,
  findAutoMatchedEventLine,
  shouldApplyAutoAssociation,
} from "../../.mobile-core-tests/dist/lib/create-task-association.js";

const eventLines = [
  {
    id: "event-a",
    name: "益语智库-周会跟进",
    primaryClientId: "client-a",
    primaryClientName: "益语智库",
    status: "active",
  },
  {
    id: "event-b",
    name: "第二项目-执行推进",
    primaryClientId: "client-b",
    primaryClientName: "第二项目",
    status: "active",
  },
];

const clients = [
  { id: "client-a", name: "益语智库" },
  { id: "client-b", name: "第二项目" },
];

test("buildProjectOptions prefers explicit clients when available", () => {
  const options = buildProjectOptions(clients, eventLines);
  assert.deepEqual(
    options.map((item) => item.id),
    ["client:client-a", "client:client-b"],
  );
});

test("filterEventLinesForSelection scopes by selected client", () => {
  const filtered = filterEventLinesForSelection(eventLines, "client-a", null);
  assert.deepEqual(filtered.map((item) => item.id), ["event-a"]);
});

test("findAutoMatchedEventLine matches title keywords to event line aliases", () => {
  const matched = findAutoMatchedEventLine("益语智库周会纪要", eventLines);
  assert.equal(matched?.id, "event-a");
});

test("findAutoMatchedClient matches title/description keywords to a client", () => {
  // 模拟"标题+描述"拼成的搜索串命中客户名（事件线没命中时的回退）
  const matched = findAutoMatchedClient("下周给益语智库交周报", clients);
  assert.equal(matched?.id, "client-a");
});

test("findAutoMatchedClient matches client alias", () => {
  const matched = findAutoMatchedClient("贝石的尽调材料", [
    { id: "client-c", name: "贝石基金会", alias: "贝石" },
  ]);
  assert.equal(matched?.id, "client-c");
});

test("findAutoMatchedClient returns null when nothing matches", () => {
  assert.equal(findAutoMatchedClient("随便写点不相关的东西", clients), null);
});

test("manual association wins over auto association", () => {
  assert.equal(shouldApplyAutoAssociation({
    source: "manual",
    lockedTitleKey: "益语智库周会纪要",
    titleSearchKey: "益语智库周会纪要",
    selectedEventLineId: "event-a",
    autoMatchedEventLineId: "event-b",
  }), false);

  assert.equal(shouldApplyAutoAssociation({
    source: "default",
    lockedTitleKey: null,
    titleSearchKey: "益语智库周会纪要",
    selectedEventLineId: null,
    autoMatchedEventLineId: "event-a",
  }), true);
});

// 收敛不变量(防再次出现主仓 TasksView2 式的"Maximum update depth"无限渲染)：
// CreateTask 的自动归属 effect 依赖数组里含它自己会 setState 改变的值
// (selectedEventLineId / associationSource),靠 shouldApplyAutoAssociation 自然收敛。
// 一旦 syncSelectionFromEventLine 把 selectedEventLine 设成 autoMatchedEventLine，
// 下一次判定必须返回 false——否则每帧 setState 会卡死页面。这条用例把该不变量锁死。
test("auto association converges: 应用后 selectedEventLineId === autoMatchedEventLineId 则不再重复应用", () => {
  assert.equal(shouldApplyAutoAssociation({
    source: "auto",
    lockedTitleKey: null,
    titleSearchKey: "益语智库周会纪要",
    selectedEventLineId: "event-a",
    autoMatchedEventLineId: "event-a",
  }), false);
});

test("auto association 收敛:同一标题锁定后(lockedTitleKey === titleSearchKey)不再覆盖", () => {
  assert.equal(shouldApplyAutoAssociation({
    source: "auto",
    lockedTitleKey: "益语智库周会纪要",
    titleSearchKey: "益语智库周会纪要",
    selectedEventLineId: null,
    autoMatchedEventLineId: "event-b",
  }), false);
});

test("auto association 收敛:无匹配事件线时不应用(空守卫)", () => {
  assert.equal(shouldApplyAutoAssociation({
    source: "default",
    lockedTitleKey: null,
    titleSearchKey: "随便写点东西",
    selectedEventLineId: null,
    autoMatchedEventLineId: null,
  }), false);
});
