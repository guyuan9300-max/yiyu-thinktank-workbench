#!/usr/bin/env node

import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';
import {
  APP_DISPLAY_NAME,
  APP_NAME,
  DEFAULT_INSTALL_SMOKE_PATH,
  DEFAULT_PACKAGED_REMOTE_CLOUD_API_URL,
  DEFAULT_WORKSPACE_CHAT_SMOKE_PATH,
  inspectAppBundle,
} from './app-manifest.mjs';

const projectRoot = path.resolve(new URL('..', import.meta.url).pathname);
const installedApp = path.join(os.homedir(), 'Applications', APP_NAME);
const binaryPath = path.join(installedApp, 'Contents', 'MacOS', APP_DISPLAY_NAME);
const rawElectronPattern = `${projectRoot}/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron \\.`;
const RENDERER_QUERY_ARG = '--yiyu-renderer-query';

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

function runOrFail(command, args, options = {}) {
  const result = run(command, args, options);
  if (result.error) {
    throw new Error(`${command} failed: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`${command} exited with status ${result.status}`);
  }
  return result;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function countAppProcesses() {
  const result = run('pgrep', ['-f', APP_DISPLAY_NAME]);
  return (result.stdout || '').trim().split('\n').filter(Boolean).length;
}

function parseArgs(argv) {
  const queryParams = new URLSearchParams();
  let skipValidation = false;
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    if (current === '--skip-validation') {
      skipValidation = true;
      continue;
    }
    if (current === '--tab') {
      const value = argv[index + 1];
      if (value) {
        queryParams.set('tab', value);
        index += 1;
      }
      continue;
    }
    if (current === '--settings-section') {
      const value = argv[index + 1];
      if (value) {
        queryParams.set('settingsSection', value);
        index += 1;
      }
      continue;
    }
    if (current === '--query') {
      const value = argv[index + 1];
      if (value) {
        for (const [key, paramValue] of new URLSearchParams(value.replace(/^\?+/, ''))) {
          queryParams.set(key, paramValue);
        }
        index += 1;
      }
      continue;
    }
    throw new Error(`unknown option: ${current}`);
  }
  const serialized = queryParams.toString();
  return {
    skipValidation,
    launchArgs: serialized ? [`${RENDERER_QUERY_ARG}=${serialized}`] : [],
  };
}

async function launchInstalledApp(launchArgs) {
  const exists = run('test', ['-d', installedApp]);
  if (exists.status !== 0) {
    throw new Error(`installed app not found: ${installedApp}`);
  }

  run('pkill', ['-f', rawElectronPattern], { stdio: 'ignore' });

  console.log('[open-installed-app] trying open -a ...');
  const openArgs = ['-na', installedApp, ...(launchArgs.length > 0 ? ['--args', ...launchArgs] : [])];
  run('open', openArgs, { stdio: 'inherit' });
  await sleep(4000);

  if (countAppProcesses() >= 2) {
    console.log('[open-installed-app] launched via open -a');
    run('osascript', ['-e', `tell application "${APP_DISPLAY_NAME}" to activate`], { stdio: 'ignore' });
    return;
  }

  console.log('[open-installed-app] open -a failed, falling back to direct binary with tty ...');
  if (!fs.existsSync(binaryPath)) {
    throw new Error(`binary not found: ${binaryPath}`);
  }

  const child = spawn('script', ['-q', '/dev/null', binaryPath, ...launchArgs], {
    detached: true,
    stdio: 'ignore',
    env: sanitizedLaunchEnv(),
  });
  child.unref();
  console.log(`[open-installed-app] launched via script+binary (pid: ${child.pid})`);
}

function ensureLatestInstalledBundle(sourceApp) {
  const sourceExists = fs.existsSync(sourceApp);
  const targetExists = fs.existsSync(installedApp);
  const sourceInfo = sourceExists ? inspectAppBundle(sourceApp) : null;
  const targetInfo = targetExists ? inspectAppBundle(installedApp) : null;

  if (!targetExists && !sourceExists) {
    throw new Error('installed app missing and no source dist app found. run `npm run dist:mac-local` first.');
  }
  if (!sourceExists) {
    return installedApp;
  }
  if (!sourceInfo?.bundleManifestId) {
    throw new Error(`source app manifest missing or invalid: ${sourceApp}`);
  }
  if (targetInfo?.bundleManifestId === sourceInfo.bundleManifestId) {
    return installedApp;
  }

  console.log('[open-installed-app] installed app is stale or missing, reinstalling latest local bundle ...');
  runOrFail(process.execPath, [path.join(projectRoot, 'scripts', 'install-mac-app.mjs'), sourceApp], { stdio: 'inherit' });
  return installedApp;
}

function runValidation(sourceApp) {
  runOrFail(
    process.execPath,
    [
      path.join(projectRoot, 'scripts', 'check-installed-runtime.mjs'),
      '--source-app',
      sourceApp,
      '--output',
      DEFAULT_INSTALL_SMOKE_PATH,
    ],
    { stdio: 'inherit' },
  );
  runOrFail(
    'python3',
    [
      path.join(projectRoot, 'scripts', 'smoke_workspace_chat_generation.py'),
      '--backend-url',
      process.env.YIYU_BACKEND_URL || 'http://127.0.0.1:47829',
      '--output',
      DEFAULT_WORKSPACE_CHAT_SMOKE_PATH,
    ],
    { stdio: 'inherit' },
  );
}

const { skipValidation, launchArgs } = parseArgs(process.argv.slice(2));

if (skipValidation) {
  await launchInstalledApp(launchArgs);
  process.exit(0);
}

const sourceApp = path.join(projectRoot, 'dist', 'mac-arm64', APP_NAME);
const validationSourceApp = fs.existsSync(sourceApp) ? sourceApp : installedApp;

ensureLatestInstalledBundle(sourceApp);
runValidation(validationSourceApp);
console.log('[open-installed-app] verified install receipt + install smoke + workspace chat smoke');
