import React, { useEffect, useMemo, useState } from 'react';
import { Database, FolderOpen, RefreshCw, Sparkles, UploadCloud, X } from 'lucide-react';

import type { ClientSummary, ImportRecord, LegacyScanReport } from '../../../../src/shared/types';
import { clearDemoData, loadDemoData, scanLegacy } from '../../lib/legacySettingsApi';

type FlashLevel = 'success' | 'error' | 'info';

type LegacyMigrationDemoPanelProps = {
  clients: ClientSummary[];
  currentClientId?: string;
  demoDataLoaded?: boolean;
  selectFolderBridge: () => Promise<string | null>;
  createBackup: () => Promise<{ backupPath: string; createdAt: string }>;
  importPaths: (clientId: string, mode: 'folder' | 'file', paths: string[], options?: { allowLegacy?: boolean }) => Promise<ImportRecord[]>;
  loadLogsBlock: () => Promise<void>;
  refreshWorkspace: (clientId: string) => Promise<void>;
  loadAll: (clientId?: string) => Promise<void>;
  flash: (level: FlashLevel, message: string) => void;
};

export function LegacyMigrationDemoPanel({
  clients,
  currentClientId,
  demoDataLoaded,
  selectFolderBridge,
  createBackup,
  importPaths,
  loadLogsBlock,
  refreshWorkspace,
  loadAll,
  flash,
}: LegacyMigrationDemoPanelProps) {
  const [legacyScanResult, setLegacyScanResult] = useState<LegacyScanReport | null>(null);
  const [legacyImportClientId, setLegacyImportClientId] = useState('');
  const [isImportingLegacy, setIsImportingLegacy] = useState(false);

  useEffect(() => {
    const preferredClientId =
      (currentClientId && clients.some((client) => client.id === currentClientId) && currentClientId) ||
      clients[0]?.id ||
      '';
    setLegacyImportClientId((prev) => (prev && clients.some((client) => client.id === prev) ? prev : preferredClientId));
  }, [clients, currentClientId]);

  const importableLegacyEntries = useMemo(
    () => legacyScanResult?.entries.filter((entry) => entry.importable) || [],
    [legacyScanResult],
  );

  const handleImportLegacyEntries = async () => {
    if (!legacyImportClientId) {
      flash('error', '请先选择一个客户用于接收旧数据导入');
      return;
    }
    if (!importableLegacyEntries.length) {
      flash('info', '当前扫描结果中没有可导入的 JSON 或 CSV 文件');
      return;
    }
    setIsImportingLegacy(true);
    try {
      const imported = await importPaths(
        legacyImportClientId,
        'file',
        importableLegacyEntries.map((entry) => entry.path),
        { allowLegacy: true },
      );
      await Promise.all([loadLogsBlock(), legacyImportClientId === currentClientId ? refreshWorkspace(legacyImportClientId) : Promise.resolve()]);
      flash('success', `已向目标客户导入 ${imported.reduce((sum, item) => sum + item.importedCount, 0)} 份旧数据文件`);
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '旧数据导入失败');
    } finally {
      setIsImportingLegacy(false);
    }
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
      <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
        <h2 className="text-[16px] font-bold text-gray-900 mb-4">备份与旧数据导入</h2>
        <div className="flex flex-wrap gap-3 mb-4">
          <button type="button" onClick={() => { void createBackup().then(async (backup) => { await loadAll(); flash('success', `已生成备份：${backup.backupPath.split('/').pop()}`); }).catch((error) => flash('error', error instanceof Error ? error.message : '备份失败')); }} className="inline-flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-semibold text-gray-700">
            <Database size={16} /> 立即备份
          </button>
          <button type="button" onClick={() => { void selectFolderBridge().then((folder) => { if (!folder) return; void scanLegacy(folder).then((result) => setLegacyScanResult(result)).catch((error) => flash('error', error instanceof Error ? error.message : '扫描失败')); }); }} className="inline-flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-semibold text-gray-700">
            <FolderOpen size={16} /> 扫描旧数据
          </button>
        </div>
        {legacyScanResult && (
          <div className="space-y-3">
            <p className="text-[12px] font-bold text-gray-900">{legacyScanResult.path}</p>
            <p className="text-[12px] text-gray-500">{legacyScanResult.message}</p>
            <div className="flex flex-col md:flex-row gap-3">
              <select value={legacyImportClientId} onChange={(event) => setLegacyImportClientId(event.target.value)} className="flex-1 bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none">
                <option value="">选择导入目标客户</option>
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>{client.name}</option>
                ))}
              </select>
              <button type="button" onClick={() => void handleImportLegacyEntries()} disabled={isImportingLegacy || !importableLegacyEntries.length} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-semibold text-gray-700 disabled:opacity-50">
                {isImportingLegacy ? <RefreshCw size={16} className="animate-spin" /> : <UploadCloud size={16} />}
                导入可导入文件
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-[16px] font-bold text-gray-900">演示数据</h2>
            <p className="text-[12px] text-gray-500 mt-1">只在需要演示时手动载入，正式使用可以随时清空。</p>
          </div>
          <span className={`text-[11px] font-bold px-3 py-1.5 rounded-full ${demoDataLoaded ? 'bg-amber-50 text-amber-700' : 'bg-gray-100 text-gray-500'}`}>
            {demoDataLoaded ? '已载入演示数据' : '未载入演示数据'}
          </span>
        </div>
        <div className="flex flex-wrap gap-3">
          <button type="button" onClick={() => { void loadDemoData().then(async () => { await loadAll('client_cffc'); flash('success', '演示数据已载入'); }).catch((error) => flash('error', error instanceof Error ? error.message : '载入失败')); }} className="inline-flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-semibold text-gray-700">
            <Sparkles size={16} /> 载入演示数据
          </button>
          <button type="button" onClick={() => { void clearDemoData().then(async () => { await loadAll(); flash('success', '演示数据已清空'); }).catch((error) => flash('error', error instanceof Error ? error.message : '清空失败')); }} className="inline-flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] font-semibold text-gray-700">
            <X size={16} /> 清空演示数据
          </button>
        </div>
      </div>
    </div>
  );
}
