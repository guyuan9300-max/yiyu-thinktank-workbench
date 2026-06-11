import test from "node:test";
import assert from "node:assert/strict";

import { buildConsultRequestContext } from "../../.mobile-core-tests/dist/lib/consult-context-adapter.js";

const baseFocus = {
  clientId: "client-zen",
  clientName: "禅意基金会",
  eventLineId: null,
  eventLineName: null,
  taskId: null,
  taskTitle: null,
  weekAnchorDate: "2026-05-11",
  weekLabel: "2026-W20",
  source: "manual",
  lockMode: "client",
  boundaryState: "none",
  updatedAt: "2026-05-12T01:00:00.000Z",
};

const baseSelected = {
  id: "client:client-zen",
  label: "禅意基金会",
  scope: "client",
  clientId: "client-zen",
  clientName: "禅意基金会",
  eventLineId: null,
  eventLineName: null,
};

const baseWorkspace = {
  clientId: "client-zen",
  clientName: "禅意基金会",
  status: "rich",
  availableSources: ["workspace"],
  missingSources: [],
  staleSources: [],
  sourceUpdatedAt: { workspace: "2026-05-12T01:00:00.000Z" },
  boundaryCards: [],
  boundaryState: "none",
  goals: [],
  latestMeetings: [],
  knowledgeStatus: null,
  recentDocuments: [],
  openQuestions: [],
  conflicts: [],
  relatedTasks: [],
  nextActions: [],
  headline: null,
  health: [],
  twoWeekChanges: [],
  pendingDecisions: [],
  pendingMaterials: [],
  updatedAt: "2026-05-12T01:00:00.000Z",
};

test("buildConsultRequestContext keeps week in task context and surfaces missing event line hint", () => {
  const context = buildConsultRequestContext({
    currentFocus: {
      clientId: "client-rita",
      clientName: "测试机构A",
      eventLineId: null,
      eventLineName: null,
      taskId: "task-1",
      taskTitle: "测试机构A会前准备",
      weekAnchorDate: "2026-04-13",
      weekLabel: "2026-W16",
      source: "manual",
      lockMode: "client",
      boundaryState: "pending",
      updatedAt: "2026-04-16T09:00:00.000Z",
    },
    selectedContext: {
      id: "client:client-rita",
      label: "测试机构A",
      scope: "client",
      clientId: "client-rita",
      clientName: "测试机构A",
      eventLineId: null,
      eventLineName: null,
    },
    workspaceLite: {
      clientId: "client-rita",
      clientName: "测试机构A",
      boundaryCards: [
        {
          kind: "risk",
          title: "预算未定",
          summary: "当前预算区间还没有锁死",
          sourceType: "manual",
          updatedAt: "2026-04-16T09:00:00.000Z",
          evidenceCount: 1,
          isEmpty: false,
        },
      ],
      boundaryState: "pending",
      goals: [
        {
          id: "goal-1",
          title: "锁定合作路径",
          summary: "本周把合作范围和会议目标收口",
        },
      ],
      latestMeetings: [
        {
          id: "meeting-1",
          title: "会前沟通",
          summary: "对方希望先看一版材料",
        },
      ],
      knowledgeStatus: null,
      recentDocuments: [
        {
          id: "doc-1",
          title: "合作草案",
          summary: "初版合作框架待确认",
        },
      ],
      openQuestions: [
        {
          id: "question-1",
          title: "预算口径",
          summary: "还未确认预算上限",
        },
      ],
      conflicts: [],
      relatedTasks: [],
      nextActions: ["确认预算假设", "补齐会前材料"],
      headline: "本周先收口合作路径",
      health: ["客户对方向是清楚的，但预算边界不清楚"],
      twoWeekChanges: ["最近一周从泛合作转向明确项目合作"],
      pendingDecisions: ["是否按项目包推进"],
      pendingMaterials: ["需补一版材料摘要"],
      updatedAt: "2026-04-16T09:00:00.000Z",
    },
    eventLine: null,
    tasks: [
      {
        id: "task-1",
        title: "测试机构A会前准备",
        clientId: "client-rita",
        clientName: "测试机构A",
        currentBlocker: "尚未确认预算区间",
        nextAction: "整理会前要点",
      },
    ],
  });

  assert.equal(context.clientId, "client-rita");
  assert.equal(context.eventLineId, null);
  assert.equal(context.taskId, "task-1");
  assert.equal(context.taskTitle, "测试机构A会前准备");
  assert.match(context.taskContext || "", /当前任务：测试机构A会前准备/);
  assert.match(context.taskContext || "", /任务卡点：尚未确认预算区间/);
  assert.match(context.taskContext || "", /2026-W16/);
  assert.match(context.workspaceContext || "", /客户工作台：本周先收口合作路径/);
  assert.match(context.workspaceContext || "", /阶段目标：锁定合作路径：本周把合作范围和会议目标收口/);
  assert.match(context.workspaceContext || "", /开放问题：预算口径：还未确认预算上限/);
  assert.match(context.taskBoardContext || "", /2026-W16 任务板：共 1 条，未完成 1 条/);
  assert.equal(context.missingEventLineHint, "当前未锁定事件线，回答只基于客户与任务板");
  assert.deepEqual(context.sourceLabels.slice(0, 4), [
    "当前客户：测试机构A",
    "当前任务：测试机构A会前准备",
    "当前周：2026-W16",
    "工作台",
  ]);
});

