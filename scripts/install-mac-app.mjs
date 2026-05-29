#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  APP_DISPLAY_NAME,
  APP_NAME,
  DEFAULT_INSTALL_RECEIPT_PATH,
  inspectAppBundle as inspectBundle,
} from './app-manifest.mjs';

const APP_BASENAME = APP_NAME.replace(/\.app$/, '');
const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const userApplicationsDir = path.join(os.homedir(), 'Applications');
const targetApp = path.join(userApplicationsDir, APP_NAME);
const timestamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..+/, '').replace('T', '-');
const stagingApp = path.join(userApplicationsDir, `.${APP_BASENAME}.installing-${timestamp}.app`);
const backupRoot = path.join(os.homedir(), 'Library', 'Application Support', 'yiyu-thinktank-workbench', 'runtime', 'install-backups');
const backupApp = path.join(backupRoot, `${APP_BASENAME}.old-${timestamp}.app`);
const defaultReceiptPath = DEFAULT_INSTALL_RECEIPT_PATH;
const legacyCandidates = [
  '/Applications/益语智库.app',
  '/Applications/益语智库自用平台.app',
  path.join(os.homedir(), 'Applications', '益语智库自用平台.app'),
  path.join(os.homedir(), 'Applications', '益语智库自用平台 2.0.app'),
  path.join(os.homedir(), 'Library', 'Application Support', 'yiyu-thinktank-workbench', 'runtime', 'local-electron', '益语智库工作台.app'),
  path.join(os.homedir(), 'Library', 'Application Support', 'yiyu-thinktank-workbench', 'runtime', 'local-electron-dist', '益语智库工作台.app'),
];

function parseArgs(argv) {
  let source = null;
  let receipt = defaultReceiptPath;
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    if (current === '--receipt') {
      const value = argv[index + 1];
      if (!value) {
        throw new Error('missing value for --receipt');
      }
      receipt = path.resolve(value);
      index += 1;
      continue;
    }
    if (current.startsWith('--receipt=')) {
      receipt = path.resolve(current.slice('--receipt='.length));
      continue;
    }
    if (current.startsWith('--')) {
      throw new Error(`unknown option: ${current}`);
    }
    if (source) {
      throw new Error(`unexpected extra argument: ${current}`);
    }
    source = path.resolve(current);
  }
  return {
    sourceApp: source || path.join(projectRoot, 'dist', 'mac-arm64', APP_NAME),
    receiptPath: receipt,
  };
}

function info(message) {
  console.log(`[install-mac-app] ${message}`);
}

function runOrFail(command, args) {
  const result = spawnSync(command, args, { stdio: 'inherit' });
  if (result.error) {
    throw new Error(`${command} failed: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`${command} exited with status ${result.status}`);
  }
}

function runQuiet(command, args) {
  return spawnSync(command, args, { stdio: 'ignore' });
}

function stabilizeInstalledApp(targetPath) {
  const scriptPath = path.join(projectRoot, 'scripts', 'stabilize-mac-app.mjs');
  const result = spawnSync(process.execPath, [scriptPath, targetPath], { stdio: 'inherit' });
  if (result.error) {
    throw new Error(`stabilize script failed: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`stabilize script exited with status ${result.status}`);
  }
}

function stopRunningApp() {
  info('stopping running app instances before install');
  runQuiet('osascript', ['-e', `tell application "${APP_DISPLAY_NAME}" to quit`]);
  runQuiet('osascript', ['-e', 'tell application "益语智库自用平台" to quit']);
  runQuiet('osascript', ['-e', 'tell application "益语智库自用平台 2.0" to quit']);
  runQuiet('pkill', ['-x', APP_DISPLAY_NAME]);
  runQuiet('pkill', ['-x', '益语智库自用平台']);
  runQuiet('pkill', ['-x', '益语智库自用平台 2.0']);
  runQuiet('pkill', ['-f', `${targetApp}/Contents/MacOS/${APP_BASENAME}`]);
  const waitResult = spawnSync(
    'bash',
    ['-lc', `for _ in {1..30}; do pgrep -x "${APP_DISPLAY_NAME}" >/dev/null || pgrep -x "益语智库自用平台" >/dev/null || pgrep -x "益语智库自用平台 2.0" >/dev/null || exit 0; sleep 0.2; done; exit 0`],
    { stdio: 'ignore' },
  );
  if (waitResult.status !== 0) {
    throw new Error('timed out waiting for running app instance to stop');
  }
}

