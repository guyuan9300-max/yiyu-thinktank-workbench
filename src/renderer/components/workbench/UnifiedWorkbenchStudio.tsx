import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowUp,
  BookOpenCheck,
  Check,
  CheckCircle2,
  ChevronRight,
  FileText,
  Info,
  LayoutList,
  ListTodo,
  MessageSquareQuote,
  MoreHorizontal,
  PlayCircle,
  Plus,
  Search,
  Sparkles,
  X,
} from 'lucide-react';

import type {
  AnalysisRun,
  AnalysisRunPayload,
  AnalysisTemplate,
  BettaFishSignal,
  CoachCaseRecord,
  CoachCardRecord,
  CoachReminderRule,
  DeepDnaRecord,
  DiagnosisEngineHealth,
  DiagnosisEngineMode,
  ExternalDiagnosisRequest,
  OrgWritingNorm,
  RunComparison,
} from '../../../shared/types';
import {
  type DiagnosisModeDefinition,
  type DiagnosisModeId,
  type DiagnosisWorkspaceKey,
  DIAGNOSIS_WORKSPACES,
  buildDiagnosisInputText,
  formatDiagnosisRunTitle,
  getDiagnosisAudienceType,
  getDiagnosisMode,
  getDiagnosisScene,
  getDiagnosisWorkspace,
  getWorkspaceModes,
  getWorkspaceTemplate,
  inferDiagnosisMode,
  inferDiagnosisWorkspace,
  stripDiagnosisInputText,
  stripDiagnosisRunTitle,
  workspaceSupportsBettafish,
} from './diagnosisConfig';
import {
  buildExternalSignalSummary,
  buildFundraisingJudgementCards,
  buildRiskSentenceHighlights,
  deriveBettafishInsightDrafts,
} from './BettafishInsightAdapter';
import {
  type DiagnosisProfileGroupKey,
  type DiagnosisProfileRecord,
  DIAGNOSIS_PROFILE_GROUPS,
  buildDiagnosisProfileSummary,
  getDiagnosisProfilesByGroup,
  readDiagnosisProfileSelection,
  resolveSelectedDiagnosisProfile,
  writeDiagnosisProfileSelection,
} from '../../lib/diagnosisProfiles';
import {
  buildOrganizationRiskDnaSummary,
  matchFundraisingKnowledge,
  type FundraisingKnowledgeDocument,
  type OrganizationRiskDnaDocument,
} from '../../lib/fundraisingWorkbenchAssets';

type WorkbenchInsight = {
  id: string;
  badge: string;
  kind: 'critical' | 'learning';
  title: string;
  body: string;
  bullets: string[];
  why: string;
  learningTitle: string;
  learningBody: string;
  basisSections: Array<'judgment' | 'analysis' | 'actions' | 'content'>;
  sourceTag?: string;
  coachCard?: CoachCardRecord;
};

type ProfileContext = {
  key: string;
  label: string;
  summary: string;
  corePreferences: string[];
  riskTriggers: string[];
  tonePreference?: string;
};

type UnifiedWorkbenchStudioProps = {
  templates: AnalysisTemplate[];
  runs: AnalysisRun[];
  defaultTitlePrefix: string;
  defaultHandbookTags?: string[];
  diagnosisProfiles: DiagnosisProfileRecord[];
  deepDnaLibrary: DeepDnaRecord[];
  organizationRiskDna: OrganizationRiskDnaDocument | null;
  fundraisingKnowledgeEntries: FundraisingKnowledgeDocument[];
  coachCases: CoachCaseRecord[];
  coachReminderRules: CoachReminderRule[];
  orgWritingNorms: OrgWritingNorm[];
  profileLibraryVersion?: number;
  onRunAnalysis: (payload: AnalysisRunPayload) => Promise<AnalysisRun>;
  onSaveLearningCard?: (payload: { title: string; summary: string; tags: string[] }) => Promise<void>;
  onGetDiagnosisEngineHealth: () => Promise<DiagnosisEngineHealth[]>;
  onRunBettafishDiagnosis: (payload: ExternalDiagnosisRequest) => Promise<BettaFishSignal>;
  onOpenProfileSettings?: (groupKey: DiagnosisProfileGroupKey, prefillLabel?: string) => void;
  onGetRunComparison: (runId: string) => Promise<RunComparison>;
  onSaveReminderRule: (payload: { title: string; knowledgeKey: string; issuePattern: string; message: string; modeIds: string[] }) => Promise<void>;
  onSaveWritingNorm: (payload: { title: string; description: string; instruction: string; modeIds: string[]; triggerKeywords: string[] }) => Promise<void>;
};

type InspectorTab = 'basis' | 'learning' | 'comparison' | 'mode';

const COMPLETED_STORAGE_KEY = 'yiyu.unified_workbench.completed_by_run.v2';
const SAVED_STORAGE_KEY = 'yiyu.unified_workbench.saved_learning.v1';
const ENGINE_MODE_STORAGE_KEY = 'yiyu.unified_workbench.engine_mode.v1';
const BETTAFISH_SIGNAL_STORAGE_KEY = 'yiyu.unified_workbench.bettafish_signals.v1';

const templateLabelMap: Record<string, string> = {
  fundraising: '筹款分析引擎',
  systemic: '系统诊断引擎',
};

function getTemplateLabel(template: AnalysisTemplate) {
  return templateLabelMap[template.templateKey] || template.title;
}

function getRunTemplate(run: AnalysisRun, templates: AnalysisTemplate[], fallback?: AnalysisTemplate | null) {
  return templates.find((template) => template.id === run.templateId) || fallback || null;
}

function formatRunTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function normalizeSentence(value: string) {
  return value
    .replace(/\r\n/g, '\n')
    .replace(/\s+/g, ' ')
    .replace(/^\s*(?:[-*•]|[0-9]+[.、）)]|[一二三四五六七八九十]+[、）)])\s*/, '')
    .trim();
}

function splitStructuredItems(value: string, limit = 6) {
  if (!value.trim()) return [];
  const normalized = value
    .replace(/\r\n/g, '\n')
    .replace(/([。；])/g, '$1\n')
    .replace(/\s+(?=\d+[.、）)])/g, '\n');
  const rawParts = normalized
    .split(/\n+/)
    .map((item) => normalizeSentence(item))
    .filter(Boolean);

  const deduped: string[] = [];
  const seen = new Set<string>();
  rawParts.forEach((item) => {
    const key = item.replace(/[，。；：]/g, '');
    if (!key || seen.has(key)) return;
    seen.add(key);
    deduped.push(item);
  });
  return deduped.slice(0, limit);
}

function trimTitle(value: string, fallback: string) {
  const normalized = normalizeSentence(value).replace(/[。；：]$/, '');
  if (!normalized) return fallback;
  const preferred = normalized.split(/[：:]/)[0].trim();
  const short = preferred.length >= 6 ? preferred : normalized;
  return short.length > 24 ? `${short.slice(0, 24)}…` : short;
}

function isCriticalInsight(value: string) {
  return /风险|高危|致命|不足|缺失|冲突|滞后|误读|脆弱|失衡|问题|卡点|阻力|失败|下滑|薄弱/.test(value);
}

function truncateText(value: string, limit = 110) {
  const normalized = normalizeSentence(value);
  if (normalized.length <= limit) return normalized;
  return `${normalized.slice(0, limit)}…`;
}

function readObjectStorage<T>(key: string, fallback: T) {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeObjectStorage(key: string, value: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage failures in Electron or privacy contexts.
  }
}

function modeToProfileGroup(modeId: DiagnosisModeId): DiagnosisProfileGroupKey | null {
  if (modeId === 'platform_fundraising') return 'platform_fundraising';
  if (modeId === 'monthly_donor') return 'monthly_donor';
  if (modeId === 'key_person') return 'key_person';
  return null;
}

function profileGroupToMode(groupKey: DiagnosisProfileGroupKey): DiagnosisModeId {
  if (groupKey === 'monthly_donor') return 'monthly_donor';
  if (groupKey === 'key_person') return 'key_person';
  return 'platform_fundraising';
}

function buildProfileContext(profile: DiagnosisProfileRecord | null | undefined) {
  if (!profile) return null;
  return {
    key: profile.id,
    label: profile.label,
    summary: profile.summary,
    corePreferences: profile.corePreferences,
    riskTriggers: profile.riskTriggers,
    tonePreference: profile.tonePreference,
  };
}

function buildOrganizationRiskContext(document: OrganizationRiskDnaDocument | null | undefined): ProfileContext | null {
  if (!document) return null;
  return {
    key: 'organization-risk',
    label: '组织风险 DNA',
    summary: document.summary,
    corePreferences: document.sensitiveScenarios,
    riskTriggers: document.coreRisks,
    tonePreference: document.tonePreference,
  };
}

function mergeProfileContexts(profileContext: ProfileContext | null, organizationRiskContext: ProfileContext | null) {
  if (!profileContext && !organizationRiskContext) return null;
  if (profileContext && !organizationRiskContext) return profileContext;
  if (!profileContext && organizationRiskContext) return organizationRiskContext;
  return {
    key: `${profileContext?.key || 'profile'}+${organizationRiskContext?.key || 'organization-risk'}`,
    label: `${profileContext?.label || '对象画像'} + ${organizationRiskContext?.label || '组织风险 DNA'}`,
    summary: [profileContext?.summary, organizationRiskContext?.summary].filter(Boolean).join('；'),
    corePreferences: Array.from(new Set([...(profileContext?.corePreferences || []), ...(organizationRiskContext?.corePreferences || [])])).slice(0, 8),
    riskTriggers: Array.from(new Set([...(profileContext?.riskTriggers || []), ...(organizationRiskContext?.riskTriggers || [])])).slice(0, 8),
    tonePreference: [profileContext?.tonePreference, organizationRiskContext?.tonePreference].filter(Boolean).join('；') || undefined,
  } satisfies ProfileContext;
}

function mergeDnaSummaries(
  profileSummary: ReturnType<typeof buildDiagnosisProfileSummary>,
  organizationRiskSummary: ReturnType<typeof buildOrganizationRiskDnaSummary>,
) {
  if (!profileSummary && !organizationRiskSummary) return undefined;
  return {
    corePreferences: Array.from(new Set([...(profileSummary?.corePreferences || []), ...(organizationRiskSummary?.corePreferences || [])])).slice(0, 8),
    riskTriggers: Array.from(new Set([...(profileSummary?.riskTriggers || []), ...(organizationRiskSummary?.riskTriggers || [])])).slice(0, 8),
    tonePreference: [profileSummary?.tonePreference, organizationRiskSummary?.tonePreference].filter(Boolean).join('；') || undefined,
  };
}

function deriveInsights(
  run: AnalysisRun,
  mode: DiagnosisModeDefinition,
  workspaceKey: DiagnosisWorkspaceKey,
  bettafishSignal: BettaFishSignal | null,
): WorkbenchInsight[] {
  const actionItems = splitStructuredItems(run.output.actions || '', 4);
  const judgmentItems = splitStructuredItems(run.output.judgment || '', 3);
  const analysisItems = splitStructuredItems(run.output.analysis || '', 4);
  const fallbackItems = splitStructuredItems(run.output.content || '', 3);
  const seeds = [
    ...judgmentItems.map((item, index) => ({ source: 'judgment' as const, text: item, index })),
    ...(actionItems.length ? actionItems : analysisItems.length ? analysisItems : fallbackItems).map((item, index) => ({
      source: 'action' as const,
      text: item,
      index,
    })),
  ];

  const deduped: WorkbenchInsight[] = [];
  const seenTitles = new Set<string>();
  const externalDrafts = deriveBettafishInsightDrafts(bettafishSignal, workspaceKey, mode);

  externalDrafts.forEach((draft, index) => {
    if (seenTitles.has(draft.title)) return;
    seenTitles.add(draft.title);
    deduped.push({
      id: `${run.id}-external-${index}`,
      badge: draft.badge,
      kind: draft.kind,
      title: draft.title,
      body: draft.body,
      bullets: draft.bullets,
      why: draft.why,
      learningTitle: draft.learningTitle,
      learningBody: draft.learningBody,
      basisSections: draft.basisSections,
      sourceTag: draft.sourceTag,
    });
  });

  seeds.forEach((seed, orderIndex) => {
    const body = seed.source === 'judgment'
      ? seed.text
      : analysisItems[seed.index] || judgmentItems[seed.index] || run.output.judgment || run.output.content || seed.text;
    const title = trimTitle(seed.text, `待办建议 ${orderIndex + 1}`);
    if (seenTitles.has(title)) return;
    seenTitles.add(title);
    const kind = seed.source === 'judgment' || isCriticalInsight(`${seed.text} ${body}`) ? 'critical' : 'learning';
    const bulletCandidates = splitStructuredItems(seed.source === 'action' ? seed.text : actionItems[seed.index] || seed.text, 3);
    deduped.push({
      id: `${run.id}-${seed.source}-${seed.index}`,
      badge: kind === 'critical' ? '高风险' : '必须优化',
      kind,
      title,
      body,
      bullets: bulletCandidates.length ? bulletCandidates : [seed.text],
      why: analysisItems[seed.index] || run.output.judgment || run.output.analysis || run.output.content || body,
      learningTitle: mode.learningTitle,
      learningBody: mode.learningBody,
      basisSections: seed.source === 'judgment' ? ['judgment', 'analysis'] : ['actions', 'analysis'],
    });
  });

  return deduped.slice(0, 6);
}

