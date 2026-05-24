/**
 * AI 工作指令 · 解析 + 模块能力 Manifest + 类型
 *
 * 顾源源 5/24 任务书 §7-8: 智能指令解析 + 复杂任务类型分类
 *
 * B 角色: 前端解析层 (轻量规则 + LLM 辅助, 不在 prompt 写死流程)
 */

export type AICommandMode = 'quick_task' | 'ai_command';

export type AICommandIntent =
  | 'quick_task'
  | 'generate_client_background_document'
  | 'generate_report_outline'
  | 'review_today_tasks_for_ai'
  | 'summarize_client_state'
  | 'resolve_clarifications_plan'
  | 'unknown';

export type ParsedSmartCommand = {
  mode: AICommandMode;
  bot_handle: string | null;
  client_name: string | null;
  intent: AICommandIntent;
  requested_outputs: string[];
  target_workspace: string | null;
  inline_authorization_detected: boolean;
  inline_authorization_text: string | null;
  requires_plan: boolean;
  original_text: string;
};

// 复杂任务特征关键词
const COMPLEX_TASK_KEYWORDS = [
  '帮我完成', '帮我生成', '生成报告', '写方案', '做分析', '扫描资料',
  '调用资讯', '放进工作台', '生成复盘', '帮我推进', '为某个客户',
  '集团介绍', '会谈准备', '品牌报告', '理事会说明',
];

// inline authorization 关键词
const INLINE_AUTH_PATTERNS: { re: RegExp; text: string }[] = [
  { re: /不用审批[,，]?\s*直接执行/, text: '不用审批, 直接执行' },
  { re: /直接开始/, text: '直接开始' },
  { re: /我授权你执行第一步/, text: '我授权你执行第一步' },
  { re: /不用再问我[,，]?\s*先做/, text: '不用再问我, 先做' },
  { re: /按我的授权先开始/, text: '按我的授权先开始' },
  { re: /按我的授权先执行/, text: '按我的授权先执行' },
];

// intent 识别规则 (轻量, 不写死单一场景)
function classifyIntent(text: string): AICommandIntent {
  if (/(集团介绍|背景资料|公司介绍|机构介绍)/.test(text)) {
    return 'generate_client_background_document';
  }
  if (/(报告.{0,5}提纲|提纲|outline)/.test(text)) {
    return 'generate_report_outline';
  }
  if (/(今天.{0,8}(任务|待办)|哪些.{0,5}(可以|能).{0,5}(做|接|交))/.test(text)) {
    return 'review_today_tasks_for_ai';
  }
  if (/(客户.{0,10}状态|总结.{0,10}客户|客户.{0,10}摘要)/.test(text)) {
    return 'summarize_client_state';
  }
  if (/(待澄清|待确认.{0,10}事项|澄清.{0,10}处理)/.test(text)) {
    return 'resolve_clarifications_plan';
  }
  return 'unknown';
}

// @ 机器人识别 (支持 @庆华 / @庆华 / @qinghua)
function extractBotHandle(text: string): string | null {
  const match = text.match(/@([一-龥a-zA-Z0-9_]+)/);
  return match ? match[1] : null;
}

// 客户名提取 (基于关键词附近匹配, 第一版简单, 后续可接 LLM)
function extractClientName(text: string, candidates: string[]): string | null {
  for (const name of candidates) {
    if (name && text.includes(name)) {
      return name;
    }
  }
  return null;
}

function extractOutputs(text: string): string[] {
  const outputs: string[] = [];
  const patterns = [
    /生成一份(.{2,15}?)(?:[,，。]|$)/g,
    /帮我写(.{2,15}?)(?:[,，。]|$)/g,
    /做一份(.{2,15}?)(?:[,，。]|$)/g,
  ];
  patterns.forEach((p) => {
    let m;
    while ((m = p.exec(text)) !== null) {
      const o = m[1].trim();
      if (o && !outputs.includes(o)) outputs.push(o);
    }
  });
  return outputs;
}

function extractTargetWorkspace(text: string): string | null {
  if (/客户工作台/.test(text)) return '客户工作台';
  if (/战略陪伴/.test(text)) return '战略陪伴';
  if (/资讯情报站/.test(text)) return '资讯情报站';
  if (/任务与日程/.test(text)) return '任务与日程';
  return null;
}

