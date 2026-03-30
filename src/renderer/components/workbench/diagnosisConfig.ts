import type { AnalysisRun, AnalysisTemplate, DiagnosisAudienceType, DiagnosisScene } from '../../../shared/types';

type DiagnosisPlatformDnaContext = {
  key: string;
  label: string;
  summary: string;
  corePreferences: string[];
  riskTriggers: string[];
  tonePreference?: string;
};

export type DiagnosisWorkspaceKey = 'fundraising' | 'public_opinion' | 'project_design';
export type DiagnosisModeId =
  | 'platform_fundraising'
  | 'monthly_donor'
  | 'key_person'
  | 'incident_response'
  | 'preflight_release'
  | 'project_mechanism'
  | 'stakeholder_simulation'
  | 'methodology_review';

export type DiagnosisWorkspaceDefinition = {
  key: DiagnosisWorkspaceKey;
  label: string;
  subtitle: string;
  templatePreferenceKey: string;
  handbookTag: string;
};

export type DiagnosisModeDefinition = {
  id: DiagnosisModeId;
  workspaceKey: DiagnosisWorkspaceKey;
  title: string;
  description: string;
  tags: string[];
  focusPoints: string[];
  promptChips: string[];
  learningTitle: string;
  learningBody: string;
};

const INPUT_CONTEXT_START = '[[DIAGNOSIS_CONTEXT]]';
const INPUT_CONTEXT_END = '[[/DIAGNOSIS_CONTEXT]]';
const PLATFORM_DNA_CONTEXT_START = '[[PLATFORM_DNA]]';
const PLATFORM_DNA_CONTEXT_END = '[[/PLATFORM_DNA]]';

export const DIAGNOSIS_WORKSPACES: DiagnosisWorkspaceDefinition[] = [
  {
    key: 'fundraising',
    label: '筹款文案',
    subtitle: '围绕平台、月捐人与关键对象的判断习惯，诊断一条文案为什么能打动或劝退人。',
    templatePreferenceKey: 'fundraising',
    handbookTag: '筹款文案',
  },
  {
    key: 'public_opinion',
    label: '舆情公关',
    subtitle: '在公开回应或发布前，先看不同群体会如何理解、误读和扩散。',
    templatePreferenceKey: 'systemic',
    handbookTag: '舆情公关',
  },
  {
    key: 'project_design',
    label: '项目设计',
    subtitle: '检查一个方案是否真的触及结构性问题、角色关系和持续变化路径。',
    templatePreferenceKey: 'systemic',
    handbookTag: '项目设计',
  },
];

