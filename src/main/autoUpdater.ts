import { app, BrowserWindow, ipcMain, shell } from 'electron';
import crypto from 'node:crypto';
import { once } from 'node:events';
import fs from 'node:fs';
import path from 'node:path';
import electronUpdaterPkg from 'electron-updater';
import type { OfficialPushUpdatePayload } from '../shared/types.js';

const { autoUpdater } = electronUpdaterPkg;

type UpdateEventKind =
  | 'checking'
  | 'available'
  | 'not-available'
  | 'download-progress'
  | 'downloaded'
  | 'error'
  | 'official-push-available'
  | 'official-push-not-available';

interface UpdateEventPayload {
  kind: UpdateEventKind;
  version?: string;
  releaseNotes?: string | null;
  percent?: number;
  bytesPerSecond?: number;
  transferred?: number;
  total?: number;
  message?: string;
  officialPush?: OfficialPushUpdatePayload | null;
}

interface CentralReleaseUpdatePayload {
  version?: string | null;
  releaseVersion?: string | null;
  platform?: string | null;
  packageKind?: string | null;
  customPackageId?: string | null;
  customPackageName?: string | null;
  fileName?: string | null;
  sizeBytes?: number | null;
  sha512?: string | null;
  downloadUrl?: string | null;
  releaseDate?: string | null;
}

const UPDATE_EVENT_CHANNEL = 'yiyu-workbench:update-event';
const CHECK_DELAY_MS = 10_000;
const RECHECK_INTERVAL_MS = 6 * 60 * 60 * 1000;
const ORG_PUSH_RECHECK_INTERVAL_MS = 30_000;
const UPDATE_FEED_BASE_URL = 'https://yiyu-thinktank-releases.tos-cn-beijing.volces.com/desktop/mac/';
const UPDATE_FEED_URL = `${UPDATE_FEED_BASE_URL}latest-mac.yml`;
const RELEASE_SERVICE_BASE_URL = 'https://www.yiyu.love';

let mainWindowRef: BrowserWindow | null = null;
let setupDone = false;
let recheckTimer: NodeJS.Timeout | null = null;
let officialPushTimer: NodeJS.Timeout | null = null;
// org 感知更新:登录后向官网中央发布服务登记组织身份;未设置时回退静态 TOS。
let currentOrgCode: string | null = null;
let currentFeedBaseUrl: string | null = null;
let currentIdentityKey: string | null = null;
let lastOfficialPush: OfficialPushUpdatePayload | null = null;
let lastOfficialPushSignature: string | null = null;

export interface UpdateOrgIdentity {
  organizationId?: string | null;
  organizationSlug?: string | null;
  organizationName?: string | null;
  cloudBackendUrl?: string | null;
}

function appendUpdaterLog(message: string): void {
  try {
    const logPath = path.join(app.getPath('userData'), 'runtime', 'logs', 'electron-launch.log');
    fs.mkdirSync(path.dirname(logPath), { recursive: true });
    fs.appendFileSync(logPath, `[${new Date().toISOString()}] [INFO] [autoUpdater] ${message}\n`, 'utf8');
  } catch {
    // 诊断日志失败不影响更新主链路。
  }
}

function computeFeedBaseUrl(): string {
  if (currentOrgCode && currentFeedBaseUrl) {
    return currentFeedBaseUrl;
  }
  // 兜底:未登录/无组织码 → 静态 TOS,与原行为一致,不破坏既有静默更新
  return UPDATE_FEED_BASE_URL;
}

function applyFeedUrl(): void {
  try {
    autoUpdater.setFeedURL({ provider: 'generic', url: computeFeedBaseUrl() });
  } catch (err) {
    console.warn('[autoUpdater] setFeedURL failed:', err);
  }
}

