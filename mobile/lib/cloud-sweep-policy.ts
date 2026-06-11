/**
 * cloud-sweep-policy.ts — 全量拉取(mark-and-sweep)后的删除护栏决策（纯函数，便于测试）
 *
 * 背景:`upsertTasksFromCloud` 采用 server-wins 全量协调模型——把本地已同步任务先标记为
 * "可能已删除"，云端 board 返回的任务复活，最后删掉云端缺席的。这个模型对"云端返回完整"
 * 这一前提高度敏感:一次后端异常响应（空数组 / 鉴权过滤 / 部署抖动 / 分页截断）就可能让
 * 本地任务被误删。下面两个判定给出最小、无误伤的客户端护栏。
 */

/**
 * 空响应护栏:本地有已同步任务、但云端返回 0 条——几乎一定是后端异常，而非用户真的删光
 * 所有任务（真删走逐条 delete op）。此时应跳过删除阶段，避免一次坏响应清空本地。
 */
export function shouldSkipCloudTaskSweep(
  localSyncedCount: number,
  cloudTaskCount: number,
): boolean {
  return localSyncedCount > 0 && cloudTaskCount === 0;
}

/**
 * 异常缩量诊断:客户端无法区分"云端少返回一半"与"用户真删一半"，根治需后端提供显式
 * deletedIds 增量。这里不擅自跳过（避免误伤真实批量删除），仅在单轮删除占比异常高
 * （>5 条且 ≥ 本地半数）时返回 true 以便留痕告警。
 */
export function shouldWarnLargeSweep(deleteCount: number, localSyncedCount: number): boolean {
  return deleteCount > 5 && localSyncedCount > 0 && deleteCount >= localSyncedCount * 0.5;
}
