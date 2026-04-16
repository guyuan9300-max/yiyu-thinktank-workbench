import React, { useEffect, useMemo, useState } from 'react';
import { Activity, CheckSquare, Plus, RefreshCw, Search, Sparkles, Target, X } from 'lucide-react';

import type {
  MentionCandidate,
  SessionUser,
  Task,
  TaskList,
  TaskSettings,
  TopicCandidate,
  TopicCandidateChatMessage,
  TopicCandidateInsight,
  TopicsSettings,
  TopicRadar,
  TopicRadarPreferredSource,
} from '../../../shared/types';
import {
  assistRadarDraft,
  askCandidateQuestion,
  captureTopicRadars,
  createRadar,
  createTask,
  deleteCandidate,
  getCandidateInsights,
  getMentionCandidates,
  saveTaskNote,
  suggestRadarSourceLabel,
  updateRadar,
} from '../../lib/api';
import { TopicIntelDetailPanel } from './TopicIntelDetailPanel';
import { TopicIntelInboxCard } from './TopicIntelInboxCard';

type TopicReadFilter = 'all' | 'unread';

type TopicCandidateLocalPreference = {
  saved?: boolean;
  note?: string;
  tags?: string[];
  read?: boolean;
};

type TopicCandidateLegacyPreference = TopicCandidateLocalPreference & {
  archived?: boolean;
  favorite?: boolean;
  favoriteNote?: string;
};

type TopicLocalState = {
  byCandidateId: Record<string, TopicCandidateLocalPreference>;
};

type TopicQuickTaskDraft = {
  title: string;
  desc: string;
  listId: string;
  priority: 'low' | 'normal' | 'high';
  dueDate: string;
  ddl: string;
  ownerId: string;
  ownerName: string;
  note: string;
};

type TopicRadarDraft = {
  id: string;
  title: string;
  prompt: string;
  timeRange: string;
  preferredSources: TopicRadarPreferredSource[];
};

type TopicsManagementViewProps = {
  radars: TopicRadar[];
  candidates: TopicCandidate[];
  tasks: Task[];
  activeTaskLists: TaskList[];
  effectiveTaskSettings: TaskSettings;
  topicsSettingsState: TopicsSettings;
  currentSessionUser: SessionUser | null;
  currentOperatorName: string;
  flash: (type: 'success' | 'error' | 'info', text: string) => void;
  onTopicsReload: () => Promise<unknown>;
  onTasksReload: () => Promise<unknown>;
};

const TOPIC_LOCAL_STATE_STORAGE_KEY = 'yiyu.workbench.topics.local-state.v2';
const TOPIC_LEGACY_STATE_STORAGE_KEY = 'yiyu.workbench.topics.local-state.v1';
const EMPTY_TOPIC_LOCAL_STATE: TopicLocalState = {
  byCandidateId: {},
};
const EMPTY_TOPIC_CANDIDATE_PREFERENCE: TopicCandidateLocalPreference = {
  saved: false,
  note: '',
  tags: [],
  read: false,
};

