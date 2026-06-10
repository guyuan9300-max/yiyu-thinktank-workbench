import test from "node:test";
import assert from "node:assert/strict";

import {
  buildAccountScopeKey,
  normalizeAccountScopeKey,
  redactAccountScopeKey,
} from "../../.mobile-core-tests/dist/lib/account-scope.js";

test("buildAccountScopeKey uses organization plus user id", () => {
  assert.equal(
    buildAccountScopeKey({ organizationId: "org-1", id: "user-1" }),
    "org-1:user-1",
  );
  assert.equal(
    buildAccountScopeKey({ organizationId: null, id: "user-2" }),
    "no-org:user-2",
  );
});

test("normalizeAccountScopeKey rejects malformed values", () => {
  assert.equal(normalizeAccountScopeKey(""), null);
  assert.equal(normalizeAccountScopeKey("missing-colon"), null);
  assert.equal(normalizeAccountScopeKey("org-1:user-1"), "org-1:user-1");
});

test("redactAccountScopeKey hides most of the user segment", () => {
  assert.equal(redactAccountScopeKey("org-1:user-123456"), "org-1:user***");
});
