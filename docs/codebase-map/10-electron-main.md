# src/main：Electron 主进程结构索引

## 文件清单

```
-rwx------ 1 peaceful-admiring-hopper peaceful-admiring-hopper  70083 May  9 03:47 collabGit.ts
-rw------- 1 peaceful-admiring-hopper peaceful-admiring-hopper 110970 May 11 05:23 main.ts
-rw------- 1 peaceful-admiring-hopper peaceful-admiring-hopper   3663 May  6 22:35 preload.ts
-rwx------ 1 peaceful-admiring-hopper peaceful-admiring-hopper  10643 Apr 27 07:21 runtimeManifest.ts
```

## main.ts（2976 行）

### 顶层 import 来源（前 40 条）
```
import { writeFileSync, appendFileSync, mkdirSync } from 'node:fs';
import { app, BrowserWindow, dialog, ipcMain, protocol, shell } from 'electron';
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import http from 'node:http';
import net from 'node:net';
import type {
import { buildRendererLaunchQuery } from '../shared/rendererLaunchQuery.js';
import {
```

### 顶层常量
```
25:const DEFAULT_BACKEND_PORT = 47829;
26:const DEFAULT_CLOUD_BACKEND_PORT = 47830;
27:const DEFAULT_PACKAGED_REMOTE_CLOUD_API_URL = 'http://101.126.34.232';
30:const REQUIRED_BACKEND_FEATURES = ['knowledge.vectorize-answer', 'knowledge.reclass-events', 'chat.general-answer', 'chat.async-status'];
31:const REQUIRED_BACKEND_SCHEMA_VERSION = 20260420;
32:const APP_DISPLAY_NAME = '益语智库自用平台 V2.0';
33:const APP_BUNDLE_ID = 'com.yiyu.selfworkbench2';
104:const LOCAL_DEV_CLOUD_SEED_ENV_KEYS = [
113:const RENDERER_QUERY_ARG = '--yiyu-renderer-query';
114:const PACKAGED_RUNTIME_MANIFEST_FILE = 'runtime-seed-manifest.json';
115:const PACKAGED_RUNTIME_REQUIREMENTS_FILE = 'backend-requirements.txt';
116:const PACKAGED_RUNTIME_WHEELHOUSE_DIR = 'wheelhouse';
117:const PACKAGED_RUNTIME_PYTHON_SEED_DIR = 'python-seed';
```

