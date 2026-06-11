import type {
  EventLineRecord,
  TaskContextPreviewRecord,
  TaskRecord,
  TaskUnderstandingRecord,
} from "./types";

export type TaskUnderstandingStatus = "ready" | "insufficient_context" | "weak_link";

export interface TaskUnderstandingSections {
  status: TaskUnderstandingStatus;
  whatIsThis: string;
  whyItMatters: string;
  blockerAndDecision: string;
  nextStepAndUnknowns: string;
}

export interface TaskUnderstandingCardSection {
  title: string;
  content: string;
}

export interface TaskUnderstandingCardModel {
  stateLabel: string;
  title: string;
  subtitle: string;
  sections: TaskUnderstandingCardSection[];
  evidence: string[];
  tone: TaskUnderstandingStatus;
}

const STRONG_UNDERSTANDING_SOURCES = new Set([
  "client_background",
  "quarterly_focus",
  "review_note",
  "event_line_memory",
  "meeting",
  "support_request",
  "knowledge_base",
  "org_dna",
]);

const WEAK_EVENT_LINE_HINT_PREFIX = "事件线 · ";
const SOURCE_LABELS: Record<string, string> = {
  client_background: "客户背景",
  quarterly_focus: "阶段目标",
  review_note: "复盘结论",
  event_line_memory: "事件线记录",
  meeting: "会议记录",
  support_request: "支持请求",
  knowledge_base: "知识库",
  org_dna: "组织判断",
  task_title: "任务标题",
  task_desc: "任务描述",
};

