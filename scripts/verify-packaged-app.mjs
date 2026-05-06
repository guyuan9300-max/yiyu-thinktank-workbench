#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  APP_NAME,
  computeManifestId,
  findBannedRendererCopyViolations,
  findPackagedContentViolations,
  inspectAppBundle,
  inspectBackendCapabilities,
  inspectPackagedRuntimeSeed,
  resolveAppManifestPath,
  sha256File,
} from './app-manifest.mjs';

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const targetApp = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(projectRoot, 'dist', 'mac-arm64', APP_NAME);

const COLLAB_REQUIRED_RENDERER_TEXT = [
  '提交并推送我的修改',
  '按日期预览 main 修改',
];

function inspectInternalCollabPackaging(appPath) {
  const appRoot = path.join(appPath, 'Contents', 'Resources', 'app');
  const collabMainModule = path.join(appRoot, 'build', 'main', 'collabGit.js');
  const missing = [];
  if (!fs.existsSync(collabMainModule)) {
    missing.push(`missing collaboration sync main module: ${collabMainModule}`);
  }

  const foundRendererText = new Set();
  const rendererAssetsDir = path.join(appRoot, 'dist', 'renderer', 'assets');
  if (!fs.existsSync(rendererAssetsDir)) {
    missing.push(`missing renderer assets directory: ${rendererAssetsDir}`);
    return { match: false, missing };
  }
  for (const name of fs.readdirSync(rendererAssetsDir)) {
    if (!name.endsWith('.js')) continue;
    const assetPath = path.join(rendererAssetsDir, name);
    const text = fs.readFileSync(assetPath, 'utf8');
    for (const marker of COLLAB_REQUIRED_RENDERER_TEXT) {
      if (text.includes(marker)) {
        foundRendererText.add(marker);
      }
    }
  }
  for (const marker of COLLAB_REQUIRED_RENDERER_TEXT) {
    if (!foundRendererText.has(marker)) {
      missing.push(`missing collaboration sync renderer copy: ${marker}`);
    }
  }
  return { match: missing.length === 0, missing };
}

if (!fs.existsSync(targetApp)) {
  console.error(`[verify-packaged-app] app bundle not found: ${targetApp}`);
  process.exit(1);
}

const inspection = inspectAppBundle(targetApp);
if (!inspection.manifest) {
  console.error(`[verify-packaged-app] missing version manifest: ${resolveAppManifestPath(targetApp)}`);
  process.exit(1);
}

const rendererPath = path.join(
  targetApp,
  'Contents',
  'Resources',
  'app',
  'dist',
  'renderer',
  'assets',
  inspection.manifest.rendererEntry,
);
if (!fs.existsSync(rendererPath)) {
  console.error(`[verify-packaged-app] renderer entry missing: ${rendererPath}`);
  process.exit(1);
}

const rendererHash = sha256File(rendererPath);
if (rendererHash !== inspection.manifest.rendererHash) {
  console.error(
    `[verify-packaged-app] renderer hash mismatch: manifest=${inspection.manifest.rendererHash} actual=${rendererHash}`,
  );
  process.exit(1);
}

const bannedCopyViolations = findBannedRendererCopyViolations(targetApp);
if (bannedCopyViolations.length > 0) {
  console.error('[verify-packaged-app] bundled renderer contains banned legacy copy:');
  for (const item of bannedCopyViolations) {
    console.error(` - ${item}`);
  }
  process.exit(1);
}

const packagedContentViolations = findPackagedContentViolations(targetApp);
if (packagedContentViolations.length > 0) {
  console.error('[verify-packaged-app] bundled app contains local data or generated artifacts:');
  for (const item of packagedContentViolations) {
    console.error(` - ${item}`);
  }
  process.exit(1);
}

const internalCollabPackaging = inspectInternalCollabPackaging(targetApp);
if (!internalCollabPackaging.match) {
  console.error('[verify-packaged-app] bundled app is missing collaboration sync runtime or UI copy:');
  for (const item of internalCollabPackaging.missing) {
    console.error(` - ${item}`);
  }
  process.exit(1);
}

const backendCapability = inspectBackendCapabilities(targetApp);
if (!backendCapability.match) {
  console.error('[verify-packaged-app] bundled backend is missing required workspace consultant synthesis symbols:');
  for (const item of backendCapability.missingSymbols) {
    console.error(` - ${item}`);
  }
  process.exit(1);
}

const runtimeSeed = inspectPackagedRuntimeSeed(targetApp);
if (!runtimeSeed.match) {
  console.error('[verify-packaged-app] packaged runtime seed is incomplete or stale:');
  for (const item of runtimeSeed.missing) {
    console.error(` - ${item}`);
  }
  process.exit(1);
}

console.log(
  JSON.stringify(
    {
      appPath: targetApp,
      bundleManifestId: computeManifestId(inspection.manifest),
      rendererEntry: inspection.manifest.rendererEntry,
      rendererHash,
      packagedContentClean: true,
      internalCollabAvailable: true,
      backendCapabilityMatch: backendCapability.match,
      runtimeSeedManifest: runtimeSeed.manifestPath,
      runtimeSeedPython: runtimeSeed.pythonExecutable,
      runtimeSeedWheelFileCount: runtimeSeed.wheelFileCount,
      runtimeSeedRequirementsHashMatch: runtimeSeed.requirementsHashMatch,
      runtimeSeedWheelhouseHashMatch: runtimeSeed.wheelhouseHashMatch,
    },
    null,
    2,
  ),
);
