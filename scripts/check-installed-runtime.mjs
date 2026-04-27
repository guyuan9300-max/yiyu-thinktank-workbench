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
  inspectBackendCapabilities,
  inspectAppBundle as inspectBundle,
} from './app-manifest.mjs';

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const defaultSourceApp = path.join(projectRoot, 'dist', 'mac-arm64', APP_NAME);
const targetApp = path.join(os.homedir(), 'Applications', APP_NAME);
const targetBinary = path.join(targetApp, 'Contents', 'MacOS', APP_DISPLAY_NAME);
const runtimeBackendPython = path.join(
  os.homedir(),
  'Library',
  'Application Support',
  'YiyuThinkTankWorkbench2',
  'runtime',
  'backend-venv',
  'bin',
  'python',
);
const defaultBaseUrl = process.env.YIYU_BACKEND_URL || 'http://127.0.0.1:47829';
const defaultOutput = DEFAULT_INSTALL_SMOKE_PATH;
const defaultLaunchTimeoutSeconds = 90;

function parseArgs(argv) {
  const options = {
    sourceApp: defaultSourceApp,
    baseUrl: defaultBaseUrl,
    output: defaultOutput,
    launchTimeoutSeconds: defaultLaunchTimeoutSeconds,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    const next = argv[index + 1];
    if (current === '--source-app') {
      if (!next) {
        throw new Error('missing value for --source-app');
      }
      options.sourceApp = path.resolve(next);
      index += 1;
      continue;
    }
    if (current.startsWith('--source-app=')) {
      options.sourceApp = path.resolve(current.slice('--source-app='.length));
      continue;
    }
    if (current === '--base-url') {
      if (!next) {
        throw new Error('missing value for --base-url');
      }
      options.baseUrl = next;
      index += 1;
      continue;
    }
    if (current.startsWith('--base-url=')) {
      options.baseUrl = current.slice('--base-url='.length);
      continue;
    }
    if (current === '--output') {
      if (!next) {
        throw new Error('missing value for --output');
      }
      options.output = path.resolve(next);
      index += 1;
      continue;
    }
    if (current.startsWith('--output=')) {
      options.output = path.resolve(current.slice('--output='.length));
      continue;
    }
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
    throw new Error(`unknown option: ${current}`);
  }
  if (!Number.isFinite(options.launchTimeoutSeconds) || options.launchTimeoutSeconds <= 0) {
    throw new Error(`invalid --launch-timeout-seconds value: ${options.launchTimeoutSeconds}`);
  }
  return options;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function run(command, args, options = {}) {
  return spawnSync(command, args, {
    encoding: 'utf8',
    stdio: options.stdio ?? 'pipe',
    env: options.env ?? process.env,
    ...options,
  });
}

function runText(command, args, options = {}) {
  const result = run(command, args, options);
  return {
    status: result.status ?? 0,
    stdout: result.stdout || '',
    stderr: result.stderr || '',
    error: result.error || null,
  };
}

function writeJson(outputPath, payload) {
  const target = path.resolve(outputPath);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

function findAppPids() {
  const result = runText('pgrep', ['-f', targetBinary]);
  return result.stdout.trim().split('\n').filter(Boolean).map((value) => Number(value)).filter(Number.isInteger);
}

function getListenerInfo(port) {
  const output = runText('lsof', ['-nP', `-iTCP:${port}`, '-sTCP:LISTEN', '-Fp']);
  const pid = output.stdout.split('\n')
    .find((line) => line.startsWith('p') && line.slice(1).trim())
    ?.slice(1);
  if (!pid) {
    return { pid: null, command: null };
  }
  const command = runText('ps', ['-p', pid, '-o', 'command=']).stdout.trim() || null;
  return {
    pid: Number(pid),
    command,
  };
}

function listenerMatchesInstalledRuntime(command) {
  return Boolean(command && command.includes(runtimeBackendPython));
}

function stopInstalledApp() {
  run('osascript', ['-e', `tell application "${APP_DISPLAY_NAME}" to quit`], { stdio: 'ignore' });
  run('pkill', ['-x', APP_DISPLAY_NAME], { stdio: 'ignore' });
  run('pkill', ['-f', targetBinary], { stdio: 'ignore' });
  const waitResult = run('bash', ['-lc', `for _ in {1..40}; do pgrep -f '${targetBinary.replace(/'/g, `'\\''`)}' >/dev/null || exit 0; sleep 0.25; done; exit 1`], { stdio: 'ignore' });
  return waitResult.status === 0;
}

function stopExpectedBackendListener(port) {
  const listener = getListenerInfo(port);
  if (!listener.pid) {
    return { cleared: true, reason: null };
  }
  if (!listenerMatchesInstalledRuntime(listener.command)) {
    return {
      cleared: false,
      reason: `47829 已被非安装版 runtime 进程占用：${listener.command || listener.pid}`,
    };
  }
  run('kill', ['-TERM', String(listener.pid)], { stdio: 'ignore' });
  const waitResult = run('bash', ['-lc', `for _ in {1..40}; do lsof -nP -iTCP:${port} -sTCP:LISTEN >/dev/null || exit 0; sleep 0.25; done; exit 1`], { stdio: 'ignore' });
  if (waitResult.status !== 0) {
    return {
      cleared: false,
      reason: `无法清理旧的 47829 listener pid=${listener.pid}`,
    };
  }
  return { cleared: true, reason: null };
}

async function request200(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch(url, { method: 'GET', signal: controller.signal });
    return response.status === 200;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

function payloadFromState(state) {
  return {
    recordedAt: new Date().toISOString(),
    targetAppExists: state.targetAppExists,
    sourceRendererEntry: state.sourceRendererEntry,
    sourceRendererHash: state.sourceRendererHash,
    sourceBundleManifestId: state.sourceBundleManifestId,
    sourceBackendCapabilityMatch: state.sourceBackendCapabilityMatch,
    sourceBackendCapabilityMissing: state.sourceBackendCapabilityMissing,
    sourceBackendCapabilityRoot: state.sourceBackendCapabilityRoot,
    targetRendererEntry: state.targetRendererEntry,
    targetRendererHash: state.targetRendererHash,
    targetBundleManifestId: state.targetBundleManifestId,
    targetBackendCapabilityMatch: state.targetBackendCapabilityMatch,
    targetBackendCapabilityMissing: state.targetBackendCapabilityMissing,
    targetBackendCapabilityRoot: state.targetBackendCapabilityRoot,
    rendererEntryMatch: state.rendererEntryMatch,
    bundleManifestMatch: state.bundleManifestMatch,
    launchAttempted: state.launchAttempted,
    appProcessRunning: state.appProcessRunning,
    backendStartedByInstalledApp: state.backendStartedByInstalledApp,
    backendPid: state.backendPid,
    backendCommand: state.backendCommand,
    settingsMainChainStability200: state.settingsMainChainStability200,
    analysisMigrationMetrics200: state.analysisMigrationMetrics200,
    readyToResumeA0: state.readyToResumeA0,
    readyToOpenWorkbench: state.readyToOpenWorkbench,
    blockerClass: state.blockerClass,
    reason: state.reason,
  };
}

async function main() {
  let options = {
    sourceApp: defaultSourceApp,
    baseUrl: defaultBaseUrl,
    output: defaultOutput,
    launchTimeoutSeconds: defaultLaunchTimeoutSeconds,
  };
  const state = {
    targetAppExists: false,
    sourceRendererEntry: null,
    sourceRendererHash: null,
    sourceBundleManifestId: null,
    sourceBackendCapabilityMatch: false,
    sourceBackendCapabilityMissing: [],
    sourceBackendCapabilityRoot: null,
    targetRendererEntry: null,
    targetRendererHash: null,
    targetBundleManifestId: null,
    targetBackendCapabilityMatch: false,
    targetBackendCapabilityMissing: [],
    targetBackendCapabilityRoot: null,
    rendererEntryMatch: false,
    bundleManifestMatch: false,
    launchAttempted: false,
    appProcessRunning: false,
    backendStartedByInstalledApp: false,
    backendPid: null,
    backendCommand: null,
    settingsMainChainStability200: false,
    analysisMigrationMetrics200: false,
    readyToResumeA0: false,
    readyToOpenWorkbench: false,
    blockerClass: 'packaging',
    reason: '',
  };

  try {
    options = parseArgs(process.argv.slice(2));
    const baseUrl = options.baseUrl.replace(/\/+$/, '');
    const port = Number(new URL(baseUrl).port || '80');
    const sourceInfo = inspectBundle(options.sourceApp);
    const targetInfo = inspectBundle(targetApp);
    const sourceCapability = inspectBackendCapabilities(options.sourceApp);
    const targetCapability = inspectBackendCapabilities(targetApp);
    state.targetAppExists = targetInfo.exists;
    state.sourceRendererEntry = sourceInfo.rendererEntry;
    state.sourceRendererHash = sourceInfo.rendererHash;
    state.sourceBundleManifestId = sourceInfo.bundleManifestId;
    state.sourceBackendCapabilityMatch = Boolean(sourceCapability.match);
    state.sourceBackendCapabilityMissing = sourceCapability.missingSymbols;
    state.sourceBackendCapabilityRoot = sourceCapability.rootPath;
    state.targetRendererEntry = targetInfo.rendererEntry;
    state.targetRendererHash = targetInfo.rendererHash;
    state.targetBundleManifestId = targetInfo.bundleManifestId;
    state.targetBackendCapabilityMatch = Boolean(targetCapability.match);
    state.targetBackendCapabilityMissing = targetCapability.missingSymbols;
    state.targetBackendCapabilityRoot = targetCapability.rootPath;
    state.rendererEntryMatch = Boolean(
      sourceInfo.rendererEntry
        && targetInfo.rendererEntry
        && sourceInfo.rendererEntry === targetInfo.rendererEntry
    );
    state.bundleManifestMatch = Boolean(
      sourceInfo.bundleManifestId
        && targetInfo.bundleManifestId
        && sourceInfo.bundleManifestId === targetInfo.bundleManifestId
    );

    if (!state.targetAppExists) {
      state.reason = `正式安装 target app 缺失：${targetApp}`;
      return state;
    }
    if (!state.targetBackendCapabilityMatch) {
      state.reason = `当前安装包未包含顾问综合链路，请重新打包安装。missing=${state.targetBackendCapabilityMissing.join(', ') || 'unknown'}`;
      return state;
    }
    if (!state.bundleManifestMatch) {
      state.reason = `bundle manifest 不一致：source=${state.sourceBundleManifestId || 'null'} target=${state.targetBundleManifestId || 'null'}`;
      return state;
    }
    if (!state.rendererEntryMatch) {
      state.reason = `renderer 入口不一致：source=${state.sourceRendererEntry || 'null'} target=${state.targetRendererEntry || 'null'}`;
      return state;
    }

    stopInstalledApp();
    const cleanup = stopExpectedBackendListener(port);
    if (!cleanup.cleared) {
      state.reason = cleanup.reason;
      return state;
    }

    state.launchAttempted = true;
    const openScript = path.join(projectRoot, 'scripts', 'open-installed-app.mjs');
    const launch = run(
      process.execPath,
      [openScript, '--skip-validation', '--tab', 'settings', '--settings-section', 'overview'],
      { stdio: 'inherit' },
    );
    if (launch.error) {
      state.reason = `open-installed-app.mjs 执行失败：${launch.error.message}`;
      return state;
    }
    if (launch.status !== 0) {
      state.reason = `open-installed-app.mjs 退出码 ${launch.status}`;
      return state;
    }

    const deadline = Date.now() + options.launchTimeoutSeconds * 1000;
    while (Date.now() < deadline) {
      const pids = findAppPids();
      const listener = getListenerInfo(port);
      const appProcessRunning = pids.length > 0;
      const backendStartedByInstalledApp = appProcessRunning && listenerMatchesInstalledRuntime(listener.command);
      let settingsMainChainStability200 = false;
      let analysisMigrationMetrics200 = false;
      if (backendStartedByInstalledApp) {
        settingsMainChainStability200 = await request200(`${baseUrl}/api/v1/settings/main-chain-stability`);
        analysisMigrationMetrics200 = await request200(`${baseUrl}/api/v1/runtime/analysis-migration-metrics`);
      }

      state.appProcessRunning = appProcessRunning;
      state.backendStartedByInstalledApp = backendStartedByInstalledApp;
      state.backendPid = listener.pid;
      state.backendCommand = listener.command;
      state.settingsMainChainStability200 = settingsMainChainStability200;
      state.analysisMigrationMetrics200 = analysisMigrationMetrics200;

      if (appProcessRunning && backendStartedByInstalledApp && settingsMainChainStability200 && analysisMigrationMetrics200) {
        state.readyToResumeA0 = true;
        state.readyToOpenWorkbench = true;
        state.blockerClass = 'none';
        state.reason = 'installed-runtime packaging 已恢复，可回到 A0。';
        return state;
      }

      await sleep(2_000);
    }

    if (!state.appProcessRunning) {
      state.reason = '安装版启动后未保持运行。';
      return state;
    }
    if (!state.backendStartedByInstalledApp) {
      state.reason = '47829 未由安装版 runtime backend 拉起。';
      return state;
    }
    if (!state.settingsMainChainStability200) {
      state.reason = '/api/v1/settings/main-chain-stability 未返回 200。';
      return state;
    }
    if (!state.analysisMigrationMetrics200) {
      state.reason = '/api/v1/runtime/analysis-migration-metrics 未返回 200。';
      return state;
    }
    state.reason = '安装后最小冒烟未达到恢复 A0 的条件。';
    return state;
  } catch (error) {
    state.reason = error instanceof Error ? error.message : String(error);
    return state;
  } finally {
    const payload = payloadFromState(state);
    writeJson(options.output, payload);
    console.log(JSON.stringify(payload, null, 2));
  }
}

const state = await main();
if (!state.readyToResumeA0) {
  process.exit(1);
}
