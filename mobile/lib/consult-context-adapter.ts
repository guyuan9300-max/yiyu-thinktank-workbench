import { buildTaskContextSummary } from "./consult-context";
import type { ConsultContextOption } from "./consult-context";
import { isTaskOverdue } from "./task-time";
import type {
  ClientUnderstandingSnapshot,
  ClientWorkspaceLiteSnapshot,
  CurrentFocus,
  EventLineRecord,
  TaskRecord,
  WorkspaceLiteItem,
} from "./types";

export interface ConsultRequestContext {
  clientId: string | null;
  clientName: string | null;
  eventLineId: string | null;
  eventLineName: string | null;
  taskId: string | null;
  taskTitle: string | null;
  taskContext: string | null;
  workspaceContext: string | null;
  eventLineContext: string | null;
  taskBoardContext: string | null;
  understandingContext: string | null;
  sourceLabels: string[];
  missingEventLineHint: string | null;
}

function compactText(value: string | null | undefined, maxLength = 180): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.replace(/\s+/g, " ").trim();
  if (!trimmed) {
    return null;
  }
  if (trimmed.length <= maxLength) {
    return trimmed;
  }
  return `${trimmed.slice(0, maxLength - 1)}...`;
}

function collectItemSummaries(
  items: readonly WorkspaceLiteItem[] | null | undefined,
  limit = 3,
): string[] {
  if (!items?.length) {
    return [];
  }
  return items
    .map((item) => {
      const title = compactText(item.title, 60);
      const summary = compactText(item.summary ?? null, 90);
      const subtitle = compactText(item.subtitle ?? null, 50);
      if (title && summary) {
        return `${title}：${summary}`;
      }
      if (title && subtitle) {
        return `${title}（${subtitle}）`;
      }
      return title ?? summary ?? subtitle ?? null;
    })
    .filter((item): item is string => Boolean(item))
    .slice(0, limit);
}

function collectTextSummaries(
  items: readonly string[] | null | undefined,
  limit = 3,
  maxLength = 90,
): string[] {
  if (!items?.length) {
    return [];
  }
  return items
    .map((item) => compactText(item, maxLength))
    .filter((item): item is string => Boolean(item))
    .slice(0, limit);
}

function pushSummaryLine(
  lines: string[],
  label: string,
  values: readonly string[],
): void {
  if (values.length === 0) {
    return;
  }
  lines.push(`${label}：${values.join("；")}`);
}

function buildWorkspaceContext(snapshot?: ClientWorkspaceLiteSnapshot | null): string | null {
  if (!snapshot) {
    return null;
  }
  const lines: string[] = [];
  const headline = compactText(snapshot.headline ?? null, 140);
  if (headline) {
    lines.push(`客户工作台：${headline}`);
  }
  pushSummaryLine(lines, "阶段目标", collectItemSummaries(snapshot.goals));
  pushSummaryLine(lines, "最近会议", collectItemSummaries(snapshot.latestMeetings, 2));
  pushSummaryLine(lines, "开放问题", collectItemSummaries(snapshot.openQuestions));
  pushSummaryLine(lines, "待决策", collectTextSummaries(snapshot.pendingDecisions));
  pushSummaryLine(lines, "下一步", collectTextSummaries(snapshot.nextActions));
  pushSummaryLine(lines, "健康信号", collectTextSummaries(snapshot.health, 2));
  pushSummaryLine(lines, "最近变化", collectTextSummaries(snapshot.twoWeekChanges, 2));
  pushSummaryLine(lines, "待补材料", collectTextSummaries(snapshot.pendingMaterials, 2));
  pushSummaryLine(lines, "最近资料", collectItemSummaries(snapshot.recentDocuments, 2));
  const boundaryCards = snapshot.boundaryCards
    .filter((item) => !item.isEmpty)
    .map((item) => compactText(`${item.title}：${item.summary}`, 110))
    .filter((item): item is string => Boolean(item))
    .slice(0, 2);
  pushSummaryLine(lines, "边界提醒", boundaryCards);
  return lines.length > 0 ? lines.join("\n") : null;
}

