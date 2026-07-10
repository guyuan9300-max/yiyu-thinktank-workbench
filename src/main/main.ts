import { writeFileSync, appendFileSync, mkdirSync } from 'node:fs';
try { appendFileSync('/tmp/yiyu-thinktank-electron-bootstrap.log', `[${new Date().toISOString()}] [PROBE] main.ts top-of-file reached\n`); } catch {}
import { app, BrowserWindow, dialog, ipcMain, protocol, screen, shell } from 'electron';
try { appendFileSync('/tmp/yiyu-thinktank-electron-bootstrap.log', `[${new Date().toISOString()}] [PROBE] electron imported OK\n`); } catch {}
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import http from 'node:http';
import net from 'node:net';
import type {
  DesktopAppInfo,
  DesktopStartupGateResumeResult,
} from '../shared/types.js';
import { buildRendererLaunchQuery } from '../shared/rendererLaunchQuery.js';
import {
  buildDesktopAppInfo,
  type BackendHealthPayload,
} from './runtimeManifest.js';
import { setupAutoUpdater, setUpdateOrgCode, setUpdateOrgIdentity } from './autoUpdater.js';
import type { UpdateOrgIdentity } from './autoUpdater.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// V2.1 Lab 模式 (顾源源 5/22 方案 C): ENV YIYU_LAB_MODE=1 触发, 跟主仓库 app 物理隔离
// - 端口避开主仓库 47829/47830, 用 47831/47832
// - userData 独立到 YiyuThinkTankWorkbench2_V21Lab, db 不冲突
// - bundle id + display name 不同, macOS Electron 允许双 app 同跑
// - 默认 (无 ENV) 行为完全跟主仓库一致, cherry-pick 主仓库 bug fix 不破坏
const LAB_MODE = process.env.YIYU_LAB_MODE === '1';
const COLLAB_PREVIEW_MODE = process.env.YIYU_COLLAB_PREVIEW_MODE === '1';
const DEFAULT_BACKEND_PORT = LAB_MODE ? 47831 : 47829;
const DEFAULT_CLOUD_BACKEND_PORT = LAB_MODE ? 47832 : 47830;
const DEFAULT_PACKAGED_REMOTE_CLOUD_API_URL = '';
const projectRoot = path.resolve(__dirname, '../..');
const isDev = !app.isPackaged && Boolean(process.env.VITE_DEV_SERVER_URL);
const REQUIRED_BACKEND_FEATURES = ['knowledge.vectorize-answer', 'knowledge.reclass-events', 'chat.general-answer', 'chat.async-status'];
const REQUIRED_BACKEND_SCHEMA_VERSION = 20260420;
const APP_DISPLAY_NAME = COLLAB_PREVIEW_MODE ? '益语智库 协作预览' : LAB_MODE ? '益语智库 V2.1 Lab' : '益语智库自用平台 V2.0';
const APP_BUNDLE_ID = COLLAB_PREVIEW_MODE ? 'com.yiyu.selfworkbench2.collabpreview' : LAB_MODE ? 'com.yiyu.selfworkbench2.v21lab' : 'com.yiyu.selfworkbench2';
const releasePlanPath = path.join(projectRoot, 'docs', 'mac-release-update-plan.md');
const releaseArtifactsPath = path.join(projectRoot, 'dist');
const USER_DATA_DIR_NAME = COLLAB_PREVIEW_MODE ? 'YiyuThinkTankWorkbench2_CollabPreview' : LAB_MODE ? 'YiyuThinkTankWorkbench2_V21Lab' : 'YiyuThinkTankWorkbench2';
const explicitDevUserDataPath = !app.isPackaged && process.env.YIYU_WORKBENCH_DATA_DIR
  ? path.resolve(process.env.YIYU_WORKBENCH_DATA_DIR)
  : '';
const fixedUserDataPath = explicitDevUserDataPath
  ? explicitDevUserDataPath
  : path.join(app.getPath('appData'), USER_DATA_DIR_NAME);
const runtimeLogsDir = path.join(fixedUserDataPath, 'runtime', 'logs');
const runtimeUiDir = path.join(fixedUserDataPath, 'runtime', 'ui');
const electronLaunchLogPath = path.join(runtimeLogsDir, 'electron-launch.log');
const collabRebuildLogPath = path.join(runtimeLogsDir, 'collab-rebuild.log');
const emergencyBootstrapLogPath = '/tmp/yiyu-thinktank-electron-bootstrap.log';
const savedApplicationStatePath = path.join(app.getPath('home'), 'Library', 'Saved Application State', `${APP_BUNDLE_ID}.savedState`);
app.setName(APP_DISPLAY_NAME);
app.setPath('userData', fixedUserDataPath);
// V2.1 Lab 版本号: 默认 0.2.2 (主仓库) + LAB_MODE 加后缀 ".1" → 0.2.2.1
// 顾源源 5/22 要求: 关于本软件页面要看到 0.2.2.1, 区分双 app
const APP_VERSION_DISPLAY = LAB_MODE ? `${app.getVersion()}.1` : app.getVersion();
app.setAboutPanelOptions({
  applicationName: APP_DISPLAY_NAME,
  applicationVersion: APP_VERSION_DISPLAY,
  version: APP_VERSION_DISPLAY,
});

type RuntimeSyncMetadata = {
  fingerprint: string;
  syncedAt: string;
  project: 'backend' | 'cloud_backend';
};

type PackagedRuntimeSeedManifest = {
  schemaVersion?: number;
  platform?: string;
  arch?: string;
  python?: {
    executable?: string;
    version?: string;
    treeSha256?: string;
    stdlibCheck?: string;
    dynamicLibrary?: string | null;
    venvPython?: string;
    venvUvicorn?: string;
    venvScriptsDir?: string;
  };
  backend?: {
    requirementsPath?: string;
    requirementsSha256?: string;
    pyprojectSha256?: string;
    uvLockSha256?: string;
  };
  wheelhouse?: {
    path?: string;
    sha256?: string;
    fileCount?: number;
  };
  // B 方案:预装 venv 元数据
  backendVenv?: {
    path?: string;
    sha256?: string;
    fileCount?: number;
  };
};

type PackagedRuntimeSeed = {
  root: string;
  manifestPath: string;
  manifest: PackagedRuntimeSeedManifest;
  seedPython: string;
  requirementsPath: string;
  wheelhousePath: string;
  // B 方案:预装的 backend-venv 目录在 .app bundle 内的绝对路径
  // 客户机首次启动直接复制这个目录,不再 pip install
  backendVenvPath: string;
};

let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcessWithoutNullStreams | null = null;
let cloudBackendProcess: ChildProcessWithoutNullStreams | null = null;
let rendererStaticServer: http.Server | null = null;
let rendererProtocolRegistered = false;
let backendPort = DEFAULT_BACKEND_PORT;
let cloudBackendPort = DEFAULT_CLOUD_BACKEND_PORT;
let rendererPort = 4173;
let uvBinaryPath: string | null = null;
let backendRuntimeVenv = '';
let cloudBackendRuntimeVenv = '';
let ownsBackendProcess = false;
let ownsCloudBackendProcess = false;
let backendExitDetail: string | null = null;
const backendRecentLogLines: string[] = [];
let latestDesktopAppInfo: DesktopAppInfo | null = null;
const LOCAL_DEV_CLOUD_SEED_ENV_KEYS = [
  'YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD',
  'YIYU_CLOUD_BOOTSTRAP_ADMIN_EMAIL',
  'YIYU_CLOUD_INSECURE_SEED_PASSWORDS',
  'YIYU_CLOUD_SECRET_KEY',
] as const;
const platformDnaExtractorScriptPath = path.join(projectRoot, 'backend', 'scripts', 'extract_platform_dna_text.py');
const legacyAppBasenames = new Set(['益语智库.app', '益语智库工作台.app']);
const staleInstallBundlePrefix = `.${APP_DISPLAY_NAME}.installing-`;
const RENDERER_QUERY_ARG = '--yiyu-renderer-query';
const PACKAGED_RUNTIME_MANIFEST_FILE = 'runtime-seed-manifest.json';
const PACKAGED_RUNTIME_REQUIREMENTS_FILE = 'backend-requirements.txt';
const PACKAGED_RUNTIME_WHEELHOUSE_DIR = 'wheelhouse';
const PACKAGED_RUNTIME_PYTHON_SEED_DIR = 'python-seed';
// B 方案:预装 backend-venv 目录名,跟 scripts/app-manifest.mjs 的 RUNTIME_BACKEND_VENV_DIR 对齐
const PACKAGED_RUNTIME_BACKEND_VENV_DIR = 'backend-venv-prebuilt';

function normalizeHttpUrl(rawUrl?: string | null) {
  const trimmed = rawUrl?.trim();
  if (!trimmed) return null;
  return trimmed.replace(/\/+$/, '');
}

function readPackagedOfficialCloudConfig() {
  if (!app.isPackaged) return null;
  try {
    const configPath = path.join(process.resourcesPath, 'official-cloud.json');
    const parsed = JSON.parse(fs.readFileSync(configPath, 'utf8')) as { cloudApiUrl?: string };
    return parsed.cloudApiUrl || null;
  } catch {
    return null;
  }
}

function localDevCloudSeedEnv() {
  const env: NodeJS.ProcessEnv = {};
  for (const key of LOCAL_DEV_CLOUD_SEED_ENV_KEYS) {
    const value = process.env[key]?.trim();
    if (value) {
      env[key] = value;
    }
  }
  return env;
}

function remoteCloudBackendUrl() {
  const configuredUrl = (
    normalizeHttpUrl(process.env.YIYU_REMOTE_CLOUD_API_URL)
    || normalizeHttpUrl(process.env.YIYU_PACKAGED_REMOTE_CLOUD_API_URL)
    || normalizeHttpUrl(readPackagedOfficialCloudConfig())
  );
  if (configuredUrl) {
    return configuredUrl;
  }
  return app.isPackaged ? DEFAULT_PACKAGED_REMOTE_CLOUD_API_URL : null;
}

function shouldUseRemoteCloudBackend() {
  return Boolean(remoteCloudBackendUrl());
}

function shouldUseBundledLocalCloudBackend() {
  return !app.isPackaged && !shouldUseRemoteCloudBackend();
}

function rendererLaunchQuery() {
  const inlineArg = process.argv.find((value) => value.startsWith(`${RENDERER_QUERY_ARG}=`));
  const rawValue = (
    inlineArg?.slice(`${RENDERER_QUERY_ARG}=`.length)
    || (() => {
      const argIndex = process.argv.indexOf(RENDERER_QUERY_ARG);
      return argIndex >= 0 ? process.argv[argIndex + 1] : '';
    })()
    || process.env.YIYU_RENDERER_QUERY
    || ''
  ).trim();
  return buildRendererLaunchQuery(rawValue, { packaged: app.isPackaged });
}

function appendElectronLaunchLog(level: 'INFO' | 'ERROR', message: string) {
  try {
    fs.mkdirSync(runtimeLogsDir, { recursive: true });
    const timestamp = new Date().toISOString();
    fs.appendFileSync(electronLaunchLogPath, `[${timestamp}] [${level}] ${message}\n`, 'utf8');
    fs.appendFileSync(emergencyBootstrapLogPath, `[${timestamp}] [${level}] ${message}\n`, 'utf8');
  } catch {
    // Logging should never crash app startup.
  }
}

const _stdioErrorHandled = new WeakSet<NodeJS.WriteStream>();
function writeProcessStreamSafely(stream: NodeJS.WriteStream | undefined, text: string) {
  if (!stream) return;
  if ('destroyed' in stream && stream.destroyed) return;
  if (typeof stream.writable === 'boolean' && !stream.writable) return;
  // EPIPE 在写 stdio 时是异步从底层 socket 抛上来的（afterWriteDispatched），
  // 同步 try/catch 抓不到 —— 必须在 stream 上挂 'error' 监听器先吞掉。
  // 一次进程生命周期内每个 stream 只挂一次。
  if (!_stdioErrorHandled.has(stream)) {
    _stdioErrorHandled.add(stream);
    stream.on('error', () => {
      // stdout/stderr pipe 被父进程关闭后写入会触发，日志失败不影响 app 运行。
    });
  }
  try {
    stream.write(text, (err) => {
      // write callback 形式：异步 EPIPE 在这里也会被吞掉，不再冒泡到 uncaught。
      void err;
    });
  } catch {
    // 极端情况下 sync 抛错的兜底
  }
}

function logElectronInfo(message: string) {
  appendElectronLaunchLog('INFO', message);
  writeProcessStreamSafely(process.stdout, `${message}\n`);
}

function logElectronError(message: string) {
  appendElectronLaunchLog('ERROR', message);
  writeProcessStreamSafely(process.stderr, `${message}\n`);
}

type WorkspaceInteractionState = {
  active: boolean;
  source: string;
  detail?: string | null;
  updatedAt: string;
};

type QuitRequestMetadata = Record<string, unknown>;

let workspaceInteractionState: WorkspaceInteractionState = {
  active: false,
  source: 'startup',
  detail: null,
  updatedAt: new Date().toISOString(),
};
let lastQuitRequest: {
  reason: string;
  source: string;
  metadata: QuitRequestMetadata;
  requestedAt: string;
} | null = null;

function currentRendererUrl() {
  try {
    return mainWindow && !mainWindow.isDestroyed() ? mainWindow.webContents.getURL() : null;
  } catch {
    return null;
  }
}

function isStartupGatePageActive() {
  const url = currentRendererUrl() || '';
  return url.includes('__startup_gate_blocked__.html');
}

function requestAppQuit(reason: string, source: string, metadata: QuitRequestMetadata = {}) {
  lastQuitRequest = {
    reason,
    source,
    metadata: {
      ...metadata,
      rendererUrl: currentRendererUrl(),
      workspaceInteractionActive: workspaceInteractionState.active,
      workspaceInteractionSource: workspaceInteractionState.source,
      workspaceInteractionDetail: workspaceInteractionState.detail || null,
    },
    requestedAt: new Date().toISOString(),
  };
  appendElectronLaunchLog('INFO', `[app:quit-request] ${JSON.stringify(lastQuitRequest)}`);
  app.quit();
}

function shouldDeferDangerousRestart() {
  return workspaceInteractionState.active && !isStartupGatePageActive();
}

function rememberBackendLogLine(line: string) {
  const trimmed = line.trim();
  if (!trimmed) return;
  backendRecentLogLines.push(trimmed);
  if (backendRecentLogLines.length > 40) {
    backendRecentLogLines.splice(0, backendRecentLogLines.length - 40);
  }
}

function getCollabSuggestedCandidates() {
  const visibleWorkspaceRepo = path.join(app.getPath('home'), 'openclaw', 'workspace', 'yiyu-thinktank-workbench');
  const hiddenWorkspaceRepo = path.join(app.getPath('home'), '.openclaw', 'workspace', 'yiyu-thinktank-workbench');
  return [
    path.join(app.getPath('desktop'), '2.1同步'),
    visibleWorkspaceRepo,
    hiddenWorkspaceRepo,
    path.join(path.dirname(projectRoot), 'yiyu-thinktank-workbench'),
    path.join(app.getPath('documents'), 'yiyu-thinktank-workbench'),
    path.join(app.getPath('desktop'), 'yiyu-thinktank-workbench'),
  ];
}

type InternalCollabGitModule = typeof import('./collabGit.js');
let internalCollabGitModulePromise: Promise<InternalCollabGitModule> | null = null;

async function loadInternalCollabGit() {
  internalCollabGitModulePromise ??= import('./collabGit.js');
  return internalCollabGitModulePromise;
}

function resolveBundlePath(executablePath: string) {
  let current = path.resolve(executablePath);
  while (current !== path.dirname(current)) {
    if (current.endsWith('.app')) return current;
    current = path.dirname(current);
  }
  return executablePath;
}

async function readBundleId(appBundlePath: string) {
  const plistPath = path.join(appBundlePath, 'Contents', 'Info.plist');
  const raw = await fs.promises.readFile(plistPath, 'utf8').catch(() => '');
  const bundleIdMatch = raw.match(/<key>CFBundleIdentifier<\/key>\s*<string>([^<]+)<\/string>/);
  return bundleIdMatch?.[1]?.trim() || '';
}

async function scanApplicationDirectory(baseDir: string) {
  const entries = await fs.promises.readdir(baseDir, { withFileTypes: true }).catch(() => []);
  return entries
    .filter((entry) => entry.isDirectory() && entry.name.endsWith('.app'))
    .map((entry) => path.join(baseDir, entry.name));
}

async function collectInstalledAppPaths(currentAppBundlePath: string) {
  const candidates = new Set<string>();
  const userApplications = path.join(app.getPath('home'), 'Applications');
  const scanDirs = [
    '/Applications',
    userApplications,
    path.join(fixedUserDataPath, 'runtime', 'local-electron'),
    path.join(fixedUserDataPath, 'runtime', 'local-electron-dist'),
  ];
  for (const baseDir of scanDirs) {
    const found = await scanApplicationDirectory(baseDir);
    for (const targetPath of found) {
      const baseName = path.basename(targetPath);
      if (!baseName.includes('益语智库')) continue;
      candidates.add(targetPath);
    }
  }
  candidates.add(currentAppBundlePath);
  return Array.from(candidates).sort((left, right) => left.localeCompare(right, 'zh-Hans-CN'));
}

async function cleanupStaleInstallBundles() {
  const userApplications = path.join(app.getPath('home'), 'Applications');
  const removedPaths: string[] = [];
  const entries = await fs.promises.readdir(userApplications, { withFileTypes: true }).catch(() => []);
  for (const entry of entries) {
    if (!entry.isDirectory() || !entry.name.startsWith(staleInstallBundlePrefix) || !entry.name.endsWith('.app')) {
      continue;
    }
    const targetPath = path.join(userApplications, entry.name);
    try {
      await fs.promises.rm(targetPath, { recursive: true, force: true });
      removedPaths.push(targetPath);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      logElectronError(`[install-cleanup] failed to remove stale bundle ${targetPath}: ${detail}`);
    }
  }
  if (removedPaths.length > 0) {
    logElectronInfo(`[install-cleanup] removed ${removedPaths.length} stale install bundle(s)`);
  }
  return removedPaths;
}

protocol.registerSchemesAsPrivileged([
  {
    scheme: 'app',
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
      stream: true,
    },
  },
]);

