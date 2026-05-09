#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import {
  APP_DISPLAY_NAME,
  APP_NAME,
  DEFAULT_INSTALL_SMOKE_PATH,
  DEFAULT_RUNTIME_EVIDENCE_DIR,
  sha256File,
  writeJsonFile,
} from './app-manifest.mjs';

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const packageJson = JSON.parse(fs.readFileSync(path.join(projectRoot, 'package.json'), 'utf8'));
const defaultDmgPath = path.join(projectRoot, 'dist', `${APP_DISPLAY_NAME}-${packageJson.version}-${process.arch}.dmg`);
const defaultOutputPath = path.join(DEFAULT_RUNTIME_EVIDENCE_DIR, 'dmg-install-smoke.json');
const installedAppPath = path.join(os.homedir(), 'Applications', APP_NAME);
const appBasename = APP_NAME.replace(/\.app$/, '');
const runtimeRoot = path.join(
  os.homedir(),
  'Library',
  'Application Support',
  'YiyuThinkTankWorkbench2',
  'runtime',
);
const runtimeResetTargets = [
  path.join(runtimeRoot, 'backend-venv'),
];

function parseArgs(argv) {
  const options = {
    dmgPath: defaultDmgPath,
    launchTimeoutSeconds: 300,
    freshRuntime: true,
    keepRunning: false,
    outputPath: defaultOutputPath,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    const next = argv[index + 1];
    if (current === '--launch-timeout-seconds') {
      if (!next) {
        throw new Error('missing value for --launch-timeout-seconds');
      }
      options.launchTimeoutSeconds = Number(next);
      index += 1;
      continue;
    }
    if (current.startsWith('--launch-timeout-seconds=')) {
      options.launchTimeoutSeconds = Number(current.slice('--launch-timeout-seconds='.length));
      continue;
    }
    if (current === '--output') {
      if (!next) {
        throw new Error('missing value for --output');
      }
      options.outputPath = path.resolve(next);
      index += 1;
      continue;
    }
    if (current.startsWith('--output=')) {
      options.outputPath = path.resolve(current.slice('--output='.length));
      continue;
    }
    if (current === '--no-fresh-runtime') {
      options.freshRuntime = false;
      continue;
    }
    if (current === '--keep-running') {
      options.keepRunning = true;
      continue;
    }
    if (current.startsWith('--')) {
      throw new Error(`unknown option: ${current}`);
    }
    options.dmgPath = path.resolve(current);
  }

  if (!Number.isFinite(options.launchTimeoutSeconds) || options.launchTimeoutSeconds <= 0) {
    throw new Error(`invalid --launch-timeout-seconds value: ${options.launchTimeoutSeconds}`);
  }
  return options;
}

function fail(message) {
  console.error(`[install-and-smoke-mac-dmg] ${message}`);
  process.exit(1);
}

function run(command, args, { stdio = 'inherit', allowFailure = false } = {}) {
  const result = spawnSync(command, args, { stdio, encoding: 'utf8' });
  if (result.error) {
    if (allowFailure) return result;
    throw new Error(`${command} failed: ${result.error.message}`);
  }
  if (result.status !== 0 && !allowFailure) {
    const detail = `${result.stdout || ''}${result.stderr || ''}`.trim();
    throw new Error(`${command} ${args.join(' ')} exited with status ${result.status}${detail ? `: ${detail}` : ''}`);
  }
  return result;
}

function removeFreshRuntimeTargets() {
  const removed = [];
  for (const targetPath of runtimeResetTargets) {
    if (!targetPath.startsWith(`${runtimeRoot}${path.sep}`)) {
      throw new Error(`refusing to remove runtime path outside runtime root: ${targetPath}`);
    }
    if (fs.existsSync(targetPath)) {
      fs.rmSync(targetPath, { recursive: true, force: true });
      removed.push(targetPath);
    }
  }
  return removed;
}

function stopInstalledApp() {
  run('osascript', ['-e', `tell application "${APP_DISPLAY_NAME}" to quit`], { stdio: 'ignore', allowFailure: true });
  run('pkill', ['-x', APP_DISPLAY_NAME], { stdio: 'ignore', allowFailure: true });
  run('pkill', ['-f', path.join(installedAppPath, 'Contents', 'MacOS', APP_DISPLAY_NAME)], {
    stdio: 'ignore',
    allowFailure: true,
  });
}

function readJsonIfExists(targetPath) {
  if (!fs.existsSync(targetPath)) {
    return null;
  }
  return JSON.parse(fs.readFileSync(targetPath, 'utf8'));
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (process.platform !== 'darwin') {
    throw new Error('This script only supports macOS.');
  }
  if (!fs.existsSync(options.dmgPath)) {
    throw new Error(`DMG not found: ${options.dmgPath}`);
  }

  const mountPoint = fs.mkdtempSync(path.join(os.tmpdir(), 'yiyu-dmg-install-smoke-'));
  const evidence = {
    recordedAt: new Date().toISOString(),
    dmgPath: options.dmgPath,
    sha256: sha256File(options.dmgPath),
    mountedAppPath: null,
    installedAppPath,
    launchTimeoutSeconds: options.launchTimeoutSeconds,
    freshRuntime: options.freshRuntime,
    clearedRuntimePaths: [],
    installSmokePath: DEFAULT_INSTALL_SMOKE_PATH,
    installSmoke: null,
    success: false,
  };
  let attached = false;

  try {
    run('hdiutil', ['verify', options.dmgPath]);
    run('hdiutil', ['attach', '-nobrowse', '-readonly', '-mountpoint', mountPoint, options.dmgPath]);
    attached = true;

    const mountedAppPath = path.join(mountPoint, APP_NAME);
    evidence.mountedAppPath = mountedAppPath;
    if (!fs.existsSync(mountedAppPath)) {
      throw new Error(`Mounted DMG does not contain app bundle: ${mountedAppPath}`);
    }

    run(process.execPath, [path.join(projectRoot, 'scripts', 'verify-packaged-app.mjs'), mountedAppPath]);
    run(process.execPath, [path.join(projectRoot, 'scripts', 'install-mac-app.mjs'), mountedAppPath]);

    if (options.freshRuntime) {
      evidence.clearedRuntimePaths = removeFreshRuntimeTargets();
    }

    run(process.execPath, [
      path.join(projectRoot, 'scripts', 'check-installed-runtime.mjs'),
      '--source-app',
      mountedAppPath,
      '--force-relaunch',
      '--launch-timeout-seconds',
      String(options.launchTimeoutSeconds),
      '--output',
      DEFAULT_INSTALL_SMOKE_PATH,
    ]);

    evidence.installSmoke = readJsonIfExists(DEFAULT_INSTALL_SMOKE_PATH);
    evidence.success = Boolean(evidence.installSmoke?.readyToOpenWorkbench);
    if (!evidence.success) {
      throw new Error(`installed app smoke failed: ${evidence.installSmoke?.reason || 'unknown'}`);
    }

    writeJsonFile(options.outputPath, evidence);
    console.log(JSON.stringify(evidence, null, 2));
  } finally {
    if (!options.keepRunning) {
      stopInstalledApp();
    }
    if (attached) {
      run('hdiutil', ['detach', mountPoint], { allowFailure: true });
    }
    fs.rmSync(mountPoint, { recursive: true, force: true });
  }
}

main().catch((error) => {
  fail(error instanceof Error ? error.message : String(error));
});
