#!/usr/bin/env node

import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  buildVersionManifest,
  computeManifestId,
  resolveProjectManifestPath,
  writeJsonFile,
} from './app-manifest.mjs';

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const manifestPath = resolveProjectManifestPath(projectRoot);
const manifest = buildVersionManifest(projectRoot);

writeJsonFile(manifestPath, manifest);
console.log(
  JSON.stringify(
    {
      manifestPath,
      bundleManifestId: computeManifestId(manifest),
      rendererEntry: manifest.rendererEntry,
      buildVersion: manifest.buildVersion,
    },
    null,
    2,
  ),
);