function buildEventLineContext(eventLine?: EventLineRecord | null): string | null {
  if (!eventLine) {
    return null;
  }
  const lines: string[] = [];
  const name = compactText(eventLine.name, 80);
  if (name) {
    lines.push(`事件线：${name}`);
  }
  const stage = compactText(eventLine.stage ?? null, 60);
  if (stage) {
    lines.push(`阶段：${stage}`);
  }
  const summary = compactText(eventLine.summary ?? null, 180);
  if (summary) {
    lines.push(`事件线摘要：${summary}`);
  }
  const blocker = compactText(eventLine.currentBlocker ?? null, 120);
  if (blocker) {
    lines.push(`当前卡点：${blocker}`);
  }
  const recentDecision = compactText(eventLine.recentDecision ?? null, 120);
  if (recentDecision) {
    lines.push(`最近判断：${recentDecision}`);
  }
  const nextStep = compactText(eventLine.nextStep ?? null, 120);
  if (nextStep) {
    lines.push(`下一步：${nextStep}`);
  }
  return lines.length > 0 ? lines.join("\n") : null;
}

function buildFocusedTaskContext(
  task: TaskRecord | null,
  weekLabel: string | null | undefined,
  fallbackTitle?: string | null,
): string | null {
  if (!task && !weekLabel && !fallbackTitle) {
    return null;
  }
  const lines: string[] = [];
  const title = compactText(task?.title ?? fallbackTitle ?? null, 80);
  if (title) {
    lines.push(`当前任务：${title}`);
  }
  const description = compactText(task?.description ?? null, 180);
  if (description) {
    lines.push(`任务说明：${description}`);
  }
  const blocker = compactText(task?.currentBlocker ?? null, 120);
  if (blocker) {
    lines.push(`任务卡点：${blocker}`);
  }
  const nextAction = compactText(task?.nextAction ?? null, 120);
  if (nextAction) {
    lines.push(`任务下一步：${nextAction}`);
  }
  const recentDecision = compactText(task?.recentDecision ?? null, 120);
  if (recentDecision) {
    lines.push(`任务判断：${recentDecision}`);
  }
  if (weekLabel) {
    lines.push(`当前周：${weekLabel}`);
  }
  return lines.length > 0 ? lines.join("\n") : null;
}

function buildTaskBoardContext(
  tasks: readonly TaskRecord[],
  options: {
    readonly clientId?: string | null;
    readonly eventLineId?: string | null;
    readonly weekLabel?: string | null;
  },
): string | null {
  const scopedTasks = tasks.filter((task) => {
    if (options.eventLineId) {
      return task.eventLineId === options.eventLineId;
    }
    if (options.clientId) {
      return task.clientId === options.clientId;
    }
    return true;
  });
  if (scopedTasks.length === 0) {
    return null;
  }
  const activeTasks = scopedTasks.filter((task) => task.progressStatus !== "done");
  const overdueCount = activeTasks.filter((task) => isTaskOverdue(task)).length;
  const lines: string[] = [];
  const boardLabel = options.weekLabel ? `${options.weekLabel} 任务板` : "任务板";
  lines.push(`${boardLabel}：共 ${scopedTasks.length} 条，未完成 ${activeTasks.length} 条`);
  if (overdueCount > 0) {
    lines.push(`逾期任务：${overdueCount} 条`);
  }
  const statusCounts = new Map<string, number>();
  for (const task of activeTasks) {
    const status = compactText(task.progressStatus, 24) ?? "todo";
    statusCounts.set(status, (statusCounts.get(status) ?? 0) + 1);
  }
  if (statusCounts.size > 0) {
    const statusSummary = [...statusCounts.entries()]
      .map(([status, count]) => `${status} ${count}`)
      .join("，");
    lines.push(`状态分布：${statusSummary}`);
  }
  const titleSummary =
    buildTaskContextSummary(scopedTasks, {
      clientId: options.clientId,
      eventLineId: options.eventLineId,
      weekLabel: options.weekLabel,
      limit: 6,
    }) ?? null;
  if (titleSummary) {
    lines.push(titleSummary);
  }
  const nextActions = activeTasks
    .map((task) => compactText(task.nextAction ?? task.title, 90))
    .filter((item): item is string => Boolean(item))
    .slice(0, 3);
  pushSummaryLine(lines, "优先推进", nextActions);
  return lines.length > 0 ? lines.join("\n") : null;
}

