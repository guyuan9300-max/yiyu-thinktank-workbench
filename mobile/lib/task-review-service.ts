import * as localDb from "./local-db";
import { completeTaskWithReviewOfflineFirst } from "./sync-engine";
import type { MutationReceipt, TaskRecord } from "./types";

export function saveTaskReview(
  taskId: string,
  reviewNote: string,
): { task: TaskRecord; receipt: MutationReceipt } {
  const receipt = completeTaskWithReviewOfflineFirst(taskId, reviewNote);
  const task = localDb.getTaskById(taskId);
  if (!task) {
    throw new Error("任务不存在，无法保存复盘");
  }
  return {
    task,
    receipt,
  };
}
