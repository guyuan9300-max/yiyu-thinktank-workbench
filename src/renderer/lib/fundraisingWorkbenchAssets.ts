import type { FundraisingKnowledgeDocument, OrganizationRiskDnaDocument } from '../../shared/types';
import type { DiagnosisModeId } from '../components/workbench/diagnosisConfig';

export type { FundraisingKnowledgeDocument, OrganizationRiskDnaDocument } from '../../shared/types';

export const ORGANIZATION_RISK_DNA_STORAGE_KEY = 'yiyu.unified_workbench.organization_risk_dna.v1';
export const FUNDRAISING_KNOWLEDGE_STORAGE_KEY = 'yiyu.unified_workbench.fundraising_knowledge.v1';

const HEADING_PATTERNS = {
  summary: /一句话判断|摘要|概述|核心判断/i,
  coreRisks: /组织风险|核心风险|风险点|敏感点|高风险表达|不能说/i,
  sensitiveScenarios: /敏感场景|高危场景|触发点|容易被质疑|常见误读/i,
  tonePreference: /语气|风格|表达方式|口吻|措辞/i,
  scenes: /适用场景|使用场景|适用模式|场景/i,
  tags: /标签|主题|关键词/i,
  principles: /核心原则|推荐做法|判断原则|建议/i,
  riskSignals: /常见错误|风险信号|误区|预警/i,
};

function readStorage(key: string) {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(key);
}

function writeStorage(key: string, value: unknown) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(key, JSON.stringify(value));
}

function safeParseJson<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function splitMarkdownLines(markdownContent: string) {
  return markdownContent
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

function normalizeLine(value: string) {
  return value
    .replace(/^#+\s*/, '')
    .replace(/^\s*(?:[-*•]|[0-9]+[.、）)]|[一二三四五六七八九十]+[、）)])\s*/, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function uniqueItems(items: string[], limit = 6) {
  const deduped: string[] = [];
  const seen = new Set<string>();
  items.forEach((item) => {
    const normalized = normalizeLine(item).replace(/[。；：]$/, '');
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    deduped.push(normalized);
  });
  return deduped.slice(0, limit);
}

function parseSections(markdownContent: string) {
  const lines = splitMarkdownLines(markdownContent);
  const sections: Record<string, string[]> = {
    intro: [],
    summary: [],
    coreRisks: [],
    sensitiveScenarios: [],
    tonePreference: [],
    scenes: [],
    tags: [],
    principles: [],
    riskSignals: [],
  };

  let currentSection: keyof typeof sections = 'intro';
  lines.forEach((line) => {
    const heading = normalizeLine(line).replace(/[：:]\s*$/, '');
    if (HEADING_PATTERNS.summary.test(heading)) {
      currentSection = 'summary';
      return;
    }
    if (HEADING_PATTERNS.coreRisks.test(heading)) {
      currentSection = 'coreRisks';
      return;
    }
    if (HEADING_PATTERNS.sensitiveScenarios.test(heading)) {
      currentSection = 'sensitiveScenarios';
      return;
    }
    if (HEADING_PATTERNS.tonePreference.test(heading)) {
      currentSection = 'tonePreference';
      return;
    }
    if (HEADING_PATTERNS.scenes.test(heading)) {
      currentSection = 'scenes';
      return;
    }
    if (HEADING_PATTERNS.tags.test(heading)) {
      currentSection = 'tags';
      return;
    }
    if (HEADING_PATTERNS.principles.test(heading)) {
      currentSection = 'principles';
      return;
    }
    if (HEADING_PATTERNS.riskSignals.test(heading)) {
      currentSection = 'riskSignals';
      return;
    }
    sections[currentSection].push(line);
  });

  return sections;
}

function deriveSummary(lines: string[], fallback: string) {
  const items = uniqueItems(lines, 3);
  if (items.length) return items.slice(0, 2).join('；');
  return fallback;
}

function inferKnowledgeScenes(markdownContent: string, sceneItems: string[]) {
  const explicit = uniqueItems(sceneItems, 4);
  if (explicit.length) return explicit;
  const haystack = markdownContent.toLowerCase();
  const scenes: string[] = [];
  if (/平台|腾讯公益|抖音公益|公域/.test(haystack)) scenes.push('平台筹款');
  if (/月捐|续捐|留存|长期关系/.test(haystack)) scenes.push('月捐人测试');
  if (/基金会|csr|key person|关键对象|提案/.test(haystack)) scenes.push('Key Person');
  return uniqueItems(scenes, 4);
}

function inferKnowledgeTags(markdownContent: string, tagItems: string[]) {
  const explicit = uniqueItems(tagItems, 8);
  if (explicit.length) return explicit;
  const candidates = [
    '可信度',
    '预算拆解',
    '情绪风险',
    '平台规则',
    '透明度',
    'CTA',
    '月捐留存',
    'Key Person',
    '公域转化',
    '证据链',
  ];
  return uniqueItems(candidates.filter((tag) => markdownContent.includes(tag)), 8);
}

function makeKnowledgeId(title: string) {
  const normalized = title
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9_\u4e00-\u9fa5-]/g, '')
    .slice(0, 40);
  return `knowledge:${normalized || Math.random().toString(36).slice(2, 10)}`;
}

