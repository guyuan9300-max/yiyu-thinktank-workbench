import type { DiagnosisProfileRecord } from '../../shared/types';

export type DiagnosisProfileGroupKey = 'platform_fundraising' | 'monthly_donor' | 'key_person';

export type DiagnosisProfileSelectionMap = Partial<Record<DiagnosisProfileGroupKey, string>>;

export type DiagnosisProfileGroupDefinition = {
  key: DiagnosisProfileGroupKey;
  label: string;
  helper: string;
  addButtonLabel: string;
  suggestedLabels?: string[];
};

export const DIAGNOSIS_PROFILE_STORAGE_KEY = 'yiyu.unified_workbench.diagnosis_profiles.v2';
export const DIAGNOSIS_PROFILE_SELECTION_KEY = 'yiyu.unified_workbench.diagnosis_profile_selection.v2';
const LEGACY_PLATFORM_STORAGE_KEY = 'yiyu.unified_workbench.platform_dna_docs.v1';
const LEGACY_PLATFORM_SELECTION_KEY = 'yiyu.unified_workbench.platform_dna_selected.v1';

export const DIAGNOSIS_PROFILE_GROUPS: DiagnosisProfileGroupDefinition[] = [
  {
    key: 'platform_fundraising',
    label: '筹款平台',
    helper: '上传平台判断底稿，沉淀平台公域捐赠人的偏好、风险触发点和语言边界。',
    addButtonLabel: '添加更多平台',
    suggestedLabels: ['腾讯公益', '抖音公益'],
  },
  {
    key: 'monthly_donor',
    label: '月捐人测试',
    helper: '上传不同类型月捐人的画像文档，例如新转化月捐人、老月捐人、续捐犹豫人群。',
    addButtonLabel: '添加月捐人类型',
  },
  {
    key: 'key_person',
    label: 'Key Person',
    helper: '上传基金会、企业 CSR、机构型捐赠人或关键个人的判断底稿。',
    addButtonLabel: '添加 Key Person',
  },
];

const HEADING_PATTERNS = {
  corePreferences: /核心偏好|核心看重|看重什么|偏好|支持逻辑|判断口径|信任触发|支持理由/i,
  riskTriggers: /风险触发|敏感点|反感点|雷区|误读点|不能接受|警惕|风险/i,
  tonePreference: /语气|风格|语言偏好|表达方式|措辞|口吻/i,
};

function createProfileId(groupKey: DiagnosisProfileGroupKey, label: string) {
  const normalized = label
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9_\u4e00-\u9fa5-]/g, '')
    .slice(0, 32);
  return `${groupKey}:${normalized || Math.random().toString(36).slice(2, 10)}`;
}

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

function deriveSummary(lines: string[], corePreferences: string[], riskTriggers: string[], label: string) {
  const introLines = uniqueItems(lines, 4);
  if (introLines.length > 0) return introLines.slice(0, 2).join('；');
  if (corePreferences.length > 0 || riskTriggers.length > 0) {
    return `${label}更看重${corePreferences.slice(0, 2).join('、') || '真实感与可信证据'}，同时会对${riskTriggers.slice(0, 2).join('、') || '过度情绪化与证据不足'}更敏感。`;
  }
  return `${label} 画像已上传，建议补充“核心偏好 / 风险触发 / 语言风格”三个层面的判断。`;
}

function safeParseJson<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function readStorage(key: string) {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(key);
}

function writeStorage(key: string, value: unknown) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(key, JSON.stringify(value));
}