test("buildConsultRequestContext folds explicit understanding into context blocks and source labels", () => {
  const context = buildConsultRequestContext({
    currentFocus: baseFocus,
    selectedContext: baseSelected,
    tasks: [],
    workspaceLite: baseWorkspace,
    eventLine: null,
    understanding: {
      clientId: "client-zen",
      status: "ready",
      updatedAt: "2026-05-12T01:00:00.000Z",
      snapshotHash: "abc",
      entities: [
        { id: "e1", name: "禅意基金会", type: "organization", mentions: 7 },
        { id: "e2", name: "王理事", type: "person", mentions: 4 },
      ],
      relations: [
        {
          id: "r1",
          subject: "王理事",
          predicate: "负责",
          object: "禅意基金会",
          evidenceCount: 2,
        },
      ],
      atomicFacts: [
        { id: "f1", statement: "禅意基金会 Q2 募资目标 800 万", semanticType: "fact" },
      ],
      contradictions: [
        {
          id: "c1",
          topic: "Q2 募资口径分歧",
          conflictingStatements: ["目标 800 万", "目标 1000 万"],
          severity: "medium",
        },
      ],
      glossary: [
        { id: "g1", term: "募资双飞轮", definition: "捐赠 + 项目营收并行的双引擎模型" },
      ],
    },
  });

  assert.ok(context.understandingContext, "understandingContext should not be null");
  assert.match(context.understandingContext, /关键实体：禅意基金会（organization）/);
  assert.match(context.understandingContext, /已知关系：王理事 →负责→ 禅意基金会/);
  assert.match(context.understandingContext, /原子事实：禅意基金会 Q2 募资目标 800 万/);
  assert.match(context.understandingContext, /检测到的矛盾：Q2 募资口径分歧/);
  assert.match(context.understandingContext, /客户术语：募资双飞轮：捐赠 \+ 项目营收并行的双引擎模型/);
  assert.ok(context.sourceLabels.includes("理解快照"));
});

test("buildConsultRequestContext falls back to workspaceLite.understanding when no explicit understanding is given", () => {
  const context = buildConsultRequestContext({
    currentFocus: baseFocus,
    selectedContext: baseSelected,
    tasks: [],
    workspaceLite: {
      ...baseWorkspace,
      understanding: {
        clientId: "client-zen",
        status: "partial",
        updatedAt: "2026-05-12T01:00:00.000Z",
        entities: [{ id: "e1", name: "禅意基金会", type: "organization", mentions: 7 }],
        relations: [],
        atomicFacts: [],
        contradictions: [],
        glossary: [],
      },
    },
    eventLine: null,
  });

  assert.match(context.understandingContext || "", /关键实体：禅意基金会（organization）/);
  assert.ok(context.sourceLabels.includes("理解快照"));
});

test("buildConsultRequestContext omits understandingContext when no snapshot is provided", () => {
  const context = buildConsultRequestContext({
    currentFocus: baseFocus,
    selectedContext: baseSelected,
    tasks: [],
    workspaceLite: baseWorkspace,
    eventLine: null,
  });

  assert.equal(context.understandingContext, null);
  assert.ok(!context.sourceLabels.includes("理解快照"));
});
