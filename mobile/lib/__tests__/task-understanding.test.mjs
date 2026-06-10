import test from "node:test";
import assert from "node:assert/strict";

import {
  buildTaskUnderstandingCardModel,
  buildTaskUnderstandingSections,
} from "../../.mobile-core-tests/dist/lib/task-understanding.js";

test("insufficient context tasks do not repeat task description", () => {
  const sections = buildTaskUnderstandingSections({
    task: {
      id: "task-1",
      title: "和元兵吃饭",
      description: "和元兵吃饭，看看最近怎么推进",
      progressStatus: "todo",
      priority: "normal",
    },
    understanding: {
      whatIsThis: "和元兵吃饭，看看最近怎么推进",
      whyItMatters: "",
      progressNow: "",
      unknowns: "",
      knownFacts: [],
      confidence: 20,
      coverage: 20,
      _pending: false,
      sourceBreakdown: [
        { sourceType: "task_title", available: true },
        { sourceType: "task_desc", available: true },
      ],
    },
  });

  assert.equal(sections.status, "insufficient_context");
  assert.equal(sections.whatIsThis, "暂无可靠洞察");
  assert.match(sections.blockerAndDecision, /当前缺少：/);
  assert.match(sections.nextStepAndUnknowns, /建议补充：/);
});

test("weak event line links no longer use preview judgment as task understanding", () => {
  const sections = buildTaskUnderstandingSections({
    task: {
      id: "task-2",
      title: "和元兵吃饭",
      progressStatus: "todo",
      priority: "normal",
      eventLineId: "event-1",
      eventLineName: "市场行为",
    },
    eventLine: {
      id: "event-1",
      name: "市场行为",
      recentDecision: "先观察渠道反馈",
      currentBlocker: "还没有确认联系人身份",
    },
    contextPreview: {
      taskId: "task-2",
      summaryChips: ["事件线 · 市场行为", "阶段 · 线索观察"],
      safeOutputMode: "summary_only",
      judgment: {
        summary: "这是一次关键合作推进任务",
      },
    },
  });

  assert.equal(sections.status, "weak_link");
  assert.match(sections.whatIsThis, /已关联「市场行为」/);
  assert.doesNotMatch(sections.whatIsThis, /关键合作推进任务/);
  assert.match(sections.blockerAndDecision, /事件线卡点：还没有确认联系人身份/);
});

test("ready state requires non-generic understanding with stronger evidence", () => {
  const sections = buildTaskUnderstandingSections({
    task: {
      id: "task-3",
      title: "跟进测试机构A继续推进带领者培训",
      description: "继续推进当前轮次的带领者培训和演练",
      currentBlocker: "预算还没最后确认",
      nextAction: "补最终版执行排期",
      progressStatus: "todo",
      priority: "high",
    },
    understanding: {
      mode: "enhanced",
      whatIsThis: "这条任务处在测试机构A合作方案推进的执行准备阶段，重点是把培训和演练安排收拢成可执行计划。",
      whyItMatters: "最近反馈显示对方更关注执行节奏和落地安排，如果本轮还停留在泛化表达，后续预算和排期就会继续悬空。",
      progressNow: "最近进展停在排期收拢和预算确认之间，当前需要把执行安排说清楚。",
      unknowns: "还缺最终预算范围和对方对执行节奏的确认。",
      knownFacts: [],
      confidence: 72,
      coverage: 78,
      _pending: false,
      optionalAdvice: {
        minimumAction: "先补最终版执行排期",
      },
      sourceBreakdown: [
        { sourceType: "client_background", available: true },
        { sourceType: "meeting", available: true },
      ],
    },
  });

  assert.equal(sections.status, "ready");
  assert.match(sections.whatIsThis, /执行准备阶段/);
  assert.match(sections.whyItMatters, /更关注执行节奏/);
  assert.match(sections.nextStepAndUnknowns, /最小动作：先补最终版执行排期/);
});

test("generic why-it-matters keeps the card in insufficient context", () => {
  const sections = buildTaskUnderstandingSections({
    task: {
      id: "task-4",
      title: "晚上约高瑞瑞",
      progressStatus: "todo",
      priority: "normal",
    },
    understanding: {
      whatIsThis: "「晚上约高瑞瑞」是一条todo状态的工作任务。",
      whyItMatters: "这条任务与客户「益语智库」相关。",
      progressNow: "当前状态为 todo。",
      unknowns: "系统尚未看到以下信息：客户/项目背景卡。",
      knownFacts: [],
      confidence: 48,
      coverage: 60,
      _pending: false,
      sourceBreakdown: [
        { sourceType: "org_dna", available: true },
      ],
    },
  });

  assert.equal(sections.status, "insufficient_context");
  assert.equal(sections.whatIsThis, "暂无可靠洞察");
});

test("card model surfaces evidence for ready states", () => {
  const card = buildTaskUnderstandingCardModel({
    task: {
      id: "task-5",
      title: "准备测试机构A沟通材料",
      progressStatus: "todo",
      priority: "high",
      clientName: "测试机构A",
      eventLineName: "合作方案推进",
    },
    understanding: {
      whatIsThis: "当前要把沟通材料收敛成可会前使用的版本。",
      whyItMatters: "明天的沟通会直接决定下一轮合作推进节奏。",
      progressNow: "卡在材料版本还没最终收口。",
      unknowns: "还缺预算边界。",
      knownFacts: [],
      confidence: 80,
      coverage: 82,
      _pending: false,
      sourceBreakdown: [
        { sourceType: "meeting", available: true },
        { sourceType: "client_background", available: true },
      ],
    },
    contextPreview: {
      taskId: "task-5",
      clientName: "测试机构A",
      summaryChips: ["阶段 · 会前准备", "事件线 · 合作方案推进"],
    },
  });

  assert.equal(card.tone, "ready");
  assert.equal(card.stateLabel, "已整理");
  assert.match(card.subtitle, /现有信息/);
  assert.ok(card.evidence.includes("会议记录"));
  assert.ok(card.evidence.includes("客户背景"));
});

test("card model uses caution copy for insufficient context", () => {
  const card = buildTaskUnderstandingCardModel({
    task: {
      id: "task-6",
      title: "晚上约高瑞瑞",
      progressStatus: "todo",
      priority: "normal",
    },
  });

  assert.equal(card.tone, "insufficient_context");
  assert.equal(card.stateLabel, "待补信息");
  assert.equal(card.sections[0].title, "当前提醒");
  assert.equal(card.sections[2].title, "待确认信息");
});