function migrateLegacyPlatformProfiles(): DiagnosisProfileRecord[] {
  const legacyRaw = readStorage(LEGACY_PLATFORM_STORAGE_KEY);
  const legacyDocs = safeParseJson<Record<string, any>>(legacyRaw, {});
  const items = Object.values(legacyDocs)
    .filter((item) => item && typeof item === 'object')
    .map((item) => ({
      id: createProfileId('platform_fundraising', String(item.label || item.fileName || '平台画像')),
      groupKey: 'platform_fundraising' as const,
      label: String(item.label || item.fileName || '平台画像'),
      fileName: String(item.fileName || 'uploaded.md'),
      filePath: String(item.filePath || ''),
      markdownContent: String(item.markdownContent || ''),
      summary: String(item.summary || ''),
      corePreferences: Array.isArray(item.corePreferences) ? item.corePreferences.map(String).filter(Boolean) : [],
      riskTriggers: Array.isArray(item.riskTriggers) ? item.riskTriggers.map(String).filter(Boolean) : [],
      tonePreference: item.tonePreference ? String(item.tonePreference) : '',
      updatedAt: String(item.updatedAt || new Date().toISOString()),
    }));
  if (items.length > 0) {
    writeStorage(DIAGNOSIS_PROFILE_STORAGE_KEY, items);
  }
  const legacySelected = safeParseJson<string | null>(readStorage(LEGACY_PLATFORM_SELECTION_KEY), null);
  if (legacySelected) {
    const match = items.find((item) => item.label.includes(legacySelected.includes('douyin') ? '抖音' : '腾讯')) || items[0];
    if (match) {
      writeStorage(DIAGNOSIS_PROFILE_SELECTION_KEY, { platform_fundraising: match.id });
    }
  }
  return items;
}

export function parseDiagnosisProfileDocument(
  groupKey: DiagnosisProfileGroupKey,
  label: string,
  markdownContent: string,
  fileName: string,
  filePath: string,
  existingId?: string,
): DiagnosisProfileRecord {
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

  return {
    id: existingId || createProfileId(groupKey, label),
    groupKey,
    label: label.trim(),
    fileName,
    filePath,
    markdownContent: markdownContent.trim(),
    summary: deriveSummary(sections.intro, corePreferences, riskTriggers, label.trim()),
    corePreferences,
    riskTriggers,
    tonePreference: toneCandidates.join('；'),
    updatedAt: new Date().toISOString(),
  };
}

export function readDiagnosisProfilesFromStorage(): DiagnosisProfileRecord[] {
  const raw = readStorage(DIAGNOSIS_PROFILE_STORAGE_KEY);
  const profiles = safeParseJson<DiagnosisProfileRecord[]>(raw, []);
  if (profiles.length > 0) return profiles;
  return migrateLegacyPlatformProfiles();
}

export function writeDiagnosisProfilesToStorage(profiles: DiagnosisProfileRecord[]) {
  writeStorage(DIAGNOSIS_PROFILE_STORAGE_KEY, profiles);
}

export function readDiagnosisProfileSelection(): DiagnosisProfileSelectionMap {
  return safeParseJson<DiagnosisProfileSelectionMap>(readStorage(DIAGNOSIS_PROFILE_SELECTION_KEY), {});
}

export function writeDiagnosisProfileSelection(selection: DiagnosisProfileSelectionMap) {
  writeStorage(DIAGNOSIS_PROFILE_SELECTION_KEY, selection);
}

export function getDiagnosisProfilesByGroup(profiles: DiagnosisProfileRecord[], groupKey: DiagnosisProfileGroupKey) {
  const items = profiles.filter((item) => item.groupKey === groupKey);
  if (groupKey !== 'platform_fundraising') return items;
  const suggested = DIAGNOSIS_PROFILE_GROUPS.find((group) => group.key === groupKey)?.suggestedLabels || [];
  const seeded = suggested.map((label) => items.find((item) => item.label === label)).filter(Boolean) as DiagnosisProfileRecord[];
  const rest = items.filter((item) => !suggested.includes(item.label));
  return [...seeded, ...rest];
}

export function resolveSelectedDiagnosisProfile(
  profiles: DiagnosisProfileRecord[],
  selection: DiagnosisProfileSelectionMap,
  groupKey: DiagnosisProfileGroupKey,
) {
  const groupProfiles = getDiagnosisProfilesByGroup(profiles, groupKey);
  if (groupProfiles.length === 0) return null;
  return groupProfiles.find((item) => item.id === selection[groupKey]) || groupProfiles[0];
}

export function buildDiagnosisProfileSummary(profile: DiagnosisProfileRecord | null | undefined) {
  if (!profile) return undefined;
  return {
    corePreferences: profile.corePreferences,
    riskTriggers: profile.riskTriggers,
    tonePreference: profile.tonePreference,
  };
}