function buildUnderstandingContext(
  snapshot?: ClientUnderstandingSnapshot | null,
): string | null {
  if (!snapshot || snapshot.status === "missing") {
    return null;
  }
  const lines: string[] = [];
  if (snapshot.entities.length > 0) {
    const items = snapshot.entities
      .slice(0, 5)
      .map((entity) => {
        const name = compactText(entity.name, 40);
        if (!name) return null;
        const type = compactText(entity.type ?? null, 16);
        return type ? `${name}（${type}）` : name;
      })
      .filter((item): item is string => Boolean(item));
    if (items.length > 0) {
      lines.push(`关键实体：${items.join("；")}`);
    }
  }
  if (snapshot.relations.length > 0) {
    const items = snapshot.relations
      .slice(0, 4)
      .map((relation) => {
        const subject = compactText(relation.subject, 30);
        const predicate = compactText(relation.predicate, 24);
        const object = compactText(relation.object, 30);
        if (!subject || !object) return null;
        return `${subject} →${predicate}→ ${object}`;
      })
      .filter((item): item is string => Boolean(item));
    if (items.length > 0) {
      lines.push(`已知关系：${items.join("；")}`);
    }
  }
  if (snapshot.atomicFacts.length > 0) {
    const items = snapshot.atomicFacts
      .slice(0, 4)
      .map((fact) => compactText(fact.statement, 90))
      .filter((item): item is string => Boolean(item));
    if (items.length > 0) {
      lines.push(`原子事实：${items.join("；")}`);
    }
  }
  if (snapshot.contradictions.length > 0) {
    const items = snapshot.contradictions
      .slice(0, 3)
      .map((entry) => compactText(entry.topic, 60))
      .filter((item): item is string => Boolean(item));
    if (items.length > 0) {
      lines.push(`检测到的矛盾：${items.join("；")}`);
    }
  }
  if (snapshot.glossary.length > 0) {
    const items = snapshot.glossary
      .slice(0, 4)
      .map((entry) => {
        const term = compactText(entry.term, 30);
        const definition = compactText(entry.definition ?? null, 60);
        if (!term) return null;
        return definition ? `${term}：${definition}` : term;
      })
      .filter((item): item is string => Boolean(item));
    if (items.length > 0) {
      lines.push(`客户术语：${items.join("；")}`);
    }
  }
  return lines.length > 0 ? lines.join("\n") : null;
}

export function buildConsultRequestContext(params: {
  readonly currentFocus: CurrentFocus;
  readonly selectedContext: ConsultContextOption;
  readonly tasks: readonly TaskRecord[];
  readonly workspaceLite?: ClientWorkspaceLiteSnapshot | null;
  readonly eventLine?: EventLineRecord | null;
  readonly understanding?: ClientUnderstandingSnapshot | null;
}): ConsultRequestContext {
  const clientId = params.selectedContext.clientId ?? params.currentFocus.clientId ?? null;
  const clientName = params.selectedContext.clientName ?? params.currentFocus.clientName ?? null;
  const eventLineId = params.selectedContext.eventLineId ?? params.currentFocus.eventLineId ?? null;
  const eventLineName = params.selectedContext.eventLineName ?? params.currentFocus.eventLineName ?? null;
  const focusedTask = params.currentFocus.taskId
    ? params.tasks.find((task) => task.id === params.currentFocus.taskId) ?? null
    : null;
  const taskId = focusedTask?.id ?? params.currentFocus.taskId ?? null;
  const taskTitle = focusedTask?.title ?? params.currentFocus.taskTitle ?? null;
  const workspaceContext = buildWorkspaceContext(params.workspaceLite);
  const eventLineContext = buildEventLineContext(params.eventLine);
  const taskContext = buildFocusedTaskContext(focusedTask, params.currentFocus.weekLabel, taskTitle);
  const taskBoardContext = buildTaskBoardContext(params.tasks, {
    clientId,
    eventLineId,
    weekLabel: params.currentFocus.weekLabel,
  });
  const understandingContext = buildUnderstandingContext(
    params.understanding ?? params.workspaceLite?.understanding ?? null,
  );

  const sourceLabels = [
    clientName ? `当前客户：${clientName}` : null,
    eventLineName ? `当前事件线：${eventLineName}` : null,
    taskTitle ? `当前任务：${taskTitle}` : null,
    params.currentFocus.weekLabel ? `当前周：${params.currentFocus.weekLabel}` : null,
    params.workspaceLite ? "工作台" : null,
    params.eventLine ? "事件线卡片" : null,
    params.tasks.length > 0 ? "任务板" : null,
    understandingContext ? "理解快照" : null,
  ].filter(Boolean) as string[];

  return {
    clientId,
    clientName,
    eventLineId,
    eventLineName,
    taskId,
    taskTitle,
    taskContext,
    workspaceContext,
    eventLineContext,
    taskBoardContext,
    understandingContext,
    sourceLabels,
    missingEventLineHint: clientName && !eventLineId ? "当前未锁定事件线，回答只基于客户与任务板" : null,
  };
}
