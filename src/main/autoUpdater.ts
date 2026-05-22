import { app, BrowserWindow, ipcMain } from 'electron';
import electronUpdaterPkg from 'electron-updater';

const { autoUpdater } = electronUpdaterPkg;

type UpdateEventKind =
  | 'checking'
  | 'available'
  | 'not-available'
  | 'download-progress'
  | 'downloaded'
  | 'error';

interface UpdateEventPayload {
  kind: UpdateEventKind;
  version?: string;
  releaseNotes?: string | null;
  percent?: number;
  bytesPerSecond?: number;
  transferred?: number;
  total?: number;
  message?: string;
}

const UPDATE_EVENT_CHANNEL = 'yiyu-workbench:update-event';
const CHECK_DELAY_MS = 10_000;
const RECHECK_INTERVAL_MS = 6 * 60 * 60 * 1000;
const UPDATE_FEED_URL = 'https://yiyu-thinktank-releases.tos-cn-beijing.volces.com/desktop/mac/latest-mac.yml';

let mainWindowRef: BrowserWindow | null = null;
let setupDone = false;
let recheckTimer: NodeJS.Timeout | null = null;

function broadcast(payload: UpdateEventPayload): void {
  if (!mainWindowRef || mainWindowRef.isDestroyed()) return;
  try {
    mainWindowRef.webContents.send(UPDATE_EVENT_CHANNEL, payload);
  } catch (err) {
    console.warn('[autoUpdater] broadcast failed:', err);
  }
}

function shouldEnable(): boolean {
  if (!app.isPackaged) {
    console.log('[autoUpdater] skipped: not packaged (dev mode)');
    return false;
  }
  if (process.platform !== 'darwin') {
    console.log('[autoUpdater] skipped: only enabled on macOS for now');
    return false;
  }
  return true;
}

function normalizeUpdateErrorMessage(message: string): string {
  const lower = message.toLowerCase();
  if (message.includes('latest-mac.yml') && (message.includes('404') || lower.includes('not found'))) {
    return `当前更新源尚未发布可用版本或暂不可访问。请确认 ${UPDATE_FEED_URL} 已发布。`;
  }
  if (lower.includes('net::err_internet_disconnected') || lower.includes('enotfound') || lower.includes('econnreset') || lower.includes('timeout')) {
    return '当前网络无法连接更新源，请稍后重试。';
  }
  if (lower.includes('sha512') || lower.includes('signature') || lower.includes('code signature')) {
    return '更新包签名或校验未通过，已停止安装，请联系发布负责人重新发布。';
  }
  return message;
}

export function setupAutoUpdater(mainWindow: BrowserWindow): void {
  mainWindowRef = mainWindow;

  if (setupDone) return;
  setupDone = true;

  if (!shouldEnable()) return;

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.allowDowngrade = false;
  autoUpdater.logger = {
    info: (msg: unknown) => console.log('[autoUpdater]', msg),
    warn: (msg: unknown) => console.warn('[autoUpdater]', msg),
    error: (msg: unknown) => console.error('[autoUpdater]', msg),
    debug: () => undefined,
  } as never;

  autoUpdater.on('checking-for-update', () => {
    broadcast({ kind: 'checking' });
  });

  autoUpdater.on('update-available', (info) => {
    broadcast({
      kind: 'available',
      version: info?.version,
      releaseNotes: typeof info?.releaseNotes === 'string' ? info.releaseNotes : null,
    });
  });

  autoUpdater.on('update-not-available', (info) => {
    broadcast({ kind: 'not-available', version: info?.version });
  });

  autoUpdater.on('download-progress', (progress) => {
    broadcast({
      kind: 'download-progress',
      percent: progress?.percent,
      bytesPerSecond: progress?.bytesPerSecond,
      transferred: progress?.transferred,
      total: progress?.total,
    });
  });

  autoUpdater.on('update-downloaded', (info) => {
    broadcast({ kind: 'downloaded', version: info?.version });
  });

  autoUpdater.on('error', (err) => {
    const message = normalizeUpdateErrorMessage(err?.message ?? String(err ?? 'unknown updater error'));
    broadcast({
      kind: 'error',
      message,
    });
  });

  ipcMain.handle('yiyu-workbench:update.check', async () => {
    if (!shouldEnable()) {
      return { ok: false, reason: 'updater disabled in this environment' };
    }
    try {
      const result = await autoUpdater.checkForUpdates();
      return { ok: true, version: result?.updateInfo?.version ?? null };
    } catch (err) {
      const message = normalizeUpdateErrorMessage(err instanceof Error ? err.message : String(err));
      console.error('[autoUpdater] checkForUpdates failed:', message);
      return { ok: false, reason: message };
    }
  });

  ipcMain.handle('yiyu-workbench:update.quitAndInstall', async () => {
    try {
      autoUpdater.quitAndInstall(false, true);
      return { ok: true };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return { ok: false, reason: message };
    }
  });

  setTimeout(() => {
    autoUpdater.checkForUpdates().catch((err) => {
      console.warn('[autoUpdater] initial checkForUpdates failed:', err);
    });
  }, CHECK_DELAY_MS);

  recheckTimer = setInterval(() => {
    autoUpdater.checkForUpdates().catch((err) => {
      console.warn('[autoUpdater] periodic checkForUpdates failed:', err);
    });
  }, RECHECK_INTERVAL_MS);

  app.on('before-quit', () => {
    if (recheckTimer) {
      clearInterval(recheckTimer);
      recheckTimer = null;
    }
  });
}
