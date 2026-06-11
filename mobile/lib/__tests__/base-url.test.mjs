import test from "node:test";
import assert from "node:assert/strict";

import {
  isValidBaseUrl,
  resolveStoredBaseUrl,
} from "../../.mobile-core-tests/dist/lib/base-url.js";

test("baseUrl restore preserves localhost and private network addresses", () => {
  const fallback = "https://api.yiyu.example";
  const cases = [
    "http://localhost:3000",
    "http://192.168.1.50:8080",
    "http://10.0.0.12:9000",
  ];

  for (const savedUrl of cases) {
    const resolved = resolveStoredBaseUrl(savedUrl, fallback);
    assert.equal(resolved.baseUrl, savedUrl);
    assert.equal(resolved.source, "saved");
    assert.equal(resolved.shouldDeleteSaved, false);
  }
});

test("baseUrl restore falls back only for invalid saved URL", () => {
  const resolved = resolveStoredBaseUrl("not a valid host@@", "https://fallback.example");
  assert.equal(resolved.baseUrl, "https://fallback.example");
  assert.equal(resolved.source, "invalid_saved");
  assert.equal(resolved.shouldDeleteSaved, true);
});

test("baseUrl validation accepts URLs used by settings/login flows", () => {
  assert.equal(isValidBaseUrl("localhost:3000"), true);
  assert.equal(isValidBaseUrl("192.168.10.8:8787"), true);
  assert.equal(isValidBaseUrl("10.1.2.3"), true);
  assert.equal(isValidBaseUrl("http://bad host"), false);
});