function parseSemverish(value: string | null | undefined): [number, number, number] | null {
  const match = String(value || '').trim().match(/^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$/);
  if (!match) return null;
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

function compareSemverish(left: string | null | undefined, right: string | null | undefined): number | null {
  const a = parseSemverish(left);
  const b = parseSemverish(right);
  if (!a || !b) return null;
  for (let index = 0; index < a.length; index += 1) {
    if (a[index] > b[index]) return 1;
    if (a[index] < b[index]) return -1;
  }
  return 0;
}

function buildOfficialPush(update: CentralReleaseUpdatePayload): OfficialPushUpdatePayload | null {
  const currentVersion = app.getVersion();
  const version = String(update.version || update.releaseVersion || '').trim();
  const releaseVersion = String(update.releaseVersion || '').trim() || null;
  if (!version && !releaseVersion) return null;
  const targetVersion = version || releaseVersion || '未知版本';
  const packageKind: OfficialPushUpdatePayload['packageKind'] =
    update.packageKind === 'custom' || update.customPackageId ? 'custom' : 'release';
  const isCustom = packageKind === 'custom';
  const versionDiffers = targetVersion !== currentVersion && releaseVersion !== currentVersion;
  if (!versionDiffers && !isCustom) return null;

  const comparison = compareSemverish(releaseVersion || targetVersion, currentVersion);
  const relation: OfficialPushUpdatePayload['relation'] = isCustom
    ? 'switch-custom'
    : comparison === 1
      ? 'upgrade'
      : comparison === -1
        ? 'downgrade'
        : versionDiffers
          ? 'different'
          : 'unknown';
  const customName = String(update.customPackageName || '').trim();
  const title = isCustom
    ? `收到组织定制版：${customName || targetVersion}`
    : relation === 'downgrade'
      ? `收到官方回退推送：${targetVersion}`
      : `收到益语智库官方推送：${targetVersion}`;

  return {
    title,
    version: targetVersion,
    releaseVersion,
    currentVersion,
    packageKind,
    customPackageId: update.customPackageId || null,
    customPackageName: customName || null,
    fileName: update.fileName || null,
    sizeBytes: typeof update.sizeBytes === 'number' ? update.sizeBytes : null,
    sha512: update.sha512 || null,
    downloadUrl: update.downloadUrl || null,
    organizationCode: currentOrgCode,
    relation,
  };
}

function sanitizeDownloadFileName(value: string | null | undefined, fallbackVersion: string): string {
  const raw = String(value || '').trim();
  const safe = raw
    .replace(/[\\/:\0]/g, '-')
    .replace(/^\.+$/, '')
    .slice(0, 180);
  if (safe) return safe;
  return `yiyu-workbench-${fallbackVersion || 'official-push'}.dmg`;
}

function normalizeSha512(value: string | null | undefined): string | null {
  const raw = String(value || '').trim();
  if (!raw) return null;
  if (/^[a-f0-9]{128}$/i.test(raw)) return Buffer.from(raw, 'hex').toString('base64');
  return raw;
}

async function writeChunk(stream: fs.WriteStream, chunk: Buffer): Promise<void> {
  if (stream.write(chunk)) return;
  await once(stream, 'drain');
}

async function finishWriteStream(stream: fs.WriteStream): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    stream.once('error', reject);
    stream.end(resolve);
  });
}