export function parseOrganizationRiskDnaDocument(markdownContent: string, fileName: string, filePath: string): OrganizationRiskDnaDocument {
  const sections = parseSections(markdownContent);
  const summary = deriveSummary(
    [...sections.summary, ...sections.intro],
    '组织风险 DNA 已上传，建议持续补充“组织高危风险 / 敏感场景 / 表达边界”三类信息。',
  );
  const coreRisks = uniqueItems(sections.coreRisks, 6);
  const sensitiveScenarios = uniqueItems(sections.sensitiveScenarios, 6);
  const tonePreference = uniqueItems(sections.tonePreference, 3).join('；');

  return {
    fileName,
    filePath,
    markdownContent: markdownContent.trim(),
    summary,
    coreRisks,
    sensitiveScenarios,
    tonePreference,
    updatedAt: new Date().toISOString(),
  };
}

export function readOrganizationRiskDnaFromStorage() {
  return safeParseJson<OrganizationRiskDnaDocument | null>(readStorage(ORGANIZATION_RISK_DNA_STORAGE_KEY), null);
}

export function writeOrganizationRiskDnaToStorage(document: OrganizationRiskDnaDocument | null) {
  writeStorage(ORGANIZATION_RISK_DNA_STORAGE_KEY, document);
}

export function parseFundraisingKnowledgeDocument(markdownContent: string, fileName: string, filePath: string): FundraisingKnowledgeDocument {
  const sections = parseSections(markdownContent);
  const title =
    normalizeLine(sections.intro[0] || '').replace(/^#+\s*/, '')
    || fileName.replace(/\.(md|markdown|txt|docx|pdf)$/i, '');
  const summary = deriveSummary(
    [...sections.summary, ...sections.intro.slice(1)],
    `${title} 已加入筹款知识库，建议补充适用场景、核心原则和常见错误，方便诊断时准确挂载。`,
  );

  return {
    id: makeKnowledgeId(title),
    title,
    fileName,
    filePath,
    markdownContent: markdownContent.trim(),
    summary,
    scenes: inferKnowledgeScenes(markdownContent, sections.scenes),
    tags: inferKnowledgeTags(markdownContent, sections.tags),
    principles: uniqueItems(sections.principles, 5),
    riskSignals: uniqueItems(sections.riskSignals, 5),
    updatedAt: new Date().toISOString(),
  };
}

export function readFundraisingKnowledgeFromStorage() {
  return safeParseJson<FundraisingKnowledgeDocument[]>(readStorage(FUNDRAISING_KNOWLEDGE_STORAGE_KEY), []);
}

export function writeFundraisingKnowledgeToStorage(entries: FundraisingKnowledgeDocument[]) {
  writeStorage(FUNDRAISING_KNOWLEDGE_STORAGE_KEY, entries);
}

export function buildOrganizationRiskDnaSummary(document: OrganizationRiskDnaDocument | null | undefined) {
  if (!document) return undefined;
  return {
    corePreferences: document.sensitiveScenarios,
    riskTriggers: document.coreRisks,
    tonePreference: document.tonePreference,
  };
}

function getModeSceneTokens(modeId: DiagnosisModeId) {
  if (modeId === 'platform_fundraising') return ['平台筹款', '平台', '公域转化', '腾讯公益', '抖音公益'];
  if (modeId === 'monthly_donor') return ['月捐人测试', '月捐', '续捐', '留存'];
  if (modeId === 'key_person') return ['Key Person', '关键对象', '基金会', 'CSR', '提案'];
  return [];
}

type MatchContext = {
  modeId: DiagnosisModeId;
  insightTitle: string;
  insightBody: string;
  insightBullets: string[];
  selectedProfileLabel?: string;
  organizationRiskSummary?: string;
};

export function matchFundraisingKnowledge(
  entries: FundraisingKnowledgeDocument[],
  context: MatchContext,
  limit = 2,
) {
  const haystack = [
    context.insightTitle,
    context.insightBody,
    ...context.insightBullets,
    context.selectedProfileLabel || '',
    context.organizationRiskSummary || '',
  ].join('\n').toLowerCase();
  const sceneTokens = getModeSceneTokens(context.modeId);

  return [...entries]
    .map((entry) => {
      let score = 0;
      entry.scenes.forEach((scene) => {
        if (sceneTokens.some((token) => scene.toLowerCase().includes(token.toLowerCase()))) score += 4;
      });
      entry.tags.forEach((tag) => {
        if (haystack.includes(tag.toLowerCase())) score += 3;
      });
      entry.riskSignals.forEach((signal) => {
        if (haystack.includes(signal.toLowerCase())) score += 3;
      });
      entry.principles.forEach((principle) => {
        if (haystack.includes(principle.toLowerCase())) score += 1.5;
      });
      if (context.selectedProfileLabel && entry.markdownContent.includes(context.selectedProfileLabel)) score += 2;
      if (/预算|金额|用途|成本/.test(haystack) && entry.markdownContent.includes('预算')) score += 2;
      if (/可信|证据|透明|真诚/.test(haystack) && /可信|证据|透明/.test(entry.markdownContent)) score += 2;
      if (/情绪|卖惨|绑架|误读/.test(haystack) && /情绪|卖惨|误读|风险/.test(entry.markdownContent)) score += 2;
      return { entry, score };
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, limit)
    .map((item) => item.entry);
}
