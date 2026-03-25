export type PlatformDnaProfileKey = 'tencent_gongyi' | 'douyin_gongyi';

export type PlatformDnaProfileDefinition = {
  key: PlatformDnaProfileKey;
  label: string;
  shortLabel: string;
  helper: string;
};

export type DiagnosisPlatformDnaContext = {
  key: PlatformDnaProfileKey;
  label: string;
  summary: string;
  corePreferences: string[];
  riskTriggers: string[];
  tonePreference?: string;
};

export type PlatformDnaProfileDocument = DiagnosisPlatformDnaContext & {
  fileName: string;
  filePath: string;
  markdownContent: string;
  updatedAt: string;
};

export const PLATFORM_DNA_STORAGE_KEY = 'yiyu.unified_workbench.platform_dna_docs.v1';
export const PLATFORM_DNA_SELECTED_KEY = 'yiyu.unified_workbench.platform_dna_selected.v1';

export const PLATFORM_DNA_PROFILES: PlatformDnaProfileDefinition[] = [
  {
    key: 'tencent_gongyi',
    label: '腾讯公益平台 DNA',
    shortLabel: '腾讯公益',
    helper: '适合沉淀平台公域捐赠人的判断习惯、信任触发点、雷区和语言偏好。',
  },
  {
    key: 'douyin_gongyi',
    label: '抖音公益平台 DNA',
    shortLabel: '抖音公益',
    helper: '适合沉淀短内容环境下的注意力阈值、情绪边界、可信证据与转化触发点。',
  },
];

const HEADING_PATTERNS = {
  corePreferences: /核心偏好|核心看重|看重什么|偏好|支持逻辑|判断口径|信任触发|支持理由/i,
  riskTriggers: /风险触发|敏感点|反感点|雷区|误读点|不能接受|警惕|风险/i,
  tonePreference: /语气|风格|语言偏好|表达方式|措辞|口吻/i,
};

function normalizeLine(value: string) {
  return value
    .replace(/^\s*(?:[-*•]|[0-9]+[.、）)]|[一二三四五六七八九十]+[、）)])\s*/, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function uniqueItems(items: string[], limit = 5) {
  const deduped: string[] = [];
  const seen = new Set<string>();
  items.forEach((item) => {
    const normalized = normalizeLine(item).replace(/[。；]$/, '');
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    deduped.push(normalized);
  });
  return deduped.slice(0, limit);
}

function splitMarkdownLines(markdownContent: string) {
  return markdownContent
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

function parseSections(markdownContent: string) {
  const lines = splitMarkdownLines(markdownContent);
  const sections: Record<string, string[]> = {
    intro: [],
    corePreferences: [],
    riskTriggers: [],
    tonePreference: [],
  };

  let currentSection: keyof typeof sections = 'intro';
  lines.forEach((line) => {
    const heading = line.replace(/^#+\s*/, '').replace(/[：:]\s*$/, '').trim();
    if (HEADING_PATTERNS.corePreferences.test(heading)) {
      currentSection = 'corePreferences';
      return;
    }
    if (HEADING_PATTERNS.riskTriggers.test(heading)) {
      currentSection = 'riskTriggers';
      return;
    }
    if (HEADING_PATTERNS.tonePreference.test(heading)) {
      currentSection = 'tonePreference';
      return;
    }
    sections[currentSection].push(line);
  });

  return sections;
}

function inferFallbackItems(lines: string[], pattern: RegExp, fallbackLimit = 4) {
  return uniqueItems(
    lines.filter((line) => pattern.test(line)).slice(0, fallbackLimit),
    fallbackLimit,
  );
}

function deriveSummary(lines: string[], corePreferences: string[], riskTriggers: string[], shortLabel: string) {
  const introLines = uniqueItems(lines, 4);
  if (introLines.length > 0) {
    return introLines.slice(0, 2).join('；');
  }
  if (corePreferences.length > 0 || riskTriggers.length > 0) {
    return `${shortLabel}更看重${corePreferences.slice(0, 2).join('、') || '真实感与可信证据'}，同时会对${riskTriggers.slice(0, 2).join('、') || '过度煽情与证据不足'}更敏感。`;
  }
  return `${shortLabel} DNA 已上传，建议补充“核心偏好 / 风险触发 / 语言风格”三个层面的判断。`;
}

export function parsePlatformDnaDocument(
  key: PlatformDnaProfileKey,
  markdownContent: string,
  fileName: string,
  filePath: string,
): PlatformDnaProfileDocument {
  const profile = PLATFORM_DNA_PROFILES.find((item) => item.key === key) || PLATFORM_DNA_PROFILES[0];
  const sections = parseSections(markdownContent);
  const allLines = splitMarkdownLines(markdownContent);
  const corePreferences = uniqueItems(sections.corePreferences, 5).length
    ? uniqueItems(sections.corePreferences, 5)
    : inferFallbackItems(allLines, /看重|偏好|信任|支持|更容易接受|判断依据/i, 5);
  const riskTriggers = uniqueItems(sections.riskTriggers, 5).length
    ? uniqueItems(sections.riskTriggers, 5)
    : inferFallbackItems(allLines, /敏感|反感|风险|误读|避免|警惕|不能接受|质疑/i, 5);
  const toneCandidates = uniqueItems(sections.tonePreference, 3).length
    ? uniqueItems(sections.tonePreference, 3)
    : inferFallbackItems(allLines, /语气|风格|表达|口吻|措辞/i, 3);
  const tonePreference = toneCandidates.join('；');
  const summary = deriveSummary(sections.intro, corePreferences, riskTriggers, profile.shortLabel);

  return {
    key,
    label: profile.label,
    summary,
    corePreferences,
    riskTriggers,
    tonePreference,
    fileName,
    filePath,
    markdownContent: markdownContent.trim(),
    updatedAt: new Date().toISOString(),
  };
}

export function buildPlatformDnaSummary(document: PlatformDnaProfileDocument | null | undefined) {
  if (!document) return undefined;
  return {
    corePreferences: document.corePreferences,
    riskTriggers: document.riskTriggers,
    tonePreference: document.tonePreference,
  };
}