/**
 * 解析智能指令文本
 *
 * @param text 用户输入原文
 * @param knownClientNames 已知客户名列表 (从 V2.1 lab db 拉, 用于匹配)
 */
export function parseSmartCommand(
  text: string,
  knownClientNames: string[] = [],
): ParsedSmartCommand {
  const botHandle = extractBotHandle(text);
  const hasComplexKeyword = COMPLEX_TASK_KEYWORDS.some((kw) => text.includes(kw));
  const intent = classifyIntent(text);

  // mode 判断: 有 @机器人 或 complex keyword 或 intent != unknown → ai_command
  const mode: AICommandMode =
    botHandle || hasComplexKeyword || intent !== 'unknown' ? 'ai_command' : 'quick_task';

  const inlineAuth = INLINE_AUTH_PATTERNS.find((p) => p.re.test(text));

  return {
    mode,
    bot_handle: botHandle,
    client_name: extractClientName(text, knownClientNames),
    intent: mode === 'quick_task' ? 'quick_task' : intent,
    requested_outputs: extractOutputs(text),
    target_workspace: extractTargetWorkspace(text),
    inline_authorization_detected: inlineAuth != null,
    inline_authorization_text: inlineAuth?.text ?? null,
    requires_plan: mode === 'ai_command',
    original_text: text,
  };
}

// ── 模块能力 Manifest (顾源源 §6, 不硬编码业务流程) ────

export type ModuleCapabilityEntry = {
  capabilityKey: string;
  label: string;
  riskLevel: 'low' | 'medium' | 'high';
  approvalRequired: boolean;
  toolNames: string[];
  requiredBotCapability?: string;
};

export type ModuleCapability = {
  moduleKey: string;
  moduleName: string;
  enabled: boolean;
  description: string;
  capabilities: ModuleCapabilityEntry[];
};

export const MODULE_CAPABILITY_MANIFEST_V1: ModuleCapability[] = [
  {
    moduleKey: 'tasks',
    moduleName: '任务与日程',
    enabled: true,
    description: '创建 AI 自己的任务 / 执行计划 / 复盘 / 标记状态',
    capabilities: [
      { capabilityKey: 'task.create', label: '创建任务', riskLevel: 'low', approvalRequired: false, toolNames: ['tasks.create'] },
      { capabilityKey: 'task.review', label: '写复盘', riskLevel: 'low', approvalRequired: false, toolNames: [] },
    ],
  },
  {
    moduleKey: 'workspace',
    moduleName: '客户工作台',
    enabled: true,
    description: '读取客户状态 / 工作台问答 / 写入客户工作台正式文件 (需审批)',
    capabilities: [
      { capabilityKey: 'workspace.read_state', label: '读客户状态', riskLevel: 'low', approvalRequired: false, toolNames: ['clients.agent_state'] },
      { capabilityKey: 'workspace.chat', label: '工作台问答', riskLevel: 'low', approvalRequired: false, toolNames: ['workspace.chat'] },
      { capabilityKey: 'workspace.file_write_request', label: '申请写入工作台正式文件', riskLevel: 'high', approvalRequired: true, toolNames: [], requiredBotCapability: 'workspace_file_write.request' },
    ],
  },
  {
    moduleKey: 'data_center',
    moduleName: '数据中心 / 公司大脑',
    enabled: true,
    description: '读事实/承诺/风险/待澄清/数据缺口 / 判断证据 / 触发解析',
    capabilities: [
      { capabilityKey: 'data.read_gaps', label: '查数据缺口', riskLevel: 'low', approvalRequired: false, toolNames: ['data_gaps.list'] },
      { capabilityKey: 'data.check_evidence', label: '检查证据', riskLevel: 'low', approvalRequired: false, toolNames: ['evidence.check'] },
      { capabilityKey: 'data.quality_context', label: '质量评估', riskLevel: 'low', approvalRequired: false, toolNames: ['quality.context'] },
      { capabilityKey: 'data.authority_resolve', label: '权威值判断', riskLevel: 'low', approvalRequired: false, toolNames: ['authority.resolve'] },
      { capabilityKey: 'data.parse_request', label: '申请触发数据中心解析', riskLevel: 'high', approvalRequired: true, toolNames: [], requiredBotCapability: 'data_center_parse.request' },
    ],
  },
  {
    moduleKey: 'intelligence',
    moduleName: '资讯情报站',
    enabled: false,
    description: '读已有外部证据 / 查缺口 / 申请补外部证据 (部分未暴露)',
    capabilities: [
      { capabilityKey: 'intel.read_gaps', label: '查外部证据缺口', riskLevel: 'low', approvalRequired: false, toolNames: ['data_gaps.list'] },
      { capabilityKey: 'intel.compensate', label: '申请补外部证据', riskLevel: 'medium', approvalRequired: true, toolNames: ['data_gaps.compensate'] },
    ],
  },
  {
    moduleKey: 'documents',
    moduleName: '文档生成 / 战略陪伴',
    enabled: true,
    description: '生成报告提纲 / 草稿 / 品牌建议 / 合同草稿 / 会谈包 / 模板填充',
    capabilities: [
      { capabilityKey: 'doc.fill_template', label: '模板填充 (R4-P1)', riskLevel: 'medium', approvalRequired: true, toolNames: ['documents.fill_template'], requiredBotCapability: 'external_material_draft.create' },
      { capabilityKey: 'doc.contracts_draft', label: '合同草稿 (V3.0 P0-1, 未暴露)', riskLevel: 'high', approvalRequired: true, toolNames: ['contracts.draft'], requiredBotCapability: 'external_material_draft.create' },
      { capabilityKey: 'doc.templates_generate', label: '模板生成 (V3.0 P0-2, 未暴露)', riskLevel: 'medium', approvalRequired: true, toolNames: ['templates.generate'], requiredBotCapability: 'external_material_draft.create' },
    ],
  },
  {
    moduleKey: 'growth',
    moduleName: '成长中心 / 复盘',
    enabled: true,
    description: '写 AI 任务复盘 (第一版只写任务复盘, 不沉淀到成长中心)',
    capabilities: [
      { capabilityKey: 'growth.write_review', label: '写任务复盘', riskLevel: 'low', approvalRequired: false, toolNames: [] },
    ],
  },
];

