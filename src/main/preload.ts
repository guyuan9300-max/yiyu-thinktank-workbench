import { contextBridge, ipcRenderer, webUtils } from 'electron';
import type {
  CollabActionResult,
  CollabRepoStatus,
  CommitAndPushToMainPayload,
  DesktopAppInfo,
  PullPreview,
  PullSelectedFromMainPayload,
  PushPreview,
} from '../shared/types.js';

const backendBaseUrl = process.env.YIYU_BACKEND_URL ?? 'http://127.0.0.1:47829';

contextBridge.exposeInMainWorld('yiyuWorkbench', {
  backendBaseUrl,
  getDesktopAppInfo: (): Promise<DesktopAppInfo> => ipcRenderer.invoke('yiyu-workbench:getDesktopAppInfo'),
  selectFiles: (): Promise<string[]> => ipcRenderer.invoke('yiyu-workbench:selectFiles'),
  selectFolder: (): Promise<string | null> => ipcRenderer.invoke('yiyu-workbench:selectFolder'),
  selectCollabRepo: (): Promise<string | null> => ipcRenderer.invoke('yiyu-workbench:selectCollabRepo'),
  getCollabRepoStatus: (repoPath?: string | null): Promise<CollabRepoStatus> =>
    ipcRenderer.invoke('yiyu-workbench:getCollabRepoStatus', repoPath),
  previewPushToMain: (repoPath: string): Promise<PushPreview> =>
    ipcRenderer.invoke('yiyu-workbench:previewPushToMain', repoPath),
  commitAndPushToMain: (payload: CommitAndPushToMainPayload): Promise<CollabActionResult> =>
    ipcRenderer.invoke('yiyu-workbench:commitAndPushToMain', payload),
  previewPullFromMain: (repoPath: string): Promise<PullPreview> =>
    ipcRenderer.invoke('yiyu-workbench:previewPullFromMain', repoPath),
  pullSelectedFromMain: (payload: PullSelectedFromMainPayload): Promise<CollabActionResult> =>
    ipcRenderer.invoke('yiyu-workbench:pullSelectedFromMain', payload),
  rebuildAndInstallFromRepo: (repoPath: string): Promise<boolean> =>
    ipcRenderer.invoke('yiyu-workbench:rebuildAndInstallFromRepo', repoPath),
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
  watchFile: (targetPath: string): Promise<boolean> => ipcRenderer.invoke('yiyu-workbench:watchFile', targetPath),
  unwatchFile: (targetPath: string): Promise<boolean> => ipcRenderer.invoke('yiyu-workbench:unwatchFile', targetPath),
  onFileChanged: (callback: (filePath: string) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, filePath: string) => callback(filePath);
    ipcRenderer.on('yiyu-workbench:fileChanged', handler);
    return () => { ipcRenderer.removeListener('yiyu-workbench:fileChanged', handler); };
  },
});
