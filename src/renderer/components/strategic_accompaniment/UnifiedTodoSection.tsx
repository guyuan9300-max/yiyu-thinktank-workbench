/**
 * 统一待办 — 跨 tasks/action_items/commitments union
 *
 * 设计: 参考周复盘风格 (rounded-3xl + 渐变 header + 单行布局), 无 emoji, 用 icon + chip
 */
import { useCallback, useEffect, useState } from 'react';
import { Loader2, ArrowRight, Trash2, Check } from 'lucide-react';
import {
  getUnifiedTodos,
  promoteTodoToTask,
  dismissUnifiedTodo,
  type UnifiedTodo,
  type UnifiedTodosResponse,
} from '../../lib/api';

interface UnifiedTodoSectionProps {
  clientId: string;
  flash?: (kind: 'success' | 'error', message: string) => void;
}

const SOURCE_LABEL: Record<UnifiedTodo['source'], { label: string; cls: string }> = {
  task:           { label: '任务',     cls: 'bg-blue-50 text-blue-700' },
  meeting_action: { label: '会议待办', cls: 'bg-purple-50 text-purple-700' },
  commitment:     { label: '承诺',     cls: 'bg-emerald-50 text-emerald-700' },
};

const SEVERITY_LABEL: Record<UnifiedTodo['severity'], { label: string; cls: string }> = {
  high:   { label: '紧急', cls: 'bg-rose-50 text-rose-700' },
  medium: { label: '关注', cls: 'bg-amber-50 text-amber-700' },
  low:    { label: '常规', cls: 'bg-gray-50 text-gray-600' },
};

export function UnifiedTodoSection({ clientId, flash }: UnifiedTodoSectionProps) {
  const [data, setData] = useState<UnifiedTodosResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [acting, setActing] = useState<Set<string>>(new Set());

  const load = useCallback(() => {
    if (!clientId) return;
    setLoading(true);
    void getUnifiedTodos(clientId)
      .then(setData)
      .catch((err) => {
        flash?.('error', `待办加载失败: ${err instanceof Error ? err.message : String(err)}`);
      })
      .finally(() => setLoading(false));
  }, [clientId, flash]);

  useEffect(() => {
    load();
  }, [load]);

  const setActingFor = (id: string, on: boolean) => {
    setActing((s) => {
      const ns = new Set(s);
      if (on) ns.add(id); else ns.delete(id);
      return ns;
    });
  };

  const handlePromote = async (todo: UnifiedTodo) => {
    if (todo.source === 'task') {
      flash?.('success', '已经是任务, 可在任务页查看');
      return;
    }
    setActingFor(todo.id, true);
    try {
      await promoteTodoToTask(clientId, todo.id);
      flash?.('success', '已建为任务, 同步到日历');
      load();
    } catch (err) {
      flash?.('error', `建立任务失败: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setActingFor(todo.id, false);
    }
  };

  const handleDismiss = async (todo: UnifiedTodo, action: 'complete' | 'cancel') => {
    setActingFor(todo.id, true);
    try {
      await dismissUnifiedTodo(clientId, todo.id, action);
      flash?.('success', action === 'complete' ? '已标记完成' : '已从列表移除');
      load();
    } catch (err) {
      flash?.('error', `操作失败: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setActingFor(todo.id, false);
    }
  };

  return (
    <section className="bg-white border border-gray-200 rounded-3xl shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 bg-[linear-gradient(135deg,rgba(248,250,252,0.95),rgba(255,255,255,1))]">
        <div className="flex items-baseline justify-between gap-3 flex-wrap">
          <div>
            <h3 className="text-[15px] font-bold text-gray-900">下一步要做什么</h3>
            <p className="mt-0.5 text-[11px] text-gray-500">
              跨任务、会议、承诺 union, 按紧急度排
            </p>
          </div>
          {data && (
            <div className="flex items-center gap-1.5 text-[10px]">
              <span className="rounded-full bg-gray-100 text-gray-600 px-2 py-0.5">
                共 {data.total}
              </span>
              {data.by_severity.high > 0 && (
                <span className="rounded-full bg-rose-50 text-rose-700 px-2 py-0.5 font-bold">
                  紧急 {data.by_severity.high}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {loading && (
        <div className="px-5 py-6 text-[12px] text-gray-500 flex items-center gap-2">
          <Loader2 size={13} className="animate-spin" />
          加载中
        </div>
      )}

      {!loading && (!data || data.total === 0) && (
        <div className="px-5 py-6 text-[12px] text-gray-400">当前没有待办</div>
      )}

      {!loading && data && data.total > 0 && (
        <ul className="divide-y divide-gray-100">
          {data.todos.slice(0, 12).map((t) => {
            const src = SOURCE_LABEL[t.source];
            const sev = SEVERITY_LABEL[t.severity];
            const inAction = acting.has(t.id);
            const showDirection = t.direction && t.direction !== '内部';
            const metaParts = [
              t.owner,
              t.due_date,
              showDirection ? t.direction : null,
            ].filter(Boolean);
            return (
              <li
                key={t.id}
                className="px-5 py-3 hover:bg-gray-50/60"
              >
                {/* 顶部一行: 左 = chip+紧急 / 右 = 3 个操作 icon */}
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold ${src.cls}`}>
                      {src.label}
                    </span>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${sev.cls}`}>
                      {sev.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-0.5 shrink-0">
                    <button
                      type="button"
                      onClick={() => handleDismiss(t, 'complete')}
                      disabled={inAction}
                      className="w-7 h-7 rounded-full text-gray-400 hover:text-emerald-600 hover:bg-emerald-50 inline-flex items-center justify-center transition disabled:opacity-50"
                      title="标记已完成"
                    >
                      {inAction ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDismiss(t, 'cancel')}
                      disabled={inAction}
                      className="w-7 h-7 rounded-full text-gray-400 hover:text-rose-600 hover:bg-rose-50 inline-flex items-center justify-center transition disabled:opacity-50"
                      title="删除 (不再追踪)"
                    >
                      <Trash2 size={13} />
                    </button>
                    <button
                      type="button"
                      onClick={() => handlePromote(t)}
                      disabled={inAction}
                      className="w-7 h-7 rounded-full text-gray-400 hover:text-blue-600 hover:bg-blue-50 inline-flex items-center justify-center transition disabled:opacity-50"
                      title={t.source === 'task' ? '已是任务, 查看详情' : '转为任务, 同步日历'}
                    >
                      <ArrowRight size={13} />
                    </button>
                  </div>
                </div>

                {/* 主体: 标题 (允许 2 行, 占最大空间) */}
                <div
                  className="text-[13px] text-gray-800 leading-relaxed line-clamp-2"
                  title={t.title}
                >
                  {t.title}
                </div>

                {/* 底部: meta (owner · 日期 · 方向) */}
                {metaParts.length > 0 && (
                  <div className="mt-1.5 flex items-center gap-2 text-[11px] text-gray-500 flex-wrap">
                    {metaParts.map((m, i) => (
                      <span key={i} className="inline-flex items-center gap-2">
                        {i > 0 && <span className="text-gray-300">·</span>}
                        <span>{m}</span>
                      </span>
                    ))}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {!loading && data && data.total > 12 && (
        <div className="px-5 py-2 border-t border-gray-100 text-center text-[10px] text-gray-400">
          还有 {data.total - 12} 条 (已按紧急度排序, 显示前 12)
        </div>
      )}
    </section>
  );
}
