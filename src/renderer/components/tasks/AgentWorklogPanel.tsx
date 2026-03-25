import type { AgentWeeklyDigest, AgentWorklog } from '../../../shared/types';

type AgentWorklogPanelProps = {
  dailyLogs: AgentWorklog[];
  weeklyDigests: AgentWeeklyDigest[];
};

function sourceLabel(sourceType: AgentWorklog['sourceType']) {
  if (sourceType === 'activity_log') return '内部动作';
  if (sourceType === 'topic_capture') return '情报处理';
  return '系统同步';
}

export function AgentWorklogPanel({ dailyLogs, weeklyDigests }: AgentWorklogPanelProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-[28px] border border-gray-200 bg-gray-50/60 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[13px] font-bold text-gray-900">机器人部门工作日志</p>
            <p className="mt-1 text-[12px] leading-6 text-gray-500">把庆华、大周、佳乐的真实工作痕迹接到日历里，方便 CEO 在日视图里同时看工作内容和周摘要。</p>
          </div>
          <span className="rounded-full bg-white px-3 py-1 text-[10px] font-bold text-gray-500 shadow-sm">
            只读聚合
          </span>
        </div>
      </div>

      {weeklyDigests.length > 0 && (
        <div className="space-y-3">
          <p className="text-[13px] font-bold text-gray-900">本周部门摘要</p>
          {weeklyDigests.map((digest) => (
            <div key={`${digest.agentKey}:${digest.weekLabel}`} className="rounded-[28px] border border-gray-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="h-3 w-3 rounded-full" style={{ backgroundColor: digest.color }} />
                <p className="text-[14px] font-bold text-gray-900">{digest.departmentName}</p>
                <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[10px] font-bold text-gray-500">{digest.agentName}</span>
                <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[10px] font-bold text-gray-500">{digest.evidenceCount} 条日志</span>
              </div>
              <p className="mt-3 text-[13px] leading-6 text-gray-700">{digest.summary}</p>
              {digest.focusItems.length > 0 && (
                <div className="mt-3 space-y-2">
                  {digest.focusItems.map((item) => (
                    <div key={item} className="rounded-2xl bg-slate-50 px-4 py-3 text-[12px] leading-6 text-slate-700">
                      {item}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="space-y-3">
        <p className="text-[13px] font-bold text-gray-900">当日部门日志</p>
        {dailyLogs.length > 0 ? (
          dailyLogs.map((log) => (
            <div key={log.id} className="rounded-[28px] border border-gray-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="h-3 w-3 rounded-full" style={{ backgroundColor: log.color }} />
                <p className="text-[14px] font-bold text-gray-900">{log.departmentName}</p>
                <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[10px] font-bold text-gray-500">{log.agentName}</span>
                <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[10px] font-bold text-gray-500">{sourceLabel(log.sourceType)}</span>
              </div>
              <p className="mt-3 text-[13px] font-bold text-gray-900">{log.title}</p>
              <p className="mt-2 text-[12px] leading-6 text-gray-600">{log.summary}</p>
              {log.detailLines.length > 0 && (
                <div className="mt-3 space-y-2">
                  {log.detailLines.map((item) => (
                    <div key={item} className="rounded-2xl bg-gray-50 px-4 py-2.5 text-[12px] leading-6 text-gray-600">
                      {item}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="rounded-[28px] border border-dashed border-gray-200 bg-gray-50/60 px-6 py-8 text-center text-[12px] leading-6 text-gray-400">
            这一天还没有采集到机器人部门的结构化工作日志。
          </div>
        )}
      </div>
    </div>
  );
}
