import React, { useState } from 'react';
import { RefreshCw, UploadCloud } from 'lucide-react';

import {
  parseOrganizationRiskDnaDocument,
  type OrganizationRiskDnaDocument,
} from '../../lib/fundraisingWorkbenchAssets';

type OrganizationRiskDnaSettingsPanelProps = {
  document: OrganizationRiskDnaDocument | null;
  onPickFile: () => Promise<string[]>;
  onReadFile: (targetPath: string) => Promise<string>;
  onSaveDocument: (document: OrganizationRiskDnaDocument | null) => Promise<void>;
  disabled?: boolean;
  onDataChange?: () => void;
};

export function OrganizationRiskDnaSettingsPanel({
  document,
  onPickFile,
  onReadFile,
  onSaveDocument,
  disabled = false,
  onDataChange,
}: OrganizationRiskDnaSettingsPanelProps) {
  const [isUploading, setIsUploading] = useState(false);

  const uploadDocument = async () => {
    setIsUploading(true);
    try {
      const filePaths = await onPickFile();
      const filePath = filePaths[0];
      if (!filePath) return;
      if (!/\.(md|markdown|txt|docx|pdf)$/i.test(filePath)) {
        throw new Error('当前只支持 Markdown、DOCX、PDF 或 TXT。');
      }
      const text = await onReadFile(filePath);
      if (!text.trim()) {
        throw new Error('文档里没有抽出可用文本，请换一份更完整的文件。');
      }
      const fileName = filePath.split('/').pop() || 'organization-risk.md';
      const nextDocument = parseOrganizationRiskDnaDocument(text, fileName, filePath);
      await onSaveDocument(nextDocument);
      onDataChange?.();
    } catch (error) {
      window.alert(error instanceof Error ? error.message : '组织风险 DNA 上传失败');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h2 className="text-[16px] font-bold text-gray-900">组织风险 DNA</h2>
          <p className="text-[12px] text-gray-500 mt-1">组织级一次配置，沉淀这家机构最容易触发的敏感点、误读点和表达边界，供整个测试工作台共享使用。</p>
        </div>
        <button
          type="button"
          onClick={() => {
            void uploadDocument();
          }}
          disabled={disabled}
          className="inline-flex items-center gap-2 rounded-2xl bg-[#5B7BFE] px-4 py-2.5 text-[12px] font-semibold text-white shadow-[0_10px_24px_-14px_rgba(91,123,254,0.55)]"
        >
          {isUploading ? <RefreshCw size={14} className="animate-spin" /> : <UploadCloud size={14} />}
          {document ? '替换文档' : '上传DNA文档'}
        </button>
      </div>

      {document ? (
        <div className="rounded-2xl border border-gray-100 bg-gray-50/70 px-4 py-4">
          <p className="text-[13px] font-medium leading-7 text-gray-700">{document.summary}</p>
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400">高危风险</div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {document.coreRisks.length > 0 ? (
                  document.coreRisks.slice(0, 6).map((item) => (
                    <span key={item} className="rounded-[8px] bg-white px-2 py-1 text-[10px] font-semibold text-gray-600 border border-gray-100">
                      {item}
                    </span>
                  ))
                ) : (
                  <span className="text-[12px] text-gray-400">还没有识别出高危风险条目</span>
                )}
              </div>
            </div>
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400">敏感场景</div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {document.sensitiveScenarios.length > 0 ? (
                  document.sensitiveScenarios.slice(0, 6).map((item) => (
                    <span key={item} className="rounded-[8px] bg-white px-2 py-1 text-[10px] font-semibold text-gray-600 border border-gray-100">
                      {item}
                    </span>
                  ))
                ) : (
                  <span className="text-[12px] text-gray-400">还没有识别出敏感场景条目</span>
                )}
              </div>
            </div>
          </div>
          <p className="mt-4 text-[11px] text-gray-400">{document.fileName} · {document.updatedAt.replace('T', ' ').slice(0, 16)}</p>
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-gray-200 px-4 py-8 text-center text-[12px] text-gray-400">
          还没有上传组织风险 DNA。上传后，筹款测试会自动带入组织级风险边界。
        </div>
      )}
    </div>
  );
}
