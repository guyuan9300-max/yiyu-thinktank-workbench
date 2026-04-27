import React from 'react';

export function DataCenterOpsPanel({ clientId }: { clientId?: string | null }) {
  return (
    <div className="mt-5 rounded-3xl border border-slate-100 bg-slate-50/70 p-4">
      <p className="text-[13px] font-bold text-slate-800">数据中心运行诊断</p>
      <p className="mt-1 text-[12px] leading-5 text-slate-500">
        {clientId ? '当前客户的数据中心诊断入口已保留。' : '选择客户后可查看对应数据中心诊断。'}
      </p>
    </div>
  );
}
