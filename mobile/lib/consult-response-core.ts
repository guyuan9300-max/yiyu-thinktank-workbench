import type { ConsultationChatResponse } from "./types";

export interface ConsultResponseFallbackOptions {
  hasClientName?: boolean;
  hasTaskBoardContext?: boolean;
  hasThreadSnapshot?: boolean;
  hasWorkspaceContext?: boolean;
  forceLimitedContext?: boolean;
  reason?: string | null;
}

const DEFAULT_MISSING_CONTEXT = [
  {
    type: "workspace",
    message: "客户工作台未进入本次咨询上下文。",
  },
  {
    type: "client_dna",
    message: "客户 DNA / 使命 / 核心业务资料未进入本次咨询上下文。",
  },
  {
    type: "meeting",
    message: "最近会议或现场记录未进入本次咨询上下文。",
  },
  {
    type: "strategic_cockpit",
    message: "Strategic Cockpit 判断层未进入本次咨询上下文。",
  },
  {
    type: "knowledge_surrogate",
    message: "知识代理或资料摘要未进入本次咨询上下文。",
  },
] as const;

const CONTEXT_DIAGNOSTIC_LINE_PATTERNS = [
  /^上下文质量[:：]?/,
  /^Bundle\s+v/i,
  /^已加载工作台/,
  /^可按锁定上下文/,
  /^已可用[:：]/,
  /^缺失[:：]/,
  /^依据$/,
  /^依据[:：]/,
  /^[•*-]\s*(客户|客户工作台)[:：]/,
  /^客户工作台[:：]/,
  /^阶段目标[:：]/,
  /^待决策[:：]/,
  /^下一步[:：]/,
  /^健康信号[:：]/,
  /^最近变化[:：]/,
] as const;

function unique(values: readonly string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}

export function stripVisibleContextDiagnostics(text: string): string {
  const lines = text.split(/\r?\n/);
  const firstContentIndex = lines.findIndex((line) => line.trim());
  if (firstContentIndex < 0) return "";

  const firstContentLine = lines[firstContentIndex]?.trim() ?? "";
  const startsWithDiagnostics = CONTEXT_DIAGNOSTIC_LINE_PATTERNS.some((pattern) =>
    pattern.test(firstContentLine),
  );
  if (!startsWithDiagnostics) return text;

  return lines
    .filter((line) => {
      const trimmed = line.trim();
      if (!trimmed) return true;
      return !CONTEXT_DIAGNOSTIC_LINE_PATTERNS.some((pattern) => pattern.test(trimmed));
    })
    .join("\n")
    .replace(/^\s+/, "")
    .replace(/\s+$/, "");
}

export function hasConsultResponseMetadata(response: ConsultationChatResponse): boolean {
  return Boolean(
    response.answerMode ||
      response.contextQuality ||
      (response.evidence && response.evidence.length > 0) ||
      (response.missingContext && response.missingContext.length > 0),
  );
}

export function normalizeConsultationResponseForMobile(
  response: ConsultationChatResponse,
  options: ConsultResponseFallbackOptions = {},
): ConsultationChatResponse {
  const hasMetadata = hasConsultResponseMetadata(response);
  const shouldForceLimited = options.forceLimitedContext || !hasMetadata;
  const visibleReply = stripVisibleContextDiagnostics(response.reply ?? "");

  if (!shouldForceLimited) {
    return {
      ...response,
      reply: visibleReply,
      evidence: response.evidence ?? [],
      missingContext: response.missingContext ?? [],
    };
  }

  const availableSources = unique([
    ...(options.hasClientName ? ["client_name"] : []),
    ...(options.hasTaskBoardContext ? ["task_board"] : []),
    ...(options.hasThreadSnapshot ? ["thread_snapshot"] : []),
    ...(options.hasWorkspaceContext ? ["workspace"] : []),
    ...(response.contextQuality?.availableSources ?? []),
  ]);
  const missingSources = unique([
    ...(options.hasWorkspaceContext ? [] : ["workspace"]),
    "client_dna",
    "meeting",
    "strategic_cockpit",
    "knowledge_surrogate",
    ...(response.contextQuality?.missingSources ?? []),
  ]);
  const missingContext = [
    ...(!hasMetadata
      ? [
          {
            type: "consult_contract",
            message: "当前服务未返回完整咨询信息，手机端已按普通问答继续。",
          },
        ]
      : []),
    ...(options.reason
      ? [
          {
            type: "backend_capability",
            message: options.reason,
          },
        ]
      : []),
    ...DEFAULT_MISSING_CONTEXT.filter((entry) => missingSources.includes(entry.type)),
    ...(response.missingContext ?? []),
  ];

  return {
    ...response,
    reply: visibleReply,
    answerMode:
      response.answerMode === "error" || response.answerMode === "missing_context"
        ? response.answerMode
        : "limited_context",
    contextQuality: {
      level: availableSources.includes("workspace") ? "partial" : "thin",
      availableSources,
      missingSources,
      staleSources: response.contextQuality?.staleSources ?? [],
      contextBundleHash: response.contextQuality?.contextBundleHash ?? null,
    },
    evidence: response.evidence ?? [],
    missingContext,
  };
}