// 根据 intent 推荐需要的模块
export function recommendModulesForIntent(intent: AICommandIntent): string[] {
  switch (intent) {
    case 'generate_client_background_document':
      return ['workspace', 'data_center', 'documents', 'tasks', 'growth'];
    case 'generate_report_outline':
      return ['workspace', 'data_center', 'documents', 'tasks'];
    case 'review_today_tasks_for_ai':
      return ['tasks', 'data_center'];
    case 'summarize_client_state':
      return ['workspace', 'data_center'];
    case 'resolve_clarifications_plan':
      return ['workspace', 'data_center', 'tasks'];
    default:
      return ['workspace', 'tasks'];
  }
}

// ── 执行计划数据结构 (顾源源 §9 AIExecutionPlan) ────

export type AIExecutionPlanStep = {
  order: number;
  moduleKey: string;
  action: string;
  toolName?: string;
  expectedResult: string;
  writesTo?: string[];
  readsFrom?: string[];
  approvalRequired: boolean;
  riskLevel: 'low' | 'medium' | 'high';
};

export type AIExecutionPlanApprovalItem = {
  action: string;
  reason: string;
  approverType: 'department_lead' | 'ceo' | 'any_reporting_approver';
};

export type AIExecutionPlanRequiredModule = {
  moduleKey: string;
  moduleName: string;
  enabled: boolean;
  purpose: string;
};

export type AIExecutionPlanInlineAuth = {
  detected: boolean;
  text?: string;
  humanInitiatorId?: string;
};

export type AIExecutionPlan = {
  title: string;
  botMemberId: string;
  actorId: string;
  clientId?: string;
  eventLineId?: string;
  intent: AICommandIntent;
  taskGoal: string;
  requiredModules: AIExecutionPlanRequiredModule[];
  steps: AIExecutionPlanStep[];
  expectedOutputs: string[];
  approvalItems: AIExecutionPlanApprovalItem[];
  limitations: string[];
  inlineAuthorization?: AIExecutionPlanInlineAuth;
};