function deriveCoachInsights(
  run: AnalysisRun,
  mode: DiagnosisModeDefinition,
  workspaceKey: DiagnosisWorkspaceKey,
  bettafishSignal: BettaFishSignal | null,
) {
  if (workspaceKey !== 'fundraising' || !run.coachPayload?.cards.length) {
    return deriveInsights(run, mode, workspaceKey, bettafishSignal);
  }
  return run.coachPayload.cards.map((card, index) => ({
    id: `${run.id}:coach:${index}`,
    badge: index === 0 ? '首要修正' : '教练建议',
    kind: index === 0 || /风险|误读|反感|不清|不足/.test(`${card.issueWhat} ${card.whyImportant}`) ? 'critical' as const : 'learning' as const,
    title: card.insightTitle,
    body: card.issueWhat,
    bullets: [card.selfRewriteHint, card.learningAction].filter(Boolean),
    why: card.whyImportant,
    learningTitle: card.knowledgePointTitle || mode.learningTitle,
    learningBody: card.knowledgePointBody || mode.learningBody,
    basisSections: ['judgment', 'analysis', 'actions'],
    sourceTag: '教练卡',
    coachCard: card,
  }));
}

function scoreInsightPriority(insight: WorkbenchInsight, index: number) {
  let score = 100 - index * 4;
  if (insight.kind === 'critical') score += 120;
  if (insight.sourceTag) score += 40;
  if (/高风险|致命|风险|误读|脆弱|不足|缺失/.test(`${insight.badge} ${insight.title} ${insight.body}`)) score += 36;
  if (/预算|证据|可信|情绪|误读|时间线|边界/.test(`${insight.title} ${insight.body}`)) score += 18;
  return score;
}

function buildInsightBasis(run: AnalysisRun, insight: WorkbenchInsight, mode: DiagnosisModeDefinition) {
  const rawInput = stripDiagnosisInputText(run.inputText);
  const candidates = [
    {
      id: 'judgment',
      title: '本轮判断',
      text: run.output.judgment || insight.body,
    },
    {
      id: 'analysis',
      title: '分析拆解',
      text: run.output.analysis || insight.why,
    },
    {
      id: 'actions',
      title: '调整方向',
      text: run.output.actions || insight.bullets.join('；'),
    },
    {
      id: 'material',
      title: '原始材料',
      text: rawInput,
    },
  ].filter((item) => item.text.trim());

  const preferred = candidates.filter((item) => insight.basisSections.includes(item.id as 'judgment' | 'analysis' | 'actions' | 'content'));
  const ordered = preferred.length ? preferred : candidates.slice(0, 3);
  return [
    ...ordered.slice(0, 3).map((item) => ({
      id: item.id,
      title: item.title,
      text: truncateText(item.text, item.id === 'material' ? 90 : 120),
    })),
    {
      id: 'mode',
      title: '模式关注点',
      text: mode.focusPoints.join('；'),
    },
  ];
}

