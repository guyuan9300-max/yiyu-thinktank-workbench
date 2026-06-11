import type { SmartTaskDraftResponse } from "./types";

export type RecordingTargetType = "task" | "event_line" | "meeting" | "client" | "unbound";
export type RecordingSource = "task_detail" | "record_note" | "smart_input" | "manual" | string;
export type RecordingSessionStatus =
  | "recording"
  | "local_transcribing"
  | "local_saved"
  | "asr_failed"
  | "needs_action";
export type RecordingSyncStatus = "local_only" | "pending" | "syncing" | "synced" | "failed";

export interface RecordingSegmentDraft {
  segmentIndex?: number;
  startMs?: number;
  endMs?: number | null;
  text: string;
  confidence?: number | null;
  isFinal?: boolean;
}

export interface RecordingSegment {
  id: string;
  recordingId: string;
  segmentIndex: number;
  startMs: number;
  endMs: number | null;
  text: string;
  confidence: number | null;
  isFinal: boolean;
  createdAt: string;
}

export interface RecordingSession {
  id: string;
  scopeKey: string;
  source: RecordingSource;
  targetType: RecordingTargetType;
  targetLocalId?: string | null;
  targetRemoteId?: string | null;
  clientId?: string | null;
  eventLineId?: string | null;
  taskId?: string | null;
  meetingId?: string | null;
  audioPath?: string | null;
  durationSeconds?: number | null;
  mimeType?: string | null;
  audioHash?: string | null;
  rawTranscriptPath?: string | null;
  cleanTranscriptPath?: string | null;
  summaryJson?: string | null;
  status: RecordingSessionStatus;
  syncStatus: RecordingSyncStatus;
  lastError?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  placeLabel?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface RecordingPaths {
  directory: string;
  audioPath: string;
  rawTranscriptPath: string;
  cleanTranscriptPath: string;
  summaryPath: string;
}

export interface RecordingTextIngestPayload {
  recordingId: string;
  clientId?: string | null;
  eventLineId?: string | null;
  taskId?: string | null;
  meetingId?: string | null;
  targetType?: RecordingTargetType | null;
  rawTranscript: string;
  cleanTranscript: string;
  summary?: Record<string, unknown> | null;
  segments: Array<{
    segmentIndex: number;
    startMs: number;
    endMs?: number | null;
    text: string;
    confidence?: number | null;
    isFinal: boolean;
  }>;
  recordedAt: string;
  durationSeconds?: number | null;
}

const DEFAULT_SCOPE_PART = "default";

export function sanitizeRecordingScopePart(value: string | null | undefined): string {
  const normalized = (value ?? "").trim().replace(/[^a-zA-Z0-9._-]+/g, "_").replace(/^_+|_+$/g, "");
  return normalized || DEFAULT_SCOPE_PART;
}

function trimTrailingSlash(value: string): string {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

export function buildRecordingDirectory(
  documentDirectory: string,
  scopeKey: string | null | undefined,
  recordingId: string,
): string {
  const root = trimTrailingSlash(documentDirectory || "");
  const scopePart = sanitizeRecordingScopePart(scopeKey);
  const idPart = sanitizeRecordingScopePart(recordingId);
  return `${root}/recordings/${scopePart}/${idPart}`;
}

export function buildRecordingPaths(
  documentDirectory: string,
  scopeKey: string | null | undefined,
  recordingId: string,
): RecordingPaths {
  const directory = buildRecordingDirectory(documentDirectory, scopeKey, recordingId);
  return {
    directory,
    audioPath: `${directory}/audio.m4a`,
    rawTranscriptPath: `${directory}/raw-transcript.txt`,
    cleanTranscriptPath: `${directory}/clean-transcript.txt`,
    summaryPath: `${directory}/summary.json`,
  };
}

export function cleanTranscriptText(rawTranscript: string | null | undefined): string {
  const compact = (rawTranscript ?? "")
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  if (!compact) {
    return "";
  }
  const sentenceBreak = compact
    .replace(/([。！？!?])\s+/g, "$1\n")
    .replace(/([；;])\s+/g, "$1\n")
    .replace(/(然后|接下来|下一步|另外|还有|最后)/g, "\n$1")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  if (/[。！？!?]$/.test(sentenceBreak)) {
    return sentenceBreak;
  }
  return `${sentenceBreak}。`;
}

export function normalizeRecordingSegments(
  segments: RecordingSegmentDraft[] | null | undefined,
  fallbackText: string,
  recordingId: string,
  createdAt: string,
): RecordingSegment[] {
  const normalized = (segments ?? [])
    .map((segment, index) => ({
      id: `${recordingId}-segment-${String(segment.segmentIndex ?? index).padStart(4, "0")}`,
      recordingId,
      segmentIndex: segment.segmentIndex ?? index,
      startMs: Math.max(0, Math.round(segment.startMs ?? 0)),
      endMs: segment.endMs == null ? null : Math.max(0, Math.round(segment.endMs)),
      text: segment.text.trim(),
      confidence: segment.confidence == null ? null : Number(segment.confidence),
      isFinal: segment.isFinal !== false,
      createdAt,
    }))
    .filter((segment) => segment.text.length > 0);

  if (normalized.length > 0) {
    return normalized;
  }

  const trimmedFallback = fallbackText.trim();
  if (!trimmedFallback) {
    return [];
  }
  return [
    {
      id: `${recordingId}-segment-0000`,
      recordingId,
      segmentIndex: 0,
      startMs: 0,
      endMs: null,
      text: trimmedFallback,
      confidence: null,
      isFinal: true,
      createdAt,
    },
  ];
}

export function buildRecordingSummary(input: {
  cleanTranscript: string;
  durationSeconds?: number | null;
  title?: string | null;
  generatedAt?: string | null;
}): Record<string, unknown> {
  const text = input.cleanTranscript.trim();
  const firstLine = text.split(/\n+/).find(Boolean) ?? "";
  return {
    title: input.title?.trim() || firstLine.slice(0, 32) || "录音转写",
    brief: firstLine.slice(0, 160),
    actionItems: [],
    durationSeconds: input.durationSeconds ?? null,
    generatedAt: input.generatedAt ?? new Date().toISOString(),
  };
}

export function buildRecordingTextIngestPayload(input: {
  session: RecordingSession;
  segments: RecordingSegment[];
  rawTranscript: string;
  cleanTranscript: string;
  summary?: Record<string, unknown> | null;
}): RecordingTextIngestPayload {
  return {
    recordingId: input.session.id,
    clientId: input.session.clientId ?? null,
    eventLineId: input.session.eventLineId ?? null,
    taskId: input.session.taskId ?? input.session.targetRemoteId ?? null,
    meetingId: input.session.meetingId ?? null,
    targetType: input.session.targetType,
    rawTranscript: input.rawTranscript,
    cleanTranscript: input.cleanTranscript,
    summary: input.summary ?? null,
    segments: input.segments.map((segment) => ({
      segmentIndex: segment.segmentIndex,
      startMs: segment.startMs,
      endMs: segment.endMs,
      text: segment.text,
      confidence: segment.confidence,
      isFinal: segment.isFinal,
    })),
    recordedAt: input.session.createdAt,
    durationSeconds: input.session.durationSeconds ?? null,
  };
}

function inferDueDate(text: string, referenceDate: string | null | undefined): string | null {
  if (!referenceDate) {
    return null;
  }
  const match = referenceDate.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return null;
  }
  const offset = text.includes("后天") ? 2 : text.includes("明天") ? 1 : text.includes("今天") ? 0 : null;
  if (offset == null) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) {
    return null;
  }
  return addDaysToDateKey(year, month, day, offset);
}

