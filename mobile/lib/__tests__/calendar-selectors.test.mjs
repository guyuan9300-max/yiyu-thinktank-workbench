import test from "node:test";
import assert from "node:assert/strict";

import {
  buildMonthCalendarDays,
  getFirstDayOfWeek,
} from "../../.mobile-core-tests/dist/lib/calendar-selectors.js";

test("month calendar uses Monday as the first column", () => {
  // 2026-03-01 is Sunday. In a Monday-first grid it belongs to the 7th column,
  // so the first six cells should be the previous month.
  assert.equal(getFirstDayOfWeek(2026, 2), 6);
  const days = buildMonthCalendarDays(2026, 2);
  assert.deepEqual(days.slice(0, 7).map((item) => item.dateKey), [
    "2026-02-23",
    "2026-02-24",
    "2026-02-25",
    "2026-02-26",
    "2026-02-27",
    "2026-02-28",
    "2026-03-01",
  ]);
});
