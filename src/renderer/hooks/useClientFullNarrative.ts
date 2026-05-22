/**
 * v2.2 N2 · useClientFullNarrative · React hook
 *
 * 服务: V2.2_NORTH_STAR.md 目标 N2 · 顾源源 5/22 关键洞察
 *   "AI 把碎片拼成完整故事网, 从任意入口看到全局, 才是 N2 真目标."
 *
 * 设计 (套 useClientFact 模板):
 *   - 给 3 个入口 view 用 (StrategicClarification / StrategicBrain / 客户工作台 / 任务详情)
 *   - 内部消费 GET /api/v1/clients/{client_id}/full-narrative
 *   - 同一 client_id 在不同 view 调本 hook 拿到一致 8 段故事 (任意入口看全局)
 *   - 竞态保护: clientId 切换后丢弃旧请求 (套 useClientFact 同样实现)
 *
 * 用法:
 *   function StrategicClarificationView({ clientId }: { clientId: string }) {
 *     const { narrative, isLoading, error, refresh } = useClientFullNarrative({
 *       clientId,
 *       actorId: 'view_strategic_clarification',
 *     });
 *     if (isLoading) return <Loading />;
 *     if (error) return <Error error={error} />;
 *     return <FullNarrativeSection narrative={narrative} />;
 *   }
 */
import { useCallback, useEffect, useRef, useState } from 'react';

import { fetchClientFullNarrative } from '../lib/api';
import type {
  FetchFullNarrativeOptions,
  FullNarrative,
} from '../lib/fullNarrativeTypes';

export interface UseClientFullNarrativeOptions extends FetchFullNarrativeOptions {
  /** 客户 id. null/空 时 hook 不发请求 (narrative 为 null) */
  clientId: string | null | undefined;
  /** 是否自动随 clientId 变化重新拉. 默认 true */
  autoFetch?: boolean;
}

export interface ClientFullNarrativeState {
  narrative: FullNarrative | null;
  isLoading: boolean;
  error: Error | null;
  /** 手动重新拉. Promise 在拉取完成后 resolve. */
  refresh: () => Promise<void>;
}

export function useClientFullNarrative(
  options: UseClientFullNarrativeOptions,
): ClientFullNarrativeState {
  const { clientId, autoFetch = true, forceRefresh, idempotencyKey, actorId } = options;

  const [narrative, setNarrative] = useState<FullNarrative | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const latestClientIdRef = useRef<string | null | undefined>(clientId);

  const doFetch = useCallback(async (): Promise<void> => {
    if (!clientId) {
      setNarrative(null);
      setIsLoading(false);
      setError(null);
      return;
    }
    const requestedClientId = clientId;
    latestClientIdRef.current = requestedClientId;
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchClientFullNarrative(requestedClientId, {
        forceRefresh,
        idempotencyKey,
        actorId,
      });
      if (latestClientIdRef.current !== requestedClientId) return;
      setNarrative(result);
    } catch (err) {
      if (latestClientIdRef.current !== requestedClientId) return;
      setError(err instanceof Error ? err : new Error(String(err)));
      setNarrative(null);
    } finally {
      if (latestClientIdRef.current === requestedClientId) {
        setIsLoading(false);
      }
    }
  }, [clientId, forceRefresh, idempotencyKey, actorId]);

  useEffect(() => {
    if (autoFetch) {
      void doFetch();
    }
    return () => {
      latestClientIdRef.current = null;
    };
  }, [doFetch, autoFetch]);

  return {
    narrative,
    isLoading,
    error,
    refresh: doFetch,
  };
}
