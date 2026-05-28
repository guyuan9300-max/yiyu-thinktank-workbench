import { contextBridge, ipcRenderer, webUtils } from 'electron';
import type {
  CollabActionResult,
  CollabRepoStatus,
  CommitAndPushToMainPayload,
  DesktopAppInfo,
  DesktopStartupGateResumeResult,
  PullPreview,
  PullSelectedFromMainPayload,
  PushPreview,
} from '../shared/types.js';

// V2.1 Lab 模式 (顾源源 5/22 方案 C): ENV YIYU_LAB_MODE=1 时 frontend 连 V2.1 backend (47831)
const LAB_MODE_PRELOAD = process.env.YIYU_LAB_MODE === '1';
const DEFAULT_BACKEND_PORT_PRELOAD = LAB_MODE_PRELOAD ? 47831 : 47829;
const backendBaseUrl = process.env.YIYU_BACKEND_URL ?? `http://127.0.0.1:${DEFAULT_BACKEND_PORT_PRELOAD}`;

interface UpdateEventPayload {
  kind: 'checking' | 'available' | 'not-available' | 'download-progress' | 'downloaded' | 'error';
  version?: string;
  releaseNotes?: string | null;
  percent?: number;
  bytesPerSecond?: number;
  transferred?: number;
  total?: number;
  message?: string;
}

contextBridge.exposeInMainWorld('yiyuWorkbench', {
  backendBaseUrl,
  // 迷你面板:进入/退出桌面挂件模式(缩小窗 + 置顶);主进程做窗口 resize。
  setMiniMode: (enter: boolean): Promise<{ mini: boolean }> => ipcRenderer.invoke('yiyu-workbench:setMiniMode', enter),
  getDesktopAppInfo: (): Promise<DesktopAppInfo> => ipcRenderer.invoke('yiyu-workbench:getDesktopAppInfo'),
  resumeFromStartupGate: (): Promise<DesktopStartupGateResumeResult> => ipcRenderer.invoke('yiyu-workbench:resumeFromStartupGate'),
  selectFiles: (): Promise<string[]> => ipcRenderer.invoke('yiyu-workbench:selectFiles'),
  selectFolder: (): Promise<string | null> => ipcRenderer.invoke('yiyu-workbench:selectFolder'),
  selectCollabRepo: (): Promise<string | null> => ipcRenderer.invoke('yiyu-workbench:selectCollabRepo'),
  getCollabRepoStatus: (repoPath?: string | null): Promise<CollabRepoStatus> =>
    ipcRenderer.invoke('yiyu-workbench:getCollabRepoStatus', repoPath),
  previewPushToMain: (repoPath: string): Promise<PushPreview> =>
    ipcRenderer.invoke('yiyu-workbench:previewPushToMain', repoPath),
  commitAndPushToMain: (payload: CommitAndPushToMainPayload): Promise<CollabActionResult> =>
    ipcRenderer.invoke('yiyu-workbench:commitAndPushToMain', payload),
  previewPullFromMain: (repoPath: string, targetCommit?: string | null): Promise<PullPreview> =>
    ipcRenderer.invoke('yiyu-workbench:previewPullFromMain', repoPath, targetCommit ?? null),
  pullSelectedFromMain: (payload: PullSelectedFromMainPayload): Promise<CollabActionResult> =>
    ipcRenderer.invoke('yiyu-workbench:pullSelectedFromMain', payload),
  rebuildAndInstallFromRepo: (repoPath: string): Promise<boolean> =>
    ipcRenderer.invoke('yiyu-workbench:rebuildAndInstallFromRepo', repoPath),
  setWorkspaceInteractionState: (payload: { active: boolean; source: string; detail?: string | null }): Promise<{
    active: boolean;
    source: string;
    detail?: string | null;
    updatedAt: string;
  }> => ipcRenderer.invoke('yiyu-workbench:setWorkspaceInteractionState', payload),
  getDroppedFilePath: (file: File): string | null => {
    try {
      return webUtils.getPathForFile(file) || null;
    } catch {
      return null;
    }
  },
  readTextFile: (targetPath: string): Promise<string> => ipcRenderer.invoke('yiyu-workbench:readTextFile', targetPath),
  openPath: (targetPath: string): Promise<boolean> => ipcRenderer.invoke('yiyu-workbench:openPath', targetPath),
  openExternalUrl: (targetUrl: string): Promise<boolean> => ipcRenderer.invoke('yiyu-workbench:openExternalUrl', targetUrl),
  revealInFinder: (targetPath: string): Promise<boolean> => ipcRenderer.invoke('yiyu-workbench:revealInFinder', targetPath),
  saveFileAs: (sourcePath: string, suggestedName?: string): Promise<string | null> =>
    ipcRenderer.invoke('yiyu-workbench:saveFileAs', sourcePath, suggestedName),
  quitApp: (): Promise<boolean> => ipcRenderer.invoke('yiyu-workbench:quitApp'),
  saveRecordingBlob: (payload: {
    buffer: ArrayBuffer;
    extension?: string;
    sessionId?: string;
  }): Promise<{ absolutePath: string; sizeBytes: number; sessionId: string }> =>
    ipcRenderer.invoke('yiyu-workbench:saveRecordingBlob', payload),
  readRecordingFile: (absolutePath: string): Promise<{ buffer: Uint8Array; sizeBytes: number; name: string }> =>
    ipcRenderer.invoke('yiyu-workbench:readRecordingFile', absolutePath),
  setRecordingActive: (payload: { active: boolean; taskTitle?: string }): Promise<{ active: boolean }> =>
    ipcRenderer.invoke('yiyu-workbench:setRecordingActive', payload),
  watchFile: (targetPath: string): Promise<boolean> => ipcRenderer.invoke('yiyu-workbench:watchFile', targetPath),
  unwatchFile: (targetPath: string): Promise<boolean> => ipcRenderer.invoke('yiyu-workbench:unwatchFile', targetPath),
  onFileChanged: (callback: (filePath: string) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, filePath: string) => callback(filePath);
    ipcRenderer.on('yiyu-workbench:fileChanged', handler);
    return () => { ipcRenderer.removeListener('yiyu-workbench:fileChanged', handler); };
  },
  checkForUpdates: (): Promise<{ ok: boolean; version?: string | null; reason?: string }> =>
    ipcRenderer.invoke('yiyu-workbench:update.check'),
  quitAndInstallUpdate: (): Promise<{ ok: boolean; reason?: string }> =>
    ipcRenderer.invoke('yiyu-workbench:update.quitAndInstall'),
  onUpdateEvent: (callback: (payload: UpdateEventPayload) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, payload: UpdateEventPayload) => callback(payload);
    ipcRenderer.on('yiyu-workbench:update-event', handler);
    return () => { ipcRenderer.removeListener('yiyu-workbench:update-event', handler); };
  },
});
