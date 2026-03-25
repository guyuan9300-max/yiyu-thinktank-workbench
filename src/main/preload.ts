import { contextBridge, ipcRenderer, webUtils } from 'electron';
import type { BettaFishSignal, DesktopAppInfo, DiagnosisEngineHealth, ExternalDiagnosisRequest } from '../shared/types.js';

const backendBaseUrl = process.env.YIYU_BACKEND_URL ?? 'http://127.0.0.1:47829';

contextBridge.exposeInMainWorld('yiyuWorkbench', {
  backendBaseUrl,
  getDesktopAppInfo: (): Promise<DesktopAppInfo> => ipcRenderer.invoke('yiyu-workbench:getDesktopAppInfo'),
  selectFiles: (): Promise<string[]> => ipcRenderer.invoke('yiyu-workbench:selectFiles'),
  selectFolder: (): Promise<string | null> => ipcRenderer.invoke('yiyu-workbench:selectFolder'),
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
  getDiagnosisEngineHealth: (): Promise<DiagnosisEngineHealth[]> => ipcRenderer.invoke('yiyu-workbench:diagnosisEngineHealth'),
  runBettafishDiagnosis: (payload: ExternalDiagnosisRequest): Promise<BettaFishSignal> => ipcRenderer.invoke('yiyu-workbench:runBettafishDiagnosis', payload),
});
