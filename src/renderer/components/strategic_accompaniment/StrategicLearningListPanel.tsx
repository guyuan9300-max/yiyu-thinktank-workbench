import React from 'react';

import type { GrowthContextLink, Task } from '../../../shared/types';

export type StrategicLearningTaskPayload = {
  title: string;
  description?: string;
  clientId?: string | null;
  dueDate?: string;
  sourceType?: string;
  sourceId?: string | null;
};

type StrategicLearningListPanelProps = {
  currentClientId?: string | null;
  currentClientName?: string | null;
  clients?: Array<{ id: string; name: string }>;
  tasks?: Task[];
  onTasksReload?: () => Promise<unknown> | void;
  onNavigate?: (tab: string) => void;
  onOpenContext?: (context: GrowthContextLink) => void;
  onCreateTaskFromLearning?: (payload: StrategicLearningTaskPayload) => Promise<void> | void;
  flash?: (level: 'success' | 'error' | 'info', message: string) => void;
};

export function StrategicLearningListPanel({
  currentClientName,
  tasks = [],
  onCreateTaskFromLearning,
  flash,
}: StrategicLearningListPanelProps) {
  const recentTasks = tasks.slice(0, 5);
  return (
    <div className="rounded-3xl border border-slate-100 bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[14px] font-bold text-slate-900">学习清单</p>
          <p className="mt-1 text-[12px] leading-5 text-slate-500">
            {currentClientName ? `${currentClientName} 的学习事项入口已保留。` : '战略陪伴学习事项入口已保留。'}
          </p>
        </div>
        {onCreateTaskFromLearning && (
          <button
            type="button"
            className="rounded-full bg-[#5B7BFE] px-4 py-2 text-[12px] font-bold text-white"
            onClick={() => {
              void onCreateTaskFromLearning({
                title: '补充战略陪伴学习事项',
                description: '由战略陪伴学习清单创建。',
                sourceType: 'strategic_learning',
              });
              flash?.('success', '已创建学习事项');
            }}
          >
            新建事项
          </button>
        )}
      </div>
      {recentTasks.length > 0 && (
        <div className="mt-4 space-y-2">
          {recentTasks.map((task) => (
            <div key={task.id} className="rounded-2xl bg-slate-50 px-4 py-3">
              <p className="text-[13px] font-bold text-slate-800">{task.title}</p>
              <p className="mt-1 text-[11px] text-slate-500">{task.ddl || task.dueDate || '待确认'}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