async function runTaskWindowDiagnostics(window: BrowserWindow) {
  if (!parseBooleanEnv(process.env.YIYU_ELECTRON_TASK_DIAGNOSTICS, false)) return;

  const inspectEvidenceQuery = async () => window.webContents.executeJavaScript(`
    (() => {
      const params = new URLSearchParams(window.location.search);
      const evidenceMode = params.get('evidenceMode');
      if (!evidenceMode) return null;
      const bodyText = document.body?.innerText || '';
      return {
        tab: params.get('tab') || params.get('activeTab') || '',
        evidenceMode,
        taskId: params.get('taskId') || '',
        clientId: params.get('clientId') || '',
        hasRcEvidenceLabel: bodyText.includes('RC Evidence'),
        bodySnippet: bodyText.slice(0, 600),
      };
    })()
  `, true);

  const inspectTargets = async () => window.webContents.executeJavaScript(`
    (() => {
      const findButton = (label) => Array.from(document.querySelectorAll('button'))
        .find((button) => (button.textContent || '').replace(/\\s+/g, '').includes(label.replace(/\\s+/g, '')));
      const findNavButton = (label) => Array.from(document.querySelectorAll('button'))
        .find((button) => (button.textContent || '').replace(/\\s+/g, '').includes(label.replace(/\\s+/g, '')));
      const summarize = (label) => {
        const button = findButton(label);
        if (!button) return { label, found: false };
        const rect = button.getBoundingClientRect();
        const style = window.getComputedStyle(button);
        const centerX = Math.round(rect.left + rect.width / 2);
        const centerY = Math.round(rect.top + rect.height / 2);
        const hitTarget = document.elementFromPoint(centerX, centerY);
        return {
          label,
          found: true,
          centerX,
          centerY,
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          pointerEvents: style.pointerEvents,
          text: (button.textContent || '').trim(),
          hitTargetTag: hitTarget?.tagName || null,
          hitTargetText: (hitTarget?.textContent || '').trim().slice(0, 40),
          hitTargetClass: typeof hitTarget?.className === 'string' ? hitTarget.className.slice(0, 120) : null,
        };
      };

      return {
        heading: document.querySelector('h1')?.textContent || '',
        bodyIncludesToday: document.body.innerText.includes('今天'),
        navTaskButton: (() => {
          const button = findNavButton('任务与日程');
          if (!button) return { found: false };
          const rect = button.getBoundingClientRect();
          return {
            found: true,
            centerX: Math.round(rect.left + rect.width / 2),
            centerY: Math.round(rect.top + rect.height / 2),
            text: (button.textContent || '').trim(),
          };
        })(),
        targets: [
          summarize('我的月历'),
          summarize('任务列表'),
          summarize('新建任务'),
        ],
      };
    })()
  `, true);

  const clickAt = async (x: number, y: number) => {
    window.webContents.sendInputEvent({ type: 'mouseMove', x, y });
    window.webContents.sendInputEvent({ type: 'mouseDown', x, y, button: 'left', clickCount: 1 });
    window.webContents.sendInputEvent({ type: 'mouseUp', x, y, button: 'left', clickCount: 1 });
    await new Promise((resolve) => setTimeout(resolve, 250));
  };

  try {
    const evidenceQuery = await inspectEvidenceQuery() as null | {
      tab: string;
      evidenceMode: string;
      taskId: string;
      clientId: string;
      hasRcEvidenceLabel: boolean;
      bodySnippet: string;
    };
    if (evidenceQuery) {
      logElectronInfo(`[renderer:task-diagnostics] evidence=${JSON.stringify(evidenceQuery)}`);
      return;
    }

    const before = await inspectTargets() as {
      heading: string;
      bodyIncludesToday: boolean;
      navTaskButton: { found: boolean; centerX?: number; centerY?: number; text?: string };
      targets: Array<{ label: string; found: boolean; centerX?: number; centerY?: number; pointerEvents?: string }>;
    };
    logElectronInfo(`[renderer:task-diagnostics] before=${JSON.stringify(before)}`);

    const navTaskButton = before.navTaskButton && before.navTaskButton.found && before.navTaskButton.centerX !== undefined && before.navTaskButton.centerY !== undefined
      ? before.navTaskButton
      : null;
    if (navTaskButton && navTaskButton.centerX !== undefined && navTaskButton.centerY !== undefined) {
      await clickAt(navTaskButton.centerX, navTaskButton.centerY);
    }

    const onTasksPage = await inspectTargets() as {
      heading: string;
      bodyIncludesToday: boolean;
      targets: Array<{ label: string; found: boolean; centerX?: number; centerY?: number; pointerEvents?: string }>;
    };
    logElectronInfo(`[renderer:task-diagnostics] onTasksPage=${JSON.stringify(onTasksPage)}`);

    const calendarTarget = onTasksPage.targets.find((item) => item.label === '我的月历' && item.found && item.centerX !== undefined && item.centerY !== undefined);
    if (calendarTarget && calendarTarget.centerX !== undefined && calendarTarget.centerY !== undefined) {
      await clickAt(calendarTarget.centerX, calendarTarget.centerY);
    }

    const afterCalendar = await window.webContents.executeJavaScript(`
      (() => ({
        bodyIncludesToday: document.body.innerText.includes('今天'),
        bodyIncludesMonthTitle: document.body.innerText.includes('我的月历'),
      }))()
    `, true);
    logElectronInfo(`[renderer:task-diagnostics] afterCalendar=${JSON.stringify(afterCalendar)}`);

    const listTargetPayload = await inspectTargets() as {
      targets: Array<{ label: string; found: boolean; centerX?: number; centerY?: number }>;
    };
    const listTarget = listTargetPayload.targets.find((item) => item.label === '任务列表' && item.found && item.centerX !== undefined && item.centerY !== undefined);
    if (listTarget && listTarget.centerX !== undefined && listTarget.centerY !== undefined) {
      await clickAt(listTarget.centerX, listTarget.centerY);
    }

    const createTargetPayload = await inspectTargets() as {
      targets: Array<{ label: string; found: boolean; centerX?: number; centerY?: number }>;
    };
    const createTarget = createTargetPayload.targets.find((item) => item.label === '新建任务' && item.found && item.centerX !== undefined && item.centerY !== undefined);
    if (createTarget && createTarget.centerX !== undefined && createTarget.centerY !== undefined) {
      await clickAt(createTarget.centerX, createTarget.centerY);
    }

    const afterCreate = await window.webContents.executeJavaScript(`
      (() => {
        const titleInput = Array.from(document.querySelectorAll('input'))
          .find((node) => (node.getAttribute('placeholder') || '').includes('任务标题'));
        const saveButton = Array.from(document.querySelectorAll('button'))
          .find((button) => (button.textContent || '').trim() === '保存任务');
        const cancelButton = Array.from(document.querySelectorAll('button'))
          .find((button) => (button.textContent || '').trim() === '取消');
        if (cancelButton) cancelButton.click();
        return {
          modalTitleInputFound: Boolean(titleInput),
          saveButtonFound: Boolean(saveButton),
          bodyIncludesTaskTitle: document.body.innerText.includes('任务标题'),
        };
      })()
    `, true);
    logElectronInfo(`[renderer:task-diagnostics] afterCreate=${JSON.stringify(afterCreate)}`);
  } catch (error) {
    logElectronError(`[renderer:task-diagnostics] failed=${error instanceof Error ? error.message : String(error)}`);
  }
}

async function runEventLineCreateDiagnostics(window: BrowserWindow) {
  if (!parseBooleanEnv(process.env.YIYU_ELECTRON_EVENT_LINE_DIAGNOSTICS, false)) return;

  const sleep = async (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
  const clickText = async (selector: string, label: string) =>
    window.webContents.executeJavaScript(
      `
        (() => {
          const nodes = Array.from(document.querySelectorAll(${JSON.stringify(selector)}));
          const target = nodes.find((node) => ((node.textContent || '').replace(/\\s+/g, '')).includes(${JSON.stringify(label.replace(/\s+/g, ''))}));
          if (!target) return { found: false };
          target.scrollIntoView({ block: 'center', inline: 'center' });
          target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
          return { found: true, text: (target.textContent || '').trim().slice(0, 80) };
        })()
      `,
      true,
    );
  const inspectState = async (tag: string) =>
    window.webContents.executeJavaScript(
      `
        (() => {
          const bodyText = document.body?.innerText || '';
          const heading = document.querySelector('h1')?.textContent || '';
          const modalHeading = Array.from(document.querySelectorAll('h3')).map((node) => (node.textContent || '').trim()).find(Boolean) || '';
          const eventLineButton = Array.from(document.querySelectorAll('button')).find((node) => ((node.textContent || '').replace(/\\s+/g, '')).includes('从当前任务新建'));
          const boundaryFlag = bodyText.includes('桌面界面启动失败') || bodyText.includes('Renderer Startup Failed');
          const bootEvents = Array.isArray(window.__YIYU_BOOT_EVENTS__) ? window.__YIYU_BOOT_EVENTS__ : [];
          return {
            tag: ${JSON.stringify(tag)},
            heading,
            modalHeading,
            hasEventLineCreateButton: Boolean(eventLineButton),
            eventLineCreateText: (eventLineButton?.textContent || '').trim(),
            bodySnippet: bodyText.slice(0, 800),
            boundaryFlag,
            bootEvents,
          };
        })()
      `,
      true,
    );

  try {
    await sleep(1200);
    logElectronInfo(`[renderer:event-line-diagnostics] start=${JSON.stringify(await inspectState('start'))}`);
    logElectronInfo(`[renderer:event-line-diagnostics] nav-task=${JSON.stringify(await clickText('button', '任务与日程'))}`);
    await sleep(500);
    logElectronInfo(`[renderer:event-line-diagnostics] list-mode=${JSON.stringify(await clickText('button', '任务列表'))}`);
    await sleep(500);
    const openTaskResult = await window.webContents.executeJavaScript(
      `
        (() => {
          const editButtons = Array.from(document.querySelectorAll('button')).filter((node) => ((node.textContent || '').replace(/\\s+/g, '')).includes('编辑'));
          const editButton = editButtons.find((node) => {
            const rect = node.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
          }) || editButtons[0];
          if (!editButton) return { found: false, reason: 'no-edit-button' };
          editButton.scrollIntoView({ block: 'center', inline: 'center' });
          editButton.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
          const cardText = editButton.closest('div')?.textContent || '';
          return { found: true, taskSnippet: cardText.slice(0, 160), actionText: (editButton.textContent || '').trim(), buttonCount: editButtons.length };
        })()
      `,
      true,
    );
    logElectronInfo(`[renderer:event-line-diagnostics] open-task=${JSON.stringify(openTaskResult)}`);
    await sleep(700);
    logElectronInfo(`[renderer:event-line-diagnostics] before-click=${JSON.stringify(await inspectState('before-click'))}`);
    logElectronInfo(`[renderer:event-line-diagnostics] click-create=${JSON.stringify(await clickText('button', '从当前任务新建'))}`);
    await sleep(1400);
    logElectronInfo(`[renderer:event-line-diagnostics] after-click=${JSON.stringify(await inspectState('after-click'))}`);
  } catch (error) {
    logElectronError(`[renderer:event-line-diagnostics] failed=${error instanceof Error ? error.message : String(error)}`);
  }
}

async function runUiSurfaceAudit(window: BrowserWindow) {
  const outputPath = (process.env.YIYU_UI_RUNTIME_AUDIT_OUTPUT || '').trim();
  if (!outputPath) return;

  const specPath = (
    process.env.YIYU_UI_RUNTIME_AUDIT_SPEC
    || path.join(projectRoot, 'output', 'ui-consistency-audit', 'runtime_surface_spec.json')
  ).trim();
  const autoQuit = parseBooleanEnv(process.env.YIYU_UI_RUNTIME_AUDIT_AUTOQUIT, true);
  const ensureOutputDir = () => mkdirSync(path.dirname(outputPath), { recursive: true });
  const sleep = async (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
  const writeAuditResult = (payload: Record<string, unknown>) => {
    ensureOutputDir();
    writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  };
  const finishAudit = (payload: Record<string, unknown>) => {
    writeAuditResult(payload);
    if (autoQuit) {
      setTimeout(() => {
        try {
          requestAppQuit('ui_runtime_audit_autoquit', 'runUiSurfaceAudit', { outputPath });
        } catch {}
      }, 800);
    }
  };

  let surfaceSpecs: Array<Record<string, unknown>> = [];
  try {
    surfaceSpecs = JSON.parse(fs.readFileSync(specPath, 'utf8'));
    if (!Array.isArray(surfaceSpecs)) {
      throw new Error('runtime surface spec must be an array');
    }
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    logElectronError(`[renderer:ui-audit] failed to read spec ${specPath}: ${detail}`);
    finishAudit({
      generatedAt: new Date().toISOString(),
      specPath,
      error: `failed_to_read_spec: ${detail}`,
      hits: [],
    });
    return;
  }

  const waitForReady = async () => {
    const startedAt = Date.now();
    let lastState: Record<string, unknown> | null = null;
    while (Date.now() - startedAt < 75000) {
      try {
        const state = await window.webContents.executeJavaScript(
          `
            (() => {
              const bodyText = document.body?.innerText || '';
              const normalizedBodyText = bodyText.replace(/\\s+/g, '');
              const navReady = Array.from(document.querySelectorAll('button'))
                .some((button) => ((button.textContent || '').replace(/\\s+/g, '')).includes('任务与日程'));
              const bodyReady = normalizedBodyText.includes('当前登录')
                && normalizedBodyText.includes('客户工作台')
                && normalizedBodyText.includes('系统设置');
              const root = document.getElementById('root');
              const rootChildCount = root?.childElementCount || 0;
              const rootHtmlLength = root?.innerHTML.length || 0;
              const splashVisible = normalizedBodyText.includes('正在载入核心模块数据')
                || normalizedBodyText.includes('正在连接本地后端')
                || normalizedBodyText.includes('正在恢复登录状态')
                || normalizedBodyText.includes('正在读取系统设置')
                || normalizedBodyText.includes('正在载入客户工作区')
                || normalizedBodyText.includes('正在读取员工与组织数据');
              return {
                navReady,
                bodyReady,
                ready: (navReady || bodyReady) && !splashVisible && rootChildCount >= 2 && rootHtmlLength > 12000,
                href: window.location.href,
                heading: document.querySelector('h1')?.textContent || '',
                rootChildCount,
                rootHtmlLength,
                splashVisible,
                bodySnippet: bodyText.slice(0, 240),
              };
            })()
          `,
          true,
        ) as { ready?: boolean };
        lastState = state as Record<string, unknown>;
        if (state?.ready) {
          return;
        }
      } catch (error) {
        logElectronInfo(`[renderer:ui-audit] waiting for renderer: ${error instanceof Error ? error.message : String(error)}`);
      }
      await sleep(500);
    }
    throw new Error(`ui_audit_renderer_not_ready:${JSON.stringify(lastState || {})}`);
  };

  const installAuditHooks = async () => {
    await window.webContents.executeJavaScript(
      `
        (() => {
          if (window.__YIYU_UI_AUDIT__) return true;
          const state = {
            apiCalls: [],
            ipcCalls: [],
          };
          const preview = (value) => {
            if (value == null) return value;
            if (typeof value === 'string') return value.slice(0, 160);
            if (typeof value === 'number' || typeof value === 'boolean') return value;
            if (Array.isArray(value)) return value.slice(0, 3).map(preview);
            if (typeof value === 'object') {
              const entries = Object.entries(value).slice(0, 6);
              return Object.fromEntries(entries.map(([key, inner]) => [key, preview(inner)]));
            }
            return String(value);
          };
          const normalizeUrl = (value) => {
            try {
              const parsed = new URL(String(value), window.location.origin);
              return parsed.pathname + parsed.search;
            } catch {
              return String(value || '');
            }
          };
          const originalFetch = window.fetch.bind(window);
          window.fetch = async (...args) => {
            const [input, init] = args;
            const method =
              String(
                init?.method
                || (typeof input === 'object' && input && 'method' in input ? input.method : '')
                || 'GET',
              ).toUpperCase();
            const url = typeof input === 'string' ? input : (input?.url || '');
            state.apiCalls.push({
              ts: new Date().toISOString(),
              method,
              url: normalizeUrl(url),
            });
            return await originalFetch(...args);
          };
          const workbench = window.yiyuWorkbench;
          if (workbench && !workbench.__uiAuditWrapped) {
            for (const key of Object.keys(workbench)) {
              if (key === 'backendBaseUrl') continue;
              if (typeof workbench[key] !== 'function') continue;
              const original = workbench[key].bind(workbench);
              workbench[key] = (...args) => {
                state.ipcCalls.push({
                  ts: new Date().toISOString(),
                  method: key,
                  args: preview(args),
                });
                return original(...args);
              };
            }
            Object.defineProperty(workbench, '__uiAuditWrapped', {
              value: true,
              configurable: false,
              enumerable: false,
              writable: false,
            });
          }
          window.__YIYU_UI_AUDIT__ = {
            reset() {
              state.apiCalls.length = 0;
              state.ipcCalls.length = 0;
            },
            snapshot() {
              return JSON.parse(JSON.stringify(state));
            },
          };
          return true;
        })()
      `,
      true,
    );
  };

  const inspectSurface = async (surfaceSpec: Record<string, unknown>) => {
    const serializedSpec = JSON.stringify(surfaceSpec);
    return await window.webContents.executeJavaScript(
      `
        (async () => {
          const spec = ${serializedSpec};
          const audit = window.__YIYU_UI_AUDIT__;
          const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
          const backendBaseUrl = window.yiyuWorkbench?.backendBaseUrl || '';
          const readJson = async (targetPath) => {
            if (!backendBaseUrl) return null;
            try {
              const response = await fetch(backendBaseUrl + targetPath);
              if (!response.ok) return null;
              return await response.json();
            } catch {
              return null;
            }
          };
          const fillDynamicParams = async (params) => {
            if (params.get('taskId') === '{taskId}') {
              const board = await readJson('/api/v1/tasks');
              const taskId = Array.isArray(board?.tasks) ? board.tasks[0]?.id : '';
              if (taskId) params.set('taskId', String(taskId));
              else params.delete('taskId');
            }
            if (params.get('clientId') === '{clientId}') {
              const clients = await readJson('/api/v1/clients');
              const clientId = Array.isArray(clients) ? clients[0]?.id : Array.isArray(clients?.clients) ? clients.clients[0]?.id : '';
              if (clientId) params.set('clientId', String(clientId));
              else params.delete('clientId');
            }
          };

          const params = new URLSearchParams();
          Object.entries(spec.queryParamGate || {}).forEach(([key, value]) => {
            if (value == null) return;
            params.set(key, String(value));
          });
          await fillDynamicParams(params);
          audit.reset();
          const nextUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
          window.history.pushState({}, '', nextUrl);
          window.dispatchEvent(new PopStateEvent('popstate'));
          let previousCount = -1;
          let stableTicks = 0;
          for (let index = 0; index < 40; index += 1) {
            await sleep(300);
            const snapshot = audit.snapshot();
            const currentCount = snapshot.apiCalls.length + snapshot.ipcCalls.length;
            if (currentCount === previousCount) stableTicks += 1;
            else stableTicks = 0;
            previousCount = currentCount;
            if (index >= 4 && stableTicks >= 3) break;
          }
          const snapshot = audit.snapshot();
          const bodyText = document.body?.innerText || '';
          const search = window.location.search || '';
          const evidenceNode = document.querySelector('[data-evidence-mode]');
          const querySatisfied = Object.entries(spec.queryParamGate || {}).every(([key, value]) => {
            const currentValue = new URLSearchParams(search).get(key);
            if (String(value).startsWith('{')) return Boolean(currentValue);
            return currentValue === String(value);
          });
          const markerHit = Array.isArray(spec.domMarkers)
            ? spec.domMarkers.find((marker) => marker && bodyText.includes(String(marker))) || ''
            : '';
          return {
            surfaceId: spec.surfaceId,
            entryType: spec.entryType || '',
            roleConstraint: spec.roleConstraint || '',
            query: params.toString(),
            href: window.location.href,
            heading: document.querySelector('h1')?.textContent?.trim() || '',
            evidenceMode: evidenceNode?.getAttribute('data-evidence-mode') || '',
            markerHit,
            hit: querySatisfied,
            apiCalls: snapshot.apiCalls,
            ipcCalls: snapshot.ipcCalls,
            bodySnippet: bodyText.slice(0, 500),
          };
        })()
      `,
      true,
    );
  };

  try {
    await waitForReady();
    await installAuditHooks();
    const hits: Array<Record<string, unknown>> = [];
    for (const surfaceSpec of surfaceSpecs) {
      const hit = await inspectSurface(surfaceSpec);
      hits.push(hit);
    }
    logElectronInfo(`[renderer:ui-audit] collected ${hits.length} surface hits`);
    finishAudit({
      generatedAt: new Date().toISOString(),
      specPath,
      appPackaged: app.isPackaged,
      hits,
      hitCount: hits.filter((hit) => hit.hit).length,
      surfaceCount: hits.length,
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    logElectronError(`[renderer:ui-audit] failed=${detail}`);
    finishAudit({
      generatedAt: new Date().toISOString(),
      specPath,
      error: detail,
      hits: [],
    });
  }
}

function parseBooleanEnv(value: string | undefined, fallback = false) {
  if (!value) return fallback;
  return ['1', 'true', 'yes', 'on'].includes(value.toLowerCase());
}

function quoteShellArg(value: string) {
  return `"${value.replace(/(["\\$`])/g, '\\$1')}"`;
}


