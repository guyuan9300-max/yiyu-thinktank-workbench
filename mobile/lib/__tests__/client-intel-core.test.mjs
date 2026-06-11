import test from "node:test";
import assert from "node:assert/strict";

import { deriveClientIntelAvailability } from "../../.mobile-core-tests/dist/lib/client-intel-core.js";

test("deriveClientIntelAvailability keeps workspace usable when cockpit is unavailable", () => {
  assert.deepEqual(
    deriveClientIntelAvailability([
      { source: "workspace", ok: true, status: "rich", updatedAt: "2026-04-16T09:00:00.000Z" },
      {
        source: "strategic_cockpit",
        ok: false,
        status: "unavailable",
        missingSources: ["strategic_cockpit"],
      },
    ]),
    {
      status: "partial",
      availableSources: ["workspace"],
      missingSources: ["strategic_cockpit"],
      staleSources: [],
      sourceUpdatedAt: {
        workspace: "2026-04-16T09:00:00.000Z",
        strategic_cockpit: null,
      },
    },
  );
});

test("deriveClientIntelAvailability reports missing when all sources fail", () => {
  const availability = deriveClientIntelAvailability([
    { source: "workspace", ok: false, status: "unavailable", missingSources: ["workspace"] },
    {
      source: "strategic_cockpit",
      ok: false,
      status: "unavailable",
      missingSources: ["strategic_cockpit"],
    },
  ]);

  assert.equal(availability.status, "missing");
  assert.deepEqual(availability.availableSources, []);
  assert.deepEqual(availability.missingSources, ["strategic_cockpit", "workspace"]);
});