async function downloadOfficialPushPackage(push: OfficialPushUpdatePayload): Promise<{ targetPath: string; fileName: string }> {
  const downloadUrl = String(push.downloadUrl || '').trim();
  if (!downloadUrl) {
    throw new Error('中央发布服务没有返回安装包下载地址，请先在官网后台重新上传或发布该推送包。');
  }

  const parsedUrl = new URL(downloadUrl);
  const fallbackName = path.basename(parsedUrl.pathname || '') || null;
  const fileName = sanitizeDownloadFileName(push.fileName || fallbackName, push.version);
  const downloadDir = path.join(app.getPath('userData'), 'official-push-downloads');
  fs.mkdirSync(downloadDir, { recursive: true });

  const targetPath = path.join(downloadDir, fileName);
  const tempPath = `${targetPath}.download`;
  if (fs.existsSync(tempPath)) fs.rmSync(tempPath, { force: true });

  appendUpdaterLog(`official-push-download-start version=${push.version} file=${fileName}`);
  const response = await fetch(downloadUrl, { headers: { Accept: 'application/octet-stream' } });
  if (!response.ok) {
    throw new Error(`推送安装包下载失败：${response.status}`);
  }

  const totalHeader = Number(response.headers.get('content-length') || 0);
  const total = Number.isFinite(totalHeader) && totalHeader > 0 ? totalHeader : Number(push.sizeBytes || 0);
  const hash = crypto.createHash('sha512');
  const stream = fs.createWriteStream(tempPath);
  let transferred = 0;
  let lastProgressAt = 0;

  const emitProgress = () => {
    const now = Date.now();
    if (now - lastProgressAt < 350 && transferred < total) return;
    lastProgressAt = now;
    broadcast({
      kind: 'download-progress',
      version: push.version,
      percent: total > 0 ? (transferred / total) * 100 : undefined,
      transferred,
      total: total > 0 ? total : undefined,
    });
  };

  try {
    if (!response.body) {
      const buffer = Buffer.from(await response.arrayBuffer());
      hash.update(buffer);
      transferred = buffer.length;
      await writeChunk(stream, buffer);
      emitProgress();
    } else {
      const reader = response.body.getReader();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        if (!value) continue;
        const buffer = Buffer.from(value);
        hash.update(buffer);
        transferred += buffer.length;
        await writeChunk(stream, buffer);
        emitProgress();
      }
    }
    await finishWriteStream(stream);
  } catch (err) {
    stream.destroy();
    fs.rmSync(tempPath, { force: true });
    throw err;
  }

  const expectedSha512 = normalizeSha512(push.sha512);
  const actualSha512 = hash.digest('base64');
  if (expectedSha512 && expectedSha512 !== actualSha512) {
    fs.rmSync(tempPath, { force: true });
    throw new Error('推送安装包下载完成，但 SHA512 校验未通过，请发布负责人重新上传安装包。');
  }

  fs.renameSync(tempPath, targetPath);
  appendUpdaterLog(`official-push-download-ready version=${push.version} file=${fileName} bytes=${transferred}`);
  broadcast({ kind: 'downloaded', version: push.version });
  return { targetPath, fileName };
}

function officialPushSignature(push: OfficialPushUpdatePayload | null): string | null {
  if (!push) return null;
  return [
    push.organizationCode || '',
    push.packageKind,
    push.customPackageId || '',
    push.version || '',
    push.releaseVersion || '',
    push.fileName || '',
  ].join('|');
}