function normalizeText(value: string | null | undefined): string {
  return (value ?? "")
    .toLowerCase()
    .replace(/[「」『』【】（）()《》〈〉〔〕“”‘’"'`]/g, "")
    .replace(/[\s,.;:!?，。！？：；、·\-_—/\\|]/g, "");
}

function looksLikeSameContent(candidate: string | null | undefined, references: Array<string | null | undefined>): boolean {
  const normalizedCandidate = normalizeText(candidate);
  if (!normalizedCandidate) {
    return false;
  }
  return references.some((reference) => {
    const normalizedReference = normalizeText(reference);
    if (!normalizedReference || normalizedReference.length < 4) {
      return false;
    }
    return normalizedCandidate === normalizedReference
      || normalizedCandidate.includes(normalizedReference)
      || normalizedReference.includes(normalizedCandidate);
  });
}

function isGenericWhatIsThis(candidate: string | null | undefined, task: TaskRecord): boolean {
  const value = candidate?.trim();
  if (!value) {
    return true;
  }
  if (looksLikeSameContent(value, [task.title, task.description])) {
    return true;
  }
  return value.includes("是一条")
    && (value.includes("工作任务") || value.includes("状态的任务"));
}

function isGenericWhyItMatters(candidate: string | null | undefined): boolean {
  const value = candidate?.trim();
  if (!value) {
    return true;
  }
  return value.startsWith("这条任务与客户")
    || value.startsWith("当前尚未录入客户背景信息")
    || value === "暂无理解摘要";
}

function isGenericProgress(candidate: string | null | undefined): boolean {
  const value = candidate?.trim();
  if (!value) {
    return true;
  }
  return value.startsWith("当前状态为 ");
}

function collectAvailableSources(understanding: TaskUnderstandingRecord | null): Set<string> {
  return new Set(
    (understanding?.sourceBreakdown ?? [])
      .filter((item) => item?.available && item.sourceType)
      .map((item) => item.sourceType as string),
  );
}

function hasStrongEvidence(understanding: TaskUnderstandingRecord | null): boolean {
  if (!understanding || understanding._pending) {
    return false;
  }
  const sourceTypes = collectAvailableSources(understanding);
  const hasStrongSource = [...sourceTypes].some((sourceType) => STRONG_UNDERSTANDING_SOURCES.has(sourceType));
  return hasStrongSource || understanding.coverage >= 55 || understanding.confidence >= 45;
}

function hasWeakEventLineLink(
  task: TaskRecord,
  eventLine: EventLineRecord | null,
  contextPreview: TaskContextPreviewRecord | null,
): boolean {
  if (task.eventLineId || eventLine?.id) {
    return true;
  }
  return (contextPreview?.summaryChips ?? []).some((chip) => chip.startsWith(WEAK_EVENT_LINE_HINT_PREFIX));
}

function inferMissingContext(
  task: TaskRecord,
  eventLine: EventLineRecord | null,
  contextPreview: TaskContextPreviewRecord | null,
): string[] {
  const items: string[] = [];
  const title = task.title ?? "";

  if (!task.description?.trim()) {
    if (/(吃饭|沟通|电话|见面|拜访|约|会面)/.test(title)) {
      items.push("对象身份");
      items.push("见面或沟通目的");
    } else {
      items.push("任务目的");
    }
  }

  if (!(task.clientId || contextPreview?.clientId)) {
    items.push("关联客户");
  }

  if (!(task.eventLineId || eventLine?.id)) {
    items.push("关联事件线");
  }

  if (!task.currentBlocker?.trim() && !task.recentDecision?.trim()) {
    items.push("最近变化或关键卡点");
  }

  if (task.progressStatus === "done") {
    if (!task.completionNote?.trim()) {
      items.push("完成结果或复盘结论");
    }
  } else if (!task.nextAction?.trim()) {
    items.push("下一步动作");
  }

  return [...new Set(items)];
}

function formatMissingContext(items: string[]): string {
  return items.length > 0
    ? `当前缺少：${items.join("、")}。`
    : "当前还缺少能支持任务级判断的上下文。";
}

function formatMissingSuggestion(items: string[]): string {
  return items.length > 0
    ? `建议补充：${items.join("、")}。`
    : "建议先补充任务目的、关联对象或最近变化。";
}

function buildReadySections(
  task: TaskRecord,
  understanding: TaskUnderstandingRecord | null,
): TaskUnderstandingSections {
  const whatIsThis = isGenericWhatIsThis(understanding?.whatIsThis, task)
    ? "暂无可靠洞察"
    : understanding?.whatIsThis?.trim() || "暂无可靠洞察";

  const whyItMatters = isGenericWhyItMatters(understanding?.whyItMatters)
    ? "当前还没有足够证据说明这件事为什么在现在重要。"
    : understanding?.whyItMatters?.trim() || "当前还没有足够证据说明这件事为什么在现在重要。";

  const blockerAndDecision = [
    isGenericProgress(understanding?.progressNow) ? null : understanding?.progressNow?.trim(),
    task.currentBlocker ? `卡点：${task.currentBlocker}` : null,
    task.recentDecision ? `判断：${task.recentDecision}` : null,
    understanding?.optionalAdvice?.realBlocker ? `真实阻碍：${understanding.optionalAdvice.realBlocker}` : null,
  ].filter(Boolean).join("\n") || "当前还没有足够证据说明最近的卡点或判断。";

  const nextStepAndUnknowns = [
    task.nextAction ? `下一步：${task.nextAction}` : null,
    understanding?.optionalAdvice?.minimumAction ? `最小动作：${understanding.optionalAdvice.minimumAction}` : null,
    understanding?.unknowns?.trim() ? `待补：${understanding.unknowns.trim()}` : null,
  ].filter(Boolean).join("\n") || "当前还没有足够证据给出下一步建议。";

  return {
    status: "ready",
    whatIsThis,
    whyItMatters,
    blockerAndDecision,
    nextStepAndUnknowns,
  };
}

function buildWeakLinkSections(
  task: TaskRecord,
  eventLine: EventLineRecord | null,
  contextPreview: TaskContextPreviewRecord | null,
): TaskUnderstandingSections {
  const missing = inferMissingContext(task, eventLine, contextPreview);
  const lineName = eventLine?.name ?? task.eventLineName ?? "当前事件线";
  const chips = (contextPreview?.summaryChips ?? []).filter(Boolean);
  const weakContext = [
    eventLine?.recentDecision ? `最近变化：${eventLine.recentDecision}` : null,
    eventLine?.currentBlocker ? `事件线卡点：${eventLine.currentBlocker}` : null,
    chips.length > 0 ? `已知线索：${chips.join(" · ")}` : null,
  ].filter(Boolean).join("\n");

  return {
    status: "weak_link",
    whatIsThis: `这条任务已关联「${lineName}」，但当前只有宽泛事件线线索，暂时还不能直接判断它的具体意义。`,
    whyItMatters: "目前只看到了事件线级上下文，尚未找到与这条任务直接相关的会议、历史记录或明确目的。",
    blockerAndDecision: weakContext || formatMissingContext(missing),
    nextStepAndUnknowns: formatMissingSuggestion(missing),
  };
}

function buildInsufficientSections(
  task: TaskRecord,
  eventLine: EventLineRecord | null,
  contextPreview: TaskContextPreviewRecord | null,
): TaskUnderstandingSections {
  const missing = inferMissingContext(task, eventLine, contextPreview);
  return {
    status: "insufficient_context",
    whatIsThis: "暂无可靠洞察",
    whyItMatters: "当前只看到任务本身，尚未找到关联客户、事件线、会议记录或历史判断。",
    blockerAndDecision: formatMissingContext(missing),
    nextStepAndUnknowns: formatMissingSuggestion(missing),
  };
}

export function buildTaskUnderstandingSections(params: {
  readonly task: TaskRecord;
  readonly eventLine?: EventLineRecord | null;
  readonly understanding?: TaskUnderstandingRecord | null;
  readonly contextPreview?: TaskContextPreviewRecord | null;
}): TaskUnderstandingSections {
  const { task, eventLine = null, understanding = null, contextPreview = null } = params;

  const strongEvidence = hasStrongEvidence(understanding);
  const needsInput = contextPreview?.safeOutputMode === "needs_input" || contextPreview?.readiness === "low";
  const hasReadyUnderstanding = strongEvidence
    && !needsInput
    && !isGenericWhatIsThis(understanding?.whatIsThis, task)
    && !isGenericWhyItMatters(understanding?.whyItMatters);

  if (hasReadyUnderstanding) {
    return buildReadySections(task, understanding);
  }

  if (hasWeakEventLineLink(task, eventLine, contextPreview)) {
    return buildWeakLinkSections(task, eventLine, contextPreview);
  }

  return buildInsufficientSections(task, eventLine, contextPreview);
}

function dedupeNonEmpty(items: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const values: string[] = [];
  for (const rawItem of items) {
    const item = rawItem?.trim();
    if (!item) {
      continue;
    }
    if (seen.has(item)) {
      continue;
    }
    seen.add(item);
    values.push(item);
  }
  return values;
}

function buildUnderstandingEvidence(params: {
  readonly task: TaskRecord;
  readonly eventLine?: EventLineRecord | null;
  readonly understanding?: TaskUnderstandingRecord | null;
  readonly contextPreview?: TaskContextPreviewRecord | null;
}): string[] {
  const { task, eventLine = null, understanding = null, contextPreview = null } = params;
  const sourceEvidence = (understanding?.sourceBreakdown ?? [])
    .filter((item) => item?.available)
    .map((item) => item?.label?.trim() || item?.sourceName?.trim() || SOURCE_LABELS[item?.sourceType ?? ""] || null);
  const chipEvidence = (contextPreview?.summaryChips ?? [])
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 3);
  return dedupeNonEmpty([
    ...sourceEvidence,
    ...chipEvidence,
    eventLine?.name ? `事件线：${eventLine.name}` : task.eventLineName ? `事件线：${task.eventLineName}` : null,
    contextPreview?.clientName ? `客户：${contextPreview.clientName}` : task.clientName ? `客户：${task.clientName}` : null,
  ]).slice(0, 4);
}

export function buildTaskUnderstandingCardModel(params: {
  readonly task: TaskRecord;
  readonly eventLine?: EventLineRecord | null;
  readonly understanding?: TaskUnderstandingRecord | null;
  readonly contextPreview?: TaskContextPreviewRecord | null;
}): TaskUnderstandingCardModel {
  const sections = buildTaskUnderstandingSections(params);
  const evidence = buildUnderstandingEvidence(params);

  if (sections.status === "ready") {
    return {
      stateLabel: "已整理",
      title: "任务洞察",
      subtitle: "基于现有信息整理出的当前判断",
      tone: "ready",
      sections: [
        { title: "当前判断", content: sections.whatIsThis },
        { title: "为什么现在重要", content: sections.whyItMatters },
        { title: "当前卡点 / 提醒", content: sections.blockerAndDecision },
        { title: "建议下一步", content: sections.nextStepAndUnknowns },
      ],
      evidence,
    };
  }

  if (sections.status === "weak_link") {
    return {
      stateLabel: "线索提醒",
      title: "任务洞察",
      subtitle: "结合当前线索整理出的提醒",
      tone: "weak_link",
      sections: [
        { title: "当前提醒", content: sections.whatIsThis },
        { title: "你可能需要回忆", content: sections.whyItMatters },
        { title: "已知线索", content: sections.blockerAndDecision },
        { title: "建议下一步", content: sections.nextStepAndUnknowns },
      ],
      evidence,
    };
  }

  return {
    stateLabel: "待补信息",
    title: "任务洞察",
    subtitle: "请补充任务信息后再继续推进",
    tone: "insufficient_context",
    sections: [
      { title: "当前提醒", content: sections.whatIsThis },
      { title: "需要确认", content: sections.whyItMatters },
      { title: "待确认信息", content: sections.blockerAndDecision },
      { title: "建议动作", content: sections.nextStepAndUnknowns },
    ],
    evidence,
  };
}
