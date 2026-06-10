import { getLegacyUploadPseudoOps } from "./legacy-upload-ops";
import {
  processQueuedLegacyUploadOps,
  type LegacyUploadAutoProcessResult,
} from "./legacy-upload-runner-core";

export async function processQueuedLegacyUploadPseudoOps(): Promise<LegacyUploadAutoProcessResult> {
  const { retryLegacyUploadPseudoOp } = await import("./record-note-service");
  return processQueuedLegacyUploadOps(getLegacyUploadPseudoOps(), retryLegacyUploadPseudoOp);
}
