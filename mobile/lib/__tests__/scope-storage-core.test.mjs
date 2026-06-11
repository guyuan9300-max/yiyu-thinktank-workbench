import test from "node:test";
import assert from "node:assert/strict";

import {
  buildScopedDirectoryPath,
  buildScopedStorageKey,
  resolveScopedStorageNamespace,
} from "../../.mobile-core-tests/dist/lib/scope-storage-core.js";

test("resolveScopedStorageNamespace normalizes and encodes account scopes", () => {
  assert.equal(resolveScopedStorageNamespace("org-1:user-1"), "org-1%3Auser-1");
  assert.equal(resolveScopedStorageNamespace(null), "no-org%3Ano-user");
});

test("buildScopedStorageKey prefixes a logical key with the scope namespace", () => {
  assert.equal(
    buildScopedStorageKey("cache:", "taskBoard", "org-1:user-1"),
    "cache:org-1%3Auser-1:taskBoard",
  );
});

test("buildScopedDirectoryPath appends a scope directory once", () => {
  assert.equal(
    buildScopedDirectoryPath("/tmp/smart-input-queue", "org-1:user-1"),
    "/tmp/smart-input-queue/org-1%3Auser-1/",
  );
  assert.equal(
    buildScopedDirectoryPath("/tmp/smart-input-queue/", null),
    "/tmp/smart-input-queue/no-org%3Ano-user/",
  );
});