const CHINESE_DIGITS: Record<string, number> = {
  零: 0,
  〇: 0,
  一: 1,
  二: 2,
  两: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 7,
  八: 8,
  九: 9,
};

const SPOKEN_TIME_PATTERN =
  /(?:(凌晨|早上|早晨|上午|中午|下午|傍晚|晚上|今晚)\s*)?([0-2]?\d|[零〇一二两三四五六七八九十]{1,3})\s*(?:(?:[:：]\s*([0-5]\d))|(?:[点时]\s*(半|[零〇一二两三四五六七八九十0-9]{1,3})?\s*分?))/;

const PERIOD_HOUR_PATTERN =
  /(凌晨|早上|早晨|上午|中午|下午|傍晚|晚上|今晚)\s*([0-2]?\d|[零〇一二两三四五六七八九十]{1,3})(?!\d)/;

const PM_PERIODS = new Set(["下午", "傍晚", "晚上", "今晚"]);
const AM_PERIODS = new Set(["凌晨", "早上", "早晨", "上午"]);

function parseSpokenNumber(value: string | null | undefined): number | null {
  const normalized = (value ?? "").trim().replace(/[分号]/g, "");
  if (!normalized) {
    return null;
  }
  if (/^\d+$/.test(normalized)) {
    return Number(normalized);
  }
  if (normalized === "半") {
    return 30;
  }
  const text = normalized.replace(/两/g, "二").replace(/〇/g, "零");
  if (text === "十") {
    return 10;
  }
  const tenIndex = text.indexOf("十");
  if (tenIndex >= 0) {
    const left = text.slice(0, tenIndex);
    const right = text.slice(tenIndex + 1);
    const tens = left ? CHINESE_DIGITS[left] : 1;
    const ones = right ? CHINESE_DIGITS[right] : 0;
    if (tens == null || ones == null) {
      return null;
    }
    return tens * 10 + ones;
  }

  let total = 0;
  for (const char of text) {
    const digit = CHINESE_DIGITS[char];
    if (digit == null) {
      return null;
    }
    total = total * 10 + digit;
  }
  return total;
}

