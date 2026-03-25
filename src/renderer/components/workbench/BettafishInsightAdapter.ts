import type { BettaFishSignal } from '../../../shared/types';
import type { DiagnosisModeDefinition, DiagnosisWorkspaceKey } from './diagnosisConfig';

export type ExternalInsightDraft = {
  title: string;
  body: string;
  bullets: string[];
  why: string;
  learningTitle: string;
  learningBody: string;
  kind: 'critical' | 'learning';
  badge: string;
  basisSections: Array<'judgment' | 'analysis' | 'actions' | 'content'>;
  sourceTag: string;
};

export type ExternalSignalSummary = {
  heading: string;
  summary: string;
  firstAction: string;
  avoidAction: string;
  dangerSentence: string;
  interpretation: string;
};

export type RiskSentenceHighlight = {
  sentence: string;
  label: string;
  reason: string;
};

export type FundraisingJudgementCard = {
  key: 'audience' | 'trust' | 'evidence' | 'cta';
  label: string;
  verdict: string;
  detail: string;
  tone: 'good' | 'warn' | 'risk';
};

function normalizeText(value: string) {
  return value.replace(/\s+/g, ' ').replace(/^[•\-*\d.、）)\s]+/, '').trim();
}

function trimTitle(value: string, fallback: string) {
  const normalized = normalizeText(value).replace(/[。；：]$/, '');
  if (!normalized) return fallback;
  const short = normalized.length > 24 ? `${normalized.slice(0, 24)}…` : normalized;
  return short || fallback;
}

function buildFundraisingBullets(source: 'risk' | 'misunderstanding', point: string) {
  if (/情绪|卖惨|悲情|绑架|求|绝望|夸大/.test(point)) {
    return ['删掉过度煽情或求助式词汇', '补充具体事实、预算和支持路径'];
  }
  if (/可信|证据|细节|空泛|真诚|模板/.test(point)) {
    return ['补清楚数字、对象和用途拆解', '把抽象口号改成可核验事实'];
  }
  if (source === 'misunderstanding') {
    return ['提前补一句边界说明，减少被误读空间', '把容易引发联想的表述换成更具体的事实句'];
  }
  return ['把这条风险拆成更具体的事实表达', '检查是否需要补预算、对象或执行细节'];
}

function buildPublicOpinionBullets(source: 'risk' | 'misunderstanding', point: string) {
  if (/对抗|强硬|威胁|回怼|情绪/.test(point)) {
    return ['先降语气，把立场句改成事实句', '删除会激化情绪的判断性用词'];
  }
  if (/证据|时间线|事实|信息缺口|不完整/.test(point)) {
    return ['补完整时间线、主体和关键节点', '补第三方凭证或可核验事实'];
  }
  if (source === 'misunderstanding') {
    return ['预先回答最容易被误解的问题', '把外界可能错误理解的地方直接写明边界'];
  }
  return ['把争议点拆成事实、解释和边界三段', '检查是否有会被放大的句子需要提前降温'];
}

function buildProjectBullets(source: 'risk' | 'misunderstanding', point: string) {
  if (/作秀|表演|一次性|短期/.test(point)) {
    return ['补长期机制和后续维系路径', '减少只强调活动感的外部表达'];
  }
  if (source === 'misunderstanding') {
    return ['说明项目不是一次性行动的证据', '补清楚受益逻辑和合作关系'];
  }
  return ['补机制层解释，不只描述动作', '把项目价值落到关系和行为变化上'];
}

function buildBullets(workspaceKey: DiagnosisWorkspaceKey, source: 'risk' | 'misunderstanding', point: string) {
  if (workspaceKey === 'fundraising') return buildFundraisingBullets(source, point);
  if (workspaceKey === 'public_opinion') return buildPublicOpinionBullets(source, point);
  return buildProjectBullets(source, point);
}

function splitSourceSentences(sourceText: string) {
  return sourceText
    .replace(/\r\n/g, '\n')
    .split(/[\n。！？!?]/)
    .map((item) => normalizeText(item))
    .filter(Boolean)
    .slice(0, 12);
}

function hasAny(text: string, patterns: string[]) {
  return patterns.some((pattern) => text.includes(pattern));
}

function scoreDangerSentence(workspaceKey: DiagnosisWorkspaceKey, sentence: string) {
  const patterns =
    workspaceKey === 'public_opinion'
      ? ['造谣', '抹黑', '清者自清', '追究法律责任', '完全', '绝不', '必须']
      : workspaceKey === 'fundraising'
        ? ['求求', '绝望', '没有任何希望', '救救', '必须', '马上']
        : ['一次性', '作秀', '汇演', '送物资', '短期', '立刻'];
  return patterns.reduce((total, pattern) => total + (sentence.includes(pattern) ? 2 : 0), 0) + Math.min(sentence.length / 40, 1);
}

