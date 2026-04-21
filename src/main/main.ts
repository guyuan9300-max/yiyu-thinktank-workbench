import { writeFileSync, appendFileSync, mkdirSync } from 'node:fs';
try { appendFileSync('/tmp/yiyu-thinktank-electron-bootstrap.log', `[${new Date().toISOString()}] [PROBE] main.ts top-of-file reached\n`); } catch {}
import { app, BrowserWindow, dialog, ipcMain, protocol, shell } from 'electron';
try { appendFileSync('/tmp/yiyu-thinktank-electron-bootstrap.log', `[${new Date().toISOString()}] [PROBE] electron imported OK\n`); } catch {}
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import http from 'node:http';
import net from 'node:net';
import type {
  CommitAndPushToMainPayload,
  PullSelectedFromMainPayload,
} from '../shared/types.js';
import {
  commitAndPushToMain,
  findSuggestedCollabRepoPath,
  getCollabRepoStatus,
  previewPullFromMain,
  previewPushToMain,
  pullSelectedFromMain,
} from './collabGit.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_BACKEND_PORT = 47829;
const DEFAULT_CLOUD_BACKEND_PORT = 47830;
const projectRoot = path.resolve(__dirname, '../..');
const isDev = !app.isPackaged && Boolean(process.env.VITE_DEV_SERVER_URL);
const REQUIRED_BACKEND_FEATURES = ['knowledge.vectorize-answer', 'knowledge.reclass-events', 'chat.general-answer', 'chat.async-status'];
const APP_DISPLAY_NAME = '益语智库自用平台';
const APP_BUNDLE_ID = 'com.yiyu.selfworkbench';
const WORKBENCH_DATA_DIR_NAME = 'YiyuThinkTankWorkbench';
const releasePlanPath = path.join(projectRoot, 'docs', 'mac-release-update-plan.md');
const releaseArtifactsPath = path.join(projectRoot, 'dist');
const fixedUserDataPath = path.join(app.getPath('appData'), WORKBENCH_DATA_DIR_NAME);
const runtimeLogsDir = path.join(fixedUserDataPath, 'runtime', 'logs');
const runtimeUiDir = path.join(fixedUserDataPath, 'runtime', 'ui');
const electronLaunchLogPath = path.join(runtimeLogsDir, 'electron-launch.log');
const collabRebuildLogPath = path.join(runtimeLogsDir, 'collab-rebuild.log');
const runtimeManifestPath = path.join(runtimeLogsDir, 'runtime-manifest.json');
const emergencyBootstrapLogPath = '/tmp/yiyu-thinktank-electron-bootstrap.log';
const savedApplicationStatePath = path.join(app.getPath('home'), 'Library', 'Saved Application State', `${APP_BUNDLE_ID}.savedState`);
app.setName(APP_DISPLAY_NAME);
app.setPath('userData', fixedUserDataPath);
app.setAboutPanelOptions({
  applicationName: APP_DISPLAY_NAME,
  applicationVersion: app.getVersion(),
  version: app.getVersion(),
});

type RuntimeSyncMetadata = {
  fingerprint: string;
  syncedAt: string;
  project: 'backend' | 'cloud_backend';
};