function isExecutable(filePath: string) {
  try {
    fs.accessSync(filePath, fs.constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

function runtimeVenvPythonRelative(manifest?: PackagedRuntimeSeedManifest | null) {
  if (manifest?.python?.venvPython) return manifest.python.venvPython;
  return process.platform === 'win32' ? path.join('Scripts', 'python.exe') : path.join('bin', 'python');
}

function runtimeVenvUvicornRelative(manifest?: PackagedRuntimeSeedManifest | null) {
  if (manifest?.python?.venvUvicorn) return manifest.python.venvUvicorn;
  return process.platform === 'win32' ? path.join('Scripts', 'uvicorn.exe') : path.join('bin', 'uvicorn');
}

function runtimeVenvScriptsDirRelative(manifest?: PackagedRuntimeSeedManifest | null) {
  if (manifest?.python?.venvScriptsDir) return manifest.python.venvScriptsDir;
  return process.platform === 'win32' ? 'Scripts' : 'bin';
}

function runtimeVenvSitePackagesRelative() {
  return process.platform === 'win32'
    ? path.join('Lib', 'site-packages')
    : path.join('lib', 'python3.11', 'site-packages');
}

function packagedSeedPythonRelative(manifest?: PackagedRuntimeSeedManifest | null) {
  if (manifest?.python?.executable) return manifest.python.executable;
  return process.platform === 'win32'
    ? path.join(PACKAGED_RUNTIME_PYTHON_SEED_DIR, 'python.exe')
    : path.join(PACKAGED_RUNTIME_PYTHON_SEED_DIR, 'bin', 'python3.11');
}

function packagedSeedStdlibCheckRelative(manifest?: PackagedRuntimeSeedManifest | null) {
  if (manifest?.python?.stdlibCheck) return manifest.python.stdlibCheck;
  return process.platform === 'win32'
    ? path.join(PACKAGED_RUNTIME_PYTHON_SEED_DIR, 'Lib', 'encodings', '__init__.py')
    : path.join(PACKAGED_RUNTIME_PYTHON_SEED_DIR, 'lib', 'python3.11', 'encodings', '__init__.py');
}

function resolveUvBinary() {
  const searchDirs = new Set<string>();
  for (const item of (process.env.PATH ?? '').split(path.delimiter)) {
    if (item) {
      searchDirs.add(item);
    }
  }
  const homeDir = process.env.HOME;
  if (homeDir) {
    searchDirs.add(path.join(homeDir, '.local/bin'));
    searchDirs.add(path.join(homeDir, '.cargo/bin'));
  }
  searchDirs.add('/opt/homebrew/bin');
  searchDirs.add('/usr/local/bin');

  for (const directory of searchDirs) {
    const candidate = path.join(directory, 'uv');
    if (isExecutable(candidate)) {
      return candidate;
    }
  }
  return null;
}

function backendEnv(extraEnv: NodeJS.ProcessEnv = {}) {
  const env = { ...process.env, ...extraEnv };
  delete env.PYTHONHOME;
  delete env.PYTHONPATH;
  const pathEntries = new Set<string>((env.PATH ?? '').split(path.delimiter).filter(Boolean));
  if (uvBinaryPath) {
    pathEntries.add(path.dirname(uvBinaryPath));
  }
  if (env.VIRTUAL_ENV) {
    pathEntries.add(path.join(env.VIRTUAL_ENV, process.platform === 'win32' ? 'Scripts' : 'bin'));
  }
  env.PATH = Array.from(pathEntries).join(path.delimiter);
  const configuredCloudUrl = cloudBackendUrl();
  if (configuredCloudUrl) {
    env.YIYU_CLOUD_API_URL = configuredCloudUrl;
  } else {
    delete env.YIYU_CLOUD_API_URL;
  }
  // YIYU_WORKBENCH_DATA_DIR: 允许从 shell 显式覆盖,用于 v2.1 开发分支跑独立数据目录
  // (避免新旧版 schema 冲突)。未显式设置时回退到 Electron 默认 userData 路径。
  if (!env.YIYU_WORKBENCH_DATA_DIR) {
    env.YIYU_WORKBENCH_DATA_DIR = fixedUserDataPath;
  }
  env.YIYU_BACKEND_RUNTIME_MODE = app.isPackaged ? 'packaged' : 'dev';
  env.PYTHONDONTWRITEBYTECODE = '1';
  env.PYTHONNOUSERSITE = '1';
  env.PYTHONPYCACHEPREFIX = path.join(fixedUserDataPath, 'runtime', 'pycache');
  // Packaged runtime ships its own python-build-standalone interpreter that has
  // /install baked in as its build-time prefix. When self-relocation is disrupted
  // (codesign re-signing, non-ASCII install paths, App Translocation), Python
  // falls back to /install and crashes during init_fs_encoding because the
  // standard library is unreachable. Explicitly anchor PYTHONHOME at the bundled
  // seed root so stdlib loads deterministically regardless of binary state.
  if (app.isPackaged && process.platform !== 'win32') {
    const seedRoot = path.join(packagedRuntimeRoot(), PACKAGED_RUNTIME_PYTHON_SEED_DIR);
    if (fs.existsSync(path.join(seedRoot, 'lib', 'python3.11', 'encodings', '__init__.py'))) {
      env.PYTHONHOME = seedRoot;
      // PYTHONHOME overrides venv discovery via pyvenv.cfg, so when running
      // inside a venv we must add its site-packages back explicitly.
      if (env.VIRTUAL_ENV) {
        env.PYTHONPATH = path.join(env.VIRTUAL_ENV, 'lib', 'python3.11', 'site-packages');
      }
    }
  }
  return env;
}

function runtimePythonPath(venvPath: string, manifest?: PackagedRuntimeSeedManifest | null) {
  return path.join(venvPath, runtimeVenvPythonRelative(manifest));
}

function runtimeUvicornPath(venvPath: string, manifest?: PackagedRuntimeSeedManifest | null) {
  return path.join(venvPath, runtimeVenvUvicornRelative(manifest));
}

function repairRuntimeVenvEntryPoints(venvPath: string, manifest?: PackagedRuntimeSeedManifest | null) {
  if (process.platform === 'win32') return;
  const scriptsDir = path.join(venvPath, runtimeVenvScriptsDirRelative(manifest));
  const pythonPath = runtimePythonPath(venvPath, manifest);
  if (!fs.existsSync(scriptsDir) || !fs.existsSync(pythonPath)) return;
  for (const name of fs.readdirSync(scriptsDir)) {
    const entryPath = path.join(scriptsDir, name);
    if (!fs.existsSync(entryPath)) continue;
    const stat = fs.lstatSync(entryPath);
    if (stat.isDirectory() || stat.isSymbolicLink()) continue;
    let content = '';
    try {
      content = fs.readFileSync(entryPath, 'utf8');
    } catch {
      continue;
    }
    if (!content.startsWith('#!') && !content.startsWith("#!/bin/sh\n'''exec' ")) continue;
    if (content.startsWith("#!/bin/sh\n'''exec' ")) {
      const repaired = content.replace(
        /^#!\/bin\/sh\n'''exec' "[^"]+" "\$0" "\$@"\n' '''/,
        `#!/bin/sh\n'''exec' "${pythonPath}" "$0" "$@"\n' '''`,
      );
      if (repaired !== content) {
        fs.writeFileSync(entryPath, repaired, 'utf8');
      }
    } else if (content.startsWith('#!') && !content.startsWith(`#!${pythonPath}\n`)) {
      const newlineIndex = content.indexOf('\n');
      if (newlineIndex > 0) {
        fs.writeFileSync(entryPath, `#!${pythonPath}\n${content.slice(newlineIndex + 1)}`, 'utf8');
      }
    }
    fs.chmodSync(entryPath, stat.mode | 0o755);
  }
}

async function runCommand(command: string, args: string[], env: NodeJS.ProcessEnv, label: string) {
  await new Promise<void>((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: projectRoot,
      env,
    });

    logBackend(child.stdout, `${label}:stdout`);
    logBackend(child.stderr, `${label}:stderr`);

    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`${label} exited with code ${code ?? 'unknown'}`));
    });
  });
}

async function runCommandWithAcceptedExitCodes(
  command: string,
  args: string[],
  env: NodeJS.ProcessEnv,
  label: string,
  isAcceptedExitCode: (code: number) => boolean,
) {
  await new Promise<void>((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: projectRoot,
      env,
      windowsHide: true,
    });

    logBackend(child.stdout, `${label}:stdout`);
    logBackend(child.stderr, `${label}:stderr`);

    child.on('error', (error) => {
      reject(new Error(`${label} 启动失败：${error.message}`));
    });
    child.on('exit', (code) => {
      const normalizedCode = code ?? -1;
      if (isAcceptedExitCode(normalizedCode)) {
        resolve();
        return;
      }
      reject(new Error(`${label} exited with code ${normalizedCode}`));
    });
  });
}

async function assertPythonRuntimeUsable(pythonPath: string, label: string, env: NodeJS.ProcessEnv) {
  // Do NOT use -I (isolated mode): it bypasses PYTHONHOME and pyvenv.cfg,
  // which means the smoke test would only pass when the bare binary can
  // self-relocate. python-build-standalone after ad-hoc codesign or with
  // non-ASCII install paths cannot do that, so we'd reject a runtime that
  // is in fact perfectly usable under our real spawn env. Mirror the real
  // backend env instead and rely on `env` carrying PYTHONHOME/PYTHONPATH.
  await runCommand(
    pythonPath,
    [
      '-c',
      [
        'import encodings',
        'import sys',
        'print("executable=" + sys.executable)',
        'print("prefix=" + sys.prefix)',
        'print("base_prefix=" + sys.base_prefix)',
        'print("encodings=" + str(getattr(encodings, "__file__", "")))',
      ].join('; '),
    ],
    env,
    label,
  );
}

async function runJsonCommand(command: string, args: string[], env: NodeJS.ProcessEnv, label: string) {
  return new Promise<Record<string, unknown>>((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: projectRoot,
      env,
    });

    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });
    child.on('error', reject);
    child.on('exit', (code) => {
      const trimmed = stdout.trim();
      if (code !== 0) {
        reject(new Error(stderr.trim() || trimmed || `${label} exited with code ${code ?? 'unknown'}`));
        return;
      }
      try {
        resolve((trimmed ? JSON.parse(trimmed) : {}) as Record<string, unknown>);
      } catch {
        reject(new Error(`${label} returned invalid json`));
      }
    });
  });
}

function getBackendPythonPath() {
  const runtimePython = backendRuntimeVenv ? runtimePythonPath(backendRuntimeVenv) : '';
  if (runtimePython && isExecutable(runtimePython)) {
    return runtimePython;
  }
  const fallback = path.join(
    projectRoot,
    'backend',
    '.venv',
    process.platform === 'win32' ? 'Scripts' : 'bin',
    process.platform === 'win32' ? 'python.exe' : 'python',
  );
  return fallback;
}

function projectRuntimeMetadataPath(projectDirName: 'backend' | 'cloud_backend', venvPath: string) {
  return path.join(venvPath, `.yiyu-${projectDirName}-runtime.json`);
}

function readRuntimeSyncMetadata(metadataPath: string): RuntimeSyncMetadata | null {
  try {
    const raw = fs.readFileSync(metadataPath, 'utf-8');
    const parsed = JSON.parse(raw) as Partial<RuntimeSyncMetadata>;
    if (
      typeof parsed.fingerprint === 'string' &&
      typeof parsed.syncedAt === 'string' &&
      (parsed.project === 'backend' || parsed.project === 'cloud_backend')
    ) {
      return parsed as RuntimeSyncMetadata;
    }
  } catch {
    // Ignore malformed or missing metadata and force a fresh sync.
  }
  return null;
}

function writeRuntimeSyncMetadata(metadataPath: string, metadata: RuntimeSyncMetadata) {
  fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2), 'utf-8');
}

function buildRuntimeFingerprint(projectDirName: 'backend' | 'cloud_backend') {
  const targetFiles = ['pyproject.toml', 'uv.lock'];
  return targetFiles.map((fileName) => {
    const targetPath = path.join(projectRoot, projectDirName, fileName);
    const stat = fs.statSync(targetPath);
    return `${fileName}:${stat.size}:${Math.trunc(stat.mtimeMs)}`;
  }).join('|');
}

function sha256FileHex(targetPath: string) {
  return crypto.createHash('sha256').update(fs.readFileSync(targetPath)).digest('hex');
}

function sha256DirectoryHex(rootPath: string) {
  const resolvedRoot = path.resolve(rootPath);
  const entries: Array<{ kind: string; relativePath: string; value: string }> = [];
  const visit = (entryPath: string) => {
    const stat = fs.lstatSync(entryPath);
    const relativePath = path.relative(resolvedRoot, entryPath).split(path.sep).join('/');
    if (stat.isSymbolicLink()) {
      entries.push({ kind: 'symlink', relativePath, value: fs.readlinkSync(entryPath) });
      return;
    }
    if (stat.isDirectory()) {
      for (const child of fs.readdirSync(entryPath)) {
        visit(path.join(entryPath, child));
      }
      return;
    }
    entries.push({ kind: 'file', relativePath, value: sha256FileHex(entryPath) });
  };
  visit(resolvedRoot);
  entries.sort((left, right) => left.relativePath.localeCompare(right.relativePath) || left.kind.localeCompare(right.kind));
  const digest = crypto.createHash('sha256');
  for (const entry of entries) {
    digest.update(entry.kind);
    digest.update('\0');
    digest.update(entry.relativePath);
    digest.update('\0');
    digest.update(entry.value);
    digest.update('\0');
  }
  return digest.digest('hex');
}

function packagedRuntimeRoot() {
  return app.isPackaged
    ? path.join(process.resourcesPath, 'runtime')
    : path.join(projectRoot, 'dist', 'packaged-runtime');
}

function readPackagedRuntimeSeed(): PackagedRuntimeSeed {
  const root = packagedRuntimeRoot();
  const manifestPath = path.join(root, PACKAGED_RUNTIME_MANIFEST_FILE);
  if (!fs.existsSync(manifestPath)) {
    throw new Error(`内置后端运行时准备失败：缺少 ${manifestPath}`);
  }
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8')) as PackagedRuntimeSeedManifest;
  const seedPython = path.join(
    root,
    packagedSeedPythonRelative(manifest),
  );
  const requirementsPath = path.join(root, manifest.backend?.requirementsPath || PACKAGED_RUNTIME_REQUIREMENTS_FILE);
  const wheelhousePath = path.join(root, manifest.wheelhouse?.path || PACKAGED_RUNTIME_WHEELHOUSE_DIR);
  // B 方案:预装 venv 路径
  const backendVenvPath = path.join(root, manifest.backendVenv?.path || PACKAGED_RUNTIME_BACKEND_VENV_DIR);
  return {
    root,
    manifestPath,
    manifest,
    seedPython,
    requirementsPath,
    wheelhousePath,
    backendVenvPath,
  };
}

function packagedRuntimeFingerprint(seed: PackagedRuntimeSeed) {
  const manifest = seed.manifest;
  return [
    'packaged',
    seed.root,
    manifest.schemaVersion ?? 'unknown',
    manifest.platform ?? process.platform,
    manifest.arch ?? process.arch,
    manifest.python?.version ?? 'python-unknown',
    manifest.python?.treeSha256 ?? 'python-hash-missing',
    manifest.backend?.requirementsSha256 ?? 'requirements-hash-missing',
    manifest.backend?.uvLockSha256 ?? 'uv-lock-hash-missing',
    manifest.wheelhouse?.sha256 ?? 'wheelhouse-hash-missing',
    manifest.backendVenv?.sha256 ?? 'backend-venv-hash-missing',
  ].join('|');
}

