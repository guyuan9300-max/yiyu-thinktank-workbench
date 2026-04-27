import test from 'node:test';
import assert from 'node:assert/strict';

import {
  bundleManifestMatches,
  computeBundleManifestId,
  type BundleVersionManifest,
} from './versionManifest.js';

function fixture(overrides: Partial<BundleVersionManifest> = {}): BundleVersionManifest {
  return {
    appVersion: '0.1.0',
    buildVersion: '2026.04.21-220000-deadbeef',
    gitCommit: 'deadbeef',
    builtAt: '2026-04-21T22:00:00.000Z',
    rendererEntry: 'main-demo.js',
    rendererHash: 'renderer-hash',
    backendSourceHash: 'backend-hash',
    schemaVersionMin: 20260420,
    ...overrides,
  };
}

test('manifest id stays stable for equivalent payloads', () => {
  const left = fixture();
  const right = fixture();

  assert.equal(computeBundleManifestId(left), computeBundleManifestId(right));
  assert.equal(bundleManifestMatches(left, right), true);
});

test('manifest id changes when renderer asset changes', () => {
  const left = fixture();
  const right = fixture({ rendererEntry: 'main-next.js' });

  assert.notEqual(computeBundleManifestId(left), computeBundleManifestId(right));
  assert.equal(bundleManifestMatches(left, right), false);
});
