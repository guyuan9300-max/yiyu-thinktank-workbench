#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const APP_NAME = '益语智库自用平台.app';
const projectRoot = path.resolve(new URL('..', import.meta.url).pathname);
const sourceApp = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(projectRoot, 'dist', 'mac-arm64', APP_NAME);
const userApplicationsDir = path.join(os.homedir(), 'Applications');
const targetApp = path.join(userApplicationsDir, APP_NAME);
const timestamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..+/, '').replace('T', '-');
const backupRoot = path.join(os.homedir(), 'Library', 'Application Support', 'yiyu-thinktank-workbench', 'runtime', 'install-backups');
const backupApp = path.join(backupRoot, `益语智库自用平台.old-${timestamp}.app`);
const legacyCandidates = [
  '/Applications/益语智库.app',
  path.join(os.homedir(), 'Library', 'Application Support', 'yiyu-thinktank-workbench', 'runtime', 'local-electron', '益语智库工作台.app'),
  path.join(os.homedir(), 'Library', 'Application Support', 'yiyu-thinktank-workbench', 'runtime', 'local-electron-dist', '益语智库工作台.app'),
];

function fail(message) {
  console.error(`[install-mac-app] ${message}`);
  process.exit(1);
}

function info(message) {
  console.log(`[install-mac-app] ${message}`);
}

function runOrFail(command, args) {
  const result = spawnSync(command, args, { stdio: 'inherit' });
  if (result.error) {
    fail(`${command} failed: ${result.error.message}`);
  }
  if (result.status !== 0) {
    fail(`${command} exited with status ${result.status}`);
  }
}

function runQuiet(command, args) {
  return spawnSync(command, args, { stdio: 'ignore' });
}

function stabilizeInstalledApp(targetPath) {
  const scriptPath = path.join(projectRoot, 'scripts', 'stabilize-mac-app.mjs');
  const result = spawnSync(process.execPath, [scriptPath, targetPath], { stdio: 'inherit' });
  if (result.error) {
    fail(`stabilize script failed: ${result.error.message}`);
  }
  if (result.status !== 0) {
    fail(`stabilize script exited with status ${result.status}`);
  }
}

function stopRunningApp() {
  info('stopping running app instances before install');
  runQuiet('osascript', ['-e', 'tell application "益语智库自用平台" to quit']);
  runQuiet('pkill', ['-x', '益语智库自用平台']);
  runQuiet('pkill', ['-f', `${targetApp}/Contents/MacOS/${APP_NAME.replace(/\\.app$/, '')}`]);
  const waitResult = spawnSync(
    'bash',
    ['-lc', 'for _ in {1..30}; do pgrep -x "益语智库自用平台" >/dev/null || exit 0; sleep 0.2; done; exit 0'],
    { stdio: 'ignore' },
  );
  if (waitResult.status !== 0) {
    fail('timed out waiting for running app instance to stop');
  }
}

function pickRendererEntry(assetDir) {
  const files = fs.readdirSync(assetDir).filter((name) => /^index-.*\.js$/.test(name)).sort();
  return files[0] || null;
}

if (!fs.existsSync(sourceApp)) {
  fail(`source app not found: ${sourceApp}`);
}

fs.mkdirSync(userApplicationsDir, { recursive: true });
fs.mkdirSync(backupRoot, { recursive: true });

stopRunningApp();

if (fs.existsSync(targetApp)) {
  info(`existing app detected, backing up to: ${backupApp}`);
  fs.renameSync(targetApp, backupApp);
}

info(`installing ${sourceApp} -> ${targetApp}`);
runOrFail('ditto', [sourceApp, targetApp]);
stabilizeInstalledApp(targetApp);

const sourceRendererAssetDir = path.join(sourceApp, 'Contents', 'Resources', 'app', 'dist', 'renderer', 'assets');
const targetRendererAssetDir = path.join(targetApp, 'Contents', 'Resources', 'app', 'dist', 'renderer', 'assets');
const sourceEntry = pickRendererEntry(sourceRendererAssetDir);
const targetEntry = pickRendererEntry(targetRendererAssetDir);
if (!sourceEntry || !targetEntry) {
  fail('unable to verify installed renderer assets');
}
if (sourceEntry !== targetEntry) {
  fail(`installed app renderer asset mismatch: source=${sourceEntry} target=${targetEntry}`);
}
info(`verified installed renderer asset: ${targetEntry}`);

const legacyHits = legacyCandidates.filter((targetPath) => fs.existsSync(targetPath));
if (legacyHits.length > 0) {
  info('legacy/duplicate app entries still exist. clean these manually if they are no longer needed:');
  for (const targetPath of legacyHits) {
    console.log(` - ${targetPath}`);
  }
}

info(`recommended launch entry: ${targetApp}`);