function snapshotSourceBundle(sourcePath) {
  const inspection = inspectBundle(sourcePath);
  const sourceFrameworksDir = path.join(sourcePath, 'Contents', 'Frameworks');
  return {
    frameworkEntries: fs.existsSync(sourceFrameworksDir) ? fs.readdirSync(sourceFrameworksDir).sort() : null,
    manifest: inspection.manifest,
    bundleManifestId: inspection.bundleManifestId,
    rendererEntry: inspection.rendererEntry,
    rendererHash: inspection.rendererHash,
  };
}

function scanStagingBundles(sourceRendererEntry) {
  if (!fs.existsSync(userApplicationsDir)) {
    return [];
  }
  return fs.readdirSync(userApplicationsDir)
    .filter((name) => name.startsWith(`.${APP_BASENAME}.installing-`) && name.endsWith('.app'))
    .map((name) => {
      const appPath = path.join(userApplicationsDir, name);
      const metadata = inspectBundle(appPath);
      return {
        path: appPath,
        modifiedAt: metadata.modifiedAt,
        rendererEntry: metadata.rendererEntry,
        staleForCurrentInstall: Boolean(
          sourceRendererEntry
            ? metadata.rendererEntry !== sourceRendererEntry
            : true
        ),
      };
    })
    .sort((left, right) => left.path.localeCompare(right.path, 'zh-Hans-CN'));
}

function cleanupStagingBundles(sourceRendererEntry) {
  const removedPaths = [];
  for (const candidate of scanStagingBundles(sourceRendererEntry)) {
    if (path.resolve(candidate.path) === path.resolve(stagingApp)) {
      continue;
    }
    safeRemove(candidate.path);
    removedPaths.push(candidate.path);
  }
  return removedPaths;
}

function writeReceipt(receiptPath, payload) {
  const target = path.resolve(receiptPath);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  info(`wrote install receipt: ${target}`);
}

function verifyInstalledBundle(targetPath, sourceSnapshot) {
  const requiredPaths = [
    path.join(targetPath, 'Contents', 'Info.plist'),
    path.join(targetPath, 'Contents', 'PkgInfo'),
    path.join(targetPath, 'Contents', 'Frameworks'),
    path.join(targetPath, 'Contents', 'Frameworks', 'Electron Framework.framework'),
    path.join(targetPath, 'Contents', 'Frameworks', 'Electron Framework.framework', 'Electron Framework'),
    path.join(targetPath, 'Contents', 'Frameworks', `${APP_BASENAME} Helper.app`),
  ];

  for (const requiredPath of requiredPaths) {
    if (!fs.existsSync(requiredPath)) {
      throw new Error(`installed app bundle is incomplete, missing: ${requiredPath}`);
    }
  }

  const targetFrameworksDir = path.join(targetPath, 'Contents', 'Frameworks');
  const targetFrameworkEntries = fs.readdirSync(targetFrameworksDir).sort();
  if (sourceSnapshot.frameworkEntries && sourceSnapshot.frameworkEntries.length !== targetFrameworkEntries.length) {
    throw new Error(
      `installed app framework count mismatch: source=${sourceSnapshot.frameworkEntries.length} target=${targetFrameworkEntries.length}`,
    );
  }

  const targetInspection = inspectBundle(targetPath);
  if (!sourceSnapshot.bundleManifestId || !sourceSnapshot.manifest) {
    throw new Error('source app version-manifest.json missing or invalid');
  }
  if (!targetInspection.bundleManifestId || !targetInspection.manifest) {
    throw new Error('installed app version-manifest.json missing or invalid');
  }
  if (sourceSnapshot.bundleManifestId !== targetInspection.bundleManifestId) {
    throw new Error(
      `installed app manifest mismatch: source=${sourceSnapshot.bundleManifestId} target=${targetInspection.bundleManifestId}`,
    );
  }
  if (sourceSnapshot.rendererHash !== targetInspection.rendererHash) {
    throw new Error(
      `installed app renderer hash mismatch: source=${sourceSnapshot.rendererHash} target=${targetInspection.rendererHash}`,
    );
  }
}