function pickDangerSentence(sourceText: string, workspaceKey: DiagnosisWorkspaceKey) {
  const sentences = splitSourceSentences(sourceText);
  if (!sentences.length) return '当前材料里还没有足够明确的单句风险，可优先检查标题和开头第一段。';
  const ranked = [...sentences].sort((left, right) => scoreDangerSentence(workspaceKey, right) - scoreDangerSentence(workspaceKey, left));
  return ranked[0];
}

function inferRiskSentenceReason(sentence: string, signal: BettaFishSignal | null, workspaceKey: DiagnosisWorkspaceKey) {
  if (workspaceKey === 'fundraising') {
    if (hasAny(sentence, ['求求', '绝望', '救救', '没有任何希望'])) return '情绪明显强于事实，容易先掉信任，再掉转化。';
    if (hasAny(sentence, ['5万', '50000', '10万', '元']) && !hasAny(sentence, ['每', '人', '天', '月', '学期', '用途', '预算'])) {
      return '金额出现了，但没有形成可量化的捐赠账本，看起来像空目标。';
    }
    if (hasAny(sentence, ['一直', '完全', '全部', '立刻', '必须'])) return '绝对化表述太重，会把倡议感推向夸大感。';
    if (signal && signal.misunderstandingPoints.some((point) => sentence.includes(point.slice(0, 4)))) return '这句话和外部误读点重合，容易被按另一套逻辑理解。';
    return '这句话更容易触发“先怀疑再判断”，不利于公域对象快速建立信任。';
  }
  if (workspaceKey === 'public_opinion') {
    if (hasAny(sentence, ['造谣', '抹黑', '清者自清', '追究法律责任'])) return '对抗性太强，会先激怒中立受众。';
    return '这句话更容易被放大成态度问题，而不是事实解释。';
  }
  return '这句话会让外界更快看到表达风险，而不是项目本身的机制价值。';
}

export function buildRiskSentenceHighlights(
  signal: BettaFishSignal | null,
  workspaceKey: DiagnosisWorkspaceKey,
  sourceText: string,
  limit = 3,
) {
  const sentences = splitSourceSentences(sourceText);
  if (!sentences.length) return [];
  const ranked = [...sentences]
    .map((sentence) => ({
      sentence,
      score: scoreDangerSentence(workspaceKey, sentence),
    }))
    .sort((left, right) => right.score - left.score)
    .slice(0, limit);

  return ranked.map(({ sentence }, index) => ({
    sentence,
    label: index === 0 ? '最高风险' : index === 1 ? '优先检查' : '建议复核',
    reason: inferRiskSentenceReason(sentence, signal, workspaceKey),
  })) satisfies RiskSentenceHighlight[];
}