function validatePackagedRuntimeSeed(seed: PackagedRuntimeSeed) {
  if (seed.manifest.platform && seed.manifest.platform !== process.platform) {
    throw new Error(`内置后端运行时平台不匹配：${seed.manifest.platform} != ${process.platform}`);
  }
  if (seed.manifest.arch && seed.manifest.arch !== process.arch) {
    throw new Error(`内置后端运行时架构不匹配：${seed.manifest.arch} != ${process.arch}`);
  }
  if (!isExecutable(seed.seedPython)) {
    throw new Error(`内置 Python 不可执行：${seed.seedPython}`);
  }
  if (!fs.existsSync(seed.requirementsPath)) {
    throw new Error(`内置依赖清单缺失：${seed.requirementsPath}`);
  }
  // B 方案:优先 backend-venv-prebuilt;只要预装 venv 存在就不要求 wheelhouse
  // (老的回退 pip install 路径仍可工作,但新版本一律走 prebuilt)
  const hasPrebuiltVenv = fs.existsSync(seed.backendVenvPath)
    && fs.existsSync(runtimePythonPath(seed.backendVenvPath, seed.manifest))
    && fs.existsSync(runtimeUvicornPath(seed.backendVenvPath, seed.manifest));
  if (!hasPrebuiltVenv && !fs.existsSync(seed.wheelhousePath)) {
    throw new Error(`内置 backend 运行时缺失：既无预装 venv (${seed.backendVenvPath}) 也无 wheelhouse (${seed.wheelhousePath})`);
  }
  const seedEncodings = path.join(seed.root, packagedSeedStdlibCheckRelative(seed.manifest));
  if (!fs.existsSync(seedEncodings)) {
    throw new Error(`内置 Python 标准库缺失：${seedEncodings}`);
  }
  if (seed.manifest.python?.dynamicLibrary) {
    const seedLibPython = path.join(seed.root, seed.manifest.python.dynamicLibrary);
    if (!fs.existsSync(seedLibPython)) {
      throw new Error(`内置 Python 动态库缺失：${seedLibPython}`);
    }
  }
  // 仅在走 legacy wheelhouse 路径时才校验 wheelhouse 目录
  if (!hasPrebuiltVenv) {
    const wheelFiles = fs.readdirSync(seed.wheelhousePath).filter((item) => item.endsWith('.whl'));
    if (wheelFiles.length === 0) {
      throw new Error(`内置 wheelhouse 为空：${seed.wheelhousePath}`);
    }
    if (seed.manifest.wheelhouse?.sha256) {
      const actualWheelhouseHash = sha256DirectoryHex(seed.wheelhousePath);
      if (actualWheelhouseHash !== seed.manifest.wheelhouse.sha256) {
        throw new Error('内置 wheelhouse hash 不匹配');
      }
    }
  }
  if (seed.manifest.backend?.requirementsSha256) {
    const actualRequirementsHash = sha256FileHex(seed.requirementsPath);
    if (actualRequirementsHash !== seed.manifest.backend.requirementsSha256) {
      throw new Error('内置后端依赖清单 hash 不匹配');
    }
  }
}

function assertRuntimeVenvPathIsSafe(venvPath: string) {
  const runtimeRoot = path.resolve(app.getPath('userData'), 'runtime');
  const resolvedVenv = path.resolve(venvPath);
  if (!resolvedVenv.startsWith(`${runtimeRoot}${path.sep}`)) {
    throw new Error(`拒绝重建非用户运行时目录：${resolvedVenv}`);
  }
}

function evaluateBackendRuntimeWarning(payload: BackendHealthPayload): string | null {
  const schemaVersion = Number(payload.backendSchemaVersion || 0);
  if (schemaVersion > 0 && schemaVersion < REQUIRED_BACKEND_SCHEMA_VERSION) {
    return `后端 schema 版本过低：${schemaVersion} < ${REQUIRED_BACKEND_SCHEMA_VERSION}`;
  }
  if (app.isPackaged && payload.runtimeMode && payload.runtimeMode !== 'packaged') {
    return `后端运行模式异常：当前为打包环境，但 runtimeMode=${payload.runtimeMode}`;
  }
  if (!app.isPackaged && payload.runtimeMode && payload.runtimeMode !== 'dev') {
    return `后端运行模式异常：当前为开发环境，但 runtimeMode=${payload.runtimeMode}`;
  }
  return null;
}

async function extractPlatformDnaText(targetPath: string) {
  const pythonPath = getBackendPythonPath();
  if (!isExecutable(pythonPath)) {
    throw new Error('后端 Python 环境不可用，暂时无法读取 docx/pdf。');
  }
  if (!fs.existsSync(platformDnaExtractorScriptPath)) {
    throw new Error('平台 DNA 抽取脚本不存在。');
  }
  const payload = await runJsonCommand(
    pythonPath,
    [platformDnaExtractorScriptPath, targetPath],
    backendEnv({ VIRTUAL_ENV: path.dirname(path.dirname(pythonPath)) }),
    'platform-dna:extract',
  );
  if (!payload.success) {
    throw new Error(typeof payload.error === 'string' ? payload.error : '平台 DNA 文档解析失败');
  }
  return typeof payload.text === 'string' ? payload.text : '';
}

// 防御性兜底：sherpa-onnx wheel 把 libonnxruntime.X.Y.Z.dylib 绑死在 @rpath（文件名带版本号），
// 但 wheel 自身不带这个 dylib，靠同 venv 里的 onnxruntime 包提供。如果两者版本不一致，
// `import sherpa_onnx` 会 dlopen 失败 → ImportError。第一道防线是 pyproject.toml 把
// onnxruntime 锁到与 sherpa-onnx 编译版本兼容的范围；这一层是第二道防线：扫期望版本 → 扫实际
// 版本 → 不匹配时建软链。哪怕将来 sherpa-onnx 升级又出现错配，用户首次安装/重建 venv 都不会被绊。
// 只在 macOS 处理：otool 是 macOS 专属，且 Linux/Windows 的 sherpa-onnx wheel 一般自包含 dylib。
async function ensureSherpaOnnxDylibAligned(venvPath: string): Promise<void> {
  if (process.platform !== 'darwin') return;
  try {
    const sherpaLibDir = path.join(venvPath, 'lib', 'python3.11', 'site-packages', 'sherpa_onnx', 'lib');
    const onnxCapiDir = path.join(venvPath, 'lib', 'python3.11', 'site-packages', 'onnxruntime', 'capi');
    if (!fs.existsSync(sherpaLibDir) || !fs.existsSync(onnxCapiDir)) return;
    const sherpaSo = fs.readdirSync(sherpaLibDir).find((f) => f.startsWith('_sherpa_onnx.') && f.endsWith('.so'));
    if (!sherpaSo) return;
    const sherpaSoPath = path.join(sherpaLibDir, sherpaSo);
    const otoolOutput = await new Promise<string>((resolve, reject) => {
      const child = spawn('/usr/bin/otool', ['-L', sherpaSoPath], { env: process.env });
      const chunks: string[] = [];
      child.stdout.on('data', (chunk) => chunks.push(chunk.toString()));
      child.on('error', reject);
      child.on('exit', (code) => {
        if (code === 0) resolve(chunks.join(''));
        else reject(new Error(`otool exited ${code}`));
      });
    });
    const expectedMatch = otoolOutput.match(/libonnxruntime\.(\d+\.\d+\.\d+)\.dylib/);
    if (!expectedMatch) return;
    const expectedVersion = expectedMatch[1];
    const expectedDylibName = `libonnxruntime.${expectedVersion}.dylib`;
    const expectedDylibPath = path.join(sherpaLibDir, expectedDylibName);
    if (fs.existsSync(expectedDylibPath)) return;
    const actualDylib = fs.readdirSync(onnxCapiDir).find((f) => /^libonnxruntime\.\d+\.\d+\.\d+\.dylib$/.test(f));
    if (!actualDylib) {
      logElectronError(`[asr-dylib] onnxruntime/capi 缺少 libonnxruntime.*.dylib，sherpa-onnx 期望的 ${expectedDylibName} 无法对齐`);
      return;
    }
    fs.symlinkSync(path.join(onnxCapiDir, actualDylib), expectedDylibPath);
    appendElectronLaunchLog(
      'INFO',
      `[asr-dylib] aligned ${expectedDylibName} -> ${actualDylib} (sherpa-onnx expects ${expectedVersion}, onnxruntime provides ${actualDylib.match(/(\d+\.\d+\.\d+)/)?.[1] ?? '?'})`,
    );
  } catch (error) {
    logElectronError(`[asr-dylib] 对齐失败（非致命，转写运行时会显式报错）：${error instanceof Error ? error.message : String(error)}`);
  }
}

function packagedRuntimeTempVenvPath(venvPath: string) {
  return path.join(
    path.dirname(venvPath),
    `${path.basename(venvPath)}.tmp-${process.pid}-${Date.now()}`,
  );
}

function setPyvenvConfigLine(content: string, key: string, value: string) {
  const escapedKey = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = new RegExp(`^${escapedKey}\\s*=.*$`, 'm');
  const line = `${key} = ${value}`;
  if (pattern.test(content)) {
    return content.replace(pattern, line);
  }
  return `${content.trimEnd()}\n${line}\n`;
}

function repairPackagedRuntimeVenvConfig(venvPath: string, seed: PackagedRuntimeSeed) {
  const pyvenvCfgPath = path.join(venvPath, 'pyvenv.cfg');
  if (!fs.existsSync(pyvenvCfgPath)) return;

  const seedPythonAbs = seed.seedPython;
  const seedHomeDir = path.dirname(seedPythonAbs);
  const runtimeCommand = `${seedPythonAbs} -m venv --copies --without-pip ${venvPath}`;
  let cfg = fs.readFileSync(pyvenvCfgPath, 'utf8');
  cfg = setPyvenvConfigLine(cfg, 'home', seedHomeDir);
  cfg = setPyvenvConfigLine(cfg, 'executable', seedPythonAbs);
  cfg = setPyvenvConfigLine(cfg, 'command', runtimeCommand);
  fs.writeFileSync(pyvenvCfgPath, cfg, 'utf8');
}

const WINDOWS_RUNTIME_COPY_TOOL_UNAVAILABLE_MESSAGE = 'Windows 运行时复制工具不可用，请重新安装最新版安装包；如仍失败，请联系益语支持。';

function uniqueExistingWindowsToolCandidate(candidates: string[]) {
  const seen = new Set<string>();
  for (const candidate of candidates) {
    const trimmed = candidate.trim();
    if (!trimmed) continue;
    const key = trimmed.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    if (!path.isAbsolute(trimmed) || fs.existsSync(trimmed)) {
      return trimmed;
    }
  }
  return null;
}

function windowsSystemRoots() {
  return [
    process.env.SystemRoot,
    process.env.WINDIR,
    'C:\\Windows',
  ].filter((value): value is string => Boolean(value && value.trim()));
}

function resolveWindowsSystem32Tool(fileName: string) {
  return uniqueExistingWindowsToolCandidate([
    ...windowsSystemRoots().map((root) => path.join(root, 'System32', fileName)),
    fileName,
  ]);
}

function resolveWindowsPowerShell() {
  return uniqueExistingWindowsToolCandidate([
    ...windowsSystemRoots().map((root) => path.join(root, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')),
    'powershell.exe',
  ]);
}

function isWindowsToolNotFoundError(error: unknown) {
  const value = error as NodeJS.ErrnoException | undefined;
  const message = error instanceof Error ? error.message : String(error);
  return value?.code === 'ENOENT' || /\bENOENT\b/i.test(message) || /not found/i.test(message);
}

async function tryRunWindowsCopyTool(
  command: string | null,
  args: string[],
  label: string,
  isAcceptedExitCode: (code: number) => boolean,
) {
  if (!command) return false;
  try {
    await runCommandWithAcceptedExitCodes(command, args, backendEnv(), label, isAcceptedExitCode);
    return true;
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    appendElectronLaunchLog('ERROR', `[backend:packaged-runtime] ${label} failed: ${detail}`);
    if (isWindowsToolNotFoundError(error)) return false;
    throw error;
  }
}

async function copyPrebuiltBackendVenvWithWindowsTools(seed: PackagedRuntimeSeed, targetVenvPath: string) {
  const robocopy = resolveWindowsSystem32Tool('robocopy.exe');
  appendElectronLaunchLog(
    'INFO',
    `[backend:packaged-runtime] robocopy pre-built venv ${seed.backendVenvPath} -> ${targetVenvPath} via ${robocopy || 'unavailable'}`,
  );
  if (await tryRunWindowsCopyTool(
    robocopy,
    [
      seed.backendVenvPath,
      targetVenvPath,
      '/MIR',
      '/R:2',
      '/W:1',
      '/NFL',
      '/NDL',
      '/NP',
    ],
    'backend:packaged-runtime-robocopy',
    (code) => code >= 0 && code <= 7,
  )) {
    return;
  }

  const powershell = resolveWindowsPowerShell();
  appendElectronLaunchLog(
    'INFO',
    `[backend:packaged-runtime] PowerShell fallback pre-built venv ${seed.backendVenvPath} -> ${targetVenvPath} via ${powershell || 'unavailable'}`,
  );
  if (await tryRunWindowsCopyTool(
    powershell,
    [
      '-NoProfile',
      '-ExecutionPolicy',
      'Bypass',
      '-Command',
      [
        '$ErrorActionPreference = "Stop"',
        '$source = $args[0]',
        '$destination = $args[1]',
        'if (Test-Path -LiteralPath $destination) { Remove-Item -LiteralPath $destination -Recurse -Force }',
        'New-Item -ItemType Directory -Force -Path $destination | Out-Null',
        'Get-ChildItem -LiteralPath $source -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse -Force }',
      ].join('; '),
      seed.backendVenvPath,
      targetVenvPath,
    ],
    'backend:packaged-runtime-powershell-copy',
    (code) => code === 0,
  )) {
    return;
  }

  const xcopy = resolveWindowsSystem32Tool('xcopy.exe');
  appendElectronLaunchLog(
    'INFO',
    `[backend:packaged-runtime] xcopy fallback pre-built venv ${seed.backendVenvPath} -> ${targetVenvPath} via ${xcopy || 'unavailable'}`,
  );
  if (await tryRunWindowsCopyTool(
    xcopy,
    [
      path.join(seed.backendVenvPath, '*'),
      targetVenvPath,
      '/E',
      '/H',
      '/K',
      '/Y',
      '/I',
      '/C',
    ],
    'backend:packaged-runtime-xcopy',
    (code) => code === 0 || code === 1,
  )) {
    return;
  }

  throw new Error(WINDOWS_RUNTIME_COPY_TOOL_UNAVAILABLE_MESSAGE);
}

async function copyPrebuiltBackendVenv(seed: PackagedRuntimeSeed, targetVenvPath: string) {
  if (process.platform === 'win32') {
    fs.mkdirSync(targetVenvPath, { recursive: true });
    await copyPrebuiltBackendVenvWithWindowsTools(seed, targetVenvPath);
    return;
  }

  appendElectronLaunchLog('INFO', `[backend:packaged-runtime] copying pre-built venv ${seed.backendVenvPath} -> ${targetVenvPath}`);
  fs.cpSync(seed.backendVenvPath, targetVenvPath, { recursive: true, dereference: false, verbatimSymlinks: true });
}

function replaceRuntimeVenv(tempVenvPath: string, finalVenvPath: string) {
  assertRuntimeVenvPathIsSafe(tempVenvPath);
  assertRuntimeVenvPathIsSafe(finalVenvPath);
  fs.rmSync(finalVenvPath, { recursive: true, force: true });
  fs.renameSync(tempVenvPath, finalVenvPath);
}

async function ensurePackagedBackendRuntime(venvPath: string) {
  const seed = readPackagedRuntimeSeed();
  const metadataPath = projectRuntimeMetadataPath('backend', venvPath);
  const fingerprint = packagedRuntimeFingerprint(seed);
  const pythonPath = runtimePythonPath(venvPath, seed.manifest);
  const uvicornPath = runtimeUvicornPath(venvPath, seed.manifest);
  const existingMetadata = readRuntimeSyncMetadata(metadataPath);
  const forceSync = parseBooleanEnv(process.env.YIYU_FORCE_RUNTIME_SYNC, false);
  let shouldInstall = forceSync || !isExecutable(pythonPath) || !isExecutable(uvicornPath) || existingMetadata?.fingerprint !== fingerprint;
  if (!shouldInstall) {
    try {
      await assertPythonRuntimeUsable(
        pythonPath,
        'backend:packaged-existing-python-smoke',
        backendEnv({ VIRTUAL_ENV: venvPath }),
      );
      return;
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      logElectronError(`[backend:packaged-runtime] existing runtime self-check failed; rebuilding: ${detail}`);
      shouldInstall = true;
    }
  }

  validatePackagedRuntimeSeed(seed);
  assertRuntimeVenvPathIsSafe(venvPath);
  fs.mkdirSync(path.dirname(venvPath), { recursive: true });
  await assertPythonRuntimeUsable(seed.seedPython, 'backend:packaged-seed-python-smoke', backendEnv());
  const tempVenvPath = packagedRuntimeTempVenvPath(venvPath);
  assertRuntimeVenvPathIsSafe(tempVenvPath);
  fs.rmSync(tempVenvPath, { recursive: true, force: true });

  // B 方案根治路径:.app 内有预装 venv → 复制 + 改 pyvenv.cfg,跳过 pip install
  // 旧路径(pip install from wheelhouse)被废弃,因为 wheel 内嵌 binary 公证拒收
  const hasPrebuiltVenv = fs.existsSync(seed.backendVenvPath)
    && fs.existsSync(runtimePythonPath(seed.backendVenvPath, seed.manifest))
    && fs.existsSync(runtimeUvicornPath(seed.backendVenvPath, seed.manifest));

  try {
    if (hasPrebuiltVenv) {
      await copyPrebuiltBackendVenv(seed, tempVenvPath);
      repairPackagedRuntimeVenvConfig(tempVenvPath, seed);
      repairRuntimeVenvEntryPoints(tempVenvPath, seed.manifest);
    } else {
      // 回退兼容路径:旧版本 build 没生成预装 venv 时仍走 pip install
      // 这条路径将随老版本淘汰,新版本统一走 hasPrebuiltVenv=true
      appendElectronLaunchLog('INFO', '[backend:packaged-runtime] no pre-built venv found, falling back to legacy pip install path');
      await runCommand(seed.seedPython, ['-m', 'venv', '--without-pip', '--copies', tempVenvPath], backendEnv(), 'backend:packaged-venv');
      if (seed.manifest.python?.dynamicLibrary) {
        const seedLibPython = path.join(seed.root, seed.manifest.python.dynamicLibrary);
        const venvLibPython = path.join(tempVenvPath, 'lib', path.basename(seed.manifest.python.dynamicLibrary));
        if (fs.existsSync(seedLibPython)) {
          fs.copyFileSync(seedLibPython, venvLibPython);
        }
      }
      await runCommand(
        runtimePythonPath(tempVenvPath, seed.manifest),
        ['-m', 'ensurepip', '--upgrade', '--default-pip'],
        backendEnv({ VIRTUAL_ENV: tempVenvPath }),
        'backend:packaged-ensurepip',
      );
      await runCommand(
        runtimePythonPath(tempVenvPath, seed.manifest),
        [
          '-m',
          'pip',
          'install',
          '--no-index',
          '--find-links',
          seed.wheelhousePath,
          '--requirement',
          seed.requirementsPath,
        ],
        backendEnv({ VIRTUAL_ENV: tempVenvPath }),
        'backend:packaged-wheelhouse',
      );
    }

    await assertPythonRuntimeUsable(
      runtimePythonPath(tempVenvPath, seed.manifest),
      'backend:packaged-python-smoke-temp',
      backendEnv({ VIRTUAL_ENV: tempVenvPath }),
    );
    if (!isExecutable(runtimeUvicornPath(tempVenvPath, seed.manifest))) {
      throw new Error('内置后端运行时临时安装完成后仍缺少 uvicorn');
    }

    replaceRuntimeVenv(tempVenvPath, venvPath);
    repairPackagedRuntimeVenvConfig(venvPath, seed);
    repairRuntimeVenvEntryPoints(venvPath, seed.manifest);
  } catch (error) {
    fs.rmSync(tempVenvPath, { recursive: true, force: true });
    throw error;
  }

  await assertPythonRuntimeUsable(pythonPath, 'backend:packaged-python-smoke', backendEnv({ VIRTUAL_ENV: venvPath }));
  if (!isExecutable(uvicornPath)) {
    throw new Error('内置后端运行时安装完成后仍缺少 uvicorn');
  }
  await ensureSherpaOnnxDylibAligned(venvPath);
  writeRuntimeSyncMetadata(metadataPath, {
    fingerprint,
    syncedAt: new Date().toISOString(),
    project: 'backend',
  });
}

async function ensureProjectRuntime(projectDirName: 'backend' | 'cloud_backend', venvPath: string) {
  if (app.isPackaged) {
    if (projectDirName !== 'backend') {
      throw new Error(`packaged runtime does not include local ${projectDirName}`);
    }
    await ensurePackagedBackendRuntime(venvPath);
    return;
  }
  if (!uvBinaryPath) {
    throw new Error('missing_uv_binary');
  }
  fs.mkdirSync(path.dirname(venvPath), { recursive: true });
  const pythonPath = runtimePythonPath(venvPath);
  const uvicornPath = runtimeUvicornPath(venvPath);
  const metadataPath = projectRuntimeMetadataPath(projectDirName, venvPath);
  const fingerprint = buildRuntimeFingerprint(projectDirName);
  const forceSync = parseBooleanEnv(process.env.YIYU_FORCE_RUNTIME_SYNC, false);
  if (!isExecutable(pythonPath)) {
    await runCommand(uvBinaryPath, ['venv', venvPath, '--python', '3.11'], backendEnv(), `${projectDirName}:venv`);
  }
  const existingMetadata = readRuntimeSyncMetadata(metadataPath);
  const shouldSync = forceSync || !isExecutable(uvicornPath) || existingMetadata?.fingerprint !== fingerprint;
  if (!shouldSync) {
    return;
  }
  await runCommand(
    uvBinaryPath,
    ['sync', '--project', path.join(projectRoot, projectDirName), '--active', '--locked'],
    backendEnv({ VIRTUAL_ENV: venvPath }),
    `${projectDirName}:sync`,
  );
  if (projectDirName === 'backend') {
    await ensureSherpaOnnxDylibAligned(venvPath);
  }
  writeRuntimeSyncMetadata(metadataPath, {
    fingerprint,
    syncedAt: new Date().toISOString(),
    project: projectDirName,
  });
}

function backendUrl() {
  return `http://127.0.0.1:${backendPort}`;
}

type MaintenanceModeGuardStatus = {
  active?: boolean;
  reason?: string | null;
};

function requestBackendJson<T>(pathName: string, timeoutMs = 6000): Promise<T> {
  return new Promise((resolve, reject) => {
    const req = http.get(`${backendUrl()}${pathName}`, (res) => {
      const chunks: Buffer[] = [];
      res.on('data', (chunk) => {
        chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
      });
      res.on('end', () => {
        const body = Buffer.concat(chunks).toString('utf8');
        let payload: unknown = null;
        if (body.trim()) {
          try {
            payload = JSON.parse(body);
          } catch {
            reject(new Error(body.slice(0, 240) || `HTTP ${res.statusCode || 500}`));
            return;
          }
        }
        if ((res.statusCode || 500) >= 400) {
          const detail = payload && typeof payload === 'object' && 'detail' in payload
            ? String((payload as { detail?: unknown }).detail || '')
            : '';
          reject(new Error(detail || `HTTP ${res.statusCode || 500}`));
          return;
        }
        resolve(payload as T);
      });
    });
    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error('本地服务响应超时，请稍后重试。'));
    });
    req.on('error', reject);
  });
}

