/**
 * v2.2 N2 · 客户故事全景 (FullNarrative) 前端类型
 *
 * 服务: 顾源源 5/22 关键洞察
 *   "AI 把碎片拼成完整故事网, 从任意入口看到全局, 才是 N2 真目标."
 *
 * 数据源: GET /api/v1/clients/{client_id}/full-narrative
 * 后端契约: backend/app/services/narrative_kernel.py · ClientNarrative
 * Endpoint:  backend/app/api/full_narrative_router.py
 *
 * 8 段固定 schema (改这里必须同步 backend SECTION_KEYS):
 *   identity / people / main_lines / recent_changes /
 *   risks / our_collab / open_questions / timeline
 */

export const SECTION_KEYS = [
  'identity',
  'people',
  'main_lines',
  'recent_changes',
  'risks',
  'our_collab',
  'open_questions',
  'timeline',
] as const;

export type SectionKey = (typeof SECTION_KEYS)[number];

export interface StorySection {
  section_key: SectionKey;
  title: string;
  body_markdown: string;
  cited_fact_ids: string[];
  cited_doc_ids: string[];
  confidence: number;
  source_count_by_tier: Record<string, number>;
}

export interface FullNarrative {
  client_id: string;
  client_name: string;
  story_sections: StorySection[];
  generated_at: string;
  generation_session_id: string;
  total_facts_consulted: number;
  facts_excluded_by_tier: number;
  reasoning_trace_id: string | null;
  /** B 层 5 维 acceptance 结果 */
  acceptance_status: 'passed' | 'warning';
  acceptance_notes: string[];
}

export interface FetchFullNarrativeOptions {
  /** 强制刷新 (NarrativeKernel v1 引入 LLM 缓存后生效) */
  forceRefresh?: boolean;
  /** AI agent 自动调用建议带, 防重复 LLM 调用 */
  idempotencyKey?: string;
  /** 触发入口标识 (用于追踪是哪个 view 调的: strategic_clarification / strategic_brain / task_detail) */
  actorId?: string;
}