export const DIAGNOSIS_MODES: DiagnosisModeDefinition[] = [
  {
    id: 'platform_fundraising',
    workspaceKey: 'fundraising',
    title: '平台筹款',
    description: '面向平台公域捐赠人，优先检查可信度、过度煽情、热点结合与平台风险。',
    tags: ['平台语境', '公域捐赠人'],
    focusPoints: ['可信度与真实感', '情绪表达是否过度', '平台风险触发点', '热点与时机'],
    promptChips: ['重写高风险段落', '生成预算拆解', '补一版平台标题'],
    learningTitle: '平台信任先于情绪推动',
    learningBody: '在公域平台里，先让人相信“这是真的、这钱怎么花、这事和我有什么关系”，再谈情绪共鸣。',
  },
  {
    id: 'monthly_donor',
    workspaceKey: 'fundraising',
    title: '月捐人测试',
    description: '面向长期关系型捐赠人，检查留存逻辑、关系感和长期承诺是否成立。',
    tags: ['月捐', '长期关系'],
    focusPoints: ['长期价值主张', '关系感与认同感', '续捐与留存风险', '陪伴感是否成立'],
    promptChips: ['补一版续捐沟通', '拆长期价值主张', '检查留存风险'],
    learningTitle: '月捐不是一次成交',
    learningBody: '月捐更像长期关系承诺。比起一时感动，持续信任、价值认同和被看见的感觉更重要。',
  },
  {
    id: 'key_person',
    workspaceKey: 'fundraising',
    title: 'Key Person',
    description: '面向基金会、企业 CSR 或关键个人，检查提案是否贴合对方的判断口径和关注点。',
    tags: ['关键对象', '提案判断'],
    focusPoints: ['对方关注点', '语言风格匹配', '证据与可信度', '合作逻辑'],
    promptChips: ['按关键对象重写', '补合作逻辑', '突出可信证据'],
    learningTitle: '对的人先听到对的逻辑',
    learningBody: '关键对象不缺被打动的材料，缺的是与其判断框架一致、证据扎实且可执行的合作逻辑。',
  },
  {
    id: 'incident_response',
    workspaceKey: 'public_opinion',
    title: '已发生舆情',
    description: '面向已经爆发的争议，判断质疑从哪里来、回应是否真正补足了信任缺口。',
    tags: ['回应诊断', '风险扩散'],
    focusPoints: ['质疑触发点', '公众信息缺口', '回应顺序', '二次发酵风险'],
    promptChips: ['重写温和开头', '补时间线', '列第三方凭证'],
    learningTitle: '回应不是吵赢，是补齐判断依据',
    learningBody: '舆情回应的核心不是表达委屈，而是迅速补充公众判断所需要的事实、顺序和边界。',
  },
  {
    id: 'preflight_release',
    workspaceKey: 'public_opinion',
    title: '发布前预演',
    description: '在内容公开前，先预演不同对象会如何理解和放大这段表达。',
    tags: ['发布前', '误读预演'],
    focusPoints: ['谁会误读', '哪些词会被放大', '哪些事实应提前补充', '支持与质疑路径'],
    promptChips: ['找最易误读语句', '补风险边界', '改一版更稳的表达'],
    learningTitle: '预演的价值在于提前补边界',
    learningBody: '很多风险不是因为内容本身错，而是因为外界会按另一套逻辑理解它。预演的任务就是提前补边界。',
  },
  {
    id: 'project_mechanism',
    workspaceKey: 'project_design',
    title: '项目机制评估',
    description: '判断方案是否只停留在一次性给与，还是已经触及更深层的结构性机制。',
    tags: ['机制检查', '结构问题'],
    focusPoints: ['问题结构性成因', '可干预变量', '长期变化路径', '短期与长期断层'],
    promptChips: ['检查结构性机制', '补长期变化路径', '找干预断层'],
    learningTitle: '项目不是活动堆叠',
    learningBody: '项目设计的关键不是安排多少动作，而是是否把动作放进一个真正能持续改变行为与关系的机制里。',
  },
  {
    id: 'stakeholder_simulation',
    workspaceKey: 'project_design',
    title: '角色环境预演',
    description: '模拟受益人、家属、合作方和公众等不同角色，预演项目落地后的真实反应。',
    tags: ['角色视角', '落地反应'],
    focusPoints: ['受益人变化', '家属反应', '合作方配合度', '公众理解路径'],
    promptChips: ['模拟不同角色反应', '找阻力点', '补合作方动机'],
    learningTitle: '项目会落在关系网络里',
    learningBody: '任何项目都不是只作用于一个人，它会落进一张关系网络。设计方案时必须同时看周边角色会怎么动。',
  },
  {
    id: 'methodology_review',
    workspaceKey: 'project_design',
    title: '方法论对照',
    description: '拿当前方案和成熟方法论、机构历史项目及相似案例做对照。',
    tags: ['方法论', '案例对照'],
    focusPoints: ['理论框架匹配', '历史项目对照', '评估指标合理性', '关键缺口'],
    promptChips: ['对照相似案例', '补逻辑模型', '检查评估指标'],
    learningTitle: '方法论的价值在于提醒盲区',
    learningBody: '方法论不是为了让方案写得更学术，而是帮助团队更早发现因果链、指标和执行节奏中的盲区。',
  },
];

function parseInputContext(inputText: string) {
  const trimmed = inputText.trim();
  if (!trimmed.startsWith(INPUT_CONTEXT_START)) return null;
  const endIndex = trimmed.indexOf(INPUT_CONTEXT_END);
  if (endIndex === -1) return null;
  const metaBlock = trimmed.slice(INPUT_CONTEXT_START.length, endIndex).trim();
  const rawText = trimmed.slice(endIndex + INPUT_CONTEXT_END.length).trim();
  const meta = Object.fromEntries(
    metaBlock
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const splitIndex = line.indexOf('=');
        if (splitIndex === -1) return [line, ''];
        return [line.slice(0, splitIndex), line.slice(splitIndex + 1)];
      }),
  );
  return {
    workspaceKey: meta.workspaceKey as DiagnosisWorkspaceKey | undefined,
    modeId: meta.modeId as DiagnosisModeId | undefined,
    rawText,
  };
}

function buildPlatformDnaContextBlock(platformDnaContext: DiagnosisPlatformDnaContext) {
  return [
    PLATFORM_DNA_CONTEXT_START,
    JSON.stringify(platformDnaContext),
    PLATFORM_DNA_CONTEXT_END,
  ].join('\n');
}

function stripPlatformDnaContext(rawText: string) {
  const trimmed = rawText.trim();
  if (!trimmed.startsWith(PLATFORM_DNA_CONTEXT_START)) return rawText;
  const endIndex = trimmed.indexOf(PLATFORM_DNA_CONTEXT_END);
  if (endIndex === -1) return rawText;
  return trimmed.slice(endIndex + PLATFORM_DNA_CONTEXT_END.length).trim();
}

export function getDiagnosisWorkspace(key: DiagnosisWorkspaceKey) {
  return DIAGNOSIS_WORKSPACES.find((workspace) => workspace.key === key) || DIAGNOSIS_WORKSPACES[0];
}

export function getDiagnosisMode(id: DiagnosisModeId) {
  return DIAGNOSIS_MODES.find((mode) => mode.id === id) || DIAGNOSIS_MODES[0];
}