function normalizeCustomTags(value: unknown) {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  return value
    .map((item) => (typeof item === 'string' ? item.trim().replace(/\s+/g, ' ') : ''))
    .filter((item) => {
      const key = item.toLowerCase();
      if (!item || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function normalizePreference(preference?: TopicCandidateLegacyPreference | null): TopicCandidateLocalPreference {
  const note =
    typeof preference?.note === 'string'
      ? preference.note.trimStart()
      : typeof preference?.favoriteNote === 'string'
        ? preference.favoriteNote.trimStart()
        : '';
  const tags = normalizeCustomTags(preference?.tags);
  return {
    saved: Boolean(preference?.saved || preference?.favorite || preference?.archived || note.trim() || tags.length),
    note,
    tags,
    read: Boolean(preference?.read),
  };
}

function normalizeTopicLocalState(input: unknown): TopicLocalState {
  if (!input || typeof input !== 'object' || typeof (input as TopicLocalState).byCandidateId !== 'object') {
    return EMPTY_TOPIC_LOCAL_STATE;
  }

  const nextByCandidateId: Record<string, TopicCandidateLocalPreference> = {};
  Object.entries((input as TopicLocalState).byCandidateId).forEach(([candidateId, preference]) => {
    nextByCandidateId[candidateId] = normalizePreference(preference as TopicCandidateLegacyPreference);
  });

  return { byCandidateId: nextByCandidateId };
}

function readTopicLocalState(): TopicLocalState {
  if (typeof window === 'undefined') return EMPTY_TOPIC_LOCAL_STATE;
  try {
    const raw = window.localStorage.getItem(TOPIC_LOCAL_STATE_STORAGE_KEY) || window.localStorage.getItem(TOPIC_LEGACY_STATE_STORAGE_KEY);
    if (!raw) return EMPTY_TOPIC_LOCAL_STATE;
    return normalizeTopicLocalState(JSON.parse(raw));
  } catch {
    return EMPTY_TOPIC_LOCAL_STATE;
  }
}

function writeTopicLocalState(state: TopicLocalState) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(TOPIC_LOCAL_STATE_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // In some Electron/browser contexts storage may be unavailable or read-only.
  }
}

function buildTopicAttachmentNote(
  candidate: TopicCandidate,
  radarTitle: string,
  insight: TopicCandidateInsight | null | undefined,
  operatorNote: string,
) {
  const lines = [
    `【情报附件】${candidate.title}`,
    `关联雷达：${radarTitle}`,
    `来源：${candidate.source}`,
  ];

  if (candidate.publishedAt) {
    lines.push(`发布时间：${candidate.publishedAt}`);
  }
  if (candidate.sourceUrl) {
    lines.push(`原文链接：${candidate.sourceUrl}`);
  }

  const relationReasons = insight?.recommendationReasons?.filter((item) => item.trim()) || [];
  const keyPoints = insight?.keyPoints?.filter((item) => item.trim()) || [];
  const practicalUses = insight?.practicalUses?.filter((item) => item.trim()) || [];
  const editorialNote = insight?.editorialNote?.trim() || '';
  const discussionPrompts = insight?.discussionPrompts?.filter((item) => item.trim()) || [];

  lines.push('');
  lines.push('为什么和当前雷达相关：');
  if (relationReasons.length) {
    relationReasons.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
  } else {
    lines.push(`1. 这篇内容当前被归入「${radarTitle}」雷达下，建议先按这个主题核对。`);
  }

  lines.push('');
  lines.push('主要内容：');
  lines.push(insight?.overview?.trim() || candidate.summary || '当前只有原始摘要，尚未形成完整综述。');

  lines.push('');
  lines.push('核心观点：');
  if (keyPoints.length) {
    keyPoints.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
  } else {
    lines.push('1. 当前还没有稳定的核心观点提炼，建议直接点开原文。');
  }

  lines.push('');
  lines.push('大周前哨判断：');
  lines.push(editorialNote || '当前还没有稳定的大周前哨判断，建议先结合原文和核心观点继续讨论。');

  lines.push('');
  lines.push('可直接展开成文：');
  if (practicalUses.length) {
    practicalUses.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
  } else {
    lines.push('1. 后续可围绕它是否值得写成文章、是否需要团队跟进继续讨论。');
  }

  lines.push('');
  lines.push('值得继续追问的问题：');
  if (discussionPrompts.length) {
    discussionPrompts.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
  } else {
    lines.push('1. 这篇内容背后最值得继续追问的变化，到底是什么？');
  }

  if (operatorNote.trim()) {
    lines.push('');
    lines.push('给同事的补充：');
    lines.push(operatorNote.trim());
  }

  return lines.join('\n');
}

function candidateSortTime(candidate: TopicCandidate) {
  return new Date(candidate.publishedAt || candidate.createdAt).getTime();
}

function normalizeTagDraft(value: string) {
  return value.trim().replace(/\s+/g, ' ');
}

export function TopicsManagementView({
  radars,
  candidates,
  tasks,
  activeTaskLists,
  effectiveTaskSettings,
  topicsSettingsState,
  currentSessionUser,
  currentOperatorName,
  flash,
  onTopicsReload,
  onTasksReload,
}: TopicsManagementViewProps) {
  const [selectedRadarId, setSelectedRadarId] = useState<string>('all');
  const [readFilter, setReadFilter] = useState<TopicReadFilter>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCandidateId, setSelectedCandidateId] = useState('');
  const [tagDraft, setTagDraft] = useState('');
  const [localState, setLocalState] = useState<TopicLocalState>(() => readTopicLocalState());
  const [editingPrefIndex, setEditingPrefIndex] = useState<number | null>(null);
  const [tempPref, setTempPref] = useState<TopicRadarDraft | null>(null);
  const [preferredSourceDraft, setPreferredSourceDraft] = useState('');
  const [isAssistingRadar, setIsAssistingRadar] = useState(false);
  const [isGeneratingSourceLabel, setIsGeneratingSourceLabel] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);
  const [globalMessage, setGlobalMessage] = useState<string | null>(null);
  const [insightCache, setInsightCache] = useState<Record<string, TopicCandidateInsight>>({});
  const [insightLoadingId, setInsightLoadingId] = useState<string | null>(null);
  const [chatByCandidateId, setChatByCandidateId] = useState<Record<string, TopicCandidateChatMessage[]>>({});
  const [chatDraftByCandidateId, setChatDraftByCandidateId] = useState<Record<string, string>>({});
  const [chatLoadingCandidateId, setChatLoadingCandidateId] = useState<string | null>(null);
  const [taskModalCandidateId, setTaskModalCandidateId] = useState<string | null>(null);
  const [taskDraft, setTaskDraft] = useState<TopicQuickTaskDraft | null>(null);
  const [taskAssignees, setTaskAssignees] = useState<MentionCandidate[]>([]);
  const [isPreparingTaskModal, setIsPreparingTaskModal] = useState(false);
  const [isSubmittingTask, setIsSubmittingTask] = useState(false);

  const defaultListId = effectiveTaskSettings.defaultListId || activeTaskLists[0]?.id || 'list-1';
  const radarMap = useMemo(() => new Map(radars.map((item) => [item.id, item])), [radars]);
  const relatedTasksByCandidate = useMemo(() => {
    const grouped = new Map<string, Task[]>();
    tasks.forEach((task) => {
      if (task.sourceType !== 'topic_candidate' || !task.sourceId) return;
      const rows = grouped.get(task.sourceId) || [];
      rows.push(task);
      grouped.set(task.sourceId, rows);
    });
    return grouped;
  }, [tasks]);
  const radarCards = useMemo(() => {
    const visible = [...radars].slice(-5).map((item) => ({
      id: item.id,
      title: item.title,
      prompt: item.prompt,
      timeRange: item.timeRange,
      preferredSources: item.preferredSources || [],
      candidateCount: candidates.filter((candidate) => candidate.radarId === item.id).length,
    }));
    visible.push({
      id: 'placeholder-new',
      title: '',
      prompt: '',
      timeRange: topicsSettingsState.defaultTimeRange,
      preferredSources: [],
      candidateCount: 0,
    });
    return visible;
  }, [candidates, radars, topicsSettingsState.defaultTimeRange]);

  const preferenceOf = (candidateId: string) => localState.byCandidateId[candidateId] || EMPTY_TOPIC_CANDIDATE_PREFERENCE;
  const isSavedCandidate = (candidate: TopicCandidate, preference = preferenceOf(candidate.id)) =>
    Boolean(preference.saved || candidate.status === 'archived');
  const updateLocalPreference = (candidateId: string, patch: Partial<TopicCandidateLocalPreference>) => {
    setLocalState((prev) => {
      const current = prev.byCandidateId[candidateId] || EMPTY_TOPIC_CANDIDATE_PREFERENCE;
      const nextPreference = normalizePreference({
        ...current,
        ...patch,
      });
      const shouldRemove =
        !nextPreference.saved &&
        !nextPreference.read &&
        !nextPreference.note?.trim() &&
        !(nextPreference.tags?.length);
      const nextByCandidateId = { ...prev.byCandidateId };
      if (shouldRemove) {
        delete nextByCandidateId[candidateId];
      } else {
        nextByCandidateId[candidateId] = nextPreference;
      }
      const next: TopicLocalState = {
        byCandidateId: nextByCandidateId,
      };
      writeTopicLocalState(next);
      return next;
    });
  };

  const viewCounts = useMemo(() => {
    const counts = {
      new: 0,
      saved: 0,
      task_linked: 0,
      unread: 0,
    };
    candidates.forEach((candidate) => {
      const preference = preferenceOf(candidate.id);
      const saved = isSavedCandidate(candidate, preference);
      const linked = (relatedTasksByCandidate.get(candidate.id) || []).length > 0;
      const read = Boolean(preference.read);
      if (!read) counts.unread += 1;
      if (!saved && !linked) counts.new += 1;
      if (saved) counts.saved += 1;
      if (linked) counts.task_linked += 1;
    });
    return counts;
  }, [candidates, localState, relatedTasksByCandidate]);

  const filteredCandidates = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return candidates
      .filter((candidate) => {
        const preference = preferenceOf(candidate.id);
        const saved = isSavedCandidate(candidate, preference);
        const linked = (relatedTasksByCandidate.get(candidate.id) || []).length > 0;
        const read = Boolean(preference.read);
        const customTags = preference.tags || [];

        if (selectedRadarId !== 'all' && candidate.radarId !== selectedRadarId) return false;
        if (readFilter === 'unread' && read) return false;
        if (!query) return true;

        const radarTitle = radarMap.get(candidate.radarId)?.title || '';
        const insight = insightCache[candidate.id];
        const corpus = [
          candidate.title,
          candidate.summary,
          candidate.source,
          radarTitle,
          preference.note || '',
          ...customTags,
          insight?.overview || '',
          ...(insight?.keyPoints || []),
          ...(insight?.recommendationReasons || []),
          ...(insight?.practicalUses || []),
        ]
          .join(' ')
          .toLowerCase();
        return corpus.includes(query);
      })
      .sort((left, right) => candidateSortTime(right) - candidateSortTime(left));
  }, [candidates, insightCache, localState, radarMap, readFilter, relatedTasksByCandidate, searchQuery, selectedRadarId]);

  const selectedCandidate = useMemo(
    () => filteredCandidates.find((candidate) => candidate.id === selectedCandidateId) || filteredCandidates[0] || null,
    [filteredCandidates, selectedCandidateId],
  );
  const selectedInsight = selectedCandidate ? insightCache[selectedCandidate.id] || null : null;
  const selectedRadarTitle = selectedCandidate ? radarMap.get(selectedCandidate.radarId)?.title || '未命名雷达' : '';
  const selectedRelatedTasks = selectedCandidate ? relatedTasksByCandidate.get(selectedCandidate.id) || [] : [];
  const selectedChatMessages = selectedCandidate ? chatByCandidateId[selectedCandidate.id] || [] : [];
  const selectedChatDraft = selectedCandidate ? chatDraftByCandidateId[selectedCandidate.id] || '' : '';
  const unreadCandidates = useMemo(
    () => candidates.filter((candidate) => !preferenceOf(candidate.id).read).length,
    [candidates, localState],
  );

  useEffect(() => {
    if (!filteredCandidates.length) {
      if (selectedCandidateId) setSelectedCandidateId('');
      return;
    }
    if (!filteredCandidates.some((candidate) => candidate.id === selectedCandidateId)) {
      setSelectedCandidateId(filteredCandidates[0].id);
    }
  }, [filteredCandidates, selectedCandidateId]);

  useEffect(() => {
    if (!selectedCandidateId) return;
    const preference = preferenceOf(selectedCandidateId);
    if (preference.read) return;
    updateLocalPreference(selectedCandidateId, { read: true });
  }, [selectedCandidateId]);

  useEffect(() => {
    setTagDraft('');
  }, [selectedCandidateId]);

  useEffect(() => {
    if (!selectedCandidate || selectedCandidate.insightStatus !== 'ready') return;
    if (insightCache[selectedCandidate.id]) return;
    let active = true;
    setInsightLoadingId(selectedCandidate.id);
    void getCandidateInsights(selectedCandidate.id)
      .then((insight) => {
        if (!active) return;
        setInsightCache((prev) => ({ ...prev, [selectedCandidate.id]: insight }));
      })
      .catch((error) => {
        if (!active) return;
        flash('error', error instanceof Error ? error.message : '情报详情加载失败');
      })
      .finally(() => {
        if (!active) return;
        setInsightLoadingId((current) => (current === selectedCandidate.id ? null : current));
      });
    return () => {
      active = false;
    };
  }, [flash, insightCache, selectedCandidate]);

  const showMessage = (message: string) => {
    setGlobalMessage(message);
    window.setTimeout(() => {
      setGlobalMessage((current) => (current === message ? null : current));
    }, 3200);
  };

  const ensureInsightLoaded = async (candidate: TopicCandidate) => {
    if (insightCache[candidate.id]) return insightCache[candidate.id];
    const insight = await getCandidateInsights(candidate.id);
    setInsightCache((prev) => ({ ...prev, [candidate.id]: insight }));
    return insight;
  };

  const ensureTaskAssignees = (items: MentionCandidate[]) => {
    const next = [...items];
    if (currentSessionUser && !next.some((item) => item.id === currentSessionUser.id)) {
      next.unshift({
        id: currentSessionUser.id,
        fullName: currentSessionUser.fullName,
        email: currentSessionUser.email,
        primaryRole: currentSessionUser.primaryRole,
        isSelf: true,
      });
    }
    return next;
  };

  const handleAssistRadarDraft = async () => {
    if (!tempPref?.prompt.trim()) {
      flash('error', '请先填写追踪内容说明');
      return;
    }
    setIsAssistingRadar(true);
    try {
      const assisted = await assistRadarDraft(tempPref.prompt, tempPref.timeRange);
      setTempPref((prev) => (
        prev
          ? {
              ...prev,
              title: assisted.title,
              prompt: assisted.prompt,
            }
          : prev
      ));
      showMessage('已补强检索说明，并同步提炼标题');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : 'AI 补强失败');
    } finally {
      setIsAssistingRadar(false);
    }
  };

  const handleAddPreferredSource = async () => {
    if (!tempPref) return;
    if (!preferredSourceDraft.trim()) {
      flash('error', '请先填写优先检索的网址');
      return;
    }
    setIsGeneratingSourceLabel(true);
    try {
      const suggested = await suggestRadarSourceLabel(preferredSourceDraft);
      setTempPref((prev) => {
        if (!prev) return prev;
        if (prev.preferredSources.some((item) => item.url === suggested.url)) {
          return prev;
        }
        return {
          ...prev,
          preferredSources: [...prev.preferredSources, { url: suggested.url, label: suggested.label }],
        };
      });
      setPreferredSourceDraft('');
      flash('success', `已加入优先网址「${suggested.label}」`);
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '网址添加失败');
    } finally {
      setIsGeneratingSourceLabel(false);
    }
  };

  const handleRemovePreferredSource = (url: string) => {
    setTempPref((prev) => (prev ? { ...prev, preferredSources: prev.preferredSources.filter((item) => item.url !== url) } : prev));
  };

  const handleSavePrefEdit = async () => {
    if (!tempPref || !tempPref.prompt.trim()) return;
    try {
      const payload = {
        title: tempPref.title.trim() || '自定义追踪项',
        prompt: tempPref.prompt.trim(),
        timeRange: tempPref.timeRange,
        preferredSources: tempPref.preferredSources,
      };
      const isExistingRadar = !tempPref.id.startsWith('placeholder-');
      if (isExistingRadar) {
        await updateRadar(tempPref.id, payload);
      } else {
        await createRadar(payload);
      }
      await onTopicsReload();
      setEditingPrefIndex(null);
      setTempPref(null);
      setPreferredSourceDraft('');
      showMessage(isExistingRadar ? '雷达规则已更新' : '已新增雷达规则');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '保存失败');
    }
  };

  const handleCapture = async () => {
    setIsCapturing(true);
    try {
      const result = await captureTopicRadars();
      await onTopicsReload();
      const totalFetched = result.runs.reduce((sum, item) => sum + item.fetchedCount, 0);
      if (result.totalCreated > 0) {
        showMessage(`大周本轮抓到 ${totalFetched} 条线索，新增 ${result.totalCreated} 篇情报，正在继续解析`);
      } else if (totalFetched > 0 && result.totalSkipped > 0) {
        showMessage(`大周本轮抓到 ${totalFetched} 条线索，但都已在历史情报里，本次没有新增`);
      } else {
        showMessage('大周完成本轮检索，但暂时没有新的高相关情报');
      }
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '大周抓取失败');
    } finally {
      setIsCapturing(false);
    }
  };

  const handleToggleSaved = (candidate: TopicCandidate) => {
    const current = preferenceOf(candidate.id);
    const currentlySaved = isSavedCandidate(candidate, current);
    if (candidate.status === 'archived' && currentlySaved) {
      flash('info', '这篇情报来自历史归档记录，当前只支持继续保留在资料夹中');
      return;
    }
    const next = !currentlySaved;
    updateLocalPreference(candidate.id, { saved: next });
    flash('success', next ? '已收进资料夹' : '已从资料夹移出');
  };

  const handleAddCustomTag = (candidate: TopicCandidate) => {
    const nextTag = normalizeTagDraft(tagDraft);
    if (!nextTag) return;
    const currentTags = preferenceOf(candidate.id).tags || [];
    if (currentTags.some((tag) => tag.toLowerCase() === nextTag.toLowerCase())) {
      flash('info', '这个标签已经存在');
      return;
    }
    updateLocalPreference(candidate.id, {
      saved: true,
      tags: [...currentTags, nextTag],
    });
    setTagDraft('');
    flash('success', `已添加标签「${nextTag}」`);
  };

  const handleRemoveCustomTag = (candidate: TopicCandidate, tag: string) => {
    const currentTags = preferenceOf(candidate.id).tags || [];
    updateLocalPreference(candidate.id, {
      saved: currentTags.length > 1 || Boolean(preferenceOf(candidate.id).note?.trim()),
      tags: currentTags.filter((item) => item !== tag),
    });
    flash('success', `已移除标签「${tag}」`);
  };

  const handleDeleteCandidate = async (candidate: TopicCandidate) => {
    try {
      await deleteCandidate(candidate.id);
      setInsightCache((prev) => {
        if (!prev[candidate.id]) return prev;
        const next = { ...prev };
        delete next[candidate.id];
        return next;
      });
      if (taskModalCandidateId === candidate.id) {
        setTaskModalCandidateId(null);
        setTaskDraft(null);
        setTaskAssignees([]);
      }
      if (selectedCandidateId === candidate.id) {
        setSelectedCandidateId('');
      }
      setChatByCandidateId((prev) => {
        if (!prev[candidate.id]) return prev;
        const next = { ...prev };
        delete next[candidate.id];
        return next;
      });
      setChatDraftByCandidateId((prev) => {
        if (!(candidate.id in prev)) return prev;
        const next = { ...prev };
        delete next[candidate.id];
        return next;
      });
      setChatLoadingCandidateId((current) => (current === candidate.id ? null : current));
      await onTopicsReload();
      flash('success', '情报已删除');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '删除失败');
    }
  };

  const setCandidateChatDraft = (candidateId: string, value: string) => {
    setChatDraftByCandidateId((prev) => {
      if (!value) {
        if (!(candidateId in prev)) return prev;
        const next = { ...prev };
        delete next[candidateId];
        return next;
      }
      return {
        ...prev,
        [candidateId]: value,
      };
    });
  };

  const handleAskCandidateQuestion = async (candidate: TopicCandidate, forcedQuestion?: string) => {
    const question = (forcedQuestion ?? (chatDraftByCandidateId[candidate.id] || '')).trim();
    if (!question) return;
    if (chatLoadingCandidateId === candidate.id) return;

    const userMessage: TopicCandidateChatMessage = {
      role: 'user',
      content: question,
      createdAt: new Date().toISOString(),
    };
    const history = (chatByCandidateId[candidate.id] || []).slice(-8);

    setChatByCandidateId((prev) => ({
      ...prev,
      [candidate.id]: [...(prev[candidate.id] || []), userMessage],
    }));
    if (!forcedQuestion) {
      setCandidateChatDraft(candidate.id, '');
    }
    setChatLoadingCandidateId(candidate.id);

    try {
      const response = await askCandidateQuestion(candidate.id, {
        question,
        history,
      });
      setChatByCandidateId((prev) => ({
        ...prev,
        [candidate.id]: [...(prev[candidate.id] || []), response.message],
      }));
    } catch (error) {
      const fallbackMessage: TopicCandidateChatMessage = {
        role: 'assistant',
        content: error instanceof Error ? `我暂时没能接住这个追问：${error.message}` : '我暂时没能接住这个追问，请稍后再试。',
        createdAt: new Date().toISOString(),
      };
      setChatByCandidateId((prev) => ({
        ...prev,
        [candidate.id]: [...(prev[candidate.id] || []), fallbackMessage],
      }));
      flash('error', error instanceof Error ? error.message : '追问失败');
    } finally {
      setChatLoadingCandidateId((current) => (current === candidate.id ? null : current));
    }
  };

  const openTaskModal = async (candidate: TopicCandidate) => {
    if (candidate.insightStatus !== 'ready') {
      flash('error', '请等大周完成解析后再转任务');
      return;
    }

    const defaultOwnerId = currentSessionUser?.id || '';
    setSelectedCandidateId(candidate.id);
    setTaskModalCandidateId(candidate.id);
    setTaskDraft({
      title: candidate.title.trim(),
      desc: `请查看任务备注中的情报附件，并结合团队安排决定下一步处理方式。`,
      listId: defaultListId,
      priority: 'normal',
      dueDate: '',
      ddl: '待确认',
      ownerId: defaultOwnerId,
      ownerName: currentSessionUser?.fullName || currentOperatorName,
      note: '',
    });
    setIsPreparingTaskModal(true);
    try {
      const [mentionItems] = await Promise.all([
        getMentionCandidates('').catch(() => []),
        ensureInsightLoaded(candidate),
      ]);
      const assignees = ensureTaskAssignees(mentionItems);
      setTaskAssignees(assignees);
      const defaultOwner = assignees.find((item) => item.id === defaultOwnerId) || assignees[0];
      if (defaultOwner) {
        setTaskDraft((prev) =>
          prev
            ? {
                ...prev,
                ownerId: defaultOwner.id,
                ownerName: defaultOwner.fullName,
              }
            : prev,
        );
      }
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '任务弹窗准备失败');
    } finally {
      setIsPreparingTaskModal(false);
    }
  };

  const handleSubmitTask = async () => {
    const modalCandidate = candidates.find((candidate) => candidate.id === taskModalCandidateId);
    if (!modalCandidate || !taskDraft) return;
    if (!taskDraft.title.trim()) {
      flash('error', '请填写任务标题');
      return;
    }
    if (!taskDraft.listId) {
      flash('error', '请先选择任务清单');
      return;
    }

    setIsSubmittingTask(true);
    try {
      const owner = taskAssignees.find((item) => item.id === taskDraft.ownerId);
      const ownerId = owner?.id || taskDraft.ownerId || null;
      const ownerName = owner?.fullName || taskDraft.ownerName || currentOperatorName;
      const createdTask = await createTask({
        title: taskDraft.title.trim(),
        desc: taskDraft.desc.trim(),
        priority: taskDraft.priority,
        listId: taskDraft.listId,
        dueDate: taskDraft.dueDate || null,
        ddl: taskDraft.ddl.trim() || taskDraft.dueDate || '待确认',
        ownerId,
        ownerName,
        collaboratorIds: ownerId ? [ownerId] : [],
        tagIds: [],
        tags: ['情报跟进'],
        sourceType: 'topic_candidate',
        sourceId: modalCandidate.id,
      });
      const insight = await ensureInsightLoaded(modalCandidate);
      const radarTitle = radarMap.get(modalCandidate.radarId)?.title || '未命名雷达';
      await saveTaskNote(createdTask.id, buildTopicAttachmentNote(modalCandidate, radarTitle, insight, taskDraft.note));
      await onTasksReload();
      setTaskModalCandidateId(null);
      setTaskDraft(null);
      setTaskAssignees([]);
      showMessage('已同步到任务，并附上当前情报说明');
      flash('success', '情报已转成任务');
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '转任务失败');
    } finally {
      setIsSubmittingTask(false);
    }
  };

  const taskModalCandidate = taskModalCandidateId
    ? candidates.find((candidate) => candidate.id === taskModalCandidateId) || null
    : null;
  const taskOwnerOptions = taskAssignees.length
    ? taskAssignees
    : currentSessionUser
      ? [{
          id: currentSessionUser.id,
          fullName: currentSessionUser.fullName,
          email: currentSessionUser.email,
          primaryRole: currentSessionUser.primaryRole,
          isSelf: true,
        }]
      : [];

  return (
    <div className="h-full flex flex-col bg-[#F9FAFB] overflow-hidden relative font-sans text-gray-800">
      <div className="bg-white border-b border-gray-100 px-5 lg:px-8 py-3.5 shrink-0 z-10">
        <div className="flex flex-col gap-2.5">
          {/* Row 1: title + inline stats + actions */}
          <div className="flex items-center gap-4">
            <h1 className="text-[15px] font-semibold text-gray-800 flex items-center gap-1.5 shrink-0">
              <Search size={15} className="text-[#5B7BFE]" />
              情报站
            </h1>
            <div className="flex items-center gap-3 text-[12px] text-gray-400 ml-1">
              <span><span className="font-semibold text-[#5B7BFE]">{viewCounts.new}</span> 新发现</span>
              <span className="text-gray-200">|</span>
              <span><span className="font-semibold text-gray-600">{unreadCandidates}</span> 未读</span>
              <span className="text-gray-200">|</span>
              <span><span className="font-semibold text-gray-600">{viewCounts.saved}</span> 资料夹</span>
              <span className="text-gray-200">|</span>
              <span><span className="font-semibold text-gray-600">{viewCounts.task_linked}</span> 已转任务</span>
            </div>
            <div className="flex items-center gap-2 ml-auto shrink-0 flex-wrap justify-end">
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="搜索标题、摘要、来源或核心观点"
                  className="w-[200px] rounded-xl border border-gray-200 bg-gray-50 pl-9 pr-3 py-1.5 text-[12px] outline-none focus:bg-white focus:border-[#5B7BFE]"
                />
              </div>
              <select
                value={selectedRadarId}
                onChange={(event) => setSelectedRadarId(event.target.value)}
                className="w-[132px] rounded-xl border border-gray-200 bg-gray-50 px-3 py-1.5 text-[12px] outline-none focus:bg-white focus:border-[#5B7BFE]"
              >
                <option value="all">全部雷达</option>
                {radars.map((radar) => (
                  <option key={radar.id} value={radar.id}>
                    {radar.title}
                  </option>
                ))}
              </select>
              <select
                value={readFilter}
                onChange={(event) => setReadFilter(event.target.value as TopicReadFilter)}
                className="w-[132px] rounded-xl border border-gray-200 bg-gray-50 px-3 py-1.5 text-[12px] outline-none focus:bg-white focus:border-[#5B7BFE]"
              >
                <option value="all">全部阅读状态</option>
                <option value="unread">只看未读</option>
              </select>
              <button
                type="button"
                onClick={() => {
                  const placeholderIndex = radarCards.findIndex((item) => item.id === 'placeholder-new');
                  setEditingPrefIndex(placeholderIndex);
                  setPreferredSourceDraft('');
                  setTempPref({ id: 'placeholder-new', title: '', prompt: '', timeRange: topicsSettingsState.defaultTimeRange, preferredSources: [] });
                }}
                className="px-3 py-1.5 rounded-lg text-[12px] font-medium bg-white border border-gray-200 text-gray-500 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-700 transition-all inline-flex items-center gap-1.5"
              >
                <Plus size={13} />
                管理雷达
              </button>
              <button
                type="button"
                onClick={() => void handleCapture()}
                disabled={isCapturing || radars.length === 0}
                className="px-3.5 py-1.5 rounded-lg text-[12px] font-medium bg-[#5B7BFE] text-white hover:bg-[#4a6be6] disabled:opacity-50 disabled:cursor-not-allowed transition-all inline-flex items-center gap-1.5"
              >
                {isCapturing ? <RefreshCw size={13} className="animate-spin" /> : <Search size={13} />}
                {isCapturing ? '抓取中…' : '抓取'}
              </button>
            </div>
          </div>

          {/* Row 2: radar chips */}
          <div className="flex gap-2 w-full overflow-x-auto scrollbar-hide">
            {radarCards.map((pref, index) => {
              const isPlaceholder = pref.id === 'placeholder-new';
              return (
                <button
                  key={pref.id || index}
                  type="button"
                  onClick={() => {
                    setEditingPrefIndex(index);
                    setPreferredSourceDraft('');
                    setTempPref({
                      id: pref.id,
                      title: pref.title,
                      prompt: pref.prompt,
                      timeRange: pref.timeRange,
                      preferredSources: pref.preferredSources || [],
                    });
                  }}
                  className={`shrink-0 rounded-full border px-3 py-1 text-left transition-all ${
                    isPlaceholder
                      ? 'border-dashed border-gray-200 text-gray-400 hover:border-[#b8c7ff] hover:text-[#5B7BFE]'
                      : 'bg-[#f7f9ff] border-[#e4eaff] text-[#5B7BFE] hover:bg-[#eef2ff]'
                  }`}
                >
                  <span className="flex items-center gap-1.5">
                    <Activity size={11} />
                    <span className="text-[12px] font-medium whitespace-nowrap">{pref.title || '添加雷达…'}</span>
                    {!isPlaceholder && (
                      <span className="text-[10px] text-[#5B7BFE]/50 whitespace-nowrap">{pref.candidateCount}</span>
                    )}
                  </span>
                </button>
              );
            })}
          </div>

          {globalMessage && (
            <div className="flex items-center justify-center animate-in fade-in absolute left-1/2 -translate-x-1/2 top-4 z-50">
              <div className="text-[12px] font-bold text-emerald-600 bg-emerald-50 px-4 py-2 rounded-full shadow-sm flex items-center gap-2">
                <CheckSquare size={14} /> {globalMessage}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 xl:grid-cols-[1.12fr_0.88fr] gap-6 p-8 overflow-y-auto">
        <div className="bg-white border border-gray-100 rounded-[32px] shadow-sm p-6 overflow-y-auto">
          <div className="flex flex-col gap-4">
            <div>
              <h2 className="text-[18px] font-bold text-gray-900">情报收件箱</h2>
            </div>
          </div>

          <div className="mt-5 space-y-4">
            {filteredCandidates.length > 0 ? (
              filteredCandidates.map((candidate) => {
                const preference = preferenceOf(candidate.id);
                const radarTitle = radarMap.get(candidate.radarId)?.title || '未命名雷达';
                return (
                  <TopicIntelInboxCard
                    key={candidate.id}
                    candidate={candidate}
                    radarTitle={radarTitle}
                    insight={insightCache[candidate.id]}
                    selected={selectedCandidate?.id === candidate.id}
                    read={Boolean(preference.read)}
                    saved={isSavedCandidate(candidate, preference)}
                    tags={preference.tags || []}
                    relatedTaskCount={(relatedTasksByCandidate.get(candidate.id) || []).length}
                    onSelect={() => setSelectedCandidateId(candidate.id)}
                    onDelete={() => void handleDeleteCandidate(candidate)}
                  />
                );
              })
            ) : (
              <div className="rounded-[28px] border border-dashed border-gray-200 bg-gray-50/70 px-6 py-12 text-center">
                <p className="text-[16px] font-bold text-gray-900">当前筛选条件下还没有情报</p>
                <p className="text-[13px] text-gray-500 mt-2">可以切换视图、放宽筛选，或者让大周立即再抓一轮。</p>
              </div>
            )}
          </div>
        </div>

        <TopicIntelDetailPanel
          candidate={selectedCandidate}
          radarTitle={selectedRadarTitle}
          insight={selectedInsight}
          isLoadingInsight={Boolean(selectedCandidate && insightLoadingId === selectedCandidate.id)}
          saved={Boolean(selectedCandidate && isSavedCandidate(selectedCandidate))}
          relatedTasks={selectedRelatedTasks}
          chatMessages={selectedChatMessages}
          chatDraft={selectedChatDraft}
          isChatting={Boolean(selectedCandidate && chatLoadingCandidateId === selectedCandidate.id)}
          onToggleSaved={() => {
            if (!selectedCandidate) return;
            handleToggleSaved(selectedCandidate);
          }}
          onAskDiscussionPrompt={(question) => {
            if (!selectedCandidate) return;
            void handleAskCandidateQuestion(selectedCandidate, question);
          }}
          onChatDraftChange={(value) => {
            if (!selectedCandidate) return;
            setCandidateChatDraft(selectedCandidate.id, value);
          }}
          onSendChat={() => {
            if (!selectedCandidate) return;
            void handleAskCandidateQuestion(selectedCandidate);
          }}
          onOpenTask={() => {
            if (!selectedCandidate) return;
            void openTaskModal(selectedCandidate);
          }}
          onOpenSource={() => {
            if (!selectedCandidate?.sourceUrl) return;
            window.open(selectedCandidate.sourceUrl, '_blank', 'noopener,noreferrer');
          }}
        />
      </div>

      {editingPrefIndex !== null && tempPref && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-md z-50 flex items-center justify-center animate-in fade-in">
          <div className="bg-white rounded-[28px] shadow-[0_20px_60px_rgba(0,0,0,0.15)] w-[620px] overflow-hidden transform animate-in zoom-in-95 border border-gray-100" onClick={(event) => event.stopPropagation()}>
            <div className="px-8 py-6 border-b border-gray-100 flex items-center gap-4 bg-white">
              <button type="button" onClick={() => { setEditingPrefIndex(null); setTempPref(null); setPreferredSourceDraft(''); }} className="rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700" aria-label="关闭深度追踪雷达弹窗">
                <X size={18} />
              </button>
              <h3 className="text-[18px] font-bold text-gray-900 flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-[#5B7BFE] flex items-center justify-center">
                  <Target size={16} strokeWidth={2.5} />
                </div>
                配置深度追踪雷达
              </h3>
            </div>

            <div className="p-8 space-y-6">
              <div>
                <label className="block text-[12px] font-bold text-gray-500 uppercase tracking-widest mb-2.5 flex justify-between items-end">
                  想持续追踪什么
                  <button
                    type="button"
                    onClick={() => void handleAssistRadarDraft()}
                    disabled={isAssistingRadar || !tempPref.prompt.trim()}
                    className="text-[11px] font-semibold text-indigo-500 flex items-center gap-1 bg-indigo-50 px-2.5 py-1 rounded-full border border-indigo-100 hover:bg-indigo-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isAssistingRadar ? <RefreshCw size={10} className="animate-spin" /> : <Sparkles size={10} />}
                    {isAssistingRadar ? 'AI 补强中…' : '扩写指令 + 提炼标题'}
                  </button>
                </label>
                <textarea
                  value={tempPref.prompt}
                  onChange={(event) => setTempPref({ ...tempPref, prompt: event.target.value })}
                  placeholder="例如：公益咨询团队如何做产品验收；大模型在公益组织中的落地案例；筹资团队分层运营的最新打法。"
                  className="w-full bg-gray-50 border border-gray-200 rounded-2xl p-4 text-[14px] font-medium outline-none focus:bg-white focus:border-[#5B7BFE] min-h-[120px] resize-none"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-[1.2fr_0.8fr] gap-6">
                <div>
                  <label className="block text-[12px] font-bold text-gray-500 uppercase tracking-widest mb-2.5">雷达标签名</label>
                  <input
                    type="text"
                    value={tempPref.title}
                    onChange={(event) => setTempPref({ ...tempPref, title: event.target.value })}
                    placeholder="可手动填写，或使用上方 AI 一键补强"
                    className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none focus:bg-white focus:border-[#5B7BFE]"
                  />
                </div>

                <div>
                  <label className="block text-[12px] font-bold text-gray-500 uppercase tracking-widest mb-2.5">时间范围</label>
                  <select
                    value={tempPref.timeRange}
                    onChange={(event) => setTempPref({ ...tempPref, timeRange: event.target.value })}
                    className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none focus:bg-white focus:border-[#5B7BFE]"
                  >
                    <option value="3_days">近 3 天</option>
                    <option value="7_days">近 7 天</option>
                    <option value="30_days">近 30 天</option>
                  </select>
                </div>
              </div>

              <div className="rounded-[24px] border border-gray-100 bg-gray-50/60 p-5">
                <label className="block text-[12px] font-bold text-gray-500 uppercase tracking-widest mb-2.5">优先检索网址</label>
                <p className="text-[12px] text-gray-500 leading-6">
                  大周会优先结合这些站点做检索。输入网址后，会自动生成一个简短标签。
                </p>
                <div className="mt-4 flex gap-2">
                  <input
                    type="text"
                    value={preferredSourceDraft}
                    onChange={(event) => setPreferredSourceDraft(event.target.value)}
                    placeholder="例如：https://www.chinadevelopmentbrief.org.cn 或机构公告页网址"
                    className="flex-1 bg-white border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none focus:border-[#5B7BFE]"
                  />
                  <button
                    type="button"
                    onClick={() => void handleAddPreferredSource()}
                    disabled={isGeneratingSourceLabel || !preferredSourceDraft.trim()}
                    className="px-4 py-3 rounded-2xl text-[12px] font-semibold bg-indigo-50 border border-indigo-100 text-indigo-700 hover:bg-indigo-100 transition-all disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2 shrink-0"
                  >
                    {isGeneratingSourceLabel ? <RefreshCw size={14} className="animate-spin" /> : <Sparkles size={14} />}
                    {isGeneratingSourceLabel ? '生成中…' : 'AI 生成标签'}
                  </button>
                </div>
                {tempPref.preferredSources.length > 0 ? (
                  <div className="mt-4 space-y-2">
                    {tempPref.preferredSources.map((item) => (
                      <div key={item.url} className="rounded-2xl border border-indigo-100 bg-white px-4 py-3 flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="inline-flex items-center rounded-full border border-indigo-100 bg-indigo-50 px-2.5 py-1 text-[11px] font-bold text-indigo-700">
                            {item.label}
                          </div>
                          <p className="text-[12px] text-gray-500 mt-2 break-all">{item.url}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleRemovePreferredSource(item.url)}
                          className="text-[12px] font-semibold text-gray-400 hover:text-rose-500 transition-colors shrink-0"
                        >
                          删除
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[12px] text-gray-400 mt-4">还没有优先网址。默认会先做全网检索。</p>
                )}
              </div>
            </div>

            <div className="px-8 py-5 border-t border-gray-100 bg-gray-50/50 flex justify-end gap-3">
              <button type="button" onClick={() => { setEditingPrefIndex(null); setTempPref(null); setPreferredSourceDraft(''); }} className="text-[13px] font-bold text-gray-500 hover:text-gray-800 px-5 py-2 transition-colors">
                取消
              </button>
              <button
                type="button"
                onClick={() => void handleSavePrefEdit()}
                className="px-6 py-2.5 rounded-xl text-[13px] font-semibold bg-[#5B7BFE] text-white shadow-[0_4px_12px_rgba(91,123,254,0.3)] hover:bg-[#4a6be6] transition-all inline-flex items-center gap-2"
              >
                保存配置
              </button>
            </div>
          </div>
        </div>
      )}

      {taskModalCandidate && taskDraft && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-md z-50 flex items-center justify-center animate-in fade-in">
          <div className="bg-white rounded-[28px] shadow-[0_20px_60px_rgba(0,0,0,0.15)] w-[760px] max-h-[88vh] overflow-hidden transform animate-in zoom-in-95 border border-gray-100" onClick={(event) => event.stopPropagation()}>
            <div className="px-8 py-6 border-b border-gray-100 flex items-center gap-4 bg-white">
              <button
                type="button"
                onClick={() => { if (!isSubmittingTask) { setTaskModalCandidateId(null); setTaskDraft(null); setTaskAssignees([]); } }}
                className="rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="关闭同步到任务弹窗"
                disabled={isSubmittingTask}
              >
                <X size={18} />
              </button>
              <div>
                <h3 className="text-[18px] font-bold text-gray-900 flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-blue-50 text-[#5B7BFE] flex items-center justify-center">
                    <CheckSquare size={16} strokeWidth={2.5} />
                  </div>
                  同步到任务
                </h3>
                <p className="text-[12px] text-gray-500 mt-1">这里只创建一条任务，并把当前情报的摘要、观点、原文链接写进任务备注。</p>
              </div>
            </div>

            <div className="p-8 space-y-5 overflow-y-auto max-h-[calc(88vh-150px)]">
              <div className="rounded-[24px] border border-blue-100 bg-blue-50/50 px-5 py-4">
                <p className="text-[11px] font-bold uppercase tracking-[0.24em] text-[#5B7BFE]">当前情报</p>
                <h4 className="text-[16px] font-bold text-gray-900 mt-2">{taskModalCandidate.title}</h4>
                <p className="text-[12px] text-gray-600 mt-2 leading-6">{taskModalCandidate.summary}</p>
              </div>

              {isPreparingTaskModal ? (
                <div className="rounded-[24px] border border-gray-100 bg-gray-50 px-5 py-10 text-center text-gray-500 flex flex-col items-center gap-3">
                  <RefreshCw size={20} className="animate-spin text-[#5B7BFE]" />
                  <p className="text-[13px] font-medium">正在准备任务表单与情报附件…</p>
                </div>
              ) : (
                <>
                  <div className="space-y-3">
                    <input
                      value={taskDraft.title}
                      onChange={(event) => setTaskDraft((prev) => (prev ? { ...prev, title: event.target.value } : prev))}
                      placeholder="任务标题"
                      className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[14px] font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                    />
                    <textarea
                      value={taskDraft.desc}
                      onChange={(event) => setTaskDraft((prev) => (prev ? { ...prev, desc: event.target.value } : prev))}
                      placeholder="任务说明"
                      className="w-full min-h-[96px] bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] leading-6 font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <select
                      value={taskDraft.ownerId}
                      onChange={(event) => {
                        const owner = taskOwnerOptions.find((item) => item.id === event.target.value);
                        setTaskDraft((prev) =>
                          prev
                            ? {
                                ...prev,
                                ownerId: event.target.value,
                                ownerName: owner?.fullName || prev.ownerName,
                              }
                            : prev,
                        );
                      }}
                      className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                    >
                      <option value="">请选择负责人</option>
                      {taskOwnerOptions.map((candidate) => (
                        <option key={candidate.id} value={candidate.id}>
                          {candidate.fullName}{candidate.isSelf ? '（自己）' : ''}
                        </option>
                      ))}
                    </select>

                    <select
                      value={taskDraft.listId}
                      onChange={(event) => setTaskDraft((prev) => (prev ? { ...prev, listId: event.target.value } : prev))}
                      className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                    >
                      {activeTaskLists.map((list) => (
                        <option key={list.id} value={list.id}>
                          {list.name}
                        </option>
                      ))}
                    </select>

                    <input
                      type="date"
                      value={taskDraft.dueDate}
                      onChange={(event) =>
                        setTaskDraft((prev) =>
                          prev
                            ? {
                                ...prev,
                                dueDate: event.target.value,
                                ddl: event.target.value || prev.ddl,
                              }
                            : prev,
                        )
                      }
                      className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                    />

                    <select
                      value={taskDraft.priority}
                      onChange={(event) => setTaskDraft((prev) => (prev ? { ...prev, priority: event.target.value as TopicQuickTaskDraft['priority'] } : prev))}
                      className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                    >
                      <option value="low">低优先级</option>
                      <option value="normal">普通优先级</option>
                      <option value="high">高优先级</option>
                    </select>
                  </div>

                  <input
                    value={taskDraft.ddl}
                    onChange={(event) => setTaskDraft((prev) => (prev ? { ...prev, ddl: event.target.value } : prev))}
                    placeholder="时间描述，例如 本周内 / 3 月 18 日前 / 待确认"
                    className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                  />

                  <textarea
                    value={taskDraft.note}
                    onChange={(event) => setTaskDraft((prev) => (prev ? { ...prev, note: event.target.value } : prev))}
                    placeholder="给同事的补充说明。系统会自动把情报摘要、核心观点和原文链接附在任务备注里。"
                    className="w-full min-h-[120px] bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] leading-6 font-medium outline-none focus:border-[#5B7BFE] focus:bg-white"
                  />
                </>
              )}
            </div>

            <div className="px-8 py-5 border-t border-gray-100 bg-gray-50/50 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => {
                  if (isSubmittingTask) return;
                  setTaskModalCandidateId(null);
                  setTaskDraft(null);
                  setTaskAssignees([]);
                }}
                className="text-[13px] font-bold text-gray-500 hover:text-gray-800 px-5 py-2 transition-colors"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void handleSubmitTask()}
                disabled={isPreparingTaskModal || isSubmittingTask}
                className="px-6 py-2.5 rounded-xl text-[13px] font-semibold bg-[#5B7BFE] text-white shadow-[0_4px_12px_rgba(91,123,254,0.3)] hover:bg-[#4a6be6] disabled:opacity-60 disabled:cursor-not-allowed transition-all inline-flex items-center gap-2"
              >
                {isSubmittingTask ? <RefreshCw size={14} className="animate-spin" /> : <CheckSquare size={14} />}
                {isSubmittingTask ? '同步中…' : '确认同步到任务'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
