#!/usr/bin/env node

import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';

const APP_NAME = '益语智库自用平台.app';
const WORKBENCH_DATA_DIR_NAME = 'YiyuThinkTankWorkbench';
const projectRoot = path.resolve(new URL('..', import.meta.url).pathname);
const installedApp = path.join(os.homedir(), 'Applications', APP_NAME);
const binaryPath = path.join(installedApp, 'Contents', 'MacOS', '益语智库自用平台');
const userDataPath = path.join(os.homedir(), 'Library', 'Application Support', WORKBENCH_DATA_DIR_NAME);
const runtimeManifestPath = path.join(userDataPath, 'runtime', 'logs', 'runtime-manifest.json');
const rawElectronPattern = `${projectRoot}/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron \\.`;
const DEFAULT_PACKAGED_REMOTE_CLOUD_API_URL = 'http://101.126.34.232';

function sanitizedLaunchEnv() {
  const env = { ...process.env };
  delete env.YIYU_REMOTE_CLOUD_API_URL;
  env.YIYU_PACKAGED_REMOTE_CLOUD_API_URL = DEFAULT_PACKAGED_REMOTE_CLOUD_API_URL;
  return env;
}

function run(command, args, options = {}) {
  return spawnSync(command, args, {
    stdio: options.stdio ?? 'pipe',
    encoding: 'utf8',
    env: options.env ?? sanitizedLaunchEnv(),
    ...options,
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function countAppProcesses() {
  const result = run('pgrep', ['-f', '益语智库自用平台']);
  return (result.stdout || '').trim().split('\n').filter(Boolean).length;
}

const exists = run('test', ['-d', installedApp]);
if (exists.status !== 0) {
  console.error(`[open-installed-app] installed app not found: ${installedApp}`);
  console.error('[open-installed-app] run `npm run dist:mac-local && npm run install:mac-local` first.');
  process.exit(1);
}

// 杀掉旧的 dev electron 进程
run('pkill', ['-f', rawElectronPattern], { stdio: 'ignore' });

// 方式 1: open -a
console.log('[open-installed-app] trying open -a ...');
run('open', ['-a', installedApp], { stdio: 'inherit' });
await sleep(4000);

if (countAppProcesses() >= 2) {
  console.log('[open-installed-app] launched via open -a');
  console.log(`[open-installed-app] runtime manifest: ${runtimeManifestPath}`);
  run('osascript', ['-e', 'tell application "益语智库自用平台" to activate'], { stdio: 'ignore' });
  process.exit(0);
}

// 方式 2: 直接执行二进制（Sequoia 需要 tty）
console.log('[open-installed-app] open -a failed, falling back to direct binary with tty ...');
if (!fs.existsSync(binaryPath)) {
  console.error(`[open-installed-app] binary not found: ${binaryPath}`);
  process.exit(1);
}

// 用 script -q /dev/null 模拟 tty — Electron 在 macOS Sequoia 上需要 tty 才能正常启动
const child = spawn('script', ['-q', '/dev/null', binaryPath], {
  detached: true,
  stdio: 'ignore',
  env: sanitizedLaunchEnv(),
});
child.unref();
console.log(`[open-installed-app] launched via script+binary (pid: ${child.pid})`);
console.log(`[open-installed-app] runtime manifest: ${runtimeManifestPath}`);