type RuntimeLaunchManifest = {
  writtenAt: string;
  appVersion: string;
  isPackaged: boolean;
  pid: number;
  executablePath: string;
  appPath: string;
  userDataPath: string;
  appDbPath: string;
  runtimeLogsDir: string;
  backendUrl: string;
  cloudBackendUrl: string;
  remoteCloudBackendUrl: string | null;
  usingRemoteCloudBackend: boolean;
  backendPort: number;
  cloudBackendPort: number;
  rendererPort: number;
  backendRuntimeVenv?: string;
  cloudBackendRuntimeVenv?: string;
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
const LOCAL_DEV_CLOUD_SEED_ENV = {
  YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD: process.env.YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD || 'Admin123!',
  YIYU_CLOUD_GUYUAN_PASSWORD: process.env.YIYU_CLOUD_GUYUAN_PASSWORD || 'Guyuan31',
  YIYU_CLOUD_QINGHUA_PASSWORD: process.env.YIYU_CLOUD_QINGHUA_PASSWORD || 'Qinghua123!',
  YIYU_CLOUD_JIANING_PASSWORD: process.env.YIYU_CLOUD_JIANING_PASSWORD || 'Jianing123!',
  YIYU_CLOUD_YISHUO_PASSWORD: process.env.YIYU_CLOUD_YISHUO_PASSWORD || 'Yishuo123!',
} satisfies NodeJS.ProcessEnv;
const platformDnaExtractorScriptPath = path.join(projectRoot, 'backend', 'scripts', 'extract_platform_dna_text.py');
const legacyAppBasenames = new Set(['益语智库.app', '益语智库工作台.app']);
const DEFAULT_PACKAGED_REMOTE_CLOUD_API_URL = 'http://101.126.34.232';
const DEPRECATED_PACKAGED_REMOTE_CLOUD_API_URLS = new Set(['https://api.yiyu.love', 'http://api.yiyu.love']);

function normalizeHttpUrl(rawUrl?: string | null) {
  const trimmed = rawUrl?.trim();
  if (!trimmed) return null;
  return trimmed.replace(/\/+$/, '');
}

function remoteCloudBackendUrl() {
  const explicitUrl = (
    normalizeHttpUrl(process.env.YIYU_REMOTE_CLOUD_API_URL)
    || normalizeHttpUrl(process.env.YIYU_PACKAGED_REMOTE_CLOUD_API_URL)
  );
  if (!app.isPackaged) {
    return explicitUrl;
  }
  if (explicitUrl && !DEPRECATED_PACKAGED_REMOTE_CLOUD_API_URLS.has(explicitUrl)) {
    return explicitUrl;
  }
  return DEFAULT_PACKAGED_REMOTE_CLOUD_API_URL;
}

function shouldUseRemoteCloudBackend() {
  return Boolean(remoteCloudBackendUrl());
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

function logElectronInfo(message: string) {
  console.log(message);
  appendElectronLaunchLog('INFO', message);
}

function logElectronError(message: string) {
  console.error(message);
  appendElectronLaunchLog('ERROR', message);
}

function writeRuntimeLaunchManifest(extra: Partial<RuntimeLaunchManifest> = {}) {
  try {
    fs.mkdirSync(runtimeLogsDir, { recursive: true });
    const manifest: RuntimeLaunchManifest = {
      writtenAt: new Date().toISOString(),
      appVersion: app.getVersion(),
      isPackaged: app.isPackaged,
      pid: process.pid,
      executablePath: app.getPath('exe'),
      appPath: app.getAppPath(),
      userDataPath: fixedUserDataPath,
      appDbPath: path.join(fixedUserDataPath, 'app.db'),
      runtimeLogsDir,
      backendUrl: backendUrl(),
      cloudBackendUrl: cloudBackendUrl(),
      remoteCloudBackendUrl: remoteCloudBackendUrl(),
      usingRemoteCloudBackend: shouldUseRemoteCloudBackend(),
      backendPort,
      cloudBackendPort,
      rendererPort,
      ...extra,
    };
    fs.writeFileSync(runtimeManifestPath, JSON.stringify(manifest, null, 2), 'utf8');
  } catch {
    // Diagnostics should never block app startup.
  }
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
    visibleWorkspaceRepo,
    hiddenWorkspaceRepo,
    path.join(path.dirname(projectRoot), 'yiyu-thinktank-workbench'),
    path.join(app.getPath('documents'), 'yiyu-thinktank-workbench'),
    path.join(app.getPath('desktop'), 'yiyu-thinktank-workbench'),
  ];
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
          summarize('清单列表'),
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
    const before = await inspectTargets() as {
      heading: string;
      bodyIncludesToday: boolean;
      navTaskButton: { found: boolean; centerX?: number; centerY?: number; text?: string };
      targets: Array<{ label: string; found: boolean; centerX?: number; centerY?: number; pointerEvents?: string }>;
    };
    console.log(`[renderer:task-diagnostics] before=${JSON.stringify(before)}`);

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
    console.log(`[renderer:task-diagnostics] onTasksPage=${JSON.stringify(onTasksPage)}`);

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
    console.log(`[renderer:task-diagnostics] afterCalendar=${JSON.stringify(afterCalendar)}`);

    const listTargetPayload = await inspectTargets() as {
      targets: Array<{ label: string; found: boolean; centerX?: number; centerY?: number }>;
    };
    const listTarget = listTargetPayload.targets.find((item) => item.label === '清单列表' && item.found && item.centerX !== undefined && item.centerY !== undefined);
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
    console.log(`[renderer:task-diagnostics] afterCreate=${JSON.stringify(afterCreate)}`);
  } catch (error) {
    console.error(`[renderer:task-diagnostics] failed=${error instanceof Error ? error.message : String(error)}`);
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
    logElectronInfo(`[renderer:event-line-diagnostics] list-mode=${JSON.stringify(await clickText('button', '清单列表'))}`);
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
  const pathEntries = new Set<string>((env.PATH ?? '').split(path.delimiter).filter(Boolean));
  if (uvBinaryPath) {
    pathEntries.add(path.dirname(uvBinaryPath));
  }
  if (env.VIRTUAL_ENV) {
    pathEntries.add(path.join(env.VIRTUAL_ENV, 'bin'));
  }
  env.PATH = Array.from(pathEntries).join(path.delimiter);
  env.YIYU_CLOUD_API_URL = cloudBackendUrl();
  env.YIYU_WORKBENCH_DATA_DIR = fixedUserDataPath;
  env.PYTHONDONTWRITEBYTECODE = '1';
  env.PYTHONPYCACHEPREFIX = path.join(fixedUserDataPath, 'runtime', 'pycache');
  return env;
}

function runtimePythonPath(venvPath: string) {
  return path.join(venvPath, 'bin', 'python');
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
  if (backendRuntimeVenv && isExecutable(path.join(backendRuntimeVenv, 'bin', 'python'))) {
    return path.join(backendRuntimeVenv, 'bin', 'python');
  }
  const fallback = path.join(projectRoot, 'backend', '.venv', 'bin', 'python');
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

async function ensureProjectRuntime(projectDirName: 'backend' | 'cloud_backend', venvPath: string) {
  if (!uvBinaryPath) {
    throw new Error('missing_uv_binary');
  }
  fs.mkdirSync(path.dirname(venvPath), { recursive: true });
  const pythonPath = path.join(venvPath, 'bin', 'python');
  const uvicornPath = path.join(venvPath, 'bin', 'uvicorn');
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
  writeRuntimeSyncMetadata(metadataPath, {
    fingerprint,
    syncedAt: new Date().toISOString(),
    project: projectDirName,
  });
}

function backendUrl() {
  return `http://127.0.0.1:${backendPort}`;
}

function cloudBackendUrl() {
  return remoteCloudBackendUrl() || `http://127.0.0.1:${cloudBackendPort}`;
}

function rendererUrl() {
  return `http://127.0.0.1:${rendererPort}`;
}

function rendererProtocolUrl() {
  return 'app://renderer/index.html';
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
          const payload = JSON.parse(Buffer.concat(chunks).toString('utf-8')) as { featureFlags?: string[] };
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
    process.stdout.write(`[backend:${label}] ${text}`);
    if (!onLine) return;
    for (const line of text.split(/\r?\n/)) {
      onLine(line);
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
    console.error(`后端服务启动失败: ${error.message}`);
  });

  backendProcess.on('exit', (code) => {
    backendExitDetail = `后端服务已退出，退出码=${code ?? 'unknown'}`;
    backendProcess = null;
    ownsBackendProcess = false;
    console.error(`后端服务已退出，退出码=${code ?? 'unknown'}`);
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
        ...LOCAL_DEV_CLOUD_SEED_ENV,
      }),
    },
  );
  ownsCloudBackendProcess = true;

  logBackend(cloudBackendProcess.stdout, 'cloud:stdout');
  logBackend(cloudBackendProcess.stderr, 'cloud:stderr');
  cloudBackendProcess.on('error', (error) => {
    console.error(`中心后端启动失败: ${error.message}`);
  });

  cloudBackendProcess.on('exit', (code) => {
    cloudBackendProcess = null;
    ownsCloudBackendProcess = false;
    console.error(`中心后端已退出，退出码=${code ?? 'unknown'}`);
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
  const message = detail.replace(/[&<>"]/g, (char) => {
    switch (char) {
      case '&':
        return '&amp;';
      case '<':
        return '&lt;';
      case '>':
        return '&gt;';
      case '"':
        return '&quot;';
      default:
        return char;
    }
  });
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
  const message = detail
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/\n/g, '<br />');

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

async function waitForBackend(timeoutMs = 45000): Promise<void> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (backendExitDetail) {
      throw new Error(buildBackendStartupError(backendExitDetail));
    }
    try {
      await new Promise<void>((resolve, reject) => {
        const req = http.get(`${backendUrl()}/api/v1/system/health`, (res) => {
          if ((res.statusCode ?? 500) >= 500) {
            reject(new Error(`status=${res.statusCode}`));
            return;
          }
          const chunks: Buffer[] = [];
          res.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
          res.on('end', () => {
            try {
              const payload = JSON.parse(Buffer.concat(chunks).toString('utf-8')) as { featureFlags?: string[] };
              const featureFlags = Array.isArray(payload.featureFlags) ? payload.featureFlags : [];
              const missing = REQUIRED_BACKEND_FEATURES.filter((feature) => !featureFlags.includes(feature));
              if (missing.length > 0) {
                reject(new Error(`backend_missing_features:${missing.join(',')}`));
                return;
              }
              resolve();
            } catch (error) {
              reject(error);
            }
          });
        });
        req.on('error', reject);
      });
      return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 400));
    }
  }
  throw new Error(buildBackendStartupError(`后端服务启动超时（>${Math.round(timeoutMs / 1000)} 秒）`));
}

