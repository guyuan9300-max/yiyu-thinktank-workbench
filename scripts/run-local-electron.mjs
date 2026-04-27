#!/usr/bin/env node

import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '..');
const sourceDistRoot = path.join(projectRoot, 'node_modules', 'electron', 'dist');
const sourceElectronApp = path.join(sourceDistRoot, 'Electron.app');
const sourceElectronBinary = path.join(sourceElectronApp, 'Contents', 'MacOS', 'Electron');
const sourceBundleId = 'com.yiyu.selfworkbench2.dev';
const sourceBundleName = '益语智库自用平台 2.0（开发版）';
const appArgs = process.argv.slice(2);

function fail(message) {
  console.error(`[run-local-electron] ${message}`);
  process.exit(1);
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: options.stdio ?? 'pipe',
    encoding: 'utf8',
    ...options,
  });
  if (result.status !== 0) {
    const detail = (result.stderr || result.stdout || '').trim();
    fail(`${command} ${args.join(' ')} failed${detail ? `: ${detail}` : ''}`);
  }
  return result;
}

function plistRead(plistPath, keyPath) {
  const result = spawnSync('/usr/libexec/PlistBuddy', ['-c', `Print :${keyPath}`, plistPath], {
    stdio: 'pipe',
    encoding: 'utf8',
  });
  if (result.status !== 0) return '';
  return (result.stdout || '').trim();
}

function plistSet(plistPath, keyPath, value) {
  const setResult = spawnSync('/usr/libexec/PlistBuddy', ['-c', `Set :${keyPath} ${value}`, plistPath], {
    stdio: 'ignore',
  });
  if (setResult.status === 0) return;
  run('/usr/libexec/PlistBuddy', ['-c', `Add :${keyPath} string ${value}`, plistPath], { stdio: 'ignore' });
}

function ensurePlistStringValue(plistPath, keyPath, value) {
  if (plistRead(plistPath, keyPath) === value) return false;
  plistSet(plistPath, keyPath, value);
  return true;
}

function restoreSourceElectronBundleIdentity() {
  if (!fs.existsSync(sourceElectronBinary)) {
    fail(`Electron runtime not found at ${sourceElectronBinary}`);
  }

  let changed = false;
  const topInfo = path.join(sourceElectronApp, 'Contents', 'Info.plist');
  changed = ensurePlistStringValue(topInfo, 'CFBundleIdentifier', sourceBundleId) || changed;
  changed = ensurePlistStringValue(topInfo, 'CFBundleName', sourceBundleName) || changed;
  changed = ensurePlistStringValue(topInfo, 'CFBundleDisplayName', sourceBundleName) || changed;

  const helpers = [
    {
      relative: path.join('Contents', 'Frameworks', 'Electron Helper.app', 'Contents', 'Info.plist'),
      id: `${sourceBundleId}.helper`,
      name: `${sourceBundleName} Helper`,
    },
    {
      relative: path.join('Contents', 'Frameworks', 'Electron Helper (Renderer).app', 'Contents', 'Info.plist'),
      id: `${sourceBundleId}.helper.renderer`,
      name: `${sourceBundleName} Helper (Renderer)`,
    },
    {
      relative: path.join('Contents', 'Frameworks', 'Electron Helper (GPU).app', 'Contents', 'Info.plist'),
      id: `${sourceBundleId}.helper.gpu`,
      name: `${sourceBundleName} Helper (GPU)`,
    },
    {
      relative: path.join('Contents', 'Frameworks', 'Electron Helper (Plugin).app', 'Contents', 'Info.plist'),
      id: `${sourceBundleId}.helper.plugin`,
      name: `${sourceBundleName} Helper (Plugin)`,
    },
  ];

  for (const helper of helpers) {
    const helperInfo = path.join(sourceElectronApp, helper.relative);
    if (!fs.existsSync(helperInfo)) continue;
    changed = ensurePlistStringValue(helperInfo, 'CFBundleIdentifier', helper.id) || changed;
    changed = ensurePlistStringValue(helperInfo, 'CFBundleName', helper.name) || changed;
    changed = ensurePlistStringValue(helperInfo, 'CFBundleDisplayName', helper.name) || changed;
  }

  const frameworkInfo = path.join(
    sourceElectronApp,
    'Contents',
    'Frameworks',
    'Electron Framework.framework',
    'Versions',
    'A',
    'Resources',
    'Info.plist',
  );
  if (fs.existsSync(frameworkInfo)) {
    changed = ensurePlistStringValue(frameworkInfo, 'CFBundleIdentifier', `${sourceBundleId}.framework`) || changed;
    changed = ensurePlistStringValue(frameworkInfo, 'CFBundleName', `${sourceBundleName} Framework`) || changed;
  }

  if (changed) {
    spawnSync('codesign', ['--force', '--deep', '--sign', '-', sourceElectronApp], {
      stdio: 'ignore',
    });
  }
}

if (process.platform !== 'darwin') {
  const child = spawn(sourceElectronBinary, appArgs.length ? appArgs : ['.'], {
    cwd: projectRoot,
    stdio: 'inherit',
    env: process.env,
  });
  child.on('exit', (code, signal) => {
    if (signal) process.kill(process.pid, signal);
    process.exit(code ?? 0);
  });
} else {
  restoreSourceElectronBundleIdentity();
  const child = spawn(sourceElectronBinary, appArgs.length ? appArgs : ['.'], {
    cwd: projectRoot,
    stdio: 'inherit',
    env: process.env,
  });
  child.on('exit', (code, signal) => {
    if (signal) process.kill(process.pid, signal);
    process.exit(code ?? 0);
  });
}
