import React, { useEffect, useState } from 'react';

import { listGlossaryAttributes } from '../../lib/api';

type GlossaryPendingBadgeProps = {
  clientId: string;
  onNavigateToReview?: () => void;
};

/** P-A.2: 工作台顶部徽章 — 显示该客户字典里待审属性数。
 *  - 数 = 0 时返回 null（不显示）
 *  - 数 > 0 时显示黄色徽章，点击跳战略陪伴审核
 *  - 处理完用户审核后会自动减少
 */
export function GlossaryPendingBadge({ clientId, onNavigateToReview }: GlossaryPendingBadgeProps) {
  const [pendingCount, setPendingCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!clientId) {
      setPendingCount(null);
      return;
    }
    listGlossaryAttributes(clientId, 'pending')
      .then((result) => {
        if (cancelled) return;
        setPendingCount(result.attributes.length);
      })
      .catch(() => {
        if (cancelled) return;
        setPendingCount(null);
      });
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  if (!clientId || pendingCount === null || pendingCount === 0) return null;

  return (
    <button
      type="button"
      onClick={onNavigateToReview}
      className="inline-flex items-center gap-1.5 rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 text-[11px] font-bold text-amber-700 hover:bg-amber-100 transition-colors"
      title="点击去战略陪伴审核字典待补全属性"
    >
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500" />
      字典待审 {pendingCount} 条
    </button>
  );
}