function normalizeHourForPeriod(hour: number, period: string | null | undefined): number | null {
  if (!Number.isInteger(hour) || hour < 0 || hour > 23) {
    return null;
  }
  let normalizedHour = hour;
  if (period && PM_PERIODS.has(period) && normalizedHour < 12) {
    normalizedHour += 12;
  } else if (period === "中午" && normalizedHour < 11) {
    normalizedHour += 12;
  } else if (period && AM_PERIODS.has(period) && normalizedHour === 12) {
    normalizedHour = 0;
  }
  return normalizedHour >= 0 && normalizedHour <= 23 ? normalizedHour : null;
}

function inferDueTime(text: string): string | null {
  const match = text.match(SPOKEN_TIME_PATTERN) ?? text.match(PERIOD_HOUR_PATTERN);
  if (!match) {
    return null;
  }
  const period = match[1] ?? null;
  const hour = normalizeHourForPeriod(parseSpokenNumber(match[2]) ?? -1, period);
  const minute = match[3] ? parseSpokenNumber(match[3]) : match[4] ? parseSpokenNumber(match[4]) : 0;
  if (hour == null || minute == null || minute < 0 || minute > 59) {
    return null;
  }
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function stripTaskCommandWords(text: string): string {
  return text
    .replace(SPOKEN_TIME_PATTERN, " ")
    .replace(PERIOD_HOUR_PATTERN, " ")
    .replace(/[，,。.!！?？]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^(?:今天|明天|后天|上午|下午|晚上|今晚|中午|早上|早晨|傍晚|凌晨)+/g, "")
    .replace(
      /(?:请你|请|帮我|给我|麻烦你|麻烦|记得|提醒我|提醒|安排|设置|设定|新建|创建|添加|建立|一条|一个|任务|日程|待办|事项)/g,
      " ",
    )
    .replace(/\s+/g, "")
    .replace(/^(?:去|要|把|将|再|在)+/g, "")
    .trim();
}

function extractTaskTitle(cleanText: string): string {
  const firstLine = cleanText.split(/\n+/).find(Boolean) ?? cleanText;
  const plain = firstLine.replace(/[。！？!?]+$/g, "").trim();
  if (!plain) {
    return "语音任务";
  }
  const timeMatch = plain.match(SPOKEN_TIME_PATTERN) ?? plain.match(PERIOD_HOUR_PATTERN);
  const afterTime = timeMatch ? plain.slice((timeMatch.index ?? 0) + timeMatch[0].length) : plain;
  const title = stripTaskCommandWords(afterTime) || stripTaskCommandWords(plain) || plain;
  return title.slice(0, 28) || "语音任务";
}

function addDaysToDateKey(year: number, month: number, day: number, offset: number): string | null {
  if (month < 1 || month > 12) {
    return null;
  }
  let nextYear = year;
  let nextMonth = month;
  let nextDay = day + offset;
  if (day < 1 || day > daysInMonth(nextYear, nextMonth)) {
    return null;
  }
  while (nextDay > daysInMonth(nextYear, nextMonth)) {
    nextDay -= daysInMonth(nextYear, nextMonth);
    nextMonth += 1;
    if (nextMonth > 12) {
      nextMonth = 1;
      nextYear += 1;
    }
  }
  while (nextDay < 1) {
    nextMonth -= 1;
    if (nextMonth < 1) {
      nextMonth = 12;
      nextYear -= 1;
    }
    nextDay += daysInMonth(nextYear, nextMonth);
  }
  return `${nextYear}-${String(nextMonth).padStart(2, "0")}-${String(nextDay).padStart(2, "0")}`;
}

function daysInMonth(year: number, month: number): number {
  if (month === 2) {
    const leapYear = year % 400 === 0 || (year % 4 === 0 && year % 100 !== 0);
    return leapYear ? 29 : 28;
  }
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
}

export function buildLocalSmartTaskDraftFromTranscript(
  transcriptText: string,
  referenceDate?: string | null,
): SmartTaskDraftResponse {
  const cleanText = cleanTranscriptText(transcriptText);
  const title = extractTaskTitle(cleanText);
  return {
    transcript: transcriptText.trim(),
    intent: cleanText ? "task_schedule" : "unknown",
    draft: {
      title,
      dueDate: inferDueDate(cleanText, referenceDate),
      dueTime: inferDueTime(cleanText),
      description: cleanText,
      tags: ["录音转写"],
    },
    warnings: cleanText ? [] : ["本地语音识别没有返回文本"],
    confidence: cleanText ? 0.72 : 0,
  };
}