export function UnifiedWorkbenchStudio({
  templates,
  runs,
  defaultTitlePrefix,
  defaultHandbookTags = [],
  diagnosisProfiles,
  deepDnaLibrary,
  organizationRiskDna,
  fundraisingKnowledgeEntries,
  coachCases,
  coachReminderRules,
  orgWritingNorms,
  profileLibraryVersion = 0,
  onRunAnalysis,
  onSaveLearningCard,
  onGetDiagnosisEngineHealth,
  onRunBettafishDiagnosis,
  onOpenProfileSettings,
  onGetRunComparison,
  onSaveReminderRule,
  onSaveWritingNorm,
}: UnifiedWorkbenchStudioProps) {
  const initialWorkspace = useMemo(() => {
    if (!runs[0]) return DIAGNOSIS_WORKSPACES[0].key;
    return inferDiagnosisWorkspace(runs[0], getRunTemplate(runs[0], templates));
  }, [runs, templates]);

  const [activeWorkspaceKey, setActiveWorkspaceKey] = useState<DiagnosisWorkspaceKey>(initialWorkspace);
  const [activeModeId, setActiveModeId] = useState<DiagnosisModeId>(getWorkspaceModes(initialWorkspace)[0]?.id || 'platform_fundraising');
  const [selectedRunId, setSelectedRunId] = useState<string | null>(runs[0]?.id || null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'pending' | 'risk' | 'completed'>('pending');
  const [activeInsightId, setActiveInsightId] = useState<string | null>(null);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>('basis');
  const [completedByRun, setCompletedByRun] = useState<Record<string, string[]>>(() => readObjectStorage(COMPLETED_STORAGE_KEY, {}));
  const [savedInsightIds, setSavedInsightIds] = useState<string[]>(() => readObjectStorage(SAVED_STORAGE_KEY, []));
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isSubmittingRun, setIsSubmittingRun] = useState(false);
  const [followupDraft, setFollowupDraft] = useState('');
  const [isSubmittingFollowup, setIsSubmittingFollowup] = useState(false);
  const [isSavingInsight, setIsSavingInsight] = useState(false);
  const [engineMode] = useState<DiagnosisEngineMode>(() => {
    const stored = readObjectStorage<DiagnosisEngineMode | null>(ENGINE_MODE_STORAGE_KEY, null);
    return stored || 'standard';
  });
  const [engineHealth, setEngineHealth] = useState<DiagnosisEngineHealth[]>([]);
  const [bettafishSignalsByRun, setBettafishSignalsByRun] = useState<Record<string, BettaFishSignal>>(
    () => readObjectStorage(BETTAFISH_SIGNAL_STORAGE_KEY, {}),
  );
  const [profileSelection, setProfileSelection] = useState(() => readDiagnosisProfileSelection());
  const [isRunningBettafish, setIsRunningBettafish] = useState(false);
  const [runError, setRunError] = useState('');
  const [comparisonByRun, setComparisonByRun] = useState<Record<string, RunComparison>>({});
  const [isLoadingComparison, setIsLoadingComparison] = useState(false);
  const [inlineRewriteInsightId, setInlineRewriteInsightId] = useState<string | null>(null);
  const [inlineRewriteDraft, setInlineRewriteDraft] = useState('');
  const [isSubmittingInlineRewrite, setIsSubmittingInlineRewrite] = useState(false);
  const [referenceDraftByInsight, setReferenceDraftByInsight] = useState<Record<string, string>>({});
  const [actionBusyKey, setActionBusyKey] = useState<string | null>(null);
  const [runDraft, setRunDraft] = useState({
    title: defaultTitlePrefix || '诊断记录',
    inputText: '',
  });

  useEffect(() => {
    writeObjectStorage(COMPLETED_STORAGE_KEY, completedByRun);
  }, [completedByRun]);

  useEffect(() => {
    writeObjectStorage(SAVED_STORAGE_KEY, savedInsightIds);
  }, [savedInsightIds]);

  useEffect(() => {
    writeObjectStorage(ENGINE_MODE_STORAGE_KEY, engineMode);
  }, [engineMode]);

  useEffect(() => {
    writeObjectStorage(BETTAFISH_SIGNAL_STORAGE_KEY, bettafishSignalsByRun);
  }, [bettafishSignalsByRun]);

  useEffect(() => {
    setProfileSelection(readDiagnosisProfileSelection());
  }, [profileLibraryVersion]);

  const activeWorkspace = useMemo(
    () => getDiagnosisWorkspace(activeWorkspaceKey),
    [activeWorkspaceKey],
  );

  const workspaceModes = useMemo(
    () => getWorkspaceModes(activeWorkspaceKey),
    [activeWorkspaceKey],
  );

  useEffect(() => {
    if (!workspaceModes.some((mode) => mode.id === activeModeId)) {
      setActiveModeId(workspaceModes[0]?.id || 'platform_fundraising');
    }
  }, [activeModeId, workspaceModes]);

  const activeMode = useMemo(
    () => workspaceModes.find((mode) => mode.id === activeModeId) || workspaceModes[0] || getDiagnosisMode('platform_fundraising'),
    [activeModeId, workspaceModes],
  );
  const activeProfileGroup = useMemo(() => modeToProfileGroup(activeMode.id), [activeMode.id]);
  const selectedProfileForActiveMode = useMemo(
    () => (activeProfileGroup ? resolveSelectedDiagnosisProfile(diagnosisProfiles, profileSelection, activeProfileGroup) : null),
    [activeProfileGroup, diagnosisProfiles, profileSelection],
  );
  const selectedDeepDnaForActiveMode = useMemo(
    () => (
      activeProfileGroup
        ? deepDnaLibrary.find((item) => item.id === (selectedProfileForActiveMode?.deepDnaId || selectedProfileForActiveMode?.id))
          || deepDnaLibrary.find((item) => item.groupKey === activeProfileGroup && item.status === 'published')
          || null
        : null
    ),
    [activeProfileGroup, deepDnaLibrary, selectedProfileForActiveMode?.deepDnaId, selectedProfileForActiveMode?.id],
  );

  const activeTemplate = useMemo(
    () => getWorkspaceTemplate(templates, activeWorkspaceKey),
    [activeWorkspaceKey, templates],
  );

  const refreshEngineHealth = async () => {
    try {
      const nextHealth = await onGetDiagnosisEngineHealth();
      setEngineHealth(nextHealth);
    } catch {}
  };

  useEffect(() => {
    void refreshEngineHealth();
  }, []);

  const setSelectedProfileForGroup = (groupKey: DiagnosisProfileGroupKey, profileId: string) => {
    const nextSelection = {
      ...profileSelection,
      [groupKey]: profileId,
    };
    setProfileSelection(nextSelection);
    writeDiagnosisProfileSelection(nextSelection);
  };

  const activeWorkspaceRuns = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();
    return runs
      .filter((run) => inferDiagnosisWorkspace(run, getRunTemplate(run, templates, activeTemplate)) === activeWorkspaceKey)
      .filter((run) => inferDiagnosisMode(run, activeWorkspaceKey).id === activeMode.id)
      .filter((run) => {
        if (!normalizedQuery) return true;
        return (
          stripDiagnosisRunTitle(run.title).toLowerCase().includes(normalizedQuery)
          || stripDiagnosisInputText(run.inputText).toLowerCase().includes(normalizedQuery)
        );
      });
  }, [activeMode.id, activeTemplate, activeWorkspaceKey, runs, searchQuery, templates]);

  useEffect(() => {
    if (!activeWorkspaceRuns.length) {
      setSelectedRunId(null);
      return;
    }
    if (!selectedRunId || !activeWorkspaceRuns.some((run) => run.id === selectedRunId)) {
      setSelectedRunId(activeWorkspaceRuns[0].id);
    }
  }, [activeWorkspaceRuns, selectedRunId]);

  const selectedRun = useMemo(
    () => activeWorkspaceRuns.find((run) => run.id === selectedRunId) || activeWorkspaceRuns[0] || null,
    [activeWorkspaceRuns, selectedRunId],
  );
  const selectedMode = activeMode;

  useEffect(() => {
    setRunDraft((prev) => ({
      ...prev,
      title: prev.title.trim() ? prev.title : `${activeWorkspace.label}诊断`,
    }));
  }, [activeWorkspace.label]);

  const selectedRunTitle = selectedRun ? stripDiagnosisRunTitle(selectedRun.title) : '';
  const selectedRunInput = selectedRun ? stripDiagnosisInputText(selectedRun.inputText) : '';
  const selectedProfileSummary = useMemo(() => {
    if (activeWorkspaceKey !== 'fundraising') return undefined;
    if (selectedDeepDnaForActiveMode) {
      return {
        corePreferences: [...selectedDeepDnaForActiveMode.corePreferences, ...selectedDeepDnaForActiveMode.supportTriggers].slice(0, 8),
        riskTriggers: selectedDeepDnaForActiveMode.redFlags,
        tonePreference: selectedDeepDnaForActiveMode.voiceStyle.join('；'),
      };
    }
    return buildDiagnosisProfileSummary(selectedProfileForActiveMode);
  }, [activeWorkspaceKey, selectedDeepDnaForActiveMode, selectedProfileForActiveMode]);
  const organizationRiskSummary = useMemo(
    () => buildOrganizationRiskDnaSummary(activeWorkspaceKey === 'fundraising' ? organizationRiskDna : null),
    [activeWorkspaceKey, organizationRiskDna],
  );
  const selectedProfileContext = useMemo(() => {
    if (activeWorkspaceKey !== 'fundraising') return null;
    if (selectedDeepDnaForActiveMode) {
      return {
        key: selectedDeepDnaForActiveMode.id,
        label: selectedDeepDnaForActiveMode.label,
        summary: selectedDeepDnaForActiveMode.identitySummary,
        corePreferences: [...selectedDeepDnaForActiveMode.corePreferences, ...selectedDeepDnaForActiveMode.supportTriggers].slice(0, 8),
        riskTriggers: selectedDeepDnaForActiveMode.redFlags,
        tonePreference: selectedDeepDnaForActiveMode.voiceStyle.join('；') || undefined,
      };
    }
    return buildProfileContext(selectedProfileForActiveMode);
  }, [activeWorkspaceKey, selectedDeepDnaForActiveMode, selectedProfileForActiveMode]);
  const organizationRiskContext = useMemo(
    () => (activeWorkspaceKey === 'fundraising' ? buildOrganizationRiskContext(organizationRiskDna) : null),
    [activeWorkspaceKey, organizationRiskDna],
  );
  const effectiveDnaSummary = useMemo(
    () => mergeDnaSummaries(selectedProfileSummary, organizationRiskSummary),
    [organizationRiskSummary, selectedProfileSummary],
  );
  const effectiveProfileContext = useMemo(
    () => mergeProfileContexts(selectedProfileContext, organizationRiskContext),
    [organizationRiskContext, selectedProfileContext],
  );
  const organizationRiskSummaryText = useMemo(
    () => organizationRiskDna?.summary || '',
    [organizationRiskDna],
  );
  const activeProfileGroupDefinition = useMemo(
    () => (activeProfileGroup ? DIAGNOSIS_PROFILE_GROUPS.find((group) => group.key === activeProfileGroup) || null : null),
    [activeProfileGroup],
  );
  const fundraisingProfileCards = useMemo(() => {
    if (activeWorkspaceKey !== 'fundraising') return [];
    return DIAGNOSIS_PROFILE_GROUPS.map((group) => {
      const groupProfiles = getDiagnosisProfilesByGroup(diagnosisProfiles, group.key);
      const selectedProfile = resolveSelectedDiagnosisProfile(diagnosisProfiles, profileSelection, group.key);
      const suggestedLabels = group.suggestedLabels || [];
      const visibleProfiles = [
        ...suggestedLabels.map((label) => ({
          label,
          profile: groupProfiles.find((item) => item.label === label) || null,
          isSuggested: true,
        })),
        ...groupProfiles
          .filter((item) => !suggestedLabels.includes(item.label))
          .map((profile) => ({
            label: profile.label,
            profile,
            isSuggested: false,
          })),
      ].slice(0, group.key === 'platform_fundraising' ? 4 : 5);
      return {
        group,
        modeId: profileGroupToMode(group.key),
        isActive: activeMode.id === profileGroupToMode(group.key),
        profiles: visibleProfiles,
        selectedProfile,
      };
    });
  }, [activeMode.id, activeWorkspaceKey, diagnosisProfiles, profileSelection]);
  const currentSignalKey = selectedRun ? `${selectedRun.id}:${selectedMode.id}` : '';
  const bettafishHealth = useMemo(
    () => engineHealth.find((item) => item.engineKey === 'bettafish') || null,
    [engineHealth],
  );
  const bettafishSupported = workspaceSupportsBettafish(activeWorkspaceKey);
  const activeBettafishSignal = currentSignalKey ? bettafishSignalsByRun[currentSignalKey] || null : null;

  const insights = useMemo(
    () => (selectedRun ? deriveCoachInsights(selectedRun, selectedMode, activeWorkspaceKey, activeBettafishSignal) : []),
    [activeBettafishSignal, activeWorkspaceKey, selectedMode, selectedRun],
  );

  const completedSet = useMemo(
    () => new Set(selectedRun ? completedByRun[selectedRun.id] || [] : []),
    [completedByRun, selectedRun],
  );

  const visibleInsights = useMemo(() => {
    if (activeTab === 'risk') return insights.filter((item) => item.kind === 'critical' && !completedSet.has(item.id));
    if (activeTab === 'completed') return insights.filter((item) => completedSet.has(item.id));
    return insights.filter((item) => !completedSet.has(item.id));
  }, [activeTab, completedSet, insights]);

  const priorityInsights = useMemo(
    () => insights
      .filter((item) => !completedSet.has(item.id))
      .map((item, index) => ({
        item,
        score: scoreInsightPriority(item, index),
      }))
      .sort((left, right) => right.score - left.score)
      .slice(0, 3)
      .map((entry) => entry.item),
    [completedSet, insights],
  );

  useEffect(() => {
    if (!visibleInsights.length) {
      setActiveInsightId(null);
      return;
    }
    if (!activeInsightId || !visibleInsights.some((item) => item.id === activeInsightId)) {
      setActiveInsightId((activeTab === 'completed' ? visibleInsights[0] : priorityInsights[0] || visibleInsights[0]).id);
    }
  }, [activeInsightId, activeTab, priorityInsights, visibleInsights]);

  useEffect(() => {
    if (!selectedRun || !bettafishSupported || !currentSignalKey) return;
    if (activeBettafishSignal || isRunningBettafish || !selectedRunInput.trim()) return;
    if (bettafishHealth && bettafishHealth.status !== 'healthy') return;
    void runBettafishSignal();
  }, [
    activeBettafishSignal,
    bettafishHealth,
    bettafishSupported,
    currentSignalKey,
    isRunningBettafish,
    selectedRun,
    selectedRunInput,
  ]);

  const activeInsight = useMemo(
    () => visibleInsights.find((item) => item.id === activeInsightId) || visibleInsights[0] || insights[0] || null,
    [activeInsightId, insights, visibleInsights],
  );
  const activeCoachCases = useMemo(() => {
    if (!activeInsight?.coachCard?.caseIds?.length) return [];
    return coachCases.filter((entry) => activeInsight.coachCard?.caseIds.includes(entry.id));
  }, [activeInsight?.coachCard?.caseIds, coachCases]);
  const activeComparison = selectedRun ? comparisonByRun[selectedRun.id] || null : null;
  const relatedKnowledgeEntries = useMemo(() => {
    if (activeWorkspaceKey !== 'fundraising' || !activeInsight) return [];
    return matchFundraisingKnowledge(fundraisingKnowledgeEntries, {
      modeId: selectedMode.id,
      insightTitle: activeInsight.title,
      insightBody: activeInsight.body,
      insightBullets: activeInsight.bullets,
      selectedProfileLabel: selectedProfileForActiveMode?.label,
      organizationRiskSummary: organizationRiskSummaryText,
    });
  }, [
    activeInsight,
    activeWorkspaceKey,
    fundraisingKnowledgeEntries,
    organizationRiskSummaryText,
    selectedMode.id,
    selectedProfileForActiveMode?.label,
  ]);

  useEffect(() => {
    if (!selectedRun || activeWorkspaceKey !== 'fundraising') return;
    if (comparisonByRun[selectedRun.id]) return;
    setIsLoadingComparison(true);
    onGetRunComparison(selectedRun.id)
      .then((comparison) => {
        setComparisonByRun((prev) => ({ ...prev, [selectedRun.id]: comparison }));
      })
      .catch(() => undefined)
      .finally(() => setIsLoadingComparison(false));
  }, [activeWorkspaceKey, comparisonByRun, onGetRunComparison, selectedRun]);

  const summaryStats = useMemo(() => {
    const completedCount = insights.filter((item) => completedSet.has(item.id)).length;
    const pendingCount = Math.max(insights.length - completedCount, 0);
    const criticalCount = insights.filter((item) => item.kind === 'critical' && !completedSet.has(item.id)).length;
    const healthScore = Math.max(42, Math.min(96, 90 - criticalCount * 12 - pendingCount * 4 + completedCount * 5));
    return {
      pendingCount,
      criticalCount,
      referenceCount: splitStructuredItems(selectedRun?.output.analysis || '').length + splitStructuredItems(selectedRun?.output.actions || '').length,
      healthScore,
      completedCount,
    };
  }, [completedSet, insights, selectedRun?.output.actions, selectedRun?.output.analysis]);

  const moduleCards = useMemo(() => {
    const rawInput = selectedRun ? stripDiagnosisInputText(selectedRun.inputText) : '';
    const savedCount = insights.filter((item) => savedInsightIds.includes(item.id)).length;
    const externalSignalStatus = !bettafishSupported
      ? 'idle'
      : activeBettafishSignal
        ? 'ready'
        : bettafishHealth?.status === 'healthy'
          ? 'available'
          : 'idle';
    return [
      {
        key: 'material',
        title: '原稿装载',
        status: rawInput ? 'ready' : 'idle',
        detail: rawInput ? `${Math.min(rawInput.length, 999)} 字材料` : '等待输入材料',
      },
      {
        key: 'judgment',
        title: '问题判断',
        status: selectedRun?.output.judgment ? 'ready' : 'idle',
        detail: selectedRun?.output.judgment ? `${splitStructuredItems(selectedRun.output.judgment).length || 1} 条判断` : '等待诊断结果',
      },
      {
        key: 'actions',
        title: '调整方向',
        status: selectedRun?.output.actions ? 'ready' : 'idle',
        detail: selectedRun?.output.actions ? `${splitStructuredItems(selectedRun.output.actions).length || 1} 条方向` : '等待建议拆解',
      },
      {
        key: 'learning',
        title: '学习沉淀',
        status: savedCount > 0 ? 'ready' : insights.length ? 'available' : 'idle',
        detail: savedCount > 0 ? `已沉淀 ${savedCount} 条` : insights.length ? '可写入成长手册' : '等待学习卡',
      },
      {
        key: 'external_signal',
        title: '外部信号',
        status: externalSignalStatus,
        detail: !bettafishSupported
          ? '当前工作区暂未接入'
          : activeBettafishSignal
            ? `${activeBettafishSignal.riskPoints.length + activeBettafishSignal.misunderstandingPoints.length} 条外部提示`
            : bettafishHealth?.status === 'healthy'
              ? '可运行 BettaFish 诊断'
              : '等待外部引擎就绪',
      },
    ];
  }, [activeBettafishSignal, bettafishHealth?.status, bettafishSupported, insights, savedInsightIds, selectedRun]);

  const basisItems = useMemo(() => {
    const baseItems = selectedRun && activeInsight ? buildInsightBasis(selectedRun, activeInsight, selectedMode) : [];
    if (!activeBettafishSignal) return baseItems;
    return [
      {
        id: 'bettafish-risk',
        title: '外部风险信号',
        text: activeBettafishSignal.riskPoints.length ? activeBettafishSignal.riskPoints.join('；') : '本次没有返回明确风险点。',
      },
      {
        id: 'bettafish-misunderstanding',
        title: '外部误读信号',
        text: activeBettafishSignal.misunderstandingPoints.length
          ? activeBettafishSignal.misunderstandingPoints.join('；')
          : '本次没有返回明确误读点。',
      },
      ...baseItems,
    ];
  }, [activeBettafishSignal, activeInsight, selectedMode, selectedRun]);

  const externalSignalSummary = useMemo(
    () => buildExternalSignalSummary(activeBettafishSignal, activeWorkspaceKey, selectedRunInput),
    [activeBettafishSignal, activeWorkspaceKey, selectedRunInput],
  );
  const fundraisingJudgementCards = useMemo(
    () => activeWorkspaceKey === 'fundraising'
      ? buildFundraisingJudgementCards(activeBettafishSignal, selectedRunInput, selectedDeepDnaForActiveMode?.label || selectedProfileForActiveMode?.label || selectedMode.title)
      : [],
    [activeBettafishSignal, activeWorkspaceKey, selectedDeepDnaForActiveMode?.label, selectedMode.title, selectedProfileForActiveMode?.label, selectedRunInput],
  );
  const riskSentenceHighlights = useMemo(
    () => buildRiskSentenceHighlights(activeBettafishSignal, activeWorkspaceKey, selectedRunInput),
    [activeBettafishSignal, activeWorkspaceKey, selectedRunInput],
  );

  const toggleComplete = (insightId: string) => {
    if (!selectedRun) return;
    setCompletedByRun((prev) => {
      const current = new Set(prev[selectedRun.id] || []);
      if (current.has(insightId)) current.delete(insightId);
      else current.add(insightId);
      return { ...prev, [selectedRun.id]: Array.from(current) };
    });
  };

  const openCreateModal = () => {
    setRunError('');
    setRunDraft({
      title: `${activeWorkspace.label}诊断`,
      inputText: '',
    });
    setIsCreateModalOpen(true);
  };

  const submitRun = async () => {
    if (!activeTemplate || !runDraft.title.trim() || !runDraft.inputText.trim()) return;
    setIsSubmittingRun(true);
    try {
      const created = await onRunAnalysis({
        templateId: activeTemplate.id,
        title: formatDiagnosisRunTitle(activeWorkspaceKey, activeMode.id, runDraft.title.trim()),
        inputText: buildDiagnosisInputText(activeWorkspaceKey, activeMode.id, runDraft.inputText, effectiveProfileContext),
      });
      setRunError('');
      setSelectedRunId(created.id);
      setActiveTab('pending');
      setFollowupDraft('');
      setIsCreateModalOpen(false);
    } catch (error) {
      setRunError(error instanceof Error ? error.message : '诊断运行失败');
    } finally {
      setIsSubmittingRun(false);
    }
  };

  const submitFollowup = async () => {
    if (!selectedRun || !activeTemplate || !followupDraft.trim()) return;
    setIsSubmittingFollowup(true);
    try {
      const context = [
        `当前工作区：${activeWorkspace.label}`,
        `当前模式：${selectedMode.title}`,
        effectiveProfileContext
          ? `对象画像：${effectiveProfileContext.label}\n摘要：${effectiveProfileContext.summary}\n核心偏好：${effectiveProfileContext.corePreferences.join('；') || '未提炼'}\n风险触发：${effectiveProfileContext.riskTriggers.join('；') || '未提炼'}\n语气偏好：${effectiveProfileContext.tonePreference || '未提炼'}`
          : '',
        `模式重点：${selectedMode.focusPoints.join('；')}`,
        `原始材料：\n${selectedRunInput}`,
        `已有综述：\n${selectedRun.output.content}`,
        `已有判断：\n${selectedRun.output.judgment}`,
        activeInsight ? `当前待办：\n${activeInsight.title}\n${activeInsight.why}` : '',
        `追加要求：\n${followupDraft.trim()}`,
      ]
        .filter(Boolean)
        .join('\n\n');
      const created = await onRunAnalysis({
        templateId: activeTemplate.id,
        title: formatDiagnosisRunTitle(activeWorkspaceKey, selectedMode.id, `${selectedRunTitle} · 追问`),
        inputText: buildDiagnosisInputText(activeWorkspaceKey, selectedMode.id, context, effectiveProfileContext),
        parentRunId: selectedRun.id,
      });
      setRunError('');
      setSelectedRunId(created.id);
      setActiveTab('pending');
      setFollowupDraft('');
    } catch (error) {
      setRunError(error instanceof Error ? error.message : '追问运行失败');
    } finally {
      setIsSubmittingFollowup(false);
    }
  };

  const saveLearningCard = async () => {
    if (!activeInsight || !selectedRun || !onSaveLearningCard) return;
    setIsSavingInsight(true);
    try {
      await onSaveLearningCard({
        title: `${activeWorkspace.label} · ${activeInsight.title}`,
        summary: [
          `工作区：${activeWorkspace.label}`,
          `模式：${selectedMode.title}`,
          `诊断标题：${selectedRunTitle}`,
          `问题：${activeInsight.body}`,
          `调整方向：${activeInsight.bullets.join('；')}`,
          `为什么：${activeInsight.why}`,
          `学习点：${activeInsight.learningTitle}`,
          activeInsight.learningBody,
        ].join('\n\n'),
        tags: Array.from(new Set([...defaultHandbookTags, '测试工作台', activeWorkspace.handbookTag, selectedMode.title])),
      });
      setSavedInsightIds((prev) => (prev.includes(activeInsight.id) ? prev : [...prev, activeInsight.id]));
    } finally {
      setIsSavingInsight(false);
    }
  };

  const runBettafishSignal = async () => {
    if (!selectedRun || !bettafishSupported) return;
    setIsRunningBettafish(true);
    try {
      const result = await onRunBettafishDiagnosis({
        scene: getDiagnosisScene(activeWorkspaceKey),
        audienceType: getDiagnosisAudienceType(selectedMode.id),
        title: selectedRunTitle,
        content: selectedRunInput,
        workspaceLabel: activeWorkspace.label,
        modeLabel: selectedMode.title,
        focusPoints: selectedMode.focusPoints,
        dnaSummary: effectiveDnaSummary,
        analysisOptions: {
          engineMode,
          needEmotion: true,
          needRiskPoints: true,
          needMisunderstanding: true,
        },
      });
      setBettafishSignalsByRun((prev) => ({
        ...prev,
        [currentSignalKey]: result,
      }));
    } catch {
    } finally {
      setIsRunningBettafish(false);
    }
  };

  const startInlineRewrite = () => {
    if (!selectedRun || !activeInsight) return;
    setInlineRewriteInsightId(activeInsight.id);
    setInlineRewriteDraft(selectedRunInput);
  };

  const submitInlineRewrite = async () => {
    if (!selectedRun || !activeTemplate || !inlineRewriteDraft.trim()) return;
    setIsSubmittingInlineRewrite(true);
    try {
      const context = [
        `本次为基于上一版的改稿复诊。`,
        `上一版标题：${selectedRunTitle}`,
        `上一版结论：${selectedRun.output.content}`,
        activeInsight?.coachCard ? `当前优先修正：${activeInsight.coachCard.issueWhat}` : '',
      ].filter(Boolean).join('\n');
      const created = await onRunAnalysis({
        templateId: activeTemplate.id,
        title: formatDiagnosisRunTitle(activeWorkspaceKey, activeMode.id, `${selectedRunTitle} · 试改`),
        inputText: buildDiagnosisInputText(
          activeWorkspaceKey,
          activeMode.id,
          `${context}\n\n改写后的内容：\n${inlineRewriteDraft.trim()}`,
          effectiveProfileContext,
        ),
        parentRunId: selectedRun.id,
      });
      setSelectedRunId(created.id);
      setActiveTab('pending');
      setInlineRewriteInsightId(null);
      setInlineRewriteDraft('');
      setInspectorTab('comparison');
      setRunError('');
    } catch (error) {
      setRunError(error instanceof Error ? error.message : '试改复诊失败');
    } finally {
      setIsSubmittingInlineRewrite(false);
    }
  };

  const saveReminderRule = async () => {
    if (!activeInsight) return;
    setActionBusyKey('reminder');
    try {
      await onSaveReminderRule({
        title: `${selectedMode.title} · ${activeInsight.title}`,
        knowledgeKey: activeInsight.coachCard?.knowledgePointTitle || activeInsight.learningTitle,
        issuePattern: activeInsight.coachCard?.issueKey || activeInsight.title,
        message: `下次如果再次命中“${activeInsight.title}”，先检查：${activeInsight.bullets[0] || activeInsight.body}`,
        modeIds: [selectedMode.id],
      });
    } finally {
      setActionBusyKey(null);
    }
  };

  const saveWritingNorm = async () => {
    if (!activeInsight) return;
    setActionBusyKey('norm');
    try {
      await onSaveWritingNorm({
        title: `${selectedMode.title} · ${activeInsight.title}`,
        description: activeInsight.why,
        instruction: activeInsight.bullets[0] || activeInsight.body,
        modeIds: [selectedMode.id],
        triggerKeywords: [activeInsight.coachCard?.issueKey || activeInsight.title].filter(Boolean),
      });
    } finally {
      setActionBusyKey(null);
    }
  };

  const generateReferenceDraft = () => {
    if (!activeInsight) return;
    const draft = [
      `先把最关键的问题说清：${activeInsight.coachCard?.issueWhat || activeInsight.body}`,
      `然后按这个方向改：${activeInsight.coachCard?.selfRewriteHint || activeInsight.bullets[0] || '补足对象最关心的判断依据。'}`,
      `最后补一个让人更容易接受的动作或证据：${activeInsight.coachCard?.learningAction || activeInsight.learningBody}`,
    ].join('\n');
    setReferenceDraftByInsight((prev) => ({ ...prev, [activeInsight.id]: draft }));
  };

  return (
    <div className="mx-auto h-full w-full flex flex-col pt-6 pb-20 max-w-[1480px] px-5 lg:px-8">
      <div className="h-full min-h-[780px] overflow-hidden rounded-[30px] border border-black/[0.06] bg-white shadow-[0_30px_70px_-24px_rgba(15,23,42,0.28)] flex">
        <aside className="w-[292px] shrink-0 flex flex-col bg-[#F8F9FB] border-r border-black/[0.06]">
          <div className="px-4 pt-5 pb-3">
            <div className="flex items-center gap-2 rounded-[10px] border border-black/[0.05] bg-black/[0.03] px-3 py-2 focus-within:bg-white focus-within:ring-2 focus-within:ring-[#5B7BFE]/15">
              <Search className="h-4 w-4 text-black/35" />
              <input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="搜索诊断记录..."
                className="w-full bg-transparent text-[13px] text-black/80 placeholder:text-black/35 outline-none"
              />
            </div>
          </div>

          <div className="px-4 pb-3">
            <div className="rounded-[16px] bg-white border border-black/[0.05] p-4 shadow-[0_10px_30px_-20px_rgba(15,23,42,0.2)]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-black/35">诊断学习</p>
              <h2 className="mt-2 text-[18px] font-semibold tracking-tight text-black/90">{activeWorkspace.label}</h2>
              <p className="mt-2 text-[13px] font-medium text-black/55 leading-6">{activeWorkspace.subtitle}</p>
              <div className="mt-3 inline-flex rounded-[8px] bg-[#EEF2FF] px-2.5 py-1 text-[11px] font-semibold text-[#4A64D6]">
                当前引擎：{activeTemplate ? getTemplateLabel(activeTemplate) : '未配置'}
              </div>
            </div>
          </div>

          <div className="px-3 pb-3">
            <div className="flex items-center justify-between px-2 pb-2 text-[11px] font-semibold text-black/35 uppercase tracking-[0.18em]">
              <span>模式区</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </div>
            {activeWorkspaceKey === 'fundraising' ? (
              <div className="space-y-2">
                {fundraisingProfileCards.map((card) => (
                  <div
                    key={card.group.key}
                    className={`rounded-[16px] border px-3 py-3 transition-all ${
                      card.isActive
                        ? 'border-[#5B7BFE]/20 bg-[#EAF2FF] shadow-[inset_0_0_0_1px_rgba(91,123,254,0.12)]'
                        : 'border-black/[0.05] bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <button
                        type="button"
                        onClick={() => {
                          setActiveModeId(card.modeId);
                          setInspectorTab('mode');
                        }}
                        className="min-w-0 text-left"
                      >
                        <p className={`text-[13px] tracking-tight ${card.isActive ? 'font-semibold text-[#0A53CC]' : 'font-semibold text-black/88'}`}>{card.group.label}</p>
                      </button>
                      <button
                        type="button"
                        onClick={() => onOpenProfileSettings?.(card.group.key)}
                        className={`h-7 w-7 shrink-0 rounded-[8px] border transition-colors ${
                          card.isActive
                            ? 'border-[#C8D6FF] bg-white text-[#4A64D6] hover:bg-[#F5F8FF]'
                            : 'border-black/[0.08] bg-white text-black/45 hover:bg-black/[0.03] hover:text-black/75'
                        }`}
                        aria-label={`打开${card.group.label}设置`}
                      >
                        <Plus className="mx-auto h-4 w-4" />
                      </button>
                    </div>

                    <div className="mt-2">
                      <span
                        className={`inline-flex rounded-[8px] px-2.5 py-1 text-[10px] font-semibold ${
                          card.selectedProfile
                            ? card.isActive
                              ? 'bg-white text-[#0A53CC]'
                              : 'bg-black/[0.04] text-black/58'
                            : 'bg-black/[0.04] text-black/42'
                        }`}
                      >
                        {card.selectedProfile?.label || '待选择'}
                      </span>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {card.profiles.map((entry) => {
                        const isSelected = Boolean(entry.profile && card.selectedProfile?.id === entry.profile.id);
                        const isMissing = !entry.profile;
                        return (
                          <button
                            key={`${card.group.key}:${entry.label}`}
                            type="button"
                            onClick={() => {
                              setActiveModeId(card.modeId);
                              setInspectorTab('mode');
                              if (entry.profile) {
                                setSelectedProfileForGroup(card.group.key, entry.profile.id);
                                return;
                              }
                              onOpenProfileSettings?.(card.group.key, entry.label);
                            }}
                            className={`rounded-[8px] border px-2.5 py-1 text-[10px] font-semibold transition-colors ${
                              isSelected
                                ? 'border-transparent bg-white text-[#0A53CC] shadow-[0_1px_2px_rgba(15,23,42,0.08)]'
                                : isMissing
                                  ? 'border-dashed border-black/[0.1] bg-transparent text-black/42 hover:border-black/[0.18] hover:text-black/72'
                                  : 'border-transparent bg-black/[0.04] text-black/52 hover:bg-black/[0.07] hover:text-black/82'
                            }`}
                          >
                            {entry.label}
                          </button>
                        );
                      })}
                      <button
                        type="button"
                        onClick={() => onOpenProfileSettings?.(card.group.key)}
                        className="rounded-[8px] border border-dashed border-black/[0.1] px-2.5 py-1 text-[10px] font-semibold text-black/45 hover:border-black/[0.18] hover:text-black/72"
                      >
                        添加更多
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                {workspaceModes.map((mode) => {
                  const isActive = mode.id === activeMode.id;
                  return (
                    <button
                      key={mode.id}
                      type="button"
                      onClick={() => {
                        setActiveModeId(mode.id);
                        if (!selectedRun) setInspectorTab('mode');
                      }}
                      className={`w-full rounded-[14px] border px-3 py-3 text-left transition-all ${
                        isActive
                          ? 'border-[#5B7BFE]/20 bg-[#EAF2FF] shadow-[inset_0_0_0_1px_rgba(91,123,254,0.12)]'
                          : 'border-black/[0.05] bg-white hover:bg-black/[0.02]'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className={`text-[13px] tracking-tight ${isActive ? 'font-semibold text-[#0A53CC]' : 'font-medium text-black/88'}`}>{mode.title}</p>
                        </div>
                        {isActive && <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-[#007AFF]" />}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {mode.tags.map((tag) => (
                          <span key={tag} className="rounded-[6px] bg-black/[0.04] px-2 py-0.5 text-[10px] font-semibold text-black/45">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="flex-1 overflow-y-auto px-3 pb-4">
            <div className="flex items-center justify-between px-2 pb-2 text-[11px] font-semibold text-black/35 uppercase tracking-[0.18em]">
              <span>最近诊断</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </div>
            <div className="space-y-1">
              {activeWorkspaceRuns.map((run) => {
                const isActive = selectedRun?.id === run.id;
                const runTemplate = getRunTemplate(run, templates, activeTemplate);
                const runMode = inferDiagnosisMode(run, activeWorkspaceKey);
                const runInsights = deriveCoachInsights(run, runMode, activeWorkspaceKey, null);
                return (
                  <button
                    key={run.id}
                    type="button"
                    onClick={() => {
                      setSelectedRunId(run.id);
                      setActiveModeId(runMode.id);
                      setActiveTab('pending');
                      setInspectorTab('basis');
                    }}
                    className={`w-full rounded-[12px] px-3 py-3 text-left transition-all ${
                      isActive ? 'bg-[#EAF2FF] text-[#0A53CC] shadow-[inset_0_0_0_1px_rgba(91,123,254,0.15)]' : 'hover:bg-black/[0.04] text-black/70'
                    }`}
                  >
                    <div className="flex items-start gap-2.5">
                      <div className={`mt-0.5 h-[15px] w-[15px] rounded-[4px] border flex items-center justify-center ${isActive ? 'border-[#5B7BFE] bg-white' : 'border-black/10 bg-white'}`}>
                        <ListTodo className={`h-3 w-3 ${isActive ? 'text-[#5B7BFE]' : 'text-black/30'}`} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <p className={`truncate text-[13px] tracking-tight ${isActive ? 'font-semibold' : 'font-medium'}`}>{stripDiagnosisRunTitle(run.title)}</p>
                          {isActive && <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-[#007AFF]" />}
                        </div>
                        <p className="mt-1 text-[11px] text-black/40">{formatRunTimestamp(run.createdAt)}</p>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          <span className="rounded-[6px] bg-black/[0.04] px-2 py-0.5 text-[10px] font-semibold text-black/45">
                            {runMode.title}
                          </span>
                          <span className="rounded-[6px] bg-black/[0.04] px-2 py-0.5 text-[10px] font-semibold text-black/45">
                            {runTemplate ? getTemplateLabel(runTemplate) : '诊断'}
                          </span>
                          <span className="rounded-[6px] bg-black/[0.04] px-2 py-0.5 text-[10px] font-semibold text-black/45">
                            {runInsights.length} 条建议
                          </span>
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}

              {activeWorkspaceRuns.length === 0 && (
                <div className="rounded-[12px] border border-dashed border-black/[0.08] bg-white px-4 py-8 text-center text-[12px] text-black/35">
                  当前模式下还没有诊断记录。
                </div>
              )}
            </div>
          </div>
        </aside>

        <div className="flex-1 min-w-0 flex flex-col bg-white">
          <div className="h-[58px] flex items-center justify-between px-6 border-b border-black/[0.05] bg-white/90 backdrop-blur-md shrink-0">
            <div className="flex items-center gap-3">
              <span className="text-[16px] font-semibold tracking-tight text-black/90">诊断学习</span>
              <div className="flex rounded-[10px] bg-black/[0.04] p-[3px] shadow-[inset_0_1px_1px_rgba(0,0,0,0.03)]">
                {DIAGNOSIS_WORKSPACES.map((workspace) => {
                  const isActive = workspace.key === activeWorkspaceKey;
                  return (
                    <button
                      key={workspace.key}
                      type="button"
                      onClick={() => {
                        setActiveWorkspaceKey(workspace.key);
                        setInspectorTab('mode');
                      }}
                      className={`px-4 py-1.5 text-[12px] font-medium rounded-[8px] transition-all ${
                        isActive ? 'bg-white text-black/90 shadow-[0_1px_3px_rgba(15,23,42,0.12)]' : 'text-black/45 hover:text-black/80'
                      }`}
                    >
                      {workspace.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button type="button" className="h-[30px] w-[30px] rounded-[8px] text-black/40 hover:bg-black/[0.04] hover:text-black/80 transition-colors">
                <MoreHorizontal className="h-4 w-4 mx-auto" />
              </button>
              <button
                type="button"
                onClick={openCreateModal}
                className="h-[34px] rounded-[10px] bg-[#5B7BFE] px-4 text-[12px] font-semibold text-white shadow-[0_10px_24px_-10px_rgba(91,123,254,0.48)] hover:bg-[#4A6BE6] transition-colors"
              >
                新建诊断
              </button>
            </div>
          </div>

          {runError && (
            <div className="mx-6 mt-5 rounded-[14px] border border-[#FF5A4F]/15 bg-[#FFF4F2] px-4 py-3 text-[12px] text-[#C63F35] flex items-start gap-2">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span className="leading-6">{runError}</span>
            </div>
          )}

          {!selectedRun ? (
            <div className="flex-1 flex items-center justify-center px-10">
              <div className="max-w-[560px] text-center">
                <div className="mx-auto h-14 w-14 rounded-[16px] bg-[#EAF2FF] text-[#5B7BFE] flex items-center justify-center">
                  <Sparkles className="h-6 w-6" />
                </div>
                <h2 className="mt-5 text-[24px] font-semibold tracking-tight text-black/90">{activeWorkspace.label}</h2>
                <p className="mt-3 text-[13px] leading-7 text-black/45">{activeMode.description}</p>
                <div className="mt-5 flex flex-wrap justify-center gap-2">
                  {activeMode.focusPoints.map((item) => (
                    <span key={item} className="rounded-[8px] bg-black/[0.04] px-3 py-1.5 text-[11px] font-medium text-black/58">
                      {item}
                    </span>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={openCreateModal}
                  className="mt-6 h-[40px] rounded-[12px] bg-[#5B7BFE] px-5 text-[13px] font-semibold text-white shadow-[0_14px_28px_-14px_rgba(91,123,254,0.55)]"
                >
                  开始第一条诊断
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="flex-1 overflow-y-auto">
                <div className="px-8 pt-8 pb-6">
                  <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
                    {[
                      { label: '待处理建议', value: summaryStats.pendingCount.toString() },
                      { label: '高风险项', value: summaryStats.criticalCount.toString() },
                      { label: '参考拆解', value: summaryStats.referenceCount.toString() },
                      { label: '诊断健康度', value: `${summaryStats.healthScore}%` },
                    ].map((item) => (
                      <div key={item.label} className="rounded-[16px] border border-black/[0.05] bg-[#F8F9FB] px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-black/35">{item.label}</p>
                        <p className="mt-2 text-[22px] font-semibold tracking-tight text-black/88">{item.value}</p>
                      </div>
                    ))}
                  </div>

                  <div className="mt-6 grid grid-cols-2 xl:grid-cols-4 gap-3">
                    {moduleCards.map((module) => (
                      <div key={module.key} className="rounded-[16px] border border-black/[0.05] bg-white px-4 py-3 shadow-[0_8px_20px_-18px_rgba(15,23,42,0.25)]">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-[12px] font-semibold text-black/75">{module.title}</p>
                          <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                            module.status === 'ready'
                              ? 'bg-emerald-50 text-emerald-600'
                              : module.status === 'available'
                                ? 'bg-amber-50 text-amber-600'
                                : 'bg-black/[0.05] text-black/40'
                          }`}>
                            {module.status === 'ready' ? '已就绪' : module.status === 'available' ? '可沉淀' : '待补充'}
                          </span>
                        </div>
                        <p className="mt-2 text-[12px] leading-6 text-black/48">{module.detail}</p>
                      </div>
                    ))}
                  </div>

                  <div className="mt-6 rounded-[18px] border border-black/[0.05] bg-[#F8F9FB] p-5">
                    <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-black/40">
                      <MessageSquareQuote className="h-3.5 w-3.5" />
                      待分析内容
                    </div>
                    <p className="mt-4 border-l-[3px] border-black/[0.08] pl-4 text-[14px] leading-8 text-black/80 font-medium whitespace-pre-wrap">
                      {selectedRunInput}
                    </p>
                  </div>

                  {activeWorkspaceKey === 'fundraising' && (
                    <div className="mt-6 grid gap-3 xl:grid-cols-[1.25fr_1fr]">
                      <div className="rounded-[18px] border border-black/[0.05] bg-white p-5 shadow-[0_10px_30px_-24px_rgba(15,23,42,0.2)]">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-black/35">筹款判断</div>
                            <p className="mt-2 text-[13px] leading-7 text-black/52 font-medium">
                              先看对象、信任、证据和行动号召四个环节哪一环最先拖住转化。
                            </p>
                          </div>
                          <div className="rounded-[10px] bg-[#EEF2FF] px-3 py-2 text-[11px] font-semibold text-[#4A64D6]">
                            {selectedDeepDnaForActiveMode?.label || selectedProfileForActiveMode?.label || selectedMode.title}
                          </div>
                        </div>
                        <div className="mt-4 grid gap-3 md:grid-cols-2">
                          {fundraisingJudgementCards.map((card) => (
                            <div key={card.key} className="rounded-[16px] border border-black/[0.05] bg-[#F8F9FB] px-4 py-4">
                              <div className="flex items-center justify-between gap-3">
                                <div className="text-[12px] font-semibold text-black/68">{card.label}</div>
                                <span className={`rounded-[7px] px-2 py-0.5 text-[10px] font-semibold ${
                                  card.tone === 'good'
                                    ? 'bg-emerald-50 text-emerald-600'
                                    : card.tone === 'warn'
                                      ? 'bg-amber-50 text-amber-600'
                                      : 'bg-rose-50 text-rose-600'
                                }`}>
                                  {card.tone === 'good' ? '基本稳' : card.tone === 'warn' ? '需补强' : '高优先'}
                                </span>
                              </div>
                              <div className="mt-3 text-[16px] font-semibold tracking-tight text-black/88">{card.verdict}</div>
                              <p className="mt-2 text-[12.5px] leading-6 text-black/56">{card.detail}</p>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="rounded-[18px] border border-[#FFDFC8] bg-[#FFF9F5] p-5 shadow-[0_10px_30px_-24px_rgba(124,45,18,0.18)]">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#B45A20]">最危险的几句话</div>
                        <p className="mt-2 text-[13px] leading-7 text-[#8A5A3B] font-medium">
                          这些句子最容易先伤害可信度或制造误读，建议优先处理。
                        </p>
                        <div className="mt-4 space-y-3">
                          {riskSentenceHighlights.map((item, index) => (
                            <div key={`${item.sentence}-${index}`} className="rounded-[14px] border border-[#F5D9C4] bg-white/88 px-4 py-4">
                              <div className="flex items-center justify-between gap-3">
                                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#B45A20]">{item.label}</div>
                                <div className="text-[11px] font-semibold text-[#C56A15]">句子 {index + 1}</div>
                              </div>
                              <p className="mt-2 text-[13px] leading-7 text-[#8A4E2F] font-semibold">“{item.sentence}”</p>
                              <p className="mt-2 text-[12.5px] leading-6 text-[#8A5A3B]">{item.reason}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {priorityInsights.length > 0 && (
                    <div className="mt-6 rounded-[18px] border border-[#5B7BFE]/12 bg-gradient-to-br from-[#F6F8FF] to-[#EEF4FF] p-5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.9)]">
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#4A64D6]">最重要的三条修改</div>
                          <p className="mt-2 text-[13px] leading-7 text-[#3353A5]/82 font-medium">
                            先把这三处改稳，再看其他建议，收益最高。
                          </p>
                        </div>
                        <div className="rounded-[10px] bg-white/88 px-3 py-2 text-[11px] font-semibold text-[#4A64D6]">
                          共 {priorityInsights.length} 条优先修改
                        </div>
                      </div>

                      <div className="mt-4 grid gap-3 xl:grid-cols-3">
                        {priorityInsights.map((insight, index) => {
                          const isActive = activeInsight?.id === insight.id;
                          return (
                            <button
                              key={insight.id}
                              type="button"
                              onClick={() => {
                                setActiveTab('pending');
                                setActiveInsightId(insight.id);
                                setInspectorTab('basis');
                              }}
                              className={`rounded-[16px] border px-4 py-4 text-left transition-all ${
                                isActive
                                  ? 'border-[#5B7BFE]/28 bg-white shadow-[0_14px_30px_-24px_rgba(91,123,254,0.55)]'
                                  : 'border-white/70 bg-white/84 hover:bg-white'
                              }`}
                            >
                              <div className="flex items-center justify-between gap-3">
                                <div className="text-[22px] font-semibold tracking-tight text-[#4A64D6]">0{index + 1}</div>
                                <div className="flex items-center gap-2">
                                  {insight.sourceTag && (
                                    <span className="rounded-[6px] bg-[#EEF2FF] px-2 py-0.5 text-[10px] font-semibold text-[#4A64D6]">
                                      {insight.sourceTag}
                                    </span>
                                  )}
                                  <span className={`rounded-[6px] px-2 py-0.5 text-[10px] font-semibold ${
                                    insight.kind === 'critical' ? 'bg-[#FF5A4F]/10 text-[#FF5A4F]' : 'bg-[#5B7BFE]/10 text-[#5B7BFE]'
                                  }`}>
                                    {insight.badge}
                                  </span>
                                </div>
                              </div>
                              <div className="mt-3 text-[15px] font-semibold tracking-tight text-black/88">{insight.title}</div>
                              <p className="mt-2 text-[12.5px] leading-6 text-black/58">{truncateText(insight.why, 88)}</p>
                              {insight.bullets[0] && (
                                <div className="mt-3 rounded-[10px] bg-[#F8F9FB] px-3 py-3 text-[12px] leading-6 text-black/62">
                                  <span className="font-semibold text-black/78">先改：</span>
                                  {insight.bullets[0]}
                                </div>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {activeWorkspaceKey === 'fundraising' && inlineRewriteInsightId === activeInsight?.id && (
                    <div className="mt-6 rounded-[18px] border border-[#0A53CC]/12 bg-white p-5 shadow-[0_10px_30px_-24px_rgba(15,23,42,0.2)]">
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#0A53CC]">我来试改</div>
                          <p className="mt-2 text-[13px] leading-7 text-black/58 font-medium">
                            先自己改一版，再让系统按上一版对照复诊。新版会自动挂到当前 run 的下一版。
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            setInlineRewriteInsightId(null);
                            setInlineRewriteDraft('');
                          }}
                          className="rounded-[10px] border border-black/[0.08] px-3 py-2 text-[12px] font-semibold text-black/55"
                        >
                          收起
                        </button>
                      </div>
                      <textarea
                        value={inlineRewriteDraft}
                        onChange={(event) => setInlineRewriteDraft(event.target.value)}
                        placeholder="在这里直接改你的新版本..."
                        className="mt-4 min-h-[220px] w-full rounded-[18px] border border-black/[0.08] bg-[#F8F9FB] p-4 text-[14px] leading-7 text-black/82 outline-none focus:border-[#5B7BFE]/40 focus:bg-white"
                      />
                      <div className="mt-4 flex items-center justify-between gap-4">
                        <div className="text-[12px] text-black/42">
                          提交后会生成带上一版关系的新 run，并在右侧“对比”里显示结果变化和学习变化。
                        </div>
                        <button
                          type="button"
                          onClick={() => void submitInlineRewrite()}
                          disabled={!inlineRewriteDraft.trim() || isSubmittingInlineRewrite}
                          className="inline-flex items-center gap-2 rounded-[10px] bg-[#0A53CC] px-5 py-3 text-[13px] font-semibold text-white shadow-[0_12px_24px_-14px_rgba(10,83,204,0.55)] disabled:opacity-60"
                        >
                          {isSubmittingInlineRewrite ? <Sparkles className="h-4 w-4 animate-pulse" /> : <PenTool className="h-4 w-4" />}
                          提交试改并复诊
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                <div className="border-b border-black/[0.05] px-8 flex gap-6">
                  {[
                    { key: 'pending' as const, label: '全部建议' },
                    { key: 'risk' as const, label: '高风险项' },
                    { key: 'completed' as const, label: '已完成' },
                  ].map((tab) => (
                    <button
                      key={tab.key}
                      type="button"
                      onClick={() => setActiveTab(tab.key)}
                      className={`pb-3 text-[13px] relative tracking-tight ${
                        activeTab === tab.key ? 'text-[#0A53CC] font-semibold' : 'text-black/48 hover:text-black/80 font-medium'
                      }`}
                    >
                      {tab.label}
                      {activeTab === tab.key && <span className="absolute bottom-0 left-0 h-[2px] w-full rounded-full bg-[#007AFF]" />}
                    </button>
                  ))}
                </div>

                <div className="py-2">
                  {visibleInsights.map((insight) => {
                    const isActive = activeInsight?.id === insight.id;
                    const isCompleted = completedSet.has(insight.id);
                    const isSaved = savedInsightIds.includes(insight.id);
                    return (
                      <div
                        key={insight.id}
                        onClick={() => {
                          setActiveInsightId(insight.id);
                          setInspectorTab('basis');
                        }}
                        className={`group flex items-start gap-3.5 px-8 py-4 cursor-pointer border-b border-black/[0.03] transition-colors ${
                          isActive ? 'bg-[#EAF2FF]/60' : 'hover:bg-[#F8F9FB]'
                        } ${isCompleted ? 'opacity-45 grayscale' : ''}`}
                      >
                        <div
                          className="mt-[3px] shrink-0"
                          onClick={(event) => {
                            event.stopPropagation();
                            toggleComplete(insight.id);
                          }}
                        >
                          <div className={`h-[18px] w-[18px] rounded-[5px] border-[1.5px] flex items-center justify-center transition-colors ${
                            isCompleted
                              ? 'border-black/20 bg-black/20 text-white'
                              : insight.kind === 'critical'
                                ? 'border-[#FF5A4F]/60 bg-white hover:bg-[#FF5A4F]/8'
                                : 'border-[#5B7BFE]/45 bg-white hover:bg-[#5B7BFE]/10'
                          }`}>
                            {isCompleted && <Check className="h-3 w-3" strokeWidth={3} />}
                          </div>
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2.5">
                          <div className={`truncate text-[15px] tracking-tight ${
                              isCompleted ? 'line-through text-black/45' : isActive ? 'text-[#0A53CC] font-semibold' : 'text-black/88 font-medium'
                            }`}>
                              {insight.title}
                          </div>
                          {insight.sourceTag && (
                            <span className="rounded-[6px] bg-[#EEF2FF] px-2 py-0.5 text-[10px] font-semibold text-[#4A64D6]">
                              {insight.sourceTag}
                            </span>
                          )}
                          {!isCompleted && (
                              <span className={`rounded-[6px] px-2 py-0.5 text-[10px] font-semibold ${
                                insight.kind === 'critical' ? 'bg-[#FF5A4F]/10 text-[#FF5A4F]' : 'bg-[#5B7BFE]/10 text-[#5B7BFE]'
                              }`}>
                                {insight.badge}
                              </span>
                            )}
                            {isSaved && (
                              <span className="rounded-[6px] bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-600">
                                已沉淀
                              </span>
                            )}
                          </div>
                          <p className={`mt-2 text-[13px] leading-7 ${isCompleted ? 'line-through text-black/38' : 'text-black/52'}`}>
                            {insight.body}
                          </p>
                        </div>
                      </div>
                    );
                  })}

                  {visibleInsights.length === 0 && (
                    <div className="px-8 py-16 text-center text-[13px] text-black/35">
                      当前筛选下没有可显示的待办。
                    </div>
                  )}
                </div>
              </div>

              <div className="px-6 py-4 border-t border-black/[0.05] bg-white/92 backdrop-blur-md shrink-0">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <div className="text-[12px] font-semibold text-black/52">继续追问当前模式</div>
                  <div className="text-[11px] text-black/38">{selectedMode.title}</div>
                </div>
                <div className="flex items-center gap-2 rounded-[12px] border border-black/[0.06] bg-[#F8F9FB] p-1.5 focus-within:bg-white focus-within:ring-2 focus-within:ring-[#5B7BFE]/15">
                  <Sparkles className="ml-2 h-[18px] w-[18px] shrink-0 text-[#5B7BFE]" />
                  <input
                    value={followupDraft}
                    onChange={(event) => setFollowupDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault();
                        void submitFollowup();
                      }
                    }}
                    placeholder="继续围绕当前模式追问，例如：谁最可能误读这句话？"
                    className="flex-1 bg-transparent border-none outline-none text-[13px] text-black/90 placeholder:text-black/38 font-medium"
                  />
                  <button
                    type="button"
                    onClick={() => void submitFollowup()}
                    disabled={!followupDraft.trim() || isSubmittingFollowup}
                    className="h-[32px] w-[32px] rounded-[8px] bg-[#007AFF] text-white flex items-center justify-center shadow-[0_6px_16px_-8px_rgba(0,122,255,0.45)] disabled:opacity-60"
                  >
                    {isSubmittingFollowup ? <Sparkles className="h-4 w-4 animate-pulse" /> : <ArrowUp className="h-4 w-4" strokeWidth={2.2} />}
                  </button>
                </div>
                <div className="mt-2.5 flex gap-2 overflow-x-auto no-scrollbar">
                  {selectedMode.promptChips.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => setFollowupDraft(prompt)}
                      className="rounded-[7px] bg-black/[0.03] px-3 py-1 text-[11px] font-medium text-black/58 hover:bg-black/[0.06] hover:text-black/86 transition-colors"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        <aside className="w-[388px] shrink-0 flex flex-col border-l border-black/[0.06] bg-white shadow-[-10px_0_30px_rgba(15,23,42,0.03)]">
          <div className="h-[56px] flex items-center justify-between px-6 border-b border-black/[0.05] bg-white shrink-0">
            <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.18em] text-black/35">
              <Info className="h-4 w-4" />
              检查器
            </div>
            <button type="button" className="h-[30px] w-[30px] rounded-[8px] text-black/40 hover:bg-black/[0.04] hover:text-black/80 transition-colors">
              <MoreHorizontal className="h-4 w-4 mx-auto" />
            </button>
          </div>

          {activeInsight ? (
            <>
              <div className="border-b border-black/[0.05] px-6 py-4">
                <h2 className="text-[26px] font-semibold tracking-tight text-black/92 leading-[1.25]">{activeInsight.title}</h2>
                <div className="mt-3 flex items-center gap-4 text-[12px] font-medium">
                  <span className={`inline-flex items-center gap-1.5 ${completedSet.has(activeInsight.id) ? 'text-emerald-600' : 'text-orange-500'}`}>
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {completedSet.has(activeInsight.id) ? '已完成' : '待处理'}
                  </span>
                  {activeInsight.sourceTag && (
                    <span className="inline-flex items-center gap-1.5 text-[#4A64D6]">
                      <Sparkles className="h-3.5 w-3.5" />
                      {activeInsight.sourceTag}
                    </span>
                  )}
                  {savedInsightIds.includes(activeInsight.id) && (
                    <span className="inline-flex items-center gap-1.5 text-[#0A53CC]">
                      <BookOpenCheck className="h-3.5 w-3.5" />
                      已沉淀
                    </span>
                  )}
                </div>
                <div className="mt-4 flex rounded-[10px] bg-black/[0.04] p-[3px]">
                  {[
                    { key: 'basis' as const, label: '依据' },
                    { key: 'learning' as const, label: '学习' },
                    { key: 'comparison' as const, label: '对比' },
                    { key: 'mode' as const, label: '模式说明' },
                  ].map((tab) => (
                    <button
                      key={tab.key}
                      type="button"
                      onClick={() => setInspectorTab(tab.key)}
                      className={`flex-1 rounded-[8px] px-3 py-1.5 text-[12px] font-medium transition-all ${
                        inspectorTab === tab.key ? 'bg-white text-black/88 shadow-[0_1px_3px_rgba(15,23,42,0.12)]' : 'text-black/45 hover:text-black/80'
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto px-7 py-6 no-scrollbar">
                {inspectorTab === 'basis' && (
                  <div className="space-y-4">
                    {externalSignalSummary && (
                      <div className="rounded-[18px] border border-[#5B7BFE]/12 bg-gradient-to-br from-[#F6F8FF] to-[#EEF4FF] p-5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.9)]">
                        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#4A64D6]">
                          <Sparkles className="h-3.5 w-3.5" />
                          {externalSignalSummary.heading}
                        </div>
                        <p className="mt-2 text-[13px] leading-7 text-[#3353A5]/82 font-medium">
                          {externalSignalSummary.summary}
                        </p>
                        <div className="mt-4 grid gap-3">
                          <div className="rounded-[12px] bg-white/88 px-4 py-3">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#4A64D6]/72">当前感受</div>
                            <p className="mt-1.5 text-[13px] leading-7 text-[#28489B] font-medium">{externalSignalSummary.interpretation}</p>
                          </div>
                          <div className="rounded-[12px] bg-white/88 px-4 py-3">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#4A64D6]/72">先补什么</div>
                            <p className="mt-1.5 text-[13px] leading-7 text-[#28489B] font-medium">{externalSignalSummary.firstAction}</p>
                          </div>
                          <div className="rounded-[12px] bg-white/88 px-4 py-3">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#4A64D6]/72">先别说什么</div>
                            <p className="mt-1.5 text-[13px] leading-7 text-[#28489B] font-medium">{externalSignalSummary.avoidAction}</p>
                          </div>
                          <div className="rounded-[12px] border border-[#FFB7B1]/35 bg-[#FFF7F6] px-4 py-3">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#C7564E]">最危险句子</div>
                            <p className="mt-1.5 text-[13px] leading-7 text-[#8C423B] font-medium">“{externalSignalSummary.dangerSentence}”</p>
                          </div>
                        </div>
                      </div>
                    )}
                    {basisItems.map((item) => (
                      <div key={item.id} className="rounded-[14px] border border-black/[0.05] bg-[#F8F9FB] p-4">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-black/35">{item.title}</div>
                        <p className="mt-2 text-[13px] leading-7 text-black/62 font-medium">{item.text}</p>
                      </div>
                    ))}
                  </div>
                )}

                {inspectorTab === 'learning' && (
                  <div className="space-y-6">
                    {activeWorkspaceKey === 'fundraising' && activeInsight.coachCard ? (
                      <>
                        <div className="rounded-[14px] border border-black/[0.05] bg-[#F8F9FB] p-4">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-black/35">问题是什么</div>
                          <p className="mt-2 text-[13px] leading-7 text-black/72 font-medium">{activeInsight.coachCard.issueWhat}</p>
                        </div>

                        <div className="rounded-[14px] border border-black/[0.05] bg-[#F8F9FB] p-4">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-black/35">为什么重要</div>
                          <p className="mt-2 text-[13px] leading-7 text-black/72 font-medium">{activeInsight.coachCard.whyImportant}</p>
                        </div>

                        <div className="rounded-[16px] border border-[#5B7BFE]/10 bg-gradient-to-br from-[#EAF2FF] to-[#F5F8FF] p-5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.8)]">
                          <div className="flex items-center gap-2 text-[#0A53CC]">
                            <Sparkles className="h-4 w-4" />
                            <div className="text-[13px] font-bold tracking-tight">背后的知识点：{activeInsight.coachCard.knowledgePointTitle}</div>
                          </div>
                          <p className="mt-3 text-[12.5px] leading-7 text-[#0A53CC]/85 font-medium">
                            {activeInsight.coachCard.knowledgePointBody}
                          </p>
                        </div>

                        <div>
                          <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-black/35">参考好案例</div>
                          <div className="space-y-3">
                            {(activeCoachCases.length ? activeCoachCases : coachCases.slice(0, 1)).map((entry) => (
                              <div key={entry.id} className="rounded-[14px] border border-black/[0.05] bg-white px-4 py-4 shadow-[0_8px_20px_-18px_rgba(15,23,42,0.2)]">
                                <div className="flex items-center gap-2 text-[#0A53CC]">
                                  <BookOpenCheck className="h-4 w-4" />
                                  <div className="text-[13px] font-semibold tracking-tight text-black/88">{entry.title}</div>
                                </div>
                                <p className="mt-2 text-[12.5px] leading-7 text-black/62 font-medium">{entry.summary}</p>
                                <div className="mt-3 rounded-[12px] bg-[#F8F9FB] px-3 py-3 text-[12px] leading-6 text-black/62">
                                  <span className="font-semibold text-black/75">为什么有效：</span>
                                  {entry.whyEffective}
                                </div>
                                <div className="mt-3 rounded-[12px] border border-[#E9EEF8] bg-[#FAFBFF] px-3 py-3 text-[12px] leading-6 text-black/62">
                                  <span className="font-semibold text-black/75">关键片段：</span>
                                  {entry.keyExcerpt}
                                </div>
                                {entry.takeaways[0] && (
                                  <div className="mt-3 flex flex-wrap gap-1.5">
                                    {entry.takeaways.slice(0, 4).map((item) => (
                                      <span key={`${entry.id}:${item}`} className="rounded-[8px] bg-black/[0.04] px-2 py-1 text-[10px] font-semibold text-black/45">
                                        {item}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>

                        <div>
                          <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-black/35">你自己怎么改</div>
                          <div className="space-y-3">
                            <div className="rounded-[14px] border border-black/[0.05] bg-[#F8F9FB] p-4 text-[13px] leading-7 text-black/72 font-medium">
                              {activeInsight.coachCard.selfRewriteHint}
                            </div>
                            {referenceDraftByInsight[activeInsight.id] && (
                              <div className="rounded-[14px] border border-[#CDE0FF] bg-[#F7FAFF] p-4 text-[13px] leading-7 text-[#24478F] font-medium whitespace-pre-wrap">
                                {referenceDraftByInsight[activeInsight.id]}
                              </div>
                            )}
                            <button
                              type="button"
                              onClick={generateReferenceDraft}
                              className="inline-flex items-center gap-2 rounded-[10px] border border-[#CDE0FF] bg-white px-4 py-2.5 text-[12px] font-semibold text-[#0A53CC]"
                            >
                              <Sparkles className="h-4 w-4" />
                              生成参考稿
                            </button>
                          </div>
                        </div>

                        <div className="rounded-[14px] border border-black/[0.05] bg-[#F8F9FB] p-4">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-black/35">学会后的动作</div>
                          <p className="mt-2 text-[13px] leading-7 text-black/72 font-medium">{activeInsight.coachCard.learningAction}</p>
                          <div className="mt-4 flex flex-wrap gap-2">
                            <button type="button" onClick={() => setInspectorTab('basis')} className="rounded-[10px] border border-black/[0.08] px-3 py-2 text-[12px] font-semibold text-black/58">
                              为什么更好
                            </button>
                            <button type="button" onClick={() => setInspectorTab('learning')} className="rounded-[10px] border border-black/[0.08] px-3 py-2 text-[12px] font-semibold text-black/58">
                              看案例
                            </button>
                            <button type="button" onClick={() => startInlineRewrite()} className="rounded-[10px] border border-[#CDE0FF] bg-white px-3 py-2 text-[12px] font-semibold text-[#0A53CC]">
                              我来试改
                            </button>
                            <button type="button" onClick={() => void saveReminderRule()} disabled={actionBusyKey === 'reminder'} className="rounded-[10px] border border-black/[0.08] px-3 py-2 text-[12px] font-semibold text-black/58 disabled:opacity-60">
                              {actionBusyKey === 'reminder' ? '保存中...' : '下次提醒我'}
                            </button>
                            <button type="button" onClick={() => void saveWritingNorm()} disabled={actionBusyKey === 'norm'} className="rounded-[10px] border border-black/[0.08] px-3 py-2 text-[12px] font-semibold text-black/58 disabled:opacity-60">
                              {actionBusyKey === 'norm' ? '保存中...' : '加入机构规范'}
                            </button>
                          </div>
                        </div>
                      </>
                    ) : (
                      <>
                        <div>
                          <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-black/35">你可以直接这样改</div>
                          <div className="space-y-3">
                            {activeInsight.bullets.map((bullet, index) => (
                              <label key={`${activeInsight.id}-${index}`} className="group flex items-start gap-3 rounded-[12px] bg-black/[0.03] p-3 transition-colors hover:bg-black/[0.05]">
                                <div className="mt-[2px] h-[16px] w-[16px] rounded-[4px] border-[1.5px] border-black/18 transition-colors group-hover:border-[#5B7BFE]" />
                                <span className="text-[13px] leading-6 text-black/78 font-medium">{bullet}</span>
                              </label>
                            ))}
                          </div>
                        </div>

                        <div>
                          <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-black/35">为什么要这样改</div>
                          <div className="rounded-[14px] border border-black/[0.05] bg-[#F8F9FB] p-4 text-[13px] leading-7 text-black/62 font-medium">
                            {activeInsight.why}
                          </div>
                        </div>

                        <div className="rounded-[16px] border border-[#5B7BFE]/10 bg-gradient-to-br from-[#EAF2FF] to-[#F5F8FF] p-5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.8)]">
                          <div className="flex items-center gap-2 text-[#0A53CC]">
                            <Sparkles className="h-4 w-4" />
                            <div className="text-[13px] font-bold tracking-tight">学习卡：{activeInsight.learningTitle}</div>
                          </div>
                          <p className="mt-3 text-[12.5px] leading-7 text-[#0A53CC]/85 font-medium">
                            {activeInsight.learningBody}
                          </p>
                        </div>

                        {relatedKnowledgeEntries.length > 0 && (
                          <div>
                            <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-black/35">相关知识</div>
                            <div className="space-y-3">
                              {relatedKnowledgeEntries.map((entry) => (
                                <div key={entry.id} className="rounded-[14px] border border-black/[0.05] bg-white px-4 py-4 shadow-[0_8px_20px_-18px_rgba(15,23,42,0.2)]">
                                  <div className="flex items-center gap-2 text-[#0A53CC]">
                                    <BookOpenCheck className="h-4 w-4" />
                                    <div className="text-[13px] font-semibold tracking-tight text-black/88">{entry.title}</div>
                                  </div>
                                  <p className="mt-2 text-[12.5px] leading-7 text-black/62 font-medium">{entry.summary}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}

                {inspectorTab === 'comparison' && (
                  <div className="space-y-4">
                    {isLoadingComparison && !activeComparison ? (
                      <div className="rounded-[14px] border border-black/[0.05] bg-[#F8F9FB] p-4 text-[13px] text-black/48">
                        正在生成和上一版的结构化对比...
                      </div>
                    ) : (
                      <>
                        <div className="grid gap-4 xl:grid-cols-2">
                          <div className="rounded-[14px] border border-black/[0.05] bg-[#F8F9FB] p-4">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-black/35">结果变化</div>
                            <div className="mt-3 space-y-3">
                              {(activeComparison?.resultChanges || ['当前还没有可显示的结果变化。']).map((item, index) => (
                                <div key={`${item}-${index}`} className="rounded-[12px] bg-white px-3 py-3 text-[12.5px] leading-6 text-black/68">
                                  {item}
                                </div>
                              ))}
                            </div>
                          </div>
                          <div className="rounded-[14px] border border-black/[0.05] bg-[#F8F9FB] p-4">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-black/35">学习变化</div>
                            <div className="mt-3 space-y-3">
                              {(activeComparison?.learningChanges || ['当前还没有可显示的学习变化。']).map((item, index) => (
                                <div key={`${item}-${index}`} className="rounded-[12px] bg-white px-3 py-3 text-[12.5px] leading-6 text-black/68">
                                  {item}
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>

                        <div className="grid gap-4 xl:grid-cols-3">
                          <div className="rounded-[14px] border border-black/[0.05] bg-white px-4 py-4">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-black/35">已解决</div>
                            <div className="mt-3 space-y-2">
                              {(activeComparison?.resolvedIssues || []).length ? activeComparison?.resolvedIssues.map((item) => (
                                <div key={item} className="rounded-[10px] bg-emerald-50 px-3 py-2 text-[12px] font-medium text-emerald-700">{item}</div>
                              )) : <div className="text-[12px] text-black/38">还没有明确已解决项。</div>}
                            </div>
                          </div>
                          <div className="rounded-[14px] border border-black/[0.05] bg-white px-4 py-4">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-black/35">新增问题</div>
                            <div className="mt-3 space-y-2">
                              {(activeComparison?.newIssues || []).length ? activeComparison?.newIssues.map((item) => (
                                <div key={item} className="rounded-[10px] bg-rose-50 px-3 py-2 text-[12px] font-medium text-rose-700">{item}</div>
                              )) : <div className="text-[12px] text-black/38">当前没有识别到新的高优先问题。</div>}
                            </div>
                          </div>
                          <div className="rounded-[14px] border border-black/[0.05] bg-white px-4 py-4">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-black/35">重复犯错</div>
                            <div className="mt-3 space-y-2">
                              {(activeComparison?.repeatedIssues || []).length ? activeComparison?.repeatedIssues.map((item) => (
                                <div key={item} className="rounded-[10px] bg-amber-50 px-3 py-2 text-[12px] font-medium text-amber-700">{item}</div>
                              )) : <div className="text-[12px] text-black/38">暂未发现明显重复问题。</div>}
                            </div>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                )}

                {inspectorTab === 'mode' && (
                  <div className="space-y-5">
                    <div className="rounded-[14px] border border-black/[0.05] bg-[#F8F9FB] p-4">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-black/35">当前模式</div>
                      <p className="mt-2 text-[16px] font-semibold tracking-tight text-black/88">{selectedMode.title}</p>
                      <p className="mt-2 text-[13px] leading-7 text-black/58">{selectedMode.description}</p>
                    </div>

                    <div>
                      <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-black/35">本轮优先检查</div>
                      <div className="space-y-2.5">
                        {selectedMode.focusPoints.map((point) => (
                          <div key={point} className="flex items-start gap-3 rounded-[12px] bg-black/[0.03] px-3 py-3">
                            <div className="mt-[3px] h-[10px] w-[10px] rounded-full bg-[#5B7BFE]/80" />
                            <span className="text-[13px] leading-6 text-black/72 font-medium">{point}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-[14px] border border-black/[0.05] bg-white px-4 py-4">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-black/35">当前引擎与边界</div>
                      <p className="mt-2 text-[13px] leading-7 text-black/58">
                        当前模式正在使用 {activeTemplate ? getTemplateLabel(activeTemplate) : '未配置引擎'}。这轮已经能把诊断输出拆成建议与学习卡，
                        但预测、热点、多模态输入仍会在下一阶段继续补实算链路。
                      </p>
                      {activeWorkspaceKey === 'fundraising' && (
                        <div className="mt-3 rounded-[12px] bg-[#F8F9FB] px-3 py-3 text-[12px] leading-6 text-black/62">
                          <span className="font-semibold text-black/75">当前已接入：</span>
                          Deep DNA {deepDnaLibrary.filter((item) => item.status === 'published').length} 份、案例 {coachCases.length} 条、提醒规则 {coachReminderRules.length} 条、机构规范 {orgWritingNorms.length} 条。
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className="border-t border-black/[0.05] p-5 bg-white shrink-0 space-y-3">
                <button
                  type="button"
                  onClick={() => void saveLearningCard()}
                  disabled={!onSaveLearningCard || isSavingInsight}
                  className="w-full rounded-[10px] border border-black/[0.08] py-3 text-[13px] font-semibold text-black/70 hover:bg-black/[0.03] disabled:opacity-50 transition-colors inline-flex items-center justify-center gap-2"
                >
                  <BookOpenCheck className="h-4 w-4" />
                  {savedInsightIds.includes(activeInsight.id) ? '已写入成长手册' : isSavingInsight ? '写入中...' : '写入成长手册'}
                </button>
                <button
                  type="button"
                  onClick={() => toggleComplete(activeInsight.id)}
                  className={`w-full rounded-[10px] py-3 text-[13px] font-semibold transition-colors ${
                    completedSet.has(activeInsight.id)
                      ? 'bg-black/[0.05] text-black/55 hover:bg-black/[0.08]'
                      : 'bg-[#007AFF] text-white hover:bg-[#006CE6] shadow-[0_10px_24px_-14px_rgba(0,122,255,0.5)]'
                  }`}
                >
                  {completedSet.has(activeInsight.id) ? '撤销完成' : '标记为已解决'}
                </button>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center px-8 text-center text-[13px] text-black/35">
              先从中间选择一条待办建议，这里会展开依据、学习和模式说明。
            </div>
          )}
        </aside>
      </div>

      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-md flex items-center justify-center px-4">
          <div className="w-full max-w-[880px] overflow-hidden rounded-[28px] border border-black/[0.06] bg-white shadow-[0_36px_90px_-30px_rgba(15,23,42,0.45)]" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-center gap-4 border-b border-black/[0.05] px-7 py-5">
              <button type="button" className="h-9 w-9 shrink-0 rounded-[10px] border border-black/[0.08] text-black/40 transition-colors hover:bg-black/[0.04] hover:text-black/80" onClick={() => setIsCreateModalOpen(false)} aria-label="关闭新建诊断弹窗">
                <X className="h-4 w-4 mx-auto" />
              </button>
              <div className="flex-1">
                <h3 className="text-[20px] font-semibold tracking-tight text-black/90">新建诊断</h3>
                <p className="mt-1 text-[12px] text-black/45">先确定工作区和模式，再贴入需要分析的材料。</p>
              </div>
            </div>

            <div className="px-7 py-6 space-y-5">
              <div className="flex rounded-[10px] bg-black/[0.04] p-[3px] w-fit">
                {DIAGNOSIS_WORKSPACES.map((workspace) => {
                  const isActive = workspace.key === activeWorkspaceKey;
                  return (
                    <button
                      key={workspace.key}
                      type="button"
                      onClick={() => setActiveWorkspaceKey(workspace.key)}
                      className={`px-4 py-1.5 text-[12px] font-medium rounded-[8px] transition-all ${
                        isActive ? 'bg-white text-black/90 shadow-[0_1px_3px_rgba(15,23,42,0.12)]' : 'text-black/45 hover:text-black/80'
                      }`}
                    >
                      {workspace.label}
                    </button>
                  );
                })}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {workspaceModes.map((mode) => {
                  const isActive = mode.id === activeMode.id;
                  return (
                    <button
                      key={mode.id}
                      type="button"
                      onClick={() => setActiveModeId(mode.id)}
                      className={`rounded-[16px] border px-4 py-4 text-left transition-all ${
                        isActive ? 'border-[#5B7BFE]/20 bg-[#EAF2FF]' : 'border-black/[0.06] bg-[#F8F9FB] hover:bg-black/[0.02]'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className={`text-[14px] tracking-tight ${isActive ? 'font-semibold text-[#0A53CC]' : 'font-medium text-black/88'}`}>{mode.title}</p>
                          <p className="mt-2 text-[12px] leading-6 text-black/55">{mode.description}</p>
                        </div>
                        {isActive && <LayoutList className="h-4 w-4 text-[#5B7BFE]" />}
                      </div>
                    </button>
                  );
                })}
              </div>

              {activeProfileGroupDefinition && (
                <div className="rounded-[16px] border border-[#FDE7C7] bg-[#FFF9F1] px-4 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-[12px] font-semibold text-[#B86A12]">本次会附带对象画像</div>
                      <div className="mt-1 text-[12px] leading-6 text-[#8B5A12]">
                        {selectedDeepDnaForActiveMode || selectedProfileForActiveMode
                          ? `${activeProfileGroupDefinition.label}已选中 ${selectedDeepDnaForActiveMode?.label || selectedProfileForActiveMode?.label}，提交诊断和外部信号分析时都会附带这份判断摘要。`
                          : `还没有为${activeProfileGroupDefinition.label}上传可用文档。点右上角加号进入设置后，可上传 Markdown、DOCX、PDF 或 TXT。`}
                      </div>
                    </div>
                    {(selectedDeepDnaForActiveMode || selectedProfileForActiveMode) && (
                      <div className="rounded-[8px] bg-white px-2.5 py-1 text-[11px] font-semibold text-[#B86A12]">
                        {selectedDeepDnaForActiveMode?.sources[0]?.fileName || selectedProfileForActiveMode?.fileName || 'Deep DNA'}
                      </div>
                    )}
                  </div>
                </div>
              )}

              <input
                value={runDraft.title}
                onChange={(event) => setRunDraft((prev) => ({ ...prev, title: event.target.value }))}
                placeholder="本次诊断标题"
                className="w-full rounded-[14px] border border-black/[0.08] bg-[#F8F9FB] px-4 py-3 text-[14px] font-semibold text-black/88 outline-none focus:border-[#5B7BFE]/40 focus:bg-white"
              />

              <textarea
                value={runDraft.inputText}
                onChange={(event) => setRunDraft((prev) => ({ ...prev, inputText: event.target.value }))}
                placeholder="贴入需要分析的上下文材料..."
                className="min-h-[240px] w-full rounded-[18px] border border-black/[0.08] bg-[#F8F9FB] p-4 text-[14px] leading-7 text-black/82 outline-none focus:border-[#5B7BFE]/40 focus:bg-white"
              />
            </div>

            <div className="flex items-center justify-between border-t border-black/[0.05] bg-[#F8F9FB] px-7 py-5">
              <div className="text-[12px] text-black/40">
                当前模式会写入标题元数据，并把模式上下文随本次诊断一起提交。
              </div>
              <button
                type="button"
                onClick={() => void submitRun()}
                disabled={!activeTemplate || !runDraft.title.trim() || !runDraft.inputText.trim() || isSubmittingRun}
                className="inline-flex items-center gap-2 rounded-[10px] bg-[#5B7BFE] px-5 py-3 text-[13px] font-semibold text-white shadow-[0_12px_24px_-14px_rgba(91,123,254,0.55)] hover:bg-[#4A6BE6] disabled:opacity-60"
              >
                {isSubmittingRun ? <Sparkles className="h-4 w-4 animate-pulse" /> : <PlayCircle className="h-4 w-4" />}
                开始诊断
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