async function waitForCloudBackend(timeoutMs = 20000): Promise<void> {
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

async function createMainWindow() {
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

  await mainWindow.loadURL(rendererBootstrapPageUrl());
  if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.isVisible()) {
    logElectronInfo('[window] showing startup bootstrap page');
    mainWindow.show();
    mainWindow.focus();
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
  }
}

const gotSingleInstanceLock = app.requestSingleInstanceLock();
appendElectronLaunchLog('INFO', `[app] singleInstanceLock=${gotSingleInstanceLock}`);

if (!gotSingleInstanceLock) {
  appendElectronLaunchLog('ERROR', '[app] failed to acquire single-instance lock, quitting');
  app.quit();
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
  void createMainWindow();
});

app.whenReady().then(async () => {
  appendElectronLaunchLog('INFO', '[app] whenReady entered');
  const reservedPorts = new Set<number>();
  const reuseExistingBackend = await checkBackendHealthAt(DEFAULT_BACKEND_PORT, REQUIRED_BACKEND_FEATURES);
  backendPort = reuseExistingBackend ? DEFAULT_BACKEND_PORT : await reservePort(DEFAULT_BACKEND_PORT, reservedPorts);
  reservedPorts.add(backendPort);
  const usingRemoteCloudBackend = shouldUseRemoteCloudBackend();
  const configuredRemoteCloudBackendUrl = remoteCloudBackendUrl();
  let reuseExistingCloudBackend = false;
  if (usingRemoteCloudBackend) {
    logElectronInfo(`[cloud] using remote collaboration backend ${configuredRemoteCloudBackendUrl}`);
  } else {
    reuseExistingCloudBackend = await checkCloudBackendHealthAt(DEFAULT_CLOUD_BACKEND_PORT);
    cloudBackendPort = reuseExistingCloudBackend ? DEFAULT_CLOUD_BACKEND_PORT : await reservePort(DEFAULT_CLOUD_BACKEND_PORT, reservedPorts);
    reservedPorts.add(cloudBackendPort);
  }
  process.env.YIYU_BACKEND_URL = backendUrl();
  process.env.YIYU_CLOUD_API_URL = cloudBackendUrl();
  uvBinaryPath = resolveUvBinary();
  if (!uvBinaryPath) {
    dialog.showErrorBox(
      '缺少 uv 运行时',
      '启动桌面应用前需要先安装 uv。请先执行 `curl -LsSf https://astral.sh/uv/install.sh | sh`，然后重新打开应用。',
    );
    app.quit();
    return;
  }
  const runtimeRoot = path.join(app.getPath('userData'), 'runtime');
  backendRuntimeVenv = path.join(runtimeRoot, 'backend-venv');
  cloudBackendRuntimeVenv = path.join(runtimeRoot, 'cloud-backend-venv');
  writeRuntimeLaunchManifest({
    backendRuntimeVenv,
    cloudBackendRuntimeVenv,
  });
  try {
    await ensureProjectRuntime('backend', backendRuntimeVenv);
    if (!usingRemoteCloudBackend) {
      await ensureProjectRuntime('cloud_backend', cloudBackendRuntimeVenv);
    }
    await registerRendererProtocol();
    await recyclePackagedRuntimeProcesses();
    purgeSavedApplicationState();
  } catch (error) {
    dialog.showErrorBox('后端运行时准备失败', error instanceof Error ? error.message : String(error));
    app.quit();
    return;
  }
  if (!usingRemoteCloudBackend && !reuseExistingCloudBackend) {
    startCloudBackend();
  }
  if (!reuseExistingBackend) {
    startBackend();
  }
  try {
    await waitForBackend();
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
        await waitForBackend(30000);
      } catch (secondError) {
        dialog.showErrorBox('本地后端启动失败', secondError instanceof Error ? secondError.message : String(secondError));
        app.quit();
        return;
      }
    } else {
      dialog.showErrorBox('本地后端启动失败', firstError instanceof Error ? firstError.message : String(firstError));
      app.quit();
      return;
    }
  }
  appendElectronLaunchLog('INFO', '[app] creating main window');
  try {
    await createMainWindow();
  } catch (error) {
    dialog.showErrorBox('桌面界面启动失败', error instanceof Error ? error.message : String(error));
    app.quit();
    return;
  }
  appendElectronLaunchLog('INFO', '[app] main window created successfully');
  void waitForCloudBackend().catch((error) => {
    console.error(error);
  });
  appendElectronLaunchLog('INFO', '[app] startup sequence complete, app should stay alive');

  // Periodic backend health watchdog — restart if crashed silently
  setInterval(async () => {
    if (!ownsBackendProcess) return;
    if (backendProcess) return; // still running
    // Backend was ours but process handle is gone — it crashed
    appendElectronLaunchLog('ERROR', '[backend:watchdog] backend process gone, attempting restart');
    try {
      startBackend();
      await waitForBackend(20000);
      appendElectronLaunchLog('INFO', '[backend:watchdog] backend restarted successfully');
    } catch {
      appendElectronLaunchLog('ERROR', '[backend:watchdog] backend restart failed');
    }
  }, 15000); // Check every 15 seconds

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
        await createMainWindow();
      } catch (error) {
        dialog.showErrorBox('桌面界面启动失败', error instanceof Error ? error.message : String(error));
      }
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });
});