function postBackendJson<T>(pathName: string, payload: unknown, timeoutMs = 6000): Promise<T> {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(payload ?? {});
    const req = http.request(`${backendUrl()}${pathName}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
      },
    }, (res) => {
      const chunks: Buffer[] = [];
      res.on('data', (chunk) => {
        chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
      });
      res.on('end', () => {
        const rawBody = Buffer.concat(chunks).toString('utf8');
        let parsed: unknown = null;
        if (rawBody.trim()) {
          try {
            parsed = JSON.parse(rawBody);
          } catch {
            reject(new Error(rawBody.slice(0, 240) || `HTTP ${res.statusCode || 500}`));
            return;
          }
        }
        if ((res.statusCode || 500) >= 400) {
          const detail = parsed && typeof parsed === 'object' && 'detail' in parsed
            ? String((parsed as { detail?: unknown }).detail || '')
            : '';
          reject(new Error(detail || `HTTP ${res.statusCode || 500}`));
          return;
        }
        resolve(parsed as T);
      });
    });
    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error('本地服务响应超时，请稍后重试。'));
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

async function requireActiveMaintenanceMode(actionLabel: string) {
  const status = await requestBackendJson<MaintenanceModeGuardStatus>('/api/v1/maintenance-mode/status');
  if (!status.active) {
    throw new Error(status.reason || `请先在系统日志中打开左下角推送同步，再${actionLabel}。`);
  }
}

function cloudBackendUrl() {
  return remoteCloudBackendUrl() || (shouldUseBundledLocalCloudBackend() ? `http://127.0.0.1:${cloudBackendPort}` : '');
}

function rendererUrl() {
  return `http://127.0.0.1:${rendererPort}${rendererLaunchQuery()}`;
}

function rendererProtocolUrl() {
  return `app://renderer/index.html${rendererLaunchQuery()}`;
}

function writeRendererDiagnosticPage(fileName: string, html: string) {
  fs.mkdirSync(runtimeUiDir, { recursive: true });
  const filePath = path.join(runtimeUiDir, fileName);
  fs.writeFileSync(filePath, html, 'utf8');
  return pathToFileURL(filePath).href;
}

function rendererBootstrapPageUrl(detail = '正在连接本地界面与后台服务，请稍候…') {
  return writeRendererDiagnosticPage('__bootstrap__.html', buildRendererBootstrapPage(detail));
}

function rendererFailurePageUrl(detail: string) {
  return writeRendererDiagnosticPage('__renderer_failure__.html', buildRendererFailurePage(detail));
}

function startupRepairPageUrl(appInfo: DesktopAppInfo, rebuildRepoPath: string | null) {
  return writeRendererDiagnosticPage('__startup_gate_blocked__.html', buildStartupRepairPage(appInfo, rebuildRepoPath));
}

async function registerRendererProtocol() {
  if (rendererProtocolRegistered) return;
  const rendererRoot = path.join(projectRoot, 'dist/renderer');
  protocol.handle('app', async (request) => {
    const requestUrl = new URL(request.url);
    if (requestUrl.pathname === '/__bootstrap__.html') {
      const detail = requestUrl.searchParams.get('detail') || '正在连接本地界面与后台服务，请稍候…';
      return new Response(Buffer.from(buildRendererBootstrapPage(detail)), {
        headers: {
          'Content-Type': 'text/html; charset=utf-8',
          'Cache-Control': 'no-store',
        },
      });
    }
    if (requestUrl.pathname === '/__renderer_failure__.html') {
      const detail = requestUrl.searchParams.get('detail') || '渲染界面启动失败。';
      return new Response(Buffer.from(buildRendererFailurePage(detail)), {
        headers: {
          'Content-Type': 'text/html; charset=utf-8',
          'Cache-Control': 'no-store',
        },
      });
    }
    const normalizedPath = requestUrl.pathname === '/' ? '/index.html' : requestUrl.pathname;
    const candidatePath = path.resolve(rendererRoot, `.${normalizedPath}`);
    const safePath = candidatePath.startsWith(rendererRoot) && fs.existsSync(candidatePath) && fs.statSync(candidatePath).isFile()
      ? candidatePath
      : path.join(rendererRoot, 'index.html');
    const buffer = await fs.promises.readFile(safePath);
    return new Response(buffer, {
      headers: {
        'Content-Type': rendererContentType(safePath),
        'Cache-Control': 'no-store',
      },
    });
  });
  rendererProtocolRegistered = true;
}

async function checkBackendHealthAt(port: number, requiredFeatures: string[]): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${port}/api/v1/system/health`, (res) => {
      if ((res.statusCode ?? 500) >= 500) {
        res.resume();
        resolve(false);
        return;
      }
      const chunks: Buffer[] = [];
      res.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
      res.on('end', () => {
        try {
          const payload = JSON.parse(Buffer.concat(chunks).toString('utf-8')) as BackendHealthPayload;
          const featureFlags = Array.isArray(payload.featureFlags) ? payload.featureFlags : [];
          const missing = requiredFeatures.filter((feature) => !featureFlags.includes(feature));
          resolve(missing.length === 0);
        } catch {
          resolve(false);
        }
      });
    });
    req.on('error', () => resolve(false));
    req.setTimeout(800, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function checkCloudBackendHealthAt(port: number): Promise<boolean> {
  return checkCloudBackendHealth(`http://127.0.0.1:${port}`);
}

