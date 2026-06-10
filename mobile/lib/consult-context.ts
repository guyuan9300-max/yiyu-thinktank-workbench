import type { CurrentFocus, TaskRecord } from "./types";

export interface ConsultContextOption {
  readonly id: string;
  readonly label: string;
  readonly scope: "all" | "client" | "event_line";
  readonly clientId: string | null;
  readonly clientName: string | null;
  readonly eventLineId: string | null;
  readonly eventLineName: string | null;
}

interface TaskContextSummaryOptions {
  readonly clientId?: string | null;
  readonly eventLineId?: string | null;
  readonly limit?: number;
  readonly weekLabel?: string | null;
}

export function buildConsultGreeting(option: ConsultContextOption): string {
  if (option.scope === "event_line" && option.clientName && option.eventLineName) {
    return `你好，我是你的咨询助理。当前已锁定 ${option.clientName} · ${option.eventLineName}，你想先看哪部分？`;
  }
  if (option.scope === "client" && option.clientName) {
    return `你好，我是你的咨询助理。当前已锁定 ${option.clientName}，你想先了解什么？`;
  }
  return "你好，我是你的咨询助理。当前未锁定客户或事件线，我会先基于任务板给你建议。";
}

export function buildConsultContextOptions(tasks: readonly TaskRecord[]): readonly ConsultContextOption[] {
  const options: ConsultContextOption[] = [
    {
      id: "all",
      label: "全部",
      scope: "all",
      clientId: null,
      clientName: null,
      eventLineId: null,
      eventLineName: null,
    },
  ];
  const clientMap = new Map<string, ConsultContextOption>();

  // 咨询上下文下拉只按「客户」聚合，不再列出事件线（产品要求：客户级即可，不询问事件线）。
  for (const task of tasks) {
    if (task.clientId && task.clientName && !clientMap.has(task.clientId)) {
      clientMap.set(task.clientId, {
        id: `client:${task.clientId}`,
        label: task.clientName,
        scope: "client",
        clientId: task.clientId,
        clientName: task.clientName,
        eventLineId: null,
        eventLineName: null,
      });
    }
  }

  return options.concat(Array.from(clientMap.values()));
}

export function resolveConsultContextFromFocus(
  options: readonly ConsultContextOption[],
  currentFocus: CurrentFocus | null | undefined,
): ConsultContextOption {
  if (currentFocus?.eventLineId) {
    const matchedEventLine = options.find((option) => option.eventLineId === currentFocus.eventLineId);
    if (matchedEventLine) {
      return matchedEventLine;
    }
    if (currentFocus.clientId || currentFocus.eventLineName) {
      return {
        id: `focus:event:${currentFocus.eventLineId}`,
        label: currentFocus.clientName && currentFocus.eventLineName
          ? `${currentFocus.clientName} / ${currentFocus.eventLineName}`
          : currentFocus.eventLineName || currentFocus.clientName || "当前事件线",
        scope: "event_line",
        clientId: currentFocus.clientId,
        clientName: currentFocus.clientName,
        eventLineId: currentFocus.eventLineId,
        eventLineName: currentFocus.eventLineName,
      };
    }
  }
  if (currentFocus?.clientId) {
    const matchedClient = options.find(
      (option) => option.scope === "client" && option.clientId === currentFocus.clientId,
    );
    if (matchedClient) {
      return matchedClient;
    }
    return {
      id: `focus:client:${currentFocus.clientId}`,
      label: currentFocus.clientName || "当前客户",
      scope: "client",
      clientId: currentFocus.clientId,
      clientName: currentFocus.clientName,
      eventLineId: null,
      eventLineName: null,
    };
  }
  return (
    options.find((option) => option.scope === "all") ??
    options[0] ?? {
      id: "all",
      label: "全部",
      scope: "all",
      clientId: null,
      clientName: null,
      eventLineId: null,
      eventLineName: null,
    }
  );
}

export function buildTaskContextSummary(
  tasks: readonly TaskRecord[],
  options: TaskContextSummaryOptions = {},
): string | undefined {
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
    return undefined;
  }

  const titles = scopedTasks
    .map((task) => task.title.trim())
    .filter(Boolean)
    .slice(0, options.limit ?? 5);
  if (titles.length === 0) {
    return undefined;
  }
  if (options.weekLabel) {
    return `${options.weekLabel} 任务：${titles.join("、")}`;
  }
  return `任务板：${titles.join("、")}`;
}
