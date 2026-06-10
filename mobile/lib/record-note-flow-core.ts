export type RecordNoteProgressState =
  | "任务已保存"
  | "录音待挂接"
  | "录音待同步"
  | "正在恢复暂存语音"
  | "录音需处理"
  | "完成";

const ALLOWED_TRANSITIONS: Record<RecordNoteProgressState, readonly RecordNoteProgressState[]> = {
  任务已保存: ["录音待挂接"],
  录音待挂接: ["录音待同步", "录音需处理"],
  录音待同步: ["完成", "录音需处理"],
  正在恢复暂存语音: ["录音待挂接", "录音需处理"],
  录音需处理: [],
  完成: [],
};

export function canTransitionRecordNoteProgress(
  from: RecordNoteProgressState,
  to: RecordNoteProgressState,
): boolean {
  return ALLOWED_TRANSITIONS[from].includes(to);
}

export function getAllowedRecordNoteTransitions(
  from: RecordNoteProgressState,
): readonly RecordNoteProgressState[] {
  return ALLOWED_TRANSITIONS[from];
}
