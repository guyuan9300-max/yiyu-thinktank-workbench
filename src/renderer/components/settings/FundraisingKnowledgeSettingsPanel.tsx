import React, { useMemo, useState } from 'react';
import { BookOpen, RefreshCw, UploadCloud } from 'lucide-react';

import {
  parseFundraisingKnowledgeDocument,
  type FundraisingKnowledgeDocument,
} from '../../lib/fundraisingWorkbenchAssets';

type FundraisingKnowledgeSettingsPanelProps = {
  entries: FundraisingKnowledgeDocument[];
  onPickFile: () => Promise<string[]>;
  onReadFile: (targetPath: string) => Promise<string>;
  onSaveEntries: (entries: FundraisingKnowledgeDocument[]) => Promise<void>;
  disabled?: boolean;
  onDataChange?: () => void;
};

export function FundraisingKnowledgeSettingsPanel({
  entries,
  onPickFile,
  onReadFile,
  onSaveEntries,
  disabled = false,
  onDataChange,
}: FundraisingKnowledgeSettingsPanelProps) {
  const [uploadingId, setUploadingId] = useState<string | null>(null);

  const sortedEntries = useMemo(
    () => [...entries].sort((left, right) => right.updatedAt.localeCompare(left.updatedAt)),
    [entries],
  );

  const uploadKnowledge = async (existing?: FundraisingKnowledgeDocument | null) => {
    setUploadingId(existing?.id || 'new');
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
      const fileName = filePath.split('/').pop() || 'fundraising-knowledge.md';
      const nextEntry = parseFundraisingKnowledgeDocument(text, fileName, filePath);
      const normalizedEntry = existing ? { ...nextEntry, id: existing.id, title: existing.title || nextEntry.title } : nextEntry;
      const nextEntries = [
        ...entries.filter((item) => item.id !== normalizedEntry.id),
        normalizedEntry,
      ];
      await onSaveEntries(nextEntries);
      onDataChange?.();
    } catch (error) {
      window.alert(error instanceof Error ? error.message : '筹款知识库文档上传失败');
    } finally {
      setUploadingId(null);
    }
  };

  return (
    <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h2 className="text-[16px] font-bold text-gray-900">筹款知识库</h2>
          <p className="text-[12px] text-gray-500 mt-1">上传筹款方法论、案例总结和平台规则，作为组织级共享知识库，让诊断建议自动映射到相关知识条目。</p>
        </div>
        <button
          type="button"
          onClick={() => {
            void uploadKnowledge();
          }}
          disabled={disabled}
          className="inline-flex items-center gap-2 rounded-2xl bg-[#5B7BFE] px-4 py-2.5 text-[12px] font-semibold text-white shadow-[0_10px_24px_-14px_rgba(91,123,254,0.55)]"
        >
          {uploadingId === 'new' ? <RefreshCw size={14} className="animate-spin" /> : <UploadCloud size={14} />}
          上传知识文档
        </button>
      </div>

      <div className="space-y-3">
        {sortedEntries.map((entry) => {
          const isUploading = uploadingId === entry.id;
          return (
            <div key={entry.id} className="rounded-2xl border border-gray-100 bg-gray-50/70 px-4 py-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <BookOpen size={16} className="text-[#5B7BFE]" />
                    <p className="text-[14px] font-bold text-gray-900">{entry.title}</p>
                  </div>
                  <p className="mt-2 text-[12px] leading-6 text-gray-600">{entry.summary}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {[...entry.scenes, ...entry.tags].slice(0, 6).map((tag) => (
                      <span key={`${entry.id}-${tag}`} className="rounded-[8px] bg-white px-2 py-1 text-[10px] font-semibold text-gray-500 border border-gray-100">
                        {tag}
                      </span>
                    ))}
                  </div>
                  <p className="mt-3 text-[11px] text-gray-400">{entry.fileName} · {entry.updatedAt.replace('T', ' ').slice(0, 16)}</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    void uploadKnowledge(entry);
                  }}
                  disabled={disabled}
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-2 text-[11px] font-semibold text-gray-600"
                >
                  {isUploading ? <RefreshCw size={14} className="animate-spin" /> : <UploadCloud size={14} />}
                  替换文档
                </button>
              </div>
            </div>
          );
        })}

        {sortedEntries.length === 0 && (
          <div className="rounded-2xl border border-dashed border-gray-200 px-4 py-8 text-center text-[12px] text-gray-400">
            还没有上传筹款知识库文档。上传后，系统会把建议自动映射到相关知识条目。
          </div>
        )}
      </div>
    </div>
  );
}