async function checkCloudBackendHealth(targetUrl: string): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(`${targetUrl.replace(/\/+$/, '')}/health`, (res) => {
      res.resume();
      resolve((res.statusCode ?? 500) < 500);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(800, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function fetchBackendHealthSnapshot(port = backendPort): Promise<BackendHealthPayload | null> {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${port}/api/v1/system/health`, (res) => {
      if ((res.statusCode ?? 500) >= 500) {
        res.resume();
        resolve(null);
        return;
      }
      const chunks: Buffer[] = [];
      res.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
      res.on('end', () => {
        try {
          resolve(JSON.parse(Buffer.concat(chunks).toString('utf-8')) as BackendHealthPayload);
        } catch {
          resolve(null);
        }
      });
    });
    req.on('error', () => resolve(null));
    req.setTimeout(1000, () => {
      req.destroy();
      resolve(null);
    });
  });
}

async function resolveDesktopAppInfo(healthOverride?: BackendHealthPayload | null): Promise<DesktopAppInfo> {
  await cleanupStaleInstallBundles();
  const executablePath = process.execPath;
  const appBundlePath = resolveBundlePath(executablePath);
  const recommendedInstallPath = path.join(app.getPath('home'), 'Applications', `${APP_DISPLAY_NAME}.app`);
  const detectedAppPaths = await collectInstalledAppPaths(appBundlePath);
  const legacyAppPaths: string[] = [];

  for (const targetPath of detectedAppPaths) {
    if (targetPath === appBundlePath) continue;
    const baseName = path.basename(targetPath);
    const bundleId = await readBundleId(targetPath);
    if (legacyAppBasenames.has(baseName) || (bundleId && bundleId !== APP_BUNDLE_ID)) {
      legacyAppPaths.push(targetPath);
    }
  }

  const appInfo = buildDesktopAppInfo({
    // V2.1 Lab 模式下版本号带 ".1" 后缀, 前端"关于本软件"页面区分双 app
    appVersion: APP_VERSION_DISPLAY,
    runtimeMode: app.isPackaged ? 'packaged' : 'dev',
    collabPreviewMode: COLLAB_PREVIEW_MODE,
    isPackaged: app.isPackaged,
    platform: process.platform,
    arch: process.arch,
    appBundlePath,
    executablePath,
    releasePlanPath,
    releaseArtifactsPath,
    cloudBackendUrl: cloudBackendUrl() || null,
    updateChannel: 'stable',
    updaterPhase: 'planning',
    recommendedInstallPath,
    detectedAppPaths,
    legacyAppPaths,
    health: healthOverride === undefined ? await fetchBackendHealthSnapshot() : healthOverride,
    requiredFeatures: REQUIRED_BACKEND_FEATURES,
    requiredSchemaVersion: REQUIRED_BACKEND_SCHEMA_VERSION,
  });
  latestDesktopAppInfo = appInfo;
  return appInfo;
}

async function resumeFromStartupGate(): Promise<DesktopStartupGateResumeResult> {
  purgeSavedApplicationState();
  const appInfo = await resolveDesktopAppInfo(await fetchBackendHealthSnapshot());
  if (appInfo.startupGateStatus === 'blocked') {
    return {
      resumed: false,
      appInfo,
      loadMode: 'blocked',
    };
  }
  if (!mainWindow || mainWindow.isDestroyed()) {
    await createMainWindow({ startupGateInfo: appInfo });
    return {
      resumed: true,
      appInfo,
      loadMode: 'app',
    };
  }
  const loadMode = await loadRendererWithFallback(mainWindow);
  if (loadMode !== 'error') {
    if (!mainWindow.isVisible()) {
      mainWindow.show();
    }
    mainWindow.focus();
    app.focus({ steal: true });
  }
  return {
    resumed: loadMode !== 'error',
    appInfo,
    loadMode,
  };
}

async function isPortAvailable(port: number): Promise<boolean> {
  await new Promise((resolve) => setTimeout(resolve, 10));
  return new Promise((resolve) => {
    const server = net.createServer();
    server.unref();
    server.on('error', () => resolve(false));
    server.listen(port, '127.0.0.1', () => {
      server.close(() => resolve(true));
    });
  });
}

async function reservePort(preferredPort: number, reservedPorts = new Set<number>()): Promise<number> {
  if (!reservedPorts.has(preferredPort) && await isPortAvailable(preferredPort)) {
    return preferredPort;
  }
  for (let offset = 1; offset <= 30; offset += 1) {
    const candidate = preferredPort + offset;
    if (!reservedPorts.has(candidate) && await isPortAvailable(candidate)) {
      return candidate;
    }
  }
  throw new Error(`无法为本地服务找到可用端口，起始端口=${preferredPort}`);
}

async function terminateManagedRuntimeProcess(venvPath: string) {
  const runtimePython = runtimePythonPath(venvPath);
  if (!fs.existsSync(runtimePython)) return;
  await new Promise<void>((resolve) => {
    const child = spawn('pkill', ['-f', `${runtimePython} -m uvicorn app.main:app`], {
      env: backendEnv({ VIRTUAL_ENV: venvPath }),
    });
    child.on('error', () => resolve());
    child.on('exit', () => resolve());
  });
}

async function recyclePackagedRuntimeProcesses() {
  if (!app.isPackaged) return;
  await terminateManagedRuntimeProcess(backendRuntimeVenv);
  await terminateManagedRuntimeProcess(cloudBackendRuntimeVenv);
}

function purgeSavedApplicationState() {
  try {
    fs.rmSync(savedApplicationStatePath, { recursive: true, force: true });
  } catch {
    // Ignore saved-state cleanup errors; they should not block startup.
  }
}

function logBackend(pipe: NodeJS.ReadableStream, label: string, onLine?: (line: string) => void) {
  pipe.on('data', (chunk) => {
    const text = chunk.toString();
    writeProcessStreamSafely(process.stdout, `[backend:${label}] ${text}`);
    for (const line of text.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      appendElectronLaunchLog('INFO', `[backend:${label}] ${trimmed}`);
      if (onLine) {
        onLine(trimmed);
      }
    }
  });
}

function startBackend() {
  if (backendProcess) return;
  const entrypoint = runtimePythonPath(backendRuntimeVenv);
  if (!isExecutable(entrypoint)) {
    throw new Error('missing_backend_runtime');
  }
  const args = ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(backendPort)];
  // Dev-only: hot-reload Python on source changes so we don't need to restart
  // Electron after every backend edit. Packaged builds keep the old behaviour
  // (no reload) since the bundled source is immutable.
  // YIYU_BACKEND_NO_RELOAD=1 forces the no-reload path even in dev, so the
  // backend survives external tools (e.g. parallel AI assistants) touching
  // backend/app/*.py while a verification session is running.
  if (!app.isPackaged && process.env.YIYU_BACKEND_NO_RELOAD !== '1') {
    // --reload-delay 2: 2 秒防抖窗口,多次 touch 合并成一次 reload
    //   (并行 AI assistants 改 backend/app/*.py 时不再触发 reload 风暴)
    // --reload-exclude: 跳过 __pycache__/*.pyc/test 缓存目录,只监听真业务文件
    args.push(
      '--reload',
      '--reload-dir', path.join(projectRoot, 'backend', 'app'),
      '--reload-delay', '2',
      '--reload-exclude', '**/__pycache__/**',
      '--reload-exclude', '**/*.pyc',
      '--reload-exclude', '**/.pytest_cache/**',
    );
  }
  backendProcess = spawn(
    entrypoint,
    args,
    {
      cwd: path.join(projectRoot, 'backend'),
      env: backendEnv({ VIRTUAL_ENV: backendRuntimeVenv }),
    },
  );
  ownsBackendProcess = true;
  backendExitDetail = null;
  backendRecentLogLines.length = 0;

  logBackend(backendProcess.stdout, 'stdout', rememberBackendLogLine);
  logBackend(backendProcess.stderr, 'stderr', rememberBackendLogLine);
  backendProcess.on('error', (error) => {
    backendExitDetail = `后端子进程启动失败：${error.message}`;
    logElectronError(`后端服务启动失败: ${error.message}`);
  });

  backendProcess.on('exit', (code) => {
    backendExitDetail = `后端服务已退出，退出码=${code ?? 'unknown'}`;
    backendProcess = null;
    // 不重置 ownsBackendProcess：保持 true 让 watchdog（每 15s）识别为"我们的 backend 死了"
    // 并自动重启。之前这里清成 false，导致 watchdog 第一行 `if (!ownsBackendProcess) return`
    // 直接放弃，backend 永远不被拉起来。
    logElectronError(`后端服务已退出，退出码=${code ?? 'unknown'}`);
  });
}

function startCloudBackend() {
  if (cloudBackendProcess) return;
  const entrypoint = runtimePythonPath(cloudBackendRuntimeVenv);
  if (!isExecutable(entrypoint)) {
    throw new Error('missing_cloud_backend_runtime');
  }
  const args = ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(cloudBackendPort)];
  cloudBackendProcess = spawn(
    entrypoint,
    args,
    {
      cwd: path.join(projectRoot, 'cloud_backend'),
      env: backendEnv({
        VIRTUAL_ENV: cloudBackendRuntimeVenv,
        ...localDevCloudSeedEnv(),
      }),
    },
  );
  ownsCloudBackendProcess = true;

  logBackend(cloudBackendProcess.stdout, 'cloud:stdout');
  logBackend(cloudBackendProcess.stderr, 'cloud:stderr');
  cloudBackendProcess.on('error', (error) => {
    logElectronError(`中心后端启动失败: ${error.message}`);
  });

  cloudBackendProcess.on('exit', (code) => {
    cloudBackendProcess = null;
    ownsCloudBackendProcess = false;
    logElectronError(`中心后端已退出，退出码=${code ?? 'unknown'}`);
  });
}

function stopBackend() {
  if (!backendProcess || !ownsBackendProcess) return;
  backendProcess.kill('SIGTERM');
  backendProcess = null;
  ownsBackendProcess = false;
}

function stopCloudBackend() {
  if (!cloudBackendProcess || !ownsCloudBackendProcess) return;
  cloudBackendProcess.kill('SIGTERM');
  cloudBackendProcess = null;
  ownsCloudBackendProcess = false;
}

function rendererContentType(filePath: string) {
  const ext = path.extname(filePath).toLowerCase();
  switch (ext) {
    case '.html':
      return 'text/html; charset=utf-8';
    case '.js':
      return 'text/javascript; charset=utf-8';
    case '.css':
      return 'text/css; charset=utf-8';
    case '.json':
      return 'application/json; charset=utf-8';
    case '.svg':
      return 'image/svg+xml';
    case '.png':
      return 'image/png';
    case '.jpg':
    case '.jpeg':
      return 'image/jpeg';
    case '.ico':
      return 'image/x-icon';
    default:
      return 'application/octet-stream';
  }
}

async function startRendererStaticServer() {
  if (rendererStaticServer) return;
  const rendererRoot = path.join(projectRoot, 'dist/renderer');
  logElectronInfo(`[renderer:http] preparing static server root=${rendererRoot}`);
  rendererPort = await reservePort(4173, new Set([backendPort, cloudBackendPort]));
  logElectronInfo(`[renderer:http] reserved port=${rendererPort}`);
  rendererStaticServer = http.createServer((req, res) => {
    const requestUrl = req.url || '/';
    const pathname = decodeURIComponent(requestUrl.split('?')[0] || '/');
    const normalizedPath = pathname === '/' ? '/index.html' : pathname;
    const candidatePath = path.resolve(rendererRoot, `.${normalizedPath}`);
    const safePath = candidatePath.startsWith(rendererRoot) ? candidatePath : path.join(rendererRoot, 'index.html');
    const filePath = fs.existsSync(safePath) && fs.statSync(safePath).isFile() ? safePath : path.join(rendererRoot, 'index.html');

    fs.readFile(filePath, (error, buffer) => {
      if (error) {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Not found');
        return;
      }
      res.writeHead(200, {
        'Content-Type': rendererContentType(filePath),
        'Cache-Control': 'no-store',
      });
      res.end(buffer);
    });
  });

  await new Promise<void>((resolve, reject) => {
    if (!rendererStaticServer) {
      reject(new Error('renderer_static_server_missing'));
      return;
    }
    rendererStaticServer.once('error', reject);
    rendererStaticServer.listen(rendererPort, '127.0.0.1', () => resolve());
  });
  logElectronInfo(`[renderer:http] listening on http://127.0.0.1:${rendererPort}`);
}

function stopRendererStaticServer() {
  if (!rendererStaticServer) return;
  rendererStaticServer.close();
  rendererStaticServer = null;
}

function buildRendererFailurePage(detail: string) {
  const message = escapeHtml(detail);
  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${APP_DISPLAY_NAME}</title>
    <style>
      :root { color-scheme: light; }
      body {
        margin: 0;
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #eef3ff;
        font-family: "PingFang SC", "SF Pro Display", "Helvetica Neue", sans-serif;
        color: #1f2937;
      }
      .panel {
        width: min(560px, calc(100vw - 48px));
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid #dbe5ff;
        border-radius: 24px;
        box-shadow: 0 16px 48px rgba(91, 123, 254, 0.12);
        padding: 28px;
      }
      h1 {
        margin: 0 0 10px;
        font-size: 20px;
        line-height: 1.3;
      }
      p {
        margin: 0;
        font-size: 13px;
        line-height: 1.8;
        color: #4b5563;
        white-space: pre-wrap;
      }
    </style>
  </head>
  <body>
    <main class="panel">
      <h1>桌面界面加载失败</h1>
      <p>${message}</p>
    </main>
  </body>
</html>`;
}

function buildRendererBootstrapPage(detail = '正在连接本地界面与后台服务，请稍候…') {
  const message = escapeHtml(detail).replace(/\n/g, '<br />');

  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${APP_DISPLAY_NAME}</title>
    <style>
      html, body {
        margin: 0;
        min-height: 100%;
        background: linear-gradient(180deg, #f6f8ff 0%, #f9fafb 100%);
        font-family: "PingFang SC", "SF Pro Display", "Helvetica Neue", sans-serif;
      }
      body {
        display: flex;
        align-items: center;
        justify-content: center;
        color: #111827;
      }
      .panel {
        width: min(560px, calc(100vw - 64px));
        border-radius: 28px;
        border: 1px solid #dbe5ff;
        background: rgba(255, 255, 255, 0.96);
        box-shadow: 0 24px 72px rgba(15, 23, 42, 0.12);
        padding: 28px;
      }
      .eyebrow {
        margin: 0;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.22em;
        text-transform: uppercase;
        color: #4f46e5;
      }
      h1 {
        margin: 12px 0 0;
        font-size: 28px;
        line-height: 1.3;
      }
      p {
        margin: 14px 0 0;
        font-size: 14px;
        line-height: 1.9;
        color: #4b5563;
      }
      .meta {
        margin-top: 18px;
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 13px;
        color: #374151;
      }
      .spinner {
        width: 18px;
        height: 18px;
        border-radius: 999px;
        border: 2px solid #c7d2fe;
        border-top-color: #5b7bfe;
        animation: spin 1s linear infinite;
      }
      @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
      }
    </style>
  </head>
  <body>
    <main class="panel">
      <p class="eyebrow">Startup</p>
      <h1>${APP_DISPLAY_NAME}</h1>
      <p>${message}</p>
      <div class="meta">
        <span class="spinner" aria-hidden="true"></span>
        <span>如果停留过久，应用会自动切到启动诊断页。</span>
      </div>
    </main>
  </body>
</html>`;
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function buildStartupRepairPage(appInfo: DesktopAppInfo, rebuildRepoPath: string | null) {
  const payload = JSON.stringify({
    appBundlePath: appInfo.appBundlePath,
    recommendedInstallPath: appInfo.recommendedInstallPath,
    startupGateReason: appInfo.startupGateReason,
    detectedAppPaths: appInfo.detectedAppPaths,
    legacyAppPaths: appInfo.legacyAppPaths,
    rebuildRepoPath,
  }).replace(/</g, '\\u003c');

  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${APP_DISPLAY_NAME}</title>
    <style>
      html, body {
        margin: 0;
        min-height: 100%;
        background: radial-gradient(circle at top, #fff7ed 0%, #fff1f2 48%, #f8fafc 100%);
        font-family: "PingFang SC", "SF Pro Display", "Helvetica Neue", sans-serif;
        color: #111827;
      }
      body {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 28px;
      }
      .panel {
        width: min(760px, calc(100vw - 56px));
        border-radius: 28px;
        border: 1px solid #fecaca;
        background: rgba(255, 255, 255, 0.96);
        box-shadow: 0 24px 80px rgba(127, 29, 29, 0.12);
        padding: 28px;
      }
      .eyebrow {
        margin: 0;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.22em;
        text-transform: uppercase;
        color: #b91c1c;
      }
      h1 {
        margin: 12px 0 0;
        font-size: 28px;
        line-height: 1.3;
      }
      p {
        margin: 14px 0 0;
        font-size: 14px;
        line-height: 1.8;
        color: #4b5563;
      }
      .reason {
        margin-top: 18px;
        padding: 16px 18px;
        border-radius: 18px;
        background: #fff7ed;
        border: 1px solid #fed7aa;
        color: #9a3412;
        font-size: 13px;
        line-height: 1.8;
        white-space: pre-wrap;
      }
      .card {
        margin-top: 16px;
        border-radius: 18px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 16px 18px;
      }
      .card h2 {
        margin: 0;
        font-size: 13px;
      }
      .card p, .card li {
        margin-top: 8px;
        font-size: 12px;
        line-height: 1.8;
        color: #475569;
        word-break: break-all;
      }
      ul {
        margin: 8px 0 0;
        padding-left: 18px;
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-top: 22px;
      }
      button {
        border: 0;
        border-radius: 16px;
        padding: 12px 16px;
        font-size: 13px;
        font-weight: 700;
        cursor: pointer;
      }
      .primary {
        background: #5b7bfe;
        color: white;
      }
      .secondary {
        background: white;
        border: 1px solid #d1d5db;
        color: #374151;
      }
      .disabled {
        opacity: 0.45;
        cursor: not-allowed;
      }
      .status {
        margin-top: 14px;
        min-height: 20px;
        font-size: 12px;
        color: #475569;
      }
    </style>
  </head>
  <body>
    <main class="panel">
      <p class="eyebrow">Startup Gate Blocked</p>
      <h1>客户工作台已被安全拦截</h1>
      <p>当前安装态没有通过启动门禁。系统已阻止进入客户工作台主界面，避免继续使用旧包、错包或不一致运行态。</p>
      <div class="reason" id="reason"></div>
      <div class="card">
        <h2>当前运行包</h2>
        <p id="current-path"></p>
      </div>
      <div class="card">
        <h2>唯一建议安装入口</h2>
        <p id="recommended-path"></p>
      </div>
      <div class="card">
        <h2>检测到的相关安装包</h2>
        <ul id="detected-paths"></ul>
      </div>
      <div class="actions">
        <button class="primary" id="rebuild-button">从源码仓库重装</button>
        <button class="secondary" id="refresh-button">重新检查启动门禁</button>
        <button class="secondary" id="reveal-button">在 Finder 中显示当前包</button>
        <button class="secondary" id="quit-button">退出</button>
      </div>
      <div class="status" id="status"></div>
    </main>
    <script>
      const payload = ${payload};
      const currentPath = document.getElementById('current-path');
      const recommendedPath = document.getElementById('recommended-path');
      const reason = document.getElementById('reason');
      const detectedPaths = document.getElementById('detected-paths');
      const status = document.getElementById('status');
      const rebuildButton = document.getElementById('rebuild-button');
      const refreshButton = document.getElementById('refresh-button');
      const revealButton = document.getElementById('reveal-button');
      const quitButton = document.getElementById('quit-button');

      function renderPayload(nextPayload) {
        currentPath.textContent = nextPayload.appBundlePath || '(未知)';
        recommendedPath.textContent = nextPayload.recommendedInstallPath || '(未知)';
        reason.textContent = nextPayload.startupGateReason || '未返回具体阻断原因。';
        detectedPaths.innerHTML = '';
        if (Array.isArray(nextPayload.detectedAppPaths) && nextPayload.detectedAppPaths.length > 0) {
          for (const item of nextPayload.detectedAppPaths) {
            const li = document.createElement('li');
            const tag = Array.isArray(nextPayload.legacyAppPaths) && nextPayload.legacyAppPaths.includes(item)
              ? '旧入口'
              : (item === nextPayload.appBundlePath ? '当前运行包' : '重复安装包');
            li.textContent = tag + '：' + item;
            detectedPaths.appendChild(li);
          }
        } else {
          const li = document.createElement('li');
          li.textContent = '没有检测到其他相关入口。';
          detectedPaths.appendChild(li);
        }
      }

      renderPayload(payload);

      if (!payload.rebuildRepoPath || !window.yiyuWorkbench?.rebuildAndInstallFromRepo) {
        rebuildButton.disabled = true;
        rebuildButton.classList.add('disabled');
      }

      if (!window.yiyuWorkbench?.getDesktopAppInfo || !window.yiyuWorkbench?.resumeFromStartupGate) {
        refreshButton.disabled = true;
        refreshButton.classList.add('disabled');
      }

      async function recheckStartupGate(auto = false) {
        if (!window.yiyuWorkbench?.getDesktopAppInfo || !window.yiyuWorkbench?.resumeFromStartupGate) {
          return;
        }
        if (!auto) {
          status.textContent = '正在重新检查当前安装态…';
        }
        try {
          const latestInfo = await window.yiyuWorkbench.getDesktopAppInfo();
          renderPayload(latestInfo);
          if (latestInfo.startupGateStatus !== 'blocked') {
            status.textContent = '启动门禁已解除，正在进入客户工作台…';
            const resumeResult = await window.yiyuWorkbench.resumeFromStartupGate();
            if (!resumeResult?.resumed) {
              renderPayload(resumeResult?.appInfo || latestInfo);
              status.textContent = '当前包仍未通过启动门禁，请稍后重试。';
            }
            return;
          }
          if (!auto) {
            status.textContent = '当前安装态仍未通过启动门禁。';
          }
        } catch (error) {
          status.textContent = error instanceof Error ? error.message : String(error);
        }
      }

      rebuildButton.addEventListener('click', async () => {
        if (!payload.rebuildRepoPath) {
          status.textContent = '当前机器没有可直接重装的源码仓库。';
          return;
        }
        status.textContent = '正在从源码仓库重装最新安装包…';
        try {
          const accepted = await window.yiyuWorkbench.rebuildAndInstallFromRepo(payload.rebuildRepoPath);
          if (!accepted) {
            status.textContent = '当前仍有工作台编辑或输入未完成，已延后重装。请保存当前内容后再重试。';
          }
        } catch (error) {
          status.textContent = error instanceof Error ? error.message : String(error);
        }
      });

      refreshButton.addEventListener('click', () => {
        void recheckStartupGate(false);
      });

      revealButton.addEventListener('click', async () => {
        if (!payload.appBundlePath) {
          status.textContent = '当前包路径为空。';
          return;
        }
        try {
          await window.yiyuWorkbench.revealInFinder(payload.appBundlePath);
          status.textContent = '已在 Finder 中定位当前包。';
        } catch (error) {
          status.textContent = error instanceof Error ? error.message : String(error);
        }
      });

      quitButton.addEventListener('click', async () => {
        try {
          await window.yiyuWorkbench.quitApp();
        } catch (error) {
          status.textContent = error instanceof Error ? error.message : String(error);
        }
      });

      const autoTimer = window.setInterval(() => {
        if (document.hidden) return;
        void recheckStartupGate(true);
      }, 2500);
      window.addEventListener('beforeunload', () => window.clearInterval(autoTimer));
    </script>
  </body>
</html>`;
}

async function loadRendererWithFallback(window: BrowserWindow) {
  const devServerUrl = !app.isPackaged ? process.env.VITE_DEV_SERVER_URL : undefined;
  if (devServerUrl) {
    logElectronInfo(`[renderer:load] using dev server ${devServerUrl}`);
    await window.loadURL(devServerUrl);
    return 'dev';
  }

  const loadErrors: string[] = [];
  await registerRendererProtocol();
  logElectronInfo('[renderer:load] protocol registered');

  try {
    await startRendererStaticServer();
    logElectronInfo(`[renderer:load] loading http renderer ${rendererUrl()}`);
    await window.loadURL(rendererUrl());
    logElectronInfo('[renderer:load] http renderer loaded');
    return 'http';
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    loadErrors.push(`http:${detail}`);
    logElectronError(`[renderer:load] http_failed=${detail}`);
  }

  try {
    logElectronInfo(`[renderer:load] loading protocol renderer ${rendererProtocolUrl()}`);
    await window.loadURL(rendererProtocolUrl());
    logElectronInfo('[renderer:load] protocol renderer loaded');
    return 'app';
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    loadErrors.push(`app:${detail}`);
    logElectronError(`[renderer:load] app_failed=${detail}`);
  }

  const failureMessage = loadErrors.length > 0
    ? `渲染界面启动失败。\n${loadErrors.join('\n')}`
    : '渲染界面启动失败。';
  await window.loadURL(rendererFailurePageUrl(failureMessage));
  return 'error';
}

function buildBackendStartupError(prefix: string) {
  const tail = backendRecentLogLines.slice(-10).join('\n');
  if (tail) {
    return `${prefix}\n\n最近日志：\n${tail}`;
  }
  return prefix;
}

// 首次冷启动 timeout 抬到 180s：backend/app/models.py 有 720+ 个 Pydantic BaseModel
// 子类,加上 qdrant_client / fastembed 等大型库,首次 import 需要 100s+。
// .pyc 缓存热的情况下 30-40s 就够,但保留余量避免冷启动失败。
// retry/restart 那几条(20s/30s)不动 — backend 已经热,够用。
async function waitForBackend(timeoutMs = 180_000): Promise<BackendHealthPayload> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (backendExitDetail) {
      throw new Error(buildBackendStartupError(backendExitDetail));
    }
    try {
      const payload = await new Promise<BackendHealthPayload>((resolve, reject) => {
        const req = http.get(`${backendUrl()}/api/v1/system/health`, (res) => {
          if ((res.statusCode ?? 500) >= 500) {
            reject(new Error(`status=${res.statusCode}`));
            return;
          }
          const chunks: Buffer[] = [];
          res.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
          res.on('end', () => {
            try {
              const payload = JSON.parse(Buffer.concat(chunks).toString('utf-8')) as BackendHealthPayload;
              const featureFlags = Array.isArray(payload.featureFlags) ? payload.featureFlags : [];
              const missing = REQUIRED_BACKEND_FEATURES.filter((feature) => !featureFlags.includes(feature));
              if (missing.length > 0) {
                reject(new Error(`backend_missing_features:${missing.join(',')}`));
                return;
              }
              const runtimeWarning = evaluateBackendRuntimeWarning(payload);
              if (runtimeWarning) {
                logElectronError(`[backend:runtime-warning] ${runtimeWarning}`);
              }
              resolve(payload);
            } catch (error) {
              reject(error);
            }
          });
        });
        req.on('error', reject);
      });
      return payload;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 400));
    }
  }
  throw new Error(buildBackendStartupError(`后端服务启动超时（>${Math.round(timeoutMs / 1000)} 秒）`));
}

async function waitForCloudBackend(timeoutMs = 60000): Promise<void> {
  // 默认从 20s 提到 60s——cloud_backend 首次启动可能要跑 schema migration / 加载向量库等慢操作,
  // 20s 不够会被 Electron 主进程 kill,留下 47830 端口空、维护模式 502 假象。
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    try {
      await new Promise<void>((resolve, reject) => {
        const req = http.get(`${cloudBackendUrl()}/health`, (res) => {
          if ((res.statusCode ?? 500) < 500) {
            res.resume();
            resolve();
            return;
          }
          reject(new Error(`status=${res.statusCode}`));
        });
        req.on('error', reject);
      });
      return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 400));
    }
  }
  throw new Error('中心后端启动超时');
}

async function createMainWindow(options: { startupGateInfo?: DesktopAppInfo | null } = {}) {
  mainWindow = new BrowserWindow({
    width: 1600,
    height: 980,
    minWidth: 1280,
    minHeight: 820,
    title: APP_DISPLAY_NAME,
    backgroundColor: '#eef3ff',
    titleBarStyle: 'hiddenInset',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    logElectronInfo(`[renderer:console:${level}] ${sourceId}:${line} ${message}`);
  });
  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    logElectronError(`[renderer:did-fail-load] code=${errorCode} description=${errorDescription} url=${validatedURL}`);
  });
  mainWindow.webContents.on('did-finish-load', () => {
    logElectronInfo(`[renderer:did-finish-load] url=${mainWindow?.webContents.getURL() ?? 'unknown'}`);
    const targetWindow = mainWindow;
    setTimeout(() => {
      if (!targetWindow || targetWindow.isDestroyed()) return;
      void targetWindow.webContents.executeJavaScript(`
        (() => {
          const root = document.getElementById('root');
          const style = root ? window.getComputedStyle(root) : null;
          return {
            href: location.href,
            readyState: document.readyState,
            title: document.title,
            rootChildCount: root?.childElementCount ?? 0,
            rootHtmlLength: root?.innerHTML?.length ?? 0,
            rootTextLength: (root?.textContent || '').trim().length,
            rootSnippet: (root?.textContent || '').trim().slice(0, 240),
            bodyTextLength: (document.body?.innerText || '').trim().length,
            bodySnippet: (document.body?.innerText || '').trim().slice(0, 240),
            rootDisplay: style?.display || null,
            rootVisibility: style?.visibility || null,
            rootOpacity: style?.opacity || null,
            bootEvents: Array.isArray(window.__YIYU_BOOT_EVENTS__) ? window.__YIYU_BOOT_EVENTS__ : [],
            appRendered: Boolean(window.__YIYU_APP_RENDERED__),
          };
        })()
      `, true)
        .then((snapshot) => {
          logElectronInfo(`[renderer:dom-snapshot] ${JSON.stringify(snapshot)}`);
        })
        .catch((error) => {
          const detail = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
          logElectronError(`[renderer:dom-snapshot-failed] ${detail}`);
        });
    }, 1800);
  });
  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    logElectronError(`[renderer:process-gone] reason=${details.reason} exitCode=${details.exitCode}`);
  });
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  setupAutoUpdater(mainWindow);

  await mainWindow.loadURL(rendererBootstrapPageUrl());
  if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.isVisible()) {
    logElectronInfo('[window] showing startup bootstrap page');
    mainWindow.show();
    mainWindow.focus();
  }

  if (options.startupGateInfo?.startupGateStatus === 'blocked') {
    const rebuildRepoPath = app.isPackaged
      ? null
      : await loadInternalCollabGit()
        .then((collabGit) => collabGit.findSuggestedCollabRepoPath(getCollabSuggestedCandidates()))
        .catch(() => null);
    await mainWindow.loadURL(startupRepairPageUrl(options.startupGateInfo, rebuildRepoPath));
    if (!mainWindow.isVisible()) {
      mainWindow.show();
    }
    mainWindow.focus();
    app.focus({ steal: true });
    return;
  }

  const loadMode = await loadRendererWithFallback(mainWindow);
  if (loadMode === 'dev') {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }
  if (loadMode !== 'error' && mainWindow && !mainWindow.isDestroyed()) {
    if (!mainWindow.isVisible()) {
      logElectronInfo('[window] showing renderer after fallback load');
      mainWindow.show();
    }
    mainWindow.focus();
    app.focus({ steal: true });
  }
  await new Promise((resolve) => setTimeout(resolve, 1200));
  if (loadMode !== 'error' && mainWindow && !mainWindow.isDestroyed()) {
    await runTaskWindowDiagnostics(mainWindow);
    await runEventLineCreateDiagnostics(mainWindow);
    await runUiSurfaceAudit(mainWindow);
  }
}

const uiRuntimeAuditMode = Boolean((process.env.YIYU_UI_RUNTIME_AUDIT_OUTPUT || '').trim());
const gotSingleInstanceLock = uiRuntimeAuditMode ? true : app.requestSingleInstanceLock();
appendElectronLaunchLog('INFO', `[app] singleInstanceLock=${gotSingleInstanceLock}`);

if (!gotSingleInstanceLock) {
  appendElectronLaunchLog('ERROR', '[app] failed to acquire single-instance lock, quitting');
  requestAppQuit('single_instance_lock_failed', 'startup', {});
}

app.on('second-instance', () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    if (mainWindow.isMinimized()) {
      mainWindow.restore();
    }
    mainWindow.focus();
    return;
  }
  const existingWindow = BrowserWindow.getAllWindows()[0];
  if (existingWindow) {
    if (existingWindow.isMinimized()) {
      existingWindow.restore();
    }
    existingWindow.focus();
    return;
  }
  void resolveDesktopAppInfo().then((appInfo) => createMainWindow({ startupGateInfo: appInfo }));
});

app.whenReady().then(async () => {
  appendElectronLaunchLog('INFO', '[app] whenReady entered');
  const reservedPorts = new Set<number>();
  const reuseExistingBackend = await checkBackendHealthAt(DEFAULT_BACKEND_PORT, REQUIRED_BACKEND_FEATURES);
  backendPort = reuseExistingBackend ? DEFAULT_BACKEND_PORT : await reservePort(DEFAULT_BACKEND_PORT, reservedPorts);
  reservedPorts.add(backendPort);
  const usingRemoteCloudBackend = shouldUseRemoteCloudBackend();
  const usingLocalCloudBackend = shouldUseBundledLocalCloudBackend();
  const configuredRemoteCloudBackendUrl = remoteCloudBackendUrl();
  let reuseExistingCloudBackend = false;
  if (usingRemoteCloudBackend) {
    logElectronInfo(`[cloud] using remote collaboration backend ${configuredRemoteCloudBackendUrl}`);
  } else if (usingLocalCloudBackend) {
    reuseExistingCloudBackend = await checkCloudBackendHealthAt(DEFAULT_CLOUD_BACKEND_PORT);
    cloudBackendPort = reuseExistingCloudBackend ? DEFAULT_CLOUD_BACKEND_PORT : await reservePort(DEFAULT_CLOUD_BACKEND_PORT, reservedPorts);
    reservedPorts.add(cloudBackendPort);
  } else {
    logElectronInfo('[cloud] no collaboration backend configured; cloud login/sync will stay disabled until settings are configured');
  }
  process.env.YIYU_BACKEND_URL = backendUrl();
  const configuredCloudUrl = cloudBackendUrl();
  if (configuredCloudUrl) {
    process.env.YIYU_CLOUD_API_URL = configuredCloudUrl;
  } else {
    delete process.env.YIYU_CLOUD_API_URL;
  }
  uvBinaryPath = resolveUvBinary();
  if (!app.isPackaged && !uvBinaryPath) {
    dialog.showErrorBox(
      '缺少 uv 运行时',
      '启动桌面应用前需要先安装 uv。请先执行 `curl -LsSf https://astral.sh/uv/install.sh | sh`，然后重新打开应用。',
    );
    requestAppQuit('missing_uv_runtime', 'startup', {});
    return;
  }
  const runtimeRoot = path.join(app.getPath('userData'), 'runtime');
  backendRuntimeVenv = path.join(runtimeRoot, 'backend-venv');
  cloudBackendRuntimeVenv = path.join(runtimeRoot, 'cloud-backend-venv');
  try {
    await ensureProjectRuntime('backend', backendRuntimeVenv);
    if (usingLocalCloudBackend) {
      await ensureProjectRuntime('cloud_backend', cloudBackendRuntimeVenv);
    }
    await registerRendererProtocol();
    await recyclePackagedRuntimeProcesses();
    purgeSavedApplicationState();
    await cleanupStaleInstallBundles();
  } catch (error) {
    dialog.showErrorBox('后端运行时准备失败', error instanceof Error ? error.message : String(error));
    requestAppQuit('runtime_prepare_failed', 'startup', { error: error instanceof Error ? error.message : String(error) });
    return;
  }
  if (usingLocalCloudBackend && !reuseExistingCloudBackend) {
    startCloudBackend();
  }
  if (!reuseExistingBackend) {
    startBackend();
  }
  let backendHealth: BackendHealthPayload | null = null;
  try {
    backendHealth = await waitForBackend();
  } catch (firstError) {
    logElectronError(`[backend:start] first attempt failed: ${firstError instanceof Error ? firstError.message : String(firstError)}`);
    if (!reuseExistingBackend) {
      try {
        await terminateManagedRuntimeProcess(backendRuntimeVenv);
      } catch {
        // Ignore cleanup failure and still retry once.
      }
      stopBackend();
      startBackend();
      try {
        backendHealth = await waitForBackend(30000);
      } catch (secondError) {
        dialog.showErrorBox('本地后端启动失败', secondError instanceof Error ? secondError.message : String(secondError));
        requestAppQuit('backend_start_failed_after_retry', 'startup', { error: secondError instanceof Error ? secondError.message : String(secondError) });
        return;
      }
    } else {
      dialog.showErrorBox('本地后端启动失败', firstError instanceof Error ? firstError.message : String(firstError));
      requestAppQuit('backend_start_failed_reused_backend', 'startup', { error: firstError instanceof Error ? firstError.message : String(firstError) });
      return;
    }
  }
  const desktopAppInfo = await resolveDesktopAppInfo(backendHealth);
  appendElectronLaunchLog('INFO', '[app] creating main window');
  try {
    await createMainWindow({ startupGateInfo: desktopAppInfo });
  } catch (error) {
    dialog.showErrorBox('桌面界面启动失败', error instanceof Error ? error.message : String(error));
    requestAppQuit('main_window_create_failed', 'startup', { error: error instanceof Error ? error.message : String(error) });
    return;
  }
  appendElectronLaunchLog('INFO', '[app] main window created successfully');
  if (usingLocalCloudBackend || usingRemoteCloudBackend) {
    void waitForCloudBackend().catch((error) => {
      logElectronError(error instanceof Error ? (error.stack || error.message) : String(error));
    });
  }
  appendElectronLaunchLog('INFO', '[app] startup sequence complete, app should stay alive');

  // 后端进程 watchdog —— 检测以下三种"挂了"情形并自动拉起：
  //   (a) backendProcess 句柄已被 exit 回调清掉（进程 crash）
  //   (b) ~~进程还在但 health probe 失败（僵尸进程 / 卡在死循环）~~
  //       已禁用：health probe timeout 仅 800ms，backend 处理慢请求时会被误判，
  //       结果反而把好好的 backend 杀掉重启，比"等真正僵尸"还危险。
  //       只在进程 handle 已死时才重启。
  //   (c) 启动失败时按指数退避重试，避免连续 crash 导致 spawn 风暴
  // 失败 5 次以上认为是"持续不可用"，通过 IPC 通知 renderer 显示诊断面板。
  let watchdogRestartAttempts = 0;
  let watchdogLastRestartFailedAt = 0;
  let watchdogInFlight = false;
  const WATCHDOG_BASE_INTERVAL_MS = 8_000;
  const WATCHDOG_MAX_BACKOFF_MS = 30_000;

  const _watchdogBackoffMs = (attempts: number): number => {
    if (attempts <= 0) return 0;
    return Math.min(WATCHDOG_MAX_BACKOFF_MS, 2_000 * 2 ** (attempts - 1));
  };

  setInterval(async () => {
    if (!ownsBackendProcess) return;
    if (watchdogInFlight) return;
    // 进程还在 → 不动；进程 handle 为 null 才需要重启。
    // health probe 不参与"是否要重启"的决策——仅在重启成功后才用 waitForBackend 确认。
    if (backendProcess) {
      // 进程活着就当好。即使 health 慢也不杀。
      if (watchdogRestartAttempts > 0) {
        appendElectronLaunchLog('INFO', `[backend:watchdog] backend process alive again, reset attempts (was ${watchdogRestartAttempts})`);
        watchdogRestartAttempts = 0;
        watchdogLastRestartFailedAt = 0;
      }
      return;
    }
    // 走到这里说明 backendProcess === null：crash 了。计算 backoff 时间。
    const backoffMs = _watchdogBackoffMs(watchdogRestartAttempts);
    if (backoffMs > 0 && Date.now() - watchdogLastRestartFailedAt < backoffMs) {
      return; // 还在退避窗口内
    }
    watchdogInFlight = true;
    watchdogRestartAttempts += 1;
    try {
      appendElectronLaunchLog('INFO', `[backend:watchdog] restart attempt #${watchdogRestartAttempts}`);
      startBackend();
      await waitForBackend(20_000);
      appendElectronLaunchLog('INFO', `[backend:watchdog] backend restarted successfully on attempt #${watchdogRestartAttempts}`);
      watchdogRestartAttempts = 0;
      watchdogLastRestartFailedAt = 0;
    } catch (error) {
      watchdogLastRestartFailedAt = Date.now();
      const detail = error instanceof Error ? error.message : String(error);
      appendElectronLaunchLog('ERROR', `[backend:watchdog] restart attempt #${watchdogRestartAttempts} failed: ${detail}`);
      if (watchdogRestartAttempts >= 5 && mainWindow && !mainWindow.isDestroyed()) {
        // 持续失败 → 通过 webContents 通知 renderer 弹诊断面板
        try {
          mainWindow.webContents.send('backend-watchdog-exhausted', {
            attempts: watchdogRestartAttempts,
            lastError: detail,
            logsDir: path.join(app.getPath('userData'), 'logs'),
          });
        } catch {}
      }
    } finally {
      watchdogInFlight = false;
    }
  }, WATCHDOG_BASE_INTERVAL_MS);

  app.on('activate', async () => {
    // Re-activate: ensure backend is alive before showing window
    if (ownsBackendProcess && !backendProcess) {
      // Backend was owned but has exited — restart it
      appendElectronLaunchLog('INFO', '[app:activate] backend exited, restarting');
      try {
        startBackend();
        await waitForBackend(20000);
      } catch {
        appendElectronLaunchLog('ERROR', '[app:activate] backend restart failed');
      }
    } else if (!ownsBackendProcess && !backendProcess) {
      // No backend at all — check if it's reachable
      const alive = await checkBackendHealthAt(backendPort, []);
      if (!alive) {
        appendElectronLaunchLog('INFO', '[app:activate] backend unreachable, starting fresh');
        try {
          startBackend();
          await waitForBackend(20000);
        } catch {
          appendElectronLaunchLog('ERROR', '[app:activate] backend start failed');
        }
      }
    }
    if (!mainWindow || mainWindow.isDestroyed() || BrowserWindow.getAllWindows().length === 0) {
      try {
        const appInfo = await resolveDesktopAppInfo();
        await createMainWindow({ startupGateInfo: appInfo });
      } catch (error) {
        dialog.showErrorBox('桌面界面启动失败', error instanceof Error ? error.message : String(error));
      }
    } else {
      if (latestDesktopAppInfo?.startupGateStatus === 'blocked') {
        try {
          const resumeResult = await resumeFromStartupGate();
          if (resumeResult.resumed) {
            return;
          }
        } catch (error) {
          logElectronError(`[app:activate] startup gate refresh failed: ${error instanceof Error ? error.message : String(error)}`);
        }
      }
      mainWindow.show();
      mainWindow.focus();
    }
  });
});

let isRecordingActive = false;
let recordingTaskTitle = '';
let userConfirmedQuitDespiteRecording = false;

// 退出守卫：渲染端每隔几秒把"后端真相"(跨客户的进行中/排队后台任务)上报到这里，
// before-quit 把它和录音合并成一个提醒。带新鲜度 TTL，渲染端停报后视为不可信即忽略，避免幽灵条目卡死退出。
interface ReportedBackgroundTask {
  kind: string;
  label: string;
  status?: string;
  severity?: 'loss' | 'queued';
}
let reportedBackgroundTasks: ReportedBackgroundTask[] = [];
let reportedBackgroundTasksAt = 0;
const BACKGROUND_TASKS_FRESH_MS = 15000;

ipcMain.handle(
  'yiyu-workbench:setRecordingActive',
  async (_event, payload: { active: boolean; taskTitle?: string }) => {
    isRecordingActive = Boolean(payload?.active);
    recordingTaskTitle = (payload?.taskTitle || '').trim();
    appendElectronLaunchLog(
      'INFO',
      `[recording] setRecordingActive active=${isRecordingActive} title=${recordingTaskTitle.slice(0, 60)}`,
    );
    return { active: isRecordingActive };
  },
);

ipcMain.handle(
  'yiyu-workbench:setBackgroundTasks',
  async (_event, payload?: { tasks?: ReportedBackgroundTask[] }) => {
    const incoming = Array.isArray(payload?.tasks) ? payload!.tasks! : [];
    reportedBackgroundTasks = incoming.filter(
      (task): task is ReportedBackgroundTask => Boolean(task && typeof task.label === 'string' && task.label.trim()),
    );
    reportedBackgroundTasksAt = Date.now();
    return { ok: true, count: reportedBackgroundTasks.length };
  },
);

app.on('before-quit', (event) => {
  // 合并"录音 + 后端上报的后台任务"成一份退出提醒清单。
  const items: { label: string; severity: 'loss' | 'queued' }[] = [];
  if (isRecordingActive) {
    items.push({ label: `录音「${recordingTaskTitle || '未命名录音文件'}」`, severity: 'loss' });
  }
  const tasksFresh = Date.now() - reportedBackgroundTasksAt <= BACKGROUND_TASKS_FRESH_MS;
  if (tasksFresh) {
    for (const task of reportedBackgroundTasks) {
      items.push({ label: task.label, severity: task.severity === 'queued' ? 'queued' : 'loss' });
    }
  }
  if (items.length > 0 && !userConfirmedQuitDespiteRecording) {
    const targetWindow = BrowserWindow.getAllWindows().find((w) => !w.isDestroyed()) ?? null;
    const lines = items.map((item, index) => `${index + 1}. ${item.label}`).join('\n');
    const lossCount = items.filter((item) => item.severity === 'loss').length;
    const tail = lossCount > 0
      ? '退出软件会中断这些任务，可能导致失败或内容丢失。'
      : '退出后排队中的任务不会自动继续。';
    const choice = dialog.showMessageBoxSync(
      targetWindow as BrowserWindow,
      {
        type: 'warning',
        buttons: ['取消退出', '仍然退出'],
        defaultId: 0,
        cancelId: 0,
        title: '后台任务进行中',
        message: `当前有 ${items.length} 个后台任务正在进行`,
        detail: `${lines}\n\n${tail}\n\n确定要退出吗？`,
        noLink: true,
      },
    );
    appendElectronLaunchLog('INFO', `[app] before-quit background-block items=${items.length} choice=${choice}`);
    if (choice === 0) {
      event.preventDefault();
      return;
    }
    userConfirmedQuitDespiteRecording = true;
    isRecordingActive = false;
  }
  appendElectronLaunchLog('INFO', `[app] before-quit fired quitRequest=${JSON.stringify(lastQuitRequest || { reason: 'unknown_external_or_system' })}`);
  stopBackend();
  stopCloudBackend();
});
app.on('will-quit', () => {
  appendElectronLaunchLog('INFO', `[app] will-quit fired quitRequest=${JSON.stringify(lastQuitRequest || { reason: 'unknown_external_or_system' })}`);
});
app.on('window-all-closed', () => {
  appendElectronLaunchLog('INFO', '[app] window-all-closed fired');
  if (process.platform !== 'darwin') {
    requestAppQuit('window_all_closed', 'app_event', {});
  }
});

ipcMain.handle('yiyu-workbench:selectFiles', async () => {
  const result = await dialog.showOpenDialog({
    title: '选择客户资料文件',
    properties: ['openFile', 'multiSelections'],
  });
  return result.canceled ? [] : result.filePaths;
});

ipcMain.handle('yiyu-workbench:getDesktopAppInfo', async () => {
  return resolveDesktopAppInfo();
});

// 迷你面板(桌面挂件):缩小 = 右上角小窗 + 置顶 + 隐藏红绿灯;还原 = 复位原 bounds。
// macOS 原生全屏(独立 Space)期间 setBounds 无效——必须先 setFullScreen(false) 等动画完再 resize。
let miniSavedBounds: Electron.Rectangle | null = null;
function applyMiniBounds(win: BrowserWindow) {
  if (win.isDestroyed()) return;
  miniSavedBounds = win.getBounds();
  const W = 360;
  const H = 480;
  const area = screen.getDisplayMatching(miniSavedBounds).workArea;
  win.setMinimumSize(300, 380);
  // 5/29: 迷你卡片默认缩到桌面左上角(原为右上角 area.x + area.width - W - 24)
  win.setBounds({ x: area.x + 24, y: area.y + 24, width: W, height: H });
  win.setAlwaysOnTop(true, 'floating');
  if (process.platform === 'darwin') win.setWindowButtonVisibility(false);
}
ipcMain.handle('yiyu-workbench:setUpdateOrgIdentity', async (_event, identity: UpdateOrgIdentity | null) => {
  // renderer 登录拿到 organizationId/organizationSlug 后调用;统一登记到官网中央发布服务。
  try {
    await setUpdateOrgIdentity({
      ...(identity || {}),
      cloudBackendUrl: identity?.cloudBackendUrl || cloudBackendUrl(),
    });
    return { ok: true };
  } catch (err) {
    return { ok: false, reason: err instanceof Error ? err.message : String(err) };
  }
});

ipcMain.handle('yiyu-workbench:setUpdateOrgCode', async (_event, orgCode: string | null) => {
  // 兼容旧 renderer:旧入口仍可传 slug,但内部改走官网中央发布服务。
  try {
    await setUpdateOrgCode(orgCode ?? null, cloudBackendUrl());
    return { ok: true };
  } catch (err) {
    return { ok: false, reason: err instanceof Error ? err.message : String(err) };
  }
});

ipcMain.handle('yiyu-workbench:setMiniMode', (_event, enter: boolean) => {
  if (!mainWindow) return { mini: false };
  const win = mainWindow;
  if (enter) {
    if (win.isFullScreen()) {
      // 全屏退出是异步动画;监听 'leave-full-screen' 完成后再 resize, 否则 setBounds 被吞
      win.once('leave-full-screen', () => applyMiniBounds(win));
      win.setFullScreen(false);
    } else {
      if (win.isMaximized()) win.unmaximize();
      applyMiniBounds(win);
    }
  } else {
    win.setAlwaysOnTop(false);
    if (process.platform === 'darwin') win.setWindowButtonVisibility(true);
    win.setMinimumSize(1280, 820);
    if (miniSavedBounds) win.setBounds(miniSavedBounds);
  }
  return { mini: enter };
});

ipcMain.handle('yiyu-workbench:resumeFromStartupGate', async () => {
  return resumeFromStartupGate();
});

ipcMain.handle('yiyu-workbench:selectFolder', async () => {
  const result = await dialog.showOpenDialog({
    title: '选择客户资料目录',
    properties: ['openDirectory'],
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('yiyu-workbench:selectCollabRepo', async () => {
  const collabGit = await loadInternalCollabGit();
  const result = await dialog.showOpenDialog({
    title: '选择源码仓库目录',
    properties: ['openDirectory'],
  });
  if (result.canceled || !result.filePaths[0]) return null;
  const repoPath = await collabGit.findSuggestedCollabRepoPath([result.filePaths[0]]);
  if (!repoPath) {
    throw new Error('你选中的目录不是 Git 源码仓库，请重新选择。');
  }
  return repoPath;
});

ipcMain.handle('yiyu-workbench:getCollabRepoStatus', async (_event, repoPath?: string | null) => {
  const collabGit = await loadInternalCollabGit();
  return collabGit.getCollabRepoStatus({
    repoPath,
    suggestedCandidates: getCollabSuggestedCandidates(),
    appDbPath: path.join(app.getPath('userData'), 'app.db'),
  });
});

ipcMain.handle('yiyu-workbench:previewPushToMain', async (_event, repoPath: string) => {
  await requireActiveMaintenanceMode('预览推送修改');
  const collabGit = await loadInternalCollabGit();
  return collabGit.previewPushToMain({
    repoPath,
    suggestedCandidates: getCollabSuggestedCandidates(),
    appDbPath: path.join(app.getPath('userData'), 'app.db'),
  });
});

ipcMain.handle('yiyu-workbench:pushSafelyToMain', async (_event, payload) => {
  await requireActiveMaintenanceMode('安全推送 main');
  const collabGit = await loadInternalCollabGit();
  return collabGit.pushSafelyToMain(payload, getCollabSuggestedCandidates(), path.join(app.getPath('userData'), 'app.db'));
});

ipcMain.handle('yiyu-workbench:publishCollabBranch', async (_event, payload) => {
  await requireActiveMaintenanceMode('发布协作分支');
  const collabGit = await loadInternalCollabGit();
  return collabGit.publishCollabBranch(payload, getCollabSuggestedCandidates(), path.join(app.getPath('userData'), 'app.db'));
});

ipcMain.handle('yiyu-workbench:previewPullFromMain', async (_event, repoPath: string, targetCommit?: string | null) => {
  await requireActiveMaintenanceMode('预览 main 修改');
  const collabGit = await loadInternalCollabGit();
  return collabGit.previewPullFromMain({
    repoPath,
    targetCommit,
    suggestedCandidates: getCollabSuggestedCandidates(),
    appDbPath: path.join(app.getPath('userData'), 'app.db'),
  });
});

ipcMain.handle('yiyu-workbench:fastForwardMain', async (_event, payload) => {
  await requireActiveMaintenanceMode('快进接收 main');
  const collabGit = await loadInternalCollabGit();
  return collabGit.fastForwardMain(payload, getCollabSuggestedCandidates(), path.join(app.getPath('userData'), 'app.db'));
});

ipcMain.handle('yiyu-workbench:startCollabPreview', async (_event, payload) => {
  await requireActiveMaintenanceMode('开启协作预览');
  const collabGit = await loadInternalCollabGit();
  return collabGit.startCollabPreview(
    payload,
    getCollabSuggestedCandidates(),
    path.join(app.getPath('userData'), 'app.db'),
    path.join(app.getPath('userData'), 'collab-previews'),
  );
});

ipcMain.handle('yiyu-workbench:stopCollabPreview', async (_event, payload) => {
  await requireActiveMaintenanceMode('停止协作预览');
  const collabGit = await loadInternalCollabGit();
  return collabGit.stopCollabPreview(payload, getCollabSuggestedCandidates());
});

ipcMain.handle('yiyu-workbench:setWorkspaceInteractionState', async (_event, payload?: {
  active?: boolean;
  source?: string;
  detail?: string | null;
}) => {
  workspaceInteractionState = {
    active: Boolean(payload?.active),
    source: String(payload?.source || 'renderer'),
    detail: payload?.detail ? String(payload.detail) : null,
    updatedAt: new Date().toISOString(),
  };
  appendElectronLaunchLog('INFO', `[workspace-interaction] ${JSON.stringify(workspaceInteractionState)}`);
  return workspaceInteractionState;
});

ipcMain.handle('yiyu-workbench:rebuildAndInstallFromRepo', async (_event, repoPath: string) => {
  if (typeof repoPath !== 'string' || repoPath.length === 0) {
    throw new Error('rebuildAndInstallFromRepo: 缺少 repoPath');
  }
  const normalizedRepoPath = path.resolve(repoPath);
  if (process.platform !== 'darwin') {
    throw new Error('源码已同步；Windows 自动重装暂未接入签名安装链路，请先由 Codex 或打包流程重新构建 Windows 安装包。');
  }
  let pathStat: fs.Stats;
  try {
    pathStat = fs.statSync(normalizedRepoPath);
  } catch {
    throw new Error('rebuildAndInstallFromRepo: 路径不存在');
  }
  if (!pathStat.isDirectory()) {
    throw new Error('rebuildAndInstallFromRepo: 路径不是目录');
  }
  // 不走 shell，中文路径和括号都可以；危险字符不会被解释成命令。
  if (!fs.existsSync(path.join(normalizedRepoPath, 'package.json')) ||
      !fs.existsSync(path.join(normalizedRepoPath, '.git'))) {
    throw new Error('rebuildAndInstallFromRepo: 路径不是合法的 yiyu git repo');
  }
  const metadata = {
    repoPath: normalizedRepoPath,
    startupGatePageActive: isStartupGatePageActive(),
  };
  appendElectronLaunchLog('INFO', `[rebuild-install-request] ${JSON.stringify({
    ...metadata,
    workspaceInteractionState,
  })}`);
  if (shouldDeferDangerousRestart()) {
    appendElectronLaunchLog('ERROR', `[rebuild-install-request] deferred because workspace interaction is active ${JSON.stringify(workspaceInteractionState)}`);
    return false;
  }
  fs.mkdirSync(runtimeLogsDir, { recursive: true });
  fs.appendFileSync(collabRebuildLogPath, `\n[${new Date().toISOString()}] start rebuild from ${normalizedRepoPath}\n`, 'utf8');
  // 用 spawn 数组参数: 不走 shell, 不存在命令注入面
  // npm run dist:mac-local 必须在 repo 目录 cwd 下跑
  const logStream = fs.createWriteStream(collabRebuildLogPath, { flags: 'a' });
  const rebuildChild = spawn('npm', ['run', 'dist:mac-local'], {
    cwd: normalizedRepoPath,
    detached: true,
    stdio: ['ignore', logStream, logStream],
  });
  rebuildChild.unref();
  // open-installed-app 在 rebuild 之后才有意义, 但这里 detached 不能 chain.
  // 改成: rebuild 进程结束时 spawn 第二条命令
  rebuildChild.on('exit', (code) => {
    fs.appendFileSync(
      collabRebuildLogPath,
      `\n[${new Date().toISOString()}] rebuild exited code=${code}, launching installed app\n`,
      'utf8',
    );
    if (code === 0) {
      const launchChild = spawn('node', ['scripts/open-installed-app.mjs'], {
        cwd: normalizedRepoPath,
        detached: true,
        stdio: ['ignore', logStream, logStream],
      });
      launchChild.unref();
    }
  });
  setTimeout(() => {
    requestAppQuit('rebuild_and_install_from_repo', 'ipc:yiyu-workbench:rebuildAndInstallFromRepo', metadata);
  }, 300);
  return true;
});

ipcMain.handle('yiyu-workbench:quitApp', async () => {
  setTimeout(() => requestAppQuit('manual_quit', 'ipc:yiyu-workbench:quitApp', {}), 50);
  return true;
});

ipcMain.handle('yiyu-workbench:readTextFile', async (_event, targetPath: string) => {
  const resolvedPath = path.resolve(targetPath);
  const stat = await fs.promises.stat(resolvedPath).catch(() => null);
  if (!stat || !stat.isFile()) {
    throw new Error('文件不存在，无法读取。');
  }
  const extension = path.extname(resolvedPath).toLowerCase();
  if (['.docx', '.pdf'].includes(extension)) {
    if (stat.size > 15 * 1024 * 1024) {
      throw new Error('当前只支持 15MB 以内的 docx/pdf DNA 文档。');
    }
    return extractPlatformDnaText(resolvedPath);
  }
  if (stat.size > 1024 * 1024) {
    throw new Error('当前只支持 1MB 以内的文本 DNA 文档。');
  }
  return fs.promises.readFile(resolvedPath, 'utf-8');
});

function inferClientWorkspaceRootFromPath(targetPath: string) {
  const normalized = path.resolve(targetPath);
  const parts = normalized.split(path.sep);
  const index = parts.indexOf('client_workspace');
  if (index < 0 || parts.length <= index + 1) return null;
  const root = path.join(path.sep, ...parts.slice(1, index + 2));
  return fs.existsSync(root) ? root : null;
}

function findSameNamedWorkspaceFile(targetPath: string) {
  const root = inferClientWorkspaceRootFromPath(targetPath);
  if (!root) return null;
  const targetName = path.basename(targetPath);
  if (!targetName) return null;
  const stack = [root];
  while (stack.length > 0) {
    const current = stack.pop();
    if (!current) continue;
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(current, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      const fullPath = path.join(current, entry.name);
      if (entry.isFile() && entry.name === targetName) {
        return fullPath;
      }
      if (entry.isDirectory()) {
        stack.push(fullPath);
      }
    }
  }
  return null;
}

ipcMain.handle('yiyu-workbench:openPath', async (_event, targetPath: string) => {
  const message = await shell.openPath(targetPath);
  if (message === '') {
    return true;
  }
  const recoveredPath = findSameNamedWorkspaceFile(targetPath);
  if (recoveredPath && recoveredPath !== targetPath) {
    const recoveredMessage = await shell.openPath(recoveredPath);
    if (recoveredMessage === '') {
      console.warn(`[openPath] recovered stale path=${targetPath} -> ${recoveredPath}`);
      return true;
    }
    console.warn(`[openPath] recovered path failed path=${recoveredPath} message=${recoveredMessage}`);
  }
  console.warn(`[openPath] failed path=${targetPath} message=${message}`);
  return false;
});

// --- File watcher for document edit detection ---
const activeFileWatchers = new Map<string, { watcher: fs.FSWatcher; debounceTimer: ReturnType<typeof setTimeout> | null }>();

ipcMain.handle('yiyu-workbench:watchFile', async (_event, targetPath: string) => {
  if (activeFileWatchers.has(targetPath)) return true;
  try {
    const resolvedPath = path.resolve(targetPath);
    const stat = await fs.promises.stat(resolvedPath).catch(() => null);
    if (!stat?.isFile()) return false;
    const initialMtime = stat.mtimeMs;
    const watcher = fs.watch(resolvedPath, () => {
      const entry = activeFileWatchers.get(targetPath);
      if (!entry) return;
      if (entry.debounceTimer) clearTimeout(entry.debounceTimer);
      entry.debounceTimer = setTimeout(async () => {
        const currentStat = await fs.promises.stat(resolvedPath).catch(() => null);
        if (currentStat && currentStat.mtimeMs !== initialMtime) {
          const win = BrowserWindow.getAllWindows()[0];
          if (win) {
            win.webContents.send('yiyu-workbench:fileChanged', targetPath);
          }
        }
      }, 1500);
    });
    activeFileWatchers.set(targetPath, { watcher, debounceTimer: null });
    return true;
  } catch {
    return false;
  }
});

ipcMain.handle('yiyu-workbench:unwatchFile', async (_event, targetPath: string) => {
  const entry = activeFileWatchers.get(targetPath);
  if (entry) {
    if (entry.debounceTimer) clearTimeout(entry.debounceTimer);
    entry.watcher.close();
    activeFileWatchers.delete(targetPath);
  }
  return true;
});

ipcMain.handle('yiyu-workbench:openExternalUrl', async (_event, targetUrl: string) => {
  // P0-1 修复: shell.openExternal 旧版无 scheme 校验, 渲染层注入即可触发
  // file:// (打开任意本地文件) / javascript: / smb:// 等危险 scheme.
  // 白名单只允许 http(s):// 和 mailto:.
  if (typeof targetUrl !== 'string' || targetUrl.length === 0) {
    throw new Error('openExternalUrl: 缺少 url');
  }
  let parsed: URL;
  try {
    parsed = new URL(targetUrl);
  } catch {
    throw new Error('openExternalUrl: 无效 URL');
  }
  const allowedSchemes = ['http:', 'https:', 'mailto:'];
  if (!allowedSchemes.includes(parsed.protocol)) {
    appendElectronLaunchLog(
      'ERROR',
      `[openExternalUrl] 拒绝非白名单 scheme=${parsed.protocol} url=${targetUrl.slice(0, 200)}`,
    );
    throw new Error(`openExternalUrl: 拒绝打开 ${parsed.protocol} 类型链接,仅允许 http / https / mailto`);
  }
  await shell.openExternal(targetUrl);
  return true;
});

ipcMain.handle('yiyu-workbench:revealInFinder', async (_event, targetPath: string) => {
  shell.showItemInFolder(targetPath);
  return true;
});

ipcMain.handle('yiyu-workbench:saveFileAs', async (_event, sourcePath: string, suggestedName?: string) => {
  const resolvedSourcePath = path.resolve(sourcePath);
  const sourceStat = await fs.promises.stat(resolvedSourcePath).catch(() => null);
  if (!sourceStat?.isFile()) return null;

  const { canceled, filePath } = await dialog.showSaveDialog({
    title: '另存为',
    defaultPath: path.join(app.getPath('documents'), suggestedName || path.basename(resolvedSourcePath)),
    buttonLabel: '保存',
  });
  if (canceled || !filePath) return null;

  await fs.promises.copyFile(resolvedSourcePath, filePath);
  return filePath;
});

const SAFE_RECORDING_EXTENSIONS = new Set(['webm', 'wav', 'mp3', 'm4a', 'mp4', 'ogg', 'opus', 'flac']);

ipcMain.handle(
  'yiyu-workbench:readRecordingFile',
  async (_event, absolutePath: string): Promise<{ buffer: Uint8Array; sizeBytes: number; name: string }> => {
    if (!absolutePath || typeof absolutePath !== 'string') {
      throw new Error('readRecordingFile: missing path');
    }
    const recordingsRoot = path.join(app.getPath('userData'), 'recordings');
    const normalized = path.resolve(absolutePath);
    if (!normalized.startsWith(recordingsRoot + path.sep) && normalized !== recordingsRoot) {
      throw new Error('readRecordingFile: path outside recordings directory');
    }
    const stat = await fs.promises.stat(normalized);
    if (!stat.isFile()) {
      throw new Error('readRecordingFile: not a file');
    }
    const data = await fs.promises.readFile(normalized);
    return {
      buffer: new Uint8Array(data.buffer, data.byteOffset, data.byteLength),
      sizeBytes: stat.size,
      name: path.basename(normalized),
    };
  },
);

ipcMain.handle(
  'yiyu-workbench:saveRecordingBlob',
  async (
    _event,
    payload: { buffer: ArrayBuffer | Uint8Array; extension?: string; sessionId?: string },
  ): Promise<{ absolutePath: string; sizeBytes: number; sessionId: string }> => {
    if (!payload || (!payload.buffer && (payload.buffer as unknown) !== 0)) {
      throw new Error('saveRecordingBlob: missing buffer');
    }
    const extRaw = (payload.extension || 'webm').trim().toLowerCase().replace(/^\./, '');
    const ext = SAFE_RECORDING_EXTENSIONS.has(extRaw) ? extRaw : 'webm';
    const sessionId = (payload.sessionId || crypto.randomUUID()).trim() || crypto.randomUUID();
    const recordingsRoot = path.join(app.getPath('userData'), 'recordings');
    await fs.promises.mkdir(recordingsRoot, { recursive: true });
    const targetPath = path.join(recordingsRoot, `${sessionId}.${ext}`);
    const data = payload.buffer instanceof Uint8Array
      ? Buffer.from(payload.buffer)
      : Buffer.from(new Uint8Array(payload.buffer));
    await fs.promises.writeFile(targetPath, data);
    const stat = await fs.promises.stat(targetPath);
    return { absolutePath: targetPath, sizeBytes: stat.size, sessionId };
  },
);