### 函数声明
```
119:function normalizeHttpUrl(rawUrl?: string | null) {
125:function localDevCloudSeedEnv() {
136:function remoteCloudBackendUrl() {
147:function shouldUseRemoteCloudBackend() {
151:function shouldUseBundledLocalCloudBackend() {
155:function rendererLaunchQuery() {
169:function appendElectronLaunchLog(level: 'INFO' | 'ERROR', message: string) {
180:function writeProcessStreamSafely(stream: NodeJS.WriteStream | undefined, text: string) {
191:function logElectronInfo(message: string) {
196:function logElectronError(message: string) {
223:function currentRendererUrl() {
231:function isStartupGatePageActive() {
236:function requestAppQuit(reason: string, source: string, metadata: QuitRequestMetadata = {}) {
253:function shouldDeferDangerousRestart() {
257:function rememberBackendLogLine(line: string) {
266:function getCollabSuggestedCandidates() {
281:async function loadInternalCollabGit() {
286:function resolveBundlePath(executablePath: string) {
295:async function readBundleId(appBundlePath: string) {
302:async function scanApplicationDirectory(baseDir: string) {
309:async function collectInstalledAppPaths(currentAppBundlePath: string) {
330:async function cleanupStaleInstallBundles() {
366:async function runTaskWindowDiagnostics(window: BrowserWindow) {
532:async function runEventLineCreateDiagnostics(window: BrowserWindow) {
610:async function runUiSurfaceAudit(window: BrowserWindow) {
904:function parseBooleanEnv(value: string | undefined, fallback = false) {
909:function quoteShellArg(value: string) {
914:function isExecutable(filePath: string) {
923:function resolveUvBinary() {
947:function backendEnv(extraEnv: NodeJS.ProcessEnv = {}) {
972:function runtimePythonPath(venvPath: string) {
976:async function runCommand(command: string, args: string[], env: NodeJS.ProcessEnv, label: string) {
997:async function assertPythonRuntimeUsable(pythonPath: string, label: string, env: NodeJS.ProcessEnv) {
1017:async function runJsonCommand(command: string, args: string[], env: NodeJS.ProcessEnv, label: string) {
1048:function getBackendPythonPath() {
1056:function projectRuntimeMetadataPath(projectDirName: 'backend' | 'cloud_backend', venvPath: string) {
1060:function readRuntimeSyncMetadata(metadataPath: string): RuntimeSyncMetadata | null {
1077:function writeRuntimeSyncMetadata(metadataPath: string, metadata: RuntimeSyncMetadata) {
1081:function buildRuntimeFingerprint(projectDirName: 'backend' | 'cloud_backend') {
1090:function sha256FileHex(targetPath: string) {
1094:function sha256DirectoryHex(rootPath: string) {
1126:function packagedRuntimeRoot() {
1132:function readPackagedRuntimeSeed(): PackagedRuntimeSeed {
1155:function packagedRuntimeFingerprint(seed: PackagedRuntimeSeed) {
1171:function validatePackagedRuntimeSeed(seed: PackagedRuntimeSeed) {
1220:function assertRuntimeVenvPathIsSafe(venvPath: string) {
1228:function evaluateBackendRuntimeWarning(payload: BackendHealthPayload): string | null {
1242:async function extractPlatformDnaText(targetPath: string) {
1262:async function ensurePackagedBackendRuntime(venvPath: string) {
1329:async function ensureProjectRuntime(projectDirName: 'backend' | 'cloud_backend', venvPath: string) {
1367:function backendUrl() {
1376:function requestBackendJson<T>(pathName: string, timeoutMs = 6000): Promise<T> {
1411:async function requireActiveMaintenanceMode(actionLabel: string) {
1418:function cloudBackendUrl() {
1422:function rendererUrl() {
1426:function rendererProtocolUrl() {
1430:function writeRendererDiagnosticPage(fileName: string, html: string) {
1437:function rendererBootstrapPageUrl(detail = '正在连接本地界面与后台服务，请稍候…') {
1441:function rendererFailurePageUrl(detail: string) {
1445:function startupRepairPageUrl(appInfo: DesktopAppInfo, rebuildRepoPath: string | null) {
1449:async function registerRendererProtocol() {
1488:async function checkBackendHealthAt(port: number, requiredFeatures: string[]): Promise<boolean> {
1517:async function checkCloudBackendHealthAt(port: number): Promise<boolean> {
1521:async function checkCloudBackendHealth(targetUrl: string): Promise<boolean> {
1535:async function fetchBackendHealthSnapshot(port = backendPort): Promise<BackendHealthPayload | null> {
1561:async function resolveDesktopAppInfo(healthOverride?: BackendHealthPayload | null): Promise<DesktopAppInfo> {
1601:async function resumeFromStartupGate(): Promise<DesktopStartupGateResumeResult> {
1634:async function isPortAvailable(port: number): Promise<boolean> {
1646:async function reservePort(preferredPort: number, reservedPorts = new Set<number>()): Promise<number> {
1659:async function terminateManagedRuntimeProcess(venvPath: string) {
1671:async function recyclePackagedRuntimeProcesses() {
1677:function purgeSavedApplicationState() {
1685:function logBackend(pipe: NodeJS.ReadableStream, label: string, onLine?: (line: string) => void) {
1700:function startBackend() {
1734:function startCloudBackend() {
1767:function stopBackend() {
1774:function stopCloudBackend() {
1781:function rendererContentType(filePath: string) {
1806:async function startRendererStaticServer() {
1845:function stopRendererStaticServer() {
1851:function buildRendererFailurePage(detail: string) {
1902:function buildRendererBootstrapPage(detail = '正在连接本地界面与后台服务，请稍候…') {
1987:function escapeHtml(value: string) {
1996:function buildStartupRepairPage(appInfo: DesktopAppInfo, rebuildRepoPath: string | null) {
2270:async function loadRendererWithFallback(window: BrowserWindow) {
2312:function buildBackendStartupError(prefix: string) {
2320:async function waitForBackend(timeoutMs = 45000): Promise<BackendHealthPayload> {
2364:async function waitForCloudBackend(timeoutMs = 20000): Promise<void> {
2387:async function createMainWindow(options: { startupGateInfo?: DesktopAppInfo | null } = {}) {
2856:function inferClientWorkspaceRootFromPath(targetPath: string) {
2865:function findSameNamedWorkspaceFile(targetPath: string) {
```

