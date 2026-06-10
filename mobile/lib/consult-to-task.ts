/**
 * consult-to-task —— consult tab 把 AI 答案"加为任务"时的临时 draft 传递。
 *
 * 为什么这样做：
 * - CreateTask 组件已经支持通过 SmartTaskDraft 预填 title/description/clientId/eventLineId
 * - tasks.tsx 通过 `?modal=create` 路由参数唤起 CreateTask
 * - 跨 tab 传 draft 用 router params 太丑（URL 容量有限 + encoding 麻烦）
 * - 用一个 module-level mutable ref 中转：consult set，tasks take（取出即清）
 */

import type { SmartTaskDraft } from "./types";

let pendingDraft: SmartTaskDraft | null = null;

/** consult tab 在 AI 答案"加为任务"时调用 */
export function setPendingConsultDraft(draft: SmartTaskDraft): void {
  pendingDraft = draft;
}

/** tasks tab 在 `?modal=create&from=consult` 时调用 —— 取出后立即清掉 */
export function takePendingConsultDraft(): SmartTaskDraft | null {
  const draft = pendingDraft;
  pendingDraft = null;
  return draft;
}
