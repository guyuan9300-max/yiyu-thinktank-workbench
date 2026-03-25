#!/usr/bin/env node

import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const APP_NAME = '益语智库自用平台.app';
const projectRoot = path.resolve(new URL('..', import.meta.url).pathname);
const installedApp = path.join(os.homedir(), 'Applications', APP_NAME);
const rawElectronPattern = `${projectRoot}/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron \\.`;

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: options.stdio ?? 'pipe',
    encoding: 'utf8',
    ...options,
  });
  return result;
}

const exists = run('test', ['-d', installedApp]);
if (exists.status !== 0) {
  console.error(`[open-installed-app] installed app not found: ${installedApp}`);
  console.error('[open-installed-app] run `npm run dist:mac-local && npm run install:mac-local` first.');
  process.exit(1);
}

run('pkill', ['-f', rawElectronPattern], { stdio: 'ignore' });
run('open', ['-a', installedApp], { stdio: 'inherit' });
run('osascript', ['-e', 'tell application "益语智库自用平台" to activate'], { stdio: 'ignore' });