### IPC handler 注册
```
2703:ipcMain.handle('yiyu-workbench:selectFiles', async () => {
2711:ipcMain.handle('yiyu-workbench:getDesktopAppInfo', async () => {
2715:ipcMain.handle('yiyu-workbench:resumeFromStartupGate', async () => {
2719:ipcMain.handle('yiyu-workbench:selectFolder', async () => {
2727:ipcMain.handle('yiyu-workbench:selectCollabRepo', async () => {
2741:ipcMain.handle('yiyu-workbench:getCollabRepoStatus', async (_event, repoPath?: string | null) => {
2750:ipcMain.handle('yiyu-workbench:previewPushToMain', async (_event, repoPath: string) => {
2760:ipcMain.handle('yiyu-workbench:commitAndPushToMain', async (_event, payload: CommitAndPushToMainPayload) => {
2766:ipcMain.handle('yiyu-workbench:previewPullFromMain', async (_event, repoPath: string, targetCommit?: string | null) => {
2777:ipcMain.handle('yiyu-workbench:pullSelectedFromMain', async (_event, payload: PullSelectedFromMainPayload) => {
2783:ipcMain.handle('yiyu-workbench:setWorkspaceInteractionState', async (_event, payload?: {
2798:ipcMain.handle('yiyu-workbench:rebuildAndInstallFromRepo', async (_event, repoPath: string) => {
2832:ipcMain.handle('yiyu-workbench:quitApp', async () => {
2837:ipcMain.handle('yiyu-workbench:readTextFile', async (_event, targetPath: string) => {
2893:ipcMain.handle('yiyu-workbench:openPath', async (_event, targetPath: string) => {
2914:ipcMain.handle('yiyu-workbench:watchFile', async (_event, targetPath: string) => {
2942:ipcMain.handle('yiyu-workbench:unwatchFile', async (_event, targetPath: string) => {
2952:ipcMain.handle('yiyu-workbench:openExternalUrl', async (_event, targetUrl: string) => {
2957:ipcMain.handle('yiyu-workbench:revealInFinder', async (_event, targetPath: string) => {
2962:ipcMain.handle('yiyu-workbench:saveFileAs', async (_event, sourcePath: string, suggestedName?: string) => {
```

### App 生命周期事件
```
2505:app.on('second-instance', () => {
2640:  app.on('activate', async () => {
2688:app.on('before-quit', (event) => {
2693:app.on('will-quit', () => {
2696:app.on('window-all-closed', () => {
```

### contextBridge / BrowserWindow / webContents
```
225:    return mainWindow && !mainWindow.isDestroyed() ? mainWindow.webContents.getURL() : null;
369:  const inspectEvidenceQuery = async () => window.webContents.executeJavaScript(`
386:  const inspectTargets = async () => window.webContents.executeJavaScript(`
439:    window.webContents.sendInputEvent({ type: 'mouseMove', x, y });
440:    window.webContents.sendInputEvent({ type: 'mouseDown', x, y, button: 'left', clickCount: 1 });
441:    window.webContents.sendInputEvent({ type: 'mouseUp', x, y, button: 'left', clickCount: 1 });
486:    const afterCalendar = await window.webContents.executeJavaScript(`
510:    const afterCreate = await window.webContents.executeJavaScript(`
537:    window.webContents.executeJavaScript(
551:    window.webContents.executeJavaScript(
582:    const openTaskResult = await window.webContents.executeJavaScript(
659:        const state = await window.webContents.executeJavaScript(
706:    await window.webContents.executeJavaScript(
790:    return await window.webContents.executeJavaScript(
2388:  mainWindow = new BrowserWindow({
2405:  mainWindow.webContents.on('console-message', (_event, level, message, line, sourceId) => {
2408:  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
2411:  mainWindow.webContents.on('did-finish-load', () => {
2412:    logElectronInfo(`[renderer:did-finish-load] url=${mainWindow?.webContents.getURL() ?? 'unknown'}`);
2416:      void targetWindow.webContents.executeJavaScript(`
2447:  mainWindow.webContents.on('render-process-gone', (_event, details) => {
2478:    mainWindow.webContents.openDevTools({ mode: 'detach' });
2930:            win.webContents.send('yiyu-workbench:fileChanged', targetPath);
```

## preload.ts（61 行）

### 顶层 import 来源（前 40 条）
```
import { contextBridge, ipcRenderer, webUtils } from 'electron';
import type {
```

### 顶层常量
```
```

### 函数声明
```
```

### IPC handler 注册
```
```

### App 生命周期事件
```
```

### contextBridge / BrowserWindow / webContents
```
1:import { contextBridge, ipcRenderer, webUtils } from 'electron';
15:contextBridge.exposeInMainWorld('yiyuWorkbench', {
```

