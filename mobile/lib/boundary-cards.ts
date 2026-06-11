import type { BoundaryCard } from "./types";

function toText(value: unknown): string {
  if (typeof value === "string") {
    return value.trim();
  }
  if (value == null) {
    return "";
  }
  return String(value).trim();
}

export function buildBoundaryCards(workspace: any, cockpit: any): BoundaryCard[] {
  const healthSummary = Array.isArray(cockpit?.health)
    ? cockpit.health
        .map((item: any) => toText(item?.summary || item?.label || item?.value))
        .filter(Boolean)
        .join("；")
    : "";
  const conflictSummary = Array.isArray(workspace?.latestConflicts)
    ? workspace.latestConflicts
        .map((item: any) => toText(item?.summary || item?.title))
        .filter(Boolean)
        .slice(0, 2)
        .join("；")
    : "";
  const pendingSummary = Array.isArray(cockpit?.pendingDecisions)
    ? cockpit.pendingDecisions
        .map((item: any) => toText(item?.summary || item?.title || item?.label))
        .filter(Boolean)
        .slice(0, 3)
        .join("；")
    : "";
  const reminderSummary = [
    ...(Array.isArray(workspace?.latestOpenQuestions)
      ? workspace.latestOpenQuestions
          .map((item: any) => toText(item?.summary || item?.question || item?.title))
          .filter(Boolean)
          .slice(0, 2)
      : []),
    ...(Array.isArray(cockpit?.pendingMaterials)
      ? cockpit.pendingMaterials
          .map((item: any) => toText(item?.summary || item?.title || item?.label))
          .filter(Boolean)
          .slice(0, 2)
      : []),
  ].join("；");

  const officialReady = cockpit?.officialLayerStatus === "ready";
  const officialSummary = officialReady
    ? toText(
        cockpit?.headline?.summary ||
          cockpit?.headline?.mainSummary ||
          cockpit?.headline?.primaryStatement ||
          cockpit?.headline?.title ||
          cockpit?.clientTagline ||
          cockpit?.stageLabel ||
          workspace?.client?.name,
      )
    : "";

  return [
    {
      kind: "official",
      title: officialReady ? "正式判断" : "当前暂无已批准判断",
      summary: officialSummary || "暂无正式判断，请先结合工作台与证据层继续推进。",
      sourceType: officialReady ? "manual" : "mixed",
      updatedAt: cockpit?.updatedAt ?? workspace?.client?.updatedAt ?? null,
      evidenceCount: officialReady ? null : 0,
      isEmpty: !officialReady,
    },
    {
      kind: "pending",
      title: "待确认判断",
      summary: pendingSummary || "暂无待确认判断",
      sourceType: pendingSummary ? "mixed" : "manual",
      updatedAt: cockpit?.updatedAt ?? null,
      evidenceCount: Array.isArray(cockpit?.pendingDecisions) ? cockpit.pendingDecisions.length : 0,
      isEmpty: !pendingSummary,
    },
    {
      kind: "risk",
      title: "风险 / 冲突",
      summary: [healthSummary, conflictSummary].filter(Boolean).join("；") || "暂无明显风险",
      sourceType: [healthSummary, conflictSummary].filter(Boolean).length > 1 ? "mixed" : "manual",
      updatedAt: cockpit?.updatedAt ?? null,
      evidenceCount:
        (Array.isArray(cockpit?.health) ? cockpit.health.length : 0) +
        (Array.isArray(workspace?.latestConflicts) ? workspace.latestConflicts.length : 0),
      isEmpty: !healthSummary && !conflictSummary,
    },
    {
      kind: "reminder",
      title: "提醒 / 缺口",
      summary: reminderSummary || "暂无提醒项",
      sourceType: reminderSummary ? "mixed" : "manual",
      updatedAt: cockpit?.updatedAt ?? null,
      evidenceCount:
        (Array.isArray(workspace?.latestOpenQuestions) ? workspace.latestOpenQuestions.length : 0) +
        (Array.isArray(cockpit?.pendingMaterials) ? cockpit.pendingMaterials.length : 0),
      isEmpty: !reminderSummary,
    },
  ];
}