export function buildFundraisingJudgementCards(
  signal: BettaFishSignal | null,
  sourceText: string,
  audienceLabel: string,
) {
  const normalizedText = sourceText.replace(/\s+/g, ' ');
  const combined = [...(signal?.riskPoints || []), ...(signal?.misunderstandingPoints || [])].join('；');
  const hasBudgetFigure = /\d/.test(normalizedText) && /元|万|预算|成本|单价|每人|每月|每天|学期/.test(normalizedText);
  const hasProjectEvidence = /受益|项目|学校|家庭|社区|患者|孩子|老人|服务|覆盖|完成|累计|落地/.test(normalizedText);
  const hasAction = /支持|捐|加入|成为|转发|扫码|点击|月捐|一起/.test(normalizedText);

  const audienceTone: FundraisingJudgementCard['tone'] =
    /误读|对象|平台|公域|不适合|代入/.test(combined) ? 'warn' : 'good';
  const trustTone: FundraisingJudgementCard['tone'] =
    /偏弱|较弱|不足|存疑/.test(signal?.credibility || '') || (!hasBudgetFigure && !hasProjectEvidence)
      ? 'risk'
      : /一般|中等/.test(signal?.credibility || '') || !hasProjectEvidence
        ? 'warn'
        : 'good';
  const evidenceTone: FundraisingJudgementCard['tone'] =
    hasBudgetFigure && hasProjectEvidence ? 'good' : hasBudgetFigure || hasProjectEvidence ? 'warn' : 'risk';
  const ctaTone: FundraisingJudgementCard['tone'] =
    hasAction && hasBudgetFigure ? 'good' : hasAction ? 'warn' : 'risk';

  return [
    {
      key: 'audience',
      label: '对象匹配',
      verdict: audienceTone === 'good' ? `基本对准 ${audienceLabel}` : `${audienceLabel} 的对象感还不够稳`,
      detail: audienceTone === 'good' ? '当前表达大体符合该对象的阅读入口。' : '这篇稿子还需要更明确地告诉对方：为什么此刻值得他支持。',
      tone: audienceTone,
    },
    {
      key: 'trust',
      label: '信任资产',
      verdict: trustTone === 'good' ? '信任基础基本能站住' : trustTone === 'warn' ? '信任感还需要再抬高' : '信任资产明显偏弱',
      detail: trustTone === 'good' ? '外部第一眼已能感受到一定可信度。' : trustTone === 'warn' ? '有意图，但证据和边界感还不够稳。' : '目前更容易先被怀疑，而不是先被打动。',
      tone: trustTone,
    },
    {
      key: 'evidence',
      label: '证据完整度',
      verdict: evidenceTone === 'good' ? '证据已经比较具体' : evidenceTone === 'warn' ? '证据有了，但还不成链' : '证据明显不够',
      detail: evidenceTone === 'good' ? '数字、对象和行动之间已有可理解的连接。' : evidenceTone === 'warn' ? '还需要把数字、用途和受益结果补成一条完整链路。' : '当前更多是情绪或口号，缺少可核验的项目事实。',
      tone: evidenceTone,
    },
    {
      key: 'cta',
      label: '行动号召',
      verdict: ctaTone === 'good' ? '行动号召比较清楚' : ctaTone === 'warn' ? '号召有了，但行动账本不够' : '行动号召还站不住',
      detail: ctaTone === 'good' ? '用户大体能理解为什么现在支持、支持后会发生什么。' : ctaTone === 'warn' ? '用户知道你想让他行动，但还不清楚自己的钱具体会产生什么改变。' : '现在更像在表达机构需求，还没有形成可执行的支持入口。',
      tone: ctaTone,
    },
  ] satisfies FundraisingJudgementCard[];
}

function summarizeInterpretation(signal: BettaFishSignal, workspaceKey: DiagnosisWorkspaceKey) {
  if (workspaceKey === 'public_opinion') {
    return `外部视角当前更容易感受到“${signal.emotion}”和“${signal.credibility}”。这意味着回应如果继续强调态度而不补事实，舆情更容易朝防御性解释发展。`;
  }
  if (workspaceKey === 'fundraising') {
    return `外部视角当前更容易感受到“${signal.emotion}”和“${signal.credibility}”。这说明文案若不补具体事实和用途，先丢掉的会是信任而不是转化。`;
  }
  return `外部视角当前更容易感受到“${signal.emotion}”和“${signal.credibility}”。这说明项目表达还需要补一层对外解释，而不只是内部逻辑。`;
}

function inferFirstAction(signal: BettaFishSignal, workspaceKey: DiagnosisWorkspaceKey) {
  const combined = [...signal.riskPoints, ...signal.misunderstandingPoints].join('；');
  if (workspaceKey === 'public_opinion') {
    if (/时间线|凭证|事实|证据|披露/.test(combined)) return '先补完整时间线、关键事实和第三方凭证，再决定回应顺序。';
    if (/威胁|对抗|心虚|傲慢|强硬/.test(combined) || /偏强烈/.test(signal.emotion)) return '先把态度句降温，改成事实、解释、边界三段式回应。';
    return '先把争议点拆成“事实是什么、为什么会这样、边界在哪里”三层再发。';
  }
  if (workspaceKey === 'fundraising') {
    if (/预算|用途|细节|可信|空泛/.test(combined) || /偏弱/.test(signal.credibility)) return '先补预算拆解、对象细节和执行路径，再优化情绪表达。';
    return '先删过度用力的情绪词，再把支持路径说具体。';
  }
  return '先把动作层描述补成机制层解释，再说明不同角色为什么会支持它。';
}

function inferAvoidAction(signal: BettaFishSignal, workspaceKey: DiagnosisWorkspaceKey) {
  const combined = [...signal.riskPoints, ...signal.misunderstandingPoints].join('；');
  if (workspaceKey === 'public_opinion') {
    if (/威胁|法律责任|强硬|对抗|傲慢|心虚/.test(combined)) return '先别用威胁性或回怼式语句，不要让中立受众先感到被教育。';
    return '先别急着表态自证清白，外界更在意新增事实而不是立场宣示。';
  }
  if (workspaceKey === 'fundraising') {
    if (/情绪|卖惨|绑架|求助|夸大/.test(combined)) return '先别继续加重悲情和求助式口吻，这会直接伤害可信度。';
    return '先别只喊目标金额，不说明钱怎么花。';
  }
  return '先别把项目价值全部压在一次活动效果上。';
}