export function getWorkspaceModes(workspaceKey: DiagnosisWorkspaceKey) {
  return DIAGNOSIS_MODES.filter((mode) => mode.workspaceKey === workspaceKey);
}

export function getWorkspaceTemplate(templates: AnalysisTemplate[], workspaceKey: DiagnosisWorkspaceKey) {
  const workspace = getDiagnosisWorkspace(workspaceKey);
  return templates.find((template) => template.templateKey === workspace.templatePreferenceKey) || templates[0] || null;
}

export function formatDiagnosisRunTitle(workspaceKey: DiagnosisWorkspaceKey, modeId: DiagnosisModeId, title: string) {
  const workspace = getDiagnosisWorkspace(workspaceKey);
  const mode = getDiagnosisMode(modeId);
  return `【${workspace.label} / ${mode.title}】${title.trim()}`;
}

export function stripDiagnosisRunTitle(title: string) {
  return title.replace(/^【[^】]+】\s*/, '').trim();
}

export function buildDiagnosisInputText(
  workspaceKey: DiagnosisWorkspaceKey,
  modeId: DiagnosisModeId,
  rawText: string,
  platformDnaContext?: DiagnosisPlatformDnaContext | null,
) {
  const bodyParts = [
    INPUT_CONTEXT_START,
    `workspaceKey=${workspaceKey}`,
    `modeId=${modeId}`,
    INPUT_CONTEXT_END,
  ];
  if (platformDnaContext) {
    bodyParts.push(buildPlatformDnaContextBlock(platformDnaContext));
  }
  bodyParts.push(rawText.trim());
  return bodyParts.join('\n');
}

export function stripDiagnosisInputText(inputText: string) {
  const rawText = parseInputContext(inputText)?.rawText || inputText;
  return stripPlatformDnaContext(rawText);
}

export function inferDiagnosisWorkspace(run: AnalysisRun, template?: AnalysisTemplate | null): DiagnosisWorkspaceKey {
  const parsed = parseInputContext(run.inputText);
  if (parsed?.workspaceKey && DIAGNOSIS_WORKSPACES.some((workspace) => workspace.key === parsed.workspaceKey)) {
    return parsed.workspaceKey;
  }
  const title = run.title;
  const labelMatch = DIAGNOSIS_WORKSPACES.find((workspace) => title.includes(workspace.label));
  if (labelMatch) return labelMatch.key;
  if (template?.templateKey === 'fundraising') return 'fundraising';
  const haystack = `${title}\n${stripDiagnosisInputText(run.inputText)}`;
  if (/舆情|声明|回应|质疑|误读|发酵|公关|时间线/.test(haystack)) return 'public_opinion';
  return 'project_design';
}

export function inferDiagnosisMode(run: AnalysisRun, workspaceKey: DiagnosisWorkspaceKey): DiagnosisModeDefinition {
  const parsed = parseInputContext(run.inputText);
  if (parsed?.modeId) {
    const mode = DIAGNOSIS_MODES.find((item) => item.id === parsed.modeId);
    if (mode) return mode;
  }
  const title = run.title;
  const titleMatch = getWorkspaceModes(workspaceKey).find((mode) => title.includes(mode.title));
  if (titleMatch) return titleMatch;
  const haystack = `${title}\n${stripDiagnosisInputText(run.inputText)}`;
  if (workspaceKey === 'fundraising') {
    if (/月捐|续捐|留存/.test(haystack)) return getDiagnosisMode('monthly_donor');
    if (/基金会|CSR|企业|关键|捐赠人|提案/.test(haystack)) return getDiagnosisMode('key_person');
    return getDiagnosisMode('platform_fundraising');
  }
  if (workspaceKey === 'public_opinion') {
    if (/发布前|预演|公开前|消息前/.test(haystack)) return getDiagnosisMode('preflight_release');
    return getDiagnosisMode('incident_response');
  }
  if (/角色|家属|合作方|公众|反应/.test(haystack)) return getDiagnosisMode('stakeholder_simulation');
  if (/逻辑模型|指标|案例|方法论/.test(haystack)) return getDiagnosisMode('methodology_review');
  return getDiagnosisMode('project_mechanism');
}

export function getDiagnosisScene(workspaceKey: DiagnosisWorkspaceKey): DiagnosisScene {
  if (workspaceKey === 'public_opinion') return 'pr';
  if (workspaceKey === 'project_design') return 'project';
  return 'fundraising';
}

export function getDiagnosisAudienceType(modeId: DiagnosisModeId): DiagnosisAudienceType {
  switch (modeId) {
    case 'platform_fundraising':
    case 'monthly_donor':
      return 'donor';
    case 'key_person':
      return 'key_person';
    case 'incident_response':
      return 'public';
    case 'preflight_release':
      return 'media';
    case 'stakeholder_simulation':
      return 'partner';
    case 'project_mechanism':
    case 'methodology_review':
    default:
      return 'public';
  }
}

export function workspaceSupportsBettafish(workspaceKey: DiagnosisWorkspaceKey) {
  return workspaceKey === 'fundraising' || workspaceKey === 'public_opinion';
}
