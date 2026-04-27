import React from 'react';

export function DataCenterProposalInboxPanel({ clientId }: { clientId?: string | null }) {
  return (
    <div className="mt-5 rounded-3xl border border-slate-100 bg-white p-4">
      <p className="text-[13px] font-bold text-slate-800">数据中心建议队列</p>
      <p className="mt-1 text-[12px] leading-5 text-slate-500">
        {clientId ? '当前客户的建议队列入口已保留。' : '选择客户后可查看待审核建议。'}
      </p>
    </div>
  );
}