async function checkOfficialPush(options: { broadcastResult?: boolean } = {}): Promise<OfficialPushUpdatePayload | null> {
  if (!currentOrgCode || !currentFeedBaseUrl) {
    lastOfficialPush = null;
    lastOfficialPushSignature = null;
    if (options.broadcastResult) broadcast({ kind: 'official-push-not-available', officialPush: null });
    return null;
  }
  let timer: NodeJS.Timeout | null = null;
  try {
    const controller = new AbortController();
    timer = setTimeout(() => controller.abort(), 6000);
    const response = await fetch(new URL('latest', currentFeedBaseUrl).toString(), {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`official push check failed: ${response.status}`);
    const payload = await response.json() as CentralReleaseUpdatePayload;
    const officialPush = buildOfficialPush(payload);
    const nextSignature = officialPushSignature(officialPush);
    const previousSignature = lastOfficialPushSignature;
    lastOfficialPush = officialPush;
    lastOfficialPushSignature = nextSignature;
    appendUpdaterLog(officialPush
      ? `official-push-detected org=${currentOrgCode || 'unknown'} version=${officialPush.version} relation=${officialPush.relation} kind=${officialPush.packageKind}`
      : `official-push-empty org=${currentOrgCode || 'unknown'}`);
    if (options.broadcastResult) {
      broadcast(officialPush
        ? { kind: 'official-push-available', version: officialPush.version, officialPush }
        : { kind: 'official-push-not-available', officialPush: null });
    } else if (nextSignature && nextSignature !== previousSignature && officialPush) {
      broadcast({ kind: 'official-push-available', version: officialPush.version, officialPush });
    } else if (!nextSignature && previousSignature) {
      broadcast({ kind: 'official-push-not-available', officialPush: null });
    }
    return officialPush;
  } catch (err) {
    console.warn('[autoUpdater] official push check failed:', err);
    appendUpdaterLog(`official-push-check-failed ${err instanceof Error ? err.message : String(err)}`);
    if (options.broadcastResult) {
      broadcast({ kind: 'error', message: normalizeUpdateErrorMessage(err instanceof Error ? err.message : String(err)) });
    }
    return null;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function stopOfficialPushPolling(): void {
  if (!officialPushTimer) return;
  clearInterval(officialPushTimer);
  officialPushTimer = null;
}

function startOfficialPushPolling(): void {
  if (!setupDone || officialPushTimer || !currentOrgCode || !currentFeedBaseUrl) return;
  officialPushTimer = setInterval(() => {
    void checkOfficialPush({ broadcastResult: false });
  }, ORG_PUSH_RECHECK_INTERVAL_MS);
  officialPushTimer.unref?.();
}

/**
 * 由 renderer 在拿到 /me/org-membership 后调用,把组织身份登记到官网中央发布服务。
 * 切到 org 感知 feed 后立即重检一次,让定向推送即时生效(不必等 6h 周期)。
 */
export async function setUpdateOrgIdentity(identity: UpdateOrgIdentity | null): Promise<void> {
  const nextIdentity = {
    organizationId: (identity?.organizationId || '').trim(),
    organizationSlug: (identity?.organizationSlug || '').trim(),
    organizationName: (identity?.organizationName || '').trim(),
    cloudBackendUrl: (identity?.cloudBackendUrl || '').trim(),
  };
  const nextIdentityKey = JSON.stringify(nextIdentity);
  if (nextIdentityKey === currentIdentityKey && currentOrgCode && currentFeedBaseUrl) return;
  currentIdentityKey = nextIdentityKey;

  const hasOrgIdentity = Boolean(nextIdentity.organizationId || nextIdentity.organizationSlug);
  if (!hasOrgIdentity) {
    currentOrgCode = null;
    currentFeedBaseUrl = null;
    lastOfficialPush = null;
    lastOfficialPushSignature = null;
    autoUpdater.allowDowngrade = false;
    stopOfficialPushPolling();
  } else {
    let timer: NodeJS.Timeout | null = null;
    try {
      const controller = new AbortController();
      timer = setTimeout(() => controller.abort(), 6000);
      const response = await fetch(`${RELEASE_SERVICE_BASE_URL}/api/v1/release-orgs/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(nextIdentity),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`release org resolve failed: ${response.status}`);
      const payload = await response.json() as { canonicalOrgCode?: string; updateFeedBaseUrl?: string };
      currentOrgCode = (payload.canonicalOrgCode || '').trim() || null;
      currentFeedBaseUrl = (payload.updateFeedBaseUrl || '').trim() || (
        currentOrgCode
          ? `${RELEASE_SERVICE_BASE_URL}/api/v1/updates/${encodeURIComponent(currentOrgCode)}/mac/`
          : null
      );
      appendUpdaterLog(currentOrgCode ? `release-org-resolved org=${currentOrgCode}` : 'release-org-resolved empty');
    } catch (err) {
      console.warn('[autoUpdater] central release org resolve failed, fallback to static TOS:', err);
      appendUpdaterLog(`release-org-resolve-failed ${err instanceof Error ? err.message : String(err)}`);
      currentOrgCode = null;
      currentFeedBaseUrl = null;
      lastOfficialPushSignature = null;
      stopOfficialPushPolling();
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  if (!shouldEnable()) return;
  applyFeedUrl();
  console.log('[autoUpdater] feed switched:', currentOrgCode ? `central-org-aware(${currentOrgCode})` : 'static TOS');
  appendUpdaterLog(`feed-switched ${currentOrgCode ? `central-org-aware(${currentOrgCode})` : 'static TOS'}`);
  if (currentOrgCode && currentFeedBaseUrl) {
    startOfficialPushPolling();
    await checkOfficialPush({ broadcastResult: true });
  }
}

export function setUpdateOrgCode(orgCode: string | null, cloudBaseUrl: string | null): Promise<void> {
  return setUpdateOrgIdentity({
    organizationSlug: orgCode,
    cloudBackendUrl: cloudBaseUrl,
  });
}

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
  if (message.includes('app-update.yml') && (lower.includes('enoent') || lower.includes('no such file'))) {
    return `当前安装包缺少更新配置文件，已改为使用益语官方火山云更新源。请稍后重试；若仍失败，请确认 ${UPDATE_FEED_URL} 已发布。`;
  }
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
  applyFeedUrl();
  autoUpdater.logger = {
    info: (msg: unknown) => console.log('[autoUpdater]', msg),
    warn: (msg: unknown) => console.warn('[autoUpdater]', msg),
    error: (msg: unknown) => console.error('[autoUpdater]', msg),
    debug: () => undefined,
  } as never;

  mainWindow.on('focus', () => {
    if (!currentOrgCode || !currentFeedBaseUrl) return;
    void checkOfficialPush({ broadcastResult: false });
  });

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
      if (currentOrgCode && currentFeedBaseUrl) {
        broadcast({ kind: 'checking' });
        const officialPush = await checkOfficialPush({ broadcastResult: true });
        return { ok: true, version: officialPush?.version ?? null, officialPush };
      }
      const result = await autoUpdater.checkForUpdates();
      return { ok: true, version: result?.updateInfo?.version ?? null };
    } catch (err) {
      const message = normalizeUpdateErrorMessage(err instanceof Error ? err.message : String(err));
      console.error('[autoUpdater] checkForUpdates failed:', message);
      return { ok: false, reason: message };
    }
  });

  ipcMain.handle('yiyu-workbench:update.installOfficialPush', async () => {
    if (!shouldEnable()) {
      return { ok: false, reason: 'updater disabled in this environment' };
    }
    if (!currentOrgCode || !currentFeedBaseUrl) {
      return { ok: false, reason: '当前没有组织推送源，请先登录并加入组织。' };
    }
    try {
      const officialPush = await checkOfficialPush({ broadcastResult: true }) || lastOfficialPush;
      if (!officialPush) {
        return { ok: false, reason: '当前没有可安装的官方推送。' };
      }
      broadcast({ kind: 'checking' });
      const downloaded = await downloadOfficialPushPackage(officialPush);
      const openError = await shell.openPath(downloaded.targetPath);
      if (openError) {
        return {
          ok: false,
          version: officialPush.version,
          fileName: downloaded.fileName,
          reason: `安装包已下载，但无法自动打开：${openError}`,
        };
      }
      appendUpdaterLog(`official-push-installer-opened version=${officialPush.version} file=${downloaded.fileName}`);
      return { ok: true, version: officialPush.version, fileName: downloaded.fileName };
    } catch (err) {
      const message = normalizeUpdateErrorMessage(err instanceof Error ? err.message : String(err));
      console.error('[autoUpdater] installOfficialPush failed:', message);
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
    if (currentOrgCode && currentFeedBaseUrl) {
      checkOfficialPush().catch((err) => console.warn('[autoUpdater] initial official push check failed:', err));
      return;
    }
    autoUpdater.checkForUpdates().catch((err) => console.warn('[autoUpdater] initial checkForUpdates failed:', err));
  }, CHECK_DELAY_MS);

  recheckTimer = setInterval(() => {
    if (currentOrgCode && currentFeedBaseUrl) {
      checkOfficialPush().catch((err) => console.warn('[autoUpdater] periodic official push check failed:', err));
      return;
    }
    autoUpdater.checkForUpdates().catch((err) => console.warn('[autoUpdater] periodic checkForUpdates failed:', err));
  }, RECHECK_INTERVAL_MS);

  app.on('before-quit', () => {
    if (recheckTimer) {
      clearInterval(recheckTimer);
      recheckTimer = null;
    }
    stopOfficialPushPolling();
  });
}
