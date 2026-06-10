import test from "node:test";
import assert from "node:assert/strict";

import {
  buildWeekInfo,
  formatLocalDateKey,
  getLocalWeekAnchorDateKey,
  getLocalWeekRangeKeys,
  startOfLocalDay,
  endOfLocalDay,
  weekLabelForDateKey,
} from "../../.mobile-core-tests/dist/lib/date.js";

function parseLocalDateKey(dateKey) {
  const [year, month, day] = dateKey.split("-").map(Number);
  return new Date(year, month - 1, day);
}

test("formatLocalDateKey uses local calendar date instead of UTC slices", () => {
  const localMidnight = new Date(2026, 3, 16, 0, 5, 0, 0);
  assert.equal(formatLocalDateKey(localMidnight), "2026-04-16");
});

test("local week range is monday to sunday", () => {
  const sample = new Date(2026, 3, 16, 18, 30, 0, 0);
  const range = getLocalWeekRangeKeys(sample);
  assert.equal(parseLocalDateKey(range.startKey).getDay(), 1);
  assert.equal(parseLocalDateKey(range.endKey).getDay(), 0);
  assert.ok(range.startKey <= formatLocalDateKey(sample));
  assert.ok(range.endKey >= formatLocalDateKey(sample));
});

test("start/end of local day stay within same date key", () => {
  const sample = new Date(2026, 10, 3, 12, 45, 22, 111);
  assert.equal(formatLocalDateKey(startOfLocalDay(sample)), "2026-11-03");
  assert.equal(formatLocalDateKey(endOfLocalDay(sample)), "2026-11-03");
});

test("week helpers keep monday anchor and YYYY-Www label aligned", () => {
  const sample = new Date(2026, 3, 16, 18, 30, 0, 0);
  const weekAnchorDate = getLocalWeekAnchorDateKey(sample);
  const weekInfo = buildWeekInfo(sample);

  assert.equal(weekAnchorDate, weekInfo.weekAnchorDate);
  assert.equal(weekLabelForDateKey(weekAnchorDate), weekInfo.weekLabel);
  assert.match(weekInfo.weekLabel, /^\d{4}-W\d{2}$/);
});