export function buildExternalSignalSummary(
  signal: BettaFishSignal | null,
  workspaceKey: DiagnosisWorkspaceKey,
  sourceText: string,
) {
  if (!signal) return null;

  const heading =
    workspaceKey === 'public_opinion'
      ? '外部预演摘要'
      : workspaceKey === 'fundraising'
        ? '外部感受摘要'
        : '外部理解摘要';

  const summary =
    workspaceKey === 'public_opinion'
      ? '这层不是在判断你对不对，而是在判断外界第一眼会怎么理解这段回应。'
      : workspaceKey === 'fundraising'
        ? '这层不是在替你改稿，而是在判断公域对象第一眼会不会信。'
        : '这层不是在替你重写方案，而是在判断外界会怎样理解这个项目。';

  return {
    heading,
    summary,
    firstAction: inferFirstAction(signal, workspaceKey),
    avoidAction: inferAvoidAction(signal, workspaceKey),
    dangerSentence: pickDangerSentence(sourceText, workspaceKey),
    interpretation: summarizeInterpretation(signal, workspaceKey),
  } satisfies ExternalSignalSummary;
}

function buildLearning(workspaceKey: DiagnosisWorkspaceKey, mode: DiagnosisModeDefinition, source: 'risk' | 'misunderstanding') {
  if (workspaceKey === 'fundraising') {
    return source === 'risk'
      ? {
          learningTitle: '公域先判断可信，再判断是否值得支持',
          learningBody: '筹款文案最大的损失往往不是“不够感人”，而是让人觉得不真、过度用力或缺少边界。',
        }
      : {
          learningTitle: '误读空间会直接吃掉信任',
          learningBody: '当外界需要自己脑补你的意思时，最先流失的就是信任。提前补边界，比事后解释更划算。',
        };
  }
  if (workspaceKey === 'public_opinion') {
    return source === 'risk'
      ? {
          learningTitle: '回应首先处理的是公众判断依据',
          learningBody: '舆情中最危险的不是有人反对，而是你的回应没有减少外界的不确定感，反而放大了它。',
        }
      : {
          learningTitle: '误读不是噪音，是下一轮风险入口',
          learningBody: '当一句话存在多种读法时，传播系统通常会选择最容易激化情绪的那一种。',
        };
  }
  return {
    learningTitle: mode.learningTitle,
    learningBody: mode.learningBody,
  };
}

function draftFromPoint(
  workspaceKey: DiagnosisWorkspaceKey,
  mode: DiagnosisModeDefinition,
  source: 'risk' | 'misunderstanding',
  point: string,
): ExternalInsightDraft {
  const normalized = normalizeText(point);
  const learning = buildLearning(workspaceKey, mode, source);
  return {
    title: trimTitle(
      source === 'risk'
        ? `外部风险：${normalized}`
        : `外部误读：${normalized}`,
      source === 'risk' ? '外部风险提醒' : '外部误读提醒',
    ),
    body: normalized,
    bullets: buildBullets(workspaceKey, source, normalized),
    why:
      source === 'risk'
        ? `BettaFish 将这条表述识别为外部感知层面的主要风险，说明它在公域环境中更容易被质疑、反感或放大。`
        : `BettaFish 认为这条表述存在较高误读空间，说明不同对象可能会按另一套逻辑理解它，从而带来二次解释成本。`,
    learningTitle: learning.learningTitle,
    learningBody: learning.learningBody,
    kind: 'critical',
    badge: source === 'risk' ? '外部风险' : '误读预警',
    basisSections: ['analysis', 'actions'],
    sourceTag: '外部预演',
  };
}

export function deriveBettafishInsightDrafts(
  signal: BettaFishSignal | null,
  workspaceKey: DiagnosisWorkspaceKey,
  mode: DiagnosisModeDefinition,
) {
  if (!signal) return [];

  const drafts: ExternalInsightDraft[] = [];
  const seen = new Set<string>();

  for (const point of signal.riskPoints.slice(0, 2)) {
    const draft = draftFromPoint(workspaceKey, mode, 'risk', point);
    if (seen.has(draft.title)) continue;
    seen.add(draft.title);
    drafts.push(draft);
  }

  for (const point of signal.misunderstandingPoints.slice(0, 2)) {
    const draft = draftFromPoint(workspaceKey, mode, 'misunderstanding', point);
    if (seen.has(draft.title)) continue;
    seen.add(draft.title);
    drafts.push(draft);
  }

  return drafts;
}