function safeRemove(targetPath) {
  if (!fs.existsSync(targetPath)) {
    return;
  }
  fs.rmSync(targetPath, { recursive: true, force: true });
}

let sourceApp = path.join(projectRoot, 'dist', 'mac-arm64', APP_NAME);
let receiptPath = defaultReceiptPath;
let currentStep = 'validate-source';
let promoted = false;

function buildReceipt({ failureStep = null, errorMessage = null } = {}) {
  const sourceInfo = inspectBundle(sourceApp);
  const targetInfo = inspectBundle(targetApp);
  return {
    recordedAt: new Date().toISOString(),
    sourceApp,
    sourceAppMTime: sourceInfo.modifiedAt,
    sourceRendererEntry: sourceInfo.rendererEntry,
    sourceRendererHash: sourceInfo.rendererHash,
    sourceBundleManifestId: sourceInfo.bundleManifestId,
    stagingApp,
    targetApp,
    targetAppMTime: targetInfo.modifiedAt,
    targetRendererEntry: targetInfo.rendererEntry,
    targetRendererHash: targetInfo.rendererHash,
    targetBundleManifestId: targetInfo.bundleManifestId,
    rendererEntryMatch: Boolean(
      sourceInfo.rendererEntry
        && targetInfo.rendererEntry
        && sourceInfo.rendererEntry === targetInfo.rendererEntry
    ),
    bundleManifestMatch: Boolean(
      sourceInfo.bundleManifestId
        && targetInfo.bundleManifestId
        && sourceInfo.bundleManifestId === targetInfo.bundleManifestId
    ),
    promoted,
    failureStep,
    errorMessage,
    staleCandidates: scanStagingBundles(sourceInfo.rendererEntry),
  };
}

try {
  ({ sourceApp, receiptPath } = parseArgs(process.argv.slice(2)));
  if (!fs.existsSync(sourceApp)) {
    throw new Error(`source app not found: ${sourceApp}`);
  }

  const sourceSnapshot = snapshotSourceBundle(sourceApp);

  fs.mkdirSync(userApplicationsDir, { recursive: true });
  fs.mkdirSync(backupRoot, { recursive: true });

  currentStep = 'stop-running-app';
  stopRunningApp();

  currentStep = 'clear-staging';
  safeRemove(stagingApp);

  currentStep = 'copy-to-staging';
  info(`installing ${sourceApp} -> ${stagingApp}`);
  runOrFail('ditto', [sourceApp, stagingApp]);

  currentStep = 'stabilize-staging';
  stabilizeInstalledApp(stagingApp);

  currentStep = 'verify-staging-bundle';
  verifyInstalledBundle(stagingApp, sourceSnapshot);

  currentStep = 'verify-manifest-identity';
  info(`verified installed bundle manifest: ${sourceSnapshot.bundleManifestId}`);

  if (fs.existsSync(targetApp)) {
    currentStep = 'backup-existing-target';
    info(`existing app detected, backing up to: ${backupApp}`);
    fs.renameSync(targetApp, backupApp);
  }

  currentStep = 'promote-target-app';
  info(`promoting verified app into place: ${stagingApp} -> ${targetApp}`);
  fs.renameSync(stagingApp, targetApp);
  promoted = true;

  currentStep = 'cleanup-staging-bundles';
  const removedStagingBundles = cleanupStagingBundles(sourceSnapshot.rendererEntry);
  if (removedStagingBundles.length > 0) {
    info(`cleaned ${removedStagingBundles.length} stale staging bundle(s)`);
  }

  writeReceipt(receiptPath, buildReceipt());

  const legacyHits = legacyCandidates.filter((targetPath) => fs.existsSync(targetPath));
  if (legacyHits.length > 0) {
    info('legacy/duplicate app entries still exist. clean these manually if they are no longer needed:');
    for (const targetPath of legacyHits) {
      console.log(` - ${targetPath}`);
    }
  }

  info(`recommended launch entry: ${targetApp}`);
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  writeReceipt(receiptPath, buildReceipt({ failureStep: currentStep, errorMessage: message }));
  console.error(`[install-mac-app] ${message}`);
  process.exit(1);
}
