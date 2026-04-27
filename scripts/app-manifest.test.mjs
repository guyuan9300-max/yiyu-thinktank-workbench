import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import {
  computeManifestId,
  findBannedRendererCopyViolations,
  inspectAppBundle,
  inspectBackendCapabilities,
  writeJsonFile,
} from './app-manifest.mjs';

function makeFakeAppBundle({ rendererEntry, rendererSource, rendererHash }) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'yiyu-app-bundle-'));
  const appPath = path.join(root, '益语智库自用平台 2.0.app');
  const rendererDir = path.join(appPath, 'Contents', 'Resources', 'app', 'dist', 'renderer', 'assets');
  fs.mkdirSync(rendererDir, { recursive: true });
  fs.writeFileSync(path.join(rendererDir, rendererEntry), rendererSource, 'utf8');
  writeJsonFile(
    path.join(appPath, 'Contents', 'Resources', 'app', 'dist', 'version-manifest.json'),
    {
      appVersion: '0.1.0',
      buildVersion: '2026.04.21-000000-deadbeef',
      gitCommit: 'deadbeef',
      builtAt: '2026-04-21T00:00:00.000Z',
      rendererEntry,
      rendererHash,
      backendSourceHash: 'backend-hash',
      schemaVersionMin: 42,
    },
  );
  return appPath;
}

function writeFakeBackend(appPath, source) {
  const backendDir = path.join(appPath, 'Contents', 'Resources', 'app', 'backend', 'app', 'services');
  fs.mkdirSync(backendDir, { recursive: true });
  fs.writeFileSync(path.join(backendDir, 'workspace_query_router.py'), source, 'utf8');
}

test('inspectAppBundle returns manifest identity and renderer hash', () => {
  const appPath = makeFakeAppBundle({
    rendererEntry: 'main-test.js',
    rendererSource: 'console.log("fresh bundle");\n',
    rendererHash: 'f8b07e6b6e5b57cdbb5e2a8f0a9f1b6c94f1f9d8403f0cd5c4b8cf3b9960cb1d',
  });

  const inspection = inspectAppBundle(appPath);
  assert.equal(inspection.exists, true);
  assert.equal(inspection.rendererEntry, 'main-test.js');
  assert.equal(
    inspection.bundleManifestId,
    computeManifestId(inspection.manifest),
  );
  assert.match(String(inspection.rendererHash), /^[0-9a-f]{64}$/);
});

test('findBannedRendererCopyViolations detects legacy retry copy in packaged renderer', () => {
  const appPath = makeFakeAppBundle({
    rendererEntry: 'main-legacy.js',
    rendererSource: 'console.log("已基于命中的资料生成简版可用回答；完整长文扩写未完成，可继续重试扩写。");\n',
    rendererHash: '3b18474d6d9a4d4ce92f1d9b14d39f1d5c125d4f7972a47d0a8290f22c0ae8b4',
  });

  const violations = findBannedRendererCopyViolations(appPath);
  assert.deepEqual(violations, [
    '已基于命中的资料生成简版可用回答',
    '完整长文扩写未完成',
  ]);
});

test('inspectBackendCapabilities detects consultant synthesis symbols', () => {
  const appPath = makeFakeAppBundle({
    rendererEntry: 'main-fresh.js',
    rendererSource: 'console.log("fresh bundle");\n',
    rendererHash: '6f1ed002ab5595859014ebf0951522d9fc5e55f9ee3191a61c4cbe7be0db42a8',
  });
  writeFakeBackend(
    appPath,
    [
      'generationMode = "consultant_synthesis"',
      'routeReason = "workspace_rule_consultant_synthesis"',
      'def build_consultant_synthesis_material_pack():',
      '    return None',
      '',
    ].join('\n'),
  );

  const capability = inspectBackendCapabilities(appPath);
  assert.equal(capability.exists, true);
  assert.equal(capability.match, true);
  assert.deepEqual(capability.missingSymbols, []);
});

test('inspectBackendCapabilities reports missing consultant synthesis symbols', () => {
  const appPath = makeFakeAppBundle({
    rendererEntry: 'main-stale.js',
    rendererSource: 'console.log("stale bundle");\n',
    rendererHash: '4e7e1bbef78e1c5fe327d4d6dca79615273eace3e785d613b95e399bdc96323c',
  });
  writeFakeBackend(appPath, 'generationMode = "long_synthesis"\n');

  const capability = inspectBackendCapabilities(appPath);
  assert.equal(capability.exists, true);
  assert.equal(capability.match, false);
  assert.deepEqual(capability.missingSymbols, [
    'consultant_synthesis',
    'workspace_rule_consultant_synthesis',
    'build_consultant_synthesis_material_pack',
  ]);
});
