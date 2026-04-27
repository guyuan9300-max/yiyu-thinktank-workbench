#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  APP_NAME,
  computeManifestId,
  findBannedRendererCopyViolations,
  inspectAppBundle,
  inspectBackendCapabilities,
  resolveAppManifestPath,
  sha256File,
} from './app-manifest.mjs';

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const targetApp = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(projectRoot, 'dist', 'mac-arm64', APP_NAME);

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

const backendCapability = inspectBackendCapabilities(targetApp);
if (!backendCapability.match) {
  console.error('[verify-packaged-app] bundled backend is missing required workspace consultant synthesis symbols:');
  for (const item of backendCapability.missingSymbols) {
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
      backendCapabilityMatch: backendCapability.match,
    },
    null,
    2,
  ),
);