app.on('before-quit', (event) => {
  appendElectronLaunchLog('INFO', `[app] before-quit fired`);
  stopBackend();
  stopCloudBackend();
});
app.on('will-quit', () => {
  appendElectronLaunchLog('INFO', '[app] will-quit fired');
});
app.on('window-all-closed', () => {
  appendElectronLaunchLog('INFO', '[app] window-all-closed fired');
  if (process.platform !== 'darwin') {
    app.quit();
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
  const executablePath = process.execPath;
  const appBundlePath = resolveBundlePath(executablePath);
  const recommendedInstallPath = path.join(app.getPath('home'), 'Applications', `${APP_DISPLAY_NAME}.app`);
  const detectedAppPaths = await collectInstalledAppPaths(appBundlePath);
  const legacyAppPaths: string[] = [];
  const duplicateAppPaths: string[] = [];

  for (const targetPath of detectedAppPaths) {
    if (targetPath === appBundlePath) continue;
    const baseName = path.basename(targetPath);
    const bundleId = await readBundleId(targetPath);
    if (legacyAppBasenames.has(baseName) || (bundleId && bundleId !== APP_BUNDLE_ID)) {
      legacyAppPaths.push(targetPath);
    } else {
      duplicateAppPaths.push(targetPath);
    }
  }

  let installWarning: string | null = null;
  if (legacyAppPaths.length > 0) {
    installWarning = `检测到 ${legacyAppPaths.length} 个旧入口，容易误开历史包。`;
  } else if (duplicateAppPaths.length > 0) {
    installWarning = `检测到 ${duplicateAppPaths.length} 个重复安装包，请保留单一入口。`;
  } else if (app.isPackaged && appBundlePath !== recommendedInstallPath) {
    installWarning = '当前运行包不在建议安装位置，后续升级时容易装错包。';
  }

  return {
    appVersion: app.getVersion(),
    isPackaged: app.isPackaged,
    platform: process.platform,
    arch: process.arch,
    appBundlePath,
    executablePath,
    releasePlanPath,
    releaseArtifactsPath,
    updateChannel: 'stable',
    updaterPhase: 'planning',
    recommendedInstallPath,
    installStatus: installWarning ? 'warning' : 'ok',
    installWarning,
    detectedAppPaths,
    legacyAppPaths,
  };
});

ipcMain.handle('yiyu-workbench:selectFolder', async () => {
  const result = await dialog.showOpenDialog({
    title: '选择客户资料目录',
    properties: ['openDirectory'],
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('yiyu-workbench:selectCollabRepo', async () => {
  const result = await dialog.showOpenDialog({
    title: '选择源码仓库目录',
    properties: ['openDirectory'],
  });
  if (result.canceled || !result.filePaths[0]) return null;
  const repoPath = await findSuggestedCollabRepoPath([result.filePaths[0]]);
  if (!repoPath) {
    throw new Error('你选中的目录不是 Git 源码仓库，请重新选择。');
  }
  return repoPath;
});

ipcMain.handle('yiyu-workbench:getCollabRepoStatus', async (_event, repoPath?: string | null) => {
  return getCollabRepoStatus({
    repoPath,
    suggestedCandidates: getCollabSuggestedCandidates(),
    appDbPath: path.join(app.getPath('userData'), 'app.db'),
  });
});

ipcMain.handle('yiyu-workbench:previewPushToMain', async (_event, repoPath: string) => {
  return previewPushToMain({
    repoPath,
    suggestedCandidates: getCollabSuggestedCandidates(),
    appDbPath: path.join(app.getPath('userData'), 'app.db'),
  });
});

ipcMain.handle('yiyu-workbench:commitAndPushToMain', async (_event, payload: CommitAndPushToMainPayload) => {
  return commitAndPushToMain(payload, getCollabSuggestedCandidates(), path.join(app.getPath('userData'), 'app.db'));
});

ipcMain.handle('yiyu-workbench:previewPullFromMain', async (_event, repoPath: string) => {
  return previewPullFromMain({
    repoPath,
    suggestedCandidates: getCollabSuggestedCandidates(),
    appDbPath: path.join(app.getPath('userData'), 'app.db'),
  });
});

ipcMain.handle('yiyu-workbench:pullSelectedFromMain', async (_event, payload: PullSelectedFromMainPayload) => {
  return pullSelectedFromMain(payload, getCollabSuggestedCandidates(), path.join(app.getPath('userData'), 'app.db'));
});

ipcMain.handle('yiyu-workbench:rebuildAndInstallFromRepo', async (_event, repoPath: string) => {
  const normalizedRepoPath = path.resolve(repoPath);
  const rebuildCommand = [
    `cd ${JSON.stringify(normalizedRepoPath)}`,
    `mkdir -p ${JSON.stringify(runtimeLogsDir)}`,
    `npm run dist:mac-local >> ${JSON.stringify(collabRebuildLogPath)} 2>&1`,
    `npm run install:mac-local >> ${JSON.stringify(collabRebuildLogPath)} 2>&1`,
    `node scripts/open-installed-app.mjs >> ${JSON.stringify(collabRebuildLogPath)} 2>&1`,
  ].join(' && ');
  fs.mkdirSync(runtimeLogsDir, { recursive: true });
  fs.appendFileSync(collabRebuildLogPath, `\n[${new Date().toISOString()}] start rebuild from ${normalizedRepoPath}\n`, 'utf8');
  const child = spawn('zsh', ['-lc', rebuildCommand], {
    cwd: normalizedRepoPath,
    detached: true,
    stdio: 'ignore',
  });
  child.unref();
  setTimeout(() => {
    app.quit();
  }, 300);
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

ipcMain.handle('yiyu-workbench:openPath', async (_event, targetPath: string) => {
  const message = await shell.openPath(targetPath);
  return message === '';
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
