import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import {
  CheckSquare,
  Settings,
  Plus,
  AlertCircle,
  CheckCircle2,
  Bot,
  Circle,
  Search,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  PlayCircle,
  Sparkles,
  UploadCloud,
  Briefcase,
  FolderOpen,
  Copy,
  Download,
  ExternalLink,
  Clock,
  ShieldAlert,
  BrainCircuit,
  Zap,
  LayoutTemplate,
  Target,
  BookOpen,
  Newspaper,
  RefreshCw,
  Minus,
  Inbox,
  Activity,
  Calendar as CalendarIcon,
  Flag,
  FolderDot,
  ArrowUp,
  FileBadge,
  Database,
  Layers,
  PenTool,
  Users,
  User,
  GitCommit,
  Layout,
  LayoutDashboard,
  GitMerge,
  Radio,
  Paperclip,
  Info,
  UserPlus,
  Trash2,
  Pencil,
  Square,
  X,
} from 'lucide-react';

import type {
  AiProvider,
  AgentWorklog,
  AgentWeeklyDigest,
  AgentWeeklyPlanPayload,
  AgentWeeklyPlan,
  AppSettings,
  AuthState,
  ChatMessage,
  ClientAnalysisRun,
  ClientDnaModule,
  ClientTemplateFillRun,
  ClientSummary,
  ClientTemplateFillField,
  ClientWorkspace,
  ClientWorkspaceSettings,
  CollabRepoStatus,
  CoachCaseRecord,
  CoachReminderRule,
  PullPreview,
  PushPreview,
  DepartmentOption,
  DeepDnaRecord,
  DesktopAppInfo,
  EmployeeRecord,
  EvidenceItem,
  EventLine,
  EventLineClarificationDraftResult,
  EventLineDetail,
  ExpenseEvidenceImportPayload,
  ExpenseEvidenceRecord,
  ExpenseImportSearchPayload,
  FeishuDeliveryProfile,
  OrgFeishuIntegration,
  OrgFeishuIntegrationPayload,
  OrgDingtalkFinanceIntegration,
  OrgDingtalkFinanceIntegrationPayload,
  GrowthContextLink,
  HandbookEntry,
  HandbookSettings,
  HealthResponse,
  HierarchyReport,
  KnowledgeSearchResult,
  LegacyScanReport,
  LocalInputMemory,
  MentionCandidate,
  OrganizationDnaModule,
  Operator,
  OrgInvitationRecord,
  OrgMembershipSummary,
  OrgWritingNorm,
  ProjectFlow,
  ProjectFlowPayload,
  ProjectModule,
  ProjectModulePayload,
  ProjectStructureResponse,
  ReviewDepartmentMember,
  ReviewDashboard,
  ReviewHistoryEntry,
  ReviewActionCard,
  ReviewActionExecutionResult,
  ReviewDashboardCardTarget,
  ReviewDashboardDrillTargetResponse,
  ReviewGovernanceSettings,
  OrgModelSettings,
  SupportRequestRecord,
  SystemAdminSettings,
  Task,
  TaskAttachmentRecord,
  TaskContextPreview,
  TaskExpenseEvidenceLink,
  TaskSmartBrief,
  TaskList,
  TaskGroupTemplateEventLineMode,
  TaskGroupTemplatePayload,
  TaskGroupTemplateRecord,
  TaskMutationPayload,
  TaskProjectContext,
  TaskSettings,
  TaskScopeMode,
  TaskTag,
  TaskViewDefinition,
  TaskViewFilterSet,
  TopicCandidate,
  TopicsSettings,
  TopicRadar,
  UpdateProfilePayload,
  WeeklyReviewTaskEntry,
  WeeklyReviewTaskStructuredNote,
  WorkObjectTerminologyState,
} from '../shared/types';
import {
  getTodayCalendarState,
  buildCalendarCells,
  formatMonthTitle,
  shiftCalendarMonth,
} from '../shared/calendar';
import {
  adminResetPassword,
  approveTaskReview,
  changePassword,
  completeTaskWithReview,
  confirmTask,
  clearDemoData,
  approveEmployee,
  createBackup,
  createClient,
  createClientTextDocument,
  createEventLine,
  createProjectFlow,
  createProjectModule,
  deleteClient,
  deleteClientFolder,
  createGoal,
  launchFeishuMeeting,
  createHandbook,
  createMeeting,
  createSupportRequest,
  createTask,
  createTaskGroupTemplate,
  createTaskList,
  createTaskTag,
  createWeeklyReview,
  deleteTask,
  deleteTaskGroupTemplate,
  deleteTaskList,
  deleteTaskTag,
  deleteEventLine,
  closeEventLine,
  reopenEventLine,
  disableEmployee,
  extractMeeting,
  getAgentWorklogs,
  getAuthState,
  getActivityLogs,
  getAnalysisTools,
  getFundraisingCases,
  getFundraisingRunComparison,
  cancelClientAnalysisRun,
  getDepartmentOptions,
  getClientKnowledgeStatus,
  getClientDnaDocuments,
  getEventLine,
  getEventLines,
  getClients,
  getClientWorkspaceSettings,
  getClientWorkspace,
  getClientProjectStructure,
  deleteProjectModule,
  fetchExpenseEvidenceAttachments,
  getProjectFlowDetail,
  getProjectModuleDetail,
  getEmployees,
  backfillOrgTaskLinks,
  getFeishuDeliveryProfile,
  getOrgFeishuIntegration,
  getOrgMembershipSummary,
  getHealth,
  getHandbook,
  getHandbookSettings,
  getLocalInputMemory,
  getMentionCandidates,
  getOrganizationDna,
  getOrgDingtalkFinanceIntegration,
  getOrgModelProfile,
  getReviewHistory,
  getReviewGovernanceSettings,
  getReviewDashboardDrillTarget,
  getReviews,
  getSettings,
  getSupportRequests,
  getSystemAdminSettings,
  getTaskTagSuggestions,
  getTaskBoard,
  importExpenseEvidences,
  linkEventLineExpenseEvidence,
  linkTaskExpenseEvidence,
  listEventLineExpenseEvidences,
  listTaskExpenseEvidences,
  listExpenseEvidences,
  listTaskGroupTemplates,
  getTaskLists,
  getWorkObjectTerminology,
  getTaskContextPreview,
  getTaskUnderstanding,
  getTaskSettings,
  getTopics,
  getTopicsSettings,
  getCollabRepoStatus,
  generateClientDnaCandidates,
  createFundraisingManualDna,
  createFundraisingWebDnaDraft,
  generateEventLineClarificationDraft,
  importFundraisingDna,
  importPaths,
  loadDemoData,
  login,
  ingestMeeting,
  logout,
  markTaskNotificationRead,
  processPendingConsultationKnowledgeRequests,
  previewPullFromMain,
  previewPushToMain,
  publishFundraisingDna,
  publishMeeting,
  rejectTask,
  rebuildAndInstallFromRepo,
  resolveSupportRequest,
  returnTaskReview,
  rebuildClientKnowledge,
  register,
  commitAndPushToMain,
  rejectEmployeeReview,
  resolveMeeting,
  runAnalysis,
  saveAiInputMemory,
  saveCloudAuthInputMemory,
  saveOrgDingtalkFinanceIntegration,
  saveFeishuDeliveryProfile,
  saveFeishuInputMemory,
  scanLegacy,
  searchExpenseEvidenceImports,
  searchClientKnowledge,
  getClientAnalysisRun,
  getClientChatThread,
  startClientMessage,
  getClientMessage,
  updateEmployeeRole,
  updateEmployeeDepartment,
  addEventLineNote,
  adoptTaskSmartBriefAction,
  updateEventLine,
  saveOrgFeishuIntegration,
  updateClient,
  updateClientWorkspaceSettings,
  updateProjectFlow,
  updateProjectModule,
  updateSettings,
  updateClientDnaDocument,
  updateHandbookSettings,
  updateOrgModelProfile,
  updateOrganizationDnaModule,
  updateProfile,
  updateReviewGovernanceSettings,
  updateSystemAdminSettings,
  upsertFundraisingReminderRule,
  upsertFundraisingWritingNorm,
  updateAgentWeeklyPlan,
  updateTaskList,
  updateTaskGroupTemplate,
  updateTaskSettings,
  updateTaskTag,
  updateTask,
  updateWorkObjectTerminology,
  uploadTaskAttachment,
  unlinkEventLineExpenseEvidence,
  unlinkTaskExpenseEvidence,
  updateTopicsSettings,
  upsertDna,
  vectorizeAnswer,
  exportAnswer,
  startClientTemplateFill,
  getClientTemplateFillRun,
  applyTaskGroupTemplate,
  backfillClientWorkspaceImports,
  pullSelectedFromMain,
  selectCollabRepo,
} from './lib/api';
import { getClientDnaPromptTemplate } from './lib/clientDnaPromptTemplates';
import { resolveWorkObjectTerminology } from './lib/workObjectTerminology';
import {
  formatTaskTimelineLabel as formatUnifiedTaskTimelineLabel,
  resolveTaskDateTimeRange as resolveUnifiedTaskDateTimeRange,
  resolveTaskTimelineDateTime as resolveUnifiedTaskTimelineDateTime,
  taskDateForCalendar as resolveUnifiedTaskDateForCalendar,
} from './lib/taskTimeline';
import { ClientProjectSetupPage } from './components/client_workspace/ClientProjectSetupPage';
import { EventLineClarificationComposer } from './components/tasks/EventLineClarificationComposer';
import EventLineEditorModal, {
  type EventLineEditorDraft,
  type EventLineProjectOption,
} from './components/tasks/EventLineEditorModal';
import EventLineReportPanel from './components/tasks/EventLineReportPanel';
import type { ReportDraft } from './components/tasks/EventLineReportPanel';
import { TaskTemplateEditorModal } from './components/tasks/TaskTemplateEditorModal';
import type { TemplateData } from './components/tasks/TaskTemplateEditorModal';
import { SystemLogPanel } from './components/settings/SystemLogPanel';
import { StrategicBrainView, type ThoughtTaskPayload } from './components/strategic_accompaniment/StrategicBrainView';
import { TopicsManagementView } from './components/topics/TopicsManagementView';
import { TaskCalendarView } from './components/tasks/TaskCalendarView';
import { AgentSimulationCalendarView } from './components/tasks/AgentSimulationCalendarView';
import { AgentWeeklyPlanEditor } from './components/tasks/AgentWeeklyPlanEditor';
import { ReviewHistoryPicker } from './components/tasks/ReviewHistoryPicker';
import { TaskOrgContextPanel } from './components/tasks/TaskOrgContextPanel';
import { WeeklyReviewSummaryPanel } from './components/tasks/WeeklyReviewSummaryPanel';
import { UnderstandingPanel } from './components/tasks/UnderstandingPanel';
import { WeeklyReviewStructuredFields, composeReviewNoteFromStructuredFields, createEmptyReviewStructuredNote, hasMeaningfulReviewStructuredNote } from './components/tasks/WeeklyReviewStructuredFields';
import { reviewStatusLabel, reviewTaskDateLabel, type ReviewTaskRow } from './components/tasks/reviewDraft';
import { GrowthProvider, notifyGrowthRefresh } from './components/growth/GrowthContext';
import { GrowthCenterView } from './components/handbook/GrowthCenterView';
import { BrandLogoMark, BrandLogoSettingsCard } from './components/settings/BrandLogoSettingsCard';
import { DingtalkFinanceIntegrationPanel } from './components/settings/DingtalkFinanceIntegrationPanel';
import { FeishuOrgIntegrationPanel } from './components/settings/FeishuOrgIntegrationPanel';
import { ExpenseEvidenceModal } from './components/work_objects/ExpenseEvidenceModal';
import type { OrgModelTab } from './components/settings/OrganizationModelSettingsPanel';
import { OrganizationSetupCenter } from './components/settings/OrganizationSetupCenter';
import { ReviewGovernanceSettingsPanel } from './components/settings/ReviewGovernanceSettingsPanel';
import { CollabPreviewDialog } from './components/collab/CollabDialogs';
import { CollabSyncCard } from './components/collab/CollabSyncCard';

type TemplateFillStage = 'queued' | 'parsing' | 'retrieving' | 'writing' | 'completed' | 'failed';

type TemplateFillDialogState = {
  open: boolean;
  runId: string | null;
  templateName: string;
  templatePathRaw: string;
  allowFallbackImport: boolean;
  startedAt: number;
  stage: TemplateFillStage;
  backendStatus: string;
  backendPhase: string | null;
  percent: number;
  statusLabel: string;
  hint: string;
  evidenceTitles: string[];
  fieldCount: number;
  processedCount: number;
  filledCount: number;
  missingCount: number;
  currentFieldLabel: string | null;
  attachmentChecklist: string[];
  fields: ClientTemplateFillField[];
  outputPath: string | null;
  errorMessage: string | null;
};

type ImportFeedback = {
  tone: 'info' | 'success' | 'error';
  text: string;
  detail?: string;
  timestamp: number;
};

type NavKey = 'tasks' | 'client_workspace' | 'strategic_accompaniment' | 'topics_management' | 'growth_handbook' | 'settings';
type TaskViewMode = 'inbox' | 'list' | 'calendar' | 'agent_schedule' | 'review' | 'event_lines';
type ClientOverlayMode = 'meeting' | 'goal' | 'dna' | 'paste_document' | null;
type SettingsSectionKey = 'overview' | 'org_dna' | 'tasks' | 'client_workspace' | 'topics' | 'handbook' | 'system_admin' | 'org_overview' | 'org_departments' | 'org_people' | 'org_rules' | 'system_logs';
type ReviewFormState = {
  weekLabel: string;
  entriesByTaskId: Record<string, WeeklyReviewTaskStructuredNote>;
};

type ClientTextDocumentDraft = {
  title: string;
  content: string;
  titleEdited: boolean;
};

type ReviewTaskGroup = {
  id: string;
  eventLineId: string | null;
  eventLineName: string | null;
  title: string;
  rows: ReviewTaskRow[];
  taskCount: number;
  completedCount: number;
  pendingCount: number;
  reviewedCount: number;
  sharedStructuredNote: WeeklyReviewTaskStructuredNote;
  hasDivergentNotes: boolean;
  taskStatus: Task['status'];
};

type GrowthContextJumpRequest = {
  requestId: string;
  context: GrowthContextLink;
};

type EventLineClarificationState = EventLineClarificationDraftResult & {
  transcript: string;
};

type TaskEventLineCreateDraftState = {
  name: string;
  stage: string;
  summary: string;
  intent: string;
  currentBlocker: string;
  nextStep: string;
  recentDecision: string;
};

type TaskGroupTemplateStepOverrideDraft = {
  stepIndex: number;
  title: string;
  ownerId: string;
  ownerName: string;
  collaboratorIds: string[];
  collaboratorNames: string[];
  priority: 'low' | 'normal' | 'high';
  durationDays: number;
  daysAfterPrevious: number;
};

type TaskGroupTemplateApplyDraftState = {
  startDate: string;
  startTime: string;
  listId: string;
  workObjectId: string;
  eventLineMode: TaskGroupTemplateEventLineMode;
  eventLineId: string;
  eventLineName: string;
  stepOverrides: TaskGroupTemplateStepOverrideDraft[];
};

type CollabDialogState =
  | {
      mode: 'push';
      preview: PushPreview;
    }
  | {
      mode: 'pull';
      preview: PullPreview;
    }
  | null;

type ExpenseEvidenceModalContext = {
  workObjectId: string;
  workObjectName: string;
  eventLineId?: string | null;
  eventLineName?: string | null;
  taskId?: string | null;
  taskTitle?: string | null;
};

function buildEventLineClarificationDraft(
  eventLine?: Pick<EventLine, 'summary' | 'stage' | 'intent' | 'currentBlocker' | 'nextStep' | 'recentDecision'> | null,
): EventLineClarificationState {
  return {
    transcript: '',
    summary: eventLine?.summary || '',
    stage: eventLine?.stage || '',
    intent: eventLine?.intent || '',
    currentBlocker: eventLine?.currentBlocker || '',
    nextStep: eventLine?.nextStep || '',
    recentDecision: eventLine?.recentDecision || '',
    missingInfo: [],
    confidence: 'medium',
  };
}

function buildTaskEventLineCreateDraft(): TaskEventLineCreateDraftState {
  return {
    name: '',
    stage: '本周推进',
    summary: '',
    intent: '',
    currentBlocker: '',
    nextStep: '',
    recentDecision: '',
  };
}

function buildTaskGroupTemplateApplyDraft(
  template: TaskGroupTemplateRecord,
  defaults?: Partial<TaskGroupTemplateApplyDraftState>,
): TaskGroupTemplateApplyDraftState {
  return {
    startDate: defaults?.startDate || formatDateOnlyValue(new Date()),
    startTime: defaults?.startTime || TASK_DEFAULT_DUE_TIME,
    listId: defaults?.listId || '',
    workObjectId: defaults?.workObjectId ?? (template.workObjectId || template.clientId || ''),
    eventLineMode: defaults?.eventLineMode || 'none',
    eventLineId: defaults?.eventLineId || '',
    eventLineName: defaults?.eventLineName || `${template.name}执行线`,
    stepOverrides: template.steps.map((step, index) => ({
      stepIndex: index,
      title: step.title || '',
      ownerId: step.ownerId || '',
      ownerName: step.ownerName || '',
      collaboratorIds: step.collaboratorIds || [],
      collaboratorNames: step.collaboratorNames || [],
      priority: step.priority,
      durationDays: step.durationDays,
      daysAfterPrevious: step.daysAfterPrevious,
    })),
  };
}

function buildEmptyEventLineEditorDraft(defaults?: Partial<EventLineEditorDraft>): EventLineEditorDraft {
  return {
    name: '',
    kind: 'project_line',
    primaryClientId: '',
    ownerId: '',
    ownerIds: [],
    summary: '',
    stage: '本周推进',
    currentBlocker: '',
    recentDecision: '',
    nextStep: '',
    participantIds: [],
    ...defaults,
  };
}

function buildEventLineEditorDraftFromDetail(detail: EventLineDetail): EventLineEditorDraft {
  const ownerIds = detail.eventLine.ownerIds?.length
    ? detail.eventLine.ownerIds
    : detail.eventLine.ownerId
      ? [detail.eventLine.ownerId]
      : [];
  return {
    name: detail.eventLine.name || '',
    kind: detail.eventLine.kind || 'project_line',
    primaryClientId: detail.eventLine.primaryClientId || '',
    ownerId: ownerIds[0] || detail.eventLine.ownerId || '',
    ownerIds,
    summary: detail.eventLine.summary || '',
    stage: detail.eventLine.stage || '',
    currentBlocker: detail.eventLine.currentBlocker || '',
    recentDecision: detail.eventLine.recentDecision || '',
    nextStep: detail.eventLine.nextStep || '',
    participantIds: detail.eventLine.participantIds || [],
  };
}

type TaskEditorState = {
  id: string | null;
  scopeMode: TaskScopeMode;
  scopeModeTouched: boolean;
  title: string;
  desc: string;
  listId: string;
  listIds: string[];
  priority: 'low' | 'normal' | 'high';
  priorityTouched: boolean;
  priorityReason: string;
  ownerId: string;
  startDate: string;
  startTime: string;
  dueDate: string;
  dueTime: string;
  hasSpecificDueTime: boolean;
  durationMinutes: number;
  clientId: string;
  clientTouched: boolean;
  clientConfidence: 'none' | 'low' | 'medium' | 'high' | 'manual';
  clientReason: string;
  eventLineId: string;
  eventLineTouched: boolean;
  eventLineReason: string;
  projectModuleId: string;
  projectModuleTouched: boolean;
  projectModuleReason: string;
  projectFlowId: string;
  projectFlowTouched: boolean;
  projectFlowReason: string;
  ddl: string;
  tagIds: string[];
  collaborators: MentionCandidate[];
};

const TASK_DEFAULT_DUE_TIME = '09:00';
const PERSONAL_TASK_KEYWORD_RULES = [
  { label: '吃饭社交', pattern: /(吃饭|午饭|午餐|晚饭|晚餐|早餐|约饭|聚餐|喝咖啡|喝茶)/i },
  { label: '家庭事项', pattern: /(家人|父母|孩子|接娃|送娃|家庭|回家|家里)/i },
  { label: '健康生活', pattern: /(健身|跑步|瑜伽|游泳|体检|医院|看病|牙医|理疗|理发)/i },
  { label: '个人安排', pattern: /(约会|朋友|聚会|休息|买菜|购物|看电影|逛街)/i },
] as const;

function inferPersonalTaskKeywordLabels(title: string, desc: string) {
  const haystack = `${title}\n${desc}`.trim();
  if (!haystack) return [];
  return PERSONAL_TASK_KEYWORD_RULES
    .filter((rule) => rule.pattern.test(haystack))
    .map((rule) => rule.label);
}

const colorPalette = ['#888681', '#5B7BFE', '#10B981', '#F59E0B', '#F43F5E', '#8B5CF6', '#06B6D4'];
const providerDefaultModels = {
  mock: 'mock-summarizer',
  qwen: 'qwen3.5-plus',
  doubao: 'doubao-seed-2-0-pro-260215',
} as const;

const providerDisplayNames = {
  mock: '本地 Mock',
  qwen: 'Qwen 3.5',
  doubao: '豆包 Seed 2.0 Pro（火山方舟）',
} as const;

function inferCloudVendorLabel(cloudApiUrl?: string | null) {
  const value = (cloudApiUrl || '').trim();
  if (!value) return '未配置';
  try {
    const hostname = new URL(value).hostname.toLowerCase();
    if (hostname === '127.0.0.1' || hostname === 'localhost') return '本地调试云端';
    if (
      hostname === '101.126.34.232'
      || hostname.includes('volcengine')
      || hostname.includes('volces')
      || hostname.includes('bytedance')
    ) {
      return '火山云';
    }
    if (hostname.includes('cloudflare')) return 'Cloudflare';
    if (hostname.includes('aliyun') || hostname.includes('aliyuncs')) return '阿里云';
    if (hostname.includes('tencent') || hostname.includes('qcloud')) return '腾讯云';
    return '自定义云端';
  } catch {
    return '自定义云端';
  }
}

const COLLAB_REPO_PATH_STORAGE_KEY = 'yiyu-collab-repo-path';
const EVENT_LINE_PROJECT_FILTER_STORAGE_KEY = 'yiyu-event-line-project-filter';
const COLLAB_PRIMARY_REPO_NAME = 'yiyu-thinktank-workbench';
const COLLAB_LEGACY_REPO_NAME = 'yiyu-thinktank-workbench-main-sync';
const COLLAB_VISIBLE_WORKSPACE_SEGMENT = '/openclaw/workspace';
const COLLAB_HIDDEN_WORKSPACE_SEGMENT = '/.openclaw/workspace';

function normalizeCollabRepoPathValue(rawPath: string) {
  return rawPath.replace(/[\\/]+$/, '');
}

function normalizeInitialCollabRepoPath(storedPath: string | null) {
  if (!storedPath) return null;
  let normalized = normalizeCollabRepoPathValue(storedPath);
  if (normalized.includes(COLLAB_HIDDEN_WORKSPACE_SEGMENT)) {
    normalized = normalized.replace(COLLAB_HIDDEN_WORKSPACE_SEGMENT, COLLAB_VISIBLE_WORKSPACE_SEGMENT);
  }
  if (normalized.endsWith(`/${COLLAB_LEGACY_REPO_NAME}`)) {
    return normalized.slice(0, -COLLAB_LEGACY_REPO_NAME.length) + COLLAB_PRIMARY_REPO_NAME;
  }
  if (normalized.endsWith('/workspace')) {
    return `${normalized}/${COLLAB_PRIMARY_REPO_NAME}`;
  }
  return normalized;
}

const REQUIRED_BACKEND_FEATURES = [
  'knowledge.vectorize-answer',
  'knowledge.reclass-events',
  'knowledge.search',
  'knowledge.rebuild',
  'chat.general-answer',
  'chat.instant-send',
  'chat.async-status',
] as const;

const DEFAULT_TASK_SETTINGS: TaskSettings = {
  defaultListId: null,
  defaultPriority: 'normal',
  defaultDueDatePreset: 'today',
  defaultViewMode: 'calendar',
  listSortMode: 'manual',
  showCompletedTasks: false,
  defaultReviewScope: 'work',
  autoAssignSelf: true,
  updatedAt: '',
};

const EMPTY_REVIEW_GOVERNANCE_SETTINGS: ReviewGovernanceSettings = {
  departments: [],
  updatedAt: '',
};

const EMPTY_ORG_MODEL_SETTINGS: OrgModelSettings = {
  organization: {
    organizationId: '',
    name: '',
    annualGoal: '',
    annualStrategyYear: '',
    annualStrategy: '',
    quarterPlans: [],
    quarterlyFocus: [],
    leaderUserId: null,
    managementUserIds: [],
    updatedAt: '',
  },
  departments: [],
  roles: [],
  bindings: [],
  reportingLines: [],
  taskControlRules: [],
  roleProcessTemplates: [],
  focusItems: [],
  departmentPlans: [],
  updatedAt: '',
};

const ORGANIZATION_DNA_MODULES: Array<{ moduleKey: OrganizationDnaModule['moduleKey']; title: string; helper: string }> = [
  { moduleKey: 'organization_intro', title: '组织介绍', helper: '上传机构整体介绍、历史、使命、核心问题。' },
  { moduleKey: 'business_intro', title: '业务介绍', helper: '上传业务模型、服务方式、关键产品或项目机制。' },
  { moduleKey: 'team_intro', title: '团队介绍', helper: '上传团队结构、关键角色、负责人和协作分工。' },
  { moduleKey: 'market_intro', title: '市场介绍', helper: '上传行业定位、竞品、需求和市场调研结论。' },
];

const CLIENT_DNA_MODULES: Array<{ moduleKey: ClientDnaModule['moduleKey']; title: string; helper: string }> = [
  { moduleKey: 'organization_intro', title: '组织介绍', helper: '上传该客户的组织介绍、历史、使命与核心定位。' },
  { moduleKey: 'business_intro', title: '项目介绍', helper: '上传该客户的项目介绍、核心服务、业务机制与代表项目。' },
  { moduleKey: 'team_intro', title: '团队介绍', helper: '上传该客户的团队结构、关键角色、负责人和协作分工。' },
  { moduleKey: 'market_intro', title: '市场背景介绍', helper: '上传该客户所处行业、市场背景、竞品与需求环境。' },
];

const DEFAULT_CLIENT_WORKSPACE_SETTINGS: ClientWorkspaceSettings = {
  useOrgDnaInChat: false,
  useOrgDnaInKnowledgeQa: false,
  meetingPublishDefaultListId: null,
  meetingPublishDefaultPriority: 'normal',
  defaultGoalQuarter: '',
  defaultMeetingTitlePrefix: '客户会议',
  clientDnaModeLabel: 'DNA',
  updatedAt: '',
};

const DEFAULT_TOPICS_SETTINGS: TopicsSettings = {
  chineseOnly: true,
  requireInsightBeforeActions: true,
  defaultTaskOwnerMode: 'self',
  defaultTimeRange: '3_days',
  defaultSourceStrategy: 'google_bing_news',
  useOrgDnaForInsight: true,
  useOrgDnaForTaskPlan: true,
  updatedAt: '',
};

const DEFAULT_HANDBOOK_SETTINGS: HandbookSettings = {
  defaultTags: [],
  defaultCategory: '组织沉淀',
  allowTaskSource: true,
  allowAnalysisSource: true,
  visibilityBoundary: 'organization_and_personal',
  updatedAt: '',
};

const DEFAULT_SYSTEM_ADMIN_SETTINGS: SystemAdminSettings = {
  allowBusinessSettingsForEmployees: true,
  allowOrgDnaForEmployees: true,
  protectEmployeeAdmin: true,
  protectAiAndCloud: true,
  protectCloudSecurity: true,
  brandLogoDataUrl: null,
  updatedAt: '',
};

const DEFAULT_ORG_MEMBERSHIP_SUMMARY: OrgMembershipSummary = {
  hasOrganization: false,
  organizationId: null,
  organizationName: null,
};

const DEFAULT_ORG_FEISHU_INTEGRATION: OrgFeishuIntegration = {
  organizationId: null,
  organizationName: null,
  appId: '',
  enabled: false,
  hasAppSecret: false,
  configuredBy: null,
  configuredAt: null,
  updatedAt: '',
  lastValidationStatus: 'idle',
  lastValidationMessage: null,
  recentAudits: [],
};

const DEFAULT_FEISHU_DELIVERY_PROFILE: FeishuDeliveryProfile = {
  userId: 'local-device-user',
  organizationId: null,
  organizationName: null,
  mobile: '',
  normalizedMobile: null,
  deliveryStatus: 'missing_org',
  deliveryStatusLabel: '请先连接云端并加入组织',
  readyForNotifications: false,
  receiveId: null,
  lastVerifiedAt: null,
  lastError: null,
  blockedReason: '连接云端并加入组织后，才能启用飞书任务提醒。',
};

const DEFAULT_ORG_DINGTALK_FINANCE_INTEGRATION: OrgDingtalkFinanceIntegration = {
  organizationId: null,
  organizationName: null,
  appKey: '',
  operatorMobile: '',
  resolvedOperatorUserId: null,
  enabled: false,
  hasAppSecret: false,
  syncEnabled: false,
  mappedTemplateNames: [],
  configuredBy: null,
  configuredAt: null,
  updatedAt: '',
  lastValidationStatus: 'idle',
  lastValidationMessage: '连接云端并加入或创建组织后，才能启用钉钉票据导入。',
};

const DEFAULT_EXPENSE_IMPORT_SEARCH_DRAFT: ExpenseImportSearchPayload = {
  query: '',
  applicantUserName: '',
  approvalStatus: null,
  includeImported: false,
  limit: 20,
};

const DEFAULT_LOCAL_INPUT_MEMORY: LocalInputMemory = {
  cloudAuth: {
    rememberInputs: true,
    lastEmail: null,
    accounts: [],
  },
  aiSettings: {
    rememberApiKey: false,
    apiKey: '',
  },
  feishuIntegration: {
    rememberInputs: false,
    appId: '',
    appSecret: '',
  },
};

const DEFAULT_LOCAL_AUTH_STATE: AuthState = {
  authenticated: true,
  sessionMode: 'local',
  user: {
    id: 'local-device-user',
    organizationId: 'local-device',
    email: 'local@device.yiyu',
    fullName: '本机用户',
    primaryRole: 'employee',
    accountStatus: 'approved',
  },
};

function isLocalDeviceSessionUser(user?: AuthState['user'] | null) {
  if (!user) return true;
  return (
    user.id === 'local-device-user'
    || user.organizationId === 'local-device'
    || user.email === 'local@device.yiyu'
  );
}

function normalizeAuthStateForDesktop(state: AuthState | null | undefined): AuthState {
  if (state?.authenticated && state.user) {
    const inferredSessionMode = state.sessionMode === 'cloud' || !isLocalDeviceSessionUser(state.user)
      ? 'cloud'
      : 'local';
    return {
      ...state,
      sessionMode: inferredSessionMode,
    };
  }
  return {
    ...DEFAULT_LOCAL_AUTH_STATE,
    message: state?.message || null,
  };
}

const TASK_COLOR_OPTIONS = ['#5B7BFE', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4', '#64748B', '#EC4899'];

type DisplayChatMessage = ChatMessage & {
  requestPrompt?: string;
  elapsedMs?: number;
};

const CLIENT_CHAT_DRAFT_THREAD_ID = '__client_chat_draft__';

function formatElapsedLabel(milliseconds?: number) {
  const safeValue = Math.max(milliseconds || 0, 0);
  return `${(safeValue / 1000).toFixed(1)} 秒`;
}

function mergeDisplayMessages(existingMessages: DisplayChatMessage[], incomingMessages: DisplayChatMessage[]) {
  const messageMap = new Map<string, DisplayChatMessage>();
  for (const item of existingMessages) {
    messageMap.set(item.id, item);
  }
  for (const item of incomingMessages) {
    const existing = messageMap.get(item.id);
    messageMap.set(
      item.id,
      existing
        ? {
            ...existing,
            ...item,
            requestPrompt: item.requestPrompt ?? existing.requestPrompt,
            retrievalSummary:
              item.role === 'assistant'
                ? {
                    ...(existing.retrievalSummary || {}),
                    ...(item.retrievalSummary || {}),
                  }
                : item.retrievalSummary,
          }
        : item,
    );
  }
  return Array.from(messageMap.values()).sort((left, right) => left.createdAt.localeCompare(right.createdAt));
}

function resolveLoadingPhase(summary?: Record<string, unknown> | null) {
  const raw = typeof summary?.phase === 'string' ? summary.phase : '';
  if (raw === 'retrieving' || raw === 'grounding' || raw === 'generating' || raw === 'completed' || raw === 'failed') {
    return raw;
  }
  const master = Number(summary?.masterHitCount || 0);
  const surrogate = Number(summary?.surrogateHitCount || 0);
  const rawChunk = Number(summary?.rawChunkHitCount || 0);
  return master > 0 || surrogate > 0 || rawChunk > 0 ? 'generating' : 'retrieving';
}

function loadingPhaseBounds(summary?: Record<string, unknown> | null) {
  const phase = resolveLoadingPhase(summary);
  const defaultBounds =
    phase === 'retrieving'
      ? { floor: 0, ceiling: 25 }
      : phase === 'grounding'
        ? { floor: 25, ceiling: 55 }
        : phase === 'generating'
          ? { floor: 55, ceiling: 92 }
          : { floor: 100, ceiling: 100 };
  const floor = Number(summary?.progressFloor);
  const ceiling = Number(summary?.progressCeiling);
  return {
    floor: Number.isFinite(floor) ? floor : defaultBounds.floor,
    ceiling: Number.isFinite(ceiling) ? ceiling : defaultBounds.ceiling,
  };
}

function loadingProgressValue(summary: Record<string, unknown> | null | undefined, elapsedMs: number) {
  const phase = resolveLoadingPhase(summary || null);
  if (phase === 'completed' || phase === 'failed') return 100;
  const { floor, ceiling } = loadingPhaseBounds(summary || null);
  const baseline = Math.max(floor, Math.min(Number(summary?.progress || floor), ceiling));
  const phaseSpan = Math.max(ceiling - floor, 0);
  if (phaseSpan <= 0) return baseline;
  const timeConstant = phase === 'retrieving' ? 1800 : phase === 'grounding' ? 2600 : 12000;
  const dynamic = floor + phaseSpan * (1 - Math.exp(-Math.max(elapsedMs, 0) / timeConstant));
  return Math.max(baseline, Math.min(dynamic, ceiling));
}

function loadingStageText(summary?: Record<string, unknown> | null) {
  const explicitLabel = typeof summary?.stageLabel === 'string' ? summary.stageLabel.trim() : '';
  if (explicitLabel) return explicitLabel;
  if (!summary) return '庆华正在整理背景材料，并组织分析答案';
  const master = Number(summary.masterHitCount || 0);
  const surrogate = Number(summary.surrogateHitCount || 0);
  const rawChunk = Number(summary.rawChunkHitCount || 0);
  if (master > 0 || surrogate > 0 || rawChunk > 0) {
    return '庆华已经整理好当前问题所需的背景材料，正在调用千问组织完整分析';
  }
  if (summary.failureReason) {
    return `背景整理阶段提示：${String(summary.failureReason)}`;
  }
  return '庆华正在整理背景材料，并组织分析答案';
}

function loadingSubText(summary?: Record<string, unknown> | null) {
  if (!summary) return '消息已发送。系统会先整理最相关的背景材料，再调用千问生成更完整、更专业的顾问式回答。';
  const phase = resolveLoadingPhase(summary);
  const master = Number(summary.masterHitCount || 0);
  const surrogate = Number(summary.surrogateHitCount || 0);
  const rawChunk = Number(summary.rawChunkHitCount || 0);
  if (phase === 'generating' || master > 0 || surrogate > 0 || rawChunk > 0) {
    return '背景材料已经整理完成。当前阶段主要耗时在千问组织最终答案，而不是本地资料定位。';
  }
  return '消息已发送。系统会先整理最相关的背景材料，再调用千问生成更完整、更专业的顾问式回答。';
}

function loadingPreviewText(summary?: Record<string, unknown> | null) {
  const preview = typeof summary?.previewSummary === 'string' ? summary.previewSummary.trim() : '';
  return preview;
}

function stageLabelForUi(stage?: string | null) {
  if (stage === 'master_index') return '目录概览';
  if (stage === 'surrogate') return '背景摘要';
  if (stage === 'raw_chunk') return '原文片段';
  return stage || '资料';
}

function renderInlineEmphasis(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={`${part}-${index}`} className="font-semibold text-slate-950">{part.slice(2, -2)}</strong>;
    }
    return <React.Fragment key={`${part}-${index}`}>{part}</React.Fragment>;
  });
}

function looksLikeAnswerTitle(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return false;
  if (trimmed.length < 6 || trimmed.length > 42) return false;
  if (/[。！？!?]$/.test(trimmed)) return false;
  return !/^(问题|资料简报|回答原则|当前可确认的资料事实)[:：]/.test(trimmed);
}

function normalizeAnswerTextForDisplay(rawText: string) {
  let text = rawText.replace(/\r\n/g, '\n').trim();
  const firstLineMatch = text.match(/^([^\n]{6,48}?)(\s{2,})(.+)$/s);
  if (firstLineMatch) {
    const candidateTitle = firstLineMatch[1].trim();
    const rest = firstLineMatch[3].trimStart();
    if (looksLikeAnswerTitle(candidateTitle)) {
      text = `${candidateTitle}\n\n${rest}`;
    }
  }
  text = text.replace(/\n([一二三四五六七八九十]+、)/g, '\n\n$1');
  text = text.replace(/\n(第[一二三四五六七八九十0-9]+部分)/g, '\n\n$1');
  return text;
}

type AnswerBlock =
  | { type: 'title'; text: string }
  | { type: 'heading'; text: string }
  | { type: 'subheading'; text: string }
  | { type: 'paragraph'; text: string }
  | { type: 'list'; items: string[]; ordered: boolean };

function parseAnswerBlocks(text: string): AnswerBlock[] {
  const cleaned = normalizeAnswerTextForDisplay(text);
  if (!cleaned) return [];
  const lines = cleaned.split('\n');
  const blocks: AnswerBlock[] = [];
  const firstNonEmptyIndex = lines.findIndex((line) => line.trim());
  const firstNonEmptyLine = firstNonEmptyIndex >= 0 ? lines[firstNonEmptyIndex].trim() : '';
  const visibleLineCount = lines.filter((line) => line.trim()).length;
  const treatFirstAsTitle =
    visibleLineCount > 2 &&
    firstNonEmptyLine.length >= 6 &&
    firstNonEmptyLine.length <= 34 &&
    !/[。！？!?]/.test(firstNonEmptyLine);
  let paragraphBuffer: string[] = [];
  let listBuffer: string[] = [];
  let listOrdered = false;

  const flushParagraph = () => {
    if (!paragraphBuffer.length) return;
    blocks.push({ type: 'paragraph', text: paragraphBuffer.join(' ').trim() });
    paragraphBuffer = [];
  };

  const flushList = () => {
    if (!listBuffer.length) return;
    blocks.push({ type: 'list', items: [...listBuffer], ordered: listOrdered });
    listBuffer = [];
    listOrdered = false;
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }
    if (index === firstNonEmptyIndex && treatFirstAsTitle) {
      blocks.push({ type: 'title', text: line.replace(/^#{1,6}\s*/, '') });
      continue;
    }
    const nextNonEmptyLine = lines.slice(index + 1).find((candidate) => candidate.trim())?.trim() || '';
    const previousLine = index > 0 ? lines[index - 1].trim() : '';
    const looksLikeOrderedHeading =
      /^\d+\.\s+/.test(line) &&
      line.length <= 42 &&
      !/[：:]$/.test(line) &&
      !/^(\d+\.\s+|[-*•]\s+)/.test(nextNonEmptyLine);
    const looksLikePlainHeading =
      line.length >= 4 &&
      line.length <= 22 &&
      !/[。！？!?：:]$/.test(line) &&
      !/^(\d+\.\s+|[-*•]\s+|#{1,6}\s+)/.test(line) &&
      !previousLine &&
      Boolean(nextNonEmptyLine) &&
      !/^(\d+\.\s+|[-*•]\s+)/.test(nextNonEmptyLine);
    const looksLikeSubheading =
      /^[^\n]{2,24}[：:]$/.test(line) &&
      /^(\d+\.\s+|[-*•]\s+)/.test(nextNonEmptyLine);
    if (/^#{1,6}\s+/.test(line) || /^[一二三四五六七八九十]+、/.test(line) || /^第[一二三四五六七八九十0-9]+部分/.test(line) || looksLikeOrderedHeading || looksLikePlainHeading) {
      flushParagraph();
      flushList();
      blocks.push({ type: 'heading', text: line.replace(/^#{1,6}\s*/, '') });
      continue;
    }
    if (looksLikeSubheading) {
      flushParagraph();
      flushList();
      blocks.push({ type: 'subheading', text: line });
      continue;
    }
    const unorderedMatch = line.match(/^[-*•]\s+(.+)$/);
    const orderedMatch = line.match(/^\d+\.\s+(.+)$/);
    if (unorderedMatch || orderedMatch) {
      flushParagraph();
      const nextOrdered = Boolean(orderedMatch);
      const itemText = (orderedMatch || unorderedMatch)?.[1].trim() || line;
      if (listBuffer.length && listOrdered !== nextOrdered) {
        flushList();
      }
      listOrdered = nextOrdered;
      listBuffer.push(itemText);
      continue;
    }
    paragraphBuffer.push(line);
  }

  flushParagraph();
  flushList();
  return blocks;
}

function AnswerDocument({ text }: { text: string }) {
  const blocks = useMemo(() => parseAnswerBlocks(text), [text]);
  if (!blocks.length) return null;
  const leadParagraphIndex = blocks.findIndex((block, index) => {
    if (block.type !== 'paragraph') return false;
    return blocks.slice(0, index).every((item) => item.type === 'title');
  });
  return (
    <div className="space-y-4 text-[#2c315d]">
      {blocks.map((block, index) => {
        if (block.type === 'title') {
          return (
            <div key={`title-${index}`} className="space-y-2">
              <h1 className="text-[22px] xl:text-[24px] font-semibold tracking-[-0.02em] text-[#1f275b] leading-[1.3]">
                {renderInlineEmphasis(block.text)}
              </h1>
              <div className="h-px w-16 bg-[#d8defb]" />
            </div>
          );
        }
        if (block.type === 'heading') {
          return (
            <h2 key={`heading-${index}`} className="pt-2 text-[19px] xl:text-[20px] font-semibold text-[#25306a] leading-[1.5] tracking-[-0.01em]">
              {renderInlineEmphasis(block.text)}
            </h2>
          );
        }
        if (block.type === 'subheading') {
          return (
            <h3 key={`subheading-${index}`} className="pt-1 text-[15px] xl:text-[15.5px] font-semibold text-[#2a356f] leading-7">
              {renderInlineEmphasis(block.text)}
            </h3>
          );
        }
        if (block.type === 'list') {
          const ListTag = block.ordered ? 'ol' : 'ul';
          return (
            <ListTag
              key={`list-${index}`}
              className={`${block.ordered ? 'list-decimal' : 'list-disc'} pl-6 space-y-2 text-[14.5px] xl:text-[15px] leading-7 text-[#2f376d] marker:text-[#4b63df]`}
            >
              {block.items.map((item, itemIndex) => (
                <li key={`list-item-${index}-${itemIndex}`} className="pl-1">{renderInlineEmphasis(item)}</li>
              ))}
            </ListTag>
          );
        }
        const isLead = index === leadParagraphIndex;
        return (
          <p
            key={`paragraph-${index}`}
            className={isLead
              ? 'text-[15px] xl:text-[15.5px] leading-8 text-[#24305f] font-medium'
              : 'text-[14.5px] xl:text-[15px] leading-7 text-[#30376b]'}
          >
            {renderInlineEmphasis(block.text)}
          </p>
        );
      })}
    </div>
  );
}

function WorkTracePanel({
  question,
  retrievalSummary,
  evidence,
}: {
  question: string;
  retrievalSummary?: Record<string, unknown> | null;
  evidence: Array<{
    title?: string | null;
    retrievalStage?: string | null;
    sectionLabel?: string | null;
  }>;
}) {
  const [open, setOpen] = useState(false);
  const trace = useMemo(() => {
    const payload = retrievalSummary?.workTrace;
    const normalized = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {};
    const backgroundTrail = Array.isArray(normalized.backgroundTrail)
      ? normalized.backgroundTrail.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
      : [];
    const materialTrail = Array.isArray(normalized.materialTrail)
      ? normalized.materialTrail.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
      : evidence
          .filter((item) => item.title)
          .slice(0, 6)
          .map((item) => ({
            title: item.title,
            stage: stageLabelForUi(item.retrievalStage),
            sectionLabel: item.sectionLabel,
            excerpt: '',
            path: null,
          }));
    const focus = Array.isArray(normalized.analysisFocus)
      ? normalized.analysisFocus.map((item) => String(item)).filter(Boolean)
      : [];
    const webTrail = Array.isArray(normalized.webTrail)
      ? normalized.webTrail.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
      : [];
    const clientDnaTrail = Array.isArray(normalized.clientDnaTrail)
      ? normalized.clientDnaTrail.map((item) => String(item)).filter(Boolean)
      : [];
    const problemFrame = typeof normalized.problemFrame === 'string' && normalized.problemFrame.trim()
      ? normalized.problemFrame.trim()
      : `围绕"${question}"，先建立背景理解，再确认原始证据，最后形成顾问式判断。`;
    const analysisPlan = typeof normalized.analysisPlan === 'string' ? normalized.analysisPlan.trim() : '';
    const note = typeof normalized.note === 'string' ? normalized.note.trim() : '这里展示的是本次回答如何利用背景底稿和原始证据，不是模型原始思维全文。';
    if (!problemFrame && !backgroundTrail.length && !materialTrail.length && !webTrail.length) return null;
    return { problemFrame, analysisPlan, focus, backgroundTrail, materialTrail, webTrail, clientDnaTrail, note };
  }, [evidence, question, retrievalSummary]);

  if (!trace) return null;

  return (
    <div className="rounded-[24px] border border-slate-200 bg-slate-50/90 overflow-hidden shadow-sm">
      <button
        type="button"
        className="w-full px-4 py-3.5 flex items-center justify-between text-left hover:bg-slate-100/80 transition-colors"
        onClick={() => setOpen((prev) => !prev)}
      >
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-2xl border border-emerald-100 bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <Activity size={15} />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[12px] font-semibold text-slate-800">工作轨迹</span>
              <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-500">
                原始证据 {trace.materialTrail.length} 条
              </span>
              {trace.backgroundTrail.length > 0 && (
                <span className="rounded-full border border-amber-100 bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700">
                  背景线索 {trace.backgroundTrail.length} 条
                </span>
              )}
              {trace.clientDnaTrail.length > 0 && (
                <span className="rounded-full border border-blue-100 bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-[#4b63df]">
                  DNA {trace.clientDnaTrail.length} 项
                </span>
              )}
              <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-500">
                联网补充 {trace.webTrail.length} 条
              </span>
            </div>
            <span className="text-[10px] text-slate-500">可追踪背景与证据来源，不展示原始思维全文</span>
          </div>
        </div>
        {open ? <ChevronUp size={16} className="text-slate-500" /> : <ChevronDown size={16} className="text-slate-500" />}
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-4 border-t border-slate-200/80">
          <p className="pt-3 text-[11px] leading-6 text-slate-500">{trace.note}</p>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">问题理解</p>
            <p className="mt-1 text-[13px] leading-7 text-slate-700">{trace.problemFrame}</p>
          </div>
          {trace.analysisPlan && (
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">分析方向</p>
              <p className="mt-1 text-[13px] leading-7 text-slate-700">{trace.analysisPlan}</p>
              {trace.focus.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {trace.focus.map((item) => (
                    <span key={item} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-semibold text-slate-600">
                      {item}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
          {trace.clientDnaTrail.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">背景底稿</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {trace.clientDnaTrail.map((item) => (
                  <span key={item} className="rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-[10px] font-semibold text-[#4b63df]">
                    {item}
                  </span>
                ))}
              </div>
            </div>
          )}
          {trace.backgroundTrail.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">背景线索</p>
              <div className="mt-2 space-y-2">
                {trace.backgroundTrail.map((item, index) => {
                  const title = typeof item.title === 'string' ? item.title : '';
                  const stage = typeof item.stage === 'string' ? item.stage : '';
                  const sectionLabel = typeof item.sectionLabel === 'string' ? item.sectionLabel : '';
                  const excerpt = typeof item.excerpt === 'string' ? item.excerpt : '';
                  const path = typeof item.path === 'string' ? item.path : '';
                  return (
                    <div key={`${title}-${index}`} className="rounded-2xl border border-amber-100 bg-amber-50/60 px-3 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-[12px] font-semibold text-slate-800">{title}</p>
                          <p className="mt-1 text-[11px] text-slate-500">
                            {[stage, sectionLabel].filter(Boolean).join(' · ') || '背景线索'}
                          </p>
                        </div>
                      </div>
                      {excerpt && <p className="mt-2 text-[11px] leading-6 text-slate-600">{excerpt}</p>}
                      {path && <p className="mt-2 break-all text-[10px] leading-5 text-slate-400">{path}</p>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">原始证据</p>
            <div className="mt-2 space-y-2">
              {trace.materialTrail.length > 0 ? (
                trace.materialTrail.map((item, index) => {
                  const title = typeof item.title === 'string' ? item.title : '';
                  const stage = typeof item.stage === 'string' ? item.stage : '';
                  const sectionLabel = typeof item.sectionLabel === 'string' ? item.sectionLabel : '';
                  const excerpt = typeof item.excerpt === 'string' ? item.excerpt : '';
                  const path = typeof item.path === 'string' ? item.path : '';
                  return (
                    <div key={`${title}-${index}`} className="rounded-2xl border border-slate-200 bg-white px-3 py-3 shadow-[0_4px_14px_rgba(15,23,42,0.04)]">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-[12px] font-semibold text-slate-800">{title}</p>
                          <p className="mt-1 text-[11px] text-slate-500">
                            {[stage, sectionLabel].filter(Boolean).join(' · ') || '已纳入背景材料'}
                          </p>
                        </div>
                        {stage && (
                          <span className="shrink-0 rounded-full border border-sky-100 bg-sky-50 px-2 py-0.5 text-[10px] font-semibold text-sky-700">
                            {stage}
                          </span>
                        )}
                      </div>
                      {excerpt && (
                        <p className="mt-2 text-[11px] leading-6 text-slate-600">{excerpt}</p>
                      )}
                      {path && (
                        <p className="mt-2 break-all text-[10px] leading-5 text-slate-400">{path}</p>
                      )}
                    </div>
                  );
                })
              ) : (
                <p className="text-[12px] text-slate-500">当前还没有可展示的材料路径。</p>
              )}
            </div>
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">联网补充</p>
            {trace.webTrail.length > 0 ? (
              <div className="mt-2 space-y-2">
                {trace.webTrail.map((item, index) => {
                  const title = typeof item.title === 'string' ? item.title : '';
                  const query = typeof item.query === 'string' ? item.query : '';
                  const source = typeof item.source === 'string' ? item.source : '';
                  const publishedAt =
                    typeof item.publishedAt === 'string'
                      ? item.publishedAt
                      : typeof item.published_at === 'string'
                        ? item.published_at
                        : '';
                  return (
                    <div key={`${query}-${index}`} className="rounded-2xl border border-slate-200 bg-white px-3 py-3 shadow-[0_4px_14px_rgba(15,23,42,0.04)]">
                      <p className="text-[12px] font-semibold text-slate-800">{title || query || '未命名查询'}</p>
                      <p className="mt-1 text-[11px] text-slate-500">
                        {[source, publishedAt].filter(Boolean).join(' · ') || '联网补充'}
                      </p>
                      {query && <p className="mt-2 text-[11px] leading-6 text-slate-600">搜索词：{query}</p>}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="mt-2 text-[12px] text-slate-500">本次回答未启用联网补充，当前主要基于本地资料与知识底座生成。</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function extractLoadingHits(summary?: Record<string, unknown> | null) {
  return Array.isArray(summary?.hits) ? (summary.hits as Array<Record<string, unknown>>) : [];
}

type GlobalBanner = { type: 'success' | 'error' | 'info'; text: string } | null;

const globalBannerSubscribers = new Set<(banner: GlobalBanner) => void>();
let globalBannerState: GlobalBanner = null;
let globalBannerTimer: number | null = null;

function emitGlobalBanner(nextBanner: GlobalBanner) {
  globalBannerState = nextBanner;
  globalBannerSubscribers.forEach((subscriber) => subscriber(nextBanner));
}

function showGlobalBanner(type: 'success' | 'error' | 'info', text: string) {
  if (typeof window !== 'undefined' && globalBannerTimer) {
    window.clearTimeout(globalBannerTimer);
  }
  emitGlobalBanner({ type, text });
  if (typeof window === 'undefined') return;
  globalBannerTimer = window.setTimeout(() => {
    emitGlobalBanner(null);
    globalBannerTimer = null;
  }, 2400);
}

function clearGlobalBanner() {
  if (typeof window !== 'undefined' && globalBannerTimer) {
    window.clearTimeout(globalBannerTimer);
    globalBannerTimer = null;
  }
  emitGlobalBanner(null);
}

function getGlobalBanner() {
  return globalBannerState;
}

function useGlobalBannerState() {
  const [banner, setBanner] = useState<GlobalBanner>(() => globalBannerState);
  useEffect(() => {
    globalBannerSubscribers.add(setBanner);
    return () => {
      globalBannerSubscribers.delete(setBanner);
    };
  }, []);
  return banner;
}

const GlobalBannerHost = React.memo(function GlobalBannerHost() {
  const banner = useGlobalBannerState();
  if (!banner) return null;
  return (
    <div
      className={`absolute top-4 right-4 z-50 px-4 py-2 rounded-2xl text-[12px] font-bold shadow-sm ${
        banner.type === 'success'
          ? 'bg-emerald-50 text-emerald-600'
          : banner.type === 'error'
            ? 'bg-rose-50 text-rose-600'
            : 'bg-blue-50 text-[#5B7BFE]'
      }`}
    >
      {banner.text}
    </div>
  );
});

function deriveLiveFocusQuestions(question: string, analysisFocus: string[]) {
  const trimmed = question.trim();
  const cues: string[] = [];
  if (/财务|筹款|资金|收入|成本|预算/.test(trimmed)) {
    cues.push('哪些原始财务信息真正支撑当前判断？');
    cues.push('财务问题背后更像是结构问题、效率问题还是筹资问题？');
  }
  if (/战略|定位|方向|诊断|核心/.test(trimmed)) {
    cues.push('当前最值得先回答的战略矛盾到底是什么？');
    cues.push('哪些原始证据能够支撑阶段判断，而不是只支撑现象描述？');
  }
  if (/组织|团队|协作|管理|机制/.test(trimmed)) {
    cues.push('问题的根因更偏组织机制，还是偏执行节奏与角色分工？');
  }
  if (/项目|业务|产品|服务/.test(trimmed)) {
    cues.push('哪些业务线索能说明当前真正的增长抓手？');
  }
  if (cues.length === 0) {
    cues.push('这个问题更像在问战略、业务、组织还是财务？');
    cues.push('哪些原始材料最值得优先用于形成判断？');
  }
  for (const item of analysisFocus) {
    const normalized = item.trim();
    if (!normalized) continue;
    cues.push(`当前需要先看清"${normalized}"在整体判断中的位置。`);
  }
  return Array.from(new Set(cues)).slice(0, 5);
}

const LiveThinkingTrace = React.memo(function LiveThinkingTrace({
  question,
  run,
}: {
  question: string;
  run: ClientAnalysisRun;
}) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const retrievalSummary =
    (run.assistantMessage?.retrievalSummary as Record<string, unknown> | undefined) || null;

  const trace = useMemo(() => {
    const payload = retrievalSummary?.workTrace;
    const normalized = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {};
    const analysisFocus = Array.isArray(normalized.analysisFocus)
      ? normalized.analysisFocus.map((item) => String(item)).filter(Boolean)
      : [];
    const backgroundTrail = Array.isArray(normalized.backgroundTrail)
      ? normalized.backgroundTrail.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
      : [];
    const webTrail = Array.isArray(normalized.webTrail)
      ? normalized.webTrail.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
      : [];
    const clientDnaTrail = Array.isArray(normalized.clientDnaTrail)
      ? normalized.clientDnaTrail.map((item) => String(item)).filter(Boolean)
      : [];
    const analysisPlan = typeof normalized.analysisPlan === 'string' ? normalized.analysisPlan.trim() : '';
    return { analysisFocus, backgroundTrail, webTrail, clientDnaTrail, analysisPlan };
  }, [retrievalSummary]);

  const rawEvidenceCount = Math.max(run.evidenceSummary.rawChunkHitCount || 0, run.evidenceSummary.evidenceList.length || 0);
  const backgroundCount = Math.max(
    run.evidenceSummary.masterHitCount || 0,
    run.evidenceSummary.surrogateHitCount || 0,
    trace.backgroundTrail.length,
  );
  const webCount = trace.webTrail.length;
  const dnaCount = trace.clientDnaTrail.length;
  const liveQuestions = useMemo(() => deriveLiveFocusQuestions(question, trace.analysisFocus), [question, trace.analysisFocus]);

  const entries = useMemo(() => {
    const nextEntries = [
      `阶段更新：${run.stageLabel || '正在处理当前问题'}`,
      `已定位原始证据 ${rawEvidenceCount} 条，背景线索 ${backgroundCount} 条。`,
      `联网补充 ${webCount} 条${dnaCount ? `，补充 DNA 背景 ${dnaCount} 项` : ''}。`,
      ...liveQuestions.map((item) => `当前正在追问：${item}`),
    ];
    if (trace.analysisPlan) {
      nextEntries.push(`组织答案时优先沿着这条主线展开：${trace.analysisPlan}`);
    }
    nextEntries.push('正在把已命中的线索压缩成能直接回答你的判断，而不是继续堆材料。');
    return nextEntries.filter(Boolean);
  }, [backgroundCount, dnaCount, liveQuestions, rawEvidenceCount, run.stageLabel, trace.analysisPlan, webCount]);

  const [visibleEntries, setVisibleEntries] = useState<string[]>(() => entries.slice(0, 2));

  useEffect(() => {
    setVisibleEntries(entries.slice(0, 2));
    if (entries.length <= 2) return undefined;
    let cursor = 2;
    const timer = window.setInterval(() => {
      setVisibleEntries((prev) => {
        const next = [...prev, entries[cursor % entries.length]];
        cursor += 1;
        return next.slice(-6);
      });
    }, 1350);
    return () => window.clearInterval(timer);
  }, [entries]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [visibleEntries]);

  return (
    <div className="rounded-[24px] border border-[#d8e3ff] bg-[linear-gradient(180deg,rgba(243,247,255,0.95),rgba(255,255,255,0.98))] px-4 py-4 shadow-[0_8px_24px_rgba(91,123,254,0.08)]">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="flex h-8 w-8 items-center justify-center rounded-2xl border border-blue-100 bg-white text-[#5B7BFE] shadow-sm">
            <Activity size={15} />
          </span>
          <div>
            <p className="text-[12px] font-bold text-[#314bbd]">思考过程</p>
            <p className="text-[11px] text-slate-500">这里展示的是系统正在推进的工作轨迹，不是原始隐藏推理全文。</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <span className="rounded-full border border-blue-100 bg-white px-2 py-0.5 text-[10px] font-semibold text-[#4b63df]">原始证据 {rawEvidenceCount} 条</span>
          <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-600">联网补充 {webCount} 条</span>
        </div>
      </div>
      <div
        ref={scrollRef}
        className="mt-4 max-h-[180px] overflow-y-auto rounded-2xl border border-slate-200 bg-white/90 px-3 py-3 shadow-inner"
      >
        <div className="space-y-2.5">
          {visibleEntries.map((entry, index) => (
            <div key={`${entry}-${index}`} className="flex items-start gap-2 animate-in fade-in slide-in-from-bottom-2">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#5B7BFE]" />
              <p className="text-[12px] leading-6 text-slate-700">{entry}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
});

const THINKING_HELPER_LINES = [
  '可追踪背景与证据来源，不显示原始思维全文。',
  'AI 正在持续整理材料与判断主线，不是页面卡住。',
  '如果等待较长，通常是长回答仍在生成，而不是进程停住。',
] as const;

const ThinkingWorkbenchPanel = React.memo(function ThinkingWorkbenchPanel({
  question,
  startedAt,
  stageLabel,
  providerLabel,
  run,
  mode,
}: {
  question: string;
  startedAt: string;
  stageLabel?: string | null;
  providerLabel: string;
  run?: ClientAnalysisRun | null;
  mode: 'starting' | 'running';
}) {
  const [expanded, setExpanded] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(Math.max(Date.now() - Date.parse(startedAt), 0));
  const [helperIndex, setHelperIndex] = useState(0);
  const [displayCounts, setDisplayCounts] = useState({ raw: 0, background: 0, web: 0 });
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const retrievalSummary =
    (run?.assistantMessage?.retrievalSummary as Record<string, unknown> | undefined) || null;

  const trace = useMemo(() => {
    const payload = retrievalSummary?.workTrace;
    const normalized = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {};
    const analysisFocus = Array.isArray(normalized.analysisFocus)
      ? normalized.analysisFocus.map((item) => String(item)).filter(Boolean)
      : [];
    const backgroundTrail = Array.isArray(normalized.backgroundTrail)
      ? normalized.backgroundTrail.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
      : [];
    const webTrail = Array.isArray(normalized.webTrail)
      ? normalized.webTrail.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
      : [];
    const clientDnaTrail = Array.isArray(normalized.clientDnaTrail)
      ? normalized.clientDnaTrail.map((item) => String(item)).filter(Boolean)
      : [];
    return { analysisFocus, backgroundTrail, webTrail, clientDnaTrail };
  }, [retrievalSummary]);

  const targetRaw = Math.max(run?.evidenceSummary.rawChunkHitCount || 0, run?.evidenceSummary.evidenceList.length || 0, mode === 'starting' ? 1 : 0);
  const targetBackground = Math.max(
    run?.evidenceSummary.masterHitCount || 0,
    run?.evidenceSummary.surrogateHitCount || 0,
    trace.backgroundTrail.length,
    trace.clientDnaTrail.length,
    mode === 'starting' ? 2 : 0,
  );
  const targetWeb = Math.max(trace.webTrail.length, 0);
  const liveQuestions = useMemo(() => deriveLiveFocusQuestions(question, trace.analysisFocus), [question, trace.analysisFocus]);

  const rollingEntries = useMemo(() => {
    const stage = stageLabel || (mode === 'starting' ? '问题已发送，正在建立分析任务' : 'AI 正在持续组织长回答');
    const lines = [
      `阶段更新：${stage}`,
      `引用原始证据 ${displayCounts.raw} 条，背景线索 ${displayCounts.background} 条。`,
      `联网补充 ${displayCounts.web} 条。`,
      ...liveQuestions.map((item) => `当前正在追问：${item}`),
      THINKING_HELPER_LINES[helperIndex % THINKING_HELPER_LINES.length],
    ];
    return lines.filter(Boolean);
  }, [displayCounts.background, displayCounts.raw, displayCounts.web, helperIndex, liveQuestions, mode, stageLabel]);

  useEffect(() => {
    const anchor = Date.parse(startedAt);
    setElapsedMs(Math.max(Date.now() - anchor, 0));
    const timer = window.setInterval(() => {
      setElapsedMs(Math.max(Date.now() - anchor, 0));
    }, 250);
    return () => window.clearInterval(timer);
  }, [startedAt]);

  useEffect(() => {
    setExpanded(false);
  }, [question, startedAt]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setHelperIndex((prev) => prev + 1);
    }, 1450);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setDisplayCounts((prev) => {
        const next = { ...prev };
        if (next.raw < targetRaw) {
          next.raw = Math.min(targetRaw, next.raw + Math.max(1, Math.ceil((targetRaw - next.raw) / 3)));
        }
        if (next.background < targetBackground) {
          next.background = Math.min(targetBackground, next.background + Math.max(1, Math.ceil((targetBackground - next.background) / 3)));
        }
        if (next.web < targetWeb) {
          next.web = Math.min(targetWeb, next.web + 1);
        }
        return next;
      });
    }, 420);
    return () => window.clearInterval(timer);
  }, [targetBackground, targetRaw, targetWeb]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container || !expanded) return;
    container.scrollTop = container.scrollHeight;
  }, [expanded, helperIndex]);

  const currentStageLabel = stageLabel || (mode === 'starting' ? '问题已发送，正在建立分析任务' : 'AI 正在计算，请稍候');
  const rotatingLine = rollingEntries[helperIndex % Math.max(rollingEntries.length, 1)] || THINKING_HELPER_LINES[0];
  const collapsedSummaryLine = `原始证据 ${displayCounts.raw} 条，背景线索 ${displayCounts.background} 条，联网补充 ${displayCounts.web} 条。`;
  const expandedLines = [collapsedSummaryLine, ...rollingEntries].slice(-6);
  const partialAnswer = (run?.longAnswer || '').trim();

  return (
    <div className="bg-white border border-slate-200 rounded-[28px] overflow-hidden shadow-[0_10px_30px_rgba(15,23,42,0.06)]">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full px-4 py-3.5 text-left flex items-center justify-between gap-3 bg-[linear-gradient(180deg,rgba(248,250,252,0.98),rgba(255,255,255,0.96))]"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="flex h-9 w-9 items-center justify-center rounded-2xl border border-emerald-100 bg-emerald-50 text-emerald-600 shrink-0">
            <Activity size={16} />
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-[15px] font-bold text-slate-800">工作轨迹</p>
              <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-600">原始证据 {displayCounts.raw} 条</span>
              <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700">背景线索 {displayCounts.background} 条</span>
              <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-500">联网补充 {displayCounts.web} 条</span>
            </div>
            <p className="mt-1 text-[11px] leading-5 text-slate-500">{currentStageLabel}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <div className="text-right">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">{providerLabel}</p>
            <p className="mt-1 text-[12px] font-bold text-slate-600">{formatElapsedLabel(elapsedMs)}</p>
          </div>
          {expanded ? <ChevronUp size={18} className="text-slate-400" /> : <ChevronDown size={18} className="text-slate-400" />}
        </div>
      </button>
      <div className={`px-4 pb-4 transition-all duration-300 ${expanded ? 'pt-1' : 'pt-0'}`}>
        <div
          ref={scrollRef}
          className={`rounded-[22px] border border-slate-200 bg-slate-50/75 px-3 py-3 overflow-hidden ${expanded ? 'max-h-[180px] overflow-y-auto' : 'min-h-[72px]'}`}
        >
          {expanded ? (
            <div className="space-y-2.5">
              {expandedLines.map((entry, index) => (
                <div key={`${entry}-${index}`} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#5B7BFE]" />
                  <p className="text-[12px] leading-6 text-slate-700">{entry}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex items-start gap-2 h-6 overflow-hidden">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#5B7BFE]" />
                <p className="text-[12px] leading-6 text-slate-700 whitespace-nowrap overflow-hidden text-ellipsis">{collapsedSummaryLine}</p>
              </div>
              <div className="flex items-start gap-2 h-6 overflow-hidden">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" />
                <p className="text-[12px] leading-6 text-slate-600 whitespace-nowrap overflow-hidden text-ellipsis">{rotatingLine}</p>
              </div>
            </div>
          )}
        </div>
        {partialAnswer && (
          <div className="mt-3 rounded-[22px] border border-emerald-100 bg-emerald-50/40 px-3 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-emerald-700">正在成文</p>
              </div>
              <span className="text-[10px] text-emerald-600">已生成部分正文</span>
            </div>
            <div className="mt-3 max-h-[280px] overflow-y-auto rounded-[18px] bg-white/90 px-3 py-3 border border-emerald-100">
              <AnswerDocument text={partialAnswer} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

const AnalysisRunCard = React.memo(function AnalysisRunCard({
  run,
  onRetry,
  onVectorize,
  onExport,
}: {
  run: ClientAnalysisRun;
  onRetry: (question: string) => void;
  onVectorize: (messageId: string) => void;
  onExport: (messageId: string) => void;
}) {
  const initialElapsed = run.status === 'running' || run.status === 'queued'
    ? Math.max(Date.now() - Date.parse(run.createdAt), 0)
    : run.elapsedMs;
  const [elapsedMs, setElapsedMs] = useState(initialElapsed);

  useEffect(() => {
    if (run.status !== 'running' && run.status !== 'queued') {
      setElapsedMs(run.elapsedMs);
      return undefined;
    }
    const anchor = Date.parse(run.createdAt);
    setElapsedMs(Math.max(Date.now() - anchor, 0));
    const timer = window.setInterval(() => {
      setElapsedMs(Math.max(Date.now() - anchor, 0));
    }, 300);
    return () => window.clearInterval(timer);
  }, [run.createdAt, run.elapsedMs, run.status]);

  const summary = useMemo(
    () => ({
      phase:
        run.phase === 'generating_long_answer'
          ? 'generating'
          : run.phase === 'evidence_ready'
            ? 'grounding'
            : run.phase === 'completed' || run.phase === 'failed' || run.phase === 'canceled'
              ? run.phase
              : 'retrieving',
      progress: run.progress,
      progressFloor: run.progressFloor,
      progressCeiling: run.progressCeiling,
      stageLabel: run.stageLabel,
    }),
    [run.phase, run.progress, run.progressFloor, run.progressCeiling, run.stageLabel],
  );
  const progress = useMemo(() => loadingProgressValue(summary, elapsedMs), [summary, elapsedMs]);
  const evidenceCount = run.evidenceSummary.evidenceList.length;

  return (
    <div className="space-y-4">
      <div className="bg-white border border-blue-200 rounded-[24px] overflow-hidden shadow-[0_8px_24px_rgba(91,123,254,0.08)]">
        <div className="bg-gray-50/80 border-b border-gray-100 px-4 xl:px-5 py-3 flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-[10px] xl:text-[11px] font-bold text-gray-500 uppercase tracking-widest">
            <Zap size={14} className="text-amber-500" /> 分析过程
          </span>
          <span className="text-[10px] xl:text-[11px] text-gray-400 font-medium">耗时 {formatElapsedLabel(elapsedMs)}</span>
        </div>
        <div className="p-4 xl:p-5">
          <div className="flex items-start gap-3">
            <div className="relative shrink-0">
              <div className="w-11 h-11 rounded-2xl bg-blue-50 text-[#5B7BFE] flex shrink-0 items-center justify-center border border-blue-100 shadow-sm">
                <Bot size={19} strokeWidth={2.2} />
              </div>
              <span className={`absolute -right-1 -bottom-1 w-3.5 h-3.5 rounded-full border-2 border-white ${run.status === 'failed' ? 'bg-rose-500' : run.status === 'completed' ? 'bg-emerald-500' : run.status === 'canceled' ? 'bg-slate-400' : 'bg-emerald-500 animate-pulse'}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[12px] font-bold text-gray-800">{run.stageLabel || '庆华正在处理当前问题'}</p>
                <span className="text-[11px] text-gray-400 shrink-0">{formatElapsedLabel(elapsedMs)}</span>
              </div>
              <p className="text-[11px] text-gray-500 mt-1">庆华会先整理背景材料，再生成一版更完整、更自然的长回答。</p>
              <div className="mt-3 rounded-2xl border border-blue-100 bg-blue-50/70 px-3 py-2 text-[11px] text-[#4f67d7]">
                当前问题：{run.question}
              </div>
              <div className="mt-3 h-2 rounded-full bg-blue-50 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[#5B7BFE] via-[#7ea0ff] to-[#5B7BFE] transition-[width] duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="mt-4">
                <LiveThinkingTrace question={run.question} run={run} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {(run.evidenceSummary.summaryText || evidenceCount > 0) && (
        <div className="bg-white border border-sky-100 rounded-[24px] p-4 xl:p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] xl:text-[12px] font-bold text-sky-800 uppercase tracking-[0.2em]">背景线索</p>
            <span className="text-[10px] text-sky-500 font-semibold">先看这些材料，再进入正式分析</span>
          </div>
          {run.evidenceSummary.summaryText && (
            <p className="mt-3 text-[12px] xl:text-[13px] text-sky-950/80 leading-relaxed">{run.evidenceSummary.summaryText}</p>
          )}
          {evidenceCount > 0 && (
            <div className="mt-4 space-y-2">
              {run.evidenceSummary.evidenceList.slice(0, 6).map((hit, index) => (
                <div key={`${hit.title}-${index}`} className="rounded-2xl border border-gray-100 bg-gray-50/70 px-3 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-[12px] font-semibold text-gray-800">{hit.title}</p>
                    <span className="text-[10px] font-semibold text-gray-400">{hit.stage}</span>
                  </div>
                  <p className="mt-1 text-[11px] leading-relaxed text-gray-600">{hit.excerpt}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <WorkTracePanel
        question={run.question}
        retrievalSummary={(run.assistantMessage?.retrievalSummary as Record<string, unknown> | undefined) || null}
        evidence={(run.assistantMessage?.evidence || run.evidenceSummary.evidenceList).map((item) => ({
          title: item.title,
          retrievalStage: 'retrievalStage' in item ? item.retrievalStage : ('stage' in item ? item.stage : undefined),
          sectionLabel: item.sectionLabel,
        }))}
      />

      {run.longAnswer && (
        <div className="bg-white border border-emerald-100 rounded-[24px] p-4 xl:p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] xl:text-[12px] font-bold text-emerald-800 uppercase tracking-[0.2em]">长回答</p>
            <span className="text-[10px] text-emerald-500 font-semibold">
              {run.answerMode === 'grounded_fallback' || run.answerMode === 'low_confidence_answer' ? '当前为证据整理版回答' : '正式顾问式回答'}
            </span>
          </div>
          <div className="mt-4">
            <AnswerDocument text={run.longAnswer} />
          </div>
        </div>
      )}

      {run.longAnswerStatus === 'failed' && (
        <div className="bg-white border border-rose-100 rounded-[24px] p-4 xl:p-5 shadow-sm">
          <p className="text-[12px] font-bold text-rose-700">长回答生成失败</p>
          <p className="mt-2 text-[12px] leading-relaxed text-rose-900/75">{run.failureReason || '当前只保留背景线索，请稍后重试。'}</p>
          <button
            onClick={() => onRetry(run.question)}
            className="mt-3 rounded-xl bg-rose-50 px-3 py-2 text-[12px] font-semibold text-rose-700 border border-rose-100 hover:bg-rose-100 transition-colors"
          >
            重新生成
          </button>
        </div>
      )}
      {run.longAnswerStatus === 'fallback' && (
        <div className="bg-white border border-amber-100 rounded-[24px] p-4 xl:p-5 shadow-sm">
          <p className="text-[12px] font-bold text-amber-700">正式长回答未完成</p>
          <p className="mt-2 text-[12px] leading-relaxed text-amber-900/80">当前展示的是基于已命中原始证据整理出的兜底版回答，适合继续追问或重试正式生成。</p>
        </div>
      )}

      {run.assistantMessageId && run.status === 'completed' && (
        <div className="bg-white border border-gray-100 rounded-[24px] px-3 xl:px-4 py-3 flex items-center justify-between">
          <div className="flex gap-1 xl:gap-2">
            <button
              className="text-[11px] xl:text-[12px] text-gray-500 hover:text-gray-900 hover:bg-white hover:shadow-sm font-semibold flex items-center gap-1.5 transition-all px-2.5 py-1.5 rounded-lg"
              onClick={() => {
                void navigator.clipboard.writeText(`${run.longAnswer || ''}`.trim());
              }}
            >
              <Copy size={14} />
              复制
            </button>
            <button
              className="text-[11px] xl:text-[12px] text-gray-500 hover:text-gray-900 hover:bg-white hover:shadow-sm font-semibold flex items-center gap-1.5 transition-all px-2.5 py-1.5 rounded-lg"
              onClick={() => onVectorize(run.assistantMessageId)}
            >
              <Sparkles size={14} />
              建立向量
            </button>
            <button
              className="text-[11px] xl:text-[12px] text-gray-500 hover:text-gray-900 hover:bg-white hover:shadow-sm font-semibold flex items-center gap-1.5 transition-all px-2.5 py-1.5 rounded-lg"
              onClick={() => onExport(run.assistantMessageId)}
            >
              <Download size={14} />
              导出文件
            </button>
          </div>
        </div>
      )}
    </div>
  );
});

const Button = ({
  children,
  primary,
  className = '',
  onClick,
  disabled,
  type = 'button',
}: {
  children: React.ReactNode;
  primary?: boolean;
  className?: string;
  onClick?: () => void;
  disabled?: boolean;
  type?: 'button' | 'submit';
}) => (
  <button
    type={type}
    onClick={onClick}
    disabled={disabled}
    className={`px-4 py-2 rounded-xl text-[13px] font-semibold transition-all duration-200 flex items-center justify-center gap-2 active:scale-[0.98]
      ${
        primary
          ? 'bg-[#5B7BFE] text-white shadow-[0_4px_12px_rgba(91,123,254,0.3)] hover:bg-[#4a6be6] hover:shadow-[0_6px_16px_rgba(91,123,254,0.4)] disabled:opacity-60 disabled:cursor-not-allowed'
          : 'bg-white border border-gray-200 text-gray-700 shadow-sm hover:bg-gray-50 hover:border-gray-300 disabled:opacity-60'
      } ${className}`}
  >
    {children}
  </button>
);

function getTint(hexColor: string) {
  return `${hexColor}1A`;
}

function resolveTaskSettings(taskSettings: TaskSettings | null, _lists: TaskList[]): TaskSettings {
  return {
    ...DEFAULT_TASK_SETTINGS,
    ...taskSettings,
    defaultListId: taskSettings?.defaultListId ?? null,
  };
}

function defaultDueDateFromPreset(preset: TaskSettings['defaultDueDatePreset']) {
  return preset === 'today' ? new Date().toISOString().slice(0, 10) : '';
}

function defaultDdlFromPreset(preset: TaskSettings['defaultDueDatePreset']) {
  return preset === 'today' ? '今天' : '待确认';
}

function formatDateOnlyValue(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

type InlineChineseDatePickerFieldProps = {
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
};

function InlineChineseDatePickerField({ value, placeholder, onChange }: InlineChineseDatePickerFieldProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [pickerMonth, setPickerMonth] = useState(() => {
    const parsed = parseTaskDateValue(value);
    const base = parsed || new Date();
    return new Date(base.getFullYear(), base.getMonth(), 1);
  });
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handlePointerDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const parsed = parseTaskDateValue(value);
    const base = parsed || new Date();
    setPickerMonth(new Date(base.getFullYear(), base.getMonth(), 1));
  }, [isOpen, value]);

  const calendarCells = useMemo(() => buildCalendarCells(pickerMonth), [pickerMonth]);
  const todayValue = formatDateOnlyValue(new Date());

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="inline-flex min-w-[144px] items-center justify-between gap-2 rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-bold text-gray-800 outline-none transition hover:border-[#C9D6FF] hover:text-[#5B7BFE]"
      >
        <span className={value ? 'text-gray-800' : 'text-gray-400'}>{value || placeholder}</span>
        <CalendarIcon size={14} className="text-gray-400" />
      </button>
      {isOpen && (
        <div className="absolute left-0 top-full z-[180] mt-2 w-[280px] rounded-[24px] border border-[#E7EAF3] bg-white p-4 shadow-[0_24px_60px_rgba(15,23,42,0.16)]">
          <div className="mb-4 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setPickerMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1))}
              className="flex h-8 w-8 items-center justify-center rounded-full text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
              aria-label="上个月"
            >
              <ChevronLeft size={15} />
            </button>
            <span className="text-[15px] font-bold text-gray-900">{formatMonthTitle(pickerMonth)}</span>
            <button
              type="button"
              onClick={() => setPickerMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1))}
              className="flex h-8 w-8 items-center justify-center rounded-full text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
              aria-label="下个月"
            >
              <ChevronRight size={15} />
            </button>
          </div>
          <div className="grid grid-cols-7 gap-y-2 text-center text-[11px] font-bold text-gray-400">
            {['一', '二', '三', '四', '五', '六', '日'].map((label) => (
              <span key={label}>{label}</span>
            ))}
          </div>
          <div className="mt-2 grid grid-cols-7 gap-y-1">
            {calendarCells.map((cell, index) => {
              if (!cell.date || !cell.day) {
                return <span key={`picker-empty-${index}`} className="h-9" />;
              }
              const cellValue = formatDateOnlyValue(cell.date);
              const isSelected = value === cellValue;
              const isToday = cellValue === todayValue;
              return (
                <button
                  key={cellValue}
                  type="button"
                  onClick={() => {
                    onChange(cellValue);
                    setIsOpen(false);
                  }}
                  className={`mx-auto flex h-9 w-9 items-center justify-center rounded-xl text-[13px] font-bold transition-colors ${
                    isSelected
                      ? 'bg-[#3F74FF] text-white shadow-[0_10px_20px_rgba(63,116,255,0.22)]'
                      : isToday
                        ? 'text-[#E5477A] hover:bg-rose-50'
                        : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  {cell.day}
                </button>
              );
            })}
          </div>
          <div className="mt-4 flex items-center justify-between">
            <button
              type="button"
              className="text-[13px] font-bold text-gray-400 transition-colors hover:text-gray-700"
              onClick={() => {
                onChange('');
                setIsOpen(false);
              }}
            >
              清除
            </button>
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="text-[13px] font-bold text-[#5B7BFE] transition-colors hover:text-[#3F74FF]"
                onClick={() => {
                  onChange(todayValue);
                  setPickerMonth(new Date());
                  setIsOpen(false);
                }}
              >
                今天
              </button>
              <button
                type="button"
                className="rounded-xl bg-[#5B7BFE] px-4 py-2 text-[13px] font-bold text-white shadow-[0_10px_24px_rgba(91,123,254,0.22)]"
                onClick={() => setIsOpen(false)}
              >
                确定
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function formatTimeOnlyValue(date: Date) {
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function shiftDateOnlyValue(value?: string | null, dayOffset = 0) {
  const normalized = (value || '').trim();
  if (!normalized || dayOffset === 0) return normalized;
  const parsed = parseTaskDateValue(normalized);
  if (!parsed) return normalized;
  return formatDateOnlyValue(new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate() + dayOffset));
}

function splitTaskDueDateTime(value?: string | null) {
  if (!value) return { date: '', time: '' };
  const text = value.trim();
  if (!text) return { date: '', time: '' };
  const match = text.match(/^(\d{4}-\d{2}-\d{2})(?:[T\s](\d{2}):(\d{2}))?/);
  if (match) {
    return {
      date: match[1],
      time: match[2] && match[3] ? `${match[2]}:${match[3]}` : '',
    };
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) return { date: '', time: '' };
  return {
    date: formatDateOnlyValue(parsed),
    time: `${String(parsed.getHours()).padStart(2, '0')}:${String(parsed.getMinutes()).padStart(2, '0')}`,
  };
}

function hasExplicitTaskDueTime(value?: string | null) {
  if (!value) return false;
  return /^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}/.test(value.trim());
}

function normalizeTaskTimeInput(timePart?: string | null) {
  const normalized = (timePart || '').trim();
  if (!normalized) return '';
  const match = normalized.match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return '';
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (Number.isNaN(hours) || Number.isNaN(minutes) || hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
    return '';
  }
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
}

function minuteOfDayFromTaskTime(timePart?: string | null) {
  const normalized = normalizeTaskTimeInput(timePart);
  if (!normalized) return null;
  const [hoursText, minutesText] = normalized.split(':');
  return Number(hoursText) * 60 + Number(minutesText);
}

function formatTaskMinuteOfDay(minuteOfDay: number) {
  const safeMinute = Math.max(0, Math.min(24 * 60, minuteOfDay));
  const hours = Math.floor(safeMinute / 60);
  const minutes = safeMinute % 60;
  return `${String(Math.min(hours, 24)).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
}

function resolveTaskDueTimeForDisplay(datePart?: string | null, timePart?: string | null) {
  if (!(datePart || '').trim()) return '';
  const normalizedTime = normalizeTaskTimeInput(timePart);
  return normalizedTime || TASK_DEFAULT_DUE_TIME;
}

function combineTaskDateTime(
  datePart?: string | null,
  timePart?: string | null,
  options?: { includeTime?: boolean },
) {
  const date = (datePart || '').trim();
  if (!date) return '';
  const normalizedTime = normalizeTaskTimeInput(timePart);
  const includeTime = options?.includeTime ?? Boolean(normalizedTime);
  if (!includeTime) return date;
  const time = resolveTaskDueTimeForDisplay(date, normalizedTime);
  return time ? `${date}T${time}` : date;
}

function combineTaskDueDateTime(
  datePart?: string | null,
  timePart?: string | null,
  options?: { includeTime?: boolean },
) {
  return combineTaskDateTime(datePart, timePart, options);
}

function formatTaskDateTimeLabel(
  value?: string | null,
  options?: { fallbackTime?: string | null },
) {
  if (!value) return '待确认';
  const { date, time } = splitTaskDueDateTime(value);
  if (!date) return value;
  const parsedDate = parseTaskDateValue(date);
  if (!parsedDate) return value;
  const today = new Date();
  const isToday = parsedDate.getFullYear() === today.getFullYear()
    && parsedDate.getMonth() === today.getMonth()
    && parsedDate.getDate() === today.getDate();
  const baseLabel = isToday
    ? '今天'
    : `${String(parsedDate.getMonth() + 1).padStart(2, '0')}-${String(parsedDate.getDate()).padStart(2, '0')}`;
  const explicitTime = normalizeTaskTimeInput(time);
  if (explicitTime) return `${baseLabel} ${explicitTime}`;
  const fallbackTime = normalizeTaskTimeInput(options?.fallbackTime || '');
  return fallbackTime ? `${baseLabel} ${fallbackTime}` : baseLabel;
}

function formatTaskDueLabel(value?: string | null) {
  return formatTaskDateTimeLabel(value, { fallbackTime: null });
}

function formatTaskTimelineLabel(task: Pick<Task, 'startDate' | 'dueDate' | 'durationMinutes' | 'ddl'>) {
  return formatUnifiedTaskTimelineLabel(task);
}

type EventLineNotificationSummary = {
  eventLineTitle: string;
  operation: string;
  operator: string;
  operatedAt: string;
  mainOwners: string;
  participants: string;
};

function parseEventLineNotificationSummary(task: Pick<Task, 'sourceType' | 'title' | 'desc'>): EventLineNotificationSummary | null {
  if (task.sourceType !== 'event_line_notification') return null;
  const rawLines = String(task.desc || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  const values = new Map<string, string>();
  rawLines.forEach((line) => {
    const [label, ...rest] = line.split('：');
    if (!label || rest.length === 0) return;
    values.set(label.trim(), rest.join('：').trim());
  });
  return {
    eventLineTitle: values.get('事件线标题') || task.title || '未命名事件线',
    operation: values.get('事件线操作') || '状态更新',
    operator: values.get('操作者') || '未标记',
    operatedAt: values.get('操作时间') || '',
    mainOwners: values.get('主要负责人') || '未设置',
    participants: values.get('参与者') || '暂无',
  };
}

function formatTaskDuePickerDateLabel(datePart?: string | null) {
  const parsedDate = parseTaskDateValue(datePart);
  if (!parsedDate) return '选择日期';
  return `${parsedDate.getFullYear()}/${String(parsedDate.getMonth() + 1).padStart(2, '0')}/${String(parsedDate.getDate()).padStart(2, '0')}`;
}

function formatTaskDuePickerSummaryLabel(
  startDatePart?: string | null,
  startTimePart?: string | null,
  dueDatePart?: string | null,
  timePart?: string | null,
  hasSpecificTime = false,
  durationMinutes = 0,
) {
  const dueLabel = formatTaskDuePickerDateLabel(dueDatePart);
  if (dueLabel === '选择日期') return '选择截止时间';
  if (!hasSpecificTime) {
    if (!startDatePart) return formatTaskDateTimeLabel(dueDatePart, { fallbackTime: null });
    const rangeStartLabel = formatTaskDateTimeLabel(startDatePart, { fallbackTime: null });
    const rangeDueLabel = formatTaskDateTimeLabel(dueDatePart, { fallbackTime: null });
    return `${rangeStartLabel} → ${rangeDueLabel}`;
  }
  if (!startDatePart && hasSpecificTime) {
    const normalizedDueTime = normalizeTaskTimeInput(timePart);
    if (normalizedDueTime) {
      const baseLabel = formatTaskDateTimeLabel(dueDatePart, { fallbackTime: null });
      const startMinute = minuteOfDayFromTaskTime(normalizedDueTime);
      if (startMinute !== null) {
        const endMinute = Math.min(startMinute + Math.max(15, durationMinutes || 0), 24 * 60);
        return `${baseLabel} ${normalizedDueTime}-${formatTaskMinuteOfDay(endMinute)}`.trim();
      }
    }
  }
  const deadlineLabel = formatTaskDateTimeLabel(
    combineTaskDateTime(dueDatePart, timePart, { includeTime: hasSpecificTime }),
    { fallbackTime: TASK_DEFAULT_DUE_TIME },
  );
  const startLabel = formatTaskDuePickerDateLabel(startDatePart);
  if (startLabel === '选择日期') return deadlineLabel;
  const rangeStartLabel = formatTaskDateTimeLabel(
    combineTaskDateTime(startDatePart, startTimePart, { includeTime: hasSpecificTime && Boolean(startDatePart) }),
    { fallbackTime: null },
  );
  return `${rangeStartLabel} → ${deadlineLabel}`;
}

function formatTaskDateWindowLabel(startValue?: string | null, dueValue?: string | null) {
  if (!dueValue) return '';
  const { date } = splitTaskDueDateTime(dueValue);
  if (!date) return formatTaskDueLabel(dueValue);
  const normalizedStart = (startValue || '').trim();
  if (!normalizedStart || normalizedStart === date) return formatTaskDueLabel(dueValue);
  const startDate = parseTaskDateValue(normalizedStart);
  if (!startDate) return formatTaskDueLabel(dueValue);
  const startLabel = formatTaskDateTimeLabel(normalizedStart, { fallbackTime: null });
  return `${startLabel} → ${formatTaskDueLabel(dueValue)}`;
}

function taskTagPillStyle(tag: TaskTag, emphasized = false): React.CSSProperties {
  return {
    backgroundColor: emphasized ? `${tag.color}26` : getTint(tag.color),
    color: tag.color,
    border: `1px solid ${tag.color}33`,
  };
}

function sortTasksForListView(tasks: Task[], sortMode: TaskSettings['listSortMode']) {
  const statusRank: Record<Task['status'], number> = {
    inbox: 0,
    doing: 1,
    todo: 2,
    done: 3,
    rejected: 4,
  };
  const explicitDueTimestamp = (task: Task) => resolveTaskTimelineDateTime(task)?.getTime() || Number.MAX_SAFE_INTEGER;
  const timelineTimestamp = (task: Task) => resolveTaskTimelineDateTime(task)?.getTime() || Number.MAX_SAFE_INTEGER;
  return [...tasks].sort((left, right) => {
    const leftTime = sortMode === 'dueDate' ? explicitDueTimestamp(left) : timelineTimestamp(left);
    const rightTime = sortMode === 'dueDate' ? explicitDueTimestamp(right) : timelineTimestamp(right);
    if (leftTime !== rightTime) return leftTime - rightTime;
    if (sortMode === 'priority') {
      const priorityRank = { high: 0, normal: 1, low: 2 } as const;
      const priorityDelta = priorityRank[left.priority] - priorityRank[right.priority];
      if (priorityDelta !== 0) return priorityDelta;
    }
    const statusDelta = statusRank[left.status] - statusRank[right.status];
    if (statusDelta !== 0) return statusDelta;
    return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
  });
}

function isTaskRiskyForFormalView(task: Task) {
  if (Boolean(task.orgContext?.needsReview)) return true;
  if ((task.currentBlocker || '').trim()) return true;
  if (isTaskOverdue(task)) return true;
  return Number(task.evidenceCount || 0) <= 1 && task.status !== 'done';
}

function taskMatchesFormalView(
  task: Task,
  view: TaskViewDefinition,
  extraFilters?: Partial<TaskViewFilterSet> & { clientNames?: string[]; relatedTaskIds?: string[] },
) {
  const filterSet = view.filterSet || {};
  const mergedFilters = {
    ...filterSet,
    ...(extraFilters || {}),
  };
  const sourceTypes = mergedFilters.sourceTypes || [];
  const businessCategories = mergedFilters.businessCategories || [];
  const eventLineIds = mergedFilters.eventLineIds || [];
  const clientNames = extraFilters?.clientNames || [];
  const relatedTaskIds = extraFilters?.relatedTaskIds || [];

  if (view.kind === 'event_line' && !(task.eventLineId || '').trim()) return false;
  if (view.kind === 'risk' && !isTaskRiskyForFormalView(task)) return false;
  if (view.kind === 'source' && ['', 'manual'].includes((task.sourceType || '').trim())) return false;
  if (view.kind === 'business_category' && !(task.businessCategory || '').trim()) return false;
  if (sourceTypes.length > 0 && !sourceTypes.includes(task.sourceType || '')) return false;
  if (businessCategories.length > 0 && !businessCategories.includes(task.businessCategory || '')) return false;
  if (eventLineIds.length > 0 && !eventLineIds.includes(task.eventLineId || '')) return false;
  if (clientNames.length > 0 && !clientNames.includes(task.projectContext?.clientName || '')) return false;
  if (relatedTaskIds.length > 0 && !relatedTaskIds.includes(task.id)) return false;
  if (mergedFilters.onlyRisky && !isTaskRiskyForFormalView(task)) return false;
  if (mergedFilters.onlyWithEventLine && !(task.eventLineId || '').trim()) return false;
  if (mergedFilters.needsReview !== undefined && mergedFilters.needsReview !== null && Boolean(task.orgContext?.needsReview) !== Boolean(mergedFilters.needsReview)) return false;
  if (mergedFilters.minimumEvidenceCount !== undefined && mergedFilters.minimumEvidenceCount !== null && Number(task.evidenceCount || 0) < Number(mergedFilters.minimumEvidenceCount)) return false;
  return true;
}

function sortTasksByFormalView(tasks: Task[], view: TaskViewDefinition) {
  const reverse = view.sortDirection === 'desc';
  const priorityRank = (task: Task) => ({ high: 0, normal: 1, low: 2 } as const)[task.priority] ?? 3;
  const dueTimestamp = (task: Task) => taskDateForReview(task)?.getTime() || 0;
  const sorted = [...tasks].sort((left, right) => {
    if (view.sortBy === 'priority') {
      return priorityRank(left) - priorityRank(right);
    }
    if (view.sortBy === 'dueDate') {
      return dueTimestamp(left) - dueTimestamp(right);
    }
    if (view.sortBy === 'evidenceCount') {
      return Number(left.evidenceCount || 0) - Number(right.evidenceCount || 0);
    }
    return new Date(left.updatedAt).getTime() - new Date(right.updatedAt).getTime();
  });
  return reverse ? sorted.reverse() : sorted;
}

type TaskListFilter = 'doing' | 'done' | 'overdue' | 'all';
type TaskParticipationFilter = 'all' | 'personal' | 'collab';
type TaskTimeSort = 'newest' | 'oldest';
type TaskTimeRangeFilter = 'all' | 'last3days' | 'lastMonth' | 'lastHalfYear' | 'custom';
const TASK_LIST_FILTER_NONE = '__no_list__';

const TASK_LIST_FILTER_OPTIONS: Array<{ value: TaskListFilter; label: string }> = [
  { value: 'doing', label: '待推进' },
  { value: 'done', label: '已完成' },
  { value: 'overdue', label: '逾期' },
  { value: 'all', label: '全部' },
];

const TASK_PARTICIPATION_FILTER_OPTIONS: Array<{ value: TaskParticipationFilter; label: string }> = [
  { value: 'all', label: '全部任务' },
  { value: 'personal', label: '个人任务' },
  { value: 'collab', label: '协作任务' },
];

const TASK_TIME_SORT_OPTIONS: Array<{ value: TaskTimeSort; label: string }> = [
  { value: 'newest', label: '从近到远' },
  { value: 'oldest', label: '从远到近' },
];

const TASK_TIME_RANGE_OPTIONS: Array<{ value: TaskTimeRangeFilter; label: string }> = [
  { value: 'all', label: '全部时间' },
  { value: 'last3days', label: '最近三天' },
  { value: 'lastMonth', label: '最近一个月' },
  { value: 'lastHalfYear', label: '最近半年' },
  { value: 'custom', label: '自定义时间' },
];

function resolveOrganizationTaskName(organizationName?: string | null) {
  const normalized = (organizationName || '').trim();
  return normalized || '益语智库';
}

function buildOrganizationTaskAutoReason(organizationName?: string | null) {
  return `默认按组织任务"${resolveOrganizationTaskName(organizationName)}"处理；只有明确命中具体工作对象名称时才自动关联。`;
}

function buildOrganizationTaskManualReason(organizationName?: string | null) {
  return `已手动设置为组织任务"${resolveOrganizationTaskName(organizationName)}"。`;
}

function inferTaskPriority(params: {
  title: string;
  desc: string;
  dueDate?: string | null;
  clientTokens?: string[];
}): { priority: 'low' | 'normal' | 'high'; reason: string } {
  const title = params.title.trim();
  const desc = params.desc.trim();
  const text = `${title}\n${desc}`.toLowerCase();
  const dueDate = parseTaskDateValue(params.dueDate);
  const today = new Date();
  const urgentKeywords = ['紧急', '加急', '立刻', '立即', '马上', '尽快', '今天', '今晚', '明早', '复核', '汇报', '上线', '交付', '截止', '会前'];
  const strategicKeywords = ['方案', '客户', '会议', '合同', '回款', '对齐', '推进', '提案', '审阅', '评审'];
  const lowKeywords = ['储备', '研究', '备选', '以后', '长期', '归档', '整理旧', '随手记', '想法'];
  const hasUrgentKeyword = urgentKeywords.some((keyword) => text.includes(keyword.toLowerCase()));
  const hasStrategicKeyword = strategicKeywords.some((keyword) => text.includes(keyword.toLowerCase()));
  const hasLowKeyword = lowKeywords.some((keyword) => text.includes(keyword.toLowerCase()));
  const matchedClient = (params.clientTokens || []).find((token) => token && text.includes(token.toLowerCase()));
  const dueToday = dueDate && !isPastCalendarDueDay(dueDate, today) && startOfCalendarDay(dueDate).getTime() === startOfCalendarDay(today).getTime();
  const duePast = dueDate && isPastCalendarDueDay(dueDate, today);
  if (duePast || dueToday || hasUrgentKeyword || (matchedClient && hasStrategicKeyword)) {
    if (duePast) return { priority: 'high', reason: '系统识别为高优先级：任务已过截止日，需优先处理。' };
    if (dueToday) return { priority: 'high', reason: '系统识别为高优先级：任务截止到今天，建议优先推进。' };
    if (matchedClient && hasStrategicKeyword) {
      return { priority: 'high', reason: `系统识别为高优先级：内容涉及客户"${matchedClient}"且带有明确推进动作。` };
    }
    return { priority: 'high', reason: '系统识别为高优先级：标题或说明中包含明显的紧急/交付信号。' };
  }
  if (hasLowKeyword && !hasStrategicKeyword) {
    return { priority: 'low', reason: '系统识别为低优先级：更像储备、归档或长期研究事项。' };
  }
  return { priority: 'normal', reason: '系统识别为普通优先级：当前未出现明显紧急或低优先级信号。' };
}

function inferTaskClient(params: {
  title: string;
  desc: string;
  clients: ClientSummary[];
  currentClientId?: string | null;
  organizationName?: string | null;
}): { clientId: string; confidence: 'none' | 'low' | 'medium' | 'high'; reason: string } {
  const text = `${params.title}\n${params.desc}`.trim().toLowerCase();
  const buildNameFragments = (value: string) => {
    const name = value.trim();
    if (!name) return [] as string[];
    const hasCjk = /[\u4e00-\u9fff]/.test(name);
    if (!hasCjk) return tokenizeScopeText(name, 2, 12);
    const normalized = name.replace(/\s+/g, '');
    if (normalized.length < 4) return [normalized.toLowerCase()];
    const fragments = new Set<string>();
    const maxLen = Math.min(4, normalized.length);
    for (let len = 2; len <= maxLen; len += 1) {
      for (let i = 0; i <= normalized.length - len; i += 1) {
        fragments.add(normalized.slice(i, i + len).toLowerCase());
      }
    }
    return Array.from(fragments);
  };
  const normalizedClients = params.clients.map((client) => {
    const domain = client.domain.replace(/^https?:\/\//i, '').replace(/^www\./i, '').trim();
    const domainParts = domain.split(/[/.]/).filter(Boolean);
    const nameFragments = buildNameFragments(client.name || '');
    const aliasFragments = buildNameFragments(client.alias || '');
    const exactTokens = [client.name, client.alias]
      .map((item) => item.trim().toLowerCase())
      .filter((item) => item.length >= 2);
    const supportTokens = Array.from(
      new Set(
        [domain, ...domainParts]
          .concat(nameFragments, aliasFragments)
          .map((item) => item.trim().toLowerCase())
          .filter((item) => item.length >= 2),
      ),
    );
    return { client, exactTokens, supportTokens };
  });
  if (!text) {
    return { clientId: '', confidence: 'none', reason: buildOrganizationTaskAutoReason(params.organizationName) };
  }
  const ranked = normalizedClients
    .map(({ client, exactTokens, supportTokens }) => {
      const exactHits = exactTokens.filter((token) => text.includes(token));
      const supportHits = supportTokens.filter((token) => text.includes(token));
      return { client, exactHits, supportHits, score: exactHits.length * 3 + supportHits.length };
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score || right.client.name.length - left.client.name.length);
  if (ranked.length > 0) {
    const winner = ranked[0];
    const hits = [...winner.exactHits, ...winner.supportHits].slice(0, 2);
    if (winner.exactHits.length === 0) {
      const strongSupport = winner.supportHits.some((token) => token.length >= 4);
      const multiSupport = winner.supportHits.length >= 2;
      if (strongSupport || multiSupport) {
        return {
          clientId: winner.client.id,
          confidence: 'medium',
          reason: `系统自动识别工作对象：命中多个关键词"${hits.join('、') || winner.client.name}"，已预填为"${winner.client.name}"。`,
        };
      }
      return {
        clientId: '',
        confidence: 'low',
        reason: `系统捕捉到与"${winner.client.name}"相关的弱信号${hits.length ? `（${hits.join('、')}）` : ''}，但不足以自动挂到项目；默认仍按组织任务"${resolveOrganizationTaskName(params.organizationName)}"处理。`,
      };
    }
    const confidence = 'high';
    return {
      clientId: winner.client.id,
      confidence,
      reason: `系统自动识别工作对象：命中"${hits.join('、') || winner.client.name}"，已预填为"${winner.client.name}"。`,
    };
  }
  return { clientId: '', confidence: 'none', reason: buildOrganizationTaskAutoReason(params.organizationName) };
}

function inferTaskEventLine(params: {
  title: string;
  desc: string;
  eventLines: EventLine[];
  currentClientId?: string | null;
}): { eventLineId: string; reason: string } {
  const text = `${params.title}\n${params.desc}`.trim().toLowerCase();
  const scopedEventLines = params.currentClientId
    ? params.eventLines.filter((item) => (item.primaryClientId || '').trim() === params.currentClientId)
    : params.eventLines;
  const candidateLines = scopedEventLines.length > 0 ? scopedEventLines : params.eventLines;
  if (candidateLines.length === 0) {
    return {
      eventLineId: '',
      reason: params.currentClientId
        ? '当前关联对象下还没有事件线，可从这条任务直接新建。'
        : '当前还没有可选事件线，可从这条任务直接新建。',
    };
  }
  const summarizeScope = () => {
    if (params.currentClientId && scopedEventLines.length > 0) {
      return `当前关联对象下已有 ${scopedEventLines.length} 条事件线，可手动调整。`;
    }
    return candidateLines.length === 1
      ? '当前仅有 1 条可选事件线，可直接确认或手动调整。'
      : `当前共有 ${candidateLines.length} 条可选事件线，可手动调整。`;
  };
  if (!text) {
    if (params.currentClientId && scopedEventLines.length === 1) {
      return {
        eventLineId: scopedEventLines[0].id,
        reason: `当前关联对象下仅有一条事件线，先预填为"${scopedEventLines[0].name}"。`,
      };
    }
    return { eventLineId: '', reason: summarizeScope() };
  }
  const ranked = candidateLines
    .map((eventLine) => {
      const exactTokens = [eventLine.name]
        .map((item) => item.trim().toLowerCase())
        .filter((item) => item.length >= 2);
      const supportTokens = [eventLine.summary, eventLine.intent, eventLine.nextStep, eventLine.stage]
        .flatMap((item) => (item ? item.split(/[，。；、,\n]/) : []))
        .map((item) => item.trim().toLowerCase())
        .filter((item) => item.length >= 3 && item.length <= 14);
      const exactHits = exactTokens.filter((token) => text.includes(token));
      const supportHits = Array.from(new Set(supportTokens.filter((token) => text.includes(token))));
      const score = exactHits.length * 4 + supportHits.length;
      return { eventLine, exactHits, supportHits, score };
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score || right.eventLine.updatedAt.localeCompare(left.eventLine.updatedAt));
  if (ranked.length > 0) {
    const winner = ranked[0];
    const hits = [...winner.exactHits, ...winner.supportHits].slice(0, 2);
    return {
      eventLineId: winner.eventLine.id,
      reason: `系统已在${params.currentClientId && scopedEventLines.length > 0 ? '当前关联对象' : '可选范围'}内匹配到事件线"${winner.eventLine.name}"${hits.length ? `，命中"${hits.join('、')}"` : ''}。`,
    };
  }
  if (params.currentClientId && scopedEventLines.length === 1) {
    return {
      eventLineId: scopedEventLines[0].id,
      reason: `当前关联对象下仅有一条事件线，先预填为"${scopedEventLines[0].name}"，可手动调整。`,
    };
  }
  return { eventLineId: '', reason: summarizeScope() };
}

function tokenizeScopeText(value?: string | null, minLength = 2, maxLength = 18) {
  return (value || '')
    .split(/[，。；、,\n\s/·\-]+/)
    .map((item) => item.trim().toLowerCase())
    .filter((item) => item.length >= minLength && item.length <= maxLength);
}

function inferTaskProjectModule(params: {
  title: string;
  desc: string;
  modules: ProjectModule[];
  eventLine?: Pick<EventLine, 'name' | 'summary' | 'intent' | 'nextStep'> | null;
}): { projectModuleId: string; reason: string } {
  const candidates = params.modules;
  if (candidates.length === 0) {
    return { projectModuleId: '', reason: '当前项目下还没有任务模块，建议先补 1-3 个长期模块。' };
  }
  const text = [
    params.title,
    params.desc,
    params.eventLine?.name,
    params.eventLine?.summary,
    params.eventLine?.intent,
    params.eventLine?.nextStep,
  ].join('\n').trim().toLowerCase();
  if (!text) {
    if (candidates.length === 1) {
      return {
        projectModuleId: candidates[0].id,
        reason: `当前项目下仅有 1 个模块，先预填为"${candidates[0].name}"。`,
      };
    }
    return { projectModuleId: '', reason: `当前项目下已有 ${candidates.length} 个模块，可手动选择。` };
  }
  const ranked = candidates
    .map((module) => {
      const exactTokens = [module.name, module.alias]
        .map((item) => (item || '').trim().toLowerCase())
        .filter((item) => item.length >= 2);
      const supportTokens = [
        module.goal,
        module.description,
        module.ownerName,
        ...module.deliverables,
        ...module.keywords,
      ].flatMap((item) => tokenizeScopeText(item, 2, 18));
      const exactHits = exactTokens.filter((token) => text.includes(token));
      const supportHits = Array.from(new Set(supportTokens.filter((token) => text.includes(token))));
      const score = exactHits.length * 5 + supportHits.length * 2;
      return { module, exactHits, supportHits, score };
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score || left.module.name.localeCompare(right.module.name, 'zh-CN'));
  if (ranked.length > 0) {
    const winner = ranked[0];
    const hits = [...winner.exactHits, ...winner.supportHits].slice(0, 3);
    return {
      projectModuleId: winner.module.id,
      reason: `系统建议挂到模块"${winner.module.name}"${hits.length ? `，命中"${hits.join('、')}"` : ''}。`,
    };
  }
  if (candidates.length === 1) {
    return {
      projectModuleId: candidates[0].id,
      reason: `当前项目下仅有 1 个模块，先预填为"${candidates[0].name}"，可手动调整。`,
    };
  }
  return { projectModuleId: '', reason: `当前项目下共有 ${candidates.length} 个模块，可手动选择。` };
}

function inferTaskProjectFlow(params: {
  title: string;
  desc: string;
  flows: ProjectFlow[];
  selectedModuleId?: string | null;
  eventLine?: Pick<EventLine, 'name' | 'summary' | 'intent' | 'nextStep'> | null;
}): { projectFlowId: string; reason: string } {
  const scopedFlows = params.selectedModuleId
    ? params.flows.filter((item) => item.moduleId === params.selectedModuleId)
    : params.flows;
  if (scopedFlows.length === 0) {
    return {
      projectFlowId: '',
      reason: params.selectedModuleId ? '当前模块下还没有标准流程，可先创建一条流程。' : '请先选择任务模块，再选择流程。',
    };
  }
  const text = [
    params.title,
    params.desc,
    params.eventLine?.name,
    params.eventLine?.summary,
    params.eventLine?.intent,
    params.eventLine?.nextStep,
  ].join('\n').trim().toLowerCase();
  if (!text) {
    if (scopedFlows.length === 1) {
      return {
        projectFlowId: scopedFlows[0].id,
        reason: `当前范围内仅有 1 条流程，先预填为"${scopedFlows[0].name}"。`,
      };
    }
    return { projectFlowId: '', reason: `当前范围内已有 ${scopedFlows.length} 条流程，可手动选择。` };
  }
  const ranked = scopedFlows
    .map((flow) => {
      const exactTokens = [flow.name, flow.moduleName]
        .map((item) => (item || '').trim().toLowerCase())
        .filter((item) => item.length >= 2);
      const supportTokens = [
        flow.description,
        flow.scenario,
        flow.triggerCondition,
        ...flow.steps,
        ...flow.inputs,
        ...flow.outputs,
        ...flow.collaborators,
        ...flow.riskPoints,
      ].flatMap((item) => tokenizeScopeText(item, 2, 18));
      const exactHits = exactTokens.filter((token) => text.includes(token));
      const supportHits = Array.from(new Set(supportTokens.filter((token) => text.includes(token))));
      const score = exactHits.length * 5 + supportHits.length * 2;
      return { flow, exactHits, supportHits, score };
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score || left.flow.name.localeCompare(right.flow.name, 'zh-CN'));
  if (ranked.length > 0) {
    const winner = ranked[0];
    const hits = [...winner.exactHits, ...winner.supportHits].slice(0, 3);
    return {
      projectFlowId: winner.flow.id,
      reason: `系统建议挂到流程"${winner.flow.name}"${hits.length ? `，命中"${hits.join('、')}"` : ''}。`,
    };
  }
  if (scopedFlows.length === 1) {
    return {
      projectFlowId: scopedFlows[0].id,
      reason: `当前范围内仅有 1 条流程，先预填为"${scopedFlows[0].name}"，可手动调整。`,
    };
  }
  return { projectFlowId: '', reason: `当前范围内共有 ${scopedFlows.length} 条流程，可手动选择。` };
}

function labelTaskClientConfidence(confidence: 'none' | 'low' | 'medium' | 'high' | 'manual') {
  switch (confidence) {
    case 'high':
      return { text: '高置信度识别', className: 'bg-emerald-50 text-emerald-700 border border-emerald-100' };
    case 'medium':
      return { text: '中置信度识别', className: 'bg-sky-50 text-sky-700 border border-sky-100' };
    case 'low':
      return { text: '低置信度建议', className: 'bg-amber-50 text-amber-700 border border-amber-100' };
    case 'manual':
      return { text: '已手动选择', className: 'bg-violet-50 text-violet-700 border border-violet-100' };
    default:
      return null;
  }
}

function taskPriorityUi(priority: 'low' | 'normal' | 'high') {
  switch (priority) {
    case 'high':
      return {
        iconClass: 'text-rose-400 hover:text-rose-500',
        selectClass: 'text-rose-600',
        helperLabel: '高优先级',
      };
    case 'low':
      return {
        iconClass: 'text-gray-300 hover:text-gray-400',
        selectClass: 'text-gray-500',
        helperLabel: '低优先级',
      };
    default:
      return {
        iconClass: 'text-sky-400 hover:text-sky-500',
        selectClass: 'text-sky-600',
        helperLabel: '普通优先级',
      };
  }
}

function buildTaskProjectPreview(params: {
  clientId: string;
  projectModuleId?: string | null;
  projectFlowId?: string | null;
  taskTitle?: string | null;
  taskDescription?: string | null;
  attachmentCount?: number;
  attachmentTitles?: string[];
  eventLine?: Pick<EventLine, 'name' | 'summary' | 'intent' | 'currentBlocker' | 'recentDecision' | 'nextStep' | 'evidenceCount'> | null;
  clients: ClientSummary[];
  workspace: ClientWorkspace | null;
  dnaModules: ClientDnaModule[];
  projectStructure: ProjectStructureResponse;
  terminology?: {
    singularLabel?: string;
    workspaceLabel?: string;
  };
}): TaskProjectContext | null {
  if (!params.clientId) return null;
  const client = params.clients.find((item) => item.id === params.clientId);
  if (!client) return null;
  const workspace = params.workspace?.client.id === params.clientId ? params.workspace : null;
  const singularLabel = params.terminology?.singularLabel || '项目';
  const workspaceLabel = params.terminology?.workspaceLabel || `${singularLabel}工作台`;
  const moduleMap = new Map(params.dnaModules.map((item) => [item.moduleKey, item]));
  const projectModule = params.projectStructure.modules.find((item) => item.id === params.projectModuleId);
  const projectFlow = params.projectStructure.flows.find((item) => item.id === params.projectFlowId);
  const goals = workspace?.goals?.map((goal) => goal.title.trim()).filter(Boolean) || [];
  const meetings = workspace?.meetings?.map((meeting) => meeting.title.trim()).filter(Boolean) || [];
  const workspaceDocumentCount = Math.max(workspace?.documentCards?.length || 0, workspace?.documents?.length || 0);
  const attachmentCount = params.attachmentCount || 0;
  const attachmentTitles = (params.attachmentTitles || []).map((item) => item.trim()).filter(Boolean);
  const taskText = `${params.taskTitle || ''} ${params.taskDescription || ''}`.replace(/\s+/g, ' ').trim();
  const taskClauses = (params.taskDescription || '')
    .split(/\n|[。；;]/)
    .map((item) => item.replace(/^(背景|目标|阻塞|下一步|说明|备注)[:：]\s*/u, '').trim())
    .filter(Boolean);
  const firstTaskClause = taskClauses[0] || '';
  const eventLineEvidenceCount = params.eventLine?.evidenceCount || 0;
  const normalizePreviewText = (value?: string | null) => (value || '').replace(/\s+/g, ' ').trim();
  const truncatePreviewText = (value: string, limit = 120) => (value.length <= limit ? value : `${value.slice(0, limit - 1).trim()}…`);
  const genericPreviewPatterns = [
    /^当前没有特别突出的阻塞/u,
    /^当前阻塞更像资料不足/u,
    /^当前阻塞仍需结合最近会议继续澄清/u,
    /^下一步动作：根据最近会议/u,
    /^最近进展：.+\s*\/\s*.+$/u,
    /^在.+心中/u,
    /^当前讨论集中在[:：]/u,
    /^最近进展仍待补充/u,
  ];
  const isGenericPreviewLine = (value?: string | null) => {
    const normalized = normalizePreviewText(value);
    if (!normalized) return true;
    if (genericPreviewPatterns.some((pattern) => pattern.test(normalized))) return true;
    const normalizedTitle = normalizePreviewText(params.taskTitle);
    if (normalizedTitle && normalized.includes(normalizedTitle) && normalized.length <= normalizedTitle.length + 20) return true;
    return false;
  };
  const extractPreviewTerms = (...texts: Array<string | null | undefined>) => {
    const terms = new Set<string>();
    texts
      .map((item) => normalizePreviewText(item))
      .filter(Boolean)
      .forEach((text) => {
        if (text.length <= 42) terms.add(text);
        const fragments = text.match(/[A-Za-z0-9]{2,}|[\u4e00-\u9fa5]{2,10}/g) || [];
        fragments.forEach((fragment) => {
          const normalized = fragment.trim();
          if (normalized.length < 2) return;
          if (/^(当前|任务|项目|推进|合作|说明|背景|目标|风险|下一步|最近|情况|已经|需要|继续|以及|相关)$/u.test(normalized)) return;
          terms.add(normalized);
        });
      });
    return Array.from(terms).slice(0, 28);
  };
  const previewTerms = extractPreviewTerms(
    params.taskTitle,
    params.taskDescription,
    params.eventLine?.name,
    params.eventLine?.summary,
    params.eventLine?.intent,
    ...attachmentTitles,
  );
  const relatedDocumentCards = (workspace?.documentCards || [])
    .map((card) => {
      const title = normalizePreviewText(card.title);
      const summary = normalizePreviewText(card.shortSummary || card.retrievalSummary || card.summary);
      const hintText = [
        ...(card.queryHints || []),
        ...(card.keywords || []),
        ...(card.tags || []),
        ...(card.entities || []),
      ].join(' ');
      const fullText = `${title} ${summary} ${hintText}`.toLowerCase();
      const score = previewTerms.reduce((total, term) => {
        const normalized = term.toLowerCase();
        let next = total;
        if (title.toLowerCase().includes(normalized)) next += 6;
        if (summary.toLowerCase().includes(normalized)) next += 3;
        if (fullText.includes(normalized)) next += 1;
        return next;
      }, 0);
      return { title, summary, score };
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score || left.title.length - right.title.length)
    .slice(0, 3);
  const relatedMeetings = meetings
    .map((title) => ({
      title,
      score: previewTerms.reduce((total, term) => total + (title.toLowerCase().includes(term.toLowerCase()) ? 3 : 0), 0),
    }))
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, 2)
    .map((item) => item.title);
  const strongestDocumentSummary = relatedDocumentCards[0]?.summary || '';
  const strongestDocumentTitle = relatedDocumentCards[0]?.title || '';
  const evidenceSignalText = normalizePreviewText(
    [
      taskText,
      params.eventLine?.name,
      params.eventLine?.summary,
      params.eventLine?.intent,
      ...attachmentTitles,
      ...relatedDocumentCards.map((item) => `${item.title} ${item.summary}`),
      ...relatedMeetings,
    ].join(' '),
  );
  const relationshipTask =
    /(见面|会面|拜访|约见|会谈|沟通|讨论|对接|吃饭|午餐|晚餐|演示|看系统|线下|电话会|会议|工作坊|研讨|赋能)/u.test(
      evidenceSignalText,
    );
  const materialTask = /(资料|附件|整理|补齐|导入|归档|文件|文稿|方案|设计|平台|系统|工具包|专题营)/u.test(evidenceSignalText);
  const solutionConversationTask =
    relationshipTask &&
    /(系统|平台|工作台|数字化|工具包|专题营|演示|AI|方案|设计|赋能|合作|工作坊)/u.test(evidenceSignalText);
  const hasToolkitSignal = /(工具包|专题营|专题营研讨|工作坊)/u.test(evidenceSignalText);
  const hasPlatformSignal = /(系统|平台|工作台|数字化|AI)/u.test(evidenceSignalText);
  const focusSubject = hasToolkitSignal && hasPlatformSignal
    ? 'AI工具包与数字化平台方案'
    : hasToolkitSignal
      ? 'AI工具包与专题营方案'
      : hasPlatformSignal
        ? '数字化系统与平台方案'
        : '合作方案';
  const concreteConversationFocus = solutionConversationTask
    ? `${client.name}这条任务更像一次业务会谈，要判断${focusSubject}能否切进基金会客户场景并形成下一步合作。`
    : '';
  const concreteConversationRisk = solutionConversationTask
    ? `真正阻碍不是资料量，而是这次会谈如果不钉住客户场景、价值主张和会后动作，${focusSubject}就会停在兴趣层。`
    : '';
  const concreteConversationNext = solutionConversationTask
    ? `下一步动作：会前先写清给谁看、解决什么问题、会后推进什么试点，再把${focusSubject}带进正式会谈。`
    : '';
  const concreteAttachmentProgress = attachmentTitles.length > 0
    ? `最近进展：已沉淀《${attachmentTitles.slice(0, 2).join('》《')}》，可直接作为这次会谈和方案设计的证据。`
    : '';
  const summarizeModule = (moduleKey: ClientDnaModule['moduleKey'], fallbackLength = 180) => {
    const module = moduleMap.get(moduleKey);
    if (!module?.hasDocument) return '';
    return module.summary.trim() || module.normalizedText.replace(/\s+/g, ' ').trim().slice(0, fallbackLength);
  };
  const businessSummary = summarizeModule('business_intro', 220);
  const organizationSummary = summarizeModule('organization_intro', 160);
  const teamSummary = summarizeModule('team_intro', 160);
  const marketSummary = summarizeModule('market_intro', 160);
  const dnaReadyCount = [businessSummary, organizationSummary, teamSummary, marketSummary].filter(Boolean).length;
  let completenessPoints = dnaReadyCount;
  if (goals.length > 0) completenessPoints += 1;
  if (projectModule || projectFlow) completenessPoints += 1;
  if (workspaceDocumentCount >= 24) completenessPoints += 2;
  else if (workspaceDocumentCount >= 8) completenessPoints += 1;
  if (attachmentCount > 0) completenessPoints += 1;
  if (eventLineEvidenceCount >= 3 || params.eventLine?.summary || params.eventLine?.intent || params.eventLine?.nextStep) completenessPoints += 1;
  const infoCompleteness: TaskProjectContext['infoCompleteness'] =
    completenessPoints >= 5 ? 'high' : completenessPoints >= 3 ? 'medium' : 'low';
  const backgroundSummary = relatedDocumentCards.length > 0
    ? solutionConversationTask
      ? truncatePreviewText(
          `${client.name}当前已有${relatedDocumentCards
            .slice(0, 2)
            .map((item) => `《${item.title}》`)
            .join('、')}等资料，这次不是从零摸索，而是把现有认知收成可谈的${focusSubject}。`,
          160,
        )
      : truncatePreviewText(
          relatedDocumentCards
            .map((item) => `${item.title}：${item.summary}`)
            .join('；'),
          160,
        )
    : [businessSummary, organizationSummary, teamSummary, marketSummary]
      .filter(Boolean)
      .join('；')
      .slice(0, 160)
    || (workspaceDocumentCount > 0
      ? `${client.name}当前已沉淀 ${workspaceDocumentCount} 份背景资料，但结构化目标、模块和流程还需要继续补齐。`
      : `${client.name}目前处于${client.stage || '推进中'}阶段，建议继续补齐项目背景。`);
  const goalSummary =
    (projectModule?.goal || '').trim() ||
    (solutionConversationTask ? `把这次会谈收成明确结论：${focusSubject}到底解决谁的问题、是否继续推进、会后由谁跟进。` : '') ||
    goals.slice(0, 2).join('；') ||
    (!isGenericPreviewLine(params.eventLine?.intent) ? (params.eventLine?.intent || '').trim() : '') ||
    strongestDocumentSummary ||
    businessSummary.slice(0, 120) ||
    '当前还没有明确写入项目目标。';
  const riskSummary =
    projectFlow?.riskPoints?.length
      ? `当前流程风险：${projectFlow.riskPoints.slice(0, 2).join('；')}`.slice(0, 120)
      : !isGenericPreviewLine(params.eventLine?.currentBlocker)
        ? params.eventLine?.currentBlocker?.slice(0, 120)
        : concreteConversationRisk
          ? truncatePreviewText(concreteConversationRisk, 120)
          : relationshipTask && workspaceDocumentCount >= 8
            ? `当前风险不在资料总量，而在这次会谈如果不明确客户场景、价值主张和会后收束动作，${focusSubject}仍会停在泛交流。`
          : materialTask && workspaceDocumentCount >= 8
            ? '当前风险不是资料少，而是这些资料还没有被收成可执行的判断、方案和后续动作。'
          : strongestDocumentSummary
            ? `当前风险更像${truncatePreviewText(strongestDocumentSummary, 72)}还没被收成明确结论。`
            : marketSummary
              ? `外部环境提示：${marketSummary}`.slice(0, 120)
              : infoCompleteness === 'low'
                ? workspaceDocumentCount >= 8
                  ? '当前并不是资料太少，而是结构化归属还偏薄，目标、模块和流程线索仍需补齐。'
                  : '当前项目背景仍偏薄，建议补齐四张项目资料卡后再做更深判断。'
                : relatedMeetings.length > 0
                  ? `最近讨论集中在：${relatedMeetings.join(' / ')}。`
                  : '当前暂无明显风险提示，可围绕既定目标继续推进。';
  const currentFocus = (() => {
    if (solutionConversationTask) {
      return truncatePreviewText(
        `当前任务的真正落点是：把${focusSubject}带进这次会谈，判断它是否能成为 CFFC 面向基金会客户的下一步合作抓手。`,
        120,
      );
    }
    if (firstTaskClause) return `当前任务更具体的落点是：${firstTaskClause}`.slice(0, 120);
    if (concreteConversationFocus) return truncatePreviewText(concreteConversationFocus, 120);
    if (relationshipTask) {
      return `${client.name}这条任务更像线下会谈/演示确认，核心是把要谈的对象、主题和合作落点说清楚。`.slice(0, 120);
    }
    if (materialTask) {
      return `${client.name}这条任务更像在补资料与设计底稿，核心是把当前事项沉淀成可继续推进的正式材料。`.slice(0, 120);
    }
    if (projectModule?.name) {
      return `${projectModule.name}${projectModule.goal ? `：${projectModule.goal}` : ''}`.slice(0, 120);
    }
    if (goals.length > 0) return `当前主要在推进：${goals[0]}`.slice(0, 120);
    if (!isGenericPreviewLine(params.eventLine?.summary)) return params.eventLine?.summary?.slice(0, 120) || '';
    if (strongestDocumentSummary && strongestDocumentTitle) return truncatePreviewText(`${strongestDocumentTitle}：${strongestDocumentSummary}`, 120);
    if (relatedMeetings.length > 0) return `当前讨论集中在：${relatedMeetings[0]}`.slice(0, 120);
    return `${client.name}当前重点仍待补充，建议先明确这一阶段的核心事项。`.slice(0, 120);
  })();
  const currentBlocker = (() => {
    if (projectFlow?.riskPoints?.length) {
      return `当前阻塞：${projectFlow.riskPoints.slice(0, 2).join('；')}`.slice(0, 120);
    }
    if (!isGenericPreviewLine(params.eventLine?.currentBlocker)) return params.eventLine?.currentBlocker?.slice(0, 120) || '';
    if (concreteConversationRisk) return truncatePreviewText(concreteConversationRisk, 120);
    if (relationshipTask && workspaceDocumentCount >= 8) {
      return `当前阻塞更像这次会谈还没有钉住客户场景、关键判断和会后责任，${focusSubject}仍可能停在交流层。`;
    }
    if (materialTask && attachmentCount > 0) {
      return '当前阻塞不是资料数量，而是这些材料还没有被收成一句明确判断和一个可执行的后续动作。';
    }
    if (infoCompleteness === 'low') {
      return workspaceDocumentCount >= 8
        ? '当前阻塞更像结构化归属不足，项目背景、目标和流程线索还没有完全挂实。'
        : '当前阻塞更像资料不足，项目背景、目标和流程线索都还不完整。';
    }
    if (relatedMeetings.length > 0) return '当前阻塞仍需结合最近讨论继续澄清。'.slice(0, 120);
    return '当前没有特别突出的阻塞，但仍需盯住推进收束。';
  })();
  const nextAction = (() => {
    if (projectFlow?.steps?.length) return `下一步动作：${projectFlow.steps[0]}`.slice(0, 120);
    if (!isGenericPreviewLine(params.eventLine?.nextStep)) return params.eventLine?.nextStep?.slice(0, 120) || '';
    if (concreteConversationNext) return truncatePreviewText(concreteConversationNext, 120);
    if (relationshipTask) {
      return `下一步动作：会前先写清"给谁看、解决什么问题、会后推进什么动作"，再带着${focusSubject}去谈。`.slice(0, 120);
    }
    if (materialTask && attachmentCount > 0) {
      return '下一步动作：先把已上传材料压成可谈的结论、关键判断和会后跟进动作，再进入正式推进。'.slice(0, 120);
    }
    if (projectModule?.name) return `下一步动作：围绕${projectModule.name}继续细化并推进落地。`.slice(0, 120);
    if (goals.length > 0) return `下一步动作：继续围绕"${goals[0]}"推进具体动作。`.slice(0, 120);
    if (relatedMeetings.length > 0) return `下一步动作：根据最近讨论"${relatedMeetings[0]}"形成明确安排。`.slice(0, 120);
    return '下一步动作：先补齐项目背景，再明确这一阶段最核心的推进事项。';
  })();
  const recentProgress = (() => {
    if (concreteAttachmentProgress) {
      return truncatePreviewText(concreteAttachmentProgress, 120);
    }
    if (!isGenericPreviewLine(params.eventLine?.recentDecision)) return `最近进展：${params.eventLine?.recentDecision}`.slice(0, 120);
    if (relatedDocumentCards.length > 0) {
      return truncatePreviewText(`最近进展：相关证据已集中在 ${relatedDocumentCards.slice(0, 2).map((item) => `《${item.title}》`).join('、')}。`, 120);
    }
    if (relatedMeetings.length > 0) return `最近进展：${relatedMeetings.join(' / ')}`.slice(0, 120);
    if (workspaceDocumentCount >= 8) {
      return `最近进展：${workspaceLabel}里已沉淀 ${workspaceDocumentCount} 份相关资料，但还需要继续把它们挂到具体推进结构上。`.slice(0, 120);
    }
    if (goals.length > 0) return `最近进展：已围绕"${goals[0]}"持续推进。`.slice(0, 120);
    return '最近进展仍待补充，建议尽快沉淀会议或推进记录。';
  })();
  const sourceEvidence = [`任务关联${singularLabel}`];
  if (workspace) sourceEvidence.push(`${workspaceLabel}上下文`);
  if (workspaceDocumentCount > 0) sourceEvidence.push(`知识资料 ${workspaceDocumentCount} 份`);
  relatedDocumentCards.slice(0, 2).forEach((item) => sourceEvidence.push(`资料卡：${item.title}`));
  attachmentTitles.slice(0, 2).forEach((item) => sourceEvidence.push(`附件：${item}`));
  if (goals.length > 0) sourceEvidence.push('项目目标');
  if (organizationSummary) sourceEvidence.push('组织介绍');
  if (businessSummary) sourceEvidence.push('项目介绍');
  if (teamSummary) sourceEvidence.push('团队介绍');
  if (marketSummary) sourceEvidence.push('市场背景');
  if (attachmentCount > 0) sourceEvidence.push(`任务附件 ${attachmentCount} 份`);
  if (params.eventLine?.name) sourceEvidence.push(`事件线：${params.eventLine.name}`);
  if (eventLineEvidenceCount > 0) sourceEvidence.push(`事件线证据 ${eventLineEvidenceCount} 条`);
  if (projectModule) sourceEvidence.push(`任务模块：${projectModule.name}`);
  if (projectFlow) sourceEvidence.push(`流程：${projectFlow.name}`);
  return {
    clientId: client.id,
    clientName: client.name,
    stage: client.stage || null,
    projectModuleId: projectModule?.id || null,
    projectModuleName: projectModule?.name || null,
    projectModuleSummary: [projectModule?.goal, projectModule?.description].filter(Boolean).join('；').slice(0, 140) || null,
    projectFlowId: projectFlow?.id || null,
    projectFlowName: projectFlow?.name || null,
    projectFlowSummary: [projectFlow?.scenario, projectFlow?.description].filter(Boolean).join('；').slice(0, 140) || null,
    backgroundSummary: backgroundSummary.slice(0, 160),
    goalSummary: goalSummary.slice(0, 120),
    riskSummary: riskSummary.slice(0, 120),
    currentFocus: currentFocus.slice(0, 120),
    currentBlocker: currentBlocker.slice(0, 120),
    nextAction: nextAction.slice(0, 120),
    recentProgress: recentProgress.slice(0, 120),
    infoCompleteness,
    sourceEvidence,
  };
}

function parseTaskDateValue(value?: string | null) {
  if (!value) return null;
  const { date } = splitTaskDueDateTime(value);
  const match = date.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (match) {
    return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate());
}

function resolveTaskDueDate(task: Task) {
  const explicitDate = parseTaskDateValue(task.dueDate);
  if (explicitDate) return explicitDate;
  if (!task.ddl || task.ddl === '待确认') return null;
  const inferredDate = normalizeDdlToDate(task.ddl);
  if (Number.isNaN(inferredDate.getTime())) return null;
  return new Date(inferredDate.getFullYear(), inferredDate.getMonth(), inferredDate.getDate());
}

function startOfCalendarDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function isPastCalendarDueDay(dueDate: Date, today = new Date()) {
  return startOfCalendarDay(dueDate).getTime() < startOfCalendarDay(today).getTime();
}

function isTaskOverdue(task: Task, today = new Date()) {
  if (task.status === 'done') return false;
  const dueDate = resolveTaskDueDate(task);
  if (!dueDate) return false;
  return isPastCalendarDueDay(dueDate, today);
}

function normalizeDdlToDate(label: string) {
  const now = new Date();
  if (label === '今天') return new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (label === '本周') return new Date(now.getFullYear(), now.getMonth(), now.getDate() + 3);
  const dayMap: Record<string, number> = { 周一: 1, 周二: 2, 周三: 3, 周四: 4, 周五: 5, 周六: 6, 周日: 0 };
  if (label in dayMap) {
    const delta = (dayMap[label] - now.getDay() + 7) % 7;
    return new Date(now.getFullYear(), now.getMonth(), now.getDate() + delta);
  }
  const match = label.match(/^(\d{2})-(\d{2})$/);
  if (match) {
    return new Date(now.getFullYear(), Number(match[1]) - 1, Number(match[2]));
  }
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function normalizeDdlToDateTime(label?: string | null) {
  if (!label) return null;
  const text = label.trim();
  if (!text || text === '待确认') return null;

  const now = new Date();
  const applyTime = (date: Date, hours = 0, minutes = 0) =>
    new Date(date.getFullYear(), date.getMonth(), date.getDate(), hours, minutes);

  const todayMatch = text.match(/^今天(?:\s+(\d{1,2}):(\d{2}))?$/);
  if (todayMatch) {
    return applyTime(
      new Date(now.getFullYear(), now.getMonth(), now.getDate()),
      Number(todayMatch[1] || 0),
      Number(todayMatch[2] || 0),
    );
  }

  const weekMatch = text.match(/^本周(?:\s+(\d{1,2}):(\d{2}))?$/);
  if (weekMatch) {
    const base = normalizeDdlToDate('本周');
    return applyTime(base, Number(weekMatch[1] || 0), Number(weekMatch[2] || 0));
  }

  const weekdayMatch = text.match(/^(周[一二三四五六日])(?:\s+(\d{1,2}):(\d{2}))?$/);
  if (weekdayMatch) {
    const base = normalizeDdlToDate(weekdayMatch[1]);
    return applyTime(base, Number(weekdayMatch[2] || 0), Number(weekdayMatch[3] || 0));
  }

  const monthDayMatch = text.match(/^(\d{2})-(\d{2})(?:\s+(\d{1,2}):(\d{2}))?$/);
  if (monthDayMatch) {
    const base = normalizeDdlToDate(`${monthDayMatch[1]}-${monthDayMatch[2]}`);
    return applyTime(base, Number(monthDayMatch[3] || 0), Number(monthDayMatch[4] || 0));
  }

  const parsed = new Date(text);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function parseTaskTimelineWindowFromLabel(label?: string | null) {
  const text = (label || '').trim();
  if (!text) {
    return { startTime: '', dueTime: '', hasSpecificTime: false };
  }
  const rangeMatch = text.match(/(?:今天|本周|周[一二三四五六日]|\d{2}-\d{2})\s+(\d{1,2}:\d{2})(?:-(\d{1,2}:\d{2}))?/);
  const normalizedStart = normalizeTaskTimeInput(rangeMatch?.[1] || '');
  const normalizedDue = normalizeTaskTimeInput(rangeMatch?.[2] || normalizedStart);
  if (!normalizedStart && !normalizedDue) {
    return { startTime: '', dueTime: '', hasSpecificTime: false };
  }
  return {
    startTime: normalizedStart,
    dueTime: normalizedDue || normalizedStart,
    hasSpecificTime: true,
  };
}

function resolveTaskTimelineDateTime(task: Task) {
  return resolveUnifiedTaskTimelineDateTime(task);
}

function taskDateForCalendar(task: Task) {
  return resolveUnifiedTaskDateForCalendar(task);
}

function taskInvolvesUser(task: Task, userId: string | null | undefined) {
  if (!userId) return false;
  if (task.ownerId === userId) return true;
  if (task.creatorId === userId) return true;
  return task.collaborators.some((item) => item.userId === userId);
}

function taskIsPrimaryForUser(task: Task, userId: string | null | undefined) {
  if (!userId) return false;
  return task.ownerId === userId || task.creatorId === userId;
}

function taskIsCollaborativeWatchForUser(task: Task, userId: string | null | undefined) {
  if (!userId) return false;
  if (taskIsPrimaryForUser(task, userId)) return false;
  return task.collaborators.some((item) => item.userId === userId);
}

function taskIsCollaborative(task: Task) {
  if (task.scopeMode === 'PERSONAL_ONLY') return false;
  const participantIds = new Set<string>();
  if (task.creatorId) participantIds.add(task.creatorId);
  if (task.ownerId) participantIds.add(task.ownerId);
  task.collaborators.forEach((item) => {
    if (item.userId) participantIds.add(item.userId);
  });
  if (participantIds.size > 1) return true;
  return task.collaborators.some((item) => !item.isOwner);
}

function taskWaitsForOthers(task: Task, userId: string | null | undefined) {
  if (!userId) return false;
  if (!taskIsPrimaryForUser(task, userId)) return false;
  return Number(task.collaborationSummary?.pending || 0) > 0;
}

function taskMatchesParticipationFilter(task: Task, filter: TaskParticipationFilter) {
  if (filter === 'all') return true;
  const collaborative = taskIsCollaborative(task);
  return filter === 'collab' ? collaborative : !collaborative;
}

function taskCanToggleCompletion(task: Task, userId: string | null | undefined) {
  if (!userId) return false;
  if (task.ownerId === userId) return true;
  return task.collaborators.some((item) => item.userId === userId);
}

function taskMatchesTimeRange(
  task: Task,
  filter: TaskTimeRangeFilter,
  customStartDate: string,
  customEndDate: string,
) {
  if (filter === 'all') return true;
  const taskDate = resolveTaskTimelineDateTime(task);
  if (!taskDate) return false;
  const taskTime = taskDate.getTime();
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  if (filter === 'last3days') {
    const start = new Date(startOfToday);
    start.setDate(start.getDate() - 2);
    return taskTime >= start.getTime();
  }
  if (filter === 'lastMonth') {
    const start = new Date(startOfToday);
    start.setMonth(start.getMonth() - 1);
    return taskTime >= start.getTime();
  }
  if (filter === 'lastHalfYear') {
    const start = new Date(startOfToday);
    start.setMonth(start.getMonth() - 6);
    return taskTime >= start.getTime();
  }
  if (filter === 'custom') {
    const start = customStartDate ? new Date(`${customStartDate}T00:00:00`) : null;
    const end = customEndDate ? new Date(`${customEndDate}T23:59:59`) : null;
    if (start && !Number.isNaN(start.getTime()) && taskTime < start.getTime()) return false;
    if (end && !Number.isNaN(end.getTime()) && taskTime > end.getTime()) return false;
    return true;
  }
  return true;
}

function sortTasksByTimeDirection(tasks: Task[], direction: TaskTimeSort) {
  return [...tasks].sort((left, right) => {
    const leftTime = resolveTaskTimelineDateTime(left)?.getTime() || 0;
    const rightTime = resolveTaskTimelineDateTime(right)?.getTime() || 0;
    return direction === 'newest' ? rightTime - leftTime : leftTime - rightTime;
  });
}

function weekLabelForDate(baseDate: Date) {
  const utcDate = new Date(Date.UTC(baseDate.getFullYear(), baseDate.getMonth(), baseDate.getDate()));
  const day = utcDate.getUTCDay() || 7;
  utcDate.setUTCDate(utcDate.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(utcDate.getUTCFullYear(), 0, 1));
  const week = Math.ceil((((utcDate.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  return `${utcDate.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

function currentWeekLabel() {
  return weekLabelForDate(new Date());
}

/** Convert "2026-W14" to "第14周" for display */
function weekLabelCN(label: string): string {
  const m = label.match(/^\d{4}-W(\d{2})$/);
  return m ? `第${parseInt(m[1], 10)}周` : label;
}

function weekBounds(weekLabel: string) {
  const match = weekLabel.match(/^(\d{4})-W(\d{2})$/);
  if (!match) return null;
  const year = Number(match[1]);
  const week = Number(match[2]);
  const start = new Date(Date.UTC(year, 0, 1 + (week - 1) * 7));
  const day = start.getUTCDay() || 7;
  if (day <= 4) {
    start.setUTCDate(start.getUTCDate() - day + 1);
  } else {
    start.setUTCDate(start.getUTCDate() + 8 - day);
  }
  const end = new Date(start);
  end.setUTCDate(start.getUTCDate() + 6);
  return { start, end };
}

function taskDateForReview(task: Task) {
  return resolveTaskTimelineDateTime(task);
}

function isTaskInReviewWeek(task: Task, weekLabel: string) {
  const bounds = weekBounds(weekLabel);
  const taskDate = taskDateForReview(task);
  if (!bounds || !taskDate) return false;
  return taskDate >= bounds.start && taskDate <= bounds.end;
}

function materializeTaskFromReviewItem(item: WeeklyReviewTaskEntry, existingTask?: Task | null): Task {
  const snapshot = item.taskSnapshot;
  const eventLineContext = snapshot.eventLineContext;
  if (existingTask) {
    return {
      ...existingTask,
      title: snapshot.title || existingTask.title,
      status: snapshot.status || existingTask.status,
      startDate: (snapshot as { startDate?: string | null }).startDate ?? existingTask.startDate ?? null,
      dueDate: snapshot.dueDate ?? existingTask.dueDate ?? null,
      clientId: snapshot.clientId ?? existingTask.clientId ?? null,
      clientName: snapshot.clientName ?? existingTask.clientName ?? null,
      eventLineId: snapshot.eventLineId ?? eventLineContext?.id ?? existingTask.eventLineId ?? null,
      eventLineName: snapshot.eventLineName ?? eventLineContext?.name ?? existingTask.eventLineName ?? null,
      ownerId: snapshot.ownerId ?? existingTask.ownerId ?? null,
      ownerName: snapshot.ownerName || existingTask.ownerName || '未指定',
      tags: snapshot.tags?.length ? snapshot.tags : existingTask.tags,
      listName: snapshot.listName || existingTask.listName,
      listColor: snapshot.listColor || existingTask.listColor,
      orgContext: snapshot.orgContext ?? existingTask.orgContext ?? null,
      projectContext: snapshot.projectContext ?? existingTask.projectContext ?? null,
      currentBlocker: eventLineContext?.currentBlocker ?? existingTask.currentBlocker ?? null,
      recentDecision: eventLineContext?.recentDecision ?? existingTask.recentDecision ?? null,
      nextAction: eventLineContext?.nextStep ?? existingTask.nextAction ?? null,
      evidenceCount: eventLineContext?.evidenceCount ?? existingTask.evidenceCount ?? 0,
      createdAt: snapshot.createdAt || existingTask.createdAt,
      updatedAt: existingTask.updatedAt || snapshot.createdAt,
    };
  }
  const syntheticListId = `review:${snapshot.listName || 'default'}`;
  return {
    id: item.taskId,
    title: snapshot.title || '未命名任务',
    desc: snapshot.projectContext?.backgroundSummary || eventLineContext?.summary || '',
    status: snapshot.status || 'todo',
    creatorId: null,
    creatorName: null,
    priority: 'normal',
    listId: syntheticListId,
    listName: snapshot.listName || '周复盘',
    listColor: snapshot.listColor || '#5B7BFE',
    ddl: snapshot.dueDate || '',
    startDate: (snapshot as { startDate?: string | null }).startDate ?? null,
    dueDate: snapshot.dueDate ?? null,
    durationMinutes: undefined,
    scopeMode: item.contentDomain === 'personal' ? 'PERSONAL_ONLY' : 'ALL',
    clientId: snapshot.clientId ?? null,
    clientName: snapshot.clientName ?? null,
    eventLineId: snapshot.eventLineId ?? eventLineContext?.id ?? null,
    eventLineName: snapshot.eventLineName ?? eventLineContext?.name ?? null,
    projectModuleId: snapshot.projectContext?.projectModuleId ?? null,
    projectModuleName: snapshot.projectContext?.projectModuleName ?? null,
    projectFlowId: snapshot.projectContext?.projectFlowId ?? null,
    projectFlowName: snapshot.projectContext?.projectFlowName ?? null,
    ownerId: snapshot.ownerId ?? null,
    ownerName: snapshot.ownerName || '未指定',
    sourceType: 'weekly_review',
    sourceId: item.reviewId ?? item.id,
    businessCategory: eventLineContext?.businessCategory ?? null,
    currentBlocker: eventLineContext?.currentBlocker ?? null,
    nextAction: eventLineContext?.nextStep ?? null,
    recentDecision: eventLineContext?.recentDecision ?? null,
    evidenceCount: eventLineContext?.evidenceCount ?? 0,
    tags: snapshot.tags || [],
    note: item.note || null,
    attachments: [],
    collaborators: [],
    collaborationSummary: {},
    viewerInboxStatus: null,
    orgContext: snapshot.orgContext ?? null,
    projectContext: snapshot.projectContext ?? null,
    memoryHints: [],
    backgroundReadiness: null,
    linkedFactsPreview: [],
    createdAt: snapshot.createdAt || new Date().toISOString(),
    updatedAt: snapshot.createdAt || new Date().toISOString(),
  };
}

function pickSharedReviewStructuredNote(rows: ReviewTaskRow[]) {
  const meaningfulRows = rows.filter(({ structuredNote, note }) => hasMeaningfulReviewStructuredNote(structuredNote) || Boolean(note.trim()));
  if (meaningfulRows.length === 0) {
    return createEmptyReviewStructuredNote();
  }
  return { ...meaningfulRows[0].structuredNote };
}

function buildReviewGroups(rows: ReviewTaskRow[]): ReviewTaskGroup[] {
  const groups = new Map<string, ReviewTaskRow[]>();
  rows.forEach((row) => {
    const eventLineId = row.task.eventLineId?.trim() || '';
    const key = eventLineId ? `event-line:${eventLineId}` : `task:${row.task.id}`;
    const bucket = groups.get(key);
    if (bucket) {
      bucket.push(row);
    } else {
      groups.set(key, [row]);
    }
  });

  return Array.from(groups.entries())
    .map(([key, groupRows]) => {
      const eventLineId = groupRows[0]?.task.eventLineId?.trim() || null;
      const eventLineName = groupRows[0]?.task.eventLineName?.trim() || null;
      const sharedStructuredNote = pickSharedReviewStructuredNote(groupRows);
      const uniqueNotes = new Set(
        groupRows
          .map(({ structuredNote, note }) =>
            JSON.stringify({
              reflection: structuredNote.reflection.trim() || note.trim(),
              lightweightTag: structuredNote.lightweightTag,
            }),
          )
          .filter((value) => value !== JSON.stringify({ reflection: '', lightweightTag: '' })),
      );
      const completedCount = groupRows.filter(({ task }) => task.status === 'done').length;
      const cancelledCount = groupRows.filter(({ task }) => task.status === 'rejected').length;
      const reviewedCount = groupRows.filter(({ note }) => Boolean(note.trim())).length;
      return {
        id: key,
        eventLineId,
        eventLineName,
        title: eventLineName || groupRows[0]?.task.title || '未命名事项',
        rows: [...groupRows].sort((left, right) => {
          const leftTime = taskDateForReview(left.task)?.getTime() || 0;
          const rightTime = taskDateForReview(right.task)?.getTime() || 0;
          return leftTime - rightTime;
        }),
        taskCount: groupRows.length,
        completedCount,
        pendingCount: groupRows.length - completedCount,
        reviewedCount,
        sharedStructuredNote,
        hasDivergentNotes: uniqueNotes.size > 1,
        taskStatus: (completedCount === groupRows.length
          ? 'done'
          : cancelledCount === groupRows.length
            ? 'rejected'
            : 'doing') as Task['status'],
      };
    })
    .sort((left, right) => {
      const leftTime = taskDateForReview(left.rows[0]?.task)?.getTime() || 0;
      const rightTime = taskDateForReview(right.rows[0]?.task)?.getTime() || 0;
      return leftTime - rightTime;
    });
}

function isPrivateTask(task: Task) {
  return task.scopeMode === 'PERSONAL_ONLY' || task.tags.some((tag) => tag.scope === 'self');
}

function isLocalDraftTaskId(taskId?: string | null) {
  return Boolean(taskId && taskId.startsWith('local-draft:'));
}

function createEmptyReviewForm(weekLabel = currentWeekLabel()): ReviewFormState {
  return {
    weekLabel,
    entriesByTaskId: {},
  };
}

const MAX_BRAND_LOGO_UPLOAD_BYTES = 3 * 1024 * 1024;
const BRAND_LOGO_MAX_EDGE = 256;

function readFileAsDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '');
    reader.onerror = () => reject(new Error('PNG 读取失败'));
    reader.readAsDataURL(file);
  });
}

function loadImageFromUrl(url: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('PNG 解码失败'));
    image.src = url;
  });
}

async function normalizeBrandLogoFile(file: File) {
  if (file.type !== 'image/png') {
    throw new Error('当前只支持上传 PNG');
  }
  if (file.size > MAX_BRAND_LOGO_UPLOAD_BYTES) {
    throw new Error('PNG 过大，请控制在 3MB 以内');
  }
  const sourceUrl = await readFileAsDataUrl(file);
  const image = await loadImageFromUrl(sourceUrl);
  const longestEdge = Math.max(image.naturalWidth || image.width || 0, image.naturalHeight || image.height || 0);
  if (!longestEdge) {
    throw new Error('PNG 尺寸无效');
  }
  const scale = Math.min(1, BRAND_LOGO_MAX_EDGE / longestEdge);
  const width = Math.max(1, Math.round((image.naturalWidth || image.width) * scale));
  const height = Math.max(1, Math.round((image.naturalHeight || image.height) * scale));
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d');
  if (!context) {
    throw new Error('当前环境不支持图片处理');
  }
  context.clearRect(0, 0, width, height);
  context.drawImage(image, 0, 0, width, height);
  const normalized = canvas.toDataURL('image/png');
  if (normalized.length > 1_500_000) {
    throw new Error('PNG 过大，请换更简单的图标');
  }
  return normalized;
}

function selectFolderBridge() {
  if (window.__YIYU_TEST_DIALOGS__?.selectFolder) return window.__YIYU_TEST_DIALOGS__.selectFolder();
  return window.yiyuWorkbench.selectFolder();
}

function selectFilesBridge() {
  if (window.__YIYU_TEST_DIALOGS__?.selectFiles) return window.__YIYU_TEST_DIALOGS__.selectFiles();
  return window.yiyuWorkbench.selectFiles();
}

function inferClientTextDocumentTitle(content: string) {
  const normalized = content.replace(/\r\n/g, '\n').trim();
  if (!normalized) return '';
  for (const rawLine of normalized.split('\n')) {
    const line = rawLine.replace(/^[#>*\-\d\.\)\s]+/, '').trim();
    if (line.length < 4) continue;
    return (line.split(/[。！？!?]/)[0] || line).trim().slice(0, 28);
  }
  return normalized.replace(/\s+/g, ' ').slice(0, 28);
}

function inferTaskArchiveDocumentTitle(params: {
  taskTitle?: string | null;
  clientName?: string | null;
  eventLineName?: string | null;
  content?: string | null;
}) {
  const taskTitle = (params.taskTitle || '').trim();
  if (taskTitle) return taskTitle.slice(0, 48);
  const eventLineName = (params.eventLineName || '').trim();
  if (eventLineName) return eventLineName.slice(0, 48);
  const clientName = (params.clientName || '').trim();
  if (clientName) return `${clientName}补充材料`.slice(0, 48);
  return inferClientTextDocumentTitle(params.content || '') || '任务补充材料';
}

type DroppedImportFile = File & { path?: string };
type DroppedTransferEntry = { isDirectory?: boolean };
type DroppedTransferItem = DataTransferItem & {
  webkitGetAsEntry?: () => DroppedTransferEntry | null;
};

function hasFileDragData(dataTransfer?: DataTransfer | null) {
  if (!dataTransfer) return false;
  return Array.from(dataTransfer.types || []).includes('Files');
}

function droppedDataContainsDirectory(dataTransfer?: DataTransfer | null) {
  if (!dataTransfer?.items?.length) return false;
  return Array.from(dataTransfer.items).some((item) => {
    const entry = (item as DroppedTransferItem).webkitGetAsEntry?.();
    return Boolean(entry?.isDirectory);
  });
}

function extractDroppedFilePaths(dataTransfer?: DataTransfer | null) {
  const seen = new Set<string>();
  const paths: string[] = [];
  for (const file of Array.from(dataTransfer?.files || []) as DroppedImportFile[]) {
    const targetPath = String(file.path || window.yiyuWorkbench.getDroppedFilePath(file) || '').trim();
    if (!targetPath || seen.has(targetPath)) continue;
    seen.add(targetPath);
    paths.push(targetPath);
  }
  for (const item of Array.from(dataTransfer?.items || []) as DroppedTransferItem[]) {
    const file = item.getAsFile?.() as DroppedImportFile | null;
    const targetPath = String((file && (file.path || window.yiyuWorkbench.getDroppedFilePath(file))) || '').trim();
    if (!targetPath || seen.has(targetPath)) continue;
    seen.add(targetPath);
    paths.push(targetPath);
  }
  return paths;
}

function normalizeDroppedFsPath(targetPath: string) {
  return targetPath.replace(/\\/g, '/').replace(/\/{2,}/g, '/').trim();
}

function parentDirectoryOfDroppedPath(targetPath: string) {
  const normalized = normalizeDroppedFsPath(targetPath);
  if (!normalized) return '';
  if (normalized === '/') return '/';
  const parts = normalized.split('/');
  parts.pop();
  if (parts.length === 0) return '';
  if (parts.length === 1 && parts[0] === '') return '/';
  return parts.join('/') || '/';
}

function inferDroppedDirectoryPath(paths: string[]) {
  const normalizedParents = paths
    .map((item) => parentDirectoryOfDroppedPath(item))
    .filter(Boolean);
  if (!normalizedParents.length) return null;
  const segmentsList = normalizedParents.map((item) => item.split('/'));
  const firstSegments = segmentsList[0] || [];
  const common: string[] = [];
  for (let index = 0; index < firstSegments.length; index += 1) {
    const candidate = firstSegments[index];
    if (!segmentsList.every((segments) => segments[index] === candidate)) break;
    common.push(candidate);
  }
  if (!common.length) return null;
  if (common.length === 1 && common[0] === '') return '/';
  return common.join('/') || '/';
}

function openPathBridge(targetPath: string) {
  if (window.__YIYU_TEST_DIALOGS__?.openPath) return window.__YIYU_TEST_DIALOGS__.openPath(targetPath);
  return window.yiyuWorkbench.openPath(targetPath);
}

function revealInFinderBridge(targetPath: string) {
  if (window.__YIYU_TEST_DIALOGS__?.revealInFinder) return window.__YIYU_TEST_DIALOGS__.revealInFinder(targetPath);
  return window.yiyuWorkbench.revealInFinder(targetPath);
}

function saveFileAsBridge(sourcePath: string, suggestedName?: string) {
  if (window.__YIYU_TEST_DIALOGS__?.saveFileAs) return window.__YIYU_TEST_DIALOGS__.saveFileAs(sourcePath, suggestedName);
  return window.yiyuWorkbench.saveFileAs(sourcePath, suggestedName);
}

function selectCollabRepoBridge() {
  if (window.__YIYU_TEST_DIALOGS__?.selectCollabRepo) return window.__YIYU_TEST_DIALOGS__.selectCollabRepo();
  return selectCollabRepo();
}

function createUiId(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

type TaskPropertyRowProps = {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
};

const COMMON_SURNAME_SET = new Set(['王', '张', '李', '赵', '刘', '陈', '杨', '黄', '周', '吴', '徐', '孙', '胡', '朱', '高', '林', '何', '郭', '马', '罗', '梁', '宋', '郑', '谢', '韩', '唐', '冯', '于', '董', '程']);

const buildNameBadge = (name: string) => {
  const trimmed = name.trim();
  if (!trimmed) return '未';
  const firstChar = trimmed[0];
  if (COMMON_SURNAME_SET.has(firstChar) && trimmed.length > 1) {
    return trimmed[1];
  }
  return firstChar;
};

function TaskPropertyRow({ icon, label, children }: TaskPropertyRowProps) {
  return (
    <div className="flex items-center">
      <div className="flex w-[104px] flex-shrink-0 items-center gap-2 text-gray-500">
        {icon}
        <span className="text-sm">{label}</span>
      </div>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export default function App() {
  const initialTodayState = getTodayCalendarState();
  const [activeTab, setActiveTab] = useState<NavKey>('tasks');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem('yiyu-sidebar-collapsed') === '1';
  });
  const [collabRepoPath, setCollabRepoPath] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return normalizeInitialCollabRepoPath(window.localStorage.getItem(COLLAB_REPO_PATH_STORAGE_KEY));
  });
  const [collabStatus, setCollabStatus] = useState<CollabRepoStatus | null>(null);
  const [isCollabStatusLoading, setIsCollabStatusLoading] = useState(false);
  const [collabBusyAction, setCollabBusyAction] = useState<'push' | 'pull' | 'rebuild' | null>(null);
  const [collabDialogState, setCollabDialogState] = useState<CollabDialogState>(null);
  const [collabSelectedPaths, setCollabSelectedPaths] = useState<string[]>([]);
  const [collabCommitMessage, setCollabCommitMessage] = useState('');
  const [collabDialogError, setCollabDialogError] = useState<string | null>(null);
  const collabAutoSwitchTargetRef = useRef<string | null>(null);
  const [taskViewMode, setTaskViewMode] = useState<TaskViewMode>('calendar');
  const previousTaskViewModeRef = useRef<TaskViewMode>('calendar');
  const taskViewportRef = useRef<HTMLDivElement | null>(null);
    const [taskSelectedDay, setTaskSelectedDay] = useState(initialTodayState.selectedDay);
    const [taskCalendarDisplayMode, setTaskCalendarDisplayMode] = useState<'month' | 'week'>('month');
    const [taskSelectedDate, setTaskSelectedDate] = useState(() => new Date(initialTodayState.calendarDate.getFullYear(), initialTodayState.calendarDate.getMonth(), initialTodayState.selectedDay));
  const [taskCalendarDate, setTaskCalendarDate] = useState(initialTodayState.calendarDate);
  const [expandedTaskIds, setExpandedTaskIds] = useState<string[]>([]);
  const taskCalendarMonthLabel = `${taskCalendarDate.getFullYear()}-${String(taskCalendarDate.getMonth() + 1).padStart(2, '0')}`;
  const [clientOverlayMode, setClientOverlayMode] = useState<ClientOverlayMode>(null);
  const [workspaceSelectedMeetingId, setWorkspaceSelectedMeetingId] = useState('');
  const [workspaceMeetingTranscript, setWorkspaceMeetingTranscript] = useState('');
  const [workspaceMeetingNotes, setWorkspaceMeetingNotes] = useState('');

  const [authState, setAuthState] = useState<AuthState>(DEFAULT_LOCAL_AUTH_STATE);
  const [departmentOptions, setDepartmentOptions] = useState<DepartmentOption[]>([]);
  const [employeeReviews, setEmployeeReviews] = useState<EmployeeRecord[]>([]);
  const [settingsState, setSettingsState] = useState<AppSettings | null>(null);
  const [workObjectTerminologyState, setWorkObjectTerminologyState] = useState<WorkObjectTerminologyState | null>(null);
  const [taskSettingsState, setTaskSettingsState] = useState<TaskSettings | null>(null);
  const [reviewGovernanceState, setReviewGovernanceState] = useState<ReviewGovernanceSettings>(EMPTY_REVIEW_GOVERNANCE_SETTINGS);
  const [orgModelState, setOrgModelState] = useState<OrgModelSettings>(EMPTY_ORG_MODEL_SETTINGS);
  const [agentWorklogs, setAgentWorklogs] = useState<AgentWorklog[]>([]);
  const [agentWeeklyDigests, setAgentWeeklyDigests] = useState<AgentWeeklyDigest[]>([]);
  const [agentWeeklyPlans, setAgentWeeklyPlans] = useState<AgentWeeklyPlan[]>([]);
  const [operators, setOperators] = useState<Operator[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [desktopAppInfo, setDesktopAppInfo] = useState<DesktopAppInfo | null>(null);
  const previousActiveTabRef = useRef(activeTab);
  const [backendCompatibilityError, setBackendCompatibilityError] = useState<string | null>(null);
  const [isImportSubmitting, setIsImportSubmitting] = useState(false);
  const [latestImportFeedback, setLatestImportFeedback] = useState<ImportFeedback | null>(null);
  const importProgressHoldUntilRef = useRef<number>(0);
  const [settingsSection, setSettingsSection] = useState<SettingsSectionKey>('overview');
  const [settingsSectionLoaded, setSettingsSectionLoaded] = useState<Record<SettingsSectionKey, boolean>>({
    overview: true,
    org_dna: false,
    tasks: true,
    client_workspace: false,
    topics: false,
    handbook: false,
    system_admin: false,
    org_overview: false,
    org_departments: false,
    org_people: false,
    org_rules: false,
  });
  const [logs, setLogs] = useState<
    Array<{
      id: string;
      actorName: string;
      action: string;
      entityType: string;
      entityId: string;
      detail: Record<string, unknown>;
      createdAt: string;
    }>
  >([]);
  const [organizationDnaModules, setOrganizationDnaModules] = useState<OrganizationDnaModule[]>([]);
  const [orgDnaSavingKey, setOrgDnaSavingKey] = useState<OrganizationDnaModule['moduleKey'] | null>(null);
  const [clientWorkspaceSettingsState, setClientWorkspaceSettingsState] = useState<ClientWorkspaceSettings>(DEFAULT_CLIENT_WORKSPACE_SETTINGS);
  const [topicsSettingsState, setTopicsSettingsState] = useState<TopicsSettings>(DEFAULT_TOPICS_SETTINGS);
  const [handbookSettingsState, setHandbookSettingsState] = useState<HandbookSettings>(DEFAULT_HANDBOOK_SETTINGS);
  const [systemAdminSettingsState, setSystemAdminSettingsState] = useState<SystemAdminSettings>(DEFAULT_SYSTEM_ADMIN_SETTINGS);
  const [orgMembershipState, setOrgMembershipState] = useState<OrgMembershipSummary>(DEFAULT_ORG_MEMBERSHIP_SUMMARY);
  const [orgFeishuIntegrationState, setOrgFeishuIntegrationState] = useState<OrgFeishuIntegration>(DEFAULT_ORG_FEISHU_INTEGRATION);
  const [isSavingOrgFeishuIntegration, setIsSavingOrgFeishuIntegration] = useState(false);
  const [feishuDeliveryProfileState, setFeishuDeliveryProfileState] = useState<FeishuDeliveryProfile>(DEFAULT_FEISHU_DELIVERY_PROFILE);
  const [isSavingFeishuDeliveryProfile, setIsSavingFeishuDeliveryProfile] = useState(false);
  const [orgDingtalkFinanceIntegrationState, setOrgDingtalkFinanceIntegrationState] = useState<OrgDingtalkFinanceIntegration>(DEFAULT_ORG_DINGTALK_FINANCE_INTEGRATION);
  const [isSavingOrgDingtalkFinanceIntegration, setIsSavingOrgDingtalkFinanceIntegration] = useState(false);

  const [clients, setClients] = useState<ClientSummary[]>([]);
  const [currentClientId, setCurrentClientId] = useState<string>('');
  const [workspace, setWorkspace] = useState<ClientWorkspace | null>(null);
  const [growthContextJump, setGrowthContextJump] = useState<GrowthContextJumpRequest | null>(null);
  const hasAppliedInitialTaskViewModeRef = useRef(false);

  useEffect(() => {
    setLatestImportFeedback(null);
  }, [currentClientId]);

  const [tasks, setTasks] = useState<Task[]>([]);
  const [updatingTaskStatusIds, setUpdatingTaskStatusIds] = useState<string[]>([]);
  const [taskLists, setTaskLists] = useState<TaskList[]>([]);
  const [isTaskListsLoading, setIsTaskListsLoading] = useState(false);
  const [taskTags, setTaskTags] = useState<TaskTag[]>([]);
  const [activeSupportRequest, setActiveSupportRequest] = useState<SupportRequestRecord | null>(null);
  const [supportRequestActionBusy, setSupportRequestActionBusy] = useState(false);
  const [supportRequestResolutionNote, setSupportRequestResolutionNote] = useState('');
  const [reviewDashboard, setReviewDashboard] = useState<ReviewDashboard | null>(null);
  const [reviewHistory, setReviewHistory] = useState<ReviewHistoryEntry[]>([]);
  const [isReviewHistoryOpen, setIsReviewHistoryOpen] = useState(false);
  const [isLoadingReviewHistory, setIsLoadingReviewHistory] = useState(false);
  const reviewDirtyTaskIdsRef = useRef<Set<string>>(new Set());
  const [reviewDirtyTaskIds, setReviewDirtyTaskIds] = useState<string[]>([]);
  const [radars, setRadars] = useState<TopicRadar[]>([]);
  const [candidates, setCandidates] = useState<TopicCandidate[]>([]);
  const [handbookEntries, setHandbookEntries] = useState<HandbookEntry[]>([]);

  useEffect(() => {
    setExpandedTaskIds((prev) => prev.filter((taskId) => tasks.some((task) => task.id === taskId)));
  }, [tasks]);

  const mergeTaskListRecords = useCallback((primary: TaskList[], secondary: TaskList[] = []) => {
    const mergedById = new Map<string, TaskList>();
    [...primary, ...secondary].forEach((list) => {
      if (!list?.id) return;
      const existing = mergedById.get(list.id);
      if (!existing) {
        mergedById.set(list.id, list);
        return;
      }
      mergedById.set(list.id, {
        ...existing,
        ...list,
        archivedAt: list.archivedAt ?? existing.archivedAt ?? null,
        scope: list.scope ?? existing.scope ?? 'org',
      });
    });
    const normalizedScope = (scope?: string | null) => {
      const value = (scope || '').trim().toLowerCase();
      return value === 'personal' ? 'personal' : 'org';
    };
    const normalizedName = (name?: string | null) => String(name || '').trim().toLowerCase().split(/\s+/).filter(Boolean).join(' ');
    const mergedByName = new Map<string, TaskList>();
    Array.from(mergedById.values()).forEach((list) => {
      const key = `${normalizedScope(list.scope)}::${normalizedName(list.name) || list.id}`;
      const existing = mergedByName.get(key);
      if (!existing) {
        mergedByName.set(key, list);
        return;
      }
      const existingScore = (existing.isDefault ? 1000 : 0) - (existing.archivedAt ? 100 : 0);
      const nextScore = (list.isDefault ? 1000 : 0) - (list.archivedAt ? 100 : 0);
      if (nextScore > existingScore) {
        mergedByName.set(key, list);
      }
    });
    return Array.from(mergedByName.values());
  }, []);

  const [loading, setLoading] = useState(true);
  const [loadingPhase, setLoadingPhase] = useState('正在初始化桌面界面…');
  const [loadingSubProgress, setLoadingSubProgress] = useState(0);
  const currentSessionUser = authState.user || null;
  const isCloudSession = authState.sessionMode === 'cloud' || !isLocalDeviceSessionUser(currentSessionUser);
  const hasOrganizationTerminologyScope = isCloudSession
    && Boolean(
      ((orgMembershipState.organizationId || currentSessionUser?.organizationId || '') || '')
        .trim()
        .replace(/^local-device$/u, ''),
    );
  const canEditWorkObjectMode = !hasOrganizationTerminologyScope || currentSessionUser?.primaryRole === 'admin';
  const terminology = useMemo(
    () => resolveWorkObjectTerminology(workObjectTerminologyState ?? {
      localMode: settingsState?.localWorkObjectMode ?? null,
      organizationMode: null,
      effectiveMode: settingsState?.localWorkObjectMode ?? 'project',
      source: settingsState?.localWorkObjectMode ? 'local' : 'default',
      lockedByOrganization: false,
      needsOnboarding: false,
      updatedAt: '',
    }),
    [settingsState?.localWorkObjectMode, workObjectTerminologyState],
  );
  useEffect(() => {
    if (typeof window === 'undefined') return;
    (window as typeof window & { __YIYU_DEBUG_AUTH__?: Record<string, unknown> }).__YIYU_DEBUG_AUTH__ = {
      authSessionMode: authState.sessionMode,
      authAuthenticated: authState.authenticated,
      authUserId: authState.user?.id || null,
      authUserEmail: authState.user?.email || null,
      authUserName: authState.user?.fullName || null,
      currentSessionUserId: currentSessionUser?.id || null,
      currentSessionUserEmail: currentSessionUser?.email || null,
      currentSessionUserName: currentSessionUser?.fullName || null,
      inferredIsLocalDeviceUser: isLocalDeviceSessionUser(currentSessionUser),
      inferredIsCloudSession: isCloudSession,
      activeTab,
      taskViewMode,
    };
  }, [activeTab, authState.authenticated, authState.sessionMode, authState.user?.email, authState.user?.fullName, authState.user?.id, currentSessionUser, isCloudSession, taskViewMode]);
  const currentOperatorName = currentSessionUser?.fullName || operators.find((item) => item.isCurrent)?.name || '庆华';
  const canManagePublicTaskTaxonomy = currentSessionUser?.primaryRole === 'admin';
  const [cloudAuthModalOpen, setCloudAuthModalOpen] = useState(false);
  const [cloudAuthMode, setCloudAuthMode] = useState<'login' | 'register'>('login');
  const [cloudAuthForm, setCloudAuthForm] = useState({
    email: '',
    fullName: '',
    password: '',
    confirmPassword: '',
    rememberMe: true,
    rememberInputs: true,
  });
  const [cloudAuthSubmitting, setCloudAuthSubmitting] = useState(false);
  const [cloudAuthMessage, setCloudAuthMessage] = useState('');
  const [cloudAuthShowPassword, setCloudAuthShowPassword] = useState(false);
  const [localInputMemoryState, setLocalInputMemoryState] = useState<LocalInputMemory>(DEFAULT_LOCAL_INPUT_MEMORY);
  const [settingsSidebarCollapsed, setSettingsSidebarCollapsed] = useState(false);
  const [draft, setDraft] = useState({
    currentOperatorId: settingsState?.currentOperatorId || '',
    aiProvider: settingsState?.aiProvider || 'mock',
    aiModel: settingsState?.aiModel || providerDefaultModels.doubao,
    apiKey: '',
  });
  const [rememberAiInputKey, setRememberAiInputKey] = useState(false);
  const [taskSettingsDraft, setTaskSettingsDraft] = useState<TaskSettings>(taskSettingsState || DEFAULT_TASK_SETTINGS);
  const [tagManageDraft, setTagManageDraft] = useState({ name: '', scope: canManagePublicTaskTaxonomy ? 'org' as const : 'self' as const, color: TASK_COLOR_OPTIONS[0] });
  const [editingTagId, setEditingTagId] = useState<string | null>(null);
  const [listManageDraft, setListManageDraft] = useState({
    name: '',
    description: '',
  });
  const [editingListId, setEditingListId] = useState<string | null>(null);
  const [legacyScanResult, setLegacyScanResult] = useState<LegacyScanReport | null>(null);
  const [legacyImportClientId, setLegacyImportClientId] = useState('');
  const [isImportingLegacy, setIsImportingLegacy] = useState(false);
  const [clientWorkspaceDraft, setClientWorkspaceDraft] = useState(clientWorkspaceSettingsState);
  const [topicsDraft, setTopicsDraft] = useState(topicsSettingsState);
  const [handbookDraft, setHandbookDraft] = useState({
    ...handbookSettingsState,
    defaultTagsText: handbookSettingsState.defaultTags.join(', '),
  });
  const [systemAdminDraft, setSystemAdminDraft] = useState(systemAdminSettingsState);
  const [reviewGovernanceDraft, setReviewGovernanceDraft] = useState(reviewGovernanceState);
  const [orgModelDraft, setOrgModelDraft] = useState(orgModelState);
  const [isSavingReviewGovernance, setIsSavingReviewGovernance] = useState(false);
  const [isSavingOrgModel, setIsSavingOrgModel] = useState(false);
  const [isSavingBrandLogo, setIsSavingBrandLogo] = useState(false);
  const [profileDraft, setProfileDraft] = useState<UpdateProfilePayload>({
    fullName: currentSessionUser?.fullName || '',
    email: currentSessionUser?.email || '',
  });
  const [profileSubmitting, setProfileSubmitting] = useState(false);
  const [profileMessage, setProfileMessage] = useState('');
  const [changePwForm, setChangePwForm] = useState({ currentPassword: '', newPassword: '', confirmPassword: '' });
  const [changePwSubmitting, setChangePwSubmitting] = useState(false);
  const [changePwError, setChangePwError] = useState('');
  const [changePwShowPassword, setChangePwShowPassword] = useState(false);
  const [employeeReviewBusyId, setEmployeeReviewBusyId] = useState<string | null>(null);
  const [rejectingEmployeeId, setRejectingEmployeeId] = useState<string | null>(null);
  const [employeeRejectReason, setEmployeeRejectReason] = useState('');
  const [resetPwEmployeeId, setResetPwEmployeeId] = useState<string | null>(null);
  const [resetPwValue, setResetPwValue] = useState('');
  const defaultTagScope: 'org' | 'self' = canManagePublicTaskTaxonomy ? 'org' : 'self';
  const organizationTaskName = resolveOrganizationTaskName(orgModelState.organization.name);
  const organizationClientId = useMemo(() => {
    const match = clients.find((c: ClientSummary) => c.name === organizationTaskName);
    return match?.id || '';
  }, [organizationTaskName, clients]);
  const organizationTaskAutoReason = buildOrganizationTaskAutoReason(organizationTaskName);
  const organizationTaskManualReason = buildOrganizationTaskManualReason(organizationTaskName);
  const effectiveTaskSettings = useMemo(
    () => resolveTaskSettings(taskSettingsState, taskLists),
    [taskSettingsState, taskLists],
  );
  const availableReviewGovernanceMembers = useMemo<ReviewDepartmentMember[]>(() => {
    const deduped = new Map<string, ReviewDepartmentMember>();
    const append = (member: ReviewDepartmentMember) => {
      const fullName = member.fullName.trim();
      if (!fullName) return;
      const key = fullName.toLowerCase();
      if (deduped.has(key)) return;
      deduped.set(key, { id: member.id, fullName, email: member.email || null });
    };
    employeeReviews.forEach((employee) => append({ id: employee.id, fullName: employee.fullName, email: employee.email }));
    operators.forEach((operator) => append({ id: operator.id, fullName: operator.name }));
    tasks.forEach((task) => append({ id: task.ownerId || '', fullName: task.ownerName }));
    if (currentSessionUser) {
      append({ id: currentSessionUser.id, fullName: currentSessionUser.fullName, email: currentSessionUser.email });
    }
    return [...deduped.values()];
  }, [currentSessionUser, employeeReviews, operators, tasks]);

  const startupRetryRef = useRef(0);
  const backendReadyRef = useRef(false);
  const startupLocalServiceErrorGraceUntilRef = useRef(Date.now() + 45000);
  const localServiceBannerProbeInFlightRef = useRef(false);
  const consultationKnowledgeSyncInFlightRef = useRef(false);

  const showBanner = (type: 'success' | 'error' | 'info', text: string) => {
    showGlobalBanner(type, text);
  };

  const flash = (type: 'success' | 'error' | 'info', text: string) => {
    if (type === 'error' && text.includes('无法连接本地服务')) {
      if (backendReadyRef.current || Date.now() < startupLocalServiceErrorGraceUntilRef.current) {
        return;
      }
      if (localServiceBannerProbeInFlightRef.current) {
        return;
      }
      localServiceBannerProbeInFlightRef.current = true;
      void probeLocalBackendHealth(900)
        .then((response) => {
          setHealth(response);
          backendReadyRef.current = true;
          clearLocalServiceStartupBanner();
        })
        .catch(() => {
          showBanner(type, text);
        })
        .finally(() => {
          localServiceBannerProbeInFlightRef.current = false;
        });
      return;
    }
    showBanner(type, text);
  };

  const openCloudAuthModal = (mode: 'login' | 'register' = 'login') => {
    const rememberedCloudAccount =
      (localInputMemoryState.cloudAuth.lastEmail
        ? localInputMemoryState.cloudAuth.accounts.find((account) => account.email === localInputMemoryState.cloudAuth.lastEmail)
        : null)
      || localInputMemoryState.cloudAuth.accounts[0]
      || null;
    setCloudAuthMode(mode);
    setCloudAuthMessage('');
    setCloudAuthShowPassword(false);
    setCloudAuthForm({
      email: rememberedCloudAccount?.email || '',
      fullName: mode === 'register' ? (rememberedCloudAccount?.fullName || '') : '',
      password: rememberedCloudAccount?.password || '',
      confirmPassword: mode === 'register' ? (rememberedCloudAccount?.password || '') : '',
      rememberMe: true,
      rememberInputs: localInputMemoryState.cloudAuth.rememberInputs,
    });
    setCloudAuthModalOpen(true);
  };

  useEffect(() => {
    if (settingsState) {
      setDraft((prev) => ({
        ...prev,
        currentOperatorId: settingsState.currentOperatorId,
        aiProvider: settingsState.aiProvider,
        aiModel: settingsState.aiModel,
      }));
    }
  }, [settingsState]);

  useEffect(() => {
    setDraft((prev) => ({
      ...prev,
      apiKey: localInputMemoryState.aiSettings.rememberApiKey ? localInputMemoryState.aiSettings.apiKey : '',
    }));
    setRememberAiInputKey(localInputMemoryState.aiSettings.rememberApiKey);
  }, [localInputMemoryState.aiSettings.apiKey, localInputMemoryState.aiSettings.rememberApiKey]);

  useEffect(() => {
    setTaskSettingsDraft(effectiveTaskSettings);
  }, [effectiveTaskSettings]);

  useEffect(() => {
    setClientWorkspaceDraft(clientWorkspaceSettingsState);
  }, [clientWorkspaceSettingsState]);

  useEffect(() => {
    setTopicsDraft(topicsSettingsState);
  }, [topicsSettingsState]);

  useEffect(() => {
    setHandbookDraft({
      ...handbookSettingsState,
      defaultTagsText: handbookSettingsState.defaultTags.join(', '),
    });
  }, [handbookSettingsState]);

  useEffect(() => {
    setSystemAdminDraft(systemAdminSettingsState);
  }, [systemAdminSettingsState]);

  useEffect(() => {
    setReviewGovernanceDraft(reviewGovernanceState);
  }, [reviewGovernanceState]);

  useEffect(() => {
    setOrgModelDraft(orgModelState);
  }, [orgModelState]);

  useEffect(() => {
    const preferredClientId =
      (currentClientId && clients.some((client) => client.id === currentClientId) && currentClientId) ||
      clients[0]?.id ||
      '';
    setLegacyImportClientId((prev) => (prev && clients.some((client) => client.id === prev) ? prev : preferredClientId));
  }, [clients, currentClientId]);

  useEffect(() => {
    setProfileDraft({
      fullName: currentSessionUser?.fullName || '',
      email: currentSessionUser?.email || '',
    });
    setProfileMessage('');
  }, [currentSessionUser?.email, currentSessionUser?.fullName]);

  const markLoadingPhase = (phase: string) => {
    setLoadingPhase(phase);
    console.info(`[bootstrap] phase=${phase}`);
  };

  const isLocalServiceStartupError = (error: unknown) => {
    const detail = error instanceof Error ? error.message : String(error ?? '');
    return detail.includes('无法连接本地服务');
  };

  const clearLocalServiceStartupBanner = () => {
    const currentBanner = getGlobalBanner();
    if (!currentBanner || currentBanner.type !== 'error' || !currentBanner.text.includes('无法连接本地服务')) return;
    clearGlobalBanner();
  };

  useEffect(() => {
    if (health?.backend === 'online') {
      backendReadyRef.current = true;
      clearLocalServiceStartupBanner();
    }
  }, [health?.backend, health?.startedAt]);

  async function refreshCollabStatus(nextRepoPath = collabRepoPath) {
    setIsCollabStatusLoading(true);
    try {
      const requestedRepoPath = normalizeInitialCollabRepoPath(nextRepoPath);
      const nextStatus = await getCollabRepoStatus(requestedRepoPath);
      const normalizedStatus: CollabRepoStatus = {
        ...nextStatus,
        repoPath: normalizeInitialCollabRepoPath(nextStatus.repoPath),
        suggestedRepoPath: normalizeInitialCollabRepoPath(nextStatus.suggestedRepoPath || null),
        workingRepoPath: normalizeInitialCollabRepoPath(nextStatus.workingRepoPath || null),
      };
      setCollabStatus(normalizedStatus);
      if (normalizedStatus.repoPath && normalizedStatus.repoPath !== requestedRepoPath && normalizedStatus.isValid) {
        setCollabRepoPath(normalizedStatus.repoPath);
      }
      return normalizedStatus;
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '源码仓库状态加载失败');
      return null;
    } finally {
      setIsCollabStatusLoading(false);
    }
  }

  function getDefaultCollabSelectedPaths(state: Exclude<CollabDialogState, null>) {
    return state.preview.files
      .filter((file) => !file.risk || !['overlap', 'delete_replace'].includes(file.risk.kind))
      .map((file) => file.path);
  }

  function openCollabDialog(state: Exclude<CollabDialogState, null>) {
    setCollabDialogState(state);
    setCollabSelectedPaths(getDefaultCollabSelectedPaths(state));
    setCollabCommitMessage(state.preview.suggestedMessage);
    setCollabDialogError(null);
  }

  async function ensureCollabRepoForAction() {
    if (collabStatus?.isConfigured && collabStatus.isValid && !collabStatus.isMainBranch && collabStatus.suggestedRepoPath) {
      setCollabRepoPath(collabStatus.suggestedRepoPath);
      return collabStatus.suggestedRepoPath;
    }
    if (collabStatus?.repoPath && collabStatus.isValid) {
      if (collabStatus.repoPath !== collabRepoPath) {
        setCollabRepoPath(collabStatus.repoPath);
      }
      return collabStatus.repoPath;
    }
    if (collabStatus?.suggestedRepoPath) {
      setCollabRepoPath(collabStatus.suggestedRepoPath);
      return collabStatus.suggestedRepoPath;
    }
    const nextRepoPath = normalizeInitialCollabRepoPath(await selectCollabRepoBridge());
    if (!nextRepoPath) return null;
    setCollabRepoPath(nextRepoPath);
    setCollabDialogState(null);
    setCollabSelectedPaths([]);
    setCollabCommitMessage('');
    setCollabDialogError(null);
    flash('success', '源码目录已绑定，后续协作按钮会围绕这个仓库工作。');
    return nextRepoPath;
  }

  async function handlePreviewPush() {
    const repoPath = await ensureCollabRepoForAction();
    if (!repoPath) {
      return;
    }
    setCollabBusyAction('push');
    try {
      const preview = await previewPushToMain(repoPath);
      openCollabDialog({ mode: 'push', preview });
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '推送预览失败');
    } finally {
      setCollabBusyAction(null);
    }
  }

  async function handlePreviewPull() {
    const repoPath = await ensureCollabRepoForAction();
    if (!repoPath) {
      return;
    }
    setCollabBusyAction('pull');
    try {
      const preview = await previewPullFromMain(repoPath);
      openCollabDialog({ mode: 'pull', preview });
    } catch (error) {
      flash('error', error instanceof Error ? error.message : '同步预览失败');
    } finally {
      setCollabBusyAction(null);
    }
  }

  function toggleCollabPath(targetPath: string) {
    setCollabDialogError(null);
    setCollabSelectedPaths((prev) => (
      prev.includes(targetPath) ? prev.filter((item) => item !== targetPath) : [...prev, targetPath]
    ));
  }

  function toggleCollabEffectPaths(targetPaths: string[]) {
    setCollabDialogError(null);
    const nextPaths = Array.from(new Set(targetPaths));
    if (!nextPaths.length) return;
    setCollabSelectedPaths((prev) => {
      const prevSet = new Set(prev);
      const allSelected = nextPaths.every((targetPath) => prevSet.has(targetPath));
      if (allSelected) {
        return prev.filter((targetPath) => !nextPaths.includes(targetPath));
      }
      const merged = new Set(prev);
      nextPaths.forEach((targetPath) => merged.add(targetPath));
      return Array.from(merged);
    });
  }

  async function handleConfirmCollabAction() {
    if (!collabDialogState) return;
    const repoPath = collabRepoPath || collabStatus?.repoPath;
    if (!repoPath) {
      setCollabDialogError('还没有绑定源码目录。');
      return;
    }
    const mode = collabDialogState.mode;
    setCollabDialogError(null);
    setCollabBusyAction(mode);
    try {
      if (mode === 'push') {
        await commitAndPushToMain({
          repoPath,
          selectedPaths: collabSelectedPaths,
          confirmedRiskPaths: [],
          message: collabCommitMessage.trim() || collabDialogState.preview.suggestedMessage,
        });
        flash('success', '已提交并推送到 main。');
      } else {
        await pullSelectedFromMain({
          repoPath,
          selectedPaths: collabSelectedPaths,
          confirmedRiskPaths: [],
          message: collabCommitMessage.trim() || collabDialogState.preview.suggestedMessage,
        });
        flash('success', '已把勾选的 main 修改同步到本地源码。');
      }
      setCollabDialogState(null);
      setCollabSelectedPaths([]);
      setCollabCommitMessage('');
      setCollabDialogError(null);
      await refreshCollabStatus(repoPath);
      if (mode === 'pull') {
        await loadSystemAdminSettingsBlock(currentSessionUser?.primaryRole === 'admin');
        const shouldRebuild = window.confirm('源码已经同步完成。要不要继续自动更新本机安装版？');
        if (shouldRebuild) {
          setCollabBusyAction('rebuild');
          await rebuildAndInstallFromRepo(repoPath);
        }
      }
    } catch (error) {
      setCollabDialogError(error instanceof Error ? error.message : '协作操作失败');
      await refreshCollabStatus(repoPath);
    } finally {
      setCollabBusyAction(null);
    }
  }

  function handleCollabMessageChange(nextValue: string) {
    setCollabDialogError(null);
    setCollabCommitMessage(nextValue);
  }

  async function loadSettingsBlock() {
    const response = await getSettings();
    setSettingsState(response.settings);
    setOperators(response.operators);
    setHealth(response.health);
    clearLocalServiceStartupBanner();
    const missingFeatures = REQUIRED_BACKEND_FEATURES.filter((feature) => !response.health.featureFlags.includes(feature));
    setBackendCompatibilityError(
      missingFeatures.length > 0 ? `本地后端版本过旧，请重启应用。缺少能力：${missingFeatures.join('、')}` : null,
    );
  }

  async function loadWorkObjectTerminologyBlock() {
    const response = await getWorkObjectTerminology();
    setWorkObjectTerminologyState(response);
    return response;
  }

  async function loadLocalInputMemoryBlock() {
    const response = await getLocalInputMemory();
    setLocalInputMemoryState(response);
    return response;
  }

  async function loadOrgMembershipBlock() {
    const response = await getOrgMembershipSummary();
    setOrgMembershipState(response);
    return response;
  }

  async function loadOrgFeishuIntegrationBlock() {
    const response = await getOrgFeishuIntegration();
    setOrgFeishuIntegrationState(response);
    return response;
  }

  async function loadFeishuDeliveryProfileBlock() {
    const response = await getFeishuDeliveryProfile();
    setFeishuDeliveryProfileState(response);
    return response;
  }

  async function loadOrgDingtalkFinanceIntegrationBlock() {
    const response = await getOrgDingtalkFinanceIntegration();
    setOrgDingtalkFinanceIntegrationState(response);
    return response;
  }

  async function loadTaskSettingsBlock() {
    const response = await getTaskSettings();
    setTaskSettingsState(response);
    return response;
  }

  async function loadReviewGovernanceSettingsBlock() {
    const response = await getReviewGovernanceSettings();
    setReviewGovernanceState(response);
    return response;
  }

  async function loadOrgModelBlock() {
    const response = await getOrgModelProfile();
    setOrgModelState(response);
    return response;
  }

  async function loadOrganizationDnaBlock() {
    const response = await getOrganizationDna();
    setOrganizationDnaModules(response.modules);
    return response.modules;
  }

  async function loadClientWorkspaceSettingsBlock() {
    const response = await getClientWorkspaceSettings();
    setClientWorkspaceSettingsState(response);
    return response;
  }

  async function loadTopicsSettingsBlock() {
    const response = await getTopicsSettings();
    setTopicsSettingsState(response);
    return response;
  }

  async function loadHandbookSettingsBlock() {
    const response = await getHandbookSettings();
    setHandbookSettingsState(response);
    return response;
  }

  async function loadSystemAdminSettingsBlock(includeOrgModel = authState.sessionMode === 'cloud') {
    const [response, orgModel] = await Promise.all([
      getSystemAdminSettings(),
      includeOrgModel ? getOrgModelProfile() : Promise.resolve(EMPTY_ORG_MODEL_SETTINGS),
    ]);
    setSystemAdminSettingsState(response);
    setOrgModelState(orgModel);
    return response;
  }

  async function loadSettingsSectionBlock(section: SettingsSectionKey, force = false) {
    if (!force && settingsSectionLoaded[section]) return;
    switch (section) {
      case 'overview':
        break;
      case 'org_dna':
        await loadOrganizationDnaBlock();
        break;
      case 'tasks':
        await loadTaskSettingsBlock();
        if (currentSessionUser?.primaryRole === 'admin') {
          await loadReviewGovernanceSettingsBlock();
        }
        break;
      case 'client_workspace':
        await loadClientWorkspaceSettingsBlock();
        break;
      case 'topics':
        await loadTopicsSettingsBlock();
        break;
      case 'handbook':
        await loadHandbookSettingsBlock();
        break;
      case 'system_admin':
      case 'org_overview':
      case 'org_departments':
      case 'org_people':
      case 'org_rules':
        await loadSystemAdminSettingsBlock(authState.sessionMode === 'cloud');
        break;
    }
    setSettingsSectionLoaded((prev) => ({ ...prev, [section]: true }));
  }

  async function loadAuthBlock() {
    const response = normalizeAuthStateForDesktop(await getAuthState());
    setAuthState(response);
    return response;
  }

  async function probeLocalBackendHealth(probeTimeoutMs = 1800) {
    return await new Promise<HealthResponse>((resolve, reject) => {
      const timer = window.setTimeout(() => {
        reject(new Error('local-backend-health-timeout'));
      }, probeTimeoutMs);
      void getHealth()
        .then((response) => {
          window.clearTimeout(timer);
          resolve(response);
        })
        .catch((error) => {
          window.clearTimeout(timer);
          reject(error);
        });
    });
  }

  async function waitForLocalBackendReady(timeoutMs = 25000) {
    if (backendReadyRef.current) {
      return;
    }
    const startedAt = Date.now();
    let lastError: unknown = null;
    while (Date.now() - startedAt < timeoutMs) {
      try {
        const response = await probeLocalBackendHealth();
        setHealth(response);
        backendReadyRef.current = true;
        clearLocalServiceStartupBanner();
        return;
      } catch (error) {
        lastError = error;
        const detail = error instanceof Error ? error.message : String(error ?? '');
        console.warn(`[bootstrap] local backend probe failed: ${detail || 'unknown'}`);
        await new Promise((resolve) => window.setTimeout(resolve, 500));
      }
    }
    console.warn(
      `[bootstrap] local backend probe timed out after ${timeoutMs}ms, continuing startup`,
      lastError,
    );
  }

  async function loadDepartmentOptionsBlock() {
    const response = await getDepartmentOptions();
    setDepartmentOptions(response);
    return response;
  }

  async function loadEmployeeReviewBlock() {
    const response = await getEmployees();
    setEmployeeReviews(response);
    return response;
  }

  async function loadLogsBlock() {
    setLogs(await getActivityLogs());
  }

  async function loadClientBlock(nextClientId?: string) {
    const clientItems = await getClients();
    console.info(`[bootstrap] loadClientBlock fetched clients=${clientItems.length}`);
    setClients(clientItems);
    const preferredClientId =
      (nextClientId && clientItems.some((item) => item.id === nextClientId) && nextClientId) ||
      (currentClientId && clientItems.some((item) => item.id === currentClientId) && currentClientId) ||
      clientItems[0]?.id ||
      '';
    const targetClientId = preferredClientId;
    if (targetClientId) {
      setCurrentClientId(targetClientId);
      console.info(`[bootstrap] loadClientBlock selecting client=${targetClientId}`);
      try {
        setWorkspace(await getClientWorkspace(targetClientId));
      } catch (error) {
        console.error('[bootstrap] loadClientBlock workspace fetch failed', error);
        setWorkspace(null);
        flash('error', error instanceof Error ? error.message : `${terminology.workspaceLabel}加载失败`);
      }
    } else {
      console.warn('[bootstrap] loadClientBlock found no selectable client');
      setCurrentClientId('');
      setWorkspace(null);
    }
    clearLocalServiceStartupBanner();
  }

  async function loadTaskBlock() {
    const response = await getTaskBoard();
    let mergedLists = response.lists;
    try {
      const library = await getTaskLists();
      mergedLists = mergeTaskListRecords(library.lists || [], response.lists || []);
    } catch {
      mergedLists = mergeTaskListRecords(response.lists || []);
    }
    setTasks(response.tasks);
    setTaskLists(mergedLists);
    setTaskTags([]);
    return {
      ...response,
      lists: mergedLists,
    };
  }

  const refreshTaskListLibrary = useCallback(async () => {
    setIsTaskListsLoading(true);
    try {
      const response = await getTaskLists();
      setTaskLists((prev) => mergeTaskListRecords(response.lists || [], prev));
      return response.lists || [];
    } finally {
      setIsTaskListsLoading(false);
    }
  }, [mergeTaskListRecords]);

  function resetCloudBoundTaskViews() {
    setTasks([]);
    setReviewDashboard(null);
    setReviewHistory([]);
  }

  async function loadAgentWorklogBlock(monthLabel: string) {
    const response = await getAgentWorklogs(monthLabel);
    setAgentWorklogs(response.worklogs);
    setAgentWeeklyDigests(response.weeklyDigests);
    setAgentWeeklyPlans(response.weeklyPlans);
    return response;
  }

  async function loadReviewBlock(weekLabel?: string) {
    const response = await getReviews(weekLabel);
    setReviewDashboard(response);
    return response;
  }

  async function loadReviewHistoryBlock() {
    setIsLoadingReviewHistory(true);
    try {
      const response = await getReviewHistory();
      setReviewHistory(response.items);
      return response.items;
    } finally {
      setIsLoadingReviewHistory(false);
    }
  }

  async function loadTopicsBlock() {
    const response = await getTopics();
    setRadars(response.radars);
    setCandidates(response.candidates);
    return response;
  }

  async function loadHandbookBlock() {
    const response = await getHandbook();
    setHandbookEntries(response.entries);
  }

  async function loadAll(nextClientId?: string, options?: { allowStartupRetry?: boolean }) {
    setLoading(true);
    markLoadingPhase('正在连接本地后端…');
    let keepLoadingForRetry = false;
    try {
      await waitForLocalBackendReady();
      markLoadingPhase('正在恢复登录状态…');
      const nextAuth = await loadAuthBlock();
      try {
        markLoadingPhase('正在读取系统设置…');
        await loadSettingsBlock();
        await loadWorkObjectTerminologyBlock();
        await loadLocalInputMemoryBlock();
      } catch (settingsError) {
        if (isLocalServiceStartupError(settingsError)) {
          window.setTimeout(() => {
            void Promise.all([loadSettingsBlock(), loadWorkObjectTerminologyBlock(), loadLocalInputMemoryBlock()]).catch(() => undefined);
          }, 1500);
        } else {
          flash('error', settingsError instanceof Error ? settingsError.message : '系统设置加载失败');
        }
      }
      if (nextAuth.authenticated) {
        markLoadingPhase('正在载入核心模块数据…');
        const backgroundLoaders: Array<{ name: string; run: () => Promise<unknown> }> = [
          { name: 'task-settings', run: () => loadTaskSettingsBlock() },
          { name: 'activity-logs', run: () => loadLogsBlock() },
          { name: 'task-board', run: () => loadTaskBlock() },
          {
            name: 'agent-worklogs',
            run: () => (nextAuth.user?.primaryRole === 'admin' ? loadAgentWorklogBlock(taskCalendarMonthLabel) : Promise.resolve()),
          },
          { name: 'reviews', run: () => loadReviewBlock() },
          { name: 'topics', run: () => loadTopicsBlock() },
          { name: 'handbook', run: () => loadHandbookBlock() },
          {
            name: 'org-membership',
            run: () =>
              loadOrgMembershipBlock().catch(() => {
                setOrgMembershipState(DEFAULT_ORG_MEMBERSHIP_SUMMARY);
                return DEFAULT_ORG_MEMBERSHIP_SUMMARY;
              }),
          },
          {
            name: 'org-feishu-integration',
            run: () =>
              loadOrgFeishuIntegrationBlock().catch(() => {
                setOrgFeishuIntegrationState(DEFAULT_ORG_FEISHU_INTEGRATION);
                return DEFAULT_ORG_FEISHU_INTEGRATION;
              }),
          },
          {
            name: 'feishu-delivery-profile',
            run: () =>
              loadFeishuDeliveryProfileBlock().catch(() => {
                setFeishuDeliveryProfileState(DEFAULT_FEISHU_DELIVERY_PROFILE);
                return DEFAULT_FEISHU_DELIVERY_PROFILE;
              }),
          },
          {
            name: 'org-dingtalk-finance-integration',
            run: () =>
              loadOrgDingtalkFinanceIntegrationBlock().catch(() => {
                setOrgDingtalkFinanceIntegrationState(DEFAULT_ORG_DINGTALK_FINANCE_INTEGRATION);
                return DEFAULT_ORG_DINGTALK_FINANCE_INTEGRATION;
              }),
          },
          {
            name: 'system-admin-settings',
            run: () => loadSystemAdminSettingsBlock(nextAuth.sessionMode === 'cloud'),
          },
          {
            name: 'review-governance',
            run: () => (nextAuth.user?.primaryRole === 'admin' ? loadReviewGovernanceSettingsBlock() : Promise.resolve()),
          },
        ];
        let completedCount = 0;
        const totalCount = backgroundLoaders.length;
        const failedBackgroundBlocks = (
          await Promise.all(
            backgroundLoaders.map(async ({ name, run }) => {
              try {
                await run();
                console.info(`[bootstrap] ${name} loaded`);
                return null;
              } catch (error) {
                console.error(`[bootstrap] ${name} failed`, error);
                return name;
              } finally {
                completedCount += 1;
                setLoadingSubProgress(Math.round((completedCount / totalCount) * 100));
              }
            }),
          )
        ).filter((item): item is string => Boolean(item));
        setLoadingSubProgress(0);
        if (nextAuth.user?.primaryRole !== 'admin') {
          setAgentWorklogs([]);
          setAgentWeeklyDigests([]);
          setAgentWeeklyPlans([]);
        }
        markLoadingPhase(`正在载入${terminology.workspaceLabel}…`);
        await loadClientBlock(nextClientId);
        if (failedBackgroundBlocks.length > 0) {
          flash('error', `部分模块加载失败：${failedBackgroundBlocks.join('、')}`);
        }
        setSettingsSectionLoaded({
          overview: true,
          org_dna: false,
          tasks: true,
          client_workspace: false,
          topics: false,
          handbook: false,
          system_admin: false,
          org_overview: false,
          org_departments: false,
          org_people: false,
          org_rules: false,
        });
        if (nextAuth.user?.primaryRole === 'admin') {
          markLoadingPhase('正在读取员工与组织数据…');
          await loadEmployeeReviewBlock();
        } else {
          setEmployeeReviews([]);
          setReviewGovernanceState(EMPTY_REVIEW_GOVERNANCE_SETTINGS);
        }
      } else {
        markLoadingPhase('正在切换到登录态…');
        setClients([]);
        setWorkspace(null);
        setTasks([]);
        setTaskLists([]);
        setTaskTags([]);
        setTaskSettingsState(null);
        setReviewGovernanceState(EMPTY_REVIEW_GOVERNANCE_SETTINGS);
        setOrgModelState(EMPTY_ORG_MODEL_SETTINGS);
        setAgentWorklogs([]);
        setAgentWeeklyDigests([]);
        setAgentWeeklyPlans([]);
        setReviewDashboard(null);
        setRadars([]);
        setCandidates([]);
        setHandbookEntries([]);
        setLogs([]);
        setEmployeeReviews([]);
        setOrganizationDnaModules([]);
        setClientWorkspaceSettingsState(DEFAULT_CLIENT_WORKSPACE_SETTINGS);
        setTopicsSettingsState(DEFAULT_TOPICS_SETTINGS);
        setHandbookSettingsState(DEFAULT_HANDBOOK_SETTINGS);
        setSystemAdminSettingsState(DEFAULT_SYSTEM_ADMIN_SETTINGS);
        setOrgMembershipState(DEFAULT_ORG_MEMBERSHIP_SUMMARY);
        setOrgFeishuIntegrationState(DEFAULT_ORG_FEISHU_INTEGRATION);
        setFeishuDeliveryProfileState(DEFAULT_FEISHU_DELIVERY_PROFILE);
        setOrgDingtalkFinanceIntegrationState(DEFAULT_ORG_DINGTALK_FINANCE_INTEGRATION);
        setSettingsSectionLoaded({
          overview: true,
          org_dna: false,
          tasks: true,
          client_workspace: false,
          topics: false,
          handbook: false,
          system_admin: false,
          org_overview: false,
          org_departments: false,
          org_people: false,
          org_rules: false,
        });
      }
      startupRetryRef.current = 0;
      clearLocalServiceStartupBanner();
      markLoadingPhase('启动完成');
    } catch (error) {
      const message = error instanceof Error ? error.message : '加载失败';
      markLoadingPhase(`启动受阻：${message}`);
      const allowStartupRetry = options?.allowStartupRetry ?? true;
      if (allowStartupRetry && isLocalServiceStartupError(error) && startupRetryRef.current < 2) {
        startupRetryRef.current += 1;
        keepLoadingForRetry = true;
        window.setTimeout(() => {
          void loadAll(nextClientId, { allowStartupRetry: true });
        }, 1200);
      } else {
        flash('error', message);
      }
    } finally {
      if (!keepLoadingForRetry) {
        setLoading(false);
      }
    }
  }

  const handleCloudAuthSubmit = async () => {
    setCloudAuthSubmitting(true);
    setCloudAuthMessage('');
    try {
      if (cloudAuthMode === 'register') {
        const response = await register({
          email: cloudAuthForm.email,
          fullName: cloudAuthForm.fullName,
          password: cloudAuthForm.password,
        });
        setAuthState(response);
      } else {
        const response = await login({
          email: cloudAuthForm.email,
          password: cloudAuthForm.password,
          rememberMe: cloudAuthForm.rememberMe,
        });
        setAuthState(response);
      }
      try {
        const nextLocalInputMemory = await saveCloudAuthInputMemory({
          rememberInputs: cloudAuthForm.rememberInputs,
          email: cloudAuthForm.email,
          fullName: cloudAuthForm.fullName,
          password: cloudAuthForm.password,
        });
        setLocalInputMemoryState(nextLocalInputMemory);
      } catch (memoryError) {
        console.warn('[cloud-auth] save local input memory failed', memoryError);
      }
      await loadAll();
      setCloudAuthForm({
        email: '',
        fullName: '',
        password: '',
        confirmPassword: '',
        rememberMe: true,
        rememberInputs: localInputMemoryState.cloudAuth.rememberInputs,
      });
      setCloudAuthMessage('');
      setCloudAuthModalOpen(false);
    } catch (error) {
      setCloudAuthMessage(error instanceof Error ? error.message : '提交失败');
    } finally {
      setCloudAuthSubmitting(false);
    }
  };

  useEffect(() => {
    void loadDepartmentOptionsBlock().catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!isCloudSession) return;
    setCloudAuthModalOpen(false);
    setCloudAuthMessage('');
    setCloudAuthForm({
      email: '',
      fullName: '',
      password: '',
      confirmPassword: '',
      rememberMe: true,
      rememberInputs: localInputMemoryState.cloudAuth.rememberInputs,
    });
  }, [isCloudSession]);

  useEffect(() => {
    void window.yiyuWorkbench.getDesktopAppInfo().then(setDesktopAppInfo).catch(() => undefined);
  }, []);

  async function refreshWorkspace(clientId?: string) {
    const targetClientId = clientId ?? currentClientId;
    if (!targetClientId) return;
    const nextWorkspace = await getClientWorkspace(targetClientId);
    setWorkspace(nextWorkspace);
    return nextWorkspace;
  }

  const requestGrowthContextJump = (context: GrowthContextLink) => {
    const normalizedTab = (context.tab === 'growth' ? 'growth_handbook' : context.tab) as NavKey | string;
    if (
      normalizedTab === 'tasks'
      || normalizedTab === 'client_workspace'
      || normalizedTab === 'strategic_accompaniment'
      || normalizedTab === 'topics_management'
      || normalizedTab === 'growth_handbook'
      || normalizedTab === 'settings'
    ) {
      setActiveTab(normalizedTab as NavKey);
    }
    setGrowthContextJump({ requestId: createUiId('growth-context'), context });
  };

  const consumeGrowthContextJump = (requestId: string) => {
    setGrowthContextJump((prev) => (prev?.requestId === requestId ? null : prev));
  };

  useEffect(() => {
    const targetClientId = currentClientId;
    if (!targetClientId) {
      setIsImportSubmitting(false);
      return;
    }
    const activeKnowledgeJobs = (workspace?.knowledgeStatus?.pendingJobs || 0) + (workspace?.knowledgeStatus?.runningJobs || 0);
    if (!isImportSubmitting && activeKnowledgeJobs === 0) return;
    let cancelled = false;
    const pollWorkspace = async () => {
      try {
        const nextWorkspace = await refreshWorkspace(targetClientId);
        if (cancelled || !nextWorkspace) return;
        const nextActiveJobs = (nextWorkspace.knowledgeStatus?.pendingJobs || 0) + (nextWorkspace.knowledgeStatus?.runningJobs || 0);
        if (nextActiveJobs === 0 && Date.now() >= importProgressHoldUntilRef.current) {
          setIsImportSubmitting(false);
        }
      } catch {
        if (!cancelled && Date.now() >= importProgressHoldUntilRef.current) {
          setIsImportSubmitting(false);
        }
      }
    };
    void pollWorkspace();
    const timer = window.setInterval(() => {
      void pollWorkspace();
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [
    currentClientId,
    isImportSubmitting,
    workspace?.knowledgeStatus?.pendingJobs,
    workspace?.knowledgeStatus?.runningJobs,
  ]);

  useEffect(() => {
    void loadAll();
  }, []);

  useEffect(() => {
    if (hasAppliedInitialTaskViewModeRef.current) return;
    if (taskSettingsState?.defaultViewMode) {
      setTaskViewMode(taskSettingsState.defaultViewMode === 'list' ? 'calendar' : taskSettingsState.defaultViewMode);
      hasAppliedInitialTaskViewModeRef.current = true;
    }
  }, [taskSettingsState?.defaultViewMode]);

  useEffect(() => {
    if (taskViewMode === 'agent_schedule') {
      setTaskViewMode('calendar');
    }
  }, [taskViewMode]);

  useEffect(() => {
    if (activeTab !== 'tasks') return;
    const viewport = taskViewportRef.current;
    if (!viewport) return;
    const reset = () => viewport.scrollTo({ top: 0, behavior: 'auto' });
    reset();
    const raf = window.requestAnimationFrame(reset);
    return () => window.cancelAnimationFrame(raf);
  }, [activeTab, taskViewMode]);

  useEffect(() => {
    if (activeTab !== 'tasks' || !authState.authenticated || currentSessionUser?.primaryRole !== 'admin') return;
    void loadAgentWorklogBlock(taskCalendarMonthLabel).catch(() => {
      setAgentWorklogs([]);
      setAgentWeeklyDigests([]);
      setAgentWeeklyPlans([]);
    });
  }, [activeTab, authState.authenticated, currentSessionUser?.primaryRole, taskCalendarMonthLabel]);

  useEffect(() => {
    if (activeTab !== 'settings' || !authState.authenticated) return;
    void loadSettingsSectionBlock(settingsSection).catch((error) => {
      flash('error', error instanceof Error ? error.message : '系统设置加载失败');
    });
  }, [activeTab, settingsSection, authState.authenticated]);

  useEffect(() => {
    if (!authState.authenticated) return;
    let cancelled = false;

    const run = async () => {
      if (consultationKnowledgeSyncInFlightRef.current) return;
      consultationKnowledgeSyncInFlightRef.current = true;
      try {
        const summary = await processPendingConsultationKnowledgeRequests();
        if (!cancelled && summary.processedCount > 0) {
          console.info(
            `[consultation-knowledge] processed=${summary.processedCount} completed=${summary.completedCount} failed=${summary.failedCount}`,
          );
          const touchedCurrentClient = Boolean(
            currentClientId && summary.items.some((item) => item.clientId === currentClientId),
          );
          if (touchedCurrentClient) {
            await refreshWorkspace(currentClientId).catch(() => undefined);
          }
        }
      } catch (error) {
        if (!cancelled) {
          console.warn('[consultation-knowledge] pending sync failed', error);
        }
      } finally {
        consultationKnowledgeSyncInFlightRef.current = false;
      }
    };

    void run();
    const timer = window.setInterval(() => {
      void run();
    }, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [authState.authenticated, currentClientId, currentSessionUser?.id]);

    const normalizeTaskListScope = (scope?: string | null) => {
      const normalized = (scope || '').trim().toLowerCase();
      return normalized === 'personal' ? 'personal' : 'org';
    };
    const activeTaskLists = taskLists.filter((item) => !item.archivedAt);
    const orgTaskLists = activeTaskLists.filter((item) => normalizeTaskListScope(item.scope) === 'org');
    const personalTaskLists = activeTaskLists.filter((item) => normalizeTaskListScope(item.scope) === 'personal');
    const resolveDefaultListId = (scope: 'org' | 'personal') => {
      const listPool = scope === 'personal' ? personalTaskLists : orgTaskLists;
      return listPool.find((item) => item.isDefault)?.id || listPool[0]?.id || '';
    };
    const seededOrgListsRef = useRef(false);
    const orgListBootstrapRef = useRef<Promise<TaskList | null> | null>(null);

    const ensureOrgTaskList = async () => {
      if (orgTaskLists.length > 0) {
        return orgTaskLists.find((item) => item.isDefault) || orgTaskLists[0] || null;
      }
      if (!orgListBootstrapRef.current) {
        orgListBootstrapRef.current = (async () => {
          const created = await createTaskList({
            name: '组织任务',
            color: '#5B7BFE',
            isDefault: true,
            scope: 'org',
          });
          await loadTaskBlock();
          return created;
        })()
          .finally(() => {
            orgListBootstrapRef.current = null;
          });
      }
      return orgListBootstrapRef.current;
    };

    useEffect(() => {
      if (seededOrgListsRef.current) return;
      if (!currentSessionUser?.id) return;
      if (orgTaskLists.length > 0) {
        seededOrgListsRef.current = true;
        return;
      }
      seededOrgListsRef.current = true;
      void ensureOrgTaskList().catch(() => {
        seededOrgListsRef.current = false;
      });
    }, [currentSessionUser?.id, orgTaskLists.length]);

  const activeTaskTags = useMemo(
    () => taskTags.filter((item) => !item.archivedAt),
    [taskTags],
  );

  useEffect(() => {
    window.localStorage.setItem('yiyu-sidebar-collapsed', isSidebarCollapsed ? '1' : '0');
  }, [isSidebarCollapsed]);

  useEffect(() => {
    const normalizedRepoPath = normalizeInitialCollabRepoPath(collabRepoPath);
    if (normalizedRepoPath !== collabRepoPath) {
      setCollabRepoPath(normalizedRepoPath);
    }
  }, [collabRepoPath]);

  useEffect(() => {
    if (collabRepoPath) {
      window.localStorage.setItem(COLLAB_REPO_PATH_STORAGE_KEY, collabRepoPath);
      return;
    }
    window.localStorage.removeItem(COLLAB_REPO_PATH_STORAGE_KEY);
  }, [collabRepoPath]);

  useEffect(() => {
    void refreshCollabStatus(collabRepoPath);
  }, [collabRepoPath]);

  useEffect(() => {
    const suggestedRepoPath = normalizeInitialCollabRepoPath(collabStatus?.suggestedRepoPath || null);
    if (!suggestedRepoPath) return;
    const normalizedCurrentRepoPath = normalizeInitialCollabRepoPath(collabRepoPath);
    const shouldSwitchToSuggested =
      !normalizedCurrentRepoPath
      || normalizedCurrentRepoPath !== collabRepoPath
      || (collabStatus?.isConfigured && !collabStatus.isMainBranch && suggestedRepoPath !== normalizedCurrentRepoPath);
    if (!shouldSwitchToSuggested) return;
    if (collabAutoSwitchTargetRef.current === suggestedRepoPath && normalizedCurrentRepoPath === suggestedRepoPath) return;
    collabAutoSwitchTargetRef.current = suggestedRepoPath;
    const switchingFrom = normalizedCurrentRepoPath;
    setCollabRepoPath(suggestedRepoPath);
    if (switchingFrom && switchingFrom !== suggestedRepoPath) {
      flash('info', '协作源码目录已切换到 main 基线仓库。');
    }
  }, [collabRepoPath, collabStatus]);

  useEffect(() => {
    if (activeTab !== 'topics_management') return undefined;
    if (!candidates.some((candidate) => candidate.insightStatus === 'pending')) return undefined;
    const timer = window.setInterval(() => {
      void loadTopicsBlock().catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [activeTab, candidates]);

  const navItems = [
    { id: 'tasks' as const, label: '任务与日程', icon: CheckSquare },
    { id: 'client_workspace' as const, label: terminology.workspaceLabel, icon: Briefcase },
    { id: 'strategic_accompaniment' as const, label: '战略陪伴', icon: Target },
    { id: 'topics_management' as const, label: '资讯情报站', icon: Newspaper },
    { id: 'growth_handbook' as const, label: '成长中心', icon: BookOpen },
    { id: 'settings' as const, label: '系统设置', icon: Settings },
  ];

  const AuthShell = () => {
    const rememberedAccounts = localInputMemoryState.cloudAuth.accounts;
    const defaultRememberedAccount =
      (localInputMemoryState.cloudAuth.lastEmail
        ? rememberedAccounts.find((account) => account.email === localInputMemoryState.cloudAuth.lastEmail)
        : null)
      || rememberedAccounts[0]
      || null;
    const createEmptyForm = (email = '', fullName = '', password = '') => ({
      email,
      fullName,
      password,
      confirmPassword: password,
    });
    const [mode, setMode] = useState<'login' | 'register'>('login');
    const [form, setForm] = useState(() => createEmptyForm(defaultRememberedAccount?.email || '', defaultRememberedAccount?.fullName || '', defaultRememberedAccount?.password || ''));
    const [rememberMe, setRememberMe] = useState(true);
    const [rememberInputs, setRememberInputs] = useState(localInputMemoryState.cloudAuth.rememberInputs);
    const [showPassword, setShowPassword] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [message, setMessage] = useState(authState.message || '');

    const switchMode = (nextMode: 'login' | 'register') => {
      setMode(nextMode);
      setMessage('');
      if (nextMode === 'register') {
        setForm(createEmptyForm(form.email, form.fullName, form.password));
        return;
      }
      setRememberMe(true);
      setForm((prev) => ({ ...prev, password: '' }));
    };

    const handleSubmit = async () => {
      setSubmitting(true);
      try {
        if (mode === 'register') {
          const response = await register({
            email: form.email,
            fullName: form.fullName,
            password: form.password,
          });
          setAuthState(response);
        } else {
          const response = await login({ email: form.email, password: form.password, rememberMe });
          setAuthState(response);
        }
        try {
          const nextLocalInputMemory = await saveCloudAuthInputMemory({
            rememberInputs,
            email: form.email,
            fullName: form.fullName,
            password: form.password,
          });
          setLocalInputMemoryState(nextLocalInputMemory);
        } catch (memoryError) {
          console.warn('[auth-shell] save local input memory failed', memoryError);
        }
        await loadAll();
      } catch (error) {
        setMessage(error instanceof Error ? error.message : '提交失败');
      } finally {
        setSubmitting(false);
      }
    };

    useEffect(() => {
      if (!message.includes('无法连接本地服务')) return;
      let cancelled = false;
      const tryRecover = async () => {
        try {
          const response = await probeLocalBackendHealth(900);
          if (cancelled) return;
          setHealth(response);
          backendReadyRef.current = true;
          clearLocalServiceStartupBanner();
          setMessage('');
          await loadAll(undefined, { allowStartupRetry: false });
        } catch {
          // 后端还没起来时保持静默轮询，避免持续打扰用户
        }
      };
      void tryRecover();
      const timer = window.setInterval(() => {
        void tryRecover();
      }, 1500);
      return () => {
        cancelled = true;
        window.clearInterval(timer);
      };
    }, [message]);

    return (
      <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center px-6">
        <div className="w-full max-w-[980px] grid grid-cols-1 lg:grid-cols-[0.95fr_1.05fr] rounded-[36px] overflow-hidden border border-gray-100 shadow-[0_20px_80px_rgba(0,0,0,0.08)] bg-white">
          <div className="p-10 bg-gradient-to-br from-[#edf2ff] via-white to-[#f8fbff] border-r border-gray-100">
            <div className="w-12 h-12 rounded-2xl bg-[#5B7BFE]/10 text-[#5B7BFE] flex items-center justify-center mb-6">
              <ShieldAlert size={24} />
            </div>
            <h1 className="text-[30px] font-bold text-gray-900 leading-tight">益语智库自用平台</h1>
            <p className="text-[14px] text-gray-500 mt-3 leading-relaxed">先把个人账号建起来，再决定是否连接云端、加入组织或接受邀请。组织审批只发生在组织层动作里，不再挡住个人注册和登录。</p>
            <div className="mt-8 space-y-3 text-[13px] text-gray-600">
              <div className="bg-white border border-gray-100 rounded-2xl px-4 py-3">个人注册成功后即可直接登录，不再等待审批</div>
              <div className="bg-white border border-gray-100 rounded-2xl px-4 py-3">加入组织、切换部门、申请权限时，再进入组织层审批或邀请流程</div>
              <div className="bg-white border border-gray-100 rounded-2xl px-4 py-3">如果你只是个人使用，可以先在本机模式下直接开始工作</div>
            </div>
          </div>
          <div className="p-10 lg:p-12">
            <div className="flex bg-gray-100/80 p-1.5 rounded-2xl border border-gray-100 mb-8 w-fit">
              <button onClick={() => switchMode('login')} className={`px-5 py-2 rounded-xl text-[13px] font-bold ${mode === 'login' ? 'bg-white shadow-sm text-[#5B7BFE]' : 'text-gray-500'}`}>登录</button>
              <button onClick={() => switchMode('register')} className={`px-5 py-2 rounded-xl text-[13px] font-bold ${mode === 'register' ? 'bg-white shadow-sm text-[#5B7BFE]' : 'text-gray-500'}`}>注册</button>
            </div>
            <div className="space-y-4">
              {mode === 'login' && (
                <>
                  {rememberedAccounts.length > 0 && (
                    <select
                      value={form.email}
                      onChange={(event) => {
                        const selected = rememberedAccounts.find((account) => account.email === event.target.value);
                        setForm(createEmptyForm(selected?.email || event.target.value, selected?.fullName || '', selected?.password || ''));
                      }}
                      className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[14px] outline-none"
                    >
                      <option value="">选择已记住的账号（可选）</option>
                      {rememberedAccounts.map((account) => (
                        <option key={account.email} value={account.email}>
                          {account.fullName ? `${account.fullName} · ${account.email}` : account.email}
                        </option>
                      ))}
                    </select>
                  )}
                  <input value={form.email} onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))} placeholder="邮箱" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[14px] outline-none" />
                  <input type={showPassword ? 'text' : 'password'} value={form.password} onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))} placeholder="密码" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[14px] outline-none" />
                  <div className="flex gap-3">
                    <label className="flex-1 flex items-center justify-between rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium text-gray-700">
                      记住我的登录状态
                      <input type="checkbox" checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} />
                    </label>
                    <label className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium text-gray-700">
                      显示密码
                      <input type="checkbox" checked={showPassword} onChange={(event) => setShowPassword(event.target.checked)} />
                    </label>
                  </div>
                  <label className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium text-gray-700">
                    记住这组账号和密码（仅本机）
                    <input type="checkbox" checked={rememberInputs} onChange={(event) => setRememberInputs(event.target.checked)} />
                  </label>
                </>
              )}
              {mode === 'register' && (
                <>
                  <div className="rounded-2xl border border-blue-100 bg-[#F8FAFF] px-4 py-3">
                    <p className="text-[12px] font-bold text-[#5B7BFE]">个人账号注册</p>
                    <p className="mt-1 text-[12px] text-gray-500">注册账号依赖云端服务；开源版默认不提供云。本机模式可直接使用，后续接好云端后再注册、同步和加入组织。</p>
                  </div>
                  <div className="space-y-4">
                    <input value={form.fullName} onChange={(event) => setForm((prev) => ({ ...prev, fullName: event.target.value }))} placeholder="姓名 / 显示名" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[14px] outline-none" />
                    <div>
                      <input value={form.email} onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))} placeholder="邮箱" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[14px] outline-none" />
                      {form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email) && <p className="text-[12px] text-red-500 mt-1 px-1">请输入有效的邮箱地址</p>}
                    </div>
                    <div>
                      <input type={showPassword ? 'text' : 'password'} value={form.password} onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))} placeholder="密码（至少 8 位）" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[14px] outline-none" />
                      {form.password && form.password.length < 8 && <p className="text-[12px] text-red-500 mt-1 px-1">密码至少需要 8 位</p>}
                    </div>
                    <div>
                      <input type={showPassword ? 'text' : 'password'} value={form.confirmPassword} onChange={(event) => setForm((prev) => ({ ...prev, confirmPassword: event.target.value }))} placeholder="确认密码" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[14px] outline-none" />
                      {form.confirmPassword && form.password !== form.confirmPassword && <p className="text-[12px] text-red-500 mt-1 px-1">两次输入的密码不一致</p>}
                    </div>
                    <label className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium text-gray-700">
                      显示密码
                      <input type="checkbox" checked={showPassword} onChange={(event) => setShowPassword(event.target.checked)} />
                    </label>
                    <label className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium text-gray-700">
                      记住这组账号和密码（仅本机）
                      <input type="checkbox" checked={rememberInputs} onChange={(event) => setRememberInputs(event.target.checked)} />
                    </label>
                  </div>
                </>
              )}
              {message && (() => {
                const isSuccess = message.includes('已提交') || message.includes('成功');
                const isPending = message.includes('等待管理员审核') || message.includes('待审核');
                const isRejected = message.includes('未通过审核') || message.includes('停用');
                const style = isSuccess
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                  : isPending
                  ? 'border-blue-200 bg-blue-50 text-blue-800'
                  : isRejected
                  ? 'border-red-200 bg-red-50 text-red-800'
                  : 'border-amber-200 bg-amber-50 text-amber-800';
                return <div className={`rounded-2xl border px-4 py-3 text-[13px] ${style}`}>{message}</div>;
              })()}
              {mode === 'login' ? (
                <Button
                  primary
                  className="w-full py-3 text-[14px]"
                  onClick={() => void handleSubmit()}
                  disabled={submitting || !form.email.trim() || !form.password.trim()}
                >
                  {submitting ? <RefreshCw size={16} className="animate-spin" /> : <ShieldAlert size={16} />}
                  进入系统
                </Button>
              ) : (
                <Button
                  primary
                  className="w-full py-3 text-[14px]"
                  onClick={() => void handleSubmit()}
                  disabled={submitting || !form.email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email) || form.password.length < 8 || form.password !== form.confirmPassword || !form.fullName.trim()}
                >
                  {submitting ? <RefreshCw size={16} className="animate-spin" /> : <ShieldAlert size={16} />}
                  提交注册
                </Button>
              )}
            </div>
            <p className="text-[12px] text-gray-400 mt-6">如果你之后要加入组织、接受邀请或切换部门，请登录后在设置里处理。</p>
            <p className="text-[12px] text-gray-400 mt-2">勾选后会在当前设备持续保留登录状态；不勾选则只保留本次应用会话。</p>
          </div>
        </div>
      </div>
    );
  };

  const CloudAuthModal = () => {
    if (!cloudAuthModalOpen) return null;
    const rememberedAccounts = localInputMemoryState.cloudAuth.accounts;
    const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cloudAuthForm.email);
    const registerValid =
      Boolean(cloudAuthForm.fullName.trim())
      && emailValid
      && cloudAuthForm.password.length >= 8
      && cloudAuthForm.password === cloudAuthForm.confirmPassword;
    const loginValid = Boolean(cloudAuthForm.email.trim()) && Boolean(cloudAuthForm.password.trim());
    return (
      <div className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-950/35 px-4">
        <div className="w-full max-w-[720px] rounded-[32px] border border-gray-100 bg-white shadow-[0_24px_90px_rgba(15,23,42,0.18)]">
          <div className="flex items-start justify-between gap-4 border-b border-gray-100 px-8 py-6">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#5B7BFE]">连接云端</p>
              <h2 className="mt-2 text-[24px] font-bold text-gray-900">{cloudAuthMode === 'register' ? '注册个人账号' : '登录云端账号'}</h2>
              <p className="mt-2 text-[13px] text-gray-500">
                {cloudAuthMode === 'register'
                  ? '注册账号依赖云端服务；开源版默认不提供云。本机模式可直接使用，接好云端后再注册、同步和加入组织。'
                  : '登录云端后才会启用云同步、组织协作和需要组织数据的功能。'}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setCloudAuthModalOpen(false)}
              className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-gray-200 bg-white text-gray-500 hover:text-gray-900"
              aria-label="关闭"
            >
              <X size={18} />
            </button>
          </div>
          <div className="px-8 py-6 space-y-5">
            <div className="flex bg-gray-100/80 p-1.5 rounded-2xl border border-gray-100 w-fit">
              <button
                type="button"
                onClick={() => {
                  setCloudAuthMode('login');
                  setCloudAuthMessage('');
                }}
                className={`px-5 py-2 rounded-xl text-[13px] font-bold ${cloudAuthMode === 'login' ? 'bg-white shadow-sm text-[#5B7BFE]' : 'text-gray-500'}`}
              >
                登录
              </button>
              <button
                type="button"
                onClick={() => {
                  setCloudAuthMode('register');
                  setCloudAuthMessage('');
                }}
                className={`px-5 py-2 rounded-xl text-[13px] font-bold ${cloudAuthMode === 'register' ? 'bg-white shadow-sm text-[#5B7BFE]' : 'text-gray-500'}`}
              >
                注册
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {rememberedAccounts.length > 0 && (
                <select
                  value={cloudAuthForm.email}
                  onChange={(event) => {
                    const selected = rememberedAccounts.find((account) => account.email === event.target.value);
                    setCloudAuthForm((prev) => ({
                      ...prev,
                      email: selected?.email || event.target.value,
                      fullName: cloudAuthMode === 'register' ? (selected?.fullName || '') : prev.fullName,
                      password: selected?.password || '',
                      confirmPassword: cloudAuthMode === 'register' ? (selected?.password || '') : '',
                    }));
                  }}
                  className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[14px] outline-none md:col-span-2"
                >
                  <option value="">选择已记住的账号（可选）</option>
                  {rememberedAccounts.map((account) => (
                    <option key={account.email} value={account.email}>
                      {account.fullName ? `${account.fullName} · ${account.email}` : account.email}
                    </option>
                  ))}
                </select>
              )}
              {cloudAuthMode === 'register' && (
                <input
                  value={cloudAuthForm.fullName}
                  onChange={(event) => setCloudAuthForm((prev) => ({ ...prev, fullName: event.target.value }))}
                  placeholder="姓名 / 昵称"
                  className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[14px] outline-none"
                />
              )}
              <input
                value={cloudAuthForm.email}
                onChange={(event) => setCloudAuthForm((prev) => ({ ...prev, email: event.target.value }))}
                placeholder="邮箱"
                className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[14px] outline-none"
              />
              <input
                type={cloudAuthShowPassword ? 'text' : 'password'}
                value={cloudAuthForm.password}
                onChange={(event) => setCloudAuthForm((prev) => ({ ...prev, password: event.target.value }))}
                placeholder={cloudAuthMode === 'register' ? '密码（至少 8 位）' : '密码'}
                className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[14px] outline-none"
              />
              {cloudAuthMode === 'register' && (
                <input
                  type={cloudAuthShowPassword ? 'text' : 'password'}
                  value={cloudAuthForm.confirmPassword}
                  onChange={(event) => setCloudAuthForm((prev) => ({ ...prev, confirmPassword: event.target.value }))}
                  placeholder="确认密码"
                  className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[14px] outline-none"
                />
              )}
            </div>

            <div className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-[13px] font-medium text-gray-700">
                <input type="checkbox" checked={cloudAuthShowPassword} onChange={(event) => setCloudAuthShowPassword(event.target.checked)} />
                显示密码
              </label>
              <label className="flex items-center gap-2 text-[13px] font-medium text-gray-700">
                <input
                  type="checkbox"
                  checked={cloudAuthForm.rememberMe}
                  onChange={(event) => setCloudAuthForm((prev) => ({ ...prev, rememberMe: event.target.checked }))}
                />
                记住我的登录状态
              </label>
              <label className="flex items-center gap-2 text-[13px] font-medium text-gray-700">
                <input
                  type="checkbox"
                  checked={cloudAuthForm.rememberInputs}
                  onChange={(event) => setCloudAuthForm((prev) => ({ ...prev, rememberInputs: event.target.checked }))}
                />
                记住这组账号和密码（仅本机）
              </label>
            </div>

            {cloudAuthMessage && (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-800">
                {cloudAuthMessage}
              </div>
            )}

            <div className="flex justify-end gap-3">
              <Button onClick={() => setCloudAuthModalOpen(false)}>取消</Button>
              <Button
                primary
                onClick={() => void handleCloudAuthSubmit()}
                disabled={cloudAuthSubmitting || (cloudAuthMode === 'register' ? !registerValid : !loginValid)}
              >
                {cloudAuthSubmitting ? <RefreshCw size={16} className="animate-spin" /> : cloudAuthMode === 'register' ? <UserPlus size={16} /> : <ShieldAlert size={16} />}
                {cloudAuthMode === 'register' ? '注册并连接云端' : '登录并连接云端'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const tasksViewBridgeRef = useRef<Record<string, unknown>>({});
  tasksViewBridgeRef.current = {
    activeTab,
    activeTaskLists,
    activeTaskTags,
    agentWeeklyDigests,
    agentWeeklyPlans,
    authState,
    canManagePublicTaskTaxonomy,
    clients,
    currentClientId,
    currentOperatorName,
    currentSessionUser,
    currentWeekLabel,
    defaultTagScope,
    departmentOptions,
    effectiveTaskSettings,
    expandedTaskIds,
    flash,
    growthContextJump,
    handbookEntries,
    isPrivateTask,
    isTaskInReviewWeek,
    loadAgentWorklogBlock,
    loadHandbookBlock,
    loadReviewBlock,
    loadReviewHistoryBlock,
    loadTaskBlock,
    notifyGrowthRefresh,
    operators,
    reviewDashboard,
    reviewHistory,
    setActiveTab,
    setCurrentClientId,
    setGrowthContextJump,
    setIsReviewHistoryOpen,
    setReviewHistory,
    setSettingsSection,
    setTaskCalendarDate,
    setTaskSelectedDate,
    setTaskSelectedDay,
    setTaskViewMode,
    settingsState,
    taskCalendarDate,
    taskCalendarDisplayMode,
    taskLists,
    orgTaskLists,
    personalTaskLists,
    taskSelectedDate,
    taskSelectedDay,
    taskTags,
    taskViewMode,
    tasks,
    workspace,
  };

  const TasksView = useMemo(() => function TasksView() {
    const {
      activeTab,
      activeTaskLists,
      activeTaskTags,
      agentWeeklyDigests,
      agentWeeklyPlans,
      authState,
      canManagePublicTaskTaxonomy,
      clients,
      currentClientId,
      currentOperatorName,
      currentSessionUser,
      currentWeekLabel,
      defaultTagScope,
      departmentOptions,
      effectiveTaskSettings,
      expandedTaskIds,
      flash,
      growthContextJump,
      handbookEntries,
      isPrivateTask,
      isTaskInReviewWeek,
      loadAgentWorklogBlock,
      loadHandbookBlock,
      loadReviewBlock,
      loadReviewHistoryBlock,
      loadTaskBlock,
      notifyGrowthRefresh,
      operators,
      reviewDashboard,
      reviewHistory,
      setActiveTab,
      setCurrentClientId,
      setGrowthContextJump,
      setIsReviewHistoryOpen,
      setReviewHistory,
      setSettingsSection,
      setTaskCalendarDate,
      setTaskSelectedDate,
      setTaskSelectedDay,
      setTaskViewMode,
      settingsState,
      taskCalendarDate,
      taskCalendarDisplayMode,
      taskLists,
      orgTaskLists,
      personalTaskLists,
      taskSelectedDate,
      taskSelectedDay,
      taskTags,
      taskViewMode,
      tasks,
      workspace,
    } = tasksViewBridgeRef.current as {
      activeTab: typeof activeTab;
      activeTaskLists: typeof activeTaskLists;
      activeTaskTags: typeof activeTaskTags;
      agentWeeklyDigests: typeof agentWeeklyDigests;
      agentWeeklyPlans: typeof agentWeeklyPlans;
      authState: typeof authState;
      canManagePublicTaskTaxonomy: typeof canManagePublicTaskTaxonomy;
      clients: typeof clients;
      currentClientId: typeof currentClientId;
      currentOperatorName: typeof currentOperatorName;
      currentSessionUser: typeof currentSessionUser;
      currentWeekLabel: typeof currentWeekLabel;
      defaultTagScope: typeof defaultTagScope;
      departmentOptions: typeof departmentOptions;
      effectiveTaskSettings: typeof effectiveTaskSettings;
      expandedTaskIds: typeof expandedTaskIds;
      flash: typeof flash;
      growthContextJump: typeof growthContextJump;
      handbookEntries: typeof handbookEntries;
      isPrivateTask: typeof isPrivateTask;
      isTaskInReviewWeek: typeof isTaskInReviewWeek;
      loadAgentWorklogBlock: typeof loadAgentWorklogBlock;
      loadHandbookBlock: typeof loadHandbookBlock;
      loadReviewBlock: typeof loadReviewBlock;
      loadReviewHistoryBlock: typeof loadReviewHistoryBlock;
      loadTaskBlock: typeof loadTaskBlock;
      notifyGrowthRefresh: typeof notifyGrowthRefresh;
      operators: typeof operators;
      reviewDashboard: typeof reviewDashboard;
      reviewHistory: typeof reviewHistory;
      setActiveTab: typeof setActiveTab;
      setCurrentClientId: typeof setCurrentClientId;
      setGrowthContextJump: typeof setGrowthContextJump;
      setIsReviewHistoryOpen: typeof setIsReviewHistoryOpen;
      setReviewHistory: typeof setReviewHistory;
      setSettingsSection: typeof setSettingsSection;
      setTaskCalendarDate: typeof setTaskCalendarDate;
      setTaskSelectedDate: typeof setTaskSelectedDate;
      setTaskSelectedDay: typeof setTaskSelectedDay;
      setTaskViewMode: typeof setTaskViewMode;
      settingsState: typeof settingsState;
      taskCalendarDate: typeof taskCalendarDate;
      taskCalendarDisplayMode: typeof taskCalendarDisplayMode;
      taskLists: typeof taskLists;
      orgTaskLists: typeof orgTaskLists;
      personalTaskLists: typeof personalTaskLists;
      taskSelectedDate: typeof taskSelectedDate;
      taskSelectedDay: typeof taskSelectedDay;
      taskTags: typeof taskTags;
      taskViewMode: typeof taskViewMode;
      tasks: typeof tasks;
      workspace: typeof workspace;
    };
    const isCloudSession = authState.sessionMode === 'cloud' || !isLocalDeviceSessionUser(currentSessionUser);
    const isLocalSession = !isCloudSession;
    const resolveTaskViewDefaultListId = (scope: 'org' | 'personal') => {
      const listPool = scope === 'personal' ? personalTaskLists : orgTaskLists;
      return listPool.find((item) => item.isDefault)?.id || listPool[0]?.id || '';
    };
    const ensureTaskViewOrgTaskList = async () => {
      if (orgTaskLists.length > 0) {
        return orgTaskLists.find((item) => item.isDefault) || orgTaskLists[0] || null;
      }
      if (!orgListBootstrapRef.current) {
        orgListBootstrapRef.current = (async () => {
          const created = await createTaskList({
            name: '组织任务',
            color: '#5B7BFE',
            isDefault: true,
            scope: 'org',
          });
          await loadTaskBlock();
          return created;
        })()
          .finally(() => {
            orgListBootstrapRef.current = null;
          });
      }
      return orgListBootstrapRef.current;
    };
    const buildDefaultCollaborators = (): MentionCandidate[] => {
      if (!effectiveTaskSettings.autoAssignSelf || !currentSessionUser) return [];
      return [{
        id: currentSessionUser.id,
        fullName: currentSessionUser.fullName,
        email: currentSessionUser.email,
        primaryRole: currentSessionUser.primaryRole,
        isSelf: true,
      }];
    };
    const [isTaskGroupOpen, setIsTaskGroupOpen] = useState(true);
    const [taskListFilter, setTaskListFilter] = useState<TaskListFilter>('all');
    const [taskParticipationFilter, setTaskParticipationFilter] = useState<TaskParticipationFilter>('all');
    const [taskListNameFilter, setTaskListNameFilter] = useState('');
    const [taskListTimeSort, setTaskListTimeSort] = useState<TaskTimeSort>('newest');
    const [taskListTimeRangeFilter, setTaskListTimeRangeFilter] = useState<TaskTimeRangeFilter>('all');
    const [taskListCustomStartDate, setTaskListCustomStartDate] = useState('');
    const [taskListCustomEndDate, setTaskListCustomEndDate] = useState('');
    const [inboxTimeSort, setInboxTimeSort] = useState<TaskTimeSort>('newest');
    const [inboxTimeRangeFilter, setInboxTimeRangeFilter] = useState<TaskTimeRangeFilter>('all');
    const [inboxCustomStartDate, setInboxCustomStartDate] = useState('');
    const [inboxCustomEndDate, setInboxCustomEndDate] = useState('');
    const [taskSearchQuery, setTaskSearchQuery] = useState('');
    const [expandedInboxTaskIds, setExpandedInboxTaskIds] = useState<string[]>([]);
    const [isTaskModalOpen, setIsTaskModalOpen] = useState(false);
    const [isDuePickerOpen, setIsDuePickerOpen] = useState(false);
    const [duePickerMonth, setDuePickerMonth] = useState(() => getTodayCalendarState().calendarDate);
    const [editingTask, setEditingTask] = useState<TaskEditorState>({
      id: null,
      scopeMode: 'COLLAB_SHARED',
      scopeModeTouched: false,
      title: '',
      desc: '',
      listId: '',
      listIds: [],
      priority: effectiveTaskSettings.defaultPriority,
      priorityTouched: false,
      priorityReason: '系统会根据任务内容自动识别优先级，你可以手动调整。',
      ownerId: '',
      startDate: '',
      startTime: '',
      dueDate: defaultDueDateFromPreset(effectiveTaskSettings.defaultDueDatePreset),
      dueTime: TASK_DEFAULT_DUE_TIME,
      hasSpecificDueTime: false,
      durationMinutes: 60,
      clientId: '',
      clientTouched: false,
      clientConfidence: 'none',
      clientReason: `可选：手动选择${terminology.singularLabel}，或先关联事件线后自动回填。`,
      eventLineId: '',
      eventLineTouched: false,
      eventLineReason: '可选：把任务挂到一条持续推进的事件线上，后续复盘会按事件线聚合。',
      projectModuleId: '',
      projectModuleTouched: false,
      projectModuleReason: `可选：把任务挂到当前${terminology.singularLabel}下的具体${terminology.structureLabel}。`,
      projectFlowId: '',
      projectFlowTouched: false,
      projectFlowReason: '可选：把任务进一步挂到标准流程，后续复盘和日历会更贴近业务动作。',
      ddl: defaultDdlFromPreset(effectiveTaskSettings.defaultDueDatePreset),
      tagIds: [],
      collaborators: buildDefaultCollaborators(),
    });
    const [taskClientDnaCache, setTaskClientDnaCache] = useState<Record<string, ClientDnaModule[]>>({});
    const [projectStructureCache, setProjectStructureCache] = useState<Record<string, ProjectStructureResponse>>({});
    const [projectStructureUnavailableClientIds, setProjectStructureUnavailableClientIds] = useState<string[]>([]);
    const projectStructureUnavailableClientIdsRef = useRef<Set<string>>(new Set());
    const [pendingTaskArchiveText, setPendingTaskArchiveText] = useState('');
    const [pendingTaskAttachmentFiles, setPendingTaskAttachmentFiles] = useState<File[]>([]);
    const [isTaskAttachmentBusy, setIsTaskAttachmentBusy] = useState(false);
    const [taskAttachmentUploadProgress, setTaskAttachmentUploadProgress] = useState<{
      currentFileName: string;
      uploadedFiles: number;
      totalFiles: number;
      percent: number;
    } | null>(null);
    const [pendingSmartBriefDraftSource, setPendingSmartBriefDraftSource] = useState<{
      sourceTaskId: string;
      actionKey: string;
      actionText: string;
    } | null>(null);
    const [pendingTaskDelete, setPendingTaskDelete] = useState<{
      id: string;
      title: string;
      clientId?: string | null;
      eventLineId?: string | null;
      closeEditor?: boolean;
    } | null>(null);
    const [isSavingTask, setIsSavingTask] = useState(false);
    const [taskUnderstanding, setTaskUnderstanding] = useState<import('./lib/api').TaskUnderstandingSnapshot | null>(null);
    const [isLoadingUnderstanding, setIsLoadingUnderstanding] = useState(false);
    const isTaskModalOpenRef = useRef(false);
    const taskInteractionBlockTimerRef = useRef<number | null>(null);
    const taskInteractionBlockUntilRef = useRef(0);
    const calendarFocusTimerRef = useRef<number | null>(null);
    const calendarTaskOpenGuardUntilRef = useRef(0);
    const taskModalCloseEventCleanupRef = useRef<(() => void) | null>(null);
    const [tagDraft, setTagDraft] = useState({ name: '', scope: defaultTagScope, color: TASK_COLOR_OPTIONS[0] });
    const [mentionQuery, setMentionQuery] = useState('');
    const [mentionOptions, setMentionOptions] = useState<MentionCandidate[]>([]);
    const [isMentionMenuOpen, setIsMentionMenuOpen] = useState(false);
    const [ownerQuery, setOwnerQuery] = useState('');
    const [ownerOptions, setOwnerOptions] = useState<MentionCandidate[]>([]);
    const [isOwnerMenuOpen, setIsOwnerMenuOpen] = useState(false);
    const [taskListQuery, setTaskListQuery] = useState('');
    const [isTaskListMenuOpen, setIsTaskListMenuOpen] = useState(false);
    const [isCreatingTaskList, setIsCreatingTaskList] = useState(false);
    const collaboratorDropdownRef = useRef<HTMLDivElement | null>(null);
    const ownerDropdownRef = useRef<HTMLDivElement | null>(null);
    const taskListDropdownRef = useRef<HTMLDivElement | null>(null);
    const [suggestedTaskTags, setSuggestedTaskTags] = useState<string[]>([]);
    const [eventLines, setEventLines] = useState<EventLine[]>([]);
    const [eventLinesLoadError, setEventLinesLoadError] = useState<string | null>(null);
    const [eventLineMemberOptions, setEventLineMemberOptions] = useState<MentionCandidate[]>([]);
    const [eventLineProjectFilterId, setEventLineProjectFilterId] = useState<string>(() => {
      if (typeof window === 'undefined') return '__all__';
      return window.localStorage.getItem(EVENT_LINE_PROJECT_FILTER_STORAGE_KEY) || '__all__';
    });
    const elProjectDropdownRef = useRef<HTMLDivElement | null>(null);
    const [elProjectDropdownOpen, setElProjectDropdownOpen] = useState(false);
    const [drillTaskViewOverride, setDrillTaskViewOverride] = useState<ReviewDashboardCardTarget | null>(null);
    const [activeReviewDrillTarget, setActiveReviewDrillTarget] = useState<ReviewDashboardDrillTargetResponse | null>(null);
    const [isLoadingReviewDrillTarget, setIsLoadingReviewDrillTarget] = useState(false);
    const [activeEventLine, setActiveEventLine] = useState<EventLineDetail | null>(null);
    const [isEventLineEditorOpen, setIsEventLineEditorOpen] = useState(false);
    const [isEventLineCreateOpen, setIsEventLineCreateOpen] = useState(false);
    const [eventLineProjectResumeTarget, setEventLineProjectResumeTarget] = useState<'create' | 'edit' | null>(null);
    const [eventLineEditorDraft, setEventLineEditorDraft] = useState<EventLineEditorDraft>(buildEmptyEventLineEditorDraft());
    const [eventLineEditorSaveNotice, setEventLineEditorSaveNotice] = useState<string | null>(null);
    const [reportEventLineId, setReportEventLineId] = useState<string | null>(null);
    const [eventLineClarificationDraft, setEventLineClarificationDraft] = useState<EventLineClarificationState>(buildEventLineClarificationDraft(null));
    const [isEventLineClarifyMode, setIsEventLineClarifyMode] = useState(false);
    const [isEventLineBusy, setIsEventLineBusy] = useState(false);
    const [isGeneratingEventLineClarification, setIsGeneratingEventLineClarification] = useState(false);
    const [isSavingEventLineClarification, setIsSavingEventLineClarification] = useState(false);
    const [eventLineNoteText, setEventLineNoteText] = useState('');
    const [isSavingEventLineNote, setIsSavingEventLineNote] = useState(false);
    const [taskEventLineClarificationDraft, setTaskEventLineClarificationDraft] = useState<EventLineClarificationState>(buildEventLineClarificationDraft(null));
    const [isTaskEventLineClarifyMode, setIsTaskEventLineClarifyMode] = useState(false);
    const [isGeneratingTaskEventLineClarification, setIsGeneratingTaskEventLineClarification] = useState(false);
    const [isSavingTaskEventLineClarification, setIsSavingTaskEventLineClarification] = useState(false);
    const [isTaskEventLineCreateOpen, setIsTaskEventLineCreateOpen] = useState(false);
    const [taskEventLineCreateDraft, setTaskEventLineCreateDraft] = useState<TaskEventLineCreateDraftState>(buildTaskEventLineCreateDraft());
    const [isCreatingEventLine, setIsCreatingEventLine] = useState(false);
    const [isDeletingEventLine, setIsDeletingEventLine] = useState(false);
    const [isSavingEventLineEditor, setIsSavingEventLineEditor] = useState(false);
    const [isExpenseEvidenceModalOpen, setIsExpenseEvidenceModalOpen] = useState(false);
    const [expenseEvidenceContext, setExpenseEvidenceContext] = useState<ExpenseEvidenceModalContext | null>(null);
    const [expenseEvidenceQuery, setExpenseEvidenceQuery] = useState('');
    const [expenseEvidenceRecords, setExpenseEvidenceRecords] = useState<ExpenseEvidenceRecord[]>([]);
    const [isLoadingExpenseEvidenceRecords, setIsLoadingExpenseEvidenceRecords] = useState(false);
    const [expenseEvidenceImportSearchDraft, setExpenseEvidenceImportSearchDraft] = useState<ExpenseImportSearchPayload>(DEFAULT_EXPENSE_IMPORT_SEARCH_DRAFT);
    const [expenseEvidenceImportSearchResult, setExpenseEvidenceImportSearchResult] = useState<ExpenseImportSearchResponse | null>(null);
    const [isExpenseEvidenceImportSearchLoading, setIsExpenseEvidenceImportSearchLoading] = useState(false);
    const [selectedExpenseEvidenceImportIds, setSelectedExpenseEvidenceImportIds] = useState<string[]>([]);
    const [linkedExpenseEvidenceIds, setLinkedExpenseEvidenceIds] = useState<string[]>([]);
    const [isCreatingTaskProjectModule, setIsCreatingTaskProjectModule] = useState(false);
    const [isCreatingTaskProjectFlow, setIsCreatingTaskProjectFlow] = useState(false);
    const [taskGroupTemplates, setTaskGroupTemplates] = useState<TaskGroupTemplateRecord[]>([]);
    const [isTaskGroupTemplatesLoading, setIsTaskGroupTemplatesLoading] = useState(false);
    const [isTemplateEditorOpen, setIsTemplateEditorOpen] = useState(false);
    const [templateEditorMode, setTemplateEditorMode] = useState<'create' | 'edit'>('create');
    const [templateEditorInitialData, setTemplateEditorInitialData] = useState<TemplateData | null>(null);
    const [taskGroupTemplateEditingWorkObjectId, setTaskGroupTemplateEditingWorkObjectId] = useState('');
    const [isTemplateListOpen, setIsTemplateListOpen] = useState(false);
    const [templateListEditingModuleId, setTemplateListEditingModuleId] = useState<string | null>(null);
    const [taskGroupTemplateApplyTarget, setTaskGroupTemplateApplyTarget] = useState<TaskGroupTemplateRecord | null>(null);
    const [taskGroupTemplateApplyDraft, setTaskGroupTemplateApplyDraft] = useState<TaskGroupTemplateApplyDraftState | null>(null);
    const [taskGroupTemplateCollaboratorMenuStep, setTaskGroupTemplateCollaboratorMenuStep] = useState<number | null>(null);
    const [isApplyingTaskGroupTemplate, setIsApplyingTaskGroupTemplate] = useState(false);
    const [recentlyCreatedTaskIds, setRecentlyCreatedTaskIds] = useState<string[]>([]);
    const [taskContextPreview, setTaskContextPreview] = useState<TaskContextPreview | null>(null);
    const [isTaskContextPreviewLoading, setIsTaskContextPreviewLoading] = useState(false);
    const [taskSmartBriefs, setTaskSmartBriefs] = useState<Record<string, TaskSmartBrief>>({});
    const [selectedInboxIds, setSelectedInboxIds] = useState<string[]>([]);
    const [transitioningInboxTaskIds, setTransitioningInboxTaskIds] = useState<string[]>([]);
    const [isRejectModalOpen, setIsRejectModalOpen] = useState(false);
    const [rejectingTaskIds, setRejectingTaskIds] = useState<string[]>([]);
    const [rejectReason, setRejectReason] = useState('');
    const [expandedReviewGroupId, setExpandedReviewGroupId] = useState<string | null>(null);
    const [isTaskInteractionBlocked, setIsTaskInteractionBlocked] = useState(false);
    const [isGeneratingGlobal, setIsGeneratingGlobal] = useState(false);
    const [savingReviewGroupId, setSavingReviewGroupId] = useState<string | null>(null);
    const [savedReviewGroupId, setSavedReviewGroupId] = useState<string | null>(null);
    const [reviewStatusChangingGroupId, setReviewStatusChangingGroupId] = useState<string | null>(null);
    const projectStructureLoadingClientIdsRef = useRef<Set<string>>(new Set());

    const markProjectStructureUnavailable = useCallback((clientIds: string[]) => {
      if (clientIds.length === 0) return;
      const next = new Set(projectStructureUnavailableClientIdsRef.current);
      clientIds.forEach((clientId) => {
        if (clientId) next.add(clientId);
      });
      projectStructureUnavailableClientIdsRef.current = next;
      setProjectStructureUnavailableClientIds(Array.from(next));
    }, []);

    const clearProjectStructureUnavailable = useCallback((clientIds: string[]) => {
      if (clientIds.length === 0) return;
      const toDelete = new Set(clientIds.filter(Boolean));
      const next = new Set(
        Array.from(projectStructureUnavailableClientIdsRef.current).filter((id) => !toDelete.has(id)),
      );
      projectStructureUnavailableClientIdsRef.current = next;
      setProjectStructureUnavailableClientIds(Array.from(next));
    }, []);

    useEffect(() => {
      isTaskModalOpenRef.current = isTaskModalOpen;
    }, [isTaskModalOpen]);

    useEffect(() => () => {
      if (taskInteractionBlockTimerRef.current !== null) {
        window.clearTimeout(taskInteractionBlockTimerRef.current);
      }
      if (calendarFocusTimerRef.current !== null) {
        window.clearTimeout(calendarFocusTimerRef.current);
      }
      taskModalCloseEventCleanupRef.current?.();
      taskModalCloseEventCleanupRef.current = null;
    }, []);

    // Load understanding and auto-refresh pending summaries
    useEffect(() => {
      if (!isTaskModalOpen || !editingTask.id) {
        setTaskUnderstanding(null);
        setIsLoadingUnderstanding(false);
        return;
      }
      let cancelled = false;
      let pollTimer: number | null = null;
      let pollAttempts = 0;

      const load = async () => {
        if (!cancelled) {
          setIsLoadingUnderstanding(true);
        }
        try {
          const snapshot = await getTaskUnderstanding(editingTask.id!);
          if (cancelled) return;
          setTaskUnderstanding(snapshot);
          if (snapshot._pending && pollAttempts < 5) {
            pollAttempts += 1;
            pollTimer = window.setTimeout(() => {
              pollTimer = null;
              void load();
            }, pollAttempts <= 2 ? 1200 : 1800);
            return;
          }
        } catch {
          if (!cancelled) {
            setTaskUnderstanding(null);
          }
        } finally {
          if (!cancelled && pollTimer === null) {
            setIsLoadingUnderstanding(false);
          }
        }
      };

      void load();
      return () => {
        cancelled = true;
        if (pollTimer !== null) {
          window.clearTimeout(pollTimer);
        }
      };
    }, [isTaskModalOpen, editingTask.id]);

    const blockTaskInteractions = (durationMs = 260) => {
      taskInteractionBlockUntilRef.current = Date.now() + durationMs;
      setIsTaskInteractionBlocked(true);
      if (taskInteractionBlockTimerRef.current !== null) {
        window.clearTimeout(taskInteractionBlockTimerRef.current);
      }
      taskInteractionBlockTimerRef.current = window.setTimeout(() => {
        setIsTaskInteractionBlocked(false);
        taskInteractionBlockUntilRef.current = 0;
        taskInteractionBlockTimerRef.current = null;
      }, durationMs);
    };

    const scheduleCalendarFocus = (dueDate?: string | null, ddl?: string | null, delayMs = 280) => {
      if (calendarFocusTimerRef.current !== null) {
        window.clearTimeout(calendarFocusTimerRef.current);
        calendarFocusTimerRef.current = null;
      }
      if (!dueDate && !ddl) return;
      calendarFocusTimerRef.current = window.setTimeout(() => {
        focusCalendarOnTaskDate(dueDate, ddl);
        calendarFocusTimerRef.current = null;
      }, delayMs);
    };

    const guardCalendarTaskOpen = (durationMs = 520) => {
      calendarTaskOpenGuardUntilRef.current = Date.now() + durationMs;
    };

    const swallowTaskModalCloseEvents = (durationMs = 520) => {
      taskModalCloseEventCleanupRef.current?.();
      const eventTypes = ['pointerdown', 'pointerup', 'mousedown', 'mouseup', 'click', 'dblclick'] as const;
      const handler = (event: Event) => {
        event.preventDefault();
        event.stopPropagation();
      };
      eventTypes.forEach((eventName) => {
        window.addEventListener(eventName, handler, true);
      });
      const timer = window.setTimeout(() => {
        eventTypes.forEach((eventName) => {
          window.removeEventListener(eventName, handler, true);
        });
        window.clearTimeout(timer);
        if (taskModalCloseEventCleanupRef.current === cleanup) {
          taskModalCloseEventCleanupRef.current = null;
        }
      }, durationMs);
      const cleanup = () => {
        eventTypes.forEach((eventName) => {
          window.removeEventListener(eventName, handler, true);
        });
        window.clearTimeout(timer);
      };
      taskModalCloseEventCleanupRef.current = cleanup;
    };

    const resetTaskModalTransientState = () => {
      setIsDuePickerOpen(false);
      setIsMentionMenuOpen(false);
      setMentionQuery('');
      setMentionOptions([]);
      setIsOwnerMenuOpen(false);
      setOwnerQuery('');
      setOwnerOptions([]);
      setIsTaskListMenuOpen(false);
      setTaskListQuery('');
      setPendingTaskAttachmentFiles([]);
      setTaskAttachmentUploadProgress(null);
      setIsTaskAttachmentBusy(false);
      setIsSavingTask(false);
      setPendingTaskArchiveText('');
      setPendingSmartBriefDraftSource(null);
      setIsTaskEventLineCreateOpen(false);
      setTaskEventLineCreateDraft(buildTaskEventLineCreateDraft());
    };

    const closeTaskModal = (reason: string) => {
      console.info(`[task-modal] close reason=${reason}`);
      resetTaskModalTransientState();
      isTaskModalOpenRef.current = false;
      blockTaskInteractions(1200);
      guardCalendarTaskOpen(1800);
      swallowTaskModalCloseEvents(640);
      setIsTaskModalOpen(false);
    };
    const [hidePersonalTasks, setHidePersonalTasks] = useState(false);
    const [reviewScope, setReviewScope] = useState<'work' | 'personal'>(effectiveTaskSettings.defaultReviewScope);
    const [activeReviewTab, setActiveReviewTab] = useState<'overview' | 'events' | 'signals' | 'ai'>('overview');
    const [reviewPerspective, setReviewPerspective] = useState<'global' | 'ceo' | 'department' | 'personal'>('global');
    const [reviewForm, setReviewForm] = useState<ReviewFormState>(createEmptyReviewForm());
    const syncReviewDirtyTaskIds = (next: Set<string>) => {
      reviewDirtyTaskIdsRef.current = next;
      setReviewDirtyTaskIds(Array.from(next));
    };

    const markReviewTasksDirty = (taskIds: string[]) => {
      if (taskIds.length === 0) return;
      const next = new Set(reviewDirtyTaskIdsRef.current);
      taskIds.forEach((taskId) => next.add(taskId));
      syncReviewDirtyTaskIds(next);
    };

    const clearReviewTasksDirty = (taskIds?: string[]) => {
      if (!taskIds || taskIds.length === 0) {
        syncReviewDirtyTaskIds(new Set());
        return;
      }
      const next = new Set(reviewDirtyTaskIdsRef.current);
      taskIds.forEach((taskId) => next.delete(taskId));
      syncReviewDirtyTaskIds(next);
    };

    useEffect(() => {
      if (!workspace?.client?.id) return;
      setTaskClientDnaCache((prev) => ({
        ...prev,
        [workspace.client.id]: workspace.dnaModules || [],
      }));
      setProjectStructureCache((prev) => ({
        ...prev,
        [workspace.client.id]: {
          modules: workspace.projectModules || [],
          flows: workspace.projectFlows || [],
        },
      }));
      clearProjectStructureUnavailable([workspace.client.id]);
    }, [clearProjectStructureUnavailable, workspace]);

    useEffect(() => {
      if (!activeEventLine) {
        setEventLineClarificationDraft(buildEventLineClarificationDraft(null));
        setIsEventLineClarifyMode(false);
        setIsGeneratingEventLineClarification(false);
        return;
      }
      setEventLineClarificationDraft(buildEventLineClarificationDraft(activeEventLine.eventLine));
    }, [activeEventLine]);

    const ensureTaskProjectStructureLoaded = useCallback(async (clientId: string) => {
      if (!clientId || clientId === workspace?.client.id) {
        return workspace?.projectModules || workspace?.projectFlows
          ? {
              modules: workspace?.projectModules || [],
              flows: workspace?.projectFlows || [],
            }
          : null;
      }
      if (projectStructureUnavailableClientIdsRef.current.has(clientId)) return null;
      if (projectStructureCache[clientId]) return projectStructureCache[clientId];
      if (projectStructureLoadingClientIdsRef.current.has(clientId)) return null;
      projectStructureLoadingClientIdsRef.current.add(clientId);
      try {
        const [modules, structure] = await Promise.all([
          taskClientDnaCache[clientId]
            ? Promise.resolve(taskClientDnaCache[clientId])
            : getClientDnaDocuments(clientId).then((response) => response.modules),
          getClientProjectStructure(clientId),
        ]);
        setTaskClientDnaCache((prev) => (
          prev[clientId] ? prev : {
            ...prev,
            [clientId]: modules,
          }
        ));
        setProjectStructureCache((prev) => (
          prev[clientId] ? prev : {
            ...prev,
            [clientId]: structure,
          }
        ));
        clearProjectStructureUnavailable([clientId]);
        return structure;
      } catch {
        markProjectStructureUnavailable([clientId]);
        return null;
      } finally {
        projectStructureLoadingClientIdsRef.current.delete(clientId);
      }
    }, [clearProjectStructureUnavailable, markProjectStructureUnavailable, projectStructureCache, taskClientDnaCache, workspace?.client.id, workspace?.projectFlows, workspace?.projectModules]);

    const loadEventLines = useCallback(async () => {
      try {
        const records = await getEventLines();
        setEventLines(records);
        setEventLinesLoadError(null);
      } catch (error) {
        console.warn('[event-lines] load failed', error);
        setEventLinesLoadError(error instanceof Error ? error.message : '事件线加载失败');
      }
    }, []);

    useEffect(() => {
      void loadEventLines();
    }, [loadEventLines]);

    useEffect(() => {
      if (!authState.authenticated || authState.sessionMode !== 'cloud' || isLocalDeviceSessionUser(currentSessionUser)) {
        setEventLines([]);
        setEventLinesLoadError(null);
        setActiveEventLine(null);
        setReportEventLineId(null);
        return;
      }
      void loadEventLines();
    }, [
      authState.authenticated,
      authState.sessionMode,
      currentSessionUser?.id,
      currentSessionUser?.organizationId,
      loadEventLines,
    ]);

    useEffect(() => {
      if (activeTab !== 'tasks' || taskViewMode !== 'event_lines') return;
      void loadEventLines();
    }, [activeTab, loadEventLines, taskViewMode]);

    // 自定义下拉菜单：点击外部关闭
    useEffect(() => {
      if (!elProjectDropdownOpen) return;
      const handler = (e: MouseEvent) => {
        if (elProjectDropdownRef.current && !elProjectDropdownRef.current.contains(e.target as Node)) {
          setElProjectDropdownOpen(false);
        }
      };
      document.addEventListener('mousedown', handler, true);
      return () => document.removeEventListener('mousedown', handler, true);
    }, [elProjectDropdownOpen]);

    useEffect(() => {
      if (!isTaskModalOpen) {
        setIsDuePickerOpen(false);
        return;
      }
      if (!editingTask.dueDate) {
        setDuePickerMonth(getTodayCalendarState().calendarDate);
        return;
      }
      const parsedDate = parseTaskDateValue(editingTask.dueDate);
      if (parsedDate) {
        setDuePickerMonth(new Date(parsedDate.getFullYear(), parsedDate.getMonth(), 1));
      }
    }, [editingTask.dueDate, isTaskModalOpen]);

    useEffect(() => {
      if (!isTaskModalOpen) return;
      const nextPriority = !editingTask.priorityTouched
        ? inferTaskPriority({
            title: editingTask.title,
            desc: editingTask.desc,
            dueDate: combineTaskDueDateTime(editingTask.dueDate, editingTask.dueTime, {
              includeTime: editingTask.hasSpecificDueTime,
            }),
            clientTokens: clients.flatMap((client) => [client.name, client.alias, client.domain]),
          })
        : null;
      const nextClient = !editingTask.clientTouched
        && editingTask.scopeMode !== 'PERSONAL_ONLY'
        ? inferTaskClient({
            title: editingTask.title,
            desc: editingTask.desc,
            clients,
            currentClientId,
            organizationName: organizationTaskName,
          })
        : null;
      const nextClientIdForInference = nextClient ? nextClient.clientId : editingTask.clientId;
      const nextEventLine = !editingTask.eventLineTouched
        && editingTask.scopeMode !== 'PERSONAL_ONLY'
        ? inferTaskEventLine({
            title: editingTask.title,
            desc: editingTask.desc,
            eventLines,
            currentClientId: nextClientIdForInference,
          })
        : null;
      if (!nextPriority && !nextClient && !nextEventLine) return;
      setEditingTask((prev) => {
        const updates: Partial<TaskEditorState> = {};
        if (nextPriority && (!prev.priorityTouched && (prev.priority !== nextPriority.priority || prev.priorityReason !== nextPriority.reason))) {
          updates.priority = nextPriority.priority;
          updates.priorityReason = nextPriority.reason;
        }
        if (nextClient && (!prev.clientTouched && (prev.clientId !== (nextClient.clientId || organizationClientId) || prev.clientReason !== nextClient.reason || prev.clientConfidence !== nextClient.confidence))) {
          updates.clientId = nextClient.clientId || organizationClientId;
          updates.clientReason = nextClient.reason;
          updates.clientConfidence = nextClient.confidence;
        }
        if (nextEventLine && (!prev.eventLineTouched && (prev.eventLineId !== nextEventLine.eventLineId || prev.eventLineReason !== nextEventLine.reason))) {
          updates.eventLineId = nextEventLine.eventLineId;
          updates.eventLineReason = nextEventLine.reason;
        }
        return Object.keys(updates).length > 0 ? { ...prev, ...updates } : prev;
      });
    }, [
      clients,
      currentClientId,
      editingTask.clientTouched,
      editingTask.desc,
      editingTask.dueDate,
      editingTask.dueTime,
      editingTask.eventLineTouched,
      editingTask.clientId,
      editingTask.priorityTouched,
      editingTask.scopeMode,
      editingTask.title,
      eventLines,
      isTaskModalOpen,
      organizationTaskName,
    ]);

    useEffect(() => {
      if (!isTaskModalOpen) return;
      if (editingTask.scopeMode === 'PERSONAL_ONLY') return;
      if (orgTaskLists.length > 0 || isTaskListsLoading) return;
      void refreshTaskListLibrary().catch(() => undefined);
    }, [
      editingTask.scopeMode,
      isTaskModalOpen,
      isTaskListsLoading,
      orgTaskLists.length,
      refreshTaskListLibrary,
    ]);

    useEffect(() => {
      if (!isTaskModalOpen) return;
      if (editingTask.scopeMode === 'PERSONAL_ONLY') {
        if (personalTaskLists.length === 0) return;
        const fallbackListId = resolveTaskViewDefaultListId('personal');
        const nextListIds = Array.from(new Set((editingTask.listIds || []).filter((listId) => personalTaskLists.some((item) => item.id === listId))));
        const nextPrimaryListId = nextListIds[0] || fallbackListId || '';
        const normalizedListIds = nextListIds.length > 0 ? nextListIds : (nextPrimaryListId ? [nextPrimaryListId] : []);
        if (editingTask.listId === nextPrimaryListId && JSON.stringify(editingTask.listIds) === JSON.stringify(normalizedListIds)) return;
        setEditingTask((prev) => ({ ...prev, listId: nextPrimaryListId, listIds: normalizedListIds }));
        return;
      }
      if (orgTaskLists.length === 0) return;
      const fallbackListId = resolveTaskViewDefaultListId('org');
      const nextListIds = Array.from(new Set((editingTask.listIds || []).filter((listId) => orgTaskLists.some((item) => item.id === listId))));
      const nextPrimaryListId = nextListIds[0] || fallbackListId || '';
      const normalizedListIds = nextListIds.length > 0 ? nextListIds : (nextPrimaryListId ? [nextPrimaryListId] : []);
      if (editingTask.listId === nextPrimaryListId && JSON.stringify(editingTask.listIds) === JSON.stringify(normalizedListIds)) return;
      setEditingTask((prev) => ({ ...prev, listId: nextPrimaryListId, listIds: normalizedListIds }));
    }, [
      editingTask.listId,
      editingTask.listIds,
      editingTask.scopeMode,
      isTaskModalOpen,
      orgTaskLists,
      personalTaskLists,
      resolveTaskViewDefaultListId,
    ]);
    const latestReview = reviewDashboard?.currentReview || null;
    const teamReport = reviewDashboard?.teamReport || null;
    const orgReport = reviewDashboard?.orgReport || null;
    const executiveOrgReport = reviewDashboard?.executiveOrgReport || null;
    const departmentReports = reviewDashboard?.departmentReports || [];
    const agentDepartmentDigests = reviewDashboard?.agentDepartmentDigests || [];
    const agentDepartmentPlans = reviewDashboard?.agentDepartmentPlans || [];
    const simulationBundle = reviewDashboard?.simulationBundle || null;
    const selfReviewReport = reviewDashboard?.selfReport || null;
    const workReviewItems = reviewDashboard?.workItems || [];
    const personalReviewItems = reviewDashboard?.personalItems || [];
    const collectStageAnalysis = reviewScope === 'work' ? reviewDashboard?.workAnalysis || null : reviewDashboard?.personalAnalysis || null;
    const calendarMonthLabel = `${taskCalendarDate.getFullYear()}-${String(taskCalendarDate.getMonth() + 1).padStart(2, '0')}`;
    const selectedCalendarWeekLabel = weekLabelForDate(new Date(taskCalendarDate.getFullYear(), taskCalendarDate.getMonth(), taskSelectedDay));
    const selectedWeekAgentDigests = agentWeeklyDigests.filter((item) => item.weekLabel === selectedCalendarWeekLabel);
    const selectedWeekAgentPlans = agentWeeklyPlans.filter((item) => item.weekLabel === selectedCalendarWeekLabel);

    useEffect(() => {
      const weekLabel = latestReview?.weekLabel || currentWeekLabel();
      const shouldPreserveDirty = reviewDirtyTaskIdsRef.current.size > 0 && reviewForm.weekLabel === weekLabel;
      const nextEntries = Object.fromEntries(
        [...workReviewItems, ...personalReviewItems].map((item) => {
          const structuredNote = item.structuredNote || createEmptyReviewStructuredNote();
          const hasStructuredContent = hasMeaningfulReviewStructuredNote(structuredNote);
          return [
            item.taskId,
            hasStructuredContent
              ? structuredNote
              : { ...createEmptyReviewStructuredNote(), reflection: item.note || '' },
          ];
        }),
      );
      if (!shouldPreserveDirty && reviewDirtyTaskIdsRef.current.size > 0) {
        clearReviewTasksDirty();
      }
      setReviewForm((prev) => {
        if (shouldPreserveDirty && prev.weekLabel === weekLabel) {
          const mergedEntries = { ...nextEntries };
          Object.entries(prev.entriesByTaskId).forEach(([taskId, entry]) => {
            if (reviewDirtyTaskIdsRef.current.has(taskId) && hasMeaningfulReviewStructuredNote(entry)) {
              mergedEntries[taskId] = { ...entry };
            }
          });
          return { weekLabel, entriesByTaskId: mergedEntries };
        }
        return { weekLabel, entriesByTaskId: nextEntries };
      });
    }, [latestReview, reviewForm.weekLabel, workReviewItems, personalReviewItems]);

    useEffect(() => {
      setReviewScope(effectiveTaskSettings.defaultReviewScope);
    }, [effectiveTaskSettings.defaultReviewScope]);

    useEffect(() => {
      if (!isTaskModalOpen) {
        setIsMentionMenuOpen(false);
        setMentionQuery('');
        setMentionOptions([]);
        setIsOwnerMenuOpen(false);
        setOwnerQuery('');
        setOwnerOptions([]);
        setSuggestedTaskTags([]);
        return;
      }
      const normalizedQuery = mentionQuery.trim();
      void getMentionCandidates(normalizedQuery)
        .then((items) => setMentionOptions(items))
        .catch(() => setMentionOptions([]));
    }, [isTaskModalOpen, mentionQuery]);

    useEffect(() => {
      if (!isMentionMenuOpen) return;
      const handler = (event: MouseEvent) => {
        if (collaboratorDropdownRef.current && !collaboratorDropdownRef.current.contains(event.target as Node)) {
          setIsMentionMenuOpen(false);
        }
      };
      document.addEventListener('mousedown', handler, true);
      return () => document.removeEventListener('mousedown', handler, true);
    }, [isMentionMenuOpen]);

    useEffect(() => {
      if (!isOwnerMenuOpen) return;
      const handler = (event: MouseEvent) => {
        if (ownerDropdownRef.current && !ownerDropdownRef.current.contains(event.target as Node)) {
          setIsOwnerMenuOpen(false);
        }
      };
      document.addEventListener('mousedown', handler, true);
      return () => document.removeEventListener('mousedown', handler, true);
    }, [isOwnerMenuOpen]);

    useEffect(() => {
      if (!isTaskListMenuOpen) return;
      const handler = (event: MouseEvent) => {
        if (taskListDropdownRef.current && !taskListDropdownRef.current.contains(event.target as Node)) {
          setIsTaskListMenuOpen(false);
        }
      };
      document.addEventListener('mousedown', handler, true);
      return () => document.removeEventListener('mousedown', handler, true);
    }, [isTaskListMenuOpen]);

    useEffect(() => {
      if (!isTaskModalOpen) return;
      const normalizedQuery = ownerQuery.trim();
      void getMentionCandidates(normalizedQuery)
        .then((items) => setOwnerOptions(items))
        .catch(() => setOwnerOptions([]));
    }, [isTaskModalOpen, ownerQuery]);

    useEffect(() => {
      if (!isCloudSession) {
        setEventLineMemberOptions([]);
        return;
      }
      void getMentionCandidates('')
        .then((items) => setEventLineMemberOptions(items))
        .catch(() => setEventLineMemberOptions([]));
    }, [isCloudSession]);

    const loadTaskGroupTemplateBlock = useCallback(async () => {
      setIsTaskGroupTemplatesLoading(true);
      try {
        const response = await listTaskGroupTemplates();
        setTaskGroupTemplates(response.templates || []);
        return response.templates || [];
      } finally {
        setIsTaskGroupTemplatesLoading(false);
      }
    }, []);

    useEffect(() => {
      void loadTaskGroupTemplateBlock().catch(() => setTaskGroupTemplates([]));
    }, [authState.sessionMode, currentSessionUser?.id, currentSessionUser?.organizationId, loadTaskGroupTemplateBlock]);

    const getListColor = (listId: string) => taskLists.find((list) => list.id === listId)?.color || '#888681';
    const getListName = (listId: string) => {
      const normalizedId = (listId || '').trim();
      if (!normalizedId) return '';
      return taskLists.find((list) => list.id === normalizedId)?.name || '';
    };
    const taskControlLevelLabel = (task: Task) => {
      const level = task.orgContext?.controlLevel;
      if (level === 'leader_control') return '负责人控制';
      if (level === 'department_control') return '部门控制';
      if (level === 'organization_control') return '机构控制';
      return '';
    };

    const canManageEventLine = useCallback((eventLine?: Pick<EventLine, 'ownerId' | 'ownerIds'> | null) => {
      if (!eventLine || !currentSessionUser?.id) return false;
      if (currentSessionUser.primaryRole === 'admin') return true;
      const ownerIds = eventLine.ownerIds?.length
        ? eventLine.ownerIds
        : eventLine.ownerId
          ? [eventLine.ownerId]
          : [];
      return ownerIds.includes(currentSessionUser.id);
    }, [currentSessionUser?.id, currentSessionUser?.primaryRole]);

    const canReviewTask = (task: Task) => {
      if (!task.orgContext?.needsReview || !currentSessionUser?.id) return false;
      if (task.ownerId && task.ownerId === currentSessionUser.id) return false;
      return true;
    };

    const inboundPendingTasks = tasks.filter((task) => task.status === 'inbox' && !transitioningInboxTaskIds.includes(task.id));
    const outboundPendingTasks = tasks.filter(
      (task) => task.status !== 'rejected'
        && task.status !== 'inbox'
        && !transitioningInboxTaskIds.includes(task.id)
        && taskWaitsForOthers(task, currentSessionUser?.id),
    );
    const inboundNotificationTasks = useMemo(
      () => sortTasksByTimeDirection(
        inboundPendingTasks.filter((task) =>
          task.sourceType === 'event_line_notification'
          && taskMatchesTimeRange(task, inboxTimeRangeFilter, inboxCustomStartDate, inboxCustomEndDate)
        ),
        inboxTimeSort,
      ),
      [inboundPendingTasks, inboxCustomEndDate, inboxCustomStartDate, inboxTimeRangeFilter, inboxTimeSort],
    );
    const inboundConfirmableTasks = useMemo(
      () => sortTasksByTimeDirection(
        inboundPendingTasks.filter((task) =>
          task.sourceType !== 'event_line_notification'
          && taskMatchesTimeRange(task, inboxTimeRangeFilter, inboxCustomStartDate, inboxCustomEndDate)
        ),
        inboxTimeSort,
      ),
      [inboundPendingTasks, inboxCustomEndDate, inboxCustomStartDate, inboxTimeRangeFilter, inboxTimeSort],
    );
    const filteredOutboundPendingTasks = useMemo(
      () => sortTasksByTimeDirection(
        outboundPendingTasks.filter((task) =>
          taskMatchesTimeRange(task, inboxTimeRangeFilter, inboxCustomStartDate, inboxCustomEndDate)
        ),
        inboxTimeSort,
      ),
      [inboxCustomEndDate, inboxCustomStartDate, inboxTimeRangeFilter, inboxTimeSort, outboundPendingTasks],
    );
    const actionableInboxTasks = useMemo(
      () => [...inboundConfirmableTasks],
      [inboundConfirmableTasks],
    );
    const inboxBadgeCount = inboundPendingTasks.length + outboundPendingTasks.length;
    const inboxFeedItems = useMemo(() => {
      const items = [
        ...inboundConfirmableTasks.map((task) => ({ task, kind: 'confirmable' as const })),
        ...filteredOutboundPendingTasks.map((task) => ({ task, kind: 'outbound' as const })),
        ...inboundNotificationTasks.map((task) => ({ task, kind: 'notification' as const })),
      ];
      return items.sort((left, right) => {
        const leftTime = new Date(left.task.updatedAt || left.task.createdAt || 0).getTime();
        const rightTime = new Date(right.task.updatedAt || right.task.createdAt || 0).getTime();
        return inboxTimeSort === 'oldest' ? leftTime - rightTime : rightTime - leftTime;
      });
    }, [filteredOutboundPendingTasks, inboxTimeSort, inboundConfirmableTasks, inboundNotificationTasks]);
    const activeFormalTaskView = useMemo(() => {
      if (drillTaskViewOverride?.targetType === 'task_view') {
        return {
          id: `drill-${drillTaskViewOverride.targetId}`,
          name: drillTaskViewOverride.targetLabel || '下钻视图',
          kind: 'custom',
          description: '来自周判断卡片的临时下钻视图。',
          calendarScope: 'all',
          shareability: 'private',
          sortBy: 'updatedAt',
          sortDirection: 'desc',
          visibleFields: ['title', 'eventLine', 'sourceType', 'evidenceCount'],
          filterSet: (drillTaskViewOverride.targetFilters || {}) as TaskViewFilterSet,
          builtIn: false,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        } satisfies TaskViewDefinition;
      }
      return null;
    }, [drillTaskViewOverride]);
    const baseListTasks = tasks.filter((task) => task.status !== 'rejected' && task.status !== 'inbox');
    const participationFilteredTasks = baseListTasks.filter((task) => taskMatchesParticipationFilter(task, taskParticipationFilter));
    const taskBucketCounts = useMemo(
      () => ({
        doing: participationFilteredTasks.filter((task) => task.status !== 'done').length,
        done: participationFilteredTasks.filter((task) => task.status === 'done').length,
        overdue: participationFilteredTasks.filter((task) => isTaskOverdue(task)).length,
        all: participationFilteredTasks.length,
      }),
      [participationFilteredTasks],
    );
    const taskParticipationCounts = useMemo(
      () => ({
        all: baseListTasks.length,
        personal: baseListTasks.filter((task) => !taskIsCollaborative(task)).length,
        collab: baseListTasks.filter((task) => taskIsCollaborative(task)).length,
      }),
      [baseListTasks],
    );
    const rawListTasks = sortTasksForListView(
      participationFilteredTasks.filter((task) => {
        if (taskListFilter === 'done') return task.status === 'done';
        if (taskListFilter === 'overdue') return isTaskOverdue(task);
        if (taskListFilter === 'all') return true;
        return task.status !== 'done';
      }).filter((task) => taskMatchesTimeRange(task, taskListTimeRangeFilter, taskListCustomStartDate, taskListCustomEndDate)),
      effectiveTaskSettings.listSortMode,
    );
    const listTasks = useMemo(() => {
      let filtered = rawListTasks;
      if (taskListNameFilter) {
        filtered = filtered.filter((task) => {
          const names = Array.from(new Set((task.listNames && task.listNames.length > 0
            ? task.listNames
            : [task.listName || getListName(task.listId)]).filter(Boolean)));
          if (taskListNameFilter === TASK_LIST_FILTER_NONE) {
            return names.length === 0;
          }
          return names.includes(taskListNameFilter);
        });
      }
      if (activeFormalTaskView) {
        filtered = sortTasksByFormalView(
          filtered.filter((task) => taskMatchesFormalView(task, activeFormalTaskView)),
          activeFormalTaskView,
        );
      }
      if (taskSearchQuery.trim()) {
        const q = taskSearchQuery.trim().toLowerCase();
        filtered = filtered.filter((task) =>
          task.title.toLowerCase().includes(q)
          || (task.desc || '').toLowerCase().includes(q)
          || (task.clientName || '').toLowerCase().includes(q)
          || (task.eventLineName || '').toLowerCase().includes(q)
          || (task.ownerName || '').toLowerCase().includes(q)
          || (task.note || '').toLowerCase().includes(q)
        );
      }
      return sortTasksByTimeDirection(filtered, taskListTimeSort);
    }, [activeFormalTaskView, rawListTasks, taskListNameFilter, taskListTimeSort, taskSearchQuery]);
    useEffect(() => {
      const availableIds = new Set(actionableInboxTasks.map((task) => task.id));
      setSelectedInboxIds((prev) => prev.filter((id) => availableIds.has(id)));
    }, [actionableInboxTasks]);
    useEffect(() => {
      const availableIds = new Set(inboxFeedItems.map((item) => item.task.id));
      setExpandedInboxTaskIds((prev) => prev.filter((id) => availableIds.has(id)));
    }, [inboxFeedItems]);
    const baseCalendarTasks = tasks.filter((task) => {
      if (task.status === 'rejected') return false;
      if (hidePersonalTasks && task.scopeMode === 'PERSONAL_ONLY') return false;
      return true;
    });
    const calendarTasks = useMemo(() => {
      if (!activeFormalTaskView) return baseCalendarTasks;
      return sortTasksByFormalView(
        baseCalendarTasks.filter((task) => taskMatchesFormalView(task, activeFormalTaskView)),
        activeFormalTaskView,
      );
    }, [activeFormalTaskView, baseCalendarTasks]);
    const isAllSelected = actionableInboxTasks.length > 0 && selectedInboxIds.length === actionableInboxTasks.length;

    const tasksById = new Map(tasks.map((task) => [task.id, task]));
    const buildReviewRows = (items: WeeklyReviewTaskEntry[]): ReviewTaskRow[] =>
      items
        .map((item) => {
          const task = materializeTaskFromReviewItem(item, tasksById.get(item.taskId));
          const structuredNote = reviewForm.entriesByTaskId[item.taskId] ?? item.structuredNote ?? createEmptyReviewStructuredNote();
          return {
            task,
            note: composeReviewNoteFromStructuredFields(structuredNote, task.status) || item.note || '',
            structuredNote,
            reviewedAt: item.reviewedAt || null,
          };
        })
        .sort((left, right) => {
          const leftReviewed = Boolean(left.note.trim());
          const rightReviewed = Boolean(right.note.trim());
          if (leftReviewed !== rightReviewed) return leftReviewed ? 1 : -1;
          const leftTime = taskDateForReview(left.task)?.getTime() || 0;
          const rightTime = taskDateForReview(right.task)?.getTime() || 0;
          return leftTime - rightTime;
        });
    const workReviewRows = buildReviewRows(workReviewItems);
    const personalReviewRows = buildReviewRows(personalReviewItems);
    const activeReviewRows = reviewScope === 'work' ? workReviewRows : personalReviewRows;
    const workReviewGroups = buildReviewGroups(workReviewRows);
    const personalReviewGroups = buildReviewGroups(personalReviewRows);
    const activeReviewGroups = reviewScope === 'work' ? workReviewGroups : personalReviewGroups;
    useEffect(() => {
      if (!expandedReviewGroupId) return;
      if (!activeReviewGroups.some((group) => group.id === expandedReviewGroupId)) {
        setExpandedReviewGroupId(null);
      }
    }, [activeReviewGroups, expandedReviewGroupId]);

    const ownerCollaborator = editingTask.ownerId
      ? editingTask.collaborators.find((item) => item.id === editingTask.ownerId) || null
      : null;
    const selectedTaskCollaborators = ownerCollaborator
      ? editingTask.collaborators.filter((item) => item.id !== ownerCollaborator.id)
      : editingTask.collaborators;
    const collaboratorNames = editingTask.collaborators.map((item) => item.fullName);
    const selectedTaskTags = taskTags.filter((tag) => editingTask.tagIds.includes(tag.id));
    const selectedTaskListIds = useMemo(
      () => Array.from(new Set((editingTask.listIds || []).filter(Boolean))),
      [editingTask.listIds],
    );
    const visibleOrgTaskLists = useMemo(() => {
      const uniqueByName = new Map<string, TaskList>();
      orgTaskLists.forEach((list) => {
        const key = (list.name || '').trim().toLowerCase() || list.id;
        const current = uniqueByName.get(key);
        if (!current) {
          uniqueByName.set(key, list);
          return;
        }
        if (selectedTaskListIds.includes(current.id)) return;
        if (selectedTaskListIds.includes(list.id) || (!current.isDefault && list.isDefault)) {
          uniqueByName.set(key, list);
        }
      });
      return Array.from(uniqueByName.values()).sort((left, right) => {
        if (left.isDefault !== right.isDefault) return left.isDefault ? -1 : 1;
        return left.name.localeCompare(right.name, 'zh-Hans-CN');
      });
    }, [orgTaskLists, selectedTaskListIds]);
    const selectedTaskLists = useMemo(
      () => selectedTaskListIds
        .map((listId) => visibleOrgTaskLists.find((list) => list.id === listId) || orgTaskLists.find((list) => list.id === listId) || null)
        .filter((list): list is TaskList => Boolean(list)),
      [orgTaskLists, selectedTaskListIds, visibleOrgTaskLists],
    );
    const normalizedTaskListQuery = taskListQuery.trim().toLowerCase();
    const filteredTaskListOptions = visibleOrgTaskLists.filter((list) => {
      if (!normalizedTaskListQuery) return true;
      return list.name.toLowerCase().includes(normalizedTaskListQuery);
    });
    const hasExactTaskListMatch = visibleOrgTaskLists.some((list) => list.name.trim().toLowerCase() === normalizedTaskListQuery);
    useEffect(() => {
      if (typeof window === 'undefined') return;
      (window as typeof window & { __YIYU_DEBUG_TASK_LISTS__?: Record<string, unknown> }).__YIYU_DEBUG_TASK_LISTS__ = {
        isTaskModalOpen,
        taskListsCount: taskLists.length,
        taskListSamples: taskLists.slice(0, 20).map((item) => ({
          id: item.id,
          name: item.name,
          scope: item.scope,
          archivedAt: item.archivedAt,
          isDefault: item.isDefault,
        })),
        activeTaskListsCount: activeTaskLists.length,
        orgTaskListsCount: orgTaskLists.length,
        orgTaskListNames: orgTaskLists.map((item) => `${item.scope}:${item.name}:${item.id}`),
        visibleOrgTaskListsCount: visibleOrgTaskLists.length,
        visibleOrgTaskListNames: visibleOrgTaskLists.map((item) => item.name),
        selectedTaskListIds,
        selectedTaskListNames: selectedTaskLists.map((item) => item.name),
        taskListQuery,
        filteredTaskListOptionNames: filteredTaskListOptions.map((item) => item.name),
      };
    }, [
      activeTaskLists.length,
      filteredTaskListOptions,
      isTaskModalOpen,
      orgTaskLists,
      selectedTaskListIds,
      selectedTaskLists,
      taskListQuery,
      taskLists.length,
      visibleOrgTaskLists,
    ]);
    useEffect(() => {
      if (!isTaskListMenuOpen) {
        setTaskListQuery('');
      }
    }, [isTaskListMenuOpen]);
    useEffect(() => {
      if (!taskListNameFilter) return;
      if (taskListNameFilter === TASK_LIST_FILTER_NONE) return;
      const exists = visibleOrgTaskLists.some((list) => list.name === taskListNameFilter);
      if (!exists) {
        setTaskListNameFilter('');
      }
    }, [taskListNameFilter, visibleOrgTaskLists]);
    const pendingTaskAttachmentKeys = new Set<string>();
    const pendingTaskAttachmentItems = pendingTaskAttachmentFiles.filter((file) => {
      const key = `${file.name}::${file.size}::${file.lastModified}`;
      if (pendingTaskAttachmentKeys.has(key)) return false;
      pendingTaskAttachmentKeys.add(key);
      return true;
    });
    const taskClientOptions = clients
      .map((client) => ({ id: client.id, name: client.name, label: client.name, alias: client.alias }))
      .sort((left, right) => left.label.localeCompare(right.label, 'zh-CN'));
    const selectedTaskClientLabel = taskClientOptions.find((item) => item.id === editingTask.clientId)?.label || '';
    const applyClientInferenceToDraft = (title: string, desc: string, prev: TaskEditorState) => {
      if (prev.clientTouched || prev.scopeMode === 'PERSONAL_ONLY') return null;
      const nextClient = inferTaskClient({
        title,
        desc,
        clients,
        currentClientId,
        organizationName: organizationTaskName,
      });
      if (nextClient.confidence === 'high' || nextClient.confidence === 'medium') {
        return {
          clientId: nextClient.clientId,
          clientConfidence: nextClient.confidence,
          clientReason: nextClient.reason,
        } as const;
      }
      if (nextClient.confidence === 'low' && prev.clientConfidence !== 'low') {
        return {
          clientConfidence: 'low' as const,
          clientReason: nextClient.reason,
        } as const;
      }
      return null;
    };
    const activeTaskDnaModules =
      editingTask.clientId && editingTask.clientId === workspace?.client.id
        ? workspace?.dnaModules || []
        : (editingTask.clientId ? taskClientDnaCache[editingTask.clientId] || [] : []);
    const effectiveTaskClientId = editingTask.clientId || organizationClientId;
    const activeProjectStructure =
      effectiveTaskClientId && effectiveTaskClientId === workspace?.client.id
        ? {
            modules: workspace?.projectModules || [],
            flows: workspace?.projectFlows || [],
          }
        : (effectiveTaskClientId
          ? projectStructureCache[effectiveTaskClientId] || { modules: [], flows: [] }
          : { modules: [], flows: [] });
    const taskProjectModuleOptions = activeProjectStructure.modules;
    const taskProjectFlowOptions = activeProjectStructure.flows.filter((flow: ProjectFlow) => {
      if (!editingTask.projectModuleId) return true;
      return flow.moduleId === editingTask.projectModuleId;
    });
    const sortedEventLines = useMemo(
      () =>
        [...eventLines].sort((left, right) => {
          const statusOrder = { active: 0, blocked: 1, paused: 2, done: 3, archived: 4 } as const;
          const statusGap = (statusOrder[left.status] ?? 9) - (statusOrder[right.status] ?? 9);
          if (statusGap !== 0) return statusGap;
          return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
        }),
      [eventLines],
    );
    const eventLineMemberLabelById = useMemo(
      () => new Map(eventLineMemberOptions.map((item) => [item.id, item.fullName])),
      [eventLineMemberOptions],
    );
    const eventLineProjectOptions = useMemo(() => {
      const labelById = new Map<string, string>();
      sortedEventLines.forEach((item) => {
        const clientId = (item.primaryClientId || '').trim();
        if (!clientId) return;
        const matchedClient = clients.find((client) => (client.id || '').trim() === clientId);
        const matchedLabel = (matchedClient?.name || '').trim();
        const cloudLabel = item.primaryClientName?.trim();
        const nextLabel = matchedLabel || cloudLabel || `未命名${terminology.singularLabel}`;
        if (!labelById.has(clientId) || labelById.get(clientId) === `未命名${terminology.singularLabel}`) {
          labelById.set(clientId, nextLabel);
        }
      });
      return Array.from(labelById.entries())
        .map(([id, label]) => ({ id, label }))
        .sort((left, right) => left.label.localeCompare(right.label, 'zh-Hans-CN'));
    }, [clients, sortedEventLines]);
    const eventLineEditorProjectOptions = useMemo<EventLineProjectOption[]>(() => {
      const optionMap = new Map<string, string>();
      clients.forEach((client) => {
        const clientId = (client.id || '').trim();
        const clientName = (client.name || '').trim();
        if (!clientId || !clientName) return;
        optionMap.set(clientId, clientName);
      });
      eventLineProjectOptions.forEach((option) => {
        if (!optionMap.has(option.id)) {
          optionMap.set(option.id, option.label);
        }
      });
      return Array.from(optionMap.entries())
        .map(([id, label]) => ({ id, label }))
        .sort((left, right) => left.label.localeCompare(right.label, 'zh-Hans-CN'));
    }, [clients, eventLineProjectOptions]);
    const filteredEventLines = useMemo(() => {
      const visibleEventLines = sortedEventLines.filter((item) => {
        if (!currentSessionUser) return false;
        if (currentSessionUser.primaryRole === 'admin') return true;
        const visibleUserIds = new Set([
          ...(item.participantIds || []).filter(Boolean),
          ...(item.ownerIds || []).filter(Boolean),
          item.ownerId || '',
        ]);
        return visibleUserIds.has(currentSessionUser.id);
      });
      if (eventLineProjectFilterId === '__all__') return visibleEventLines;
      return visibleEventLines.filter((item) => (item.primaryClientId || '').trim() === eventLineProjectFilterId);
    }, [currentSessionUser, eventLineProjectFilterId, sortedEventLines]);
    useEffect(() => {
      if (typeof window === 'undefined') return;
      if (eventLineProjectFilterId === '__all__') {
        window.localStorage.removeItem(EVENT_LINE_PROJECT_FILTER_STORAGE_KEY);
        return;
      }
      window.localStorage.setItem(EVENT_LINE_PROJECT_FILTER_STORAGE_KEY, eventLineProjectFilterId);
    }, [eventLineProjectFilterId]);
    useEffect(() => {
      if (eventLineProjectFilterId === '__all__') return;
      const exists = eventLineProjectOptions.some((option) => option.id === eventLineProjectFilterId);
      if (!exists) {
        setEventLineProjectFilterId('__all__');
      }
    }, [eventLineProjectFilterId, eventLineProjectOptions]);
    const eventLineById = useMemo(
      () =>
        sortedEventLines.reduce<Record<string, EventLine>>((acc, item) => {
          acc[item.id] = item;
          return acc;
        }, {}),
      [sortedEventLines],
    );
    const taskEventLineOptions = useMemo(() => {
      const activeLines = sortedEventLines.filter((item) => item.status !== 'archived' && item.status !== 'done');
      const base = !editingTask.clientId ? activeLines
        : activeLines.filter((item) => (item.primaryClientId || '').trim() === editingTask.clientId);
      if (editingTask.eventLineId && !base.some((item) => item.id === editingTask.eventLineId)) {
        const selected = sortedEventLines.find((item) => item.id === editingTask.eventLineId);
        return selected ? [selected, ...base] : base;
      }
      return base;
    }, [editingTask.clientId, editingTask.eventLineId, sortedEventLines]);
    const formatTaskEventLineOptionLabel = useCallback(
      (line: EventLine) => (line.primaryClientName ? `${line.name} · ${line.primaryClientName}` : line.name),
      [],
    );
    const handleTaskEventLineChange = useCallback((eventLineId: string) => {
      const selectedLine = sortedEventLines.find((item) => item.id === eventLineId) || null;
      const selectedClientId = (selectedLine?.primaryClientId || '').trim();
      if (selectedClientId) {
        void ensureTaskProjectStructureLoaded(selectedClientId);
      }
      setEditingTask((prev) => {
        const shouldAutofillClient = Boolean(selectedLine && selectedClientId);
        const clientChanged = shouldAutofillClient && selectedClientId !== prev.clientId;
        const selectedClientLabel =
          taskClientOptions.find((item) => item.id === selectedClientId)?.name
          || selectedLine?.primaryClientName
          || `已关联${terminology.singularLabel}`;
        return {
          ...prev,
          clientId: shouldAutofillClient ? selectedClientId : prev.clientId,
          clientTouched: shouldAutofillClient ? true : prev.clientTouched,
          clientConfidence: shouldAutofillClient ? 'manual' : prev.clientConfidence,
          clientReason: shouldAutofillClient
            ? `已根据事件线自动回填${terminology.singularLabel}：${selectedClientLabel}。`
            : prev.clientReason,
          eventLineId,
          eventLineTouched: true,
          eventLineReason: eventLineId
            ? `已关联事件线：${selectedLine?.name || '已选择事件线'}。`
            : '可选：把任务挂到一条持续推进的事件线上，后续复盘会按事件线聚合。',
          projectModuleId: clientChanged ? '' : prev.projectModuleId,
          projectModuleTouched: clientChanged ? false : prev.projectModuleTouched,
          projectModuleReason: clientChanged ? `可选：把任务挂到当前${terminology.singularLabel}下的具体${terminology.structureLabel}。` : prev.projectModuleReason,
          projectFlowId: clientChanged ? '' : prev.projectFlowId,
          projectFlowTouched: clientChanged ? false : prev.projectFlowTouched,
          projectFlowReason: clientChanged ? '可选：把任务进一步挂到标准流程，后续复盘和日历会更贴近业务动作。' : prev.projectFlowReason,
        };
      });
    }, [ensureTaskProjectStructureLoaded, sortedEventLines, taskClientOptions]);
    const editingTaskRecord = useMemo(
      () => (editingTask.id ? tasks.find((item: Task) => item.id === editingTask.id) || null : null),
      [editingTask.id, tasks],
    );
    const selectedEventLineSummary = sortedEventLines.find((item) => item.id === editingTask.eventLineId) || null;
    const taskClientPreview = useMemo(
      () =>
        buildTaskProjectPreview({
          clientId: editingTask.clientId,
          projectModuleId: editingTask.projectModuleId,
          projectFlowId: editingTask.projectFlowId,
          taskTitle: editingTask.title,
          taskDescription: editingTask.desc,
          attachmentCount: (editingTaskRecord?.attachments?.length || 0) + (pendingTaskArchiveText.trim() ? 1 : 0),
          attachmentTitles: [
            ...((editingTaskRecord?.attachments || []).map((item: TaskAttachmentRecord) => item.title).filter(Boolean)),
            ...(pendingTaskArchiveText.trim()
              ? [inferTaskArchiveDocumentTitle({
                  taskTitle: editingTask.title,
                  clientName: clients.find((item: ClientSummary) => item.id === editingTask.clientId)?.name || null,
                  eventLineName: selectedEventLineSummary?.name || null,
                  content: pendingTaskArchiveText,
                })]
              : []),
          ],
          eventLine: selectedEventLineSummary,
          clients,
          workspace,
          dnaModules: activeTaskDnaModules,
          projectStructure: activeProjectStructure,
          terminology,
        }),
      [
        activeProjectStructure,
        activeTaskDnaModules,
        clients,
        editingTask.clientId,
        editingTask.desc,
        editingTask.projectFlowId,
        editingTask.projectModuleId,
        editingTask.title,
        editingTaskRecord?.attachments?.length,
        pendingTaskArchiveText,
        selectedEventLineSummary,
        terminology,
        workspace,
      ],
    );
    const closeReviewDrillTarget = () => {
      setActiveReviewDrillTarget(null);
      setDrillTaskViewOverride(null);
    };
    const handleReviewDashboardDrillTarget = async (target: ReviewDashboardCardTarget) => {
      setIsLoadingReviewDrillTarget(true);
      try {
        const response = await getReviewDashboardDrillTarget({
          targetType: target.targetType,
          targetId: target.targetId,
          targetLabel: target.targetLabel,
          targetFilters: target.targetFilters,
        });
        setActiveReviewDrillTarget(response);
        if (target.targetType === 'task_view') {
          setDrillTaskViewOverride(target);
          setTaskViewMode('list');
        }
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '打开判断下钻失败');
      } finally {
        setIsLoadingReviewDrillTarget(false);
      }
    };
    useEffect(() => {
      if (!isTaskModalOpen) {
        setTaskEventLineClarificationDraft(buildEventLineClarificationDraft(null));
        setIsTaskEventLineClarifyMode(false);
        setIsGeneratingTaskEventLineClarification(false);
        return;
      }
      setTaskEventLineClarificationDraft(buildEventLineClarificationDraft(selectedEventLineSummary));
      setIsTaskEventLineClarifyMode(false);
    }, [isTaskModalOpen, selectedEventLineSummary]);
    useEffect(() => {
      if (!isTaskModalOpen || !editingTask.id || editingTask.scopeMode === 'PERSONAL_ONLY') {
        setTaskContextPreview(null);
        setIsTaskContextPreviewLoading(false);
        return;
      }
      let cancelled = false;
      setIsTaskContextPreviewLoading(true);
      void getTaskContextPreview(editingTask.id)
        .then((preview) => {
          if (!cancelled) {
            setTaskContextPreview(preview);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setTaskContextPreview(null);
          }
        })
        .finally(() => {
          if (!cancelled) {
            setIsTaskContextPreviewLoading(false);
          }
        });
      return () => {
        cancelled = true;
      };
    }, [editingTask.id, editingTask.scopeMode, isTaskModalOpen]);
    const eventLineScopeHint = editingTask.clientId
      ? selectedTaskClientLabel
        ? `系统会先在"${selectedTaskClientLabel}"下建议事件线。`
        : `系统会先在当前${terminology.singularLabel}下建议事件线。`
      : `系统会先尝试识别${terminology.singularLabel}，再建议事件线。`;
    const clientConfidenceBadge = labelTaskClientConfidence(editingTask.clientConfidence);
    const availableMentionOptions = mentionOptions.filter((candidate) => candidate.id !== ownerCollaborator?.id);
    const selectedTaskCollaboratorIds = new Set(selectedTaskCollaborators.map((item) => item.id));
    const toggleTaskCollaborator = (candidate: MentionCandidate) => {
      setEditingTask((prev) => {
        const alreadySelected = prev.collaborators.some((item) => item.id === candidate.id);
        const nextCollaborators = alreadySelected
          ? prev.collaborators.filter((item) => item.id !== candidate.id)
          : [...prev.collaborators, candidate];
        return {
          ...prev,
          collaborators: nextCollaborators,
        };
      });
    };
    const removeTaskOwner = () => {
      setEditingTask((prev) => ({
        ...prev,
        ownerId: '',
      }));
    };
    const removePendingTaskAttachment = (target: File) => {
      setPendingTaskAttachmentFiles((prev) => prev.filter((file) => !(
        file.name === target.name
        && file.size === target.size
        && file.lastModified === target.lastModified
      )));
    };
    const handleCreateTaskListFromQuery = async () => {
      const trimmedName = taskListQuery.trim();
      if (!trimmedName) return;
      setIsCreatingTaskList(true);
      try {
        const created = await createTaskList({
          name: trimmedName,
          description: null,
          scope: 'org',
        });
        await loadTaskBlock();
        setEditingTask((prev) => {
          const nextListIds = Array.from(new Set([...(prev.listIds || []), created.id]));
          return {
            ...prev,
            listId: nextListIds[0] || created.id,
            listIds: nextListIds,
          };
        });
        setTaskListQuery('');
        setIsTaskListMenuOpen(true);
        flash('success', `已创建清单“${created.name}”`);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '清单创建失败');
      } finally {
        setIsCreatingTaskList(false);
      }
    };
    const handleTaskListQueryChange = (value: string) => {
      setTaskListQuery(value);
      setIsTaskListMenuOpen(true);
    };
    const handleSelectTaskList = (list: TaskList) => {
      setEditingTask((prev) => {
        const exists = (prev.listIds || []).includes(list.id);
        const nextListIds = exists
          ? (prev.listIds || []).filter((item) => item !== list.id)
          : [...(prev.listIds || []), list.id];
        return {
          ...prev,
          listId: nextListIds[0] || '',
          listIds: nextListIds,
        };
      });
      setTaskListQuery('');
      setIsTaskListMenuOpen(true);
    };
    const duePickerSummaryLabel = formatTaskDuePickerSummaryLabel(
      editingTask.startDate,
      editingTask.startTime,
      editingTask.dueDate,
      editingTask.dueTime,
      editingTask.hasSpecificDueTime,
      editingTask.durationMinutes,
    );
    const editingTaskPriorityMeta = taskPriorityUi(editingTask.priority);
    const duePickerCalendarCells = useMemo(() => buildCalendarCells(duePickerMonth), [duePickerMonth]);

    useEffect(() => {
      if (!isTaskModalOpen) return;
      const moduleStillExists = !editingTask.projectModuleId || taskProjectModuleOptions.some((item) => item.id === editingTask.projectModuleId);
      const flowStillExists = !editingTask.projectFlowId || taskProjectFlowOptions.some((item) => item.id === editingTask.projectFlowId);
      if (moduleStillExists && flowStillExists) return;
      setEditingTask((prev) => ({
        ...prev,
        projectModuleId: moduleStillExists ? prev.projectModuleId : '',
        projectModuleReason: moduleStillExists ? prev.projectModuleReason : '当前项目下还没有选择任务模块，或原模块已失效。',
        projectFlowId: flowStillExists ? prev.projectFlowId : '',
        projectFlowReason: flowStillExists ? prev.projectFlowReason : '当前模块下还没有选择流程，或原流程已失效。',
      }));
    }, [editingTask.projectFlowId, editingTask.projectModuleId, isTaskModalOpen, taskProjectFlowOptions, taskProjectModuleOptions]);

    useEffect(() => {
      if (!isTaskModalOpen || !editingTask.clientId) return;
      const inferredModule = !editingTask.projectModuleTouched
        ? inferTaskProjectModule({
            title: editingTask.title,
            desc: editingTask.desc,
            modules: taskProjectModuleOptions,
            eventLine: selectedEventLineSummary,
          })
        : null;
      const selectedModuleId = inferredModule?.projectModuleId || editingTask.projectModuleId;
      const inferredFlow = !editingTask.projectFlowTouched
        ? inferTaskProjectFlow({
            title: editingTask.title,
            desc: editingTask.desc,
            flows: activeProjectStructure.flows,
            selectedModuleId,
            eventLine: selectedEventLineSummary,
          })
        : null;
      if (!inferredModule && !inferredFlow) return;
      setEditingTask((prev) => {
        const updates: Partial<TaskEditorState> = {};
        if (!prev.projectModuleTouched && inferredModule && (prev.projectModuleId !== inferredModule.projectModuleId || prev.projectModuleReason !== inferredModule.reason)) {
          updates.projectModuleId = inferredModule.projectModuleId;
          updates.projectModuleReason = inferredModule.reason;
        }
        const nextModuleId = (updates.projectModuleId ?? prev.projectModuleId) || '';
        const nextFlowReason = inferredFlow?.reason ?? prev.projectFlowReason;
        if (!prev.projectFlowTouched && inferredFlow) {
          const shouldResetFlow = prev.projectFlowId && inferredFlow.projectFlowId !== prev.projectFlowId && nextModuleId !== prev.projectModuleId;
          if (prev.projectFlowId !== inferredFlow.projectFlowId || prev.projectFlowReason !== nextFlowReason || shouldResetFlow) {
            updates.projectFlowId = inferredFlow.projectFlowId;
            updates.projectFlowReason = nextFlowReason;
          }
        }
        return Object.keys(updates).length > 0 ? { ...prev, ...updates } : prev;
      });
    }, [
      activeProjectStructure.flows,
      editingTask.clientId,
      editingTask.desc,
      editingTask.projectFlowId,
      editingTask.projectFlowReason,
      editingTask.projectFlowTouched,
      editingTask.projectModuleId,
      editingTask.projectModuleReason,
      editingTask.projectModuleTouched,
      editingTask.title,
      isTaskModalOpen,
      selectedEventLineSummary,
      taskProjectModuleOptions,
    ]);

    const handleOpenReviewHistory = async () => {
      setIsReviewHistoryOpen((prev) => !prev);
      if (isReviewHistoryOpen || reviewHistory.length > 0) return;
      try {
        await loadReviewHistoryBlock();
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '历史复盘加载失败');
      }
    };

    const handleSelectHistoricalReview = async (weekLabel: string) => {
      try {
        clearReviewTasksDirty();
        setSavedReviewGroupId(null);
        const response = await loadReviewBlock(weekLabel);
        setIsReviewHistoryOpen(false);
        flash('success', `已切换到${weekLabelCN(response.currentReview?.weekLabel || weekLabel)}的复盘。`);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '历史复盘打开失败');
      }
    };

    const openEventLineDetail = async (eventLineId: string, options?: { clarify?: boolean }) => {
      setIsEventLineBusy(true);
      setEventLineEditorSaveNotice(null);
      try {
        const detail = await getEventLine(eventLineId);
        setActiveEventLine(detail);
        setEventLineEditorDraft(buildEventLineEditorDraftFromDetail(detail));
        setIsEventLineEditorOpen(true);
        setIsEventLineClarifyMode(Boolean(options?.clarify));
        return detail;
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '事件线加载失败');
        return null;
      } finally {
        setIsEventLineBusy(false);
      }
    };

    const handleOpenEventLineCreate = () => {
      const defaultClientId = eventLineProjectFilterId !== '__all__' ? eventLineProjectFilterId : '';
      const defaultOwnerId = currentSessionUser?.id || '';
      setEventLineEditorSaveNotice(null);
      setEventLineEditorDraft(buildEmptyEventLineEditorDraft({
        primaryClientId: defaultClientId,
        kind: defaultClientId ? 'project_line' : 'custom',
        ownerId: defaultOwnerId,
        ownerIds: defaultOwnerId ? [defaultOwnerId] : [],
      }));
      setIsEventLineCreateOpen(true);
    };

    const handleQuickCreateEventLineProject = async (initialName?: string) => {
      const normalizedName = (initialName || '').trim();
      if (!normalizedName) {
        flash('error', `请先输入${terminology.singularLabel}名称`);
        return;
      }
      const existingClient = clients.find((item) => item.name.trim().toLowerCase() === normalizedName.toLowerCase());
      if (existingClient) {
        setEventLineEditorDraft((prev) => ({ ...prev, primaryClientId: existingClient.id }));
        flash('success', `已关联现有${terminology.singularLabel}“${existingClient.name}”`);
        return;
      }
      try {
        const savedClient = await createClient({
          name: normalizedName,
          alias: normalizedName,
          domain: terminology.singularLabel,
          type: terminology.singularLabel,
          intro: `等待导入已有资料，系统将自动分析归档并建立${terminology.singularLabel}上下文。`,
          stage: '待导入资料',
        });
        const nextClients = await getClients();
        setClients(nextClients);
        setEventLineEditorDraft((prev) => ({ ...prev, primaryClientId: savedClient.id }));
        flash('success', `${terminology.singularLabel}“${savedClient.name}”已创建并关联到当前事件线`);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : `创建${terminology.singularLabel}失败`);
      }
    };

    const handleSaveEventLineEditor = async () => {
      if (!activeEventLine) return;
      const ownerIds = Array.from(
        new Set(
          (
            eventLineEditorDraft.ownerIds?.length
              ? eventLineEditorDraft.ownerIds
              : eventLineEditorDraft.ownerId
                ? [eventLineEditorDraft.ownerId]
                : activeEventLine.eventLine.ownerIds?.length
                  ? activeEventLine.eventLine.ownerIds
                  : activeEventLine.eventLine.ownerId
                    ? [activeEventLine.eventLine.ownerId]
                    : currentSessionUser?.id
                      ? [currentSessionUser.id]
                      : []
          ).filter(Boolean),
        ),
      );
      const linkedParticipantIds = new Set<string>();
      activeEventLine.tasks.forEach((task) => {
        if (task.ownerId) linkedParticipantIds.add(task.ownerId);
        task.collaborators.forEach((item) => {
          if (item.id) linkedParticipantIds.add(item.id);
        });
      });
      const participantIds = Array.from(
        new Set(
          eventLineEditorDraft.participantIds
            .filter(Boolean)
            .filter((id) => !linkedParticipantIds.has(id) && !ownerIds.includes(id)),
        ),
      );
      const ownerId = ownerIds[0] || null;
      setIsSavingEventLineEditor(true);
      try {
        const updated = await updateEventLine(activeEventLine.eventLine.id, {
          name: eventLineEditorDraft.name.trim(),
          kind: eventLineEditorDraft.kind,
          primaryClientId: eventLineEditorDraft.primaryClientId || null,
          summary: eventLineEditorDraft.summary.trim() || null,
          stage: eventLineEditorDraft.stage.trim() || null,
          currentBlocker: eventLineEditorDraft.currentBlocker.trim() || null,
          recentDecision: eventLineEditorDraft.recentDecision.trim() || null,
          nextStep: eventLineEditorDraft.nextStep.trim() || null,
          participantIds,
          ownerIds,
          ownerId,
        });
        setEventLines((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
        const refreshed = await getEventLine(updated.id);
        setActiveEventLine(refreshed);
        setEventLineEditorDraft(buildEventLineEditorDraftFromDetail(refreshed));
        setEventLineEditorSaveNotice('事件线已保存，最新改动已经同步到当前详情。');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '事件线保存失败');
      } finally {
        setIsSavingEventLineEditor(false);
      }
    };

    const handleMarkNotificationRead = async (taskId: string) => {
      if (!taskId) return false;
      setTransitioningInboxTaskIds((prev) => Array.from(new Set([...prev, taskId])));
      try {
        await markTaskNotificationRead(taskId);
        await loadTaskBlock();
        flash('success', '通知已标记为已阅。');
        return true;
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '通知状态更新失败');
        return false;
      } finally {
        setTransitioningInboxTaskIds((prev) => prev.filter((id) => id !== taskId));
      }
    };

    const handleCreateEventLineFromWorkspace = async () => {
      if (!eventLineEditorDraft.name.trim()) {
        flash('error', '请先填写事件线名称。');
        return;
      }
      setIsCreatingEventLine(true);
      try {
        const created = await createEventLine({
          name: eventLineEditorDraft.name.trim(),
          kind: eventLineEditorDraft.kind,
          status: 'active',
          primaryClientId: eventLineEditorDraft.primaryClientId || null,
          summary: eventLineEditorDraft.summary.trim() || null,
          stage: eventLineEditorDraft.stage.trim() || null,
          currentBlocker: eventLineEditorDraft.currentBlocker.trim() || null,
          recentDecision: eventLineEditorDraft.recentDecision.trim() || null,
          nextStep: eventLineEditorDraft.nextStep.trim() || null,
          participantIds: [],
          ownerIds: eventLineEditorDraft.ownerIds?.length
            ? eventLineEditorDraft.ownerIds
            : eventLineEditorDraft.ownerId
              ? [eventLineEditorDraft.ownerId]
              : currentSessionUser?.id
                ? [currentSessionUser.id]
                : [],
          ownerId: eventLineEditorDraft.ownerIds?.[0] || eventLineEditorDraft.ownerId || currentSessionUser?.id || null,
        });
        setEventLines((prev) => [created, ...prev.filter((item) => item.id !== created.id)]);
        setIsEventLineCreateOpen(false);
        flash('success', '事件线已创建');
        await openEventLineDetail(created.id);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '事件线创建失败');
      } finally {
        setIsCreatingEventLine(false);
      }
    };

    const handleEventLineStatusChange = async (
      targetEventLine: EventLine,
      nextStatus: Extract<EventLine['status'], 'active' | 'paused' | 'blocked' | 'done'>,
    ) => {
      if (targetEventLine.status === nextStatus || isDeletingEventLine) return;
      setIsDeletingEventLine(true);
      try {
        const updated = await updateEventLine(targetEventLine.id, { status: nextStatus });
        setEventLines((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
        if (activeEventLine?.eventLine.id === updated.id) {
          const refreshed = await getEventLine(updated.id);
          setActiveEventLine(refreshed);
          setEventLineEditorDraft(buildEventLineEditorDraftFromDetail(refreshed));
        }
        flash('success', `事件线状态已切换为${{ active: '进行中', paused: '暂停', blocked: '阻塞', done: '完成' }[nextStatus]}`);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '事件线状态更新失败');
      } finally {
        setIsDeletingEventLine(false);
      }
    };

    const handleOpenEventLineMeeting = (meetingId: string, label: string) => {
      setIsEventLineEditorOpen(false);
      setActiveEventLine(null);
      setActiveTab('client_workspace');
      setGrowthContextJump({
        requestId: `event-line-meeting-${meetingId}-${Date.now()}`,
        context: {
          objectType: 'meeting',
          objectId: meetingId,
          label,
          subtitle: '事件线关联会议',
          tab: 'meeting',
          statusLabel: '会议',
        },
      });
    };

    const handleAddEventLineNoteFromEditor = async (text: string) => {
      if (!activeEventLine) return;
      await addEventLineNote(activeEventLine.eventLine.id, text);
      const refreshed = await getEventLine(activeEventLine.eventLine.id);
      setActiveEventLine(refreshed);
      setEventLineEditorDraft(buildEventLineEditorDraftFromDetail(refreshed));
      flash('success', '备注已添加');
    };

    const filteredExpenseEvidenceRecords = useMemo(() => {
      const needle = expenseEvidenceQuery.trim().toLowerCase();
      if (!needle) return expenseEvidenceRecords;
      return expenseEvidenceRecords.filter((item) => {
        const haystacks = [
          item.displayTitle,
          item.sourceTitle,
          item.applicantUserName,
          item.normalizedCategory,
          item.summary,
          ...(item.tags || []),
        ]
          .filter(Boolean)
          .map((value) => String(value).toLowerCase());
        return haystacks.some((value) => value.includes(needle));
      });
    }, [expenseEvidenceQuery, expenseEvidenceRecords]);

    const loadExpenseEvidenceRecordsForContext = useCallback(async (workObjectId: string, query = '') => {
      setIsLoadingExpenseEvidenceRecords(true);
      try {
        const records = await listExpenseEvidences(workObjectId, { query, limit: 200 });
        setExpenseEvidenceRecords(records);
        return records;
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '票据池读取失败');
        setExpenseEvidenceRecords([]);
        return [];
      } finally {
        setIsLoadingExpenseEvidenceRecords(false);
      }
    }, [flash]);

    const loadLinkedExpenseEvidenceIds = useCallback(async (context?: ExpenseEvidenceModalContext | null) => {
      if (!context?.eventLineId && !context?.taskId) {
        setLinkedExpenseEvidenceIds([]);
        return [];
      }
      try {
        if (context?.taskId) {
          const links = await listTaskExpenseEvidences(context.taskId);
          setLinkedExpenseEvidenceIds(links.map((item) => item.evidenceId));
          return links;
        }
        if (context?.eventLineId) {
          const links = await listEventLineExpenseEvidences(context.eventLineId);
          setLinkedExpenseEvidenceIds(links.map((item) => item.evidenceId));
          return links;
        }
        setLinkedExpenseEvidenceIds([]);
        return [];
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '票据关联读取失败');
        setLinkedExpenseEvidenceIds([]);
        return [];
      }
    }, [flash]);

    const refreshActiveEventLineAfterEvidenceChange = useCallback(async (eventLineId?: string | null) => {
      if (!eventLineId || activeEventLine?.eventLine.id !== eventLineId) return;
      const refreshed = await getEventLine(eventLineId);
      setActiveEventLine(refreshed);
      setEventLineEditorDraft(buildEventLineEditorDraftFromDetail(refreshed));
    }, [activeEventLine?.eventLine.id]);

    const closeExpenseEvidenceModal = useCallback(() => {
      setIsExpenseEvidenceModalOpen(false);
      setExpenseEvidenceContext(null);
      setExpenseEvidenceQuery('');
      setExpenseEvidenceImportSearchDraft(DEFAULT_EXPENSE_IMPORT_SEARCH_DRAFT);
      setExpenseEvidenceImportSearchResult(null);
      setSelectedExpenseEvidenceImportIds([]);
      setLinkedExpenseEvidenceIds([]);
    }, []);

    const openExpenseEvidenceModal = useCallback(async (context: ExpenseEvidenceModalContext) => {
      if (!context.workObjectId) {
        flash('error', `请先关联${terminology.singularLabel}，再整理票据证明。`);
        return;
      }
      setExpenseEvidenceContext(context);
      setExpenseEvidenceQuery('');
      setExpenseEvidenceImportSearchDraft(DEFAULT_EXPENSE_IMPORT_SEARCH_DRAFT);
      setExpenseEvidenceImportSearchResult(null);
      setSelectedExpenseEvidenceImportIds([]);
      setLinkedExpenseEvidenceIds([]);
      setIsExpenseEvidenceModalOpen(true);
      void Promise.all([
        loadOrgDingtalkFinanceIntegrationBlock().catch(() => DEFAULT_ORG_DINGTALK_FINANCE_INTEGRATION),
        loadExpenseEvidenceRecordsForContext(context.workObjectId),
        loadLinkedExpenseEvidenceIds(context),
      ]);
    }, [flash, loadExpenseEvidenceRecordsForContext, loadLinkedExpenseEvidenceIds, terminology.singularLabel]);

    const handleRunExpenseEvidenceImportSearch = useCallback(async () => {
      if (!expenseEvidenceContext?.workObjectId) return;
      setIsExpenseEvidenceImportSearchLoading(true);
      try {
        const result = await searchExpenseEvidenceImports(expenseEvidenceContext.workObjectId, expenseEvidenceImportSearchDraft);
        setExpenseEvidenceImportSearchResult(result);
        setSelectedExpenseEvidenceImportIds([]);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '可导入票据搜索失败');
      } finally {
        setIsExpenseEvidenceImportSearchLoading(false);
      }
    }, [expenseEvidenceContext?.workObjectId, expenseEvidenceImportSearchDraft, flash]);

    const handleImportSelectedExpenseEvidence = useCallback(async () => {
      if (!expenseEvidenceContext?.workObjectId || !expenseEvidenceImportSearchResult) return;
      const selectedItems = expenseEvidenceImportSearchResult.items.filter(
        (item) => selectedExpenseEvidenceImportIds.includes(item.sourceInstanceId) && !item.importedEvidenceId,
      );
      if (selectedItems.length === 0) {
        flash('info', '请先勾选要导入的票据记录。');
        return;
      }
      const payload: ExpenseEvidenceImportPayload = {
        items: selectedItems.map((item) => ({
          sourceInstanceId: item.sourceInstanceId,
          sourceTemplateCode: item.sourceTemplateCode,
          sourceTemplateName: item.sourceTemplateName,
          sourceTitle: item.sourceTitle,
          applicantUserName: item.applicantUserName,
          amount: item.amount,
          currency: item.currency,
          submittedAt: item.submittedAt,
          approvedAt: item.approvedAt,
          approvalStatus: item.approvalStatus,
          sourceUrl: item.sourceUrl,
          attachments: item.attachments,
          rawPayload: item.rawPayload,
        })),
      };
      try {
        const result = await importExpenseEvidences(expenseEvidenceContext.workObjectId, payload);
        flash('success', `已导入 ${result.importedCount} 条票据记录`);
        setSelectedExpenseEvidenceImportIds([]);
        await loadExpenseEvidenceRecordsForContext(expenseEvidenceContext.workObjectId);
        await handleRunExpenseEvidenceImportSearch();
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '票据导入失败');
      }
    }, [
      expenseEvidenceContext?.workObjectId,
      expenseEvidenceImportSearchResult,
      flash,
      handleRunExpenseEvidenceImportSearch,
      loadExpenseEvidenceRecordsForContext,
      selectedExpenseEvidenceImportIds,
    ]);

    const handleFetchExpenseEvidenceAttachments = useCallback(async (evidenceId: string) => {
      try {
        const updated = await fetchExpenseEvidenceAttachments(evidenceId);
        setExpenseEvidenceRecords((prev) => prev.map((item) => (item.id === evidenceId ? updated : item)));
        flash('success', '已更新该票据的附件抓取状态');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '票据附件抓取失败');
      }
    }, [flash]);

    const handleLinkExpenseEvidenceToEventLine = useCallback(async (evidenceId: string) => {
      const eventLineId = expenseEvidenceContext?.eventLineId;
      if (!eventLineId) return;
      try {
        await linkEventLineExpenseEvidence(eventLineId, { evidenceId });
        await Promise.all([
          loadLinkedExpenseEvidenceIds(expenseEvidenceContext),
          refreshActiveEventLineAfterEvidenceChange(eventLineId),
        ]);
        flash('success', '票据已关联到当前事件线');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '票据关联失败');
      }
    }, [expenseEvidenceContext, flash, loadLinkedExpenseEvidenceIds, refreshActiveEventLineAfterEvidenceChange]);

    const handleUnlinkExpenseEvidenceFromEventLine = useCallback(async (evidenceId: string) => {
      const eventLineId = expenseEvidenceContext?.eventLineId;
      if (!eventLineId) return;
      try {
        await unlinkEventLineExpenseEvidence(eventLineId, evidenceId);
        await Promise.all([
          loadLinkedExpenseEvidenceIds(expenseEvidenceContext),
          refreshActiveEventLineAfterEvidenceChange(eventLineId),
        ]);
        flash('success', '票据已从当前事件线解除关联');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '解除票据关联失败');
      }
    }, [expenseEvidenceContext, flash, loadLinkedExpenseEvidenceIds, refreshActiveEventLineAfterEvidenceChange]);

    const handleLinkExpenseEvidenceToTask = useCallback(async (evidenceId: string) => {
      const taskId = expenseEvidenceContext?.taskId;
      const eventLineId = expenseEvidenceContext?.eventLineId;
      if (!taskId) return;
      try {
        await linkTaskExpenseEvidence(taskId, { evidenceId });
        await Promise.all([
          loadLinkedExpenseEvidenceIds(expenseEvidenceContext),
          refreshActiveEventLineAfterEvidenceChange(eventLineId),
        ]);
        flash('success', '票据已关联到当前任务');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '票据关联失败');
      }
    }, [expenseEvidenceContext, flash, loadLinkedExpenseEvidenceIds, refreshActiveEventLineAfterEvidenceChange]);

    const handleUnlinkExpenseEvidenceFromTask = useCallback(async (evidenceId: string) => {
      const taskId = expenseEvidenceContext?.taskId;
      const eventLineId = expenseEvidenceContext?.eventLineId;
      if (!taskId) return;
      try {
        await unlinkTaskExpenseEvidence(taskId, evidenceId);
        await Promise.all([
          loadLinkedExpenseEvidenceIds(expenseEvidenceContext),
          refreshActiveEventLineAfterEvidenceChange(eventLineId),
        ]);
        flash('success', '票据已从当前任务解除关联');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '解除票据关联失败');
      }
    }, [expenseEvidenceContext, flash, loadLinkedExpenseEvidenceIds, refreshActiveEventLineAfterEvidenceChange]);

    const handleBulkUnlinkEventLineExpenseEvidence = useCallback(
      async (items: Array<{ scope: 'eventLine' | 'task'; evidenceId: string; taskId?: string | null }>) => {
        const eventLineId = activeEventLine?.eventLine.id;
        if (!eventLineId || items.length === 0) return;
        try {
          await Promise.all(
            items.map((item) =>
              item.scope === 'task' && item.taskId
                ? unlinkTaskExpenseEvidence(item.taskId, item.evidenceId)
                : unlinkEventLineExpenseEvidence(eventLineId, item.evidenceId),
            ),
          );
          await refreshActiveEventLineAfterEvidenceChange(eventLineId);
          if (isExpenseEvidenceModalOpen) {
            await loadLinkedExpenseEvidenceIds(expenseEvidenceContext);
          }
          flash('success', `已解除 ${items.length} 条票据关联`);
        } catch (error) {
          flash('error', error instanceof Error ? error.message : '批量解除票据关联失败');
        }
      },
      [
        activeEventLine?.eventLine.id,
        expenseEvidenceContext,
        flash,
        isExpenseEvidenceModalOpen,
        loadLinkedExpenseEvidenceIds,
        refreshActiveEventLineAfterEvidenceChange,
      ],
    );

    const handleSaveEventLineClarification = async () => {
      if (!activeEventLine) return;
      setIsSavingEventLineClarification(true);
      try {
        const updated = await updateEventLine(activeEventLine.eventLine.id, {
          summary: eventLineClarificationDraft.summary.trim() || null,
          stage: eventLineClarificationDraft.stage.trim() || null,
          intent: eventLineClarificationDraft.intent.trim() || null,
          currentBlocker: eventLineClarificationDraft.currentBlocker.trim() || null,
          nextStep: eventLineClarificationDraft.nextStep.trim() || null,
          recentDecision: eventLineClarificationDraft.recentDecision.trim() || null,
        });
        setEventLines((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
        await openEventLineDetail(updated.id, { clarify: true });
        setIsEventLineClarifyMode(false);
        flash('success', '事件线当前态已更新，AI 洞察会优先读取这条澄清。');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '事件线澄清保存失败');
      } finally {
        setIsSavingEventLineClarification(false);
      }
    };

    const handleGenerateEventLineClarification = async () => {
      if (!activeEventLine) return;
      const transcript = eventLineClarificationDraft.transcript.trim();
      if (transcript.length < 8) {
        flash('error', '请先粘贴一小段聊天记录，再让 AI 整理。');
        return;
      }
      setIsGeneratingEventLineClarification(true);
      try {
        const draft = await generateEventLineClarificationDraft(activeEventLine.eventLine.id, {
          conversationText: transcript,
        });
        setEventLineClarificationDraft((prev) => ({ ...prev, ...draft }));
        flash('success', 'AI 已先整理成事件线当前态草稿，你可以再改一下再保存。');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : 'AI 整理聊天记录失败');
      } finally {
        setIsGeneratingEventLineClarification(false);
      }
    };

    const handleSaveTaskEventLineClarification = async () => {
      if (!selectedEventLineSummary) return;
      setIsSavingTaskEventLineClarification(true);
      try {
        const updated = await updateEventLine(selectedEventLineSummary.id, {
          summary: taskEventLineClarificationDraft.summary.trim() || null,
          stage: taskEventLineClarificationDraft.stage.trim() || null,
          intent: taskEventLineClarificationDraft.intent.trim() || null,
          currentBlocker: taskEventLineClarificationDraft.currentBlocker.trim() || null,
          nextStep: taskEventLineClarificationDraft.nextStep.trim() || null,
          recentDecision: taskEventLineClarificationDraft.recentDecision.trim() || null,
        });
        setEventLines((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
        if (activeEventLine?.eventLine.id === updated.id) {
          setActiveEventLine((prev) => (prev ? { ...prev, eventLine: updated } : prev));
        }
        setTaskEventLineClarificationDraft(buildEventLineClarificationDraft(updated));
        setIsTaskEventLineClarifyMode(false);
        flash('success', '事件线当前态已更新，任务卡和周判断会优先读取这条澄清。');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '事件线澄清保存失败');
      } finally {
        setIsSavingTaskEventLineClarification(false);
      }
    };

    const handleGenerateTaskEventLineClarification = async () => {
      if (!selectedEventLineSummary) return;
      const transcript = taskEventLineClarificationDraft.transcript.trim();
      if (transcript.length < 8) {
        flash('error', '请先粘贴一小段聊天记录，再让 AI 整理。');
        return;
      }
      setIsGeneratingTaskEventLineClarification(true);
      try {
        const draft = await generateEventLineClarificationDraft(selectedEventLineSummary.id, {
          conversationText: transcript,
        });
        setTaskEventLineClarificationDraft((prev) => ({ ...prev, ...draft }));
        flash('success', 'AI 已先整理成事件线当前态草稿，你可以确认后直接保存。');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : 'AI 整理聊天记录失败');
      } finally {
        setIsGeneratingTaskEventLineClarification(false);
      }
    };

    const handleCreateEventLineFromTask = async () => {
      if (editingTask.scopeMode === 'PERSONAL_ONLY') {
        flash('error', '个人日程不会接入事件线，请切回协作任务后再创建。');
        return;
      }
      setTaskEventLineCreateDraft(buildTaskEventLineCreateDraft());
      setIsTaskEventLineCreateOpen(true);
    };

    const handleSubmitTaskEventLineCreate = async () => {
      if (editingTask.scopeMode === 'PERSONAL_ONLY') {
        flash('error', '个人日程不会接入事件线，请切回协作任务后再创建。');
        return;
      }
      const name = taskEventLineCreateDraft.name.trim();
      if (!name) {
        flash('error', '请先输入事件线名称。');
        return;
      }
      setIsCreatingEventLine(true);
      try {
        const created = await createEventLine({
          name,
          kind: editingTask.clientId ? 'project_line' : 'custom',
          status: 'active',
          stage: taskEventLineCreateDraft.stage.trim() || '本周推进',
          summary: taskEventLineCreateDraft.summary.trim() || null,
          intent: taskEventLineCreateDraft.intent.trim() || null,
          currentBlocker: taskEventLineCreateDraft.currentBlocker.trim() || null,
          nextStep: taskEventLineCreateDraft.nextStep.trim() || null,
          recentDecision: taskEventLineCreateDraft.recentDecision.trim() || null,
          ownerIds: currentSessionUser?.id ? [currentSessionUser.id] : [],
          ownerId: currentSessionUser?.id || null,
          primaryClientId: editingTask.clientId || null,
          participantIds: [],
        });
        setEventLines((prev) => [created, ...prev.filter((item) => item.id !== created.id)]);
        setEditingTask((prev) => ({
          ...prev,
          eventLineId: created.id,
          eventLineTouched: true,
          eventLineReason: `已从当前任务创建事件线：${created.name}。如需补充阶段、阻塞或关键决策，可点右侧"查看事件线"。`,
        }));
        setIsTaskEventLineCreateOpen(false);
        setTaskEventLineCreateDraft(buildTaskEventLineCreateDraft());
        flash('success', '事件线已创建，并已挂到当前任务。当前会继续停留在任务编辑页。');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '事件线创建失败');
      } finally {
        setIsCreatingEventLine(false);
      }
    };

    const handleEditEventLineFromTask = () => {
      if (!selectedEventLineSummary) return;
      void openEventLineDetail(selectedEventLineSummary.id);
    };

    const handleCloseEventLine = async (targetEventLine: EventLine) => {
      if (isDeletingEventLine) return;
      const lineName = targetEventLine.name || '未命名事件线';
      if (!window.confirm(`确认归档事件线“${lineName}”？只有完成状态的事件线才建议归档。`)) {
        return;
      }
      setIsDeletingEventLine(true);
      try {
        await closeEventLine(targetEventLine.id);
        try { await loadEventLines(); } catch {}
        if (editingTask.eventLineId === targetEventLine.id) {
          setEditingTask((prev) => ({ ...prev, eventLineId: '', eventLineTouched: true, eventLineReason: `事件线已归档：${lineName}。` }));
        }
        if (activeEventLine?.eventLine.id === targetEventLine.id) {
          const refreshed = await getEventLine(targetEventLine.id).catch(() => null);
          if (refreshed) {
            setActiveEventLine(refreshed);
            setEventLineEditorDraft(buildEventLineEditorDraftFromDetail(refreshed));
          } else {
            setActiveEventLine(null);
            setIsEventLineEditorOpen(false);
          }
        }
        flash('success', '事件线已归档');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '事件线归档失败');
      } finally {
        setIsDeletingEventLine(false);
      }
    };

    const handleReopenEventLine = async (targetEventLine: EventLine) => {
      if (isDeletingEventLine) return;
      setIsDeletingEventLine(true);
      try {
        await reopenEventLine(targetEventLine.id);
        try { await loadEventLines(); } catch {}
        if (activeEventLine?.eventLine.id === targetEventLine.id) {
          const refreshed = await getEventLine(targetEventLine.id).catch(() => null);
          if (refreshed) {
            setActiveEventLine(refreshed);
            setEventLineEditorDraft(buildEventLineEditorDraftFromDetail(refreshed));
          }
        }
        flash('success', '事件线已重新打开');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '重新打开失败');
      } finally {
        setIsDeletingEventLine(false);
      }
    };

    const handleDeleteEventLine = async (targetEventLine: EventLine) => {
      if (isDeletingEventLine) return;
      const lineName = targetEventLine.name || '未命名事件线';
      if (!window.confirm(`确认删除事件线”${lineName}”？删除后不可恢复。`)) {
        return;
      }
      setIsDeletingEventLine(true);
      try {
        await deleteEventLine(targetEventLine.id);
        // Remove from local state immediately (cloud may keep an archived copy)
        setEventLines((prev) => prev.filter((el) => el.id !== targetEventLine.id));
        if (editingTask.eventLineId === targetEventLine.id) {
          setEditingTask((prev) => ({ ...prev, eventLineId: '', eventLineTouched: true, eventLineReason: `事件线已删除：${lineName}。` }));
        }
        if (activeEventLine?.eventLine.id === targetEventLine.id) {
          setActiveEventLine(null);
          setIsEventLineEditorOpen(false);
        }
        flash('success', '事件线已删除');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '事件线删除失败');
      } finally {
        setIsDeletingEventLine(false);
      }
    };
    const handleDeleteEventLineFromTask = async () => {
      if (!selectedEventLineSummary) return;
      if (selectedEventLineSummary.visibilityScope === 'private') {
        await handleDeleteEventLine(selectedEventLineSummary);
      } else {
        await handleCloseEventLine(selectedEventLineSummary);
      }
    };

    const handleCreateProjectModuleFromTask = () => {
      setTemplateEditorMode('create');
      setTemplateEditorInitialData(null);
      setTemplateListEditingModuleId(null);
      setTaskGroupTemplateEditingWorkObjectId('');
      setIsTemplateEditorOpen(true);
    };

    const handleSaveTemplate = async (data: TemplateData) => {
      setIsTemplateEditorOpen(false);
      setIsCreatingTaskProjectModule(true);
      try {
        const payload: TaskGroupTemplatePayload = {
          name: data.name,
          scenarioDesc: data.scenarioDesc || '',
          workObjectId: taskGroupTemplateEditingWorkObjectId || null,
          steps: data.tasks.map((task) => ({
            title: task.title,
            description: task.description,
            daysAfterPrevious: task.daysAfterPrevious,
            durationDays: task.durationDays,
            priority: task.priority,
            ownerId: task.ownerId || undefined,
            ownerName: task.ownerName || undefined,
            collaboratorIds: task.collaboratorIds || [],
            collaboratorNames: task.collaboratorNames || [],
            attachments: task.attachments || [],
          })),
        };
        const saved = templateListEditingModuleId
          ? await updateTaskGroupTemplate(templateListEditingModuleId, payload)
          : await createTaskGroupTemplate(payload);
        await loadTaskGroupTemplateBlock();
        setTemplateListEditingModuleId(saved.id);
        setTaskGroupTemplateEditingWorkObjectId(saved.workObjectId || saved.clientId || '');
        flash('success', `${templateListEditingModuleId ? '已更新' : '已创建'}任务组模板“${saved.name}”`);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '任务组模板保存失败');
      } finally {
        setIsCreatingTaskProjectModule(false);
      }
    };

    const handleEditTaskGroupTemplate = useCallback((template: TaskGroupTemplateRecord) => {
      setTemplateEditorMode('edit');
      setTemplateListEditingModuleId(template.id);
      setTaskGroupTemplateEditingWorkObjectId(template.workObjectId || template.clientId || '');
      setTemplateEditorInitialData({
        name: template.name,
        scenarioDesc: template.scenarioDesc || '',
        tasks: template.steps.map((step, index) => ({
          id: `${template.id}-${index}`,
          title: step.title,
          description: step.description,
          daysAfterPrevious: step.daysAfterPrevious,
          durationDays: step.durationDays,
          priority: step.priority,
          ownerId: step.ownerId || '',
          ownerName: step.ownerName,
          collaboratorIds: step.collaboratorIds || [],
          collaboratorNames: step.collaboratorNames || [],
          attachments: step.attachments || [],
        })),
        options: { autoCreateEventLine: false, aiFillEmpty: false },
      });
      setIsTemplateEditorOpen(true);
    }, []);

    const handleDeleteTaskGroupTemplateRecord = useCallback(async (template: TaskGroupTemplateRecord) => {
      if (!window.confirm(`确认删除任务组模板“${template.name}”？`)) return;
      try {
        await deleteTaskGroupTemplate(template.id);
        await loadTaskGroupTemplateBlock();
        flash('success', `已删除任务组模板“${template.name}”`);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '任务组模板删除失败');
      }
    }, []);

    const openTaskGroupTemplateApply = useCallback(async (template: TaskGroupTemplateRecord) => {
      setIsTemplateListOpen(false);
      setTaskGroupTemplateCollaboratorMenuStep(null);
      setTaskGroupTemplateApplyTarget(template);
      setTaskGroupTemplateApplyDraft(
        buildTaskGroupTemplateApplyDraft(template, {
          listId: '',
          workObjectId: template.workObjectId || template.clientId || editingTask.clientId || organizationClientId || '',
        }),
      );
    }, [editingTask.clientId, organizationClientId]);

    const handleApplyTaskGroupTemplateSubmit = useCallback(async () => {
      if (!taskGroupTemplateApplyTarget || !taskGroupTemplateApplyDraft) return;
      if (taskGroupTemplateApplyDraft.eventLineMode === 'existing' && !taskGroupTemplateApplyDraft.eventLineId) {
        flash('error', '请选择要关联的事件线。');
        return;
      }
      if (taskGroupTemplateApplyDraft.eventLineMode === 'create' && !taskGroupTemplateApplyDraft.eventLineName.trim()) {
        flash('error', '请先填写事件线名称。');
        return;
      }
      setIsApplyingTaskGroupTemplate(true);
      try {
        const result = await applyTaskGroupTemplate(taskGroupTemplateApplyTarget.id, {
          startDateTime: combineTaskDateTime(
            taskGroupTemplateApplyDraft.startDate,
            taskGroupTemplateApplyDraft.startTime || TASK_DEFAULT_DUE_TIME,
            { includeTime: true },
          ),
          listId: taskGroupTemplateApplyDraft.listId || '',
          workObjectId: taskGroupTemplateApplyDraft.workObjectId || null,
          eventLineMode: taskGroupTemplateApplyDraft.eventLineMode,
          eventLineId: taskGroupTemplateApplyDraft.eventLineMode === 'existing'
            ? taskGroupTemplateApplyDraft.eventLineId
            : null,
          eventLineDraft: taskGroupTemplateApplyDraft.eventLineMode === 'create'
            ? {
                name: taskGroupTemplateApplyDraft.eventLineName.trim(),
                kind: taskGroupTemplateApplyDraft.workObjectId ? 'project_line' : 'custom',
                primaryWorkObjectId: taskGroupTemplateApplyDraft.workObjectId || null,
                ownerId: currentSessionUser?.id || null,
              }
            : null,
          stepOverrides: taskGroupTemplateApplyDraft.stepOverrides.map((step) => ({
            stepIndex: step.stepIndex,
            title: step.title,
            ownerId: step.ownerId || undefined,
            ownerName: step.ownerName || undefined,
            collaboratorIds: step.collaboratorIds || [],
            collaboratorNames: step.collaboratorNames || [],
            priority: step.priority,
            durationDays: step.durationDays,
            daysAfterPrevious: step.daysAfterPrevious,
          })),
        });
        setTaskGroupTemplateApplyTarget(null);
        setTaskGroupTemplateApplyDraft(null);
        setTaskGroupTemplateCollaboratorMenuStep(null);
        setIsTemplateListOpen(false);
        setActiveTab('tasks');
        setTaskViewMode('list');
        setRecentlyCreatedTaskIds(result.createdTaskIds || []);
        window.setTimeout(() => {
          setRecentlyCreatedTaskIds((current) =>
            current.filter((taskId) => !(result.createdTaskIds || []).includes(taskId)),
          );
        }, 6000);
        await loadTaskBlock();
        if (result.createdEventLineId) {
          await loadEventLines();
        }
        flash('success', `已创建 ${result.createdCount} 条任务`);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '应用任务组模板失败');
      } finally {
        setIsApplyingTaskGroupTemplate(false);
      }
    }, [currentSessionUser?.id, ensureTaskViewOrgTaskList, flash, loadEventLines, taskGroupTemplateApplyDraft, taskGroupTemplateApplyTarget]);

    const toggleTaskGroupTemplateApplyCollaborator = (stepIndex: number, candidate: MentionCandidate) => {
      setTaskGroupTemplateApplyDraft((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          stepOverrides: prev.stepOverrides.map((item) => {
            if (item.stepIndex !== stepIndex) return item;
            const existingIds = item.collaboratorIds || [];
            const existing = item.collaboratorNames || [];
            const selected = existingIds.includes(candidate.id);
            return {
              ...item,
              collaboratorIds: selected
                ? existingIds.filter((id) => id !== candidate.id)
                : [...existingIds, candidate.id],
              collaboratorNames: selected
                ? existing.filter((name) => name !== candidate.fullName)
                : [...existing, candidate.fullName],
            };
          }),
        };
      });
    };

    const removeTaskGroupTemplateApplyCollaborator = (stepIndex: number, identifier: string) => {
      setTaskGroupTemplateApplyDraft((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          stepOverrides: prev.stepOverrides.map((item) => (
            item.stepIndex === stepIndex
              ? {
                ...item,
                collaboratorIds: (item.collaboratorIds || []).filter((id) => id !== identifier),
                collaboratorNames: (item.collaboratorNames || []).filter((_, index) => (item.collaboratorIds || [])[index] !== identifier),
              }
              : item
          )),
        };
      });
    };

    const handleCreateProjectFlowFromTask = async () => {
      if (editingTask.scopeMode === 'PERSONAL_ONLY') {
        flash('error', '个人日程不进入标准流程。');
        return;
      }
      if (!editingTask.clientId) {
        flash('error', `请先选择${terminology.singularLabel}。`);
        return;
      }
      if (!editingTask.projectModuleId) {
        flash('error', '请先选择任务模块，再创建流程。');
        return;
      }
      if (isCreatingTaskProjectFlow) return;
      const name = window.prompt('输入流程名称', '');
      if (!name || !name.trim()) return;
      setIsCreatingTaskProjectFlow(true);
      try {
        const created = await createProjectFlow(editingTask.clientId, {
          moduleId: editingTask.projectModuleId,
          name: name.trim(),
        });
        const structure = await getClientProjectStructure(editingTask.clientId);
        setProjectStructureCache((prev) => ({ ...prev, [editingTask.clientId!]: structure }));
        setEditingTask((prev) => ({
          ...prev,
          projectFlowId: created.id,
          projectFlowTouched: true,
          projectFlowReason: `已新建流程：${created.name}。`,
        }));
        flash('success', '流程已创建');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '流程创建失败');
      } finally {
        setIsCreatingTaskProjectFlow(false);
      }
    };

    const buildOptimisticTaskFromEditor = (
      draft: TaskEditorState,
      payload: TaskMutationPayload,
      options: {
        taskId: string;
        listId: string;
        listIds: string[];
        listName: string;
        listNames: string[];
        listColor: string;
        ownerId: string | null;
        ownerName: string;
        clientName?: string | null;
        eventLineName?: string | null;
        projectModuleName?: string | null;
        projectFlowName?: string | null;
      },
      existingTask?: Task | null,
    ): Task => {
      const now = new Date().toISOString();
      const optimisticCollaborators = draft.collaborators.map((item, index) => ({
        userId: item.id,
        fullName: item.fullName,
        email: item.email,
        orderIndex: index,
        isOwner: item.id === options.ownerId,
        inboxStatus: item.id === options.ownerId || item.isSelf ? 'accepted' as const : 'pending' as const,
        returnReason: null,
        handledAt: item.id === options.ownerId || item.isSelf ? now : null,
      }));
      const pendingCollaborationCount = optimisticCollaborators.filter((item) => item.inboxStatus === 'pending').length;
      return {
        ...(existingTask || {
          status: 'doing' as const,
          creatorId: currentSessionUser?.id || null,
          creatorName: currentOperatorName,
          sourceType: 'manual',
          sourceId: null,
          businessCategory: null,
          currentBlocker: null,
          nextAction: null,
          recentDecision: null,
          evidenceCount: 0,
          tags: [],
          note: null,
          attachments: [],
          collaborators: [],
          collaborationSummary: {},
          viewerInboxStatus: null,
          orgContext: null,
          projectContext: null,
          memoryHints: [],
          backgroundReadiness: null,
          linkedFactsPreview: [],
          createdAt: now,
          updatedAt: now,
        }),
        id: options.taskId,
        title: payload.title,
        desc: payload.desc,
        priority: payload.priority,
        listId: options.listId,
        listName: options.listName,
        listColor: options.listColor,
        listIds: options.listIds,
        listNames: options.listNames,
        ddl: payload.ddl,
        startDate: payload.startDate ?? null,
        dueDate: payload.dueDate ?? null,
        durationMinutes: payload.durationMinutes,
        scopeMode: payload.scopeMode,
        clientId: payload.clientId ?? null,
        clientName: options.clientName ?? existingTask?.clientName ?? null,
        eventLineId: payload.eventLineId ?? null,
        eventLineName: options.eventLineName ?? existingTask?.eventLineName ?? null,
        projectModuleId: payload.projectModuleId ?? null,
        projectModuleName: options.projectModuleName ?? existingTask?.projectModuleName ?? null,
        projectFlowId: payload.projectFlowId ?? null,
        projectFlowName: options.projectFlowName ?? existingTask?.projectFlowName ?? null,
        ownerId: options.ownerId,
        ownerName: options.ownerName,
        collaborators: optimisticCollaborators,
        collaborationSummary: pendingCollaborationCount > 0 ? { pending: pendingCollaborationCount } : {},
        updatedAt: now,
      };
    };

    const upsertLocalTask = (nextTask: Task, replaceId?: string | null) => {
      setTasks((prev) => {
        let matched = false;
        const next = prev.map((item) => {
          if (item.id === nextTask.id || (replaceId && item.id === replaceId)) {
            matched = true;
            return { ...item, ...nextTask };
          }
          return item;
        });
        return matched ? next : [nextTask, ...next];
      });
    };

    const uploadAttachmentsToTask = async (
      taskId: string,
      files: File[],
      options: { clientId?: string | null; eventLineId?: string | null; taskTitle?: string | null; showProgress?: boolean },
    ) => {
      if (files.length === 0) return;
      const showProgress = options.showProgress !== false;
      if (showProgress) {
        setIsTaskAttachmentBusy(true);
        setTaskAttachmentUploadProgress({
          currentFileName: files[0]?.name || '附件',
          uploadedFiles: 0,
          totalFiles: files.length,
          percent: 0,
        });
      }
      try {
        for (const [index, file] of files.entries()) {
          if (showProgress) {
            setTaskAttachmentUploadProgress({
              currentFileName: file.name,
              uploadedFiles: index,
              totalFiles: files.length,
              percent: Math.max(0, Math.min(100, Math.round((index / files.length) * 100))),
            });
          }
          await uploadTaskAttachment(taskId, {
            file,
            clientId: options.clientId || undefined,
            eventLineId: options.eventLineId || undefined,
            taskTitle: options.taskTitle || undefined,
            onProgress: (loaded, total) => {
              if (!showProgress) return;
              const currentRatio = total > 0 ? loaded / total : 0;
              const overallPercent = ((index + currentRatio) / files.length) * 100;
              setTaskAttachmentUploadProgress({
                currentFileName: file.name,
                uploadedFiles: index,
                totalFiles: files.length,
                percent: Math.max(1, Math.min(100, Math.round(overallPercent))),
              });
            },
          });
          if (showProgress) {
            setTaskAttachmentUploadProgress({
              currentFileName: file.name,
              uploadedFiles: index + 1,
              totalFiles: files.length,
              percent: Math.max(1, Math.min(100, Math.round(((index + 1) / files.length) * 100))),
            });
          }
        }
      } finally {
        if (showProgress) {
          setIsTaskAttachmentBusy(false);
          setTaskAttachmentUploadProgress(null);
        }
      }
    };

    const handleSaveTask = async () => {
      if (!editingTask.title.trim()) {
        flash('error', '请填写任务标题');
        return;
      }
      if (editingTask.startDate && !editingTask.dueDate) {
        flash('error', '填写开始日期后，还需要选择截止时间。');
        return;
      }
      const archiveTextSnapshot = pendingTaskArchiveText.trim();
      const attachmentFilesSnapshot = [...pendingTaskAttachmentFiles];
      const smartBriefSourceSnapshot = pendingSmartBriefDraftSource
        ? { ...pendingSmartBriefDraftSource }
        : null;
      if (archiveTextSnapshot && editingTask.scopeMode === 'PERSONAL_ONLY') {
        flash('error', `个人日程不会同步到${terminology.workspaceLabel}，请切回协作任务后再归档文字。`);
        return;
      }
      if (archiveTextSnapshot && !editingTask.clientId) {
        flash('error', `请先关联${terminology.singularLabel}，再把这段文字归档到${terminology.workspaceLabel}。`);
        return;
      }
      setIsDuePickerOpen(false);
      setIsSavingTask(true);
      const combinedStartDate = editingTask.startDate
        ? combineTaskDateTime(editingTask.startDate, editingTask.startTime, {
          includeTime: editingTask.hasSpecificDueTime && Boolean(editingTask.startTime),
        })
        : '';
      const combinedDueDate = combineTaskDueDateTime(editingTask.dueDate, editingTask.dueTime, {
        includeTime: editingTask.hasSpecificDueTime,
      });
      const resolvedDdl = combinedDueDate
        ? duePickerSummaryLabel
        : (editingTask.ddl.trim() || '待确认');
      const availableLists = isEditingTaskPersonal ? personalTaskLists : orgTaskLists;
      const normalizedDraftListIds = Array.from(
        new Set((editingTask.listIds || []).filter((listId) => availableLists.some((item) => item.id === listId))),
      );
      const resolvedListId = (() => {
        if (isEditingTaskPersonal) {
          if (normalizedDraftListIds.length > 0) {
            return normalizedDraftListIds[0];
          }
          return resolveTaskViewDefaultListId('personal') || editingTask.listId;
        }
        if (normalizedDraftListIds.length > 0) {
          return normalizedDraftListIds[0];
        }
        return resolveTaskViewDefaultListId('org') || editingTask.listId;
      })();
      const resolvedListIds = normalizedDraftListIds.length > 0
        ? normalizedDraftListIds
        : (resolvedListId ? [resolvedListId] : []);
      const ownerId = editingTask.ownerId || null;
      const ownerName = ownerCollaborator?.fullName || '';
      const payload: TaskMutationPayload = {
        scopeMode: editingTask.scopeMode,
        title: editingTask.title.trim(),
        desc: editingTask.desc.trim(),
        priority: editingTask.priority,
        listId: resolvedListId,
        listIds: resolvedListIds,
        startDate: combinedStartDate || null,
        dueDate: combinedDueDate || null,
        durationMinutes: editingTask.durationMinutes,
        clientId: isEditingTaskPersonal ? null : (editingTask.clientId || null),
        eventLineId: isEditingTaskPersonal ? null : (editingTask.eventLineId || null),
        projectModuleId: isEditingTaskPersonal ? null : (editingTask.projectModuleId || null),
        projectFlowId: isEditingTaskPersonal ? null : (editingTask.projectFlowId || null),
        ddl: resolvedDdl,
        ownerId,
        ownerName,
        collaboratorIds: editingTask.collaborators.map((item) => item.id),
        tagIds: [],
      };
      const draftSnapshot: TaskEditorState = {
        ...editingTask,
        tagIds: [...editingTask.tagIds],
        collaborators: editingTask.collaborators.map((item: MentionCandidate) => ({ ...item })),
      };
      void (async () => {
        try {
          if (!isEditingTaskPersonal && orgTaskLists.length === 0) {
            try {
              await ensureTaskViewOrgTaskList();
            } catch {
              // 组织清单创建失败不阻断保存
            }
          }
          const savedTask = draftSnapshot.id
            ? await updateTask(draftSnapshot.id, payload)
            : await createTask(payload);
          upsertLocalTask(savedTask, draftSnapshot.id || null);

          if (!draftSnapshot.id && smartBriefSourceSnapshot?.sourceTaskId && smartBriefSourceSnapshot.actionKey) {
            setTaskSmartBriefs((prev) => {
              const sourceBrief = prev[smartBriefSourceSnapshot.sourceTaskId];
              if (!sourceBrief) return prev;
              return {
                ...prev,
                [smartBriefSourceSnapshot.sourceTaskId]: {
                  ...sourceBrief,
                  actionItems: sourceBrief.actionItems.filter((item) => item.actionKey !== smartBriefSourceSnapshot.actionKey),
                },
              };
            });
            try {
              await adoptTaskSmartBriefAction(smartBriefSourceSnapshot.sourceTaskId, smartBriefSourceSnapshot.actionKey, {
                createdTaskId: savedTask.id,
                actionText: smartBriefSourceSnapshot.actionText,
              });
            } catch (error) {
              console.warn('[smart-brief] failed to mark action adopted', error);
            }
          }

          if (!isEditingTaskPersonal && archiveTextSnapshot && (savedTask.clientId || draftSnapshot.clientId)) {
            try {
              const targetClientId = savedTask.clientId || draftSnapshot.clientId;
              await createClientTextDocument(targetClientId, {
                title: inferTaskArchiveDocumentTitle({
                  taskTitle: savedTask.title || draftSnapshot.title,
                  clientName: clients.find((item: ClientSummary) => item.id === targetClientId)?.name || null,
                  eventLineName: eventLines.find((item: EventLine) => item.id === (savedTask.eventLineId || draftSnapshot.eventLineId))?.name || null,
                  content: archiveTextSnapshot,
                }),
                content: archiveTextSnapshot,
              });
              if (currentClientId && currentClientId === targetClientId) {
                await refreshWorkspace(targetClientId);
              }
            } catch (error) {
              void loadTaskBlock();
              if ((savedTask?.eventLineId || draftSnapshot.eventLineId) && activeEventLine?.eventLine.id === (savedTask?.eventLineId || draftSnapshot.eventLineId)) {
                void openEventLineDetail(savedTask?.eventLineId || draftSnapshot.eventLineId);
              }
              setIsSavingTask(false);
              flash(
                'error',
                `${draftSnapshot.id ? '任务已更新' : '任务已创建'}，但文字归档失败：${
                  error instanceof Error ? error.message : '请稍后重试'
                }`,
              );
              return;
            }
          }

          if (attachmentFilesSnapshot.length > 0) {
            try {
              await uploadAttachmentsToTask(savedTask.id, attachmentFilesSnapshot, {
                clientId: savedTask.clientId || draftSnapshot.clientId,
                eventLineId: savedTask.eventLineId || draftSnapshot.eventLineId,
                taskTitle: savedTask.title || draftSnapshot.title,
              });
              setPendingTaskAttachmentFiles([]);
            } catch (error) {
              void loadTaskBlock();
              if ((savedTask?.eventLineId || draftSnapshot.eventLineId) && activeEventLine?.eventLine.id === (savedTask?.eventLineId || draftSnapshot.eventLineId)) {
                void openEventLineDetail(savedTask?.eventLineId || draftSnapshot.eventLineId);
              }
              setIsSavingTask(false);
              flash(
                'error',
                `${draftSnapshot.id ? '任务已更新' : '任务已创建'}，但附件上传失败：${
                  error instanceof Error ? error.message : '请稍后重试'
                }`,
              );
              return;
            }
          }

          closeTaskModal('save-succeeded');
          void loadTaskBlock();
          if ((savedTask?.eventLineId || draftSnapshot.eventLineId) && activeEventLine?.eventLine.id === (savedTask?.eventLineId || draftSnapshot.eventLineId)) {
            void openEventLineDetail(savedTask?.eventLineId || draftSnapshot.eventLineId);
          }
          flash(
            'success',
            archiveTextSnapshot || attachmentFilesSnapshot.length > 0
              ? `任务已保存，${[
                archiveTextSnapshot ? `文字已归档到当前电脑的${terminology.workspaceLabel}` : '',
                attachmentFilesSnapshot.length > 0 ? `${attachmentFilesSnapshot.length} 个附件已上传` : '',
              ].filter(Boolean).join('，')}。`
              : draftSnapshot.id
                ? '任务已更新'
                : '任务已创建',
          );
        } catch (error) {
          setIsSavingTask(false);
          flash('error', `${error instanceof Error ? error.message : (draftSnapshot.id ? '更新失败' : '创建失败')}。请检查后重试。`);
        }
      })();
    };

    const requestDeleteTaskRecord = (
      task: { id: string; title: string; clientId?: string | null; eventLineId?: string | null },
      options?: { closeEditor?: boolean },
    ) => {
      setPendingTaskDelete({
        id: task.id,
        title: task.title,
        clientId: task.clientId || null,
        eventLineId: task.eventLineId || null,
        closeEditor: options?.closeEditor || false,
      });
    };

    const handleDeleteTaskRecord = async (
      task: { id: string; title: string; clientId?: string | null; eventLineId?: string | null },
      options?: { closeEditor?: boolean },
    ) => {
      if (options?.closeEditor || editingTask.id === task.id) {
        closeTaskModal('delete-started');
        resetTaskDraft();
      }
      const deletedId = task.id;
      setTasks((prev) => prev.filter((t) => t.id !== deletedId));
      flash('success', '任务已删除');
      void (async () => {
        try {
          await deleteTask(deletedId);
          // Wait for cloud to process before refreshing
          await new Promise((r) => setTimeout(r, 2000));
          await loadTaskBlock();
          // Ensure deleted task stays deleted even if cloud returned stale data
          setTasks((prev) => prev.filter((t) => t.id !== deletedId));
          if (reviewDashboard?.weekLabel) void loadReviewBlock(reviewDashboard.weekLabel);
          void refreshWorkspace(task.clientId || undefined);
          if (task.eventLineId && activeEventLine?.eventLine.id === task.eventLineId) void openEventLineDetail(task.eventLineId);
        } catch {
          // Delete already removed locally — don't restore
        }
      })();
    };

    const confirmDeleteTaskRecord = async () => {
      if (!pendingTaskDelete) return;
      const payload = pendingTaskDelete;
      setPendingTaskDelete(null);
      await handleDeleteTaskRecord(
        {
          id: payload.id,
          title: payload.title,
          clientId: payload.clientId || null,
          eventLineId: payload.eventLineId || null,
        },
        { closeEditor: payload.closeEditor },
      );
    };

    const handleUploadOrgDna = async (moduleKey: OrganizationDnaModule['moduleKey']) => {
      const paths = await selectFilesBridge();
      const filePath = paths[0];
      if (!filePath) return;
      setOrgDnaSavingKey(moduleKey);
      try {
        await updateOrganizationDnaModule(moduleKey, { filePath });
        await Promise.all([loadSettingsSectionBlock('org_dna', true), loadLogsBlock()]);
        flash('success', '组织 DNA 已更新');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '组织 DNA 上传失败');
      } finally {
        setOrgDnaSavingKey(null);
      }
    };

    const buildReviewPayload = (draftOverride?: { workFreeNote?: string; personalGrowthNote?: string; personalPrivateNote?: string }) => {
      const taskEntries = [...workReviewRows, ...personalReviewRows].map(({ task, note, structuredNote }) => ({
        taskId: task.id,
        contentDomain: isPrivateTask(task) ? 'personal' as const : 'work' as const,
        note: note.trim(),
        structuredNote,
      }));
      return {
        weekLabel: reviewForm.weekLabel || currentWeekLabel(),
        taskEntries,
        workFreeNote: draftOverride?.workFreeNote ?? latestReview?.workFreeNote ?? '',
        personalGrowthNote: draftOverride?.personalGrowthNote ?? latestReview?.personalGrowthNote ?? '',
        personalPrivateNote: draftOverride?.personalPrivateNote ?? latestReview?.personalPrivateNote ?? '',
      };
    };

    const buildReviewPayloadForGroup = (group: ReviewTaskGroup) => {
      const taskEntriesByTaskId = new Map(
        [...workReviewItems, ...personalReviewItems].map((item) => [
          item.taskId,
          {
            taskId: item.taskId,
            contentDomain: item.contentDomain,
            note: item.note.trim(),
            structuredNote: item.structuredNote,
          },
        ]),
      );

      group.rows.forEach(({ task }) => {
        const structuredNote = reviewForm.entriesByTaskId[task.id] ?? createEmptyReviewStructuredNote();
        const note = composeReviewNoteFromStructuredFields(structuredNote, task.status).trim();
        const nextEntry = {
          taskId: task.id,
          contentDomain: isPrivateTask(task) ? 'personal' as const : 'work' as const,
          note,
          structuredNote,
        };
        if (note || hasMeaningfulReviewStructuredNote(structuredNote)) {
          taskEntriesByTaskId.set(task.id, nextEntry);
        } else {
          taskEntriesByTaskId.delete(task.id);
        }
      });

      return {
        weekLabel: reviewForm.weekLabel || currentWeekLabel(),
        taskEntries: Array.from(taskEntriesByTaskId.values()),
        workFreeNote: latestReview?.workFreeNote ?? '',
        personalGrowthNote: latestReview?.personalGrowthNote ?? '',
        personalPrivateNote: latestReview?.personalPrivateNote ?? '',
      };
    };

    const readActionPayloadStrings = (value: unknown): string[] => (
      Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0) : []
    );

    const handleTriggerReviewAction = async (action: ReviewActionCard, report: HierarchyReport): Promise<ReviewActionExecutionResult | void> => {
      const summary = typeof action.payload.summary === 'string' && action.payload.summary.trim()
        ? action.payload.summary.trim()
        : action.title;
      const relatedTaskIds = readActionPayloadStrings(action.payload.relatedTaskIds);
      const relatedTaskTitles = readActionPayloadStrings(action.payload.relatedTaskTitles);
      const primaryTaskId = relatedTaskIds[0] || null;
      const primaryClientId = typeof action.payload.primaryClientId === 'string' && action.payload.primaryClientId.trim()
        ? action.payload.primaryClientId.trim()
        : null;
      const primaryClientName = typeof action.payload.primaryClientName === 'string' && action.payload.primaryClientName.trim()
        ? action.payload.primaryClientName.trim()
        : null;
      const primaryDepartmentId = typeof action.payload.primaryDepartmentId === 'string' && action.payload.primaryDepartmentId.trim()
        ? action.payload.primaryDepartmentId.trim()
        : null;
      const primaryEventLineId = typeof action.payload.primaryEventLineId === 'string' && action.payload.primaryEventLineId.trim()
        ? action.payload.primaryEventLineId.trim()
        : null;
      const primaryEventLineName = typeof action.payload.primaryEventLineName === 'string' && action.payload.primaryEventLineName.trim()
        ? action.payload.primaryEventLineName.trim()
        : null;
      const titlePrefix = action.actionType === 'one_on_one' ? '1v1：' : '';
      const descBody = [
        summary,
        relatedTaskTitles.length > 0 ? `关联任务：${relatedTaskTitles.join('、')}` : '',
        `来源：周判断动作卡`,
      ].filter(Boolean).join('\n\n');

      try {
        if (action.actionType === 'meeting') {
          if (!primaryClientId) {
            flash('error', `这条动作卡还没有挂接${terminology.singularLabel}背景，暂时不能直接发起会议。`);
            return;
          }
          const result = await launchFeishuMeeting(primaryClientId, {
            title: action.title,
            sourceTaskId: primaryTaskId,
          });
          flash(result.deliveryStatus === 'failed' ? 'error' : 'success', result.deliveryMessage);
          if (result.deliveryStatus !== 'sent') {
            window.alert(
              `${result.deliveryMessage}\n\n会议草稿：${result.meeting.title}\n会议编号：${result.meeting.id}\n\n${result.commandHint}`,
            );
          }
          if (primaryClientId === currentClientId) {
            await refreshWorkspace(primaryClientId);
          }
          return {
            objectType: 'meeting',
            objectId: result.meeting.id,
            objectLabel: result.meeting.title,
            targetClientId: primaryClientId,
            targetClientName: primaryClientName,
            targetEventLineId: primaryEventLineId,
            targetEventLineName: primaryEventLineName,
            canOpen: Boolean(primaryClientId),
          };
        }

        if (action.actionType === 'support_request' || action.actionType === 'resource_request') {
          const targetScope = report.scopeType === 'org'
            ? 'organization'
            : primaryDepartmentId
              ? 'department'
              : 'organization';
          const targetRefId = targetScope === 'department' ? primaryDepartmentId : null;
          const requestType = action.actionType === 'resource_request' ? 'workload' : 'collaboration';
          const supportRequest = await createSupportRequest({
            taskId: primaryTaskId,
            eventLineId: primaryEventLineId,
            targetScope,
            targetRefId,
            requestType,
            urgency: report.scopeType === 'org' ? 'high' : 'medium',
            summary,
          });
          flash('success', action.actionType === 'resource_request' ? '资源请求已创建。' : '支持请求已创建。');
          return {
            objectType: 'support_request',
            objectId: supportRequest.id,
            objectLabel: supportRequest.summary,
            targetClientId: primaryClientId,
            targetClientName: primaryClientName,
            targetEventLineId: primaryEventLineId,
            targetEventLineName: primaryEventLineName,
            canOpen: true,
            supportRequest,
          };
        }

        const createdTask = await createTask({
          title: `${titlePrefix}${action.title}`,
          desc: descBody,
          priority: report.scopeType === 'org' ? 'high' : 'normal',
          listId: '',
          dueDate: null,
          durationMinutes: 60,
          clientId: primaryClientId,
          eventLineId: primaryEventLineId,
          ddl: '待确认',
          ownerId: null,
          ownerName: '',
          collaboratorIds: [],
          tagIds: [],
          sourceType: 'review_action',
          sourceId: action.id,
        });
        await loadTaskBlock();
        flash('success', action.actionType === 'one_on_one' ? '1v1 动作已转成任务。' : '动作已转成任务。');
        return {
          objectType: 'task',
          objectId: createdTask.id,
          objectLabel: createdTask.title,
          targetClientId: primaryClientId,
          targetClientName: primaryClientName,
          targetEventLineId: primaryEventLineId,
          targetEventLineName: primaryEventLineName,
          canOpen: true,
        };
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '动作执行失败');
      }
    };

    const handleOpenReviewActionResult = async (
      result: ReviewActionExecutionResult,
      _action: ReviewActionCard,
      _report: HierarchyReport,
    ) => {
      if (result.objectType === 'task') {
        const task = tasks.find((item) => item.id === result.objectId);
        if (!task) {
          flash('error', '任务已创建，但当前列表还没刷新到这条任务。');
          return;
        }
        setTaskViewMode('list');
        openTaskEditor(task);
        return;
      }

      if (result.objectType === 'meeting' && result.targetClientId) {
        setCurrentClientId(result.targetClientId);
        await refreshWorkspace(result.targetClientId);
        flash('success', `已定位到 ${result.targetClientName || `对应${terminology.singularLabel}`} ${terminology.workspaceLabel}，可继续查看会议草稿。`);
        return;
      }

      if (result.objectType === 'support_request') {
        if (result.supportRequest) {
          setSupportRequestResolutionNote(result.supportRequest.resolutionNote || '');
          setActiveSupportRequest(result.supportRequest);
          return;
        }
        try {
          const requests = await getSupportRequests();
          const matched = requests.find((item) => item.id === result.objectId);
          if (!matched) {
            flash('error', '支持请求已创建，但当前没取回到对应记录。');
            return;
          }
          setSupportRequestResolutionNote(matched.resolutionNote || '');
          setActiveSupportRequest(matched);
        } catch (error) {
          flash('error', error instanceof Error ? error.message : '打开支持请求失败');
        }
      }
    };

    const handleResolveSupportRequest = async (status: 'accepted' | 'resolved' | 'dismissed') => {
      if (!activeSupportRequest) return;
      setSupportRequestActionBusy(true);
      try {
        const nextRecord = await resolveSupportRequest(activeSupportRequest.id, {
          status,
          resolutionNote: supportRequestResolutionNote.trim(),
        });
        setActiveSupportRequest(nextRecord);
        setSupportRequestResolutionNote(nextRecord.resolutionNote || '');
        flash(
          'success',
          status === 'accepted' ? '支持请求已接受。' : status === 'dismissed' ? '支持请求已驳回。' : '支持请求已解决。',
        );
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '更新支持请求失败');
      } finally {
        setSupportRequestActionBusy(false);
      }
    };

    const isEditingTaskPersonal = editingTask.scopeMode === 'PERSONAL_ONLY';

    const ensureTagSelected = async (name: string, scope: 'org' | 'self' = defaultTagScope, color?: string) => {
      void name;
      void scope;
      void color;
      return null;
    };

    const resetTaskDraft = (dueDate?: string, options?: { durationMinutes?: number }) => {
      const nextDueDate = dueDate ?? defaultDueDateFromPreset(effectiveTaskSettings.defaultDueDatePreset);
      const nextDueParts = splitTaskDueDateTime(nextDueDate);
      resetTaskModalTransientState();
      const parsedDate = parseTaskDateValue(nextDueParts.date);
      setDuePickerMonth(parsedDate ? new Date(parsedDate.getFullYear(), parsedDate.getMonth(), 1) : getTodayCalendarState().calendarDate);
      setEditingTask({
        id: null,
        scopeMode: 'COLLAB_SHARED',
        scopeModeTouched: false,
        title: '',
        desc: '',
        listId: '',
        listIds: [],
        priority: effectiveTaskSettings.defaultPriority,
        priorityTouched: false,
        priorityReason: '系统会根据任务内容自动识别优先级，你可以手动调整。',
        ownerId: '',
        startDate: '',
        startTime: '',
        dueDate: nextDueParts.date,
        dueTime: nextDueParts.time || TASK_DEFAULT_DUE_TIME,
        hasSpecificDueTime: Boolean(nextDueParts.time),
        durationMinutes: Math.max(15, options?.durationMinutes ?? 60),
        clientId: '',
        clientTouched: false,
        clientConfidence: 'none',
        clientReason: `可选：手动选择${terminology.singularLabel}，或先关联事件线后自动回填。`,
        eventLineId: '',
        eventLineTouched: false,
        eventLineReason: '可选：把任务挂到一条持续推进的事件线上，后续复盘会按事件线聚合。',
        projectModuleId: '',
        projectModuleTouched: false,
        projectModuleReason: `可选：把任务挂到当前${terminology.singularLabel}下的具体${terminology.structureLabel}。`,
        projectFlowId: '',
        projectFlowTouched: false,
        projectFlowReason: '可选：把任务进一步挂到标准流程，后续复盘和日历会更贴近业务动作。',
        ddl: nextDueParts.date ? formatTaskDueLabel(nextDueDate) : defaultDdlFromPreset(effectiveTaskSettings.defaultDueDatePreset),
        tagIds: [],
        collaborators: buildDefaultCollaborators(),
      });
      setTagDraft({ name: '', scope: defaultTagScope, color: TASK_COLOR_OPTIONS[0] });
      setSuggestedTaskTags([]);
      setPendingTaskArchiveText('');
      setPendingTaskAttachmentFiles([]);
    };

    const canOpenTaskEditorModal = (source: 'general' | 'calendar' = 'general') => {
      if (Date.now() < taskInteractionBlockUntilRef.current && !isTaskModalOpenRef.current) {
        return false;
      }
      if (isTaskInteractionBlocked && !isTaskModalOpenRef.current) {
        return false;
      }
      if (source === 'calendar' && Date.now() < calendarTaskOpenGuardUntilRef.current) {
        return false;
      }
      return true;
    };

    const requestCreateTaskEditor = (dueDate?: string, options?: { durationMinutes?: number }) => {
      if (!canOpenTaskEditorModal()) return;
      resetTaskDraft(dueDate, options);
      isTaskModalOpenRef.current = true;
      setIsTaskModalOpen(true);
    };

    const openTaskEditor = (task?: Task, dueDate?: string, options?: { durationMinutes?: number }) => {
      if (!task) {
        requestCreateTaskEditor(dueDate, options);
        return;
      }
      if (!canOpenTaskEditorModal()) {
        return;
      }
      if (isLocalDraftTaskId(task.id)) {
        flash('info', '任务正在后台保存，稍等一下就会稳定出现在列表里。');
        return;
      }
      const resolvedDueDate = task.dueDate || dueDate || new Date().toISOString().slice(0, 10);
      const resolvedDueParts = splitTaskDueDateTime(resolvedDueDate);
      const resolvedStartParts = splitTaskDueDateTime(task.startDate || '');
      const resolvedTimelineRange = resolveUnifiedTaskDateTimeRange(task);
      const resolvedTimelineStartDate = formatDateOnlyValue(resolvedTimelineRange.startDateTime);
      const resolvedTimelineStartTime = formatTimeOnlyValue(resolvedTimelineRange.startDateTime);
      const resolvedTimelineDueDate = formatDateOnlyValue(resolvedTimelineRange.endDateTime);
      const resolvedTimelineDueTime = formatTimeOnlyValue(resolvedTimelineRange.endDateTime);
      const safeDurationMinutes = Math.max(15, task.durationMinutes ?? options?.durationMinutes ?? 60);
      const legacyTimedTaskStartMinute = !resolvedStartParts.date
        ? minuteOfDayFromTaskTime(resolvedDueParts.time)
        : null;
      const legacyTimedTaskEndMinute = legacyTimedTaskStartMinute !== null
        ? Math.min(legacyTimedTaskStartMinute + Math.max(15, task.durationMinutes ?? 0), 24 * 60)
        : null;
      const explicitStartMinute = minuteOfDayFromTaskTime(resolvedStartParts.time);
      const explicitTimedTaskEndMinute = explicitStartMinute !== null
        ? explicitStartMinute + safeDurationMinutes
        : null;
      const explicitTimedTaskEndDate = explicitTimedTaskEndMinute !== null
        ? shiftDateOnlyValue(resolvedDueParts.date || resolvedStartParts.date, Math.floor(explicitTimedTaskEndMinute / (24 * 60)))
        : resolvedDueParts.date;
      const ddlWindow = parseTaskTimelineWindowFromLabel(task.ddl);
      const displayWindow = parseTaskTimelineWindowFromLabel(formatUnifiedTaskTimelineLabel(task));
      const inferredStartDate = resolvedStartParts.date
        || (legacyTimedTaskStartMinute !== null ? resolvedDueParts.date : '')
        || (displayWindow.hasSpecificTime ? resolvedDueParts.date || resolvedTimelineDueDate : '')
        || resolvedTimelineStartDate;
      const inferredStartTime = resolvedStartParts.time
        || (legacyTimedTaskStartMinute !== null ? resolvedDueParts.time : '')
        || displayWindow.startTime
        || ddlWindow.startTime
        || resolvedTimelineStartTime;
      const inferredDueDate = resolvedDueParts.time
        ? resolvedDueParts.date
        : (explicitTimedTaskEndDate || resolvedDueParts.date || resolvedTimelineDueDate);
      const inferredDueTime = legacyTimedTaskEndMinute !== null
        ? formatTaskMinuteOfDay(legacyTimedTaskEndMinute)
        : (
          resolvedDueParts.time
          || (explicitTimedTaskEndMinute !== null ? resolvedTimelineDueTime : '')
          || displayWindow.dueTime
          || ddlWindow.dueTime
          || resolvedTimelineDueTime
          || TASK_DEFAULT_DUE_TIME
        );
      const inferredHasSpecificTime = Boolean(
        resolvedStartParts.time
        || resolvedDueParts.time
        || legacyTimedTaskStartMinute !== null
        || explicitStartMinute !== null
        || displayWindow.hasSpecificTime
        || ddlWindow.hasSpecificTime
        || resolvedTimelineRange.hasExplicitTime
      );
      const normalizedStartDate = inferredStartDate || (ddlWindow.hasSpecificTime ? inferredDueDate : '') || resolvedTimelineStartDate;
      resetTaskModalTransientState();
      const parsedDate = parseTaskDateValue(resolvedDueParts.date);
      setDuePickerMonth(parsedDate ? new Date(parsedDate.getFullYear(), parsedDate.getMonth(), 1) : getTodayCalendarState().calendarDate);
      setEditingTask({
        id: task.id,
        scopeMode: task.scopeMode || (isPrivateTask(task) ? 'PERSONAL_ONLY' : 'COLLAB_SHARED'),
        scopeModeTouched: false,
        title: task.title,
        desc: task.desc,
        listId: task.listId,
        listIds: task.listIds && task.listIds.length > 0
          ? task.listIds
          : (task.listId ? [task.listId] : []),
        priority: task.priority,
        priorityTouched: true,
        priorityReason: '保留当前优先级，你可以手动调整。',
        ownerId: task.ownerId || '',
        startDate: normalizedStartDate,
        startTime: inferredStartTime,
        dueDate: inferredDueDate,
        dueTime: inferredDueTime,
        hasSpecificDueTime: inferredHasSpecificTime,
        durationMinutes: safeDurationMinutes,
        clientId: task.clientId || '',
        clientTouched: Boolean(task.clientId),
        clientConfidence: task.clientId ? 'manual' : 'none',
        clientReason: task.clientName ? `当前任务已关联${terminology.singularLabel}“${task.clientName}”，你可以手动调整。` : organizationTaskManualReason,
        eventLineId: task.eventLineId || '',
        eventLineTouched: Boolean(task.eventLineId),
        eventLineReason: task.eventLineName ? `当前任务已挂到事件线"${task.eventLineName}"。` : '可选：把任务挂到一条持续推进的事件线上，后续复盘会按事件线聚合。',
        projectModuleId: task.projectModuleId || '',
        projectModuleTouched: Boolean(task.projectModuleId),
        projectModuleReason: task.projectModuleName ? `当前任务已挂到模块"${task.projectModuleName}"。` : `可选：把任务挂到当前${terminology.singularLabel}下的具体${terminology.structureLabel}。`,
        projectFlowId: task.projectFlowId || '',
        projectFlowTouched: Boolean(task.projectFlowId),
        projectFlowReason: task.projectFlowName ? `当前任务已挂到流程"${task.projectFlowName}"。` : '可选：把任务进一步挂到标准流程，后续复盘和日历会更贴近业务动作。',
        ddl: formatTaskTimelineLabel(task),
        tagIds: [],
        collaborators: (() => {
          const nextCollaborators = task.collaborators.map((item) => ({
            id: item.userId,
            fullName: item.fullName,
            email: item.email,
            primaryRole: currentSessionUser.primaryRole,
            isSelf: item.userId === currentSessionUser.id,
          }));
          if (task.ownerId && !nextCollaborators.some((item) => item.id === task.ownerId)) {
            nextCollaborators.unshift({
              id: task.ownerId,
              fullName: task.ownerName || '未指定',
              email: '',
              primaryRole: currentSessionUser.primaryRole,
              isSelf: task.ownerId === currentSessionUser.id,
            });
          }
          return nextCollaborators;
        })(),
      });
      setTagDraft({ name: '', scope: defaultTagScope, color: TASK_COLOR_OPTIONS[0] });
      setSuggestedTaskTags([]);
      setPendingTaskArchiveText('');
      setPendingTaskAttachmentFiles([]);
      isTaskModalOpenRef.current = true;
      setIsTaskModalOpen(true);
    };

    const openTaskEditorFromCalendar = (task?: Task, dueDate?: string, options?: { durationMinutes?: number }) => {
      if (!canOpenTaskEditorModal('calendar')) {
        return;
      }
      openTaskEditor(task, dueDate, options);
    };

    useEffect(() => {
      if (activeTab !== 'tasks' || !growthContextJump) return;
      const requestId = growthContextJump.requestId;
      const context = growthContextJump.context;
      if (!['task', 'event_line', 'review', 'project_module', 'project_flow'].includes(context.objectType)) return;
      let cancelled = false;
      const clearRequest = () => {
        if (cancelled) return;
        setGrowthContextJump((prev) => (prev?.requestId === requestId ? null : prev));
      };
      const run = async () => {
        if (context.objectType === 'task') {
          setTaskViewMode('list');
          const board = await loadTaskBlock().catch(() => null);
          const targetTask = (board?.tasks || tasks).find((item) => item.id === context.objectId);
          if (targetTask) {
            openTaskEditor(targetTask);
            flash('success', `已打开任务「${targetTask.title}」`);
          } else {
            flash('error', `当前没有找到任务「${context.label}」`);
          }
          clearRequest();
          return;
        }
        if (context.objectType === 'event_line') {
          setTaskViewMode('list');
          const detail = await openEventLineDetail(context.objectId);
          if (detail) {
            flash('success', `已打开事件线「${detail.eventLine.name}」`);
          }
          clearRequest();
          return;
        }
        if (context.objectType === 'project_module') {
          setTaskViewMode('list');
          const board = await loadTaskBlock().catch(() => null);
          const scopedTasks = board?.tasks || tasks;
          const fallbackTask = scopedTasks.find((item) => item.projectModuleId === context.objectId);
          const scopedClientId = fallbackTask?.clientId || currentClientId || null;
          const detail = scopedClientId ? await getProjectModuleDetail(scopedClientId, context.objectId).catch(() => null) : null;
          const targetTask = detail
            ? scopedTasks.find((item) => detail.relatedTaskIds.includes(item.id))
            : fallbackTask;
          if (targetTask) {
            openTaskEditor(targetTask);
            flash('success', detail?.contextSummary || `已定位到模块「${context.label}」`);
          } else {
            flash('success', detail?.contextSummary || `已切到任务页，可继续围绕模块「${context.label}」补齐动作`);
          }
          clearRequest();
          return;
        }
        if (context.objectType === 'project_flow') {
          setTaskViewMode('list');
          const board = await loadTaskBlock().catch(() => null);
          const scopedTasks = board?.tasks || tasks;
          const fallbackTask = scopedTasks.find((item) => item.projectFlowId === context.objectId);
          const scopedClientId = fallbackTask?.clientId || currentClientId || null;
          const detail = scopedClientId ? await getProjectFlowDetail(scopedClientId, context.objectId).catch(() => null) : null;
          const targetTask = detail
            ? scopedTasks.find((item) => detail.relatedTaskIds.includes(item.id))
            : fallbackTask;
          if (targetTask) {
            openTaskEditor(targetTask);
            flash('success', detail?.contextSummary || `已定位到流程「${context.label}」`);
          } else {
            flash('success', detail?.contextSummary || `已切到任务页，可继续围绕流程「${context.label}」补齐动作`);
          }
          clearRequest();
          return;
        }
        setTaskViewMode('review');
        flash('success', `已切到周复盘，可继续查看「${context.label}」`);
        clearRequest();
      };
      void run();
      return () => {
        cancelled = true;
      };
    }, [activeTab, currentClientId, flash, growthContextJump, tasks]);

    const handleCalendarShift = (monthDelta: number) => {
      const nextState = shiftCalendarMonth(taskCalendarDate, taskSelectedDate.getDate(), monthDelta);
      setTaskCalendarDate(nextState.calendarDate);
      setTaskSelectedDay(nextState.selectedDay);
      setTaskSelectedDate(new Date(nextState.calendarDate.getFullYear(), nextState.calendarDate.getMonth(), nextState.selectedDay));
    };

    const handleCalendarToday = () => {
      const todayState = getTodayCalendarState();
      setTaskCalendarDate(todayState.calendarDate);
      setTaskSelectedDay(todayState.selectedDay);
      setTaskSelectedDate(new Date(todayState.calendarDate.getFullYear(), todayState.calendarDate.getMonth(), todayState.selectedDay));
    };

    const handleCalendarDateSelect = (date: Date) => {
      setTaskCalendarDate(new Date(date.getFullYear(), date.getMonth(), 1));
      setTaskSelectedDay(date.getDate());
      setTaskSelectedDate(date);
    };

    const handleTaskCalendarDateSelect = (date: Date) => {
      setTaskSelectedDay(date.getDate());
      setTaskSelectedDate(date);
    };

    const handleAlignTaskCalendarDate = (date: Date) => {
      setTaskCalendarDate(new Date(date.getFullYear(), date.getMonth(), 1));
    };

    const focusCalendarOnTaskDate = (dueDate?: string | null, ddl?: string | null) => {
      const explicitDate = parseTaskDateValue(dueDate);
      const fallbackDate = !explicitDate && ddl ? normalizeDdlToDate(ddl) : null;
      const nextDate = explicitDate || fallbackDate;
      if (!nextDate || Number.isNaN(nextDate.getTime())) return;
      setTaskCalendarDate(new Date(nextDate.getFullYear(), nextDate.getMonth(), 1));
      setTaskSelectedDay(nextDate.getDate());
      setTaskSelectedDate(nextDate);
    };

    const toggleTaskStatus = async (id: string, nextDone?: boolean) => {
      const task = tasks.find((item) => item.id === id);
      if (!task) return;
      const willBeDone = nextDone ?? task.status !== 'done';
      const nextStatus = willBeDone ? 'done' : 'doing';
      setUpdatingTaskStatusIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
      setTasks((prev) => prev.map((item) => (item.id === id ? { ...item, status: nextStatus } : item)));
      try {
        await updateTask(id, { status: nextStatus });
        await loadTaskBlock();
        await refreshWorkspace();
        flash('success', willBeDone ? '任务已标记完成' : '任务已恢复待推进');
      } catch (error) {
        await loadTaskBlock().catch(() => undefined);
        flash('error', error instanceof Error ? error.message : '更新任务状态失败');
      } finally {
        setUpdatingTaskStatusIds((prev) => prev.filter((taskId) => taskId !== id));
      }
    };

    const toggleTaskExpanded = (taskId: string) => {
      const isCollapsing = expandedTaskIds.includes(taskId);
      setExpandedTaskIds((prev) =>
        isCollapsing ? prev.filter((id) => id !== taskId) : [...prev, taskId],
      );
    };

    const handleRescheduleTask = async (
      task: Task,
      nextDate: string,
      options?: { preserveCalendarViewport?: boolean },
    ) => {
      const currentParts = splitTaskDueDateTime(task.dueDate);
      const nextParts = splitTaskDueDateTime(nextDate);
      const shouldKeepExplicitTime = hasExplicitTaskDueTime(nextDate) || hasExplicitTaskDueTime(task.dueDate);
      const nextDueDate = nextParts.date
        ? combineTaskDueDateTime(nextParts.date, nextParts.time || currentParts.time || TASK_DEFAULT_DUE_TIME, { includeTime: shouldKeepExplicitTime })
        : combineTaskDueDateTime(nextDate, currentParts.time || TASK_DEFAULT_DUE_TIME, { includeTime: shouldKeepExplicitTime });
      const nextDueValue = nextDueDate || nextDate;
      const nextDueLabel = formatTaskDateWindowLabel(task.startDate, nextDueValue);
      const previousTaskSnapshot = task;
      const applyLocalTaskPatch = (nextTask: Task) => {
        const nextTaskDueParts = splitTaskDueDateTime(nextTask.dueDate);
        setTasks((prev) => prev.map((item) => (item.id === nextTask.id ? { ...item, ...nextTask } : item)));
        setEditingTask((prev) => (prev.id === nextTask.id
          ? {
              ...prev,
              startDate: nextTask.startDate || prev.startDate,
              dueDate: nextTaskDueParts.date || prev.dueDate,
              dueTime: nextTaskDueParts.time || prev.dueTime || TASK_DEFAULT_DUE_TIME,
              hasSpecificDueTime: Boolean(nextTaskDueParts.time),
              ddl: nextTask.ddl || formatTaskDateWindowLabel(nextTask.startDate, nextTask.dueDate || nextDueValue),
            }
          : prev));
      };

      applyLocalTaskPatch({
        ...task,
        dueDate: nextDueValue,
        ddl: nextDueLabel,
      });

      if (!options?.preserveCalendarViewport) {
        focusCalendarOnTaskDate(nextDueValue, nextDueLabel);
      }
      try {
        const updatedTask = await updateTask(task.id, {
          dueDate: nextDueValue,
          ddl: nextDueLabel,
        });
        applyLocalTaskPatch(updatedTask);
        flash('success', `任务已调整到 ${nextDueLabel}。`);
      } catch (error) {
        applyLocalTaskPatch(previousTaskSnapshot);
        flash('error', error instanceof Error ? error.message : '任务调整失败');
      }
    };

    const handleUpdateTaskDuration = async (task: Task, durationMinutes: number) => {
      const safeDuration = Math.max(15, Math.min(12 * 60, Math.round(durationMinutes / 15) * 15));
      await updateTask(task.id, {
        durationMinutes: safeDuration,
      });
      await loadTaskBlock();
      flash('success', `任务时长已调整为 ${safeDuration} 分钟。`);
    };

    const applyEditingTaskDueTime = (nextDueTime: string) => {
      setEditingTask((prev) => {
        const normalizedDueTime = normalizeTaskTimeInput(nextDueTime) || TASK_DEFAULT_DUE_TIME;
        const nextDueValue = combineTaskDueDateTime(prev.dueDate, normalizedDueTime, {
          includeTime: prev.hasSpecificDueTime,
        });
        return {
          ...prev,
          dueTime: normalizedDueTime,
          ddl: nextDueValue ? formatTaskDateWindowLabel(prev.startDate, nextDueValue) : (prev.dueDate ? formatTaskDateWindowLabel(prev.startDate, prev.dueDate) : '待确认'),
        };
      });
    };

    const applyEditingTaskStartTime = (nextStartTime: string) => {
      setEditingTask((prev) => {
        const normalizedStartTime = normalizeTaskTimeInput(nextStartTime);
        const nextStartValue = prev.startDate
          ? combineTaskDateTime(prev.startDate, normalizedStartTime, {
            includeTime: prev.hasSpecificDueTime && Boolean(normalizedStartTime),
          })
          : '';
        const nextDueValue = combineTaskDueDateTime(prev.dueDate, prev.dueTime || TASK_DEFAULT_DUE_TIME, {
          includeTime: prev.hasSpecificDueTime,
        });
        return {
          ...prev,
          startTime: normalizedStartTime,
          ddl: nextDueValue ? formatTaskDateWindowLabel(nextStartValue || prev.startDate, nextDueValue) : (prev.dueDate ? formatTaskDateWindowLabel(nextStartValue || prev.startDate, prev.dueDate) : '待确认'),
        };
      });
    };

    const applyEditingTaskDueDate = (nextDueDate: string) => {
      setEditingTask((prev) => {
        const normalizedStartDate = prev.startDate && nextDueDate && prev.startDate > nextDueDate ? nextDueDate : prev.startDate;
        const nextDueValue = combineTaskDueDateTime(nextDueDate, prev.dueTime || TASK_DEFAULT_DUE_TIME, {
          includeTime: prev.hasSpecificDueTime,
        });
        return {
          ...prev,
          startDate: normalizedStartDate,
          dueDate: nextDueDate,
          dueTime: prev.dueTime || TASK_DEFAULT_DUE_TIME,
          ddl: nextDueValue ? formatTaskDateWindowLabel(normalizedStartDate, nextDueValue) : '待确认',
        };
      });
      const parsedDate = parseTaskDateValue(nextDueDate);
      if (parsedDate) {
        setDuePickerMonth(new Date(parsedDate.getFullYear(), parsedDate.getMonth(), 1));
      }
    };

    const applyEditingTaskStartDate = (nextStartDate: string) => {
      setEditingTask((prev) => {
        const normalizedDueDate = prev.dueDate && nextStartDate && nextStartDate > prev.dueDate ? nextStartDate : prev.dueDate;
        const nextDueValue = combineTaskDueDateTime(normalizedDueDate, prev.dueTime || TASK_DEFAULT_DUE_TIME, {
          includeTime: prev.hasSpecificDueTime,
        });
        const normalizedStartTime = nextStartDate ? prev.startTime : '';
        const nextStartValue = nextStartDate
          ? combineTaskDateTime(nextStartDate, normalizedStartTime, {
            includeTime: prev.hasSpecificDueTime && Boolean(normalizedStartTime),
          })
          : '';
        return {
          ...prev,
          startDate: nextStartDate,
          startTime: normalizedStartTime,
          dueDate: normalizedDueDate,
          ddl: nextDueValue ? formatTaskDateWindowLabel(nextStartValue || nextStartDate, nextDueValue) : (normalizedDueDate ? formatTaskDateWindowLabel(nextStartValue || nextStartDate, normalizedDueDate) : '待确认'),
        };
      });
    };

    const setEditingTaskSpecificDueTime = (enabled: boolean) => {
      setEditingTask((prev) => {
        const nextDueTime = prev.dueTime || TASK_DEFAULT_DUE_TIME;
        const nextDueValue = combineTaskDueDateTime(prev.dueDate, nextDueTime, { includeTime: enabled });
        return {
          ...prev,
          hasSpecificDueTime: enabled,
          dueTime: nextDueTime,
          ddl: nextDueValue ? formatTaskDateWindowLabel(prev.startDate, nextDueValue) : (prev.dueDate ? formatTaskDateWindowLabel(prev.startDate, prev.dueDate) : '待确认'),
        };
      });
    };

    const clearEditingTaskSchedule = () => {
      setEditingTask((prev) => ({
        ...prev,
        startDate: '',
        dueDate: '',
        dueTime: TASK_DEFAULT_DUE_TIME,
        hasSpecificDueTime: false,
        ddl: '待确认',
      }));
    };

    const handleSaveAgentWeeklyPlan = async (payload: AgentWeeklyPlanPayload) => {
      if (currentSessionUser?.primaryRole !== 'admin') return;
      await updateAgentWeeklyPlan(payload.weekLabel, payload.agentKey, payload);
      await Promise.all([
        loadAgentWorklogBlock(calendarMonthLabel),
        loadReviewBlock(),
      ]);
      flash('success', '机器人部门正式计划已更新。');
    };

    const handleManualTaskViewModeChange = (mode: TaskViewMode) => {
      if (mode === 'review') {
        setGrowthContextJump(null);
        void loadReviewBlock(reviewDashboard?.currentReview?.weekLabel);
      }
      if (mode !== 'list') {
        setDrillTaskViewOverride(null);
      }
      if (mode === 'calendar') {
        blockTaskInteractions(1400);
        guardCalendarTaskOpen(2200);
      }
      setTaskViewMode(mode);
    };

    useEffect(() => {
      const enteredCalendarMode = taskViewMode === 'calendar' && previousTaskViewModeRef.current !== 'calendar';
      const enteredTasksTabWithCalendar = activeTab === 'tasks'
        && taskViewMode === 'calendar'
        && previousActiveTabRef.current !== 'tasks';

      if (enteredCalendarMode || enteredTasksTabWithCalendar) {
        blockTaskInteractions(1400);
        guardCalendarTaskOpen(2200);
      }

      previousTaskViewModeRef.current = taskViewMode;
      previousActiveTabRef.current = activeTab;
    }, [activeTab, taskViewMode]);

    const handleApproveTaskReview = async (taskId: string) => {
      try {
        await approveTaskReview(taskId);
        await Promise.all([
          loadTaskBlock(),
          loadReviewBlock(reviewDashboard?.currentReview?.weekLabel),
        ]);
        flash('success', '任务已通过复核。');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '复核通过失败');
      }
    };

    const handleReturnTaskReview = async (taskId: string) => {
      const reason = window.prompt('请填写退回复核原因');
      if (reason === null) return;
      if (!reason.trim()) {
        flash('error', '请填写退回复核原因。');
        return;
      }
      try {
        await returnTaskReview(taskId, reason.trim());
        await Promise.all([
          loadTaskBlock(),
          loadReviewBlock(reviewDashboard?.currentReview?.weekLabel),
        ]);
        flash('success', '任务已退回复核。');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '退回复核失败');
      }
    };

    const handleCompleteWithReview = async (taskId: string) => {
      const reviewNote = window.prompt('请填写完成复核备注（说明完成情况）');
      if (reviewNote === null) return;
      if (!reviewNote.trim()) {
        flash('error', '请填写复核备注。');
        return;
      }
      try {
        await completeTaskWithReview(taskId, reviewNote.trim());
        await Promise.all([
          loadTaskBlock(),
          loadReviewBlock(reviewDashboard?.currentReview?.weekLabel),
        ]);
        flash('success', '任务已完成并发起复核。');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '完成复核失败');
      }
    };

    const handleConfirmTasks = async (idsToConfirm: string[]) => {
      const taskIds = Array.from(new Set(idsToConfirm)).filter(Boolean);
      if (taskIds.length === 0) return;
      setTransitioningInboxTaskIds((prev) => Array.from(new Set([...prev, ...taskIds])));
      setSelectedInboxIds((prev) => prev.filter((id) => !taskIds.includes(id)));
      const results = await Promise.allSettled(taskIds.map((id) => confirmTask(id)));
      const failedIds = results.flatMap((result, index) => (result.status === 'rejected' ? [taskIds[index]] : []));
      const succeededIds = taskIds.filter((id) => !failedIds.includes(id));
      if (failedIds.length > 0) {
        setTransitioningInboxTaskIds((prev) => prev.filter((id) => !failedIds.includes(id)));
        const firstFailure = results.find((result) => result.status === 'rejected') as PromiseRejectedResult | undefined;
        flash('error', firstFailure?.reason instanceof Error ? firstFailure.reason.message : '部分协作任务确认失败');
      }
      if (succeededIds.length > 0) {
        try {
          await loadTaskBlock();
          flash('success', succeededIds.length === taskIds.length ? '任务已进入进行中。' : `已确认 ${succeededIds.length} 条任务。`);
          setTransitioningInboxTaskIds((prev) => prev.filter((id) => !succeededIds.includes(id)));
        } catch (error) {
          flash('error', error instanceof Error ? error.message : '任务列表刷新失败');
        }
      }
    };

    const confirmReject = async () => {
      if (!rejectReason.trim()) {
        flash('error', '为了保证协作顺畅，请填写退回理由。');
        return;
      }
      setIsRejectModalOpen(false);
      const taskIds = Array.from(new Set(rejectingTaskIds)).filter(Boolean);
      if (taskIds.length === 0) {
        setRejectingTaskIds([]);
        setRejectReason('');
        return;
      }
      setTransitioningInboxTaskIds((prev) => Array.from(new Set([...prev, ...taskIds])));
      setSelectedInboxIds((prev) => prev.filter((id) => !taskIds.includes(id)));
      setRejectingTaskIds([]);
      setRejectReason('');
      const results = await Promise.allSettled(taskIds.map((id) => rejectTask(id, rejectReason.trim())));
      const failedIds = results.flatMap((result, index) => (result.status === 'rejected' ? [taskIds[index]] : []));
      const succeededIds = taskIds.filter((id) => !failedIds.includes(id));
      if (failedIds.length > 0) {
        setTransitioningInboxTaskIds((prev) => prev.filter((id) => !failedIds.includes(id)));
        const firstFailure = results.find((result) => result.status === 'rejected') as PromiseRejectedResult | undefined;
        flash('error', firstFailure?.reason instanceof Error ? firstFailure.reason.message : '部分协作任务退回失败');
      }
      if (succeededIds.length > 0) {
        try {
          await loadTaskBlock();
          flash('success', succeededIds.length === taskIds.length ? '任务已退回。' : `已退回 ${succeededIds.length} 条任务。`);
          setTransitioningInboxTaskIds((prev) => prev.filter((id) => !succeededIds.includes(id)));
        } catch (error) {
          flash('error', error instanceof Error ? error.message : '任务列表刷新失败');
        }
      }
    };

    const generateGlobalSummary = async () => {
      setIsGeneratingGlobal(true);
      try {
        const nextDashboard = await createWeeklyReview(buildReviewPayload());
        clearReviewTasksDirty();
        setSavedReviewGroupId(null);
        setReviewDashboard(nextDashboard);
        void loadReviewHistoryBlock();
        notifyGrowthRefresh();
        setExpandedReviewGroupId(null);
        await loadTaskBlock();
        flash('success', reviewScope === 'work' ? '本周复盘已更新。' : '成长复盘已更新。');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '生成复盘草稿失败');
      } finally {
        setIsGeneratingGlobal(false);
      }
    };

    const persistReviewCollectionDraft = async (groupId: string) => {
      setSavingReviewGroupId(groupId);
      try {
        const targetGroup = [...workReviewGroups, ...personalReviewGroups].find((group) => group.id === groupId);
        const nextDashboard = await createWeeklyReview(targetGroup ? buildReviewPayloadForGroup(targetGroup) : buildReviewPayload());
        if (targetGroup) {
          clearReviewTasksDirty(targetGroup.rows.map(({ task }) => task.id));
        } else {
          clearReviewTasksDirty();
        }
        setSavedReviewGroupId(groupId);
        setReviewDashboard(nextDashboard);
        void loadReviewHistoryBlock();
        notifyGrowthRefresh();
        await loadTaskBlock();
        flash('success', '当前复盘条目已保存。');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '保存失败');
      } finally {
        setSavingReviewGroupId((current) => (current === groupId ? null : current));
      }
    };

    const handleUpdateReviewGroupStatus = async (
      group: ReviewTaskGroup,
      nextStatus: 'done' | 'delayed' | 'cancelled',
    ) => {
      setReviewStatusChangingGroupId(group.id);
      try {
        setSavedReviewGroupId((current) => (current === group.id ? null : current));
        markReviewTasksDirty(group.rows.map(({ task }) => task.id));
        if (nextStatus === 'cancelled') {
          await Promise.all(group.rows.map(({ task }) => deleteTask(task.id)));
          setReviewForm((prev) => {
            const nextEntries = { ...prev.entriesByTaskId };
            for (const { task } of group.rows) {
              delete nextEntries[task.id];
            }
            return {
              ...prev,
              entriesByTaskId: nextEntries,
            };
          });
        } else {
          const nextTaskStatus: Task['status'] = nextStatus === 'done' ? 'done' : 'doing';
          await Promise.all(group.rows.map(({ task }) => updateTask(task.id, { status: nextTaskStatus })));
          setReviewForm((prev) => ({
            ...prev,
            entriesByTaskId: {
              ...prev.entriesByTaskId,
              ...Object.fromEntries(
                group.rows.map(({ task }) => {
                  const current = prev.entriesByTaskId[task.id] ?? createEmptyReviewStructuredNote();
                  const nextNote =
                    nextStatus === 'done'
                      ? {
                          ...current,
                          completionStatus: current.completionStatus === 'done_late' ? 'done_late' : 'done_on_time',
                        }
                      : {
                          ...current,
                          completionStatus: 'not_done',
                        };
                  return [task.id, nextNote];
                }),
              ),
            },
          }));
        }
        await loadTaskBlock();
        await loadReviewBlock(reviewDashboard?.weekLabel);
        await refreshWorkspace();
        flash(
          'success',
          nextStatus === 'done'
            ? '已标记为完成。'
            : nextStatus === 'delayed'
              ? '已标记为延迟。'
              : group.taskCount > 1
                ? '本组任务已删除。'
                : '任务已删除。',
        );
      } catch (error) {
        flash('error', error instanceof Error ? error.message : nextStatus === 'cancelled' ? '任务删除失败' : '任务状态更新失败');
      } finally {
        setReviewStatusChangingGroupId((current) => (current === group.id ? null : current));
      }
    };

    return (
      <div className="mx-auto w-full min-w-0 h-full flex flex-col pt-10 md:pt-12 pb-20 max-w-7xl px-5 lg:px-8 relative">
        <div className={`window-no-drag flex justify-between items-center mb-8 shrink-0 ${isTaskInteractionBlocked ? 'pointer-events-none' : ''}`}>
          <div className="flex items-center gap-4">
            <h1 className="text-[20px] lg:text-[24px] font-bold text-gray-900 tracking-tight">任务与日程</h1>
            <div className="flex bg-gray-100/80 p-1.5 rounded-2xl border border-gray-100 ml-2 overflow-x-auto scrollbar-hide">
              <button
                onClick={() => handleManualTaskViewModeChange('inbox')}
                className={`text-[12px] lg:text-[13px] font-bold px-4 lg:px-5 py-2 rounded-xl transition-all duration-300 flex items-center gap-2 relative whitespace-nowrap ${
                  taskViewMode === 'inbox' ? 'bg-white shadow-sm text-[#5B7BFE]' : 'text-gray-500 hover:text-gray-800'
                }`}
              >
                <Inbox size={16} className={taskViewMode === 'inbox' ? 'text-[#5B7BFE]' : 'text-gray-400'} />
                协作收件箱
                {inboxBadgeCount > 0 && (
                  <span className="ml-1 inline-flex min-w-[18px] items-center justify-center rounded-full bg-rose-500 px-1.5 py-0.5 text-[10px] font-bold leading-none text-white">
                    {inboxBadgeCount}
                  </span>
                )}
              </button>
                {[
                  { id: 'list', label: '任务列表' },
                  { id: 'calendar', label: '我的月历' },
                  { id: 'event_lines', label: '事件线' },
                  { id: 'review', label: '周复盘' },
                ].map((mode) => (
                  <button
                    key={mode.id}
                  onClick={() => handleManualTaskViewModeChange(mode.id as TaskViewMode)}
                    className={`text-[12px] lg:text-[13px] font-bold px-4 lg:px-5 py-2 rounded-xl transition-all duration-300 flex items-center gap-1.5 whitespace-nowrap ${
                      taskViewMode === mode.id ? 'bg-white shadow-sm text-[#5B7BFE]' : 'text-gray-500 hover:text-gray-800'
                    }`}
                >
                  {mode.id === 'review' && taskViewMode === 'review' && <Sparkles size={14} className="text-amber-500" />}
                  {mode.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-3">
            {taskViewMode === 'list' && (
              <Button
                className="px-5 h-[48px] rounded-2xl"
                disabled={isTaskInteractionBlocked}
                onClick={() => {
                  void loadTaskGroupTemplateBlock();
                  setIsTemplateListOpen(true);
                }}
              >
                <LayoutTemplate size={16} />
                从模板创建
              </Button>
            )}
            <Button
              primary
              className="px-6 h-[48px] rounded-2xl"
              disabled={isTaskInteractionBlocked}
              onClick={() => {
                requestCreateTaskEditor();
              }}
            >
              <Plus size={16} />
              新建任务
            </Button>
          </div>
        </div>

        <div ref={taskViewportRef} className={`flex-1 min-w-0 overflow-y-auto scrollbar-hide ${isTaskInteractionBlocked ? 'pointer-events-none' : ''}`}>
          {taskViewMode === 'list' && (
            <div className="max-w-3xl">
              {isLocalSession && baseListTasks.length === 0 && (
                <div className="mb-4 rounded-2xl border border-dashed border-slate-200 bg-white/90 px-5 py-5">
                  <p className="text-[13px] font-bold text-slate-800">当前是本机模式</p>
                  <p className="mt-2 text-[12px] leading-6 text-slate-500">
                    这里只显示本机创建的任务，不显示顾源源等云端账号的协作任务。连接云端后，才会恢复组织共享的任务与协作数据。
                  </p>
                </div>
              )}
              <div className="flex items-center justify-between gap-3 mb-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 cursor-pointer select-none group" onClick={() => setIsTaskGroupOpen(!isTaskGroupOpen)}>
                    <div className={`p-1 rounded-md transition-all ${isTaskGroupOpen ? 'bg-gray-100 text-gray-600' : 'bg-gray-50 text-gray-400 group-hover:bg-gray-100'}`}>
                      <ChevronDown size={14} className={`transition-transform duration-300 ${isTaskGroupOpen ? '' : '-rotate-90'}`} />
                    </div>
                    <span className="text-[14px] font-bold text-gray-800">任务数量</span>
                    <span className="text-[11px] font-bold text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                      {listTasks.length}
                    </span>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <div className="flex items-center gap-1.5 rounded-2xl border border-gray-200 bg-white px-3 py-2">
                    <Search size={14} className="text-gray-400 shrink-0" />
                    <input
                      type="text"
                      value={taskSearchQuery}
                      onChange={(e) => setTaskSearchQuery(e.target.value)}
                      placeholder="搜索任务..."
                      className="w-[260px] bg-transparent text-[12px] font-bold text-gray-800 outline-none placeholder:text-gray-400 placeholder:font-normal"
                    />
                    {taskSearchQuery && (
                      <button type="button" onClick={() => setTaskSearchQuery('')} className="text-gray-300 hover:text-gray-500">
                        <X size={12} />
                      </button>
                    )}
                  </div>
                  <label className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-bold text-gray-500">
                    <span>完成情况</span>
                    <select
                      value={taskListFilter}
                      onChange={(event) => setTaskListFilter(event.target.value as TaskListFilter)}
                      className="bg-transparent text-[12px] font-bold text-gray-800 outline-none"
                    >
                      {TASK_LIST_FILTER_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-bold text-gray-500">
                    <span>类型</span>
                    <select
                      value={taskParticipationFilter}
                      onChange={(event) => setTaskParticipationFilter(event.target.value as TaskParticipationFilter)}
                      className="bg-transparent text-[12px] font-bold text-gray-800 outline-none"
                    >
                      {TASK_PARTICIPATION_FILTER_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-bold text-gray-500">
                    <span>任务清单</span>
                    <select
                      value={taskListNameFilter}
                      onChange={(event) => setTaskListNameFilter(event.target.value)}
                      className="bg-transparent text-[12px] font-bold text-gray-800 outline-none"
                    >
                      <option value="">全部清单</option>
                      <option value={TASK_LIST_FILTER_NONE}>无清单</option>
                      {visibleOrgTaskLists.map((list) => (
                        <option key={`task-list-filter-${list.id}`} value={list.name}>
                          {list.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-bold text-gray-500">
                    <span>时间排序</span>
                    <select
                      value={taskListTimeSort}
                      onChange={(event) => setTaskListTimeSort(event.target.value as TaskTimeSort)}
                      className="bg-transparent text-[12px] font-bold text-gray-800 outline-none"
                    >
                      {TASK_TIME_SORT_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-bold text-gray-500">
                    <span>时间范围</span>
                    <select
                      value={taskListTimeRangeFilter}
                      onChange={(event) => setTaskListTimeRangeFilter(event.target.value as TaskTimeRangeFilter)}
                      className="bg-transparent text-[12px] font-bold text-gray-800 outline-none"
                    >
                      {TASK_TIME_RANGE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  {taskListTimeRangeFilter === 'custom' && (
                    <>
                      <InlineChineseDatePickerField
                        value={taskListCustomStartDate}
                        onChange={setTaskListCustomStartDate}
                        placeholder="开始日期"
                      />
                      <span className="text-[12px] font-bold text-gray-300">至</span>
                      <InlineChineseDatePickerField
                        value={taskListCustomEndDate}
                        onChange={setTaskListCustomEndDate}
                        placeholder="结束日期"
                      />
                    </>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      setActiveTab('settings');
                      setSettingsSection('tasks');
                    }}
                    className="inline-flex items-center gap-2 rounded-2xl border border-[#D7E0FF] bg-[#F8FAFF] px-3 py-2 text-[12px] font-bold text-[#5B7BFE] transition hover:bg-[#EEF2FF]"
                  >
                    <Layout size={14} />
                    清单管理
                  </button>
                </div>
              </div>
              <div className={`space-y-3 transition-all duration-300 ${isTaskGroupOpen ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-4 pointer-events-none h-0 overflow-hidden'}`}>
                {listTasks.length === 0 && (
                  <div className="rounded-2xl border border-dashed border-gray-200 bg-white/80 px-5 py-8 text-center text-[13px] text-gray-400">
                    {baseListTasks.length === 0 ? (
                      <>
                        <div className="mx-auto mb-3 w-10 h-10 rounded-full bg-[#EEF2FF] flex items-center justify-center">
                          <Plus className="w-5 h-5 text-[#5B7BFE]" />
                        </div>
                        <p className="text-[14px] font-bold text-gray-600 mb-1">{isLocalSession ? '本机模式下还没有任务' : '还没有任务'}</p>
                        <p className="text-gray-400 mb-4">
                          {isLocalSession
                            ? '当前不会显示已登录账号的云端任务；如果只是本机使用，可以先创建本地任务。'
                            : '创建第一条任务，系统会自动追踪它的事件线和推进过程。'}
                        </p>
                        <button
                          type="button"
                          onClick={() => { requestCreateTaskEditor(); }}
                          className="rounded-full bg-[#5B7BFE] px-5 py-2 text-[13px] font-bold text-white hover:bg-[#4a6ae8] transition-colors"
                        >
                          创建第一条任务
                        </button>
                      </>
                    ) : (
                      <>
                        <p>当前筛选下暂无任务。</p>
                        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
                          {TASK_PARTICIPATION_FILTER_OPTIONS.map((option) => (
                            <button
                              key={option.value}
                              type="button"
                              onClick={() => setTaskParticipationFilter(option.value)}
                              className={`rounded-full border px-3 py-1.5 text-[12px] font-bold transition-colors ${
                                taskParticipationFilter === option.value
                                  ? 'border-[#5B7BFE] bg-[#EEF2FF] text-[#5B7BFE]'
                                  : 'border-gray-200 bg-white text-gray-500 hover:border-[#C9D6FF] hover:text-[#5B7BFE]'
                              }`}
                            >
                              {option.label} {taskParticipationCounts[option.value]}
                            </button>
                          ))}
                          {TASK_LIST_FILTER_OPTIONS.map((option) => (
                            <button
                              key={option.value}
                              type="button"
                              onClick={() => setTaskListFilter(option.value)}
                              className={`rounded-full border px-3 py-1.5 text-[12px] font-bold transition-colors ${
                                taskListFilter === option.value
                                  ? 'border-[#5B7BFE] bg-[#EEF2FF] text-[#5B7BFE]'
                                  : 'border-gray-200 bg-white text-gray-500 hover:border-[#C9D6FF] hover:text-[#5B7BFE]'
                              }`}
                            >
                              {option.label} {taskBucketCounts[option.value]}
                            </button>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                )}
                {listTasks.map((task) => {
                  const listColor = getListColor(task.listId);
                  const taskPriorityMeta = taskPriorityUi(task.priority);
                  const isExpanded = expandedTaskIds.includes(task.id);
                  const isRecentlyCreatedFromTemplate = recentlyCreatedTaskIds.includes(task.id);
                  const isStatusUpdating = updatingTaskStatusIds.includes(task.id);
                  const canToggleCompletion = taskCanToggleCompletion(task, currentSessionUser?.id);
                  const taskTimelineLabel = formatTaskTimelineLabel(task);
                  const hasDetailContent = Boolean(
                    task.desc ||
                    canReviewTask(task) ||
                    task.collaborators.some((item) => item.inboxStatus === 'returned' && item.returnReason) ||
                    task.eventLineId ||
                    task.projectContext?.clientName,
                  );
                  const toggleTaskCard = () => toggleTaskExpanded(task.id);
                  return (
                    <div
                      key={task.id}
                      className={`bg-white border rounded-2xl p-4 shadow-sm transition-all duration-300 group flex items-start gap-3.5 ${
                        isRecentlyCreatedFromTemplate
                          ? 'border-[#5B7BFE] shadow-[0_12px_32px_rgba(91,123,254,0.16)] bg-[#F8FAFF]'
                          : isExpanded
                          ? 'border-blue-100 shadow-md'
                          : 'border-gray-100 hover:shadow-md hover:border-blue-100'
                      } cursor-pointer`}
                      role="button"
                      tabIndex={0}
                      onClick={toggleTaskCard}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          toggleTaskCard();
                        }
                      }}
                      aria-expanded={isExpanded}
                    >
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          if (!canToggleCompletion) return;
                          void toggleTaskStatus(task.id);
                        }}
                        disabled={isStatusUpdating || !canToggleCompletion}
                        title={canToggleCompletion ? undefined : '只有负责人或协作者可以标记任务完成'}
                        className={`mt-0.5 shrink-0 transition-transform active:scale-90 ${
                          taskPriorityMeta.iconClass
                        } ${isStatusUpdating ? 'cursor-wait opacity-60' : ''} ${!canToggleCompletion ? 'cursor-not-allowed opacity-40 hover:text-gray-300' : ''}`}
                      >
                        {task.status === 'done' ? <CheckCircle2 size={22} strokeWidth={2} /> : <Circle size={22} strokeWidth={2} />}
                      </button>
                      <div className="flex-1 min-w-0 pt-0.5">
                        <div className="flex justify-between items-start gap-3 mb-2">
                          <div className="min-w-0 flex-1 text-left">
                            <p className="text-[14px] lg:text-[15px] text-gray-800 font-bold truncate pr-4 leading-snug">{task.title}</p>
                            {!isExpanded && task.desc && (
                              <p className="mt-2 text-[12px] leading-6 text-gray-400 line-clamp-1">
                                {task.desc}
                              </p>
                            )}
                          </div>
                          <div className="flex shrink-0 items-center gap-3">
                            <button
                              type="button"
                              className="text-[11px] font-bold text-gray-400 hover:text-[#5B7BFE]"
                              onClick={(event) => {
                                event.stopPropagation();
                                openTaskEditor(task);
                              }}
                            >
                              编辑
                            </button>
                            <button
                              type="button"
                              className="text-[11px] font-bold text-gray-300 hover:text-rose-500"
                              onClick={(event) => {
                                event.stopPropagation();
                                requestDeleteTaskRecord(task);
                              }}
                            >
                              删除
                            </button>
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                toggleTaskCard();
                              }}
                              className={`inline-flex items-center justify-center rounded-full border border-gray-200 bg-gray-50 p-1.5 text-gray-400 transition-transform hover:border-[#C9D6FF] hover:text-[#5B7BFE] ${
                                isExpanded ? 'rotate-180' : ''
                              }`}
                              aria-label={isExpanded ? '收起任务卡片' : '展开任务卡片'}
                            >
                              <ChevronDown size={14} />
                            </button>
                          </div>
                        </div>
                        <div className="flex w-full flex-wrap items-center gap-2 text-[11px] font-medium text-left">
                          <span className={`flex items-center gap-1 px-2 py-1 rounded-md ${taskTimelineLabel.startsWith('今天') ? 'bg-orange-50 text-orange-600' : 'bg-gray-50 text-gray-500'}`}>
                            <CalendarIcon size={12} /> {taskTimelineLabel}
                          </span>
                          {taskWaitsForOthers(task, currentSessionUser?.id) && (
                            <span className="flex items-center gap-1 px-2 py-1 rounded-md bg-amber-50 text-amber-700">
                              <Clock size={12} /> 待 {task.collaborationSummary.pending || 0} 人确认
                            </span>
                          )}
                          {(Array.from(new Set((task.listNames && task.listNames.length > 0
                            ? task.listNames
                            : [task.listName || getListName(task.listId)]).filter(Boolean))).length > 0
                            ? Array.from(new Set((task.listNames && task.listNames.length > 0
                              ? task.listNames
                              : [task.listName || getListName(task.listId)]).filter(Boolean)))
                            : ['无清单']).map((listName) => {
                            const chipColor = taskLists.find((list) => list.name === listName)?.color || listColor;
                            return (
                              <span
                                key={`${task.id}-${listName}`}
                                className="flex items-center gap-1 px-2 py-1 rounded-md transition-colors"
                                style={{ color: chipColor, backgroundColor: getTint(chipColor) }}
                              >
                                <FolderDot size={12} /> {listName}
                              </span>
                            );
                          })}
                          {task.projectContext?.clientName && (
                            <span className="flex items-center gap-1 px-2 py-1 rounded-md bg-blue-50 text-blue-700">
                              {task.projectContext.clientName}
                            </span>
                          )}
                          {task.eventLineName && task.eventLineId && (
                            <button
                              type="button"
                              className="flex items-center gap-1 px-2 py-1 rounded-md bg-white text-slate-600 border border-slate-200 hover:bg-slate-50 hover:border-slate-300 transition-colors cursor-pointer"
                              onClick={(e) => { e.stopPropagation(); openEventLineDetail(task.eventLineId!); }}
                            >
                              事件线 · {task.eventLineName}
                            </button>
                          )}
                          {task.collaborators.length > 0 && (
                            <span className="flex items-center gap-1 px-2 py-1 rounded-md bg-gray-50 text-gray-500">
                              <UserPlus size={12} /> {task.collaborators.map((item) => item.fullName).join('、')}
                            </span>
                          )}
                        </div>
                        {isExpanded && (
                          <div className="mt-3 border-t border-gray-100 pt-3" onClick={(event) => event.stopPropagation()}>
                            {task.desc && (
                              <div className="mb-3 rounded-2xl border border-gray-100 bg-gray-50/80 px-3 py-3">
                                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">任务说明</p>
                                <p className="mt-2 text-[12px] leading-6 text-gray-600 whitespace-pre-wrap">{task.desc}</p>
                              </div>
                            )}
                            {task.attachments && task.attachments.length > 0 && (
                              <div className="mb-3 flex flex-wrap gap-2">
                                {task.attachments.map((att) => (
                                  <span key={att.id} className="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-[11px] text-gray-600">
                                    <Paperclip size={11} className="text-gray-400" />
                                    {att.title}
                                  </span>
                                ))}
                              </div>
                            )}
                            {task.clientId && (
                              <div className="mb-3">
                                <label className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-gray-300 bg-white px-3 py-2 text-[11px] font-medium text-gray-500 cursor-pointer transition hover:border-[#5B7BFE] hover:text-[#5B7BFE] hover:bg-blue-50/50">
                                  <UploadCloud size={14} />
                                  上传附件
                                  <input
                                    type="file"
                                    multiple
                                    className="hidden"
                                    onChange={(event) => {
                                      const files = event.target.files;
                                      if (!files || files.length === 0) return;
                                      void uploadAttachmentsToTask(
                                        task.id,
                                        Array.from(files),
                                        { clientId: task.clientId, eventLineId: task.eventLineId, taskTitle: task.title },
                                      ).then(() => loadTaskBlock());
                                      event.target.value = '';
                                    }}
                                  />
                                </label>
                                <span className="ml-2 text-[10px] text-gray-400">附件会先进入当前电脑的{terminology.workspaceLabel}</span>
                              </div>
                            )}
                            {task.status === 'doing' && task.orgContext?.needsReview && canToggleCompletion && (
                              <div className="flex flex-wrap gap-2 mb-2">
                                <Button
                                  className="px-3 py-1.5 text-[12px] bg-emerald-500 text-white hover:bg-emerald-600"
                                  onClick={() => void handleCompleteWithReview(task.id)}
                                >
                                  完成并发起复核
                                </Button>
                              </div>
                            )}
                            {canReviewTask(task) && (
                              <div className="flex flex-wrap gap-2">
                                <Button
                                  primary
                                  className="px-3 py-1.5 text-[12px]"
                                  onClick={() => void handleApproveTaskReview(task.id)}
                                >
                                  通过复核
                                </Button>
                                <Button
                                  className="px-3 py-1.5 text-[12px]"
                                  onClick={() => void handleReturnTaskReview(task.id)}
                                >
                                  退回复核
                                </Button>
                              </div>
                            )}
                            {task.collaborators.some((item) => item.inboxStatus === 'returned' && item.returnReason) && (
                              <p className="text-[11px] text-rose-600 mt-2">
                                退回反馈：{task.collaborators.filter((item) => item.inboxStatus === 'returned' && item.returnReason).map((item) => `${item.fullName}：${item.returnReason}`).join('；')}
                              </p>
                            )}
                            {!task.desc && !canReviewTask(task) && !task.collaborators.some((item) => item.inboxStatus === 'returned' && item.returnReason) && !hasDetailContent && (
                              <div className="mb-3 rounded-2xl border border-dashed border-gray-200 bg-gray-50/70 px-3 py-3">
                                <p className="text-[12px] text-gray-400 italic">点击编辑可以为这条任务添加详细描述、背景说明或注意事项。</p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {taskViewMode === 'inbox' && (
            <div className="max-w-4xl">
              <div className="bg-white border border-gray-100 rounded-3xl p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
                  <div>
                    <h2 className="text-[18px] font-bold text-gray-900">协作收件箱</h2>
                    <p className="text-[12px] text-gray-500 mt-1">
                      这里统一显示需要你确认、已发出待他人确认，以及系统协作通知。待确认任务一旦确认接受，就会进入任务列表；自己发起的协作任务会同时保存在任务列表，确认完成后收件箱不再显示该任务，以免消息堆积。
                    </p>
                  </div>
                  {actionableInboxTasks.length > 0 && (
                    <div className="flex items-center gap-2">
                      <Button onClick={() => setSelectedInboxIds(isAllSelected ? [] : actionableInboxTasks.map((task) => task.id))}>{isAllSelected ? '取消全选' : '全选'}</Button>
                      <Button primary onClick={() => void handleConfirmTasks(selectedInboxIds.length ? selectedInboxIds : actionableInboxTasks.map((task) => task.id))}>
                        确认接收
                      </Button>
                    </div>
                  )}
                </div>
                <div className="mb-4 flex flex-wrap items-center gap-2">
                  <label className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-bold text-gray-500">
                    <span>时间排序</span>
                    <select
                      value={inboxTimeSort}
                      onChange={(event) => setInboxTimeSort(event.target.value as TaskTimeSort)}
                      className="bg-transparent text-[12px] font-bold text-gray-800 outline-none"
                    >
                      {TASK_TIME_SORT_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-bold text-gray-500">
                    <span>时间范围</span>
                    <select
                      value={inboxTimeRangeFilter}
                      onChange={(event) => setInboxTimeRangeFilter(event.target.value as TaskTimeRangeFilter)}
                      className="bg-transparent text-[12px] font-bold text-gray-800 outline-none"
                    >
                      {TASK_TIME_RANGE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  {inboxTimeRangeFilter === 'custom' && (
                    <>
                      <InlineChineseDatePickerField
                        value={inboxCustomStartDate}
                        onChange={setInboxCustomStartDate}
                        placeholder="开始日期"
                      />
                      <span className="text-[12px] font-bold text-gray-300">至</span>
                      <InlineChineseDatePickerField
                        value={inboxCustomEndDate}
                        onChange={setInboxCustomEndDate}
                        placeholder="结束日期"
                      />
                    </>
                  )}
                </div>
                <div className="space-y-3">
                  {inboxFeedItems.map(({ task, kind }) => {
                    const isExpanded = expandedInboxTaskIds.includes(task.id);
                    const isSelectable = kind === 'confirmable';
                    const notificationSummary = parseEventLineNotificationSummary(task);
                    const pendingParticipantNames = Array.from(
                      new Set(
                        task.collaborators
                          .filter((item) => item.inboxStatus === 'pending')
                          .map((item) => ({
                            id: (item.userId || item.id || '').trim(),
                            name: (item.fullName || '').trim(),
                          }))
                          .filter((item) => item.name)
                          .filter((item) => {
                            const creatorId = (task.creatorId || '').trim();
                            const creatorName = (task.creatorName || '').trim();
                            if (creatorId && item.id && item.id === creatorId) return false;
                            if (creatorName && item.name === creatorName) return false;
                            if (kind === 'outbound' && currentSessionUser?.id && item.id && item.id === currentSessionUser.id) return false;
                            if (kind === 'outbound' && currentSessionUser?.fullName && item.name === currentSessionUser.fullName) return false;
                            return true;
                          })
                          .map((item) => item.name),
                      ),
                    );
                    const pendingCount = pendingParticipantNames.length;
                    const creatorLabel =
                      notificationSummary?.operator
                      || task.creatorName
                      || (kind === 'outbound' ? currentSessionUser?.fullName : null)
                      || '未标记';
                    const statusBadge =
                      kind === 'notification'
                        ? { label: '系统通知', className: 'bg-sky-50 text-sky-700' }
                        : kind === 'outbound'
                          ? { label: pendingCount > 0 ? `待 ${pendingCount} 人确认` : '已发出', className: 'bg-amber-50 text-amber-700' }
                          : { label: '待你确认', className: 'bg-blue-50 text-[#5B7BFE]' };
                    const notificationTimeLabel = new Date(task.createdAt).toLocaleString('zh-CN', {
                      month: '2-digit',
                      day: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit',
                      hour12: false,
                    });
                    return (
                      <div
                        key={`${kind}-${task.id}`}
                        className={`border rounded-2xl px-4 py-4 shadow-sm transition-all duration-300 flex items-start gap-3 ${
                          isExpanded ? 'border-blue-100 shadow-md bg-[#FBFCFF]' : 'border-gray-100 bg-white hover:border-blue-100 hover:shadow-md'
                        }`}
                      >
                        {isSelectable ? (
                          <input
                            type="checkbox"
                            checked={selectedInboxIds.includes(task.id)}
                            onChange={(event) => {
                              setSelectedInboxIds((prev) =>
                                event.target.checked ? [...prev, task.id] : prev.filter((item) => item !== task.id),
                              );
                            }}
                            className="mt-1 h-4 w-4 rounded border-gray-300 text-[#5B7BFE] focus:ring-[#5B7BFE]"
                          />
                        ) : (
                          <div className="mt-1 h-4 w-4 rounded-full border border-amber-300 bg-amber-50" />
                        )}
                        <div className="min-w-0 flex-1">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className={`px-2 py-1 rounded-md text-[10px] font-bold ${statusBadge.className}`}>{statusBadge.label}</span>
                                <span className="text-[14px] font-bold text-gray-900">{task.title}</span>
                              </div>
                              {!isExpanded && (
                                <p className="mt-2 text-[12px] text-gray-500 line-clamp-2">
                                  {kind === 'notification'
                                    ? notificationSummary
                                      ? `${notificationSummary.operation} · 主要负责人：${notificationSummary.mainOwners}`
                                      : (task.desc || '来自内部协作系统的提醒。')
                                    : (task.desc || '点击展开可查看任务详情与协作状态。')}
                                </p>
                              )}
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              {kind === 'confirmable' && (
                                <>
                                  <Button onClick={() => void handleConfirmTasks([task.id])}>确认</Button>
                                  <Button
                                    onClick={() => {
                                      setRejectingTaskIds([task.id]);
                                      setIsRejectModalOpen(true);
                                    }}
                                  >
                                    退回
                                  </Button>
                                </>
                              )}
                              {kind === 'notification' && task.eventLineId ? (
                                <Button
                                  onClick={async () => {
                                    const detail = await openEventLineDetail(task.eventLineId!);
                                    if (detail) {
                                      await handleMarkNotificationRead(task.id);
                                    }
                                  }}
                                >
                                  查看事件线
                                </Button>
                              ) : kind === 'notification' ? (
                                <Button onClick={() => void handleMarkNotificationRead(task.id)}>查看通知</Button>
                              ) : null}
                              {kind === 'outbound' && <Button onClick={() => openTaskEditor(task)}>查看任务</Button>}
                              <button
                                type="button"
                                onClick={() => {
                                  setExpandedInboxTaskIds((prev) =>
                                    prev.includes(task.id) ? prev.filter((item) => item !== task.id) : [...prev, task.id],
                                  );
                                }}
                                className={`inline-flex items-center justify-center rounded-full border border-gray-200 bg-gray-50 p-1.5 text-gray-400 transition-transform hover:border-[#C9D6FF] hover:text-[#5B7BFE] ${isExpanded ? 'rotate-180' : ''}`}
                                aria-label={isExpanded ? '收起任务卡片' : '展开任务卡片'}
                              >
                                <ChevronDown size={14} />
                              </button>
                            </div>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-medium">
                            <span className="bg-orange-50 text-orange-600 px-2 py-1 rounded-md">
                              {kind === 'notification' ? `通知时间 ${notificationTimeLabel}` : formatTaskTimelineLabel(task)}
                            </span>
                          </div>
                          <div className="mt-2 space-y-1 text-[11px] font-medium">
                            <div className="rounded-xl bg-blue-50 px-3 py-2 text-[#5B7BFE]">
                              {kind === 'notification'
                                ? `操作者：${creatorLabel}`
                                : `发起人：${creatorLabel}`}
                            </div>
                            {kind === 'notification' && notificationSummary ? (
                              <>
                                <div className="rounded-xl bg-sky-50 px-3 py-2 text-sky-700">
                                  事件线操作：{notificationSummary.operation}
                                </div>
                                <div className="rounded-xl bg-slate-50 px-3 py-2 text-slate-600">
                                  主要负责人：{notificationSummary.mainOwners}
                                </div>
                                <div className="rounded-xl bg-slate-50 px-3 py-2 text-slate-600">
                                  参与者：{notificationSummary.participants}
                                </div>
                              </>
                            ) : null}
                            {kind !== 'notification' ? (
                              <div className="rounded-xl bg-amber-50 px-3 py-2 text-amber-700">
                                待确认：{pendingParticipantNames.length > 0 ? pendingParticipantNames.join('、') : '无'}
                              </div>
                            ) : null}
                          </div>
                          {isExpanded && (
                            <div className="mt-3 border-t border-gray-100 pt-3 space-y-3">
                              {kind === 'notification' && notificationSummary ? (
                                <div className="rounded-2xl border border-sky-100 bg-sky-50/80 px-3 py-3 text-[12px] leading-6 text-sky-700">
                                  <div>事件线标题：{notificationSummary.eventLineTitle}</div>
                                  <div>事件线操作：{notificationSummary.operation}</div>
                                  <div>操作者：{notificationSummary.operator}</div>
                                  <div>操作时间：{notificationSummary.operatedAt || notificationTimeLabel}</div>
                                  <div>主要负责人：{notificationSummary.mainOwners}</div>
                                  <div>参与者：{notificationSummary.participants}</div>
                                </div>
                              ) : (
                                <div className="rounded-2xl border border-gray-100 bg-gray-50/80 px-3 py-3">
                                  <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">{kind === 'notification' ? '通知内容' : '任务说明'}</p>
                                  <p className="mt-2 text-[12px] leading-6 text-gray-600 whitespace-pre-wrap">{task.desc || (kind === 'notification' ? '来自内部协作系统的提醒。' : '暂无详细说明。')}</p>
                                </div>
                              )}
                              {kind === 'notification' && task.eventLineId ? (
                                <div className="rounded-2xl border border-sky-100 bg-sky-50/80 px-3 py-3 text-[12px] leading-6 text-sky-700">
                                  这是一条只读系统通知。查看事件线后，这条通知会自动标记为已阅，不会进入待确认任务。
                                </div>
                              ) : null}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  {inboxFeedItems.length === 0 && (
                    <div className="text-center py-16 text-gray-400">
                      <div className="mx-auto mb-3 w-10 h-10 rounded-full bg-emerald-50 flex items-center justify-center">
                        <Inbox className="w-5 h-5 text-emerald-500" />
                      </div>
                      <p className="text-[14px] font-bold text-gray-600 mb-1">{isLocalSession ? '当前是本机模式' : '收件箱已清空'}</p>
                      <p className="text-[13px] text-gray-400">
                        {isLocalSession
                          ? '收件箱只显示云端协作任务。退出登录后，这里不会再显示任何账号的协作数据。'
                          : '待你确认或等待对方确认的协作任务会出现在这里。'}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {taskViewMode === 'calendar' && (
            <div className="space-y-3">
              {isLocalSession && calendarTasks.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-white/90 px-5 py-12 text-center">
                  <p className="text-[14px] font-bold text-slate-700">当前是本机模式</p>
                  <p className="mt-2 text-[13px] leading-6 text-slate-500">
                    月历不会显示已登录账号的云端任务。连接云端后，你才能看到组织共享日程；如果只是本机使用，先创建本地任务即可。
                  </p>
                </div>
              ) : (
                <TaskCalendarView
                  tasks={calendarTasks}
                  currentUserId={currentSessionUser?.id || null}
                  calendarDisplayMode={taskCalendarDisplayMode}
                  onSetCalendarDisplayMode={setTaskCalendarDisplayMode}
                  calendarDate={taskCalendarDate}
                  selectedDate={taskSelectedDate}
                  onSelectDate={handleTaskCalendarDateSelect}
                  onShiftMonth={handleCalendarShift}
                  onAlignCalendarDate={handleAlignTaskCalendarDate}
                  onGoToToday={handleCalendarToday}
                  onOpenTaskEditor={openTaskEditorFromCalendar}
                  onCalendarNotice={flash}
                  onToggleTaskStatus={toggleTaskStatus}
                  onRescheduleTask={handleRescheduleTask}
                  onUpdateTaskDuration={handleUpdateTaskDuration}
                  onApproveTaskReview={handleApproveTaskReview}
                  onReturnTaskReview={handleReturnTaskReview}
                  isTaskOverdue={isTaskOverdue}
                  showCollaborativeTasks={hidePersonalTasks}
                  onToggleCollaborativeTasks={() => setHidePersonalTasks((prev) => !prev)}
                />
              )}
            </div>
          )}

          {taskViewMode === 'agent_schedule' && currentSessionUser?.primaryRole === 'admin' && (
            <AgentSimulationCalendarView
              agentWorklogs={agentWorklogs}
              weeklyDigests={selectedWeekAgentDigests}
              weeklyPlans={selectedWeekAgentPlans}
              onSavePlan={handleSaveAgentWeeklyPlan}
              calendarDate={taskCalendarDate}
              selectedDay={taskSelectedDay}
              onSelectDay={setTaskSelectedDay}
              onSelectDate={handleCalendarDateSelect}
              onShiftMonth={handleCalendarShift}
              onGoToToday={handleCalendarToday}
            />
          )}

          {taskViewMode === 'event_lines' && (
            <div className="max-w-4xl mx-auto pb-10">
              {isLocalSession ? (
                <div className="rounded-2xl border border-dashed border-gray-200 bg-white/80 px-5 py-12 text-center">
                  <p className="text-[14px] font-bold text-gray-700">当前未连接云端协作</p>
                  <p className="mt-2 text-[13px] leading-6 text-gray-400">
                    事件线按组织协作维度管理。退出登录后，这里只保留空白骨架，不显示任何云端账号的事件线内容。
                  </p>
                </div>
              ) : (
                <>
              <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div className="flex items-end gap-3">
                  <button
                    type="button"
                    onClick={handleOpenEventLineCreate}
                    className="inline-flex items-center gap-2 rounded-2xl bg-[#5B7BFE] px-4 py-3 text-[13px] font-bold text-white shadow-[0_12px_30px_rgba(91,123,254,0.24)] transition hover:bg-[#4A6AE8]"
                  >
                    <Plus size={16} />
                    新建事件线
                  </button>
                  <div>
                    <h2 className="text-[18px] font-bold text-gray-900">事件线</h2>
                    <p className="mt-1 text-[12px] text-gray-500">
                      按{terminology.singularLabel}查看事件线；卡片主体进入汇报预览，右侧可直接切状态、编辑或删除。仅管理员和主要负责人可操作；参与者仍可查看、关联票据与导出汇报。
                    </p>
                  </div>
                </div>
                <div className="window-no-drag w-full md:max-w-[320px]" style={{ WebkitAppRegion: 'no-drag' as any }}>
                  <label className="mb-2 block text-[11px] font-bold text-gray-400">{terminology.singularLabel}筛选</label>
                  <div className="relative" ref={elProjectDropdownRef}>
                    {/* 自定义下拉按钮 — 替代原生 select，绕过 Electron hiddenInset 事件丢失 */}
                    <button
                      type="button"
                      onClick={() => {
                        setElProjectDropdownOpen((v) => !v);
                      }}
                      className="w-full appearance-none rounded-2xl border border-gray-200 bg-white/90 py-3 pl-4 pr-10 text-left text-[13px] font-semibold text-gray-700 shadow-sm outline-none transition hover:border-[#5B7BFE]/40 focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/10 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
                      style={{ WebkitAppRegion: 'no-drag' as any }}
                    >
                      {eventLineProjectFilterId === '__all__'
                        ? `全部${terminology.pluralLabel}（${eventLineProjectOptions.length}）`
                        : (eventLineProjectOptions.find((o) => o.id === eventLineProjectFilterId)?.label ?? `未知${terminology.singularLabel}`)}
                    </button>
                    <ChevronDown
                      className={`pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 transition-transform ${elProjectDropdownOpen ? 'rotate-180' : ''}`}
                    />
                    {/* 自定义下拉列表 */}
                    {elProjectDropdownOpen && (
                      <div
                        className="absolute left-0 right-0 top-full z-50 mt-1 max-h-[260px] overflow-y-auto rounded-xl border border-gray-200 bg-white shadow-lg"
                        style={{ WebkitAppRegion: 'no-drag' as any }}
                      >
                        <button
                          type="button"
                          onClick={() => {
                            setEventLineProjectFilterId('__all__');
                            setElProjectDropdownOpen(false);
                          }}
                          className={`w-full px-4 py-2.5 text-left text-[13px] transition hover:bg-[#5B7BFE]/5 ${eventLineProjectFilterId === '__all__' ? 'font-bold text-[#5B7BFE] bg-[#5B7BFE]/10' : 'text-gray-700'}`}
                        >
                          全部{terminology.pluralLabel}（{eventLineProjectOptions.length}）
                        </button>
                        {eventLineProjectOptions.map((option) => (
                          <button
                            key={option.id}
                            type="button"
                            onClick={() => {
                              setEventLineProjectFilterId(option.id);
                              setElProjectDropdownOpen(false);
                            }}
                            className={`w-full px-4 py-2.5 text-left text-[13px] transition hover:bg-[#5B7BFE]/5 ${eventLineProjectFilterId === option.id ? 'font-bold text-[#5B7BFE] bg-[#5B7BFE]/10' : 'text-gray-700'}`}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <p className="mt-2 text-[11px] text-gray-500">
                    选择{terminology.singularLabel}后，只显示该{terminology.singularLabel}下的事件线。
                  </p>
                </div>
              </div>
              {filteredEventLines.length === 0 && (
                <div className="rounded-2xl border border-dashed border-gray-200 bg-white/80 px-5 py-12 text-center">
                  <p className="text-[13px] text-gray-400">
                    {eventLinesLoadError || (eventLineProjectFilterId === '__all__'
                      ? '还没有事件线。可以先在这里新建事件线，再把任务挂进对应主线。'
                      : `当前${terminology.singularLabel}下还没有事件线。可先在这里新建一条主线。`)}
                  </p>
                </div>
              )}
              <div className="space-y-3">
                {filteredEventLines.map((el) => {
                  const taskCount = tasks.filter((t) => t.eventLineId === el.id).length;
                  const eventLineManageable = canManageEventLine(el);
                  const participantNames = (el.participantIds || [])
                    .map((id) => eventLineMemberLabelById.get(id))
                    .filter((value): value is string => Boolean(value));
                  return (
                    <div
                      key={el.id}
                      className="w-full rounded-2xl border border-gray-100 bg-white p-5 text-left shadow-sm transition hover:border-blue-100 hover:shadow-md"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <button
                          type="button"
                          className="min-w-0 flex-1 text-left"
                          onClick={() => setReportEventLineId(el.id)}
                        >
                          <p className="text-[15px] font-bold text-gray-900 truncate">{el.name}</p>
                          {el.summary && (
                            <p className="mt-1 text-[12px] leading-5 text-gray-500 line-clamp-2">{el.summary}</p>
                          )}
                          <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                            <span className="rounded-full bg-emerald-50 px-2.5 py-1 font-bold text-emerald-700">{{ active: '进行中', blocked: '受阻', paused: '暂停', done: '已完成', archived: '已完成' }[el.status] || el.status}</span>
                            {el.stage && <span className="rounded-full bg-amber-50 px-2.5 py-1 font-bold text-amber-700">{el.stage}</span>}
                            <span className="rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-600">
                              {(el.ownerNames?.length ? el.ownerNames.join('、') : el.ownerName) ? `主要负责人 · ${el.ownerNames?.length ? el.ownerNames.join('、') : el.ownerName}` : '未设置主要负责人'}
                            </span>
                            {participantNames.length > 0 ? (
                              <span className="rounded-full bg-slate-50 px-2.5 py-1 font-semibold text-slate-500">
                                {`参与者 · ${participantNames.join('、')}`}
                              </span>
                            ) : null}
                            {el.primaryClientName && <span className="rounded-full bg-violet-50 px-2.5 py-1 font-bold text-violet-700">{el.primaryClientName}</span>}
                            <span className="rounded-full bg-gray-100 px-2.5 py-1 font-semibold text-gray-500">{taskCount} 条关联任务</span>
                          </div>
                        </button>
                        <div className="shrink-0 flex flex-col items-end gap-2">
                          <div className="pt-1 text-[11px] text-gray-400">{el.updatedAt.slice(0, 10)}</div>
                          <div className="flex flex-wrap justify-end gap-2">
                            <select
                              value={el.status === 'archived' ? 'done' : el.status}
                              onChange={(event) => void handleEventLineStatusChange(el, event.target.value as 'active' | 'paused' | 'blocked' | 'done')}
                              disabled={isDeletingEventLine || !eventLineManageable}
                              title={eventLineManageable ? '切换事件线状态' : '只有管理员和主要负责人可以切换事件线状态'}
                              className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-bold text-gray-700 outline-none transition hover:border-[#5B7BFE] focus:border-[#5B7BFE] disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
                            >
                              <option value="active">进行中</option>
                              <option value="paused">暂停</option>
                              <option value="blocked">阻塞</option>
                              <option value="done">完成</option>
                            </select>
                          </div>
                          <div className="flex flex-wrap justify-end gap-2">
                          <button
                            type="button"
                            className="rounded-xl border border-[#D7E0FF] bg-[#F8FAFF] px-3 py-2 text-[12px] font-bold text-[#5B7BFE] transition hover:bg-[#EEF2FF]"
                            onClick={() => void openEventLineDetail(el.id)}
                            disabled={!eventLineManageable}
                            title={eventLineManageable ? '编辑事件线' : '只有管理员和主要负责人可以编辑事件线'}
                          >
                            编辑
                          </button>
                            <button
                              type="button"
                              className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-[12px] font-bold text-rose-600 transition hover:bg-rose-100 disabled:opacity-50"
                              onClick={() => void handleDeleteEventLine(el)}
                              disabled={isDeletingEventLine || !eventLineManageable}
                              title={eventLineManageable ? '删除事件线' : '只有管理员和主要负责人可以删除事件线'}
                            >
                              删除
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
                </>
              )}
            </div>
          )}

          {taskViewMode === 'review' && (
            <div className="max-w-5xl mx-auto flex flex-col" style={{ height: 'calc(100vh - 80px)' }}>

              {/* ── 上下文控制栏 ── */}
              <div className="flex items-center justify-between gap-4 py-2 shrink-0">
                <div className="flex items-center gap-3">
                  <div className="flex items-center bg-gray-100/60 p-0.5 rounded-[12px]">
                    <button
                      type="button"
                      onClick={() => { setReviewScope('work'); }}
                      className={`px-3 py-1 rounded-[10px] text-[12px] font-bold transition ${reviewScope === 'work' ? 'bg-white text-[#5B7BFE] shadow-sm border border-gray-200/40' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                      组织复盘
                    </button>
                    <button
                      type="button"
                      onClick={() => { setReviewScope('personal'); }}
                      className={`px-3 py-1 rounded-[10px] text-[12px] font-bold transition ${reviewScope === 'personal' ? 'bg-white text-[#5B7BFE] shadow-sm border border-gray-200/40' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                      成长复盘
                    </button>
                  </div>
                  <div className="flex items-center gap-3 text-[12px] font-bold text-gray-400">
                    <span><span className="text-gray-700">{activeReviewRows.length}</span> 纳入</span>
                    <span><span className="text-emerald-500">{activeReviewRows.filter(r => r.task.status === 'done').length}</span> 完成</span>
                    <span><span className="text-amber-500">{activeReviewRows.filter(r => r.task.status !== 'done').length}</span> 未完成</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => void handleOpenReviewHistory()}
                  className="flex items-center gap-1.5 px-3 py-1 bg-white border border-gray-200 rounded-xl text-[12px] font-bold text-gray-500 hover:bg-gray-50"
                >
                  <Clock size={12} className="text-gray-400" /> {isReviewHistoryOpen ? '收起' : '历史'}
                </button>
              </div>
              <ReviewHistoryPicker
                open={isReviewHistoryOpen}
                loading={isLoadingReviewHistory}
                items={reviewHistory}
                activeWeekLabel={reviewForm.weekLabel || currentWeekLabel()}
                onClose={() => setIsReviewHistoryOpen(false)}
                onSelect={(weekLabel) => void handleSelectHistoricalReview(weekLabel)}
              />

              {/* ── 模块 tab + 视角胶囊（同一行，带下划线） ── */}
              <div className="flex items-center justify-between border-b border-gray-200 mb-0 shrink-0 overflow-x-auto">
                <div className="flex items-center gap-8">
                  {([
                    { id: 'overview' as const, label: '机构概览', Icon: LayoutDashboard },
                    { id: 'events' as const, label: '重点事件线', Icon: GitMerge },
                    { id: 'signals' as const, label: '部门信号', Icon: Radio },
                    { id: 'ai' as const, label: 'AI摘要', Icon: Bot },
                  ]).map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setActiveReviewTab(tab.id)}
                      className={`relative pb-3 flex items-center gap-2 text-[14px] font-bold transition whitespace-nowrap ${activeReviewTab === tab.id ? 'text-[#5B7BFE]' : 'text-gray-400 hover:text-gray-600'}`}
                    >
                      <tab.Icon size={15} className={activeReviewTab === tab.id ? 'text-[#5B7BFE]' : 'text-gray-300'} />
                      {tab.label}
                      {activeReviewTab === tab.id && <span className="absolute bottom-[-1px] left-0 w-full h-[2.5px] bg-[#5B7BFE] rounded-t-full" />}
                    </button>
                  ))}
                </div>
                <div className="flex items-center bg-gray-100/50 p-1 rounded-full mb-3 shrink-0 ml-4">
                  {([
                    { key: 'global' as const, label: '全局视角' },
                    ...(currentSessionUser?.primaryRole === 'admin' ? [{ key: 'ceo' as const, label: 'CEO视角' }] : []),
                    { key: 'department' as const, label: '部门视角' },
                    { key: 'personal' as const, label: '个人视角' },
                  ]).map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => setReviewPerspective(item.key)}
                      className={`px-4 py-1.5 rounded-full text-[12px] font-bold transition ${reviewPerspective === item.key ? 'bg-white text-[#5B7BFE] shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* ── 内容区域（独立滚动，填满剩余高度） ── */}
              <div className="flex-1 overflow-y-auto py-4 min-h-0">

              {/* ── 机构概览 ── */}
              {activeReviewTab === 'overview' && (
                <div className="space-y-5">
                  {/* 执行概览文字 */}
                  <div className="bg-white p-7 rounded-2xl border border-gray-100 shadow-sm space-y-5">
                    <div>
                      <h3 className="text-[11px] font-bold text-gray-300 uppercase tracking-[0.15em] mb-3">执行概览</h3>
                      {selfReviewReport ? (
                        <div className="space-y-2">
                          <p className="text-gray-600 leading-[1.7] text-[14px] font-medium whitespace-pre-wrap">{selfReviewReport.summary}</p>
                        </div>
                      ) : (
                        <p className="text-gray-400 leading-[1.7] text-[14px] font-medium italic">点击下方「生成周复盘」后，AI 将基于本周任务和事件线产出执行概览。</p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* ── 重点事件线 ── */}
              {activeReviewTab === 'events' && (
                <div className="bg-white border border-gray-100 rounded-2xl shadow-sm p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-[16px] font-bold text-gray-900">{reviewScope === 'work' ? '组织复盘事件线' : '成长复盘事件线'}</h3>
                      <p className="text-[12px] text-gray-500 mt-1">
                        {reviewScope === 'work'
                          ? '系统会先按事件线把本周任务串起来；同一条线只复盘一次，没有事件线的任务仍按单条事项处理。'
                          : '成长事项也会优先按事件线归并，避免围绕同一件事重复写多次。'}
                      </p>
                    </div>
                    <span className="text-[11px] font-bold px-3 py-1.5 rounded-full bg-gray-100 text-gray-500">
                      {activeReviewGroups.length} 个模块 · {activeReviewRows.length} 条任务
                    </span>
                  </div>

                  {activeReviewGroups.length === 0 && (
                    <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50/70 px-5 py-10 text-center">
                      <div className="mx-auto mb-3 w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center">
                        <Activity className="w-5 h-5 text-[#5B7BFE]" />
                      </div>
                      {reviewScope === 'work' ? (
                        <>
                          <p className="text-[14px] font-bold text-gray-600 mb-1">{'本周还没有可复盘的公共任务'}</p>
                          <p className="text-[13px] text-gray-400">{'先在任务列表中推进本周的工作，完成的任务会自动出现在这里供你复盘。'}</p>
                        </>
                      ) : (
                        <>
                          <p className="text-[14px] font-bold text-gray-600 mb-1">{'本周还没有带私人标签的任务'}</p>
                          <p className="text-[13px] text-gray-400">{'给任务添加私人标签后，它就会出现在成长复盘中。'}</p>
                        </>
                      )}
                    </div>
                  )}

                  {activeReviewGroups.map((group) => {
                    const isExpanded = expandedReviewGroupId === group.id;
                    const reviewed = group.reviewedCount > 0;
                    const groupDraftStructuredNote = pickSharedReviewStructuredNote(group.rows);
                    const groupHasDirtyEntries = group.rows.some(({ task }) => reviewDirtyTaskIds.includes(task.id));
                    const groupHasSavableContent = group.rows.some(
                      ({ structuredNote, note }) =>
                        hasMeaningfulReviewStructuredNote(structuredNote) || Boolean(note.trim()),
                    );
                    return (
                      <div key={group.id} className={`border rounded-2xl overflow-hidden transition-all ${isExpanded ? 'border-[#5B7BFE] shadow-[0_8px_30px_rgba(91,123,254,0.12)]' : 'border-gray-200'}`}>
                        <button
                          type="button"
                          className="w-full text-left px-5 py-5 bg-white flex items-start justify-between gap-4"
                          onClick={() => setExpandedReviewGroupId(isExpanded ? null : group.id)}
                        >
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className={`text-[15px] font-bold ${group.taskStatus === 'done' ? 'text-gray-400 line-through' : 'text-gray-900'}`}>{group.title}</p>
                              <span className="text-[10px] font-bold px-2 py-1 rounded-full bg-gray-100 text-gray-500">
                                {group.eventLineId ? '事件线复盘' : '单项复盘'}
                              </span>
                              {reviewed && <span className="text-[10px] font-bold px-2 py-1 rounded-full bg-emerald-50 text-emerald-600">已复盘</span>}
                            </div>
                            <div className="flex flex-wrap gap-2 mt-3 text-[11px]">
                              <span className="px-2 py-1 rounded-md bg-gray-50 text-gray-500">
                                本周共 {group.taskCount} 条任务，已完成 {group.completedCount} 条，待推进 {group.pendingCount} 条
                              </span>
                              {group.eventLineName ? (
                                <span className="px-2 py-1 rounded-md bg-[#EEF4FF] text-[#335CFF]">{group.eventLineName}</span>
                              ) : null}
                            </div>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${isExpanded ? 'bg-blue-50 text-[#5B7BFE]' : 'bg-gray-50 text-gray-400'}`}>
                              {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                            </div>
                          </div>
                        </button>
                        {isExpanded && (
                          <div className="border-t border-gray-100 bg-gray-50/50 p-5">
                            <div className="space-y-3 mb-5">
                              {group.hasDivergentNotes ? (
                                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-[12px] leading-6 text-amber-700">
                                  这条事件线下已有不同任务复盘内容。当前按事件线统一编辑后，会把同一条判断同步到这条线下的相关任务。
                                </div>
                              ) : null}
                              <div className="rounded-2xl border border-gray-200 bg-white px-4 py-4">
                                <div className="flex items-center justify-between gap-3">
                                  <p className="text-[12px] font-bold uppercase tracking-[0.16em] text-gray-400">
                                    {group.eventLineId ? '本周事件线任务' : '本周相关任务'}
                                  </p>
                                  <span className="text-[11px] text-gray-400">
                                    {group.taskCount} 条任务
                                  </span>
                                </div>
                                <div className="mt-3 space-y-2">
                                  {group.rows.map(({ task, note: rowNote }) => (
                                    <div key={task.id} className="flex items-center justify-between gap-3 rounded-2xl border border-gray-100 bg-gray-50 px-3 py-2.5">
                                      <div className="min-w-0">
                                        <div className="flex flex-wrap items-center gap-2">
                                          <p className={`text-[13px] font-semibold ${task.status === 'done' ? 'text-gray-400 line-through' : 'text-gray-700'}`}>{task.title}</p>
                                          <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-bold text-gray-400">{reviewStatusLabel(task)}</span>
                                        </div>
                                        <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-gray-400">
                                          <span>{reviewTaskDateLabel(task)}</span>
                                          <span>·</span>
                                          <span>清单：{Array.from(new Set((task.listNames && task.listNames.length > 0 ? task.listNames : [task.listName || getListName(task.listId)]).filter(Boolean))).join('、') || '无清单'}</span>
                                          {rowNote.trim() ? (
                                            <>
                                              <span>·</span>
                                              <span className="text-emerald-600">已有复盘</span>
                                            </>
                                          ) : null}
                                        </div>
                                      </div>
                                      <button
                                        type="button"
                                        className="shrink-0 text-[11px] font-bold text-gray-400 hover:text-[#5B7BFE]"
                                        onClick={() => openTaskEditor(task)}
                                      >
                                        编辑任务
                                      </button>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </div>
                            <WeeklyReviewStructuredFields
                              scope={reviewScope}
                              value={groupDraftStructuredNote}
                              taskStatus={group.taskStatus}
                              onSave={() => void persistReviewCollectionDraft(group.id)}
                              isSaving={savingReviewGroupId === group.id}
                              saveDisabled={!groupHasSavableContent}
                              saveSucceeded={savedReviewGroupId === group.id && !groupHasDirtyEntries}
                              onStatusChange={(nextStatus) => void handleUpdateReviewGroupStatus(group, nextStatus)}
                              isStatusChanging={reviewStatusChangingGroupId === group.id}
                              statusScopeLabel={group.taskCount > 1 ? '本组任务状态' : '本条任务状态'}
                              onChange={(nextValue) => {
                                setSavedReviewGroupId((current) => (current === group.id ? null : current));
                                markReviewTasksDirty(group.rows.map(({ task }) => task.id));
                                setReviewForm((prev) => ({
                                  ...prev,
                                  entriesByTaskId: {
                                    ...prev.entriesByTaskId,
                                    ...Object.fromEntries(
                                      group.rows.map(({ task }) => [task.id, { ...nextValue }]),
                                    ),
                                  },
                                }));
                              }}
                            />
                          </div>
                        )}
                      </div>
                    );
                  })}

                </div>
              )}

              {/* ── 部门信号 ── */}
              {activeReviewTab === 'signals' && (
                <div className="space-y-4">
                  {departmentReports.length > 0 ? (
                    departmentReports.map((report: any, idx: number) => (
                      <div key={idx} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
                        <h2 className="text-[16px] font-bold text-gray-800 mb-4">{typeof report === 'object' && report !== null && 'departmentName' in report ? (report as { departmentName: string }).departmentName : `部门 ${idx + 1}`}</h2>
                        <div className="bg-[#F8F9FB] p-4 rounded-2xl border border-gray-100 text-[14px] font-medium leading-relaxed text-gray-600 italic">
                          "{typeof report === 'string' ? report : typeof report === 'object' && report !== null && 'summary' in report ? (report as { summary: string }).summary : '暂无信号摘要'}"
                        </div>
                        {typeof report === 'object' && report !== null && 'highlights' in report && Array.isArray((report as { highlights: string[] }).highlights) && (
                          <div className="mt-5">
                            <h3 className="text-[11px] font-bold text-gray-300 uppercase tracking-wider mb-3 flex items-center gap-2">
                              <Activity size={14} /> 本周焦点信号
                            </h3>
                            <div className="space-y-2">
                              {((report as { highlights: string[] }).highlights).map((h, i) => (
                                <div key={i} className="bg-gray-50 p-4 rounded-2xl text-[13px] text-gray-600 font-medium border border-gray-100/50">{h}</div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))
                  ) : agentDepartmentDigests.length > 0 ? (
                    agentDepartmentDigests.map((digest: any, idx: number) => (
                      <div key={idx} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
                        <h2 className="text-[16px] font-bold text-gray-800 mb-4">{typeof digest === 'object' && digest !== null && 'departmentName' in digest ? (digest as { departmentName: string }).departmentName : `部门 ${idx + 1}`}</h2>
                        <div className="bg-[#F8F9FB] p-4 rounded-2xl border border-gray-100 text-[14px] font-medium leading-relaxed text-gray-600 italic">
                          "{typeof digest === 'string' ? digest : typeof digest === 'object' && digest !== null && 'content' in digest ? (digest as { content: string }).content : JSON.stringify(digest)}"
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="bg-white p-12 rounded-2xl border border-gray-100 shadow-sm text-center flex flex-col items-center gap-3">
                      <div className="w-12 h-12 bg-gray-50 rounded-2xl flex items-center justify-center text-gray-300">
                        <Radio size={24} />
                      </div>
                      <div>
                        <h3 className="font-bold text-gray-600 text-[15px] mb-1">暂无部门信号</h3>
                        <p className="text-gray-400 text-[13px] font-medium">点击「生成周复盘」后，系统将基于各部门任务数据自动生成信号摘要。</p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {activeReviewTab === 'ai' && reviewScope === 'work' && (selfReviewReport || departmentReports.length > 0 || executiveOrgReport || simulationBundle || agentDepartmentDigests.length > 0 || agentDepartmentPlans.length > 0) && (
                <WeeklyReviewSummaryPanel
                  selfReport={selfReviewReport}
                  selfAnalysis={collectStageAnalysis}
                  departmentReports={departmentReports}
                  executiveOrgReport={executiveOrgReport}
                  organizationDnaModules={organizationDnaModules}
                  onUploadOrganizationDna={(moduleKey) => handleUploadOrgDna(moduleKey)}
                  orgDnaSavingKey={orgDnaSavingKey}
                  agentDepartmentDigests={agentDepartmentDigests}
                  agentDepartmentPlans={agentDepartmentPlans}
                  simulationBundle={simulationBundle}
                  onTriggerAction={handleTriggerReviewAction}
                  onOpenActionResult={handleOpenReviewActionResult}
                  onDrillTarget={handleReviewDashboardDrillTarget}
                  viewerRole={currentSessionUser?.primaryRole === 'admin' ? 'admin' : currentSessionUser?.isDepartmentLead ? 'department_lead' : 'employee'}
                />
              )}

              </div>{/* end overflow-y-auto */}

              {/* ── 右下角固定生成按钮 ── */}
              <div className="fixed bottom-8 right-8 z-40">
                <Button primary className="py-3 px-6 text-[13px] shadow-[0_8px_30px_rgba(91,123,254,0.35)] rounded-full" onClick={() => void generateGlobalSummary()} disabled={isGeneratingGlobal}>
                  {isGeneratingGlobal ? (
                    <>
                      <RefreshCw size={16} className="animate-spin" />
                      生成中...
                    </>
                  ) : (
                    <>
                      <Sparkles size={16} />
                      {reviewScope === 'work' ? '生成周复盘' : '生成成长复盘'}
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}
        </div>

        {activeReviewDrillTarget && (
          <div
            className="fixed inset-0 z-[52] flex items-center justify-center bg-black/30 p-4 backdrop-blur-sm"
            onClick={closeReviewDrillTarget}
          >
            <div
              className="w-full max-w-[920px] rounded-[28px] border border-gray-100 bg-white p-6 shadow-[0_20px_60px_rgba(0,0,0,0.15)]"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[12px] font-bold tracking-[0.14em] text-[#5B7BFE]">DRILL DOWN</p>
                  <h3 className="mt-2 text-[20px] font-bold text-gray-900">{activeReviewDrillTarget.target.targetLabel || '判断下钻'}</h3>
                  <p className="mt-1 text-[12px] leading-6 text-gray-500">
                    这里把当前判断背后的任务、会议、支持请求和附件集中到一层，方便从管理判断回到证据。
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {activeReviewDrillTarget.target.targetType === 'event_line' && (
                    <Button
                      className="px-4 py-2 rounded-2xl text-[12px]"
                      onClick={() => void openEventLineDetail(activeReviewDrillTarget.target.targetId)}
                    >
                      打开事件线
                    </Button>
                  )}
                  <button
                    type="button"
                    className="rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700"
                    onClick={closeReviewDrillTarget}
                    aria-label="关闭判断下钻"
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap gap-2 text-[11px] font-bold">
                <span className="rounded-full bg-slate-100 px-3 py-1.5 text-slate-600">{activeReviewDrillTarget.target.targetType}</span>
                <span className="rounded-full bg-blue-50 px-3 py-1.5 text-[#33449a]">{activeReviewDrillTarget.tasks.length} 条任务</span>
                <span className="rounded-full bg-violet-50 px-3 py-1.5 text-violet-700">{activeReviewDrillTarget.meetings.length} 场会议</span>
                <span className="rounded-full bg-amber-50 px-3 py-1.5 text-amber-700">{activeReviewDrillTarget.supportRequests.length} 条支持请求</span>
                <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-emerald-700">{activeReviewDrillTarget.attachments.length} 个附件</span>
              </div>

              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                <div className="rounded-3xl border border-gray-200 bg-gray-50/70 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-[14px] font-bold text-gray-900">相关任务</h4>
                    {activeReviewDrillTarget.tasks.length > 0 && (
                      <span className="text-[11px] text-gray-400">{activeReviewDrillTarget.tasks.length} 条</span>
                    )}
                  </div>
                  <div className="mt-3 space-y-2">
                    {activeReviewDrillTarget.tasks.length === 0 && (
                      <div className="rounded-2xl bg-white px-3 py-3 text-[12px] text-gray-400">当前没有直接关联的任务。</div>
                    )}
                    {activeReviewDrillTarget.tasks.slice(0, 8).map((task) => (
                      <div key={task.id} className="rounded-2xl bg-white px-3 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-[13px] font-bold text-gray-900">{task.title}</p>
                            <p className="mt-1 text-[11px] leading-5 text-gray-500">{formatTaskTimelineLabel(task)} · 清单：{Array.from(new Set((task.listNames && task.listNames.length > 0 ? task.listNames : [task.listName || getListName(task.listId)]).filter(Boolean))).join('、') || '无清单'}</p>
                          </div>
                          <button
                            type="button"
                            className="shrink-0 text-[11px] font-bold text-[#5B7BFE]"
                            onClick={() => openTaskEditor(task)}
                          >
                            打开
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="rounded-3xl border border-gray-200 bg-gray-50/70 p-4">
                    <div className="flex items-center justify-between gap-2">
                      <h4 className="text-[14px] font-bold text-gray-900">相关会议</h4>
                      <span className="text-[11px] text-gray-400">{activeReviewDrillTarget.meetings.length} 场</span>
                    </div>
                    <div className="mt-3 space-y-2">
                      {activeReviewDrillTarget.meetings.length === 0 && (
                        <div className="rounded-2xl bg-white px-3 py-3 text-[12px] text-gray-400">当前没有直接关联的会议。</div>
                      )}
                      {activeReviewDrillTarget.meetings.slice(0, 6).map((meeting) => (
                        <div key={meeting.id} className="rounded-2xl bg-white px-3 py-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-[13px] font-bold text-gray-900">{meeting.title}</p>
                              <p className="mt-1 text-[11px] text-gray-500">{meeting.stage} · {meeting.scheduledAt || meeting.updatedAt}</p>
                            </div>
                            <button
                              type="button"
                              className="shrink-0 text-[11px] font-bold text-[#5B7BFE]"
                              onClick={() => void handleReviewDashboardDrillTarget({
                                targetType: 'meeting',
                                targetId: meeting.id,
                                targetLabel: meeting.title,
                              })}
                            >
                              证据链
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-3xl border border-gray-200 bg-gray-50/70 p-4">
                    <div className="flex items-center justify-between gap-2">
                      <h4 className="text-[14px] font-bold text-gray-900">支持请求与附件</h4>
                      <span className="text-[11px] text-gray-400">{activeReviewDrillTarget.supportRequests.length + activeReviewDrillTarget.attachments.length} 条证据</span>
                    </div>
                    <div className="mt-3 space-y-2">
                      {activeReviewDrillTarget.supportRequests.slice(0, 4).map((request) => (
                        <div key={request.id} className="rounded-2xl bg-white px-3 py-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-[12px] font-bold text-gray-900">{request.summary}</p>
                              <p className="mt-1 text-[11px] text-gray-500">{request.requestType} · {request.status} · {request.urgency}</p>
                            </div>
                            <button
                              type="button"
                              className="shrink-0 text-[11px] font-bold text-[#5B7BFE]"
                              onClick={() => void handleReviewDashboardDrillTarget({
                                targetType: 'support_request',
                                targetId: request.id,
                                targetLabel: request.summary,
                              })}
                            >
                              证据链
                            </button>
                          </div>
                        </div>
                      ))}
                      {activeReviewDrillTarget.attachments.slice(0, 4).map((attachment) => (
                        <div key={attachment.id} className="rounded-2xl bg-white px-3 py-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-[12px] font-bold text-gray-900">{attachment.title}</p>
                              <p className="mt-1 text-[11px] text-gray-500">{attachment.kind.toUpperCase()} · {attachment.path}</p>
                            </div>
                            <button
                              type="button"
                              className="shrink-0 text-[11px] font-bold text-[#5B7BFE]"
                              onClick={() => void handleReviewDashboardDrillTarget({
                                targetType: 'attachment_group',
                                targetId: `attachment_group:${attachment.id}`,
                                targetLabel: attachment.title,
                                targetFilters: {
                                  attachmentIds: [attachment.id],
                                  taskIds: [attachment.taskId],
                                  eventLineId: attachment.eventLineId || undefined,
                                },
                              })}
                            >
                              证据链
                            </button>
                          </div>
                        </div>
                      ))}
                      {activeReviewDrillTarget.supportRequests.length === 0 && activeReviewDrillTarget.attachments.length === 0 && (
                        <div className="rounded-2xl bg-white px-3 py-3 text-[12px] text-gray-400">当前还没有更多可回看的支持请求或附件证据。</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {isTaskModalOpen && isTaskEventLineCreateOpen && (
          <div
            className="fixed inset-0 z-[95] flex items-center justify-center bg-black/25 px-4 py-6 backdrop-blur-sm"
            onClick={() => {
              if (isCreatingEventLine) return;
              setIsTaskEventLineCreateOpen(false);
              setTaskEventLineCreateDraft(buildTaskEventLineCreateDraft());
            }}
          >
            <div
              className="w-full max-w-[640px] rounded-[24px] border border-gray-100 bg-white p-6 shadow-[0_24px_72px_rgba(0,0,0,0.18)]"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[12px] font-bold tracking-[0.12em] text-[#5B7BFE]">NEW EVENT LINE</p>
                  <h3 className="mt-2 text-[22px] font-bold text-gray-900">新建事件线</h3>
                  <p className="mt-2 text-[13px] leading-6 text-gray-500">
                    事件线名称用来描述一条持续推进的主线，不需要等于当前任务标题。先起一个更稳定的线名，后面再继续挂任务。
                  </p>
                </div>
                <button
                  type="button"
                  className="rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700"
                  onClick={() => {
                    if (isCreatingEventLine) return;
                    setIsTaskEventLineCreateOpen(false);
                    setTaskEventLineCreateDraft(buildTaskEventLineCreateDraft());
                  }}
                  aria-label="关闭新建事件线"
                >
                  <X size={16} />
                </button>
              </div>

              <div className="mt-4 flex flex-wrap gap-2 text-[12px] font-bold">
                {editingTask.clientId && (
                  <span className="rounded-full bg-violet-50 px-3 py-1.5 text-violet-700">
                    {taskClientOptions.find((item) => item.id === editingTask.clientId)?.name || `已选择${terminology.singularLabel}`}
                  </span>
                )}
                {editingTask.title.trim() && (
                  <span className="rounded-full bg-slate-100 px-3 py-1.5 text-slate-600">
                    当前任务：{editingTask.title.trim()}
                  </span>
                )}
              </div>

              <div className="mt-5 space-y-4">
                <div>
                  <label className="mb-2 block text-[12px] font-bold text-gray-500">事件线名称</label>
                  <input
                    value={taskEventLineCreateDraft.name}
                    onChange={(event) => setTaskEventLineCreateDraft((prev) => ({ ...prev, name: event.target.value }))}
                    placeholder="输入事件线名称"
                    className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[15px] font-semibold text-gray-900 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/15 placeholder:text-gray-300"
                    autoFocus
                  />
                  <p className="mt-2 text-[11px] text-gray-400">建议写成一条可持续推进的线名，例如“日慈教师赋能成效表达收束”或“CFFC 工作坊合作推进”。</p>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-[12px] font-bold text-gray-500">当前阶段</label>
                    <input
                      value={taskEventLineCreateDraft.stage}
                      onChange={(event) => setTaskEventLineCreateDraft((prev) => ({ ...prev, stage: event.target.value }))}
                      placeholder="例如：本周推进"
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[14px] text-gray-700 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/15 placeholder:text-gray-300"
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-[12px] font-bold text-gray-500">这条线想推进什么</label>
                    <input
                      value={taskEventLineCreateDraft.intent}
                      onChange={(event) => setTaskEventLineCreateDraft((prev) => ({ ...prev, intent: event.target.value }))}
                      placeholder="可选：写一句这条线想推进什么"
                      className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[14px] text-gray-700 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/15 placeholder:text-gray-300"
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-2 block text-[12px] font-bold text-gray-500">补充说明</label>
                  <textarea
                    value={taskEventLineCreateDraft.summary}
                    onChange={(event) => setTaskEventLineCreateDraft((prev) => ({ ...prev, summary: event.target.value }))}
                    placeholder="可选：补一句背景说明，后面查看事件线时会直接看到。"
                    className="min-h-[96px] w-full resize-none rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[14px] leading-6 text-gray-700 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/15 placeholder:text-gray-300"
                  />
                </div>
              </div>

              <div className="mt-6 flex items-center justify-end gap-3">
                <button
                  type="button"
                  className="rounded-2xl px-4 py-2 text-[13px] font-medium text-gray-500 transition hover:bg-gray-100"
                  onClick={() => {
                    if (isCreatingEventLine) return;
                    setIsTaskEventLineCreateOpen(false);
                    setTaskEventLineCreateDraft(buildTaskEventLineCreateDraft());
                  }}
                >
                  取消
                </button>
                <button
                  type="button"
                  className="rounded-2xl bg-[#5B7BFE] px-5 py-2.5 text-[13px] font-bold text-white transition hover:bg-[#4a6ae8] disabled:cursor-not-allowed disabled:opacity-50"
                  onClick={() => void handleSubmitTaskEventLineCreate()}
                  disabled={isCreatingEventLine || !taskEventLineCreateDraft.name.trim()}
                >
                  {isCreatingEventLine ? '创建中...' : '创建并关联'}
                </button>
              </div>
            </div>
          </div>
        )}

        {isTemplateListOpen && (
          <div className="fixed inset-0 z-[95] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4" onClick={() => setIsTemplateListOpen(false)}>
            <div className="bg-white w-full max-w-5xl rounded-2xl shadow-2xl flex flex-col overflow-hidden max-h-[85vh]" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
                <div>
                  <h2 className="text-lg font-semibold text-gray-800 tracking-wide">任务组模板</h2>
                  <p className="mt-1 text-[12px] text-gray-400">从一个模板批量生成一组普通任务，可选关联已有事件线或新建事件线。</p>
                </div>
                <button onClick={() => setIsTemplateListOpen(false)} className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-colors">
                  <X size={20} />
                </button>
              </div>
              <div className="p-6 overflow-y-auto space-y-6 bg-gray-50/50">
                {isTaskGroupTemplatesLoading ? (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-5 py-10 text-center text-sm text-slate-400">
                    正在载入任务组模板…
                  </div>
                ) : (
                  <>
                    {[
                      { key: 'organization', title: '组织共享模板', description: '当前已加入组织时，这里的模板会默认给整个组织复用。' },
                      { key: 'local', title: '本机模板', description: '未入组织或本机模式下保存的模板，只在当前设备可见。' },
                    ].map((group) => {
                      const templates = taskGroupTemplates
                        .filter((item) => item.scope === group.key)
                        .sort((left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime());
                      if (templates.length === 0) return null;
                      return (
                        <div key={group.key} className="space-y-3">
                          <div>
                            <p className="text-[14px] font-bold text-slate-800">{group.title}</p>
                            <p className="mt-1 text-[12px] text-slate-400">{group.description}</p>
                          </div>
                          <div className="grid gap-3 md:grid-cols-2">
                            {templates.map((template) => (
                              <div key={template.id} className="rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
                                <div className="flex items-start justify-between gap-3">
                                  <div className="min-w-0">
                                    <div className="flex items-center gap-2">
                                      <p className="truncate text-[15px] font-bold text-slate-800">{template.name}</p>
                                      <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-bold text-blue-600">
                                        {template.steps.length} 步
                                      </span>
                                    </div>
                                    <p className="mt-2 text-[12px] leading-6 text-slate-500 line-clamp-2">
                                      {template.scenarioDesc || '未填写适用场景说明。'}
                                    </p>
                                  </div>
                                  <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold text-slate-500">
                                    {template.scope === 'organization' ? '组织' : '本机'}
                                  </span>
                                </div>
                                <div className="mt-4 flex flex-wrap items-center gap-2">
                                  <Button primary onClick={() => openTaskGroupTemplateApply(template)}>
                                    从模板创建
                                  </Button>
                                  <Button onClick={() => handleEditTaskGroupTemplate(template)}>
                                    编辑
                                  </Button>
                                  <Button onClick={() => void handleDeleteTaskGroupTemplateRecord(template)}>
                                    删除
                                  </Button>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                    {taskGroupTemplates.length === 0 && (
                      <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-5 py-10 text-center">
                        <p className="text-[14px] font-bold text-slate-700">还没有任务组模板</p>
                        <p className="mt-2 text-[12px] leading-6 text-slate-400">
                          先建一个常用任务组模板，后面就能按模板一口气创建整组任务。
                        </p>
                      </div>
                    )}
                  </>
                )}
              </div>
              <div className="p-4 border-t border-gray-100 bg-white">
                <button
                  onClick={() => void handleCreateProjectModuleFromTask()}
                  className="w-full py-2.5 flex items-center justify-center gap-2 text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-lg font-medium transition-colors"
                >
                  <Plus size={18} />
                  <span>新建任务组模板</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {isTemplateEditorOpen && (
          <TaskTemplateEditorModal
            mode={templateEditorMode}
            initialData={templateEditorInitialData}
            onClose={() => setIsTemplateEditorOpen(false)}
            onSave={(data) => void handleSaveTemplate(data)}
            memberOptions={eventLineMemberOptions}
          />
        )}

        {taskGroupTemplateApplyTarget && taskGroupTemplateApplyDraft && (
          <div
            className="fixed inset-0 z-[97] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
            onClick={() => {
              if (isApplyingTaskGroupTemplate) return;
              setTaskGroupTemplateCollaboratorMenuStep(null);
              setTaskGroupTemplateApplyTarget(null);
              setTaskGroupTemplateApplyDraft(null);
            }}
          >
            <div className="bg-white w-full max-w-4xl rounded-2xl shadow-2xl flex flex-col overflow-hidden max-h-[88vh]" onClick={(event) => event.stopPropagation()}>
              <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
                <div>
                  <h2 className="text-lg font-semibold text-gray-800 tracking-wide">从模板创建任务</h2>
                  <p className="mt-1 text-[12px] text-gray-400">模板：{taskGroupTemplateApplyTarget.name}</p>
                </div>
                <button
                  onClick={() => {
                    if (isApplyingTaskGroupTemplate) return;
                    setTaskGroupTemplateCollaboratorMenuStep(null);
                    setTaskGroupTemplateApplyTarget(null);
                    setTaskGroupTemplateApplyDraft(null);
                  }}
                  className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-colors"
                >
                  <X size={20} />
                </button>
              </div>
              <div className="overflow-y-auto p-6 space-y-6 bg-gray-50/50">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <p className="text-[13px] font-bold text-slate-800">首任务开始时间</p>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <input
                        type="date"
                        value={taskGroupTemplateApplyDraft.startDate}
                        onChange={(event) => setTaskGroupTemplateApplyDraft((prev) => prev ? { ...prev, startDate: event.target.value } : prev)}
                        className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#5B7BFE]"
                      />
                      <input
                        type="time"
                        value={taskGroupTemplateApplyDraft.startTime}
                        onChange={(event) => setTaskGroupTemplateApplyDraft((prev) => prev ? { ...prev, startTime: event.target.value || TASK_DEFAULT_DUE_TIME } : prev)}
                        className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#5B7BFE]"
                      />
                    </div>
                    <p className="mt-2 text-[11px] leading-5 text-slate-400">如果只选日期不改时间，这组任务会从当天 09:00 开始链式排期。</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <p className="text-[13px] font-bold text-slate-800">创建落点</p>
                    <div className="mt-3 space-y-3">
                      <label className="block">
                        <span className="mb-1 block text-[12px] font-medium text-slate-500">任务清单</span>
                        <select
                          value={taskGroupTemplateApplyDraft.listId}
                          onChange={(event) => setTaskGroupTemplateApplyDraft((prev) => prev ? { ...prev, listId: event.target.value } : prev)}
                          className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#5B7BFE]"
                        >
                          <option value="">不指定清单（创建后为无清单）</option>
                          {activeTaskLists.map((list) => (
                            <option key={list.id} value={list.id}>
                              {list.name}
                            </option>
                          ))}
                        </select>
                        {!taskGroupTemplateApplyDraft.listId && (
                          <p className="mt-2 text-[11px] leading-5 text-slate-400">
                            这批任务会直接以“无清单”创建；后续如需归类，再在任务列表里补挂清单即可。
                          </p>
                        )}
                      </label>
                      <label className="block">
                        <span className="mb-1 block text-[12px] font-medium text-slate-500">关联{terminology.singularLabel}（事件线）</span>
                        <select
                          value={taskGroupTemplateApplyDraft.workObjectId}
                          onChange={(event) => setTaskGroupTemplateApplyDraft((prev) => prev ? { ...prev, workObjectId: event.target.value } : prev)}
                          className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#5B7BFE]"
                        >
                          <option value="">不关联{terminology.singularLabel}</option>
                          {taskClientOptions.map((option) => (
                            <option key={option.id} value={option.id}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                        <p className="mt-2 text-[11px] leading-5 text-slate-400">
                          这里主要用于把本次任务组和事件线放进同一个{terminology.singularLabel}上下文里；如果还没有对应{terminology.singularLabel}，也可以先留空。
                        </p>
                      </label>
                    </div>
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-[13px] font-bold text-slate-800">事件线衔接</p>
                      <p className="mt-1 text-[11px] leading-5 text-slate-400">这一步是可选的。你可以只创建任务组，也可以顺手挂到已有事件线，或新建一条事件线。</p>
                    </div>
                    <select
                      value={taskGroupTemplateApplyDraft.eventLineMode}
                      onChange={(event) => setTaskGroupTemplateApplyDraft((prev) => prev ? {
                        ...prev,
                        eventLineMode: event.target.value as TaskGroupTemplateEventLineMode,
                        eventLineId: event.target.value === 'existing' ? prev.eventLineId : '',
                      } : prev)}
                      className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#5B7BFE]"
                    >
                      <option value="none">不关联事件线</option>
                      <option value="existing">关联已有事件线</option>
                      <option value="create">新建事件线</option>
                    </select>
                  </div>
                  {taskGroupTemplateApplyDraft.eventLineMode === 'existing' && (
                    <div className="mt-4">
                      <select
                        value={taskGroupTemplateApplyDraft.eventLineId}
                        onChange={(event) => setTaskGroupTemplateApplyDraft((prev) => prev ? { ...prev, eventLineId: event.target.value } : prev)}
                        className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#5B7BFE]"
                      >
                        <option value="">请选择已有事件线</option>
                        {sortedEventLines
                          .filter((line) => !taskGroupTemplateApplyDraft.workObjectId || (line.primaryClientId || '') === taskGroupTemplateApplyDraft.workObjectId)
                          .map((line) => (
                            <option key={line.id} value={line.id}>
                              {formatTaskEventLineOptionLabel(line)}
                            </option>
                          ))}
                      </select>
                    </div>
                  )}
                  {taskGroupTemplateApplyDraft.eventLineMode === 'create' && (
                    <div className="mt-4">
                      <input
                        type="text"
                        value={taskGroupTemplateApplyDraft.eventLineName}
                        onChange={(event) => setTaskGroupTemplateApplyDraft((prev) => prev ? { ...prev, eventLineName: event.target.value } : prev)}
                        placeholder="输入要新建的事件线名称"
                        className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#5B7BFE]"
                      />
                    </div>
                  )}
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-[13px] font-bold text-slate-800">逐条微调步骤</p>
                      <p className="mt-1 text-[11px] leading-5 text-slate-400">这里调整的是本次应用结果，不会直接改掉原模板。</p>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold text-slate-500">
                      {taskGroupTemplateApplyDraft.stepOverrides.length} 步
                    </span>
                  </div>
                  <div className="mt-4 space-y-3">
                    {taskGroupTemplateApplyDraft.stepOverrides.map((step, index) => (
                      <div key={`${taskGroupTemplateApplyTarget.id}-${step.stepIndex}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                        <div className="flex items-center gap-3">
                          <span className="text-[11px] font-bold text-slate-400">步骤 {index + 1}</span>
                          <input
                            type="text"
                            value={step.title}
                            onChange={(event) => setTaskGroupTemplateApplyDraft((prev) => prev ? {
                              ...prev,
                              stepOverrides: prev.stepOverrides.map((item) => item.stepIndex === step.stepIndex ? { ...item, title: event.target.value } : item),
                            } : prev)}
                            className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#5B7BFE]"
                            placeholder="任务标题"
                          />
                        </div>
                        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                          <label className="block">
                            <span className="mb-1 block text-[11px] font-medium text-slate-500">负责人</span>
                            <select
                              value={step.ownerId}
                              onChange={(event) => setTaskGroupTemplateApplyDraft((prev) => prev ? {
                                ...prev,
                                stepOverrides: prev.stepOverrides.map((item) => item.stepIndex === step.stepIndex
                                  ? {
                                    ...item,
                                    ownerId: event.target.value,
                                    ownerName: eventLineMemberOptions.find((candidate) => candidate.id === event.target.value)?.fullName || '',
                                  }
                                  : item),
                              } : prev)}
                              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#5B7BFE]"
                            >
                              <option value="">留空则待指定</option>
                              {eventLineMemberOptions.map((item) => (
                                <option key={`template-owner-${item.id}`} value={item.id}>
                                  {item.fullName}
                                </option>
                              ))}
                            </select>
                          </label>
                          <div className="block">
                            <span className="mb-1 block text-[11px] font-medium text-slate-500">协作者</span>
                            <div className="relative">
                              <button
                                type="button"
                                onClick={() => setTaskGroupTemplateCollaboratorMenuStep((current) => current === step.stepIndex ? null : step.stepIndex)}
                                className={`flex w-full items-center justify-between rounded-xl border px-3 py-2 text-sm outline-none transition ${
                                  (step.collaboratorNames || []).length > 0
                                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                    : 'border-slate-200 bg-white text-slate-500 hover:border-emerald-300'
                                }`}
                              >
                                <span className="truncate">
                                  {(step.collaboratorNames || []).length > 0
                                    ? `已选 ${(step.collaboratorNames || []).length} 人`
                                    : '选择协作者'}
                                </span>
                                <ChevronDown size={14} />
                              </button>
                              {taskGroupTemplateCollaboratorMenuStep === step.stepIndex && (
                                <div className="absolute left-0 right-0 top-full z-20 mt-1 max-h-52 overflow-y-auto rounded-xl border border-slate-200 bg-white py-1 shadow-xl">
                                  {eventLineMemberOptions.map((item) => {
                                    const selected = (step.collaboratorIds || []).includes(item.id);
                                    return (
                                      <button
                                        key={`template-collab-${step.stepIndex}-${item.id}`}
                                        type="button"
                                        onClick={() => toggleTaskGroupTemplateApplyCollaborator(step.stepIndex, item)}
                                        className={`flex w-full items-center justify-between px-3 py-2 text-left text-[12px] hover:bg-emerald-50 ${selected ? 'font-bold text-emerald-700' : 'text-slate-700'}`}
                                      >
                                        <span>{item.fullName}</span>
                                        {selected ? <Check size={14} /> : null}
                                      </button>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                            {(step.collaboratorNames || []).length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                {(step.collaboratorNames || []).map((name, index) => (
                                  <button
                                    key={`template-collab-chip-${step.stepIndex}-${(step.collaboratorIds || [])[index] || name}`}
                                    type="button"
                                    onClick={() => removeTaskGroupTemplateApplyCollaborator(step.stepIndex, (step.collaboratorIds || [])[index] || name)}
                                    className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 transition hover:bg-emerald-100"
                                    title={`移除协作者 ${name}`}
                                  >
                                    <span>{name}</span>
                                    <span>×</span>
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                          <label className="block">
                            <span className="mb-1 block text-[11px] font-medium text-slate-500">优先级</span>
                            <select
                              value={step.priority}
                              onChange={(event) => setTaskGroupTemplateApplyDraft((prev) => prev ? {
                                ...prev,
                                stepOverrides: prev.stepOverrides.map((item) => item.stepIndex === step.stepIndex ? { ...item, priority: event.target.value as 'low' | 'normal' | 'high' } : item),
                              } : prev)}
                              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#5B7BFE]"
                            >
                              <option value="low">低</option>
                              <option value="normal">普通</option>
                              <option value="high">高</option>
                            </select>
                          </label>
                          <label className="block">
                            <span className="mb-1 block text-[11px] font-medium text-slate-500">上一步后几天开始</span>
                            <input
                              type="number"
                              min="0"
                              value={step.daysAfterPrevious}
                              onChange={(event) => setTaskGroupTemplateApplyDraft((prev) => prev ? {
                                ...prev,
                                stepOverrides: prev.stepOverrides.map((item) => item.stepIndex === step.stepIndex ? { ...item, daysAfterPrevious: Number(event.target.value) || 0 } : item),
                              } : prev)}
                              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#5B7BFE]"
                            />
                            <span className="mt-1 block text-[10px] text-slate-400">单位：天，默认以上一步结束时间为起点。</span>
                          </label>
                          <label className="block">
                            <span className="mb-1 block text-[11px] font-medium text-slate-500">耗时</span>
                            <input
                              type="number"
                              min="0.5"
                              step="0.5"
                              value={step.durationDays}
                              onChange={(event) => setTaskGroupTemplateApplyDraft((prev) => prev ? {
                                ...prev,
                                stepOverrides: prev.stepOverrides.map((item) => item.stepIndex === step.stepIndex ? { ...item, durationDays: Number(event.target.value) || 0.5 } : item),
                              } : prev)}
                              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#5B7BFE]"
                            />
                            <span className="mt-1 block text-[10px] text-slate-400">1 天按 24 小时算，1.5 天会排成 36 小时。</span>
                          </label>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="flex items-center justify-between gap-3 border-t border-gray-100 bg-white px-6 py-4">
                <p className="text-[12px] leading-5 text-gray-400">负责人暂时留空也可以创建；待后续指定负责人时，再按现有规则触发提醒。</p>
                <div className="flex items-center gap-3">
                  <Button onClick={() => {
                    setTaskGroupTemplateCollaboratorMenuStep(null);
                    setTaskGroupTemplateApplyTarget(null);
                    setTaskGroupTemplateApplyDraft(null);
                  }}>取消</Button>
                  <Button primary onClick={() => void handleApplyTaskGroupTemplateSubmit()} disabled={isApplyingTaskGroupTemplate}>
                    {isApplyingTaskGroupTemplate ? '正在创建…' : '应用模板'}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeEventLine && isEventLineEditorOpen && (
          <EventLineEditorModal
            mode="edit"
            detail={activeEventLine}
            draft={eventLineEditorDraft}
            projectOptions={eventLineEditorProjectOptions}
            memberOptions={eventLineMemberOptions}
            workObjectLabel={terminology.singularLabel}
            canDelete={canManageEventLine(activeEventLine.eventLine)}
            isSaving={isSavingEventLineEditor}
            saveNotice={eventLineEditorSaveNotice}
            onClose={() => {
              setEventLineEditorSaveNotice(null);
              setIsEventLineEditorOpen(false);
              setActiveEventLine(null);
            }}
            onChange={(patch) => {
              setEventLineEditorSaveNotice(null);
              setEventLineEditorDraft((prev) => ({ ...prev, ...patch }));
            }}
            onSubmit={() => void handleSaveEventLineEditor()}
            onCreateProject={handleQuickCreateEventLineProject}
            onDelete={() => void handleDeleteEventLine(activeEventLine.eventLine)}
            onOpenReport={() => {
              setReportEventLineId(activeEventLine.eventLine.id);
              setIsEventLineEditorOpen(false);
            }}
            onOpenTask={(task) => {
              setIsEventLineEditorOpen(false);
              setActiveEventLine(null);
              openTaskEditor(task);
            }}
            onOpenMeeting={handleOpenEventLineMeeting}
            expenseEvidenceLinks={activeEventLine.expenseEvidenceLinks}
            onOpenTaskExpenseEvidence={(task) => {
              const workObjectId = task.workObjectId || task.clientId || activeEventLine.eventLine.primaryClientId || '';
              void openExpenseEvidenceModal({
                workObjectId,
                workObjectName:
                  task.workObjectName ||
                  task.clientName ||
                  activeEventLine.eventLine.primaryClientName ||
                  clients.find((item) => item.id === workObjectId)?.name ||
                  `当前${terminology.singularLabel}`,
                eventLineId: activeEventLine.eventLine.id,
                eventLineName: activeEventLine.eventLine.name,
                taskId: task.id,
                taskTitle: task.title,
              });
            }}
            onBulkUnlinkExpenseEvidence={(items) => handleBulkUnlinkEventLineExpenseEvidence(items)}
            onAddNote={handleAddEventLineNoteFromEditor}
          />
        )}

        {isEventLineCreateOpen && (
          <EventLineEditorModal
            mode="create"
            draft={eventLineEditorDraft}
            projectOptions={eventLineEditorProjectOptions}
            memberOptions={eventLineMemberOptions}
            workObjectLabel={terminology.singularLabel}
            canDelete={false}
            isSaving={isCreatingEventLine}
            onClose={() => {
              setEventLineEditorSaveNotice(null);
              setIsEventLineCreateOpen(false);
            }}
            onChange={(patch) => {
              setEventLineEditorSaveNotice(null);
              setEventLineEditorDraft((prev) => ({ ...prev, ...patch }));
            }}
            onSubmit={() => void handleCreateEventLineFromWorkspace()}
            onCreateProject={handleQuickCreateEventLineProject}
          />
        )}

        {reportEventLineId && (
          <EventLineReportPanel
            eventLineId={reportEventLineId}
            backendBaseUrl={window.yiyuWorkbench?.backendBaseUrl || 'http://127.0.0.1:47829'}
            onClose={() => setReportEventLineId(null)}
            onOpenTaskExpenseEvidence={(task) => {
              const workObjectId = task.workObjectId || task.clientId || activeEventLine?.eventLine.primaryClientId || '';
              void openExpenseEvidenceModal({
                workObjectId,
                workObjectName:
                  task.workObjectName ||
                  task.clientName ||
                  activeEventLine?.eventLine.primaryClientName ||
                  clients.find((item) => item.id === workObjectId)?.name ||
                  `当前${terminology.singularLabel}`,
                eventLineId: reportEventLineId,
                eventLineName:
                  activeEventLine?.eventLine.name ||
                  eventLines.find((detail) => detail.eventLine.id === reportEventLineId)?.eventLine.name ||
                  '当前事件线',
                taskId: task.id,
                taskTitle: task.title,
              });
            }}
            onExportWord={(draft) => {
              void (async () => {
                try {
                  const response = await fetch(`${window.yiyuWorkbench?.backendBaseUrl || 'http://127.0.0.1:47829'}/api/v1/event-lines/${reportEventLineId}/export-word`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(draft),
                  });
                  if (!response.ok) throw new Error(`导出失败 (${response.status})`);
                  const result = await response.json();
                  if (!result.filePath) throw new Error('后端未返回文件路径');
                  const saved = await window.yiyuWorkbench?.saveFileAs(result.filePath, result.fileName);
                  if (saved) {
                    flash('success', `Word 文档已导出到 ${saved}`);
                  }
                } catch (err) {
                  flash('error', err instanceof Error ? err.message : '导出 Word 失败');
                }
              })();
            }}
          />
        )}

        <ExpenseEvidenceModal
          open={isExpenseEvidenceModalOpen && Boolean(expenseEvidenceContext)}
          workObjectLabel={terminology.singularLabel}
          workObjectName={expenseEvidenceContext?.workObjectName || `当前${terminology.singularLabel}`}
          eventLineName={expenseEvidenceContext?.eventLineName || null}
          taskTitle={expenseEvidenceContext?.taskTitle || null}
          integration={orgDingtalkFinanceIntegrationState}
          integrationLoading={false}
          evidenceItems={filteredExpenseEvidenceRecords}
          evidenceLoading={isLoadingExpenseEvidenceRecords}
          existingQuery={expenseEvidenceQuery}
          onExistingQueryChange={setExpenseEvidenceQuery}
          onRefreshEvidence={() => {
            if (!expenseEvidenceContext?.workObjectId) return;
            void loadExpenseEvidenceRecordsForContext(expenseEvidenceContext.workObjectId);
          }}
          importSearchDraft={expenseEvidenceImportSearchDraft}
          onImportSearchDraftChange={(patch) => setExpenseEvidenceImportSearchDraft((prev) => ({ ...prev, ...patch }))}
          importSearchResult={expenseEvidenceImportSearchResult}
          importSearchLoading={isExpenseEvidenceImportSearchLoading}
          selectedImportSourceIds={selectedExpenseEvidenceImportIds}
          onToggleImportSource={(sourceInstanceId) =>
            setSelectedExpenseEvidenceImportIds((prev) =>
              prev.includes(sourceInstanceId)
                ? prev.filter((item) => item !== sourceInstanceId)
                : [...prev, sourceInstanceId],
            )
          }
          onRunImportSearch={() => void handleRunExpenseEvidenceImportSearch()}
          onImportSelected={() => void handleImportSelectedExpenseEvidence()}
          onFetchAttachments={(evidenceId) => void handleFetchExpenseEvidenceAttachments(evidenceId)}
          linkedEvidenceIds={linkedExpenseEvidenceIds}
          onLinkEvidence={
            expenseEvidenceContext?.taskId
              ? (evidenceId) => void handleLinkExpenseEvidenceToTask(evidenceId)
              : expenseEvidenceContext?.eventLineId
                ? (evidenceId) => void handleLinkExpenseEvidenceToEventLine(evidenceId)
                : undefined
          }
          onUnlinkEvidence={
            expenseEvidenceContext?.taskId
              ? (evidenceId) => void handleUnlinkExpenseEvidenceFromTask(evidenceId)
              : expenseEvidenceContext?.eventLineId
                ? (evidenceId) => void handleUnlinkExpenseEvidenceFromEventLine(evidenceId)
                : undefined
          }
          onClose={closeExpenseEvidenceModal}
        />

        {activeSupportRequest && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4 backdrop-blur-md animate-in fade-in"
          >
            <div
              className="w-full max-w-[520px] rounded-[28px] border border-gray-100 bg-white p-6 shadow-[0_20px_60px_rgba(0,0,0,0.15)]"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-start gap-4">
                <button
                  type="button"
                  className="mt-1 rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700"
                  onClick={() => setActiveSupportRequest(null)}
                  aria-label="关闭支持请求"
                >
                  <X size={16} />
                </button>
                <div className="flex-1">
                  <p className="text-[12px] font-bold tracking-[0.12em] text-[#5B7BFE]">SUPPORT REQUEST</p>
                  <h3 className="mt-2 text-[20px] font-bold text-gray-900">支持请求</h3>
                  <p className="mt-2 text-[13px] leading-6 text-gray-500">{activeSupportRequest.summary}</p>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap gap-2 text-[12px] font-bold">
                <span className="rounded-full bg-slate-100 px-3 py-1.5 text-slate-600">#{activeSupportRequest.id}</span>
                <span className="rounded-full bg-amber-50 px-3 py-1.5 text-amber-700">{activeSupportRequest.requestType}</span>
                <span className="rounded-full bg-blue-50 px-3 py-1.5 text-[#33449a]">{activeSupportRequest.targetScope}</span>
                <span className="rounded-full bg-rose-50 px-3 py-1.5 text-rose-700">{activeSupportRequest.urgency}</span>
                <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-emerald-700">{activeSupportRequest.status}</span>
              </div>

              <div className="mt-5 rounded-3xl border border-gray-200 bg-gray-50/70 p-4">
                <p className="text-[12px] font-bold text-gray-500">处理说明</p>
                <textarea
                  value={supportRequestResolutionNote}
                  onChange={(event) => setSupportRequestResolutionNote(event.target.value)}
                  placeholder="补充当前支持请求的处理动作、解决方式或暂不处理原因。"
                  className="mt-3 min-h-[120px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] text-gray-700 outline-none focus:border-[#5B7BFE]"
                />
              </div>

              <div className="mt-5 flex flex-wrap justify-end gap-2">
                <Button
                  onClick={() => void handleResolveSupportRequest('accepted')}
                  disabled={supportRequestActionBusy || activeSupportRequest.status === 'accepted'}
                >
                  标记接受
                </Button>
                <Button
                  onClick={() => void handleResolveSupportRequest('dismissed')}
                  disabled={supportRequestActionBusy || activeSupportRequest.status === 'dismissed'}
                >
                  驳回
                </Button>
                <Button
                  primary
                  onClick={() => void handleResolveSupportRequest('resolved')}
                  disabled={supportRequestActionBusy || activeSupportRequest.status === 'resolved'}
                >
                  {supportRequestActionBusy ? '处理中...' : '标记解决'}
                </Button>
              </div>
            </div>
          </div>
        )}

        {isTaskInteractionBlocked && !isTaskModalOpen && (
          <div className="fixed inset-0 z-[79] bg-transparent" aria-hidden="true" />
        )}

        {isTaskModalOpen && (
          <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/34 px-4 py-6 backdrop-blur-sm">
            <div
              className="relative z-[81] flex h-[700px] w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-2xl"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-center justify-between border-b border-gray-100 bg-gray-50/60 px-6 py-4">
                <div className="flex min-w-0 items-center gap-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded bg-blue-100 text-blue-600">
                    <CheckSquare size={14} />
                  </div>
                  <h2 className="text-lg font-semibold text-gray-800">{editingTask.id ? '编辑任务' : '新建任务'}</h2>
                  <span className="ml-2 text-sm text-gray-400">专注核心事务，结构化沉淀</span>
                </div>
                <div className="flex items-center gap-2">
                  {editingTask.id && (
                    <button
                      type="button"
                      className="inline-flex items-center gap-2 rounded-full border border-rose-200 bg-rose-50 px-3 py-1.5 text-[12px] font-semibold text-rose-600 transition hover:bg-rose-100"
                      onClick={() =>
                        requestDeleteTaskRecord(
                          {
                            id: editingTask.id,
                            title: editingTask.title.trim() || '未命名任务',
                            clientId: editingTask.clientId || null,
                            eventLineId: editingTask.eventLineId || null,
                          },
                          { closeEditor: true },
                        )
                      }
                    >
                      <Trash2 size={13} />
                      删除任务
                    </button>
                  )}
                  <button
                    type="button"
                    className="rounded-full p-2 text-gray-500 transition hover:bg-gray-200"
                    onClick={() => closeTaskModal('header-close')}
                    aria-label="关闭任务弹窗"
                  >
                    <X size={18} />
                  </button>
                </div>
              </div>

              <div className="flex min-h-0 flex-1 overflow-hidden">
                <div className="flex min-h-0 flex-1 flex-col overflow-y-auto p-8">
                  <input
                    value={editingTask.title}
                    onChange={(event) =>
                      setEditingTask((prev) => {
                        const nextTitle = event.target.value;
                        const next = { ...prev, title: nextTitle };
                        const inferred = applyClientInferenceToDraft(nextTitle, prev.desc, prev);
                        if (inferred) {
                          return {
                            ...next,
                            ...inferred,
                          };
                        }
                        return next;
                      })
                    }
                    placeholder="任务标题..."
                    className="mb-6 w-full border-none text-3xl font-bold text-gray-900 outline-none placeholder:text-gray-300"
                  />

                  <textarea
                    value={editingTask.desc}
                    onChange={(event) =>
                      setEditingTask((prev) => {
                        const nextDesc = event.target.value;
                        const next = { ...prev, desc: nextDesc };
                        const inferred = applyClientInferenceToDraft(prev.title, nextDesc, prev);
                        if (inferred) {
                          return {
                            ...next,
                            ...inferred,
                          };
                        }
                        return next;
                      })
                    }
                    placeholder="添加任务描述，背景、目的、预期结果..."
                    className="min-h-[220px] w-full flex-1 resize-none border-none text-[15px] leading-relaxed text-gray-600 outline-none placeholder:text-gray-400"
                  />

                  {/* 智能摘要面板 */}
                  <div className="mt-5 rounded-2xl border border-blue-100 bg-blue-50/20 p-4">
                    <div className="mb-3 flex items-center gap-2">
                      <div className="flex h-5 w-5 items-center justify-center rounded bg-blue-100">
                        <BrainCircuit size={12} className="text-blue-600" />
                      </div>
                      <span className="text-[12px] font-bold text-blue-700">智能摘要</span>
                      {isLoadingUnderstanding && editingTask.id && (
                        <span className="animate-pulse text-[11px] text-slate-400">正在整理...</span>
                      )}
                    </div>
                    {!editingTask.id ? (
                      <div className="rounded-2xl border border-blue-100 bg-white/80 px-4 py-3">
                        <p className="text-[13px] leading-6 text-slate-500">
                          保存任务后会自动生成智能摘要，并在你补充项目、事件线或材料后一起刷新。
                        </p>
                      </div>
                    ) : taskUnderstanding ? (
                      <UnderstandingPanel snapshot={taskUnderstanding} />
                    ) : isLoadingUnderstanding ? (
                      <div className="space-y-2">
                        <div className="h-4 w-3/4 animate-pulse rounded bg-blue-100/50" />
                        <div className="h-4 w-1/2 animate-pulse rounded bg-blue-100/50" />
                        <div className="h-4 w-2/3 animate-pulse rounded bg-blue-100/50" />
                      </div>
                    ) : (
                      <p className="text-[12px] text-slate-400">暂时还没整理出摘要，请稍后再看。</p>
                    )}
                  </div>

                  <div className="mt-6 space-y-3">
                    <div className="rounded-lg border-2 border-dashed border-gray-200 bg-white p-4 transition focus-within:border-blue-400 focus-within:bg-blue-50/40">
                      <div className="mb-3 flex items-center gap-2 text-gray-500">
                        <PenTool size={18} className="text-gray-400" />
                        <p className="text-sm font-medium">往里面贴文字</p>
                      </div>
                      <textarea
                        value={pendingTaskArchiveText}
                        onChange={(event) => setPendingTaskArchiveText(event.target.value)}
                        disabled={isSavingTask}
                        placeholder={`把纪要、背景说明、补充材料直接贴在这里，保存任务时会先归档到当前电脑的${terminology.workspaceLabel}`}
                        className={`min-h-[120px] w-full resize-none border-none bg-transparent text-[14px] leading-relaxed outline-none placeholder:text-gray-400 ${
                          isSavingTask ? 'cursor-not-allowed text-gray-300' : 'text-gray-600'
                        }`}
                      />
                      {/* 附件名称列表（显示在文本框内部） */}
                      {(editingTaskRecord?.attachments?.length || pendingTaskAttachmentItems.length > 0) ? (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {(editingTaskRecord?.attachments || []).map((attachment: TaskAttachmentRecord) => (
                            <span
                              key={attachment.id}
                              className="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-[11px] text-gray-600"
                            >
                              <Paperclip size={10} className="text-gray-400" />
                              <span className="truncate max-w-[180px]">{attachment.title}</span>
                            </span>
                          ))}
                          {pendingTaskAttachmentItems.map((file) => (
                            <span
                              key={`${file.name}-${file.size}-${file.lastModified}`}
                              className="inline-flex items-center gap-1 rounded-lg border border-blue-200 bg-blue-50 px-2 py-1 text-[11px] text-blue-700"
                            >
                              <Paperclip size={10} className="text-blue-400" />
                              <span className="truncate max-w-[180px]">{file.name}</span>
                              <span className="rounded-full bg-white/80 px-1.5 py-0.5 text-[10px] font-medium text-blue-500">待上传</span>
                              <button
                                type="button"
                                className="text-blue-300 transition hover:text-blue-600"
                                onClick={() => removePendingTaskAttachment(file)}
                                aria-label={`移除待上传附件${file.name}`}
                              >
                                <X size={11} />
                              </button>
                            </span>
                          ))}
                        </div>
                      ) : null}
                      <div className="mt-2 flex items-center justify-between">
                        <p className="text-xs text-gray-400">
                          保存后文字和附件会先进入当前电脑的{terminology.workspaceLabel}；共享工作台同步取决于后续云同步。
                        </p>
                        {taskAttachmentUploadProgress ? (
                          <div className="shrink-0 flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-1.5">
                            <div className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-blue-200 border-t-[#5B7BFE]" />
                            <div className="flex flex-col">
                              <span className="text-[11px] font-medium text-[#5B7BFE]">
                                上传中 {taskAttachmentUploadProgress.percent}%
                              </span>
                              <span className="text-[10px] text-blue-400 truncate max-w-[120px]">
                                {taskAttachmentUploadProgress.currentFileName}
                              </span>
                            </div>
                          </div>
                        ) : (
                          <label className="shrink-0 inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px] font-medium text-gray-400 cursor-pointer transition hover:text-[#5B7BFE] hover:bg-blue-50">
                            <UploadCloud size={13} />
                            上传附件
                            <input
                              type="file"
                              multiple
                              className="hidden"
                              onChange={(event) => {
                                const files = event.target.files;
                                if (!files || files.length === 0) return;
                                const fileList = Array.from(files);
                                if (!editingTask.id) {
                                  setPendingTaskAttachmentFiles((prev) => {
                                    const seen = new Set(prev.map((file) => `${file.name}::${file.size}::${file.lastModified}`));
                                    const next = [...prev];
                                    fileList.forEach((file) => {
                                      const key = `${file.name}::${file.size}::${file.lastModified}`;
                                      if (seen.has(key)) return;
                                      seen.add(key);
                                      next.push(file);
                                    });
                                    return next;
                                  });
                                  flash('success', `已暂存 ${fileList.length} 个附件，保存任务后会一起上传`);
                                  event.target.value = '';
                                  return;
                                }
                                void uploadAttachmentsToTask(
                                  editingTask.id,
                                  fileList,
                                  { clientId: editingTask.clientId, eventLineId: editingTask.eventLineId, taskTitle: editingTask.title },
                                ).then(() => {
                                  setTasks((prev: Task[]) => prev.map((t: Task) => {
                                    if (t.id !== editingTask.id) return t;
                                    const newAtts = fileList.map((f, i) => ({
                                      id: `pending_${Date.now()}_${i}`,
                                      title: f.name,
                                      kind: f.name.split('.').pop() || 'bin',
                                      path: '',
                                      source: 'task_attachment',
                                      sizeBytes: f.size,
                                      createdAt: new Date().toISOString(),
                                    }));
                                    return { ...t, attachments: [...(t.attachments || []), ...newAtts] } as Task;
                                  }));
                                  flash('success', `已上传 ${fileList.length} 个附件`);
                                  void loadTaskBlock();
                                }).catch((err: Error) => {
                                  flash('error', err.message || '附件上传失败');
                                });
                                event.target.value = '';
                              }}
                            />
                          </label>
                        )}
                      </div>
                    </div>
                    {pendingTaskArchiveText.trim() && (
                      <div className="flex items-center justify-between gap-3 rounded-2xl border border-[#DDE6FF] bg-[#F7F9FF] px-4 py-3 text-[12px] text-slate-600">
                        <div className="min-w-0">
                          <p className="font-bold text-slate-700">
                            {inferTaskArchiveDocumentTitle({
                              taskTitle: editingTask.title,
                              clientName: clients.find((item: ClientSummary) => item.id === editingTask.clientId)?.name || null,
                              eventLineName: selectedEventLineSummary?.name || null,
                              content: pendingTaskArchiveText,
                            })}
                          </p>
                          <p className="mt-1 text-[11px] text-slate-400">
                            已暂存 {pendingTaskArchiveText.trim().length} 个字，保存任务后会先归档到当前电脑
                          </p>
                        </div>
                        <button
                          type="button"
                          className="shrink-0 text-slate-400 hover:text-slate-700"
                          onClick={() => setPendingTaskArchiveText('')}
                        >
                          <X size={14} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                <div className="w-[340px] min-h-0 flex-shrink-0 overflow-y-auto border-l border-gray-100 bg-gray-50/30">
                  <div className="space-y-4 border-b border-gray-100 p-5">
                    <TaskPropertyRow icon={<User size={16} />} label="负责人">
                      <div ref={ownerDropdownRef} className="relative w-full">
                        <button
                          type="button"
                          onClick={() => setIsOwnerMenuOpen((prev) => !prev)}
                          className="flex min-h-[40px] w-full items-center justify-between rounded-lg border border-gray-200 bg-white px-3 py-2 text-left transition hover:border-[#5B7BFE]"
                        >
                          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                            {ownerCollaborator ? (
                              <span className="inline-flex max-w-full items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-sm text-gray-700">
                                <span className="truncate">{ownerCollaborator.fullName}</span>
                                <span
                                  role="button"
                                  tabIndex={0}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    removeTaskOwner();
                                  }}
                                  onKeyDown={(event) => {
                                    if (event.key === 'Enter' || event.key === ' ') {
                                      event.preventDefault();
                                      event.stopPropagation();
                                      removeTaskOwner();
                                    }
                                  }}
                                  className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full text-gray-400 hover:bg-slate-200 hover:text-gray-600"
                                  aria-label={`移除负责人${ownerCollaborator.fullName}`}
                                >
                                  <X size={12} />
                                </span>
                              </span>
                            ) : (
                              <span className="text-sm text-gray-400">点击选择负责人</span>
                            )}
                          </div>
                          <ChevronDown
                            size={16}
                            className={`ml-2 flex-shrink-0 text-gray-400 transition-transform ${isOwnerMenuOpen ? 'rotate-180' : ''}`}
                          />
                        </button>
                        {isOwnerMenuOpen && (
                          <div className="absolute left-0 right-0 top-[calc(100%+8px)] z-20 rounded-lg border border-gray-200 bg-white p-2 shadow-lg">
                            <div className="flex items-center gap-2 rounded-md border border-gray-200 px-3 py-2">
                              <Search size={14} className="text-gray-400" />
                              <input
                                value={ownerQuery}
                                onChange={(event) => setOwnerQuery(event.target.value)}
                                placeholder="搜索成员"
                                className="w-full border-0 bg-transparent text-sm outline-none"
                              />
                            </div>
                            <div className="mt-2 max-h-56 overflow-y-auto">
                              {ownerOptions.length === 0 && (
                                <div className="px-3 py-2 text-xs text-gray-400">暂无匹配人员</div>
                              )}
                              {ownerOptions.map((candidate) => (
                                <button
                                  key={candidate.id}
                                  type="button"
                                  className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-xs text-gray-700 hover:bg-gray-50"
                                  onClick={() => {
                                    setEditingTask((prev) => {
                                      const nextCollaborators = prev.collaborators.some((item) => item.id === candidate.id)
                                        ? prev.collaborators
                                        : [candidate, ...prev.collaborators];
                                      return {
                                        ...prev,
                                        ownerId: candidate.id,
                                        collaborators: nextCollaborators,
                                      };
                                    });
                                    setOwnerQuery('');
                                    setIsOwnerMenuOpen(false);
                                  }}
                                >
                                  <span>{candidate.fullName}{candidate.isSelf ? '（自己）' : ''}</span>
                                  <div
                                    className={`ml-3 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded border text-[12px] font-bold transition ${
                                      editingTask.ownerId === candidate.id
                                        ? 'border-[#5B7BFE] bg-[#5B7BFE] text-white'
                                        : 'border-gray-300 bg-white text-transparent'
                                    }`}
                                  >
                                    ✓
                                  </div>
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </TaskPropertyRow>

                    <TaskPropertyRow icon={<Users size={16} />} label="协作者">
                      <div ref={collaboratorDropdownRef} className="relative w-full">
                        <button
                          type="button"
                          onClick={() => setIsMentionMenuOpen((prev) => !prev)}
                          className="flex min-h-[40px] w-full items-center justify-between rounded-lg border border-gray-200 bg-white px-3 py-2 text-left transition hover:border-[#5B7BFE]"
                        >
                          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                            {selectedTaskCollaborators.length > 0 ? (
                              selectedTaskCollaborators.map((candidate) => (
                                <span
                                  key={candidate.id}
                                  className="inline-flex max-w-full items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-sm text-gray-700"
                                >
                                  <span className="truncate">{candidate.fullName}</span>
                                  <span
                                    role="button"
                                    tabIndex={0}
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      toggleTaskCollaborator(candidate);
                                    }}
                                    onKeyDown={(event) => {
                                      if (event.key === 'Enter' || event.key === ' ') {
                                        event.preventDefault();
                                        event.stopPropagation();
                                        toggleTaskCollaborator(candidate);
                                      }
                                    }}
                                    className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full text-gray-400 hover:bg-slate-200 hover:text-gray-600"
                                    aria-label={`移除协作者${candidate.fullName}`}
                                  >
                                    <X size={12} />
                                  </span>
                                </span>
                              ))
                            ) : (
                              <span className="text-sm text-gray-400">点击选择协作者</span>
                            )}
                          </div>
                          <ChevronDown
                            size={16}
                            className={`ml-2 flex-shrink-0 text-gray-400 transition-transform ${isMentionMenuOpen ? 'rotate-180' : ''}`}
                          />
                        </button>
                        {isMentionMenuOpen && (
                          <div className="absolute left-0 right-0 top-[calc(100%+8px)] z-20 rounded-lg border border-gray-200 bg-white p-2 shadow-lg">
                            <div className="flex items-center gap-2 rounded-md border border-gray-200 px-3 py-2">
                              <Search size={14} className="text-gray-400" />
                              <input
                                value={mentionQuery}
                                onChange={(event) => setMentionQuery(event.target.value)}
                                placeholder="搜索成员"
                                className="w-full border-0 bg-transparent text-sm outline-none"
                              />
                            </div>
                            <div className="mt-2 max-h-56 overflow-y-auto">
                              {availableMentionOptions.length === 0 && (
                                <div className="px-3 py-2 text-xs text-gray-400">暂无匹配人员</div>
                              )}
                              {availableMentionOptions.map((candidate) => {
                                const isSelected = selectedTaskCollaboratorIds.has(candidate.id);
                                return (
                                  <button
                                    key={candidate.id}
                                    type="button"
                                    className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-xs text-gray-700 hover:bg-gray-50"
                                    onClick={() => toggleTaskCollaborator(candidate)}
                                  >
                                    <span className="truncate text-sm text-gray-700">
                                      {candidate.fullName}
                                      {candidate.isSelf ? '（自己）' : ''}
                                    </span>
                                    <div
                                      className={`ml-3 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded border text-[12px] font-bold transition ${
                                        isSelected
                                          ? 'border-[#5B7BFE] bg-[#5B7BFE] text-white'
                                          : 'border-gray-300 bg-white text-transparent'
                                      }`}
                                    >
                                      ✓
                                    </div>
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    </TaskPropertyRow>

                    <TaskPropertyRow icon={<CalendarIcon size={16} />} label="截止时间">
                      <button
                        type="button"
                        onClick={() => setIsDuePickerOpen((prev) => !prev)}
                        className="rounded px-2 py-1 text-sm font-medium text-gray-700 hover:bg-gray-100"
                      >
                        {duePickerSummaryLabel}
                      </button>
                    </TaskPropertyRow>

                    <TaskPropertyRow icon={<Flag size={16} className={editingTaskPriorityMeta.selectClass} />} label="优先级">
                      <select
                        value={editingTask.priority}
                        onChange={(event) =>
                          setEditingTask((prev) => ({
                            ...prev,
                            priority: event.target.value as 'low' | 'normal' | 'high',
                            priorityTouched: true,
                            priorityReason: '已手动调整优先级，可继续修改。',
                          }))
                        }
                        className={`w-full rounded border border-transparent bg-transparent px-2 py-1 text-sm font-medium hover:bg-gray-100 ${editingTaskPriorityMeta.selectClass}`}
                      >
                        <option value="low">低优先级</option>
                        <option value="normal">普通优先级</option>
                        <option value="high">高优先级</option>
                      </select>
                    </TaskPropertyRow>

                    <TaskPropertyRow icon={<Layout size={16} />} label="任务清单">
                      <div ref={taskListDropdownRef} className="relative w-full">
                        <div className="rounded-2xl border border-gray-200 bg-white px-3 py-2 transition focus-within:border-[#5B7BFE] focus-within:ring-2 focus-within:ring-[#5B7BFE]/10">
                          {selectedTaskLists.length > 0 && (
                            <div className="mb-2 flex flex-wrap gap-2">
                              {selectedTaskLists.map((list) => (
                                <span
                                  key={`selected-task-list-${list.id}`}
                                  className="inline-flex items-center gap-1 rounded-full border border-[#D7E0FF] bg-[#F8FAFF] px-2.5 py-1 text-[11px] font-bold text-[#5B7BFE]"
                                >
                                  {list.name}
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setEditingTask((prev) => {
                                        const nextListIds = (prev.listIds || []).filter((item) => item !== list.id);
                                        return {
                                          ...prev,
                                          listId: nextListIds[0] || '',
                                          listIds: nextListIds,
                                        };
                                      });
                                    }}
                                    className="flex h-4 w-4 items-center justify-center rounded-full text-[#5B7BFE]/70 transition hover:bg-[#E8EEFF] hover:text-[#5B7BFE]"
                                    aria-label={`移除清单 ${list.name}`}
                                  >
                                    <X size={11} />
                                  </button>
                                </span>
                              ))}
                            </div>
                          )}
                          <div className="flex items-center gap-2">
                            <Search size={14} className="shrink-0 text-gray-400" />
                            <input
                              value={taskListQuery}
                              onChange={(event) => handleTaskListQueryChange(event.target.value)}
                              onFocus={() => setIsTaskListMenuOpen(true)}
                              onKeyDown={(event) => {
                                if (event.key === 'Enter') {
                                  event.preventDefault();
                                  if (filteredTaskListOptions[0]) {
                                    handleSelectTaskList(filteredTaskListOptions[0]);
                                  } else if (taskListQuery.trim() && !hasExactTaskListMatch) {
                                    void handleCreateTaskListFromQuery();
                                  }
                                }
                              }}
                              placeholder={isTaskListsLoading ? '正在加载清单…' : visibleOrgTaskLists.length > 0 ? '输入清单名称搜索或直接创建' : '输入清单名称后直接创建'}
                              className="w-full border-0 bg-transparent text-[14px] font-medium text-gray-800 outline-none"
                            />
                            <ChevronDown size={16} className={`shrink-0 text-gray-400 transition-transform ${isTaskListMenuOpen ? 'rotate-180' : ''}`} />
                          </div>
                        </div>
                        {isTaskListMenuOpen && (
                          <div className="absolute left-0 right-0 top-[calc(100%+8px)] z-20 rounded-2xl border border-gray-200 bg-white p-2 shadow-lg">
                            <div className="max-h-56 overflow-y-auto">
                              {filteredTaskListOptions.map((list) => (
                                <button
                                  key={list.id}
                                  type="button"
                                  className="flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm text-gray-700 transition hover:bg-gray-50"
                                  onClick={() => handleSelectTaskList(list)}
                                >
                                  <span className="truncate">{list.name}</span>
                                  <div
                                    className={`ml-3 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded border text-[12px] font-bold transition ${
                                      selectedTaskListIds.includes(list.id)
                                        ? 'border-[#5B7BFE] bg-[#5B7BFE] text-white'
                                        : 'border-gray-300 bg-white text-transparent'
                                    }`}
                                  >
                                    ✓
                                  </div>
                                </button>
                              ))}
                              {filteredTaskListOptions.length === 0 && (
                                <div className="px-3 py-2 text-xs text-gray-400">
                                  {isTaskListsLoading ? '正在加载清单…' : '没有找到匹配清单'}
                                </div>
                              )}
                            </div>
                            {taskListQuery.trim() && !hasExactTaskListMatch && (
                              <button
                                type="button"
                                onClick={() => void handleCreateTaskListFromQuery()}
                                disabled={isCreatingTaskList}
                                className="mt-2 inline-flex items-center gap-1 rounded-full border border-[#D7E0FF] bg-[#F8FAFF] px-3 py-1 text-[11px] font-bold text-[#5B7BFE] transition hover:bg-[#EEF2FF] disabled:cursor-wait disabled:opacity-60"
                              >
                                <Layout size={12} />
                                {isCreatingTaskList ? '正在创建…' : `创建清单“${taskListQuery.trim()}”`}
                              </button>
                            )}
                          </div>
                        )}
                        <p className="mt-2 text-[12px] text-gray-400">
                          这里支持多选。输入清单名称可直接搜索；如果没有匹配项，可以直接创建清单。
                        </p>
                      </div>
                    </TaskPropertyRow>
                  </div>

                  <div className="border-b border-gray-100 p-5">
                    <div className="space-y-3">
                      {isCloudSession && (
                        <TaskPropertyRow icon={<GitCommit size={16} />} label="关联事件线">
                          <select
                            value={editingTask.eventLineId}
                            onChange={(event) => handleTaskEventLineChange(event.target.value)}
                            disabled={isEditingTaskPersonal}
                            className="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-700 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400"
                          >
                            <option value="">可选：加入事件线</option>
                            {taskEventLineOptions.map((line) => (
                              <option key={line.id} value={line.id}>
                                {formatTaskEventLineOptionLabel(line)}
                              </option>
                            ))}
                          </select>
                        </TaskPropertyRow>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="relative z-[96] flex shrink-0 items-center justify-between border-t border-gray-200 bg-white px-6 py-4">
                <div className="min-w-0">
                  <div className="text-sm text-gray-500">
                    <span className="mr-2 inline-block h-2 w-2 rounded-full bg-green-500" />
                    {taskAttachmentUploadProgress ? `正在上传附件 ${taskAttachmentUploadProgress.percent}%` : '草稿已自动保存'}
                  </div>
                  {taskAttachmentUploadProgress && (
                    <div className="mt-2 w-[280px] max-w-full">
                      <div className="mb-1 flex items-center justify-between gap-3 text-[12px] text-gray-400">
                        <span className="truncate">{taskAttachmentUploadProgress.currentFileName}</span>
                        <span>
                          {Math.min(taskAttachmentUploadProgress.uploadedFiles + 1, taskAttachmentUploadProgress.totalFiles)}/
                          {taskAttachmentUploadProgress.totalFiles}
                        </span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-blue-500 transition-[width] duration-200"
                          style={{ width: `${taskAttachmentUploadProgress.percent}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
                <div className="flex gap-3">
                  <button
                    type="button"
                    className="rounded-lg px-5 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50"
                    onClick={() => closeTaskModal('footer-cancel')}
                    disabled={isSavingTask || isTaskAttachmentBusy}
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    className={`rounded-lg px-6 py-2 text-sm font-medium text-white shadow-sm shadow-blue-200 disabled:cursor-wait disabled:opacity-80 ${
                      isSavingTask || isTaskAttachmentBusy ? 'bg-blue-400' : 'bg-blue-600 hover:bg-blue-700'
                    }`}
                    onClick={() => {
                      void handleSaveTask();
                    }}
                    disabled={isSavingTask || isTaskAttachmentBusy}
                  >
                    {isTaskAttachmentBusy && taskAttachmentUploadProgress
                      ? `上传中 ${taskAttachmentUploadProgress.percent}%`
                      : isSavingTask
                        ? '正在保存…'
                        : editingTask.id
                          ? '保存修改'
                          : '保存任务'}
                  </button>
                </div>
              </div>
              {isDuePickerOpen && (
                <div
                  className="fixed inset-0 z-[140] flex items-center justify-center bg-black/10 px-6 py-10"
                  onClick={() => setIsDuePickerOpen(false)}
                >
                  <div
                    className="w-[318px] max-w-full overflow-hidden rounded-[24px] border border-[#E7EAF3] bg-white shadow-[0_28px_70px_rgba(15,23,42,0.18)]"
                    onClick={(event) => event.stopPropagation()}
                  >
                    <div className="p-4">
                      <div className="mb-4 flex items-center justify-between">
                        <button
                          type="button"
                          onClick={() => setDuePickerMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1))}
                          className="flex h-8 w-8 items-center justify-center rounded-full text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
                        >
                          <ChevronDown size={15} className="rotate-90" />
                        </button>
                        <span className="text-[15px] font-bold text-gray-900">{formatMonthTitle(duePickerMonth)}</span>
                        <button
                          type="button"
                          onClick={() => setDuePickerMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1))}
                          className="flex h-8 w-8 items-center justify-center rounded-full text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
                        >
                          <ChevronDown size={15} className="-rotate-90" />
                        </button>
                      </div>

                      <div className="grid grid-cols-7 gap-y-2 text-center text-[11px] font-bold text-gray-400">
                        {['一', '二', '三', '四', '五', '六', '日'].map((label) => (
                          <span key={label}>{label}</span>
                        ))}
                      </div>
                      <div className="mt-2 grid grid-cols-7 gap-y-1">
                        {duePickerCalendarCells.map((cell, index) => {
                          if (!cell.date || !cell.day) {
                            return <span key={`empty-${index}`} className="h-9" />;
                          }
                          const cellDateValue = formatDateOnlyValue(cell.date);
                          const isSelected = editingTask.dueDate === cellDateValue;
                          const isToday = cell.date.toDateString() === new Date().toDateString();
                          return (
                            <button
                              key={cellDateValue}
                              type="button"
                              onClick={() => applyEditingTaskDueDate(cellDateValue)}
                              className={`mx-auto flex h-9 w-9 items-center justify-center rounded-xl text-[13px] font-bold transition-colors ${
                                isSelected
                                  ? 'bg-[#3F74FF] text-white shadow-[0_10px_20px_rgba(63,116,255,0.22)]'
                                  : isToday
                                    ? 'text-[#E5477A] hover:bg-rose-50'
                                    : 'text-gray-700 hover:bg-gray-100'
                              }`}
                            >
                              {cell.day}
                            </button>
                          );
                        })}
                      </div>

                      <div className="mt-4 space-y-3">
                        <label className="block">
                          <span className="mb-1 block text-[12px] font-medium text-gray-500">开始日期（选填）</span>
                          <input
                            type="date"
                            value={editingTask.startDate}
                            onChange={(event) => applyEditingTaskStartDate(event.target.value)}
                            className="w-full rounded-2xl border border-gray-200 px-3 py-2 text-[14px] text-gray-700 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/10"
                          />
                        </label>
                        <label className="block">
                          <span className="mb-1 block text-[12px] font-medium text-gray-500">截止日期</span>
                          <input
                            type="date"
                            value={editingTask.dueDate}
                            onChange={(event) => applyEditingTaskDueDate(event.target.value)}
                            className="w-full rounded-2xl border border-gray-200 px-3 py-2 text-[14px] text-gray-700 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/10"
                          />
                        </label>

                        <label className="flex items-center gap-2 text-[13px] font-medium text-gray-700">
                          <input
                            type="checkbox"
                            checked={editingTask.hasSpecificDueTime}
                            onChange={(event) => setEditingTaskSpecificDueTime(event.target.checked)}
                          />
                          具体时间
                        </label>

                        {editingTask.hasSpecificDueTime && (
                          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                            <label className="block">
                              <span className="mb-1 block text-[12px] font-medium text-gray-500">开始时间（选填）</span>
                              <input
                                type="text"
                                inputMode="numeric"
                                value={editingTask.startTime}
                                onChange={(event) => setEditingTask((prev) => ({ ...prev, startTime: event.target.value }))}
                                onBlur={(event) => applyEditingTaskStartTime(event.target.value)}
                                placeholder="09:00"
                                disabled={!editingTask.startDate}
                                className="w-full rounded-2xl border border-gray-200 px-3 py-2 text-[14px] text-gray-700 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/10 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400"
                              />
                            </label>
                            <label className="block">
                              <span className="mb-1 block text-[12px] font-medium text-gray-500">截止时间</span>
                              <input
                                type="text"
                                inputMode="numeric"
                                value={editingTask.dueTime || TASK_DEFAULT_DUE_TIME}
                                onChange={(event) => setEditingTask((prev) => ({ ...prev, dueTime: event.target.value }))}
                                onBlur={(event) => applyEditingTaskDueTime(event.target.value)}
                                placeholder="09:00"
                                disabled={!editingTask.dueDate}
                                className="w-full rounded-2xl border border-gray-200 px-3 py-2 text-[14px] text-gray-700 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/10 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400"
                              />
                            </label>
                          </div>
                        )}

                        <div className="rounded-[18px] border border-slate-200 bg-slate-50 px-3 py-2 text-[12px] leading-5 text-slate-500">
                          只选择截止日期时，任务会按默认截止时间 09:00 排序；勾选“具体时间”后，可分别填写开始时间和截止时间。
                        </div>
                      </div>

                      <div className="mt-4 flex items-center justify-between">
                        <button
                          type="button"
                          className="text-[13px] font-bold text-gray-400 transition-colors hover:text-gray-700"
                          onClick={() => {
                            clearEditingTaskSchedule();
                            setIsDuePickerOpen(false);
                          }}
                        >
                          清除
                        </button>
                        <div className="flex items-center gap-3">
                          <button
                            type="button"
                            className="text-[13px] font-bold text-[#5B7BFE] transition-colors hover:text-[#3F74FF]"
                            onClick={() => {
                              const today = new Date();
                              const todayValue = formatDateOnlyValue(today);
                              setDuePickerMonth(new Date(today.getFullYear(), today.getMonth(), 1));
                              applyEditingTaskDueDate(todayValue);
                            }}
                          >
                            今天
                          </button>
                          <button
                            type="button"
                            className="rounded-xl bg-[#5B7BFE] px-4 py-2 text-[13px] font-bold text-white shadow-[0_10px_24px_rgba(91,123,254,0.22)]"
                            onClick={() => setIsDuePickerOpen(false)}
                          >
                            确定
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {pendingTaskDelete && (
          <div className="fixed inset-0 z-[92] flex items-center justify-center bg-black/35 px-4 py-6 backdrop-blur-sm">
            <div
              className="w-full max-w-[420px] overflow-hidden rounded-[24px] border border-rose-100 bg-white shadow-[0_24px_80px_rgba(0,0,0,0.18)]"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="border-b border-rose-100 bg-rose-50/70 px-6 py-5">
                <div className="flex items-center gap-4">
                  <button
                    type="button"
                    className="rounded-2xl border border-rose-200 bg-white p-2 text-rose-400 transition hover:text-rose-700"
                    onClick={() => setPendingTaskDelete(null)}
                    aria-label="关闭删除任务确认"
                  >
                    <X size={16} />
                  </button>
                  <div className="text-[16px] font-bold text-rose-700">确认删除任务</div>
                </div>
                <p className="mt-2 text-[12px] leading-6 text-rose-600">
                  这会永久删除这条任务及其相关活动记录，且无法恢复。
                </p>
              </div>
              <div className="px-6 py-5">
                <p className="text-[13px] leading-6 text-gray-600">
                  即将删除：
                  <span className="mx-1 font-bold text-gray-900">“{pendingTaskDelete.title || '未命名任务'}”</span>
                </p>
              </div>
              <div className="flex items-center justify-end gap-3 border-t border-gray-100 bg-gray-50/50 px-6 py-4">
                <button
                  type="button"
                  onClick={() => setPendingTaskDelete(null)}
                  className="px-4 py-2 text-[13px] font-bold text-gray-500 transition-colors hover:text-gray-800"
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={() => void confirmDeleteTaskRecord()}
                  className="rounded-2xl bg-rose-500 px-5 py-2 text-[13px] font-bold text-white shadow-[0_12px_30px_rgba(244,63,94,0.28)] transition-colors hover:bg-rose-600"
                >
                  确认删除
                </button>
              </div>
            </div>
          </div>
        )}

        {isRejectModalOpen && (
          <div className="fixed inset-0 bg-black/30 backdrop-blur-md z-50 flex items-center justify-center animate-in fade-in">
            <div className="bg-white rounded-[28px] shadow-[0_20px_60px_rgba(0,0,0,0.15)] w-[480px] overflow-hidden transform animate-in zoom-in-95 border border-gray-100" onClick={(event) => event.stopPropagation()}>
              <div className="px-8 py-6 border-b border-gray-100 flex items-center gap-4 bg-white">
                <button
                  type="button"
                  className="rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700"
                  onClick={() => setIsRejectModalOpen(false)}
                  aria-label="关闭退回任务弹窗"
                >
                  <X size={16} />
                </button>
                <h3 className="text-[18px] font-bold text-gray-900">退回任务</h3>
              </div>
              <div className="p-8">
                <textarea value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} placeholder="请填写退回理由..." className="w-full bg-gray-50 border border-gray-200 rounded-2xl p-4 text-[14px] font-medium outline-none min-h-[140px]" />
              </div>
              <div className="px-8 py-5 border-t border-gray-100 bg-gray-50/50 flex justify-end gap-3">
                <button onClick={() => setIsRejectModalOpen(false)} className="text-[13px] font-bold text-gray-500 hover:text-gray-800 px-5 py-2 transition-colors">
                  取消
                </button>
                <Button primary onClick={() => void confirmReject()} className="px-6 shadow-md">
                  确认退回
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }, [
    terminology.effectiveMode,
    terminology.singularLabel,
    terminology.pluralLabel,
    terminology.workspaceLabel,
    terminology.associateLabel,
    terminology.recentLabel,
    terminology.statsLabel,
    terminology.structureLabel,
  ]);

  const ClientWorkspaceView = () => {
    const currentClient = clients.find((client) => client.id === currentClientId) || clients[0];
    const [searchQuery, setSearchQuery] = useState('');
    const [workspaceFileSearchQuery, setWorkspaceFileSearchQuery] = useState('');
    const [workspaceFileSearchSubmittedQuery, setWorkspaceFileSearchSubmittedQuery] = useState('');
    const [workspaceFileSearchResult, setWorkspaceFileSearchResult] = useState<KnowledgeSearchResult | null>(null);
    const [isWorkspaceFileSearching, setIsWorkspaceFileSearching] = useState(false);
    const [inputValue, setInputValue] = useState('');
    const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
    const [clientImportDropZone, setClientImportDropZone] = useState<'buffer' | 'composer' | null>(null);
    const [answerActionState, setAnswerActionState] = useState<Record<string, 'vectorize' | 'export'>>({});
    const [isTemplateFilling, setIsTemplateFilling] = useState(false);
    const [templateFillDialog, setTemplateFillDialog] = useState<TemplateFillDialogState | null>(null);
    const [isClientModalOpen, setIsClientModalOpen] = useState(false);
    const [editingClientId, setEditingClientId] = useState<string | null>(null);
    const [clientModalSource, setClientModalSource] = useState<'workspace' | 'event_line'>('workspace');
    const [isDeleteClientConfirmOpen, setIsDeleteClientConfirmOpen] = useState(false);
    const [deleteClientConfirmInput, setDeleteClientConfirmInput] = useState('');
    const [clientTextDocumentDraft, setClientTextDocumentDraft] = useState<ClientTextDocumentDraft>({
      title: '',
      content: '',
      titleEdited: false,
    });
    const [isCreatingClientTextDocument, setIsCreatingClientTextDocument] = useState(false);
    const [isFolderEditMode, setIsFolderEditMode] = useState(false);
    const [clientDraft, setClientDraft] = useState({
      name: '',
      alias: '',
      domain: '项目',
      type: '项目',
      intro: '',
      stage: '待导入资料',
    });
    const [meetingTitle, setMeetingTitle] = useState(clientWorkspaceSettingsState.defaultMeetingTitlePrefix || '本周推进会');
  const [goalDraft, setGoalDraft] = useState({
      title: '',
      quarter: clientWorkspaceSettingsState.defaultGoalQuarter || '2026 Q2',
      progress: 50,
      ownerName: currentOperatorName,
    });
  const [dnaDraft, setDnaDraft] = useState({ category: '组织习惯', canonicalName: '', aliases: '', description: '' });
  const [clientDnaSavingKey, setClientDnaSavingKey] = useState<ClientDnaModule['moduleKey'] | null>(null);
  const [optimisticMessages, setOptimisticMessages] = useState<DisplayChatMessage[]>([]);
  const [threadMessagesById, setThreadMessagesById] = useState<Record<string, DisplayChatMessage[]>>({});
  const [threadMessagesLoadingId, setThreadMessagesLoadingId] = useState<string | null>(null);
  const [activeAnalysisRun, setActiveAnalysisRun] = useState<ClientAnalysisRun | null>(null);
  const [isStartingMessage, setIsStartingMessage] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState('');
  const [pendingStartedAt, setPendingStartedAt] = useState('');
  const [clientWorkspaceSurfaceMode, setClientWorkspaceSurfaceMode] = useState<'setup' | 'workspace'>('workspace');
  const chatContainerRef = useRef<HTMLDivElement | null>(null);
  const analysisRunPollTimerRef = useRef<number | null>(null);
  const activePollingRunIdRef = useRef<string | null>(null);
  const startMessageAbortControllerRef = useRef<AbortController | null>(null);
  const lastAutoScrolledMessageIdRef = useRef<string | null>(null);
  const lastThinkingPanelVisibleRef = useRef(false);
  const setupModeClientIdRef = useRef<string | null>(null);
  const clientImportDropDepthRef = useRef<{ buffer: number; composer: number }>({ buffer: 0, composer: 0 });
    const aggregatedWorkspaceFileHits = useMemo(() => {
      const hitMap = new Map<string, {
        key: string;
        title: string;
        path: string | null;
        excerpt: string;
        score: number;
        matchedTerms: string[];
        stage: string;
        hitCount: number;
      }>();
      (workspaceFileSearchResult?.hits || []).forEach((hit) => {
        const key = (hit.path && hit.path.trim()) || hit.title.trim();
        if (!key) return;
        const score = hit.score || 0;
        const existing = hitMap.get(key);
        if (!existing) {
          hitMap.set(key, {
            key,
            title: hit.title,
            path: hit.path || null,
            excerpt: hit.excerpt,
            score,
            matchedTerms: [...hit.matchedTerms],
            stage: hit.stage,
            hitCount: 1,
          });
          return;
        }
        existing.hitCount += 1;
        if (score > existing.score) {
          existing.score = score;
          existing.excerpt = hit.excerpt;
          existing.title = hit.title;
          existing.path = hit.path || existing.path;
          existing.stage = hit.stage;
        }
        existing.matchedTerms = Array.from(new Set([...existing.matchedTerms, ...hit.matchedTerms])).slice(0, 6);
      });
      return Array.from(hitMap.values()).sort((left, right) => {
        if (right.score !== left.score) return right.score - left.score;
        if (right.hitCount !== left.hitCount) return right.hitCount - left.hitCount;
        return left.title.localeCompare(right.title, 'zh-CN');
      });
    }, [workspaceFileSearchResult]);
    const isWorkspaceFileSearchMode = workspaceFileSearchSubmittedQuery.trim().length > 0;
    useEffect(() => {
      if (activeTab !== 'client_workspace' || !growthContextJump) return;
      const requestId = growthContextJump.requestId;
      const context = growthContextJump.context;
      if (!['client', 'meeting'].includes(context.objectType)) return;
      let cancelled = false;
      const clearRequest = () => {
        if (cancelled) return;
        setGrowthContextJump((prev) => (prev?.requestId === requestId ? null : prev));
      };
      const openClientContext = async (clientId: string) => {
        setClientWorkspaceSurfaceMode('workspace');
        setClientOverlayMode(null);
        if (clientId !== currentClientId || !workspace) {
          setCurrentClientId(clientId);
          await refreshWorkspace(clientId);
        }
      };
      const applyMeetingContext = async (clientId: string, targetWorkspace?: ClientWorkspace | null) => {
        const nextWorkspace = targetWorkspace || (clientId === currentClientId && workspace ? workspace : await getClientWorkspace(clientId));
        const targetMeeting = nextWorkspace?.meetings.find((meeting) => meeting.id === context.objectId) || null;
        if (!targetMeeting) return false;
        setCurrentClientId(clientId);
        setWorkspace(nextWorkspace);
        setClientWorkspaceSurfaceMode('workspace');
        setClientOverlayMode('meeting');
        setWorkspaceSelectedMeetingId(targetMeeting.id);
        setWorkspaceMeetingTranscript(targetMeeting.transcriptText || '');
        setWorkspaceMeetingNotes(targetMeeting.notes || '');
        flash('success', `已打开会议「${targetMeeting.title}」`);
        return true;
      };
      const run = async () => {
        if (context.objectType === 'client') {
          await openClientContext(context.objectId);
          flash('success', `已切到${terminology.singularLabel}「${context.label}」`);
          clearRequest();
          return;
        }
        const currentMeeting = workspace?.meetings.find((meeting) => meeting.id === context.objectId) || null;
        if (currentMeeting && currentClientId) {
          await applyMeetingContext(currentClientId, workspace);
          clearRequest();
          return;
        }
        const orderedClients = clients.slice().sort((left, right) => {
          if (left.id === currentClientId) return -1;
          if (right.id === currentClientId) return 1;
          return 0;
        });
        for (const client of orderedClients) {
          try {
            const candidateWorkspace = client.id === currentClientId && workspace ? workspace : await getClientWorkspace(client.id);
            if (await applyMeetingContext(client.id, candidateWorkspace)) {
              clearRequest();
              return;
            }
          } catch {
            continue;
          }
        }
        flash('error', `当前没有找到会议「${context.label}」`);
        clearRequest();
      };
      void run();
      return () => {
        cancelled = true;
      };
    }, [activeTab, clients, currentClientId, flash, growthContextJump, workspace]);
    const clearAnalysisRunPollTimer = (options?: { keepRunId?: boolean }) => {
      if (analysisRunPollTimerRef.current !== null) {
        window.clearInterval(analysisRunPollTimerRef.current);
        analysisRunPollTimerRef.current = null;
      }
      if (!options?.keepRunId) {
        activePollingRunIdRef.current = null;
      }
    };

    const hasPendingAnalysisRun = Boolean(activeAnalysisRun && (activeAnalysisRun.status === 'queued' || activeAnalysisRun.status === 'running'));
    const visibleActiveAnalysisRun =
      activeAnalysisRun && (activeAnalysisRun.status === 'queued' || activeAnalysisRun.status === 'running')
        ? activeAnalysisRun
        : null;

    const upsertWorkspaceMessages = (messages: DisplayChatMessage[], nextThreadId: string) => {
      setThreadMessagesById((prev) => ({
        ...prev,
        [nextThreadId]: mergeDisplayMessages(prev[nextThreadId] || [], messages),
      }));
      setWorkspace((prev) => {
        if (!prev) return prev;
        const threadUpdatedAt = messages[messages.length - 1]?.createdAt || new Date().toISOString();
        const existingThread = prev.threads.find((thread) => thread.id === nextThreadId);
        const nextThreads = existingThread
          ? prev.threads
              .map((thread) => (thread.id === nextThreadId ? { ...thread, updatedAt: threadUpdatedAt } : thread))
              .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))
          : [
              {
                id: nextThreadId,
                clientId: currentClientId || '',
                title: messages.find((item) => item.role === 'user')?.content.slice(0, 16) || '新对话',
                createdAt: messages[0]?.createdAt || new Date().toISOString(),
                updatedAt: threadUpdatedAt,
              },
              ...prev.threads,
            ];
        return {
          ...prev,
          threads: nextThreads,
          recentMessages: mergeDisplayMessages(prev.recentMessages as DisplayChatMessage[], messages),
        };
      });
    };

    const upsertAnalysisRun = (run: ClientAnalysisRun, options?: { persistToWorkspace?: boolean }) => {
      setActiveAnalysisRun(run);
      if (!options?.persistToWorkspace) return;
      setWorkspace((prev) => {
        if (!prev) return prev;
        const nextRuns = [run, ...(prev.analysisRuns || []).filter((item) => item.id !== run.id)].sort((left, right) =>
          right.updatedAt.localeCompare(left.updatedAt),
        );
        return {
          ...prev,
          analysisRuns: nextRuns,
        };
      });
    };

    const beginAnalysisRunPolling = (runId: string, clientId: string) => {
      if (analysisRunPollTimerRef.current !== null && activePollingRunIdRef.current === runId) {
        return;
      }
      clearAnalysisRunPollTimer();
      activePollingRunIdRef.current = runId;
      const pollRun = () => {
        void getClientAnalysisRun(clientId, runId)
          .then((run) => {
            flushSync(() => {
              upsertAnalysisRun(run, { persistToWorkspace: run.status !== 'queued' && run.status !== 'running' });
              if (run.assistantMessage && run.assistantMessage.status !== 'loading') {
                upsertWorkspaceMessages([run.assistantMessage], run.threadId);
              }
            });
            if (run.status === 'completed' || run.status === 'failed' || run.status === 'canceled') {
      clearAnalysisRunPollTimer();
      flushSync(() => {
        setOptimisticMessages([]);
                setActiveAnalysisRun(run.status === 'canceled' ? null : run);
                setPendingQuestion('');
                setPendingStartedAt('');
                if (run.assistantMessageId) {
                  setActiveMessageId(run.assistantMessageId);
                }
      });
              void refreshWorkspace(clientId).catch(() => undefined);
            }
          })
          .catch(() => undefined);
      };
      pollRun();
      analysisRunPollTimerRef.current = window.setInterval(pollRun, 1200);
    };

    useEffect(() => {
      if (!workspace?.meetings.length) {
        if (workspaceSelectedMeetingId) setWorkspaceSelectedMeetingId('');
      } else if (!workspaceSelectedMeetingId || !workspace.meetings.some((meeting) => meeting.id === workspaceSelectedMeetingId)) {
        setWorkspaceSelectedMeetingId(workspace.meetings[0].id);
      }
    }, [workspace?.meetings, workspaceSelectedMeetingId]);

    useEffect(() => {
      setOptimisticMessages([]);
      setThreadMessagesById({});
      setThreadMessagesLoadingId(null);
      setActiveAnalysisRun(null);
      setIsStartingMessage(false);
      setPendingQuestion('');
      setPendingStartedAt('');
      setClientImportDropZone(null);
      setTemplateFillDialog(null);
      clientImportDropDepthRef.current.buffer = 0;
      clientImportDropDepthRef.current.composer = 0;
      startMessageAbortControllerRef.current?.abort();
      startMessageAbortControllerRef.current = null;
      lastAutoScrolledMessageIdRef.current = null;
      lastThinkingPanelVisibleRef.current = false;
      setupModeClientIdRef.current = null;
      clearAnalysisRunPollTimer();
    }, [currentClientId]);

    const knowledgeStatus = workspace?.knowledgeStatus || null;
    const sourceDocumentCount = knowledgeStatus?.totalDocuments || workspace?.documents.length || 0;
    const clientNeedsProjectSetup = sourceDocumentCount === 0;
    const dnaDocumentCount = (workspace?.dnaModules || []).filter((module) => module.hasDocument).length;
    const hasWorkspaceBootstrapSignals = Boolean(
      sourceDocumentCount > 0 ||
      (workspace?.recentMessages.length || 0) > 0 ||
      (workspace?.meetings.length || 0) > 0 ||
      (workspace?.goals.length || 0) > 0,
    );

    useEffect(() => {
      const workspaceClientId = workspace?.client.id || currentClientId || null;
      if (workspaceClientId == null) return;
      if (setupModeClientIdRef.current === workspaceClientId) return;
      setupModeClientIdRef.current = workspaceClientId;
      setClientWorkspaceSurfaceMode(clientNeedsProjectSetup && hasWorkspaceBootstrapSignals === false ? 'setup' : 'workspace');
    }, [currentClientId, workspace?.client.id, clientNeedsProjectSetup, hasWorkspaceBootstrapSignals]);

    const buildTemplateFillDialogInitialState = (templatePath: string): TemplateFillDialogState => ({
      open: true,
      runId: null,
      templateName: templatePath.split('/').pop() || '模板文档',
      templatePathRaw: templatePath,
      allowFallbackImport: false,
      startedAt: Date.now(),
      stage: 'queued',
      backendStatus: 'queued',
      backendPhase: 'queued',
      percent: 2,
      statusLabel: '正在创建模板填写任务',
      hint: '系统正在准备模板识别与资料检索链路，请稍候。',
      evidenceTitles: [],
      fieldCount: 0,
      processedCount: 0,
      filledCount: 0,
      missingCount: 0,
      currentFieldLabel: null,
      attachmentChecklist: [],
      fields: [],
      outputPath: null,
      errorMessage: null,
    });

    const buildTemplateFillDialogFromRun = (
      run: ClientTemplateFillRun,
      previous?: TemplateFillDialogState | null,
    ): TemplateFillDialogState => {
      const normalizedStage: TemplateFillStage =
        run.status === 'completed'
          ? 'completed'
          : run.status === 'failed'
            ? 'failed'
            : run.phase === 'queued'
              ? 'queued'
              : run.phase;
      const defaultStatusLabel =
        normalizedStage === 'queued'
          ? '排队等待开始'
          : normalizedStage === 'parsing'
          ? '正在识别模板字段'
          : normalizedStage === 'retrieving'
            ? `正在检索${terminology.singularLabel}资料`
            : normalizedStage === 'writing'
              ? 'AI 正在填写模板'
              : normalizedStage === 'completed'
                ? '填写完成'
                : '模板填写失败';
      const hint =
        normalizedStage === 'completed'
          ? `已生成 ${run.templateName.replace(/\.docx$/i, '')} 的填写结果，共处理 ${run.fieldCount} 个字段；其中 ${run.filledCount} 项已自动填写，${run.missingCount} 项待确认。`
          : normalizedStage === 'failed'
            ? '这次自动填写没有成功完成，可以关闭后重试。'
          : normalizedStage === 'queued'
            ? '当前有其他模板填写任务正在处理。前面的任务完成后会自动开始，无需重复点击或刷新。'
          : normalizedStage === 'retrieving'
              ? `正在为字段资料做检索（${Math.min(run.processedCount || 0, run.fieldCount || 0)}/${run.fieldCount || 0}）。${run.currentFieldLabel ? ` 当前批次：${run.currentFieldLabel}` : ''}`
              : normalizedStage === 'writing'
                ? `AI 正在逐字段填写模板（${Math.min(run.processedCount || 0, run.fieldCount || 0)}/${run.fieldCount || 0}）。${run.currentFieldLabel ? ` 当前字段：${run.currentFieldLabel}` : ''}`
                : '系统先判断这份文档里哪些位置需要自动填写。';
      return {
        open: true,
        runId: run.id,
        templateName: run.templateName,
        templatePathRaw: run.templatePath,
        allowFallbackImport: previous?.allowFallbackImport ?? false,
        startedAt: previous?.runId === run.id ? previous.startedAt : Date.parse(run.createdAt || '') || Date.now(),
        stage: normalizedStage,
        backendStatus: run.status,
        backendPhase: run.phase || null,
        percent:
          normalizedStage === 'queued'
            ? Math.max(2, Math.min(8, Math.round(run.progress || 0)))
            : Math.max(0, Math.min(100, Math.round(run.progress || 0))),
        statusLabel: run.stageLabel || defaultStatusLabel,
        hint,
        evidenceTitles: run.evidenceTitles || [],
        fieldCount: run.fieldCount || 0,
        processedCount: run.processedCount || 0,
        filledCount: run.filledCount || 0,
        missingCount: run.missingCount || 0,
        currentFieldLabel: run.currentFieldLabel || null,
        attachmentChecklist: run.attachmentChecklist || [],
        fields: run.fields || [],
        outputPath: run.outputPath || null,
        errorMessage: run.errorMessage || null,
      };
    };

    const buildTemplateFillStepStatuses = (
      dialog: TemplateFillDialogState,
    ): Array<[string, 'idle' | 'active' | 'done' | 'failed']> => {
      const steps: Array<[string, 'idle' | 'active' | 'done' | 'failed']> = [
        ['模板识别', 'idle'],
        ['资料检索', 'idle'],
        ['AI 填写', 'idle'],
        ['生成文档', 'idle'],
      ];
      const backendPhase = dialog.backendPhase;
      const backendStatus = dialog.backendStatus;
      if (backendStatus === 'completed') {
        return steps.map(([label]) => [label, 'done']);
      }
      if (backendStatus === 'queued' || backendPhase === 'queued') {
        return steps;
      }
      if (backendStatus === 'failed') {
        if (backendPhase === 'parsing') {
          steps[0][1] = 'failed';
        } else if (backendPhase === 'retrieving') {
          steps[0][1] = 'done';
          steps[1][1] = 'failed';
        } else if (backendPhase === 'writing') {
          steps[0][1] = 'done';
          steps[1][1] = 'done';
          steps[2][1] = 'failed';
        } else if (backendPhase === 'completed') {
          return steps.map(([label]) => [label, 'done']);
        }
        return steps;
      }
      if (backendPhase === 'parsing') {
        steps[0][1] = 'active';
      } else if (backendPhase === 'retrieving') {
        steps[0][1] = 'done';
        steps[1][1] = 'active';
      } else if (backendPhase === 'writing') {
        steps[0][1] = 'done';
        steps[1][1] = 'done';
        steps[2][1] = 'active';
      } else if (backendPhase === 'completed') {
        return steps.map(([label]) => [label, 'done']);
      }
      return steps;
    };

    const buildTemplateMissingMaterialItems = (fields: ClientTemplateFillField[]) => {
      const items: Array<{
        label: string;
        reason: string;
        suggestedSources: string[];
      }> = [];
      const seen = new Set<string>();
      for (const field of fields) {
        if (!(field.status === 'missing' || field.reviewRequired)) continue;
        const key = field.label.trim();
        if (!key || seen.has(key)) continue;
        seen.add(key);
        items.push({
          label: field.label,
          reason: field.followUpQuestion || field.basisSummary || '当前资料不足，建议继续补资料后复核。',
          suggestedSources: (field.suggestedSources || []).slice(0, 4),
        });
      }
      return items;
    };

    useEffect(() => {
      if (!currentClientId || !templateFillDialog?.open || !templateFillDialog.runId) {
        return;
      }
      let cancelled = false;
      let timeoutId: number | null = null;
      let consecutivePollFailures = 0;
      const poll = async () => {
        try {
          const run = await getClientTemplateFillRun(currentClientId, templateFillDialog.runId!);
          if (cancelled) return;
          consecutivePollFailures = 0;
          setTemplateFillDialog((previous) => buildTemplateFillDialogFromRun(run, previous));
          const terminal = run.status === 'completed' || run.status === 'failed';
          setIsTemplateFilling(!terminal);
          if (terminal) {
            if (run.status === 'completed') {
              flash('success', `模板已填写：${run.filledCount}/${run.fieldCount} 个字段`);
              if (run.outputPath) {
                void openPathBridge(run.outputPath);
              }
            } else if (run.errorMessage) {
              const unsupportedTemplate =
                /没有识别到可自动填写的字段/i.test(run.errorMessage)
                || /只支持 \.docx/i.test(run.errorMessage);
              if (unsupportedTemplate && templateFillDialog.allowFallbackImport) {
                setTemplateFillDialog(null);
                void handleImport('file', [templateFillDialog.templatePathRaw]);
                flash('info', '未识别为可填写模板，已按普通资料导入。');
              } else {
                flash('error', run.errorMessage);
              }
            } else {
              flash('error', '模板填写失败');
            }
            return;
          }
          timeoutId = window.setTimeout(poll, 1200);
        } catch (error) {
          if (cancelled) return;
          consecutivePollFailures += 1;
          let backendHealthy = false;
          try {
            const response = await probeLocalBackendHealth(1200);
            setHealth(response);
            backendReadyRef.current = true;
            clearLocalServiceStartupBanner();
            backendHealthy = response.backend === 'online';
          } catch {
            backendHealthy = false;
          }
          const detail = error instanceof Error ? error.message : '无法获取模板填写状态';
          if (backendHealthy && consecutivePollFailures < 4) {
            setTemplateFillDialog((previous) =>
              previous
                ? {
                    ...previous,
                    statusLabel: '正在等待后台返回最新进度',
                    hint: '模板填写仍在后台继续。正在重新连接本地服务并刷新进度…',
                  }
                : previous,
            );
            timeoutId = window.setTimeout(poll, 1500);
            return;
          }
          setTemplateFillDialog((previous) =>
            previous
              ? {
                  ...previous,
                  stage: 'failed',
                  statusLabel: '模板填写失败',
                  hint: backendHealthy
                    ? '填写任务未能继续返回进度，请关闭后重试。'
                    : '本地服务暂时不可用，请等待应用恢复后重试。',
                  errorMessage: detail,
                }
              : previous,
          );
          setIsTemplateFilling(false);
          flash('error', detail);
        }
      };
      void poll();
      return () => {
        cancelled = true;
        if (timeoutId !== null) {
          window.clearTimeout(timeoutId);
        }
      };
    }, [currentClientId, templateFillDialog?.open, templateFillDialog?.runId]);

    useEffect(() => {
      const recentMessages = (workspace?.recentMessages || []) as DisplayChatMessage[];
      if (!recentMessages.length) return;
      const groupedMessages = recentMessages.reduce<Record<string, DisplayChatMessage[]>>((accumulator, message) => {
        if (!accumulator[message.threadId]) {
          accumulator[message.threadId] = [];
        }
        accumulator[message.threadId].push(message);
        return accumulator;
      }, {});
      setThreadMessagesById((prev) => {
        const next = { ...prev };
        for (const [threadId, messages] of Object.entries(groupedMessages)) {
          next[threadId] = mergeDisplayMessages(prev[threadId] || [], messages);
        }
        return next;
      });
    }, [workspace?.recentMessages]);

    const latestActiveWorkspaceRun = useMemo(
      () => (workspace?.analysisRuns || []).find((item) => item.status === 'queued' || item.status === 'running') || null,
      [workspace?.analysisRuns],
    );

    useEffect(() => {
      if (!currentClientId) return;
      if (hasPendingAnalysisRun) return;
      if (!latestActiveWorkspaceRun) {
        return;
      }
      setActiveAnalysisRun((prev) =>
        prev?.id === latestActiveWorkspaceRun.id ? { ...prev, ...latestActiveWorkspaceRun } : latestActiveWorkspaceRun,
      );
      setActiveMessageId(latestActiveWorkspaceRun.assistantMessageId || null);
      if (activePollingRunIdRef.current !== latestActiveWorkspaceRun.id) {
        beginAnalysisRunPolling(latestActiveWorkspaceRun.id, currentClientId);
      }
    }, [currentClientId, latestActiveWorkspaceRun?.id, hasPendingAnalysisRun]);

    useEffect(() => {
      setMeetingTitle((prev) => (prev === '本周推进会' || !prev.trim() ? clientWorkspaceSettingsState.defaultMeetingTitlePrefix || '本周推进会' : prev));
      setGoalDraft((prev) => ({
        ...prev,
        quarter: prev.quarter === '2026 Q2' || !prev.quarter.trim() ? clientWorkspaceSettingsState.defaultGoalQuarter || '2026 Q2' : prev.quarter,
        ownerName: prev.ownerName || currentOperatorName,
      }));
    }, [clientWorkspaceSettingsState.defaultGoalQuarter, clientWorkspaceSettingsState.defaultMeetingTitlePrefix, currentOperatorName]);

    useEffect(() => () => {
      startMessageAbortControllerRef.current?.abort();
      startMessageAbortControllerRef.current = null;
      clearAnalysisRunPollTimer();
    }, []);

    useEffect(() => {
      const lastJobStatus = workspace?.knowledgeStatus?.lastJobStatus;
      const shouldPoll = Boolean(currentClientId) && (lastJobStatus === 'queued' || lastJobStatus === 'running');
      if (!shouldPoll) return undefined;
      let disposed = false;
      const pollStatus = () => {
        void getClientKnowledgeStatus(currentClientId)
          .then((nextStatus) => {
            if (disposed) return;
            setWorkspace((prev) => {
              if (!prev) return prev;
              const previousStatus = prev.knowledgeStatus;
              const unchanged =
                previousStatus &&
                previousStatus.totalDocuments === nextStatus.totalDocuments &&
                previousStatus.totalChunks === nextStatus.totalChunks &&
                previousStatus.vectorizedDocuments === nextStatus.vectorizedDocuments &&
                previousStatus.dedupedDocuments === nextStatus.dedupedDocuments &&
                previousStatus.reviewPendingDocuments === nextStatus.reviewPendingDocuments &&
                previousStatus.surrogateCount === nextStatus.surrogateCount &&
                previousStatus.memoryDocCount === nextStatus.memoryDocCount &&
                previousStatus.masterIndexCount === nextStatus.masterIndexCount &&
                previousStatus.reclassifiedDocumentCount === nextStatus.reclassifiedDocumentCount &&
                previousStatus.qdrantReady === nextStatus.qdrantReady &&
                previousStatus.lastUpdatedAt === nextStatus.lastUpdatedAt &&
                previousStatus.pendingJobs === nextStatus.pendingJobs &&
                previousStatus.runningJobs === nextStatus.runningJobs &&
                previousStatus.lastJobStatus === nextStatus.lastJobStatus &&
                previousStatus.lastJobError === nextStatus.lastJobError &&
                previousStatus.lastSuccessfulRunAt === nextStatus.lastSuccessfulRunAt &&
                previousStatus.embeddingMode === nextStatus.embeddingMode &&
                previousStatus.embeddingModel === nextStatus.embeddingModel &&
                previousStatus.embeddingError === nextStatus.embeddingError;
              return unchanged ? prev : { ...prev, knowledgeStatus: nextStatus };
            });
            if (nextStatus.lastJobStatus !== 'queued' && nextStatus.lastJobStatus !== 'running') {
              window.clearInterval(timer);
              void refreshWorkspace(currentClientId).catch(() => undefined);
            }
          })
          .catch(() => undefined);
      };
      const timer = window.setInterval(pollStatus, 3000);
      return () => {
        disposed = true;
        window.clearInterval(timer);
      };
    }, [currentClientId, workspace?.knowledgeStatus?.lastJobStatus]);

    const filteredClients = clients.filter((client) => !searchQuery.trim() || `${client.name}${client.alias}${client.domain}`.includes(searchQuery.trim()));
    const currentThreadId = activeAnalysisRun?.threadId || workspace?.threads?.[0]?.id || null;
    const visibleThreadAnalysisRun =
      visibleActiveAnalysisRun && visibleActiveAnalysisRun.threadId === currentThreadId ? visibleActiveAnalysisRun : null;
    const activeAssistantMessageId = visibleThreadAnalysisRun?.assistantMessageId || null;
    const activeOptimisticMessages = optimisticMessages.filter((item) =>
      currentThreadId ? item.threadId === currentThreadId : item.threadId === CLIENT_CHAT_DRAFT_THREAD_ID,
    );
    const currentThreadMessages = currentThreadId ? threadMessagesById[currentThreadId] || [] : [];

    const currentChat = useMemo(() => {
      return mergeDisplayMessages(currentThreadMessages, activeOptimisticMessages)
        .filter((item) => item.status !== 'loading' && item.id !== activeAssistantMessageId)
        .sort((left, right) => left.createdAt.localeCompare(right.createdAt));
    }, [currentThreadMessages, activeOptimisticMessages, activeAssistantMessageId]);

    useEffect(() => {
      if (!currentClientId || !currentThreadId) {
        setThreadMessagesLoadingId(null);
        return undefined;
      }
      let disposed = false;
      setThreadMessagesLoadingId(currentThreadId);
      void getClientChatThread(currentClientId, currentThreadId)
        .then((detail) => {
          if (disposed) return;
          setThreadMessagesById((prev) => ({
            ...prev,
            [currentThreadId]: mergeDisplayMessages(prev[currentThreadId] || [], detail.messages as DisplayChatMessage[]),
          }));
        })
        .catch(() => undefined)
        .finally(() => {
          if (!disposed) {
            setThreadMessagesLoadingId((prev) => (prev === currentThreadId ? null : prev));
          }
        });
      return () => {
        disposed = true;
      };
    }, [currentClientId, currentThreadId]);

    useEffect(() => {
      const assistantMessages = currentChat.filter((message) => message.role === 'assistant');
      if (!assistantMessages.length) {
        if (activeMessageId) {
          setActiveMessageId(null);
        }
        return;
      }
      if (!activeMessageId || !assistantMessages.some((message) => message.id === activeMessageId)) {
        setActiveMessageId(assistantMessages[assistantMessages.length - 1].id);
      }
    }, [currentChat, activeMessageId]);

    const selectedChatMessage = currentChat.find((message) => message.id === activeMessageId) || null;
    const activeRunEvidence: EvidenceItem[] =
      visibleThreadAnalysisRun?.evidenceSummary?.evidenceList?.map((item, index) => ({
        id: `${visibleThreadAnalysisRun.id}_${index}`,
        title: item.title,
        excerpt: item.excerpt,
        sourceType: item.stage,
        documentId: null,
        path: item.path || undefined,
        score: item.score ?? undefined,
        matchedTerms: item.matchedTerms,
        sectionLabel: item.sectionLabel || undefined,
        retrievalStage: item.stage,
      })) || [];
    const activeEvidence: EvidenceItem[] =
      activeRunEvidence.length > 0
        ? activeRunEvidence
        : selectedChatMessage?.evidence && selectedChatMessage.evidence.length > 0
        ? selectedChatMessage.evidence
        : !activeMessageId && workspace?.documentCards?.[0]
          ? [
              {
                id: 'default-evidence',
                title: workspace.documentCards[0].title,
                excerpt: workspace.documentCards[0].summary,
                sourceType: workspace.documentCards[0].kind,
                documentId: workspace.documentCards[0].documentId,
                path: workspace.documentCards[0].sourcePath,
                score: undefined,
                matchedTerms: [],
                sectionLabel: undefined,
                retrievalStage: undefined,
              },
            ]
          : [];
    const latestImport = workspace?.imports[0] || null;
    const topDocumentCards = workspace?.documentCards?.slice(0, 6) || [];
    const importStats = useMemo(
      () => ({
        batches: workspace?.imports.length || 0,
        imported: knowledgeStatus?.totalDocuments || 0,
        skipped: latestImport?.skippedCount || 0,
        chunks: knowledgeStatus?.totalChunks || 0,
        vectorized: knowledgeStatus?.vectorizedDocuments || 0,
        deduped: knowledgeStatus?.dedupedDocuments || 0,
        reviewPending: knowledgeStatus?.reviewPendingDocuments || 0,
        surrogates: knowledgeStatus?.surrogateCount || 0,
        memoryDocs: knowledgeStatus?.memoryDocCount || 0,
        reclassified: knowledgeStatus?.reclassifiedDocumentCount || 0,
        pendingJobs: knowledgeStatus?.pendingJobs || 0,
        runningJobs: knowledgeStatus?.runningJobs || 0,
      }),
      [workspace, latestImport, knowledgeStatus],
    );

      const latestKnowledgeJob = workspace?.knowledgeJobs?.[0] || null;
      const composerProviderLabel =
        health?.ai.provider && health.ai.provider !== 'mock' && health.ai.ready ? providerDisplayNames[health.ai.provider] : 'AI';
      const latestChatMessageId = currentChat[currentChat.length - 1]?.id || null;
      const transientThinkingPanel = useMemo(() => {
        if (visibleThreadAnalysisRun) {
          const stableQuestion = pendingQuestion && pendingQuestion === visibleThreadAnalysisRun.question ? pendingQuestion : visibleThreadAnalysisRun.question;
          const stableStartedAt =
            pendingStartedAt && stableQuestion === pendingQuestion ? pendingStartedAt : visibleThreadAnalysisRun.createdAt;
          return {
            question: stableQuestion,
            startedAt: stableStartedAt,
            stageLabel: visibleThreadAnalysisRun.stageLabel || 'AI 正在计算，请稍候',
            run: visibleThreadAnalysisRun,
            mode: 'running' as const,
          };
        }
        if (pendingQuestion) {
          return {
            question: pendingQuestion,
            startedAt: pendingStartedAt || new Date().toISOString(),
            stageLabel: '问题已发送，正在建立分析任务',
            run: null,
            mode: 'starting' as const,
          };
        }
        return null;
      }, [pendingQuestion, pendingStartedAt, visibleThreadAnalysisRun]);
      const thinkingPanelVisible = Boolean(transientThinkingPanel);
      const composerBusyMode: 'starting' | 'running' | null = transientThinkingPanel?.mode || null;

    useEffect(() => {
      const container = chatContainerRef.current;
      if (!container) return;
      const thinkingPanelBecameVisible = thinkingPanelVisible && !lastThinkingPanelVisibleRef.current;
      const hasNewMessage = Boolean(latestChatMessageId) && latestChatMessageId !== lastAutoScrolledMessageIdRef.current;
      if (thinkingPanelBecameVisible || hasNewMessage) {
        container.scrollTop = container.scrollHeight;
      }
      lastThinkingPanelVisibleRef.current = thinkingPanelVisible;
      if (latestChatMessageId) {
        lastAutoScrolledMessageIdRef.current = latestChatMessageId;
      }
    }, [latestChatMessageId, thinkingPanelVisible]);

    const aiStatus = useMemo(() => {
      if (!health?.ai.provider) {
        return {
          label: 'AI 状态加载中',
          className: 'text-gray-600 bg-gray-50 border-gray-200 hover:bg-gray-100',
          dotClassName: 'bg-gray-400',
          subtitle: '正在读取当前模型',
        };
      }
      const provider = health.ai.provider as AiProvider;
      const providerLabel = providerDisplayNames[provider] || provider;
      if (provider !== 'mock' && health.ai.ready) {
        return {
          label: `${providerLabel} 已连接`,
          className: 'text-emerald-600 bg-emerald-50 border-emerald-100 hover:bg-emerald-100',
          dotClassName: 'bg-emerald-500',
          subtitle: health.ai.model,
        };
      }
      if (provider !== 'mock' && !health.ai.ready) {
        return {
          label: `${providerLabel} 未配置`,
          className: 'text-amber-700 bg-amber-50 border-amber-100 hover:bg-amber-100',
          dotClassName: 'bg-amber-500',
          subtitle: '当前回退 mock',
        };
      }
      return {
        label: '本地 Mock 模式',
        className: 'text-sky-700 bg-sky-50 border-sky-100 hover:bg-sky-100',
        dotClassName: 'bg-sky-500',
        subtitle: '用于流程联调',
      };
    }, [health]);

    const clientDnaDisplayLabel = 'DNA';
    const clientDnaReady = Boolean(workspace?.dnaModules?.some((module) => module.hasDocument));
    const clientDnaStatus = clientDnaReady
      ? {
          className: 'text-emerald-600 bg-emerald-50 border-emerald-100 hover:bg-emerald-100',
          dotClassName: 'bg-emerald-500',
        }
      : {
          className: 'text-gray-500 bg-gray-50 border-gray-200 hover:bg-gray-100',
          dotClassName: 'bg-gray-400',
        };

    const selectedMeeting = workspace?.meetings.find((meeting) => meeting.id === workspaceSelectedMeetingId) || workspace?.meetings[0];
    const isBackendBlocked = Boolean(backendCompatibilityError);

    const handleRebuildKnowledge = async () => {
      if (!currentClientId) return;
      try {
        await rebuildClientKnowledge(currentClientId);
        await refreshWorkspace(currentClientId);
        flash('success', '知识重建任务已入队，正在后台处理');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '知识重建失败');
      }
    };

    const handleBackfillWorkspaceImports = async () => {
      if (!currentClientId) return;
      try {
        const result = await backfillClientWorkspaceImports(currentClientId);
        await loadClientBlock(currentClientId);
        flash(
          'success',
          `已从现有${terminology.singularLabel}目录补录 ${result.imported} 份资料${result.skipped ? `，跳过 ${result.skipped} 份已存在文件` : ''}`,
        );
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '回填现有目录失败');
      }
    };

    const handleUploadClientDna = async (moduleKey: ClientDnaModule['moduleKey']) => {
      if (!currentClientId) return;
      const paths = await selectFilesBridge();
      const filePath = paths[0];
      if (!filePath) return;
      if (!/\.(?:md|markdown|docx)$/i.test(filePath)) {
        flash('error', '这里只允许上传 .md、.markdown 或 .docx 文件');
        return;
      }
      setClientDnaSavingKey(moduleKey);
      try {
        await updateClientDnaDocument(currentClientId, moduleKey, { filePath });
        await refreshWorkspace(currentClientId);
        const moduleTitle = CLIENT_DNA_MODULES.find((item) => item.moduleKey === moduleKey)?.title || '项目资料';
        flash('success', `${moduleTitle} 已更新`);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : 'DNA 上传失败');
      } finally {
        setClientDnaSavingKey(null);
      }
    };

    const handleCopyClientDnaPrompt = async (moduleKey: ClientDnaModule['moduleKey']) => {
      const prompt = getClientDnaPromptTemplate(moduleKey);
      const moduleTitle = CLIENT_DNA_MODULES.find((item) => item.moduleKey === moduleKey)?.title || '项目资料';
      try {
        await navigator.clipboard.writeText(prompt);
        flash('success', `${moduleTitle} AI 指令已复制`);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '复制 AI 指令失败');
      }
    };

    const handleGenerateClientDnaCandidates = async () => {
      if (!currentClientId) return;
      try {
        await generateClientDnaCandidates(currentClientId, { refreshGenerated: true });
        await refreshWorkspace(currentClientId);
        flash('success', '系统已开始基于资料库重新生成候选文档');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '候选文档生成失败');
      }
    };

    const handleCreateProjectModule = async (payload: ProjectModulePayload) => {
      if (!currentClientId) return;
      try {
        await createProjectModule(currentClientId, payload);
        await refreshWorkspace(currentClientId);
        flash('success', '任务模块已创建');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '任务模块创建失败');
      }
    };

    const handleCreateProjectFlow = async (payload: ProjectFlowPayload) => {
      if (!currentClientId) return;
      try {
        await createProjectFlow(currentClientId, payload);
        await refreshWorkspace(currentClientId);
        flash('success', '流程已创建');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '流程创建失败');
      }
    };

    const resumeEventLineModalAfterProject = () => {
      if (eventLineProjectResumeTarget === 'create') {
        setIsEventLineCreateOpen(true);
      } else if (eventLineProjectResumeTarget === 'edit' && activeEventLine) {
        setIsEventLineEditorOpen(true);
      }
      setEventLineProjectResumeTarget(null);
    };

    const closeClientModal = (options?: { resumeEventLine?: boolean }) => {
      setIsDeleteClientConfirmOpen(false);
      setDeleteClientConfirmInput('');
      setIsClientModalOpen(false);
      if (options?.resumeEventLine && clientModalSource === 'event_line') {
        resumeEventLineModalAfterProject();
      } else if (!options?.resumeEventLine) {
        setEventLineProjectResumeTarget(null);
      }
    };

    const openCreateClientModal = (
      source: 'workspace' | 'event_line' = 'workspace',
      options?: { initialName?: string },
    ) => {
      setClientModalSource(source);
      if (source === 'event_line') {
        const nextResumeTarget = isEventLineCreateOpen ? 'create' : (isEventLineEditorOpen ? 'edit' : null);
        setEventLineProjectResumeTarget(nextResumeTarget);
        setIsEventLineCreateOpen(false);
        setIsEventLineEditorOpen(false);
      } else {
        setEventLineProjectResumeTarget(null);
      }
      setEditingClientId(null);
      const initialName = options?.initialName?.trim() || '';
      setClientDraft({
        name: initialName,
        alias: '',
        domain: terminology.singularLabel,
        type: terminology.singularLabel,
        intro: '',
        stage: '待导入资料',
      });
      setIsClientModalOpen(true);
    };

    const openEditClientModal = (client: ClientSummary) => {
      setClientModalSource('workspace');
      setEditingClientId(client.id);
      setClientDraft({
        name: client.name,
        alias: client.alias,
        domain: client.domain,
        type: client.type,
        intro: client.intro,
        stage: client.stage,
      });
      setIsClientModalOpen(true);
    };

    const submitClientModal = async () => {
      if (!clientDraft.name.trim()) {
        flash('error', `请先填写${terminology.singularLabel}名称`);
        return;
      }
      const isEditingProject = Boolean(editingClientId);
      const payload = {
        name: clientDraft.name.trim(),
        alias: clientDraft.alias.trim() || clientDraft.name.trim(),
        domain: clientDraft.domain.trim() || terminology.singularLabel,
        type: clientDraft.type.trim() || terminology.singularLabel,
        intro: clientDraft.intro.trim() || `等待导入已有资料，系统将自动分析归档并建立${terminology.singularLabel}上下文。`,
        stage: clientDraft.stage.trim() || '待导入资料',
      };
      try {
        const savedClient = editingClientId ? await updateClient(editingClientId, payload) : await createClient(payload);
        setSearchQuery('');
        setIsClientModalOpen(false);
        if (clientModalSource === 'event_line') {
          const nextClients = await getClients();
          setClients(nextClients);
          setEventLineEditorDraft((prev) => ({ ...prev, primaryClientId: savedClient.id }));
          resumeEventLineModalAfterProject();
          flash('success', isEditingProject ? `${terminology.singularLabel}已更新，可继续回到事件线编辑。` : `${terminology.singularLabel}已创建，已经自动带入当前事件线。`);
          return;
        }
        setEventLineProjectResumeTarget(null);
        setActiveTab('client_workspace');
        if (!isEditingProject) {
          setClientWorkspaceSurfaceMode('setup');
        }
        try {
          await loadClientBlock(savedClient.id);
        } catch (workspaceError) {
          const clientItems = await getClients();
          setClients(clientItems);
          setCurrentClientId(savedClient.id);
          setWorkspace(null);
          flash('success', isEditingProject ? `${terminology.singularLabel}信息已更新` : `${terminology.singularLabel}已创建，先导入已有资料，系统会自动分析归档并建立${terminology.singularLabel}上下文。`);
          return;
        }
        flash('success', isEditingProject ? `${terminology.singularLabel}信息已更新` : `${terminology.singularLabel}已创建，先导入已有资料，系统会自动分析归档并建立${terminology.singularLabel}上下文。`);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : `保存${terminology.singularLabel}失败`);
      }
    };

    const handleClientModalKeyDown = (event: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      if (event.key !== 'Enter') return;
      if (event.currentTarget.tagName === 'TEXTAREA' && !event.metaKey && !event.ctrlKey) return;
      if (event.shiftKey) return;
      event.preventDefault();
      void submitClientModal();
    };

    const handleDeleteClient = () => {
      if (!editingClientId) return;
      setDeleteClientConfirmInput('');
      setIsDeleteClientConfirmOpen(true);
    };

    const confirmDeleteClient = async () => {
      if (!editingClientId) return;
      const targetClient = clients.find((client) => client.id === editingClientId);
      const targetName = targetClient?.name || clientDraft.name.trim() || `该${terminology.singularLabel}`;
      if (deleteClientConfirmInput.trim() !== targetName) {
        flash('error', `${terminology.singularLabel}名称不匹配，已取消删除`);
        return;
      }
      try {
        await deleteClient(editingClientId);
        const nextClients = await getClients();
        setClients(nextClients);
        setIsDeleteClientConfirmOpen(false);
        setDeleteClientConfirmInput('');
        setIsClientModalOpen(false);
        setEditingClientId(null);
        setClientDraft({
          name: '',
          alias: '',
          domain: '',
          type: '',
          intro: '',
          stage: '战略陪伴中',
        });
        setActiveMessageId(null);
        if (currentClientId === editingClientId) {
          const fallbackClientId = nextClients[0]?.id ?? null;
          setCurrentClientId(fallbackClientId);
          if (fallbackClientId) {
            await loadClientBlock(fallbackClientId);
          } else {
            setWorkspace(null);
          }
        }
        flash('success', `${terminology.singularLabel}及其全部档案已删除`);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : `删除${terminology.singularLabel}失败`);
      }
    };

    const handleDeleteClientFolder = async (folder: ClientWorkspace['folders'][number]) => {
      if (!currentClientId) return;
      if (!window.confirm(`确认移除快捷通道里的"${folder.label}"？只有空文件夹可以移除。`)) {
        return;
      }
      try {
        await deleteClientFolder(currentClientId, folder.id);
        await refreshWorkspace(currentClientId);
        flash('success', '文件夹已移除');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '移除文件夹失败');
      }
    };

    const runWorkspaceFileSearch = async (rawQuery?: string) => {
      const query = (rawQuery ?? workspaceFileSearchQuery).trim();
      if (!currentClientId) {
        flash('error', `请先选择${terminology.singularLabel}`);
        return;
      }
      if (!query) {
        setWorkspaceFileSearchSubmittedQuery('');
        setWorkspaceFileSearchResult(null);
        return;
      }
      try {
        setIsWorkspaceFileSearching(true);
        const result = await searchClientKnowledge(currentClientId, query, currentThreadId || undefined);
        setWorkspaceFileSearchSubmittedQuery(query);
        setWorkspaceFileSearchResult(result);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '搜索文件失败');
      } finally {
        setIsWorkspaceFileSearching(false);
      }
    };

    const clearWorkspaceFileSearch = () => {
      setWorkspaceFileSearchQuery('');
      setWorkspaceFileSearchSubmittedQuery('');
      setWorkspaceFileSearchResult(null);
      setIsWorkspaceFileSearching(false);
    };

    const handleImport = async (mode: 'folder' | 'file', paths: string[]) => {
      if (!currentClientId) {
        flash('error', `请先选择${terminology.singularLabel}`);
        return;
      }
      if (backendCompatibilityError) {
        flash('error', backendCompatibilityError);
        return;
      }
      if (!paths.length) return;
      try {
        setIsImportSubmitting(true);
        setLatestImportFeedback(null);
        importProgressHoldUntilRef.current = Date.now() + 3000;
        const importResults = await importPaths(currentClientId, mode, paths);
        const importedCount = importResults.reduce((sum, item) => sum + (item.importedCount || 0), 0);
        const skippedCount = importResults.reduce((sum, item) => sum + (item.skippedCount || 0), 0);
        const queuedImports = importResults.filter((item) => item.status === 'queued').length;
        const nextWorkspace = await refreshWorkspace(currentClientId);
        const nextActiveJobs = (nextWorkspace?.knowledgeStatus?.pendingJobs || 0) + (nextWorkspace?.knowledgeStatus?.runningJobs || 0);
        if (importedCount === 0 && nextActiveJobs === 0) {
          setIsImportSubmitting(false);
        } else if (nextActiveJobs === 0) {
          window.setTimeout(() => {
            if (Date.now() >= importProgressHoldUntilRef.current) {
              setIsImportSubmitting(false);
            }
          }, 1600);
        }
        if (importedCount === 0) {
          const text = skippedCount > 0 ? `没有发现新增资料，本次跳过 ${skippedCount} 个已入库或不支持的文件。` : '没有发现可导入的新资料。';
          setLatestImportFeedback({
            tone: 'info',
            text,
            detail: mode === 'folder'
              ? '如果这是同一个资料文件夹，系统会自动跳过已经入库的文件，不会重复建库。'
              : '当前选中的文件可能已经入库，或不是系统支持的资料格式。',
            timestamp: Date.now(),
          });
          flash('info', text);
        } else if (queuedImports > 0) {
          setLatestImportFeedback({
            tone: 'success',
            text: mode === 'folder' ? `已接收 ${importedCount} 个新文件，后台正在分析归档并建库。` : `已接收 ${importedCount} 个新文件，后台正在处理。`,
            detail: '你可以留在当前页面观察建库进度，也可以切到工作台继续其他操作。',
            timestamp: Date.now(),
          });
          flash('success', mode === 'folder' ? `已入队 ${importedCount} 个新文件，后台正在分析归档并建库` : `已入队 ${importedCount} 个文件，后台正在处理`);
        } else {
          setLatestImportFeedback({
            tone: 'success',
            text: `已完成 ${importedCount} 个文件的导入处理。`,
            detail: `资料已经进入当前${terminology.singularLabel}的${terminology.workspaceLabel}与知识库。`,
            timestamp: Date.now(),
          });
          flash('success', `已完成 ${importedCount} 个文件的导入处理`);
        }
      } catch (error) {
        setIsImportSubmitting(false);
        setLatestImportFeedback({
          tone: 'error',
          text: error instanceof Error ? error.message : '导入失败',
          detail: '本次导入没有成功进入后台处理链，请稍后重试。',
          timestamp: Date.now(),
        });
        flash('error', error instanceof Error ? error.message : '导入失败');
      }
    };

    useEffect(() => {
      clearWorkspaceFileSearch();
    }, [currentClientId]);

    const fillTemplateFromPath = async (
      templatePath: string,
      options?: { showDialog?: boolean; allowFallbackImport?: boolean },
    ) => {
      if (!currentClientId) {
        flash('error', `请先选择${terminology.singularLabel}`);
        return 'error' as const;
      }
      if (backendCompatibilityError) {
        flash('error', backendCompatibilityError);
        return 'error' as const;
      }
      const shouldShowDialog = options?.showDialog !== false;
      if (shouldShowDialog) {
        setTemplateFillDialog({
          ...buildTemplateFillDialogInitialState(templatePath),
          allowFallbackImport: options?.allowFallbackImport === true,
        });
      }
      try {
        setIsTemplateFilling(true);
        const run = await startClientTemplateFill(currentClientId, templatePath);
        if (shouldShowDialog) {
          setTemplateFillDialog((previous) =>
            buildTemplateFillDialogFromRun(run, previous || {
              ...buildTemplateFillDialogInitialState(templatePath),
              allowFallbackImport: options?.allowFallbackImport === true,
            }),
          );
        }
        return 'started' as const;
      } catch (error) {
        const detail = error instanceof Error ? error.message : '模板填写失败';
        if (shouldShowDialog) {
          setTemplateFillDialog((previous) => ({
            ...(previous || buildTemplateFillDialogInitialState(templatePath)),
            open: true,
            stage: 'failed',
            percent: Math.max(8, Math.min(previous?.percent || 8, 96)),
            statusLabel: '模板填写失败',
            hint: '这次自动填写没有成功完成，可以关闭后重试。',
            errorMessage: detail,
          }));
        }
        flash('error', detail);
        setIsTemplateFilling(false);
        return 'error' as const;
      }
    };

    const handleFillTemplate = async () => {
      if (!currentClientId) {
        flash('error', `请先选择${terminology.singularLabel}`);
        return;
      }
      if (backendCompatibilityError) {
        flash('error', backendCompatibilityError);
        return;
      }
      try {
        const paths = await selectFilesBridge();
        const templatePath = paths.find((item) => /\.docx$/i.test(item));
        if (!templatePath) {
          flash('error', '当前自动填写 MVP 只支持选择一个 .docx 模板。');
          return;
        }
        await fillTemplateFromPath(templatePath, { showDialog: true });
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '打开模板失败');
      }
    };

    const openClientTextDocumentOverlay = () => {
      if (!currentClientId) {
        flash('error', `请先选择${terminology.singularLabel}`);
        return;
      }
      setClientTextDocumentDraft({
        title: '',
        content: '',
        titleEdited: false,
      });
      setClientOverlayMode('paste_document');
    };

    const handleClientTextDocumentContentChange = (value: string) => {
      setClientTextDocumentDraft((prev) => {
        const nextTitle =
          !prev.titleEdited || !prev.title.trim() ? inferClientTextDocumentTitle(value) : prev.title;
        return {
          ...prev,
          content: value,
          title: nextTitle,
        };
      });
    };

    const handleCreateClientTextDocument = async () => {
      if (!currentClientId) {
        flash('error', `请先选择${terminology.singularLabel}`);
        return;
      }
      const content = clientTextDocumentDraft.content.trim();
      if (!content) {
        flash('error', '请先粘贴文档内容');
        return;
      }
      try {
        setIsCreatingClientTextDocument(true);
        const result = await createClientTextDocument(currentClientId, {
          title: clientTextDocumentDraft.title.trim(),
          content,
        });
        await refreshWorkspace(currentClientId);
        setClientOverlayMode(null);
        setClientTextDocumentDraft({
          title: '',
          content: '',
          titleEdited: false,
        });
        flash('success', `已生成《${result.title}》并加入当前${terminology.singularLabel}文档库`);
        void openPathBridge(result.path).catch(() => undefined);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '生成 Word 失败');
      } finally {
        setIsCreatingClientTextDocument(false);
      }
    };

    const handleDroppedClientFiles = async (paths: string[]) => {
      if (!paths.length) {
        flash('error', '没有识别到可导入文件。');
        return;
      }
      if (paths.length === 1 && /\.docx$/i.test(paths[0] || '')) {
        const handled = await fillTemplateFromPath(paths[0], { showDialog: true, allowFallbackImport: true });
        if (handled === 'started' || handled === 'error') return;
      }
      await handleImport('file', paths);
    };

    const resetClientImportDropZone = (zone?: 'buffer' | 'composer') => {
      if (zone) {
        clientImportDropDepthRef.current[zone] = 0;
        setClientImportDropZone((prev) => (prev === zone ? null : prev));
        return;
      }
      clientImportDropDepthRef.current.buffer = 0;
      clientImportDropDepthRef.current.composer = 0;
      setClientImportDropZone(null);
    };

    const handleClientImportDragEnter =
      (zone: 'buffer' | 'composer') => (event: React.DragEvent<HTMLDivElement>) => {
        if (!currentClientId || isBackendBlocked || !hasFileDragData(event.dataTransfer)) return;
        event.preventDefault();
        event.stopPropagation();
        clientImportDropDepthRef.current[zone] += 1;
        setClientImportDropZone(zone);
      };

    const handleClientImportDragOver =
      (zone: 'buffer' | 'composer') => (event: React.DragEvent<HTMLDivElement>) => {
        if (!currentClientId || isBackendBlocked || !hasFileDragData(event.dataTransfer)) return;
        event.preventDefault();
        event.stopPropagation();
        event.dataTransfer.dropEffect = 'copy';
        if (clientImportDropZone !== zone) {
          setClientImportDropZone(zone);
        }
      };

    const handleClientImportDragLeave =
      (zone: 'buffer' | 'composer') => (event: React.DragEvent<HTMLDivElement>) => {
        if (!hasFileDragData(event.dataTransfer)) return;
        event.preventDefault();
        event.stopPropagation();
        clientImportDropDepthRef.current[zone] = Math.max(0, clientImportDropDepthRef.current[zone] - 1);
        if (clientImportDropDepthRef.current[zone] === 0 && clientImportDropZone === zone) {
          setClientImportDropZone(null);
        }
      };

    const handleClientImportDrop =
      (zone: 'buffer' | 'composer') => (event: React.DragEvent<HTMLDivElement>) => {
        if (!currentClientId || isBackendBlocked || !hasFileDragData(event.dataTransfer)) return;
        event.preventDefault();
        event.stopPropagation();
        resetClientImportDropZone(zone);
        const droppedPaths = extractDroppedFilePaths(event.dataTransfer);
        if (droppedDataContainsDirectory(event.dataTransfer)) {
          const inferredDirectoryPath = inferDroppedDirectoryPath(droppedPaths);
          if (inferredDirectoryPath) {
            void handleImport('folder', [inferredDirectoryPath]);
            return;
          }
          flash('info', '已识别到目录拖拽，但系统没有拿到稳定路径。接下来会打开系统目录选择器，请再确认一次文件夹。');
          void handleSelectImportFolder();
          return;
        }
        void handleDroppedClientFiles(droppedPaths);
      };

    const handleSelectImportFiles = async () => {
      try {
        const paths = await selectFilesBridge();
        await handleImport('file', paths);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '选择文件失败');
      }
    };

    const handleSelectImportFolder = async () => {
      try {
        const folder = await selectFolderBridge();
        await handleImport('folder', folder ? [folder] : []);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '选择文件夹失败');
      }
    };

    const sendMessage = async (overridePrompt?: string) => {
      const resolvedPrompt = (overridePrompt ?? inputValue).trim();
      if (!resolvedPrompt || !currentClientId || hasPendingAnalysisRun || isStartingMessage) return;
      if (backendCompatibilityError) {
        flash('error', backendCompatibilityError);
        return;
      }
      const prompt = resolvedPrompt;
      const createdAt = new Date().toISOString();
      const draftThreadId = currentThreadId || CLIENT_CHAT_DRAFT_THREAD_ID;
      const tempUserId = `temp_user_${Date.now()}`;
      const userMessage: DisplayChatMessage = {
        id: tempUserId,
        threadId: draftThreadId,
        role: 'user',
        content: prompt,
        createdAt,
        status: 'success',
        evidence: [],
      };
      flushSync(() => {
        setOptimisticMessages([userMessage]);
        setInputValue('');
        setActiveMessageId(null);
        setActiveAnalysisRun(null);
        setIsStartingMessage(true);
        setPendingQuestion(prompt);
        setPendingStartedAt(createdAt);
      });
      await new Promise<void>((resolve) => {
        window.requestAnimationFrame(() => {
          // Force scroll to bottom so thinking panel is visible immediately
          const container = chatContainerRef.current;
          if (container) {
            container.scrollTop = container.scrollHeight;
          }
          window.setTimeout(resolve, 32);
        });
      });

      try {
        const controller = new AbortController();
        startMessageAbortControllerRef.current = controller;
        const started = await startClientMessage(currentClientId, prompt, currentThreadId, undefined, { signal: controller.signal });
        upsertAnalysisRun(started.analysisRun);
        flushSync(() => {
          upsertWorkspaceMessages([started.userMessage as DisplayChatMessage, started.assistantMessage as DisplayChatMessage], started.threadId);
          setOptimisticMessages([]);
          setActiveMessageId(started.assistantMessage.id);
          setActiveAnalysisRun(started.analysisRun);
          setIsStartingMessage(false);
        });
        window.requestAnimationFrame(() => {
          const container = chatContainerRef.current;
          if (container) container.scrollTop = container.scrollHeight;
        });
        startMessageAbortControllerRef.current = null;
        beginAnalysisRunPolling(started.analysisRun.id, currentClientId);
      } catch (error) {
        clearAnalysisRunPollTimer();
        startMessageAbortControllerRef.current = null;
        if (error instanceof DOMException && error.name === 'AbortError') {
          setIsStartingMessage(false);
          setPendingQuestion('');
          setPendingStartedAt('');
          setOptimisticMessages([]);
          setInputValue(prompt);
          flash('info', '已停止发送，问题草稿已保留');
          return;
        }
        const detail = error instanceof Error ? error.message : '发送失败';
        setIsStartingMessage(false);
        setPendingQuestion('');
        setPendingStartedAt('');
        setOptimisticMessages([
          userMessage,
          {
            id: `temp_error_${Date.now()}`,
            threadId: draftThreadId,
            role: 'assistant',
            createdAt: new Date(Date.now() + 1).toISOString(),
            status: 'success',
            content: '庆华暂时没能完成这次回答。',
            modelRoute: '发送失败',
            answerMode: 'system_failure',
            evidenceStatus: 'none',
            failureReason: detail,
            evidence: [],
            llmInvoked: false,
            providerUsed: null,
            requestPrompt: prompt,
            retrievalSummary: {
              phase: 'failed',
              progress: 100,
              progressFloor: 100,
              progressCeiling: 100,
              stageLabel: '问题提交失败',
              startedAt: createdAt,
              lastUpdatedAt: createdAt,
            },
            structuredData: {
              content: '庆华暂时没能完成这次回答。',
              judgment: '当前请求发送失败，尚未生成正式回答。',
              analysis: detail,
              actions: '请稍后重试；如果持续失败，请检查本地后端是否为最新版本。',
              timeline: '修复后可立即重试。',
            },
          },
        ]);
        flash('error', detail);
      }
    };

    const handleStopMessage = async () => {
      if (isStartingMessage) {
        startMessageAbortControllerRef.current?.abort();
        return;
      }
      if (!currentClientId || !activeAnalysisRun || !hasPendingAnalysisRun) return;
      try {
        clearAnalysisRunPollTimer();
        const canceledRun = await cancelClientAnalysisRun(currentClientId, activeAnalysisRun.id);
        flushSync(() => {
          setOptimisticMessages([]);
          if (canceledRun.assistantMessage) {
            upsertWorkspaceMessages([canceledRun.assistantMessage], canceledRun.threadId);
            setActiveMessageId(canceledRun.assistantMessage.id);
          }
          setActiveAnalysisRun(null);
          setPendingQuestion('');
          setPendingStartedAt('');
          setWorkspace((prev) => {
            if (!prev) return prev;
            const nextRuns = [canceledRun, ...(prev.analysisRuns || []).filter((item) => item.id !== canceledRun.id)].sort((left, right) =>
              right.updatedAt.localeCompare(left.updatedAt),
            );
            return {
              ...prev,
              analysisRuns: nextRuns,
            };
          });
        });
        flash('info', '已停止当前回答');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '停止失败');
      }
    };

    const handleComposerKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        void sendMessage();
      }
    };

    const syncMeetingFromPipeline = async (
      pipelineAction: () => Promise<{ meeting: { id: string; stage: string; transcriptText: string; notes: string }; message: string }>,
      options?: { refreshTasks?: boolean; verifyPublished?: boolean },
    ) => {
      if (!currentClientId) return;
      const result = await pipelineAction();
      setWorkspaceSelectedMeetingId(result.meeting.id);
      setWorkspaceMeetingTranscript(result.meeting.transcriptText || '');
      setWorkspaceMeetingNotes(result.meeting.notes || '');
      const [nextWorkspace, nextTaskBoard] = await Promise.all([
        refreshWorkspace(currentClientId),
        options?.refreshTasks ? loadTaskBlock() : Promise.resolve(undefined),
      ]);
      if (options?.verifyPublished) {
        const publishedMeeting = nextWorkspace?.meetings.find((meeting) => meeting.id === result.meeting.id);
        const inboxTaskExists = nextTaskBoard?.tasks.some((task) => task.sourceId === result.meeting.id && task.status === 'inbox');
        if (publishedMeeting?.stage !== 'published' || !inboxTaskExists) {
          throw new Error('会议发布未完成，行动项尚未进入任务收件箱');
        }
      }
      flash('success', result.message);
    };

    const handleVectorizeAnswer = async (messageId: string) => {
      if (!currentClientId || answerActionState[messageId]) return;
      try {
        setAnswerActionState((prev) => ({ ...prev, [messageId]: 'vectorize' }));
        const result = await vectorizeAnswer(currentClientId, messageId);
        await refreshWorkspace(currentClientId);
        const opened = await openPathBridge(result.path).catch(() => false);
        flash('success', opened ? `已生成并打开机读文档：${result.fileName}` : `已生成机读文档，并已归档到当前${terminology.singularLabel}：${result.fileName}`);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '建立向量失败');
      } finally {
        setAnswerActionState((prev) => {
          const next = { ...prev };
          delete next[messageId];
          return next;
        });
      }
    };

    const handleExportAnswer = async (messageId: string) => {
      if (!currentClientId || answerActionState[messageId]) return;
      try {
        setAnswerActionState((prev) => ({ ...prev, [messageId]: 'export' }));
        const result = await exportAnswer(currentClientId, messageId);
        await refreshWorkspace(currentClientId);
        const opened = await openPathBridge(result.path).catch(() => false);
        flash('success', opened ? `已生成、归档并打开 Word 文件：${result.fileName}` : `已生成并归档 Word 文件：${result.fileName}`);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '导出文件失败');
      } finally {
        setAnswerActionState((prev) => {
          const next = { ...prev };
          delete next[messageId];
          return next;
        });
      }
    };

    return (
      <div className="h-full bg-[#F9FAFB] overflow-x-auto overflow-y-hidden">
        <div className="flex h-full min-w-[850px]">
          <div className="w-[220px] xl:w-[260px] bg-white border-r border-gray-100 flex flex-col h-full z-10 shrink-0 shadow-[2px_0_10px_rgba(0,0,0,0.02)]">
            <div className="p-5 xl:p-6 border-b border-gray-50">
              <div className="mb-4 flex items-center gap-2">
                <div className="relative group flex-1">
                  <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400 group-focus-within:text-[#5B7BFE] transition-colors" />
                  <input
                    type="text"
                    placeholder={`搜索${terminology.singularLabel}...`}
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                    className="w-full bg-gray-50/80 border border-gray-100 rounded-full pl-10 pr-4 py-2 text-[13px] font-medium outline-none focus:bg-white focus:border-[#5B7BFE] focus:ring-4 focus:ring-blue-500/10 transition-all placeholder-gray-400"
                  />
                </div>
                <Button
                  className="h-11 w-11 shrink-0 rounded-[16px] p-0 border border-[#E5E5EA] bg-[#F2F2F7] text-[#6B7280] shadow-[0_1px_2px_rgba(0,0,0,0.05)] hover:bg-[#E9E9EE] hover:border-[#D1D5DB] hover:text-[#4B5563]"
                  onClick={() => openCreateClientModal()}
                  aria-label={`创建${terminology.singularLabel}`}
                  title={`创建${terminology.singularLabel}`}
                >
                  <Plus size={20} strokeWidth={2.4} />
                </Button>
              </div>

              <div>
                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">{terminology.recentLabel}</p>
                <div className="space-y-1.5">
                  {filteredClients.map((client) => (
                    <div
                      key={client.id}
                      className={`w-full px-2 py-1 rounded-2xl transition-all duration-200 flex items-center gap-1.5 group ${
                        currentClientId === client.id ? 'bg-blue-50/80 shadow-[inset_0_1px_3px_rgba(91,123,254,0.05)]' : 'hover:bg-gray-50'
                      }`}
                    >
                      <button
                        onClick={() => {
                          setCurrentClientId(client.id);
                          void refreshWorkspace(client.id);
                          setActiveMessageId(null);
                        }}
                        onDoubleClick={() => openEditClientModal(client)}
                        className={`flex-1 text-left px-3 xl:px-4 py-2.5 rounded-2xl text-[13px] font-bold transition-all duration-200 flex items-center justify-between ${
                          currentClientId === client.id ? 'text-[#5B7BFE]' : 'text-gray-600'
                        }`}
                      >
                        <span className="truncate pr-2">{client.name}</span>
                        {currentClientId === client.id && <CheckCircle2 size={16} className="text-[#5B7BFE] shrink-0 opacity-80" />}
                      </button>
                      <button
                        onClick={() => openEditClientModal(client)}
                        className="shrink-0 rounded-xl px-2 py-2 text-[11px] font-bold text-gray-400 hover:text-[#5B7BFE] hover:bg-white transition-colors"
                        title={`编辑${terminology.singularLabel}：${client.name}`}
                      >
                        <PenTool size={14} />
                      </button>
                    </div>
                  ))}
                  {filteredClients.length === 0 && (
                    <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50/70 px-4 py-4 text-center">
                      <p className="text-[12px] font-semibold text-gray-500">没有找到匹配的{terminology.singularLabel}</p>
                      <button
                        onClick={() => {
                          setSearchQuery('');
                          openCreateClientModal();
                        }}
                        className="mt-2 text-[12px] font-bold text-[#5B7BFE] hover:text-[#4a6be6]"
                      >
                        清空搜索并创建{terminology.singularLabel}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="p-5 xl:p-6 flex-1 overflow-y-auto">
              <div className="flex items-center justify-between mb-3">
                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
                  <FolderOpen size={12} />
                  根目录快捷通道
                </p>
                {isWorkspaceFileSearchMode ? (
                  <button
                    type="button"
                    onClick={clearWorkspaceFileSearch}
                    className="rounded-full px-2.5 py-1 text-[9px] font-bold tracking-wider border border-gray-200 bg-gray-100 text-gray-500 hover:border-[#5B7BFE] hover:text-[#5B7BFE] transition-colors"
                  >
                    清空搜索
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setIsFolderEditMode((prev) => !prev)}
                    className={`group rounded-full px-2.5 py-1 text-[9px] font-bold tracking-wider transition-all duration-300 ${
                      isFolderEditMode
                        ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow-[0_8px_18px_rgba(16,185,129,0.25)] hover:from-emerald-600 hover:to-teal-600'
                        : 'border border-gray-200 bg-gray-100 text-gray-500 shadow-none hover:border-[#5B7BFE] hover:bg-gradient-to-r hover:from-[#5B7BFE] hover:to-sky-500 hover:text-white hover:shadow-[0_8px_20px_rgba(91,123,254,0.24)]'
                    }`}
                  >
                    {isFolderEditMode ? '完成' : (
                      <>
                        <span className="group-hover:hidden">{knowledgeStatus?.totalDocuments || workspace?.documents.length || 0} 文件</span>
                        <span className="hidden group-hover:inline">编辑</span>
                      </>
                    )}
                  </button>
                )}
              </div>
              <div className="mb-3 flex items-center gap-2">
                <div className="relative flex-1">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    value={workspaceFileSearchQuery}
                    onChange={(event) => setWorkspaceFileSearchQuery(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault();
                        void runWorkspaceFileSearch();
                      }
                    }}
                    placeholder="搜索文件"
                    className="w-full rounded-2xl border border-gray-200 bg-white pl-9 pr-10 py-2 text-[12px] font-medium text-gray-700 outline-none transition-all focus:border-[#5B7BFE] focus:ring-4 focus:ring-blue-500/10"
                  />
                  {workspaceFileSearchQuery && (
                    <button
                      type="button"
                      onClick={clearWorkspaceFileSearch}
                      className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
                      aria-label="清空文件搜索"
                    >
                      <X size={13} />
                    </button>
                  )}
                </div>
                <Button
                  className="h-9 shrink-0 rounded-[14px] px-3 border border-[#E5E5EA] bg-white text-[#5B7BFE] shadow-none hover:bg-blue-50"
                  onClick={() => void runWorkspaceFileSearch()}
                  disabled={isWorkspaceFileSearching}
                >
                  {isWorkspaceFileSearching ? '搜索中' : '搜索'}
                </Button>
              </div>
              {isWorkspaceFileSearchMode && (
                <div className="mb-3 text-[11px] text-gray-400">
                  {workspaceFileSearchSubmittedQuery
                    ? `按相关度显示"${workspaceFileSearchSubmittedQuery}"的文件结果 · 共 ${aggregatedWorkspaceFileHits.length} 项`
                    : '输入关键词后回车或点击搜索'}
                </div>
              )}
              <div className="grid grid-cols-1 gap-2.5">
                {isWorkspaceFileSearchMode ? (
                  aggregatedWorkspaceFileHits.length > 0 ? (
                    aggregatedWorkspaceFileHits.map((hit, index) => (
                      <button
                        type="button"
                        key={hit.key}
                        onClick={() =>
                          hit.path
                            ? void openPathBridge(hit.path).then((opened) => {
                                if (!opened) flash('error', '文件不存在或暂时无法打开');
                              })
                            : undefined
                        }
                        className="bg-white border border-gray-100 p-2.5 xl:p-3 rounded-2xl shadow-sm hover:shadow-md hover:border-blue-200 transition-all duration-300 text-left"
                      >
                        <div className="flex items-start gap-3">
                          <div className="w-7 h-7 rounded-xl bg-blue-50/50 flex items-center justify-center shrink-0 text-[11px] font-bold text-[#5B7BFE]">
                            {index + 1}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="text-[12px] xl:text-[13px] font-bold text-gray-700 truncate">{hit.title}</div>
                            <div className="mt-1 text-[11px] text-gray-500 line-clamp-3">{hit.excerpt}</div>
                            <div className="mt-2 flex items-center justify-between gap-2">
                              <div className="flex flex-wrap gap-1.5">
                                {hit.matchedTerms.slice(0, 4).map((term) => (
                                  <span key={`${hit.key}-${term}`} className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-[#5B7BFE]">
                                    {term}
                                  </span>
                                ))}
                              </div>
                              <span className="shrink-0 text-[10px] font-bold text-gray-400">
                                相关度 {Math.round(hit.score)}
                              </span>
                            </div>
                          </div>
                        </div>
                      </button>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50/70 px-4 py-4 text-center text-[12px] text-gray-500">
                      没有找到匹配的文件，请换一个关键词试试。
                    </div>
                  )
                ) : (
                  <>
                    {(workspace?.folders || []).map((folder) => (
                      <div
                        key={folder.id}
                        className="bg-white border border-gray-100 p-2.5 xl:p-3 rounded-2xl shadow-sm hover:shadow-md hover:border-blue-200 transition-all duration-300 flex items-center gap-3 group text-left"
                      >
                        <button
                          type="button"
                          onClick={() =>
                            void openPathBridge(folder.path).then((opened) => {
                              if (!opened) flash('error', '目录不存在或暂时无法打开');
                            })
                          }
                          className="flex flex-1 items-center gap-3 min-w-0"
                        >
                          <div className="w-8 h-8 rounded-xl bg-blue-50/50 flex items-center justify-center shrink-0 group-hover:bg-blue-100 transition-colors">
                            <FolderDot size={16} className="text-[#5B7BFE]" />
                          </div>
                          <span className="text-[12px] xl:text-[13px] font-bold text-gray-700 truncate group-hover:text-[#5B7BFE] transition-colors">{folder.label}</span>
                        </button>
                        {isFolderEditMode && (
                          <button
                            type="button"
                            onClick={() => void handleDeleteClientFolder(folder)}
                            className="shrink-0 rounded-xl p-2 text-red-400 hover:bg-red-50 hover:text-red-500 transition-colors"
                            title={`移除 ${folder.label}`}
                          >
                            <Minus size={14} />
                          </button>
                        )}
                      </div>
                    ))}
                    {workspace?.folders.length === 0 && <div className="text-[12px] text-gray-400 py-2">还没有绑定任何{terminology.singularLabel}目录。</div>}
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="flex-1 flex flex-col min-w-[320px] relative">
            <div className="h-[68px] bg-white/80 backdrop-blur-md border-b border-gray-100 px-6 xl:px-8 flex items-center justify-between shrink-0 z-10 sticky top-0">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-gradient-to-tr from-gray-800 to-gray-600 rounded-xl flex items-center justify-center text-white shadow-sm shrink-0">
                  <Briefcase size={16} strokeWidth={2.5} />
                </div>
                <div className="min-w-0">
                  <h2 className="text-[16px] xl:text-[18px] font-bold text-gray-900 truncate">{currentClient?.name || `未选择${terminology.singularLabel}`}</h2>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <div className="hidden lg:flex gap-2">
                  {currentClient ? (
                    <button
                      onClick={() =>
                        void openExpenseEvidenceModal({
                          workObjectId: currentClient.id,
                          workObjectName: currentClient.name,
                        })
                      }
                      className="flex items-center gap-2 text-[12px] font-bold px-3 py-1.5 rounded-xl border border-amber-200 bg-amber-50 text-amber-700 shadow-sm transition-all duration-300 cursor-pointer select-none hover:bg-amber-100 active:scale-95"
                      title="打开当前工作对象的票据证明池"
                    >
                      <FileBadge size={14} />
                      票据证明
                    </button>
                  ) : null}
                  <button
                    onClick={() => setClientOverlayMode('dna')}
                    className={`flex items-center gap-2 text-[12px] font-bold px-3 py-1.5 rounded-xl border shadow-sm transition-all duration-300 cursor-pointer select-none active:scale-95 ${clientDnaStatus.className}`}
                    title={clientDnaReady ? 'DNA 已上传并启用' : 'DNA 尚未上传'}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${clientDnaStatus.dotClassName}`} />
                    <Target size={14} />
                    {clientDnaDisplayLabel}
                  </button>
                </div>
                <button
                  onClick={() => setActiveTab('settings')}
                  className={`flex items-center gap-2 text-[11px] xl:text-[12px] font-bold px-3 py-1.5 rounded-xl border shadow-sm transition-all duration-300 cursor-pointer select-none active:scale-95 ${aiStatus.className}`}
                  title={health?.ai.detail || aiStatus.subtitle}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${aiStatus.dotClassName}`} />
                  {aiStatus.label}
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6 xl:p-8 space-y-8" ref={chatContainerRef}>
              {!currentClient ? (
                <div className="h-full flex flex-col items-center justify-center text-gray-400">
                  <div className="w-16 h-16 xl:w-20 xl:h-20 bg-blue-50 rounded-full flex items-center justify-center mb-5">
                    <Briefcase size={30} className="text-[#5B7BFE]" strokeWidth={2} />
                  </div>
                  <p className="text-[16px] font-bold text-gray-800 mb-2">还没有{terminology.workspaceLabel}</p>
                  <p className="text-[12px] text-center max-w-md leading-relaxed text-gray-500 mb-6">
                    先创建一个{terminology.singularLabel}开始正式使用；如果只是想演示流程，也可以手动载入演示数据。
                  </p>
                  <div className="flex items-center gap-3">
                    <Button primary onClick={() => openCreateClientModal()}>
                      <Plus size={16} />
                      创建{terminology.singularLabel}
                    </Button>
                    <Button
                      onClick={() =>
                        void loadDemoData()
                          .then(async () => {
                            await loadAll('client_cffc');
                            flash('success', '演示数据已载入，可用于首次演示');
                          })
                          .catch((error) => flash('error', error instanceof Error ? error.message : '载入演示数据失败'))
                      }
                    >
                      <Sparkles size={16} />
                      载入演示数据
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  {backendCompatibilityError && (
                    <div className="rounded-3xl border border-rose-200 bg-rose-50 px-5 py-4 text-[13px] text-rose-700 shadow-sm">
                      <p className="font-bold">本地后端版本过旧</p>
                      <p className="mt-1 leading-relaxed">{backendCompatibilityError}</p>
                    </div>
                  )}
                  {clientWorkspaceSurfaceMode === 'setup' && (
                    <ClientProjectSetupPage
                      clientName={currentClient?.name || `当前${terminology.singularLabel}`}
                      workObjectLabel={terminology.singularLabel}
                      workspaceLabel={terminology.workspaceLabel}
                      modules={workspace?.dnaModules || []}
                      projectModules={workspace?.projectModules || []}
                      projectFlows={workspace?.projectFlows || []}
                      moduleMetas={CLIENT_DNA_MODULES}
                      sourceDocumentCount={sourceDocumentCount}
                      isKnowledgeBuilding={Boolean((knowledgeStatus?.pendingJobs || 0) + (knowledgeStatus?.runningJobs || 0))}
                      knowledgeStatus={knowledgeStatus}
                      latestKnowledgeJob={latestKnowledgeJob}
                      isImportSubmitting={isImportSubmitting}
                      isTemplateFilling={isTemplateFilling}
                      latestImportFeedback={latestImportFeedback}
                      onImportFiles={() => {
                        void handleSelectImportFiles();
                      }}
                      onImportFolder={() => {
                        void handleSelectImportFolder();
                      }}
                      onGenerateCandidates={() => {
                        void handleGenerateClientDnaCandidates();
                      }}
                      onCopyModulePrompt={(moduleKey) => {
                        void handleCopyClientDnaPrompt(moduleKey);
                      }}
                      onUploadModule={(moduleKey) => {
                        void handleUploadClientDna(moduleKey);
                      }}
                      onCreateProjectModule={(payload) => {
                        void handleCreateProjectModule(payload);
                      }}
                      onCreateProjectFlow={(payload) => {
                        void handleCreateProjectFlow(payload);
                      }}
                      onOpenExpenseEvidence={() => {
                        if (!currentClient) return;
                        void openExpenseEvidenceModal({
                          workObjectId: currentClient.id,
                          workObjectName: currentClient.name,
                        });
                      }}
                      onOpenDnaPanel={() => setClientOverlayMode('dna')}
                      onContinueWorkspace={() => setClientWorkspaceSurfaceMode('workspace')}
                    />
                  )}
                  <div className={`space-y-4 ${clientWorkspaceSurfaceMode === 'setup' ? 'hidden' : ''}`}>
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-[13px] xl:text-[14px] font-bold text-gray-900 flex items-center gap-2">
                          <Database size={16} className="text-[#5B7BFE]" />
                          扫描目录与文件卡
                        </h3>
                        <p className="text-[11px] text-gray-400 mt-1">先理解资料，再进入深读问答与行动沉淀。</p>
                      </div>
                      <span className="text-[11px] font-bold text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full">
                        {knowledgeStatus?.totalDocuments || 0} 份资料
                      </span>
                    </div>
                    {topDocumentCards.length > 0 ? (
                      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                        {topDocumentCards.map((card) => (
                          <div key={card.id} className="bg-white border border-gray-200 rounded-2xl p-4 shadow-sm">
                            <div className="flex items-start justify-between gap-3 mb-2">
                              <div>
                                <p className="text-[13px] font-bold text-gray-900 leading-snug">{card.title}</p>
                                <p className="text-[11px] text-gray-400 mt-1">{card.primaryCategory} · {card.secondaryCategory}</p>
                              </div>
                              <span className={`text-[10px] font-bold px-2 py-1 rounded-full ${card.needsReview ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'}`}>
                                {card.needsReview ? '待复核' : '已归档'}
                              </span>
                            </div>
                            <p className="text-[12px] text-gray-600 leading-relaxed">{card.shortSummary}</p>
                            <div className="mt-2 space-y-1 text-[10px] text-gray-400">
                              <p>原始路径：{card.sourcePath}</p>
                              <p>逻辑分类：{card.logicalCategory || card.primaryCategory}{card.logicalSubcategory ? ` / ${card.logicalSubcategory}` : ''}</p>
                              {card.classificationReason && <p>分类依据：{card.classificationReason}</p>}
                              <p>AI 代理：{card.surrogateMdPath ? '已生成' : '待生成'} · {card.documentRole}</p>
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {card.tags.slice(0, 3).map((tag) => (
                                <span key={`${card.id}-${tag}`} className="text-[10px] font-bold text-[#5B7BFE] bg-blue-50 px-2 py-1 rounded-full">
                                  {tag}
                                </span>
                              ))}
                            </div>
                            <div className="mt-3 flex items-center justify-between text-[10px] text-gray-400">
                              <span>向量状态：{card.vectorStatus}</span>
                              <span>块数：{card.chunkCount}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="bg-white border border-dashed border-gray-200 rounded-2xl px-4 py-8 text-[12px] text-gray-400 text-center">
                        <p>还没有生成文件卡。先导入{terminology.singularLabel}资料，系统会自动扫描目录、生成文件卡和知识状态。</p>
                        {currentClientId && (
                          <div className="mt-4">
                            <button
                              onClick={() => void handleBackfillWorkspaceImports()}
                              className="inline-flex items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-[12px] font-bold text-[#3652c9] transition-colors hover:bg-blue-100"
                            >
                              <RefreshCw size={14} />
                              回填现有目录
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {clientWorkspaceSurfaceMode === 'setup' ? null : currentChat.length === 0 && !activeAnalysisRun && !transientThinkingPanel ? (
                    <div className="pt-2 h-full flex flex-col items-center justify-center text-gray-400">
                      <div className="w-16 h-16 xl:w-20 xl:h-20 bg-blue-50 rounded-full flex items-center justify-center mb-5">
                        <Bot size={32} className="text-[#5B7BFE]" strokeWidth={2} />
                      </div>
                      <p className="text-[15px] xl:text-[16px] font-bold text-gray-800 mb-2">已为您加载 {currentClient?.name || `当前${terminology.singularLabel}`} 的业务大脑</p>
                      <p className="text-[12px] xl:text-[13px] text-center max-w-sm xl:max-w-md leading-relaxed text-gray-500">
                        {health?.ai.provider && health.ai.provider !== 'mock' && health.ai.ready
                          ? `本次对话已连接到 ${providerDisplayNames[health.ai.provider]} 结构化问答引擎。`
                          : '本次对话当前运行在本地 mock 模式，可稳定验证流程与数据链路。'}
                      </p>
                    </div>
                  ) : (
                    <>
                      {currentChat.map((msg) => (
                      <div key={msg.id} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`} onClick={() => msg.role === 'assistant' && setActiveMessageId(msg.id)}>
                        {msg.role === 'user' && (
                          <div className="bg-[#5B7BFE] text-white px-4 py-3 xl:px-5 xl:py-3.5 rounded-[20px] rounded-tr-sm max-w-[85%] text-[13px] xl:text-[14px] font-medium leading-relaxed shadow-[0_4px_12px_rgba(91,123,254,0.25)]">
                            {msg.content}
                          </div>
                        )}

                        {msg.role === 'assistant' && (
                          <div className={`bg-white border rounded-[24px] rounded-tl-sm max-w-[98%] xl:max-w-[95%] overflow-hidden transition-all duration-300 shadow-sm ${activeMessageId === msg.id ? 'border-[#5B7BFE] ring-4 ring-blue-500/10 shadow-[0_8px_24px_rgba(91,123,254,0.12)]' : 'border-gray-200 hover:border-blue-200'}`}>
                              <div>
                                <div className="bg-gray-50/80 border-b border-gray-100 px-4 xl:px-5 py-3 flex items-center justify-between">
                                  <span className="flex items-center gap-1.5 text-[10px] xl:text-[11px] font-bold text-gray-500 uppercase tracking-widest">
                                    <Zap size={14} className="text-amber-500" /> {msg.llmInvoked ? msg.modelRoute || `AI · ${msg.providerUsed || health?.ai.model || 'qwen'}` : '背景整理'}
                                  </span>
                                  <span className="text-[10px] xl:text-[11px] text-gray-400 font-medium">
                                    {msg.timing?.totalMs ? `耗时 ${formatElapsedLabel(msg.timing.totalMs)}` : '点击激活右侧证据线索'}
                                  </span>
                                </div>

                                <div className="p-4 xl:p-6 space-y-5 xl:space-y-6">
                                  {msg.answerMode === 'general_answer' &&
                                    msg.failureReason === 'no_relevant_materials' &&
                                    ((knowledgeStatus?.totalDocuments || workspace?.documents.length || currentClient?.documentCount || 0) > 0) && (
                                      <div className="rounded-2xl border border-amber-100 bg-amber-50/80 px-4 py-3 text-[12px] font-bold text-amber-700">
                                        这是一条历史结果：生成当时该{terminology.singularLabel}资料尚未正式入库。当前资料已进入知识库，请重新提问以获取基于现有资料的正式回答。
                                      </div>
                                    )}
                                  {msg.answerMode === 'grounded_answer' && (
                                    <div className="rounded-2xl border border-emerald-100 bg-emerald-50/70 px-4 py-3 text-[12px] font-bold text-emerald-700">
                                      已基于当前资料与背景线索生成正式分析回答。
                                    </div>
                                  )}
                                  {(msg.answerMode === 'grounded_fallback' || msg.answerMode === 'low_confidence_answer') && (
                                    <div className="rounded-2xl border border-amber-100 bg-amber-50/80 px-4 py-3 text-[12px] font-bold text-amber-700">
                                      当前展示的是基于已命中原始证据整理出的兜底版回答，正式长回答没有成功完成。
                                    </div>
                                  )}
                                  {msg.answerMode === 'general_answer' && (
                                    <div className="rounded-2xl border border-sky-100 bg-sky-50/80 px-4 py-3 text-[12px] font-bold text-sky-700">
                                      当前没有命中足够的原始材料，以下回答来自通用背景判断，不代表{terminology.singularLabel}资料中的正式结论。
                                    </div>
                                  )}
                                  {msg.answerMode === 'system_failure' && (
                                    <div className="rounded-2xl border border-rose-100 bg-rose-50/80 px-4 py-3 text-[12px] font-bold text-rose-700">
                                      本次回答未成功生成。{msg.failureReason || '请稍后重试。'}
                                    </div>
                                  )}

                                  <WorkTracePanel
                                    question={msg.requestPrompt || '当前问题'}
                                    retrievalSummary={(msg.retrievalSummary as Record<string, unknown> | undefined) || null}
                                    evidence={msg.evidence}
                                  />

                                  {msg.content && (
                                    <div className="rounded-[24px] bg-[linear-gradient(180deg,rgba(255,255,255,1),rgba(248,250,252,0.92))] border border-slate-100 px-5 py-5 xl:px-6 xl:py-6 shadow-[0_8px_28px_rgba(15,23,42,0.05)]">
                                      <AnswerDocument text={msg.content} />
                                    </div>
                                  )}

                                </div>

                                <div className="bg-gray-50/80 border-t border-gray-100 px-3 xl:px-4 py-3 flex items-center justify-between">
                                  <div className="flex gap-1 xl:gap-2">
                                    <button
                                      className="text-[11px] xl:text-[12px] text-gray-500 hover:text-gray-900 hover:bg-white hover:shadow-sm font-semibold flex items-center gap-1.5 transition-all px-2.5 py-1.5 rounded-lg"
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        void navigator.clipboard.writeText(`${msg.content}`.trim());
                                        flash('success', '已复制当前回答');
                                      }}
                                    >
                                      <Copy size={14} /> 复制
                                    </button>
                                    <button
                                      className="text-[11px] xl:text-[12px] text-gray-500 hover:text-gray-900 hover:bg-white hover:shadow-sm font-semibold flex items-center gap-1.5 transition-all px-2.5 py-1.5 rounded-lg disabled:opacity-50"
                                      disabled={msg.answerMode === 'system_failure' || Boolean(answerActionState[msg.id])}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        void handleVectorizeAnswer(msg.id);
                                      }}
                                    >
                                      <Sparkles size={14} /> {answerActionState[msg.id] === 'vectorize' ? '建立中…' : '建立向量'}
                                    </button>
                                    <button
                                      className="text-[11px] xl:text-[12px] text-gray-500 hover:text-gray-900 hover:bg-white hover:shadow-sm font-semibold flex items-center gap-1.5 transition-all px-2.5 py-1.5 rounded-lg disabled:opacity-50"
                                      disabled={msg.answerMode === 'system_failure' || Boolean(answerActionState[msg.id])}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        void handleExportAnswer(msg.id);
                                      }}
                                    >
                                      <Download size={14} /> {answerActionState[msg.id] === 'export' ? '导出中…' : '导出文件'}
                                    </button>
                                    {msg.answerMode === 'system_failure' && msg.requestPrompt && (
                                      <button
                                        className="text-[11px] xl:text-[12px] text-rose-600 hover:text-rose-700 hover:bg-white hover:shadow-sm font-semibold flex items-center gap-1.5 transition-all px-2.5 py-1.5 rounded-lg"
                                        onClick={(event) => {
                                          event.stopPropagation();
                                          void sendMessage(msg.requestPrompt);
                                        }}
                                      >
                                        <RefreshCw size={14} /> 重试
                                      </button>
                                    )}
                                  </div>
                                  <button
                                    className="text-[11px] xl:text-[12px] text-white bg-[#5B7BFE] hover:bg-[#4a6be6] shadow-[0_2px_8px_rgba(91,123,254,0.3)] font-bold flex items-center gap-1.5 transition-all px-3 xl:px-4 py-1.5 rounded-xl shrink-0 disabled:opacity-50"
                                    disabled={msg.answerMode === 'system_failure'}
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      void createTask({
                                        title: `${currentClient?.name || '客户'} · ${msg.structuredData?.actions?.slice(0, 18) || '跟进事项'}`,
                                        desc: msg.structuredData?.analysis || msg.content,
                                        priority: 'normal',
                                        listId: '',
                                        dueDate: defaultDueDateFromPreset(effectiveTaskSettings.defaultDueDatePreset) || null,
                                        ddl: '本周',
                                        ownerId: null,
                                        ownerName: '',
                                        collaboratorIds: currentSessionUser ? [currentSessionUser.id] : [],
                                        tagIds: [],
                                        tags: ['AI 转任务', currentClient?.name || '客户'],
                                        sourceType: 'chat',
                                        sourceId: currentClientId || undefined,
                                      }).then(async () => {
                                        await loadTaskBlock();
                                        flash('success', '已转为任务');
                                      });
                                    }}
                                  >
                                    <Plus size={14} strokeWidth={2.5} /> 转为任务
                                  </button>
                                </div>
                              </div>
                          </div>
                        )}
                      </div>
                    ))}
                      {transientThinkingPanel && (
                        <ThinkingWorkbenchPanel
                          question={transientThinkingPanel.question}
                          startedAt={transientThinkingPanel.startedAt}
                          stageLabel={transientThinkingPanel.stageLabel}
                          providerLabel={composerProviderLabel}
                          run={transientThinkingPanel.run}
                          mode={transientThinkingPanel.mode}
                        />
                      )}
                      {activeAnalysisRun && !visibleThreadAnalysisRun && (
                        <AnalysisRunCard
                          run={activeAnalysisRun}
                          onRetry={(question) => {
                            void sendMessage(question);
                          }}
                          onVectorize={(messageId) => {
                            void handleVectorizeAnswer(messageId);
                          }}
                          onExport={(messageId) => {
                            void handleExportAnswer(messageId);
                          }}
                        />
                      )}
                    </>
                  )}
                </>
              )}
            </div>

            <div className={`${clientWorkspaceSurfaceMode === 'setup' ? 'hidden ' : ''}px-6 xl:px-8 pb-6 xl:pb-8 pt-4 shrink-0 bg-gradient-to-t from-[#F9FAFB] via-[#F9FAFB] to-transparent`}>
              <div className="flex gap-2.5 mb-3 overflow-x-auto scrollbar-hide">
                {['提炼最新会议纪要', '定位合同违约责任', '生成战略分析简报', '梳理近期推进卡点'].map((prompt) => (
                  <button key={prompt} onClick={() => setInputValue(prompt)} className="text-[11px] xl:text-[12px] font-semibold text-gray-600 bg-white border border-gray-200 px-3 xl:px-4 py-2 rounded-full shadow-sm hover:border-[#5B7BFE] hover:text-[#5B7BFE] hover:shadow-[0_2px_8px_rgba(91,123,254,0.15)] transition-all whitespace-nowrap active:scale-95">
                    <Sparkles size={12} className="inline mr-1 opacity-50" />
                    {prompt}
                  </button>
                ))}
              </div>

              <div
                className={`relative flex items-end gap-3 rounded-[24px] shadow-[0_4px_20px_rgba(0,0,0,0.04)] transition-all p-2 ${
                  clientImportDropZone === 'composer'
                    ? 'bg-blue-50/70 border border-[#5B7BFE] ring-4 ring-blue-500/10'
                    : 'bg-white border border-gray-200 focus-within:border-[#5B7BFE] focus-within:ring-4 focus-within:ring-blue-500/10'
                }`}
                onDragEnter={handleClientImportDragEnter('composer')}
                onDragOver={handleClientImportDragOver('composer')}
                onDragLeave={handleClientImportDragLeave('composer')}
                onDrop={handleClientImportDrop('composer')}
              >
                {clientImportDropZone === 'composer' && (
                  <div className="pointer-events-none absolute inset-1 z-10 flex items-center justify-center rounded-[20px] border-2 border-dashed border-[#5B7BFE] bg-white/92 backdrop-blur-sm">
                    <div className="text-center px-6">
                      <p className="text-[13px] font-bold text-[#3652c9]">松手即可自动识别处理</p>
                      <p className="mt-1 text-[11px] text-[#5c6fb8]">普通资料会自动归档；带字段的 docx 模板会直接尝试自动填写</p>
                    </div>
                  </div>
                )}
                <textarea
                  className="w-full bg-transparent p-2.5 pl-4 text-[13px] xl:text-[14px] text-gray-800 outline-none resize-none min-h-[44px] xl:min-h-[50px] max-h-[120px] leading-relaxed placeholder-gray-400 font-medium"
                  placeholder={`让 ${health?.ai.provider && health.ai.provider !== 'mock' && health.ai.ready ? providerDisplayNames[health.ai.provider] : 'AI'} 帮你推演 ${currentClient?.name || `当前${terminology.singularLabel}`} 的业务问题...`}
                  value={inputValue}
                  onChange={(event) => setInputValue(event.target.value)}
                  onKeyDown={handleComposerKeyDown}
                  disabled={hasPendingAnalysisRun || isBackendBlocked || isStartingMessage}
                />
                <button
                  onClick={() => {
                    if (composerBusyMode) {
                      void handleStopMessage();
                      return;
                    }
                    void sendMessage();
                  }}
                  disabled={composerBusyMode ? false : !inputValue.trim() || !currentClientId || isBackendBlocked}
                  title={composerBusyMode ? '停止当前回答' : '发送问题'}
                  aria-label={composerBusyMode ? '停止当前回答' : '发送问题'}
                  className={`mb-1 mr-1 shrink-0 rounded-2xl p-2.5 xl:p-3 text-white shadow-[0_4px_12px_rgba(91,123,254,0.3)] transition-all ${
                    composerBusyMode
                      ? 'bg-[#4F67D7] hover:bg-[#4258bc] animate-pulse'
                      : 'bg-[#5B7BFE] hover:bg-[#4a6be6]'
                  } disabled:opacity-50 disabled:shadow-none`}
                >
                  {composerBusyMode ? (
                    <span className="block h-[13px] w-[13px] rounded-[3px] bg-white" />
                  ) : (
                    <ArrowUp size={18} strokeWidth={2.6} />
                  )}
                </button>
              </div>
            </div>
          </div>

          <div className="w-[260px] xl:w-[320px] bg-white border-l border-gray-100 flex flex-col h-full shrink-0 z-10 shadow-[-2px_0_10px_rgba(0,0,0,0.02)]">
            <div className="p-5 xl:p-6 border-b border-gray-50 bg-gray-50/50">
              <h3 className="text-[13px] xl:text-[14px] font-bold text-gray-900 mb-4 flex items-center gap-2">
                <UploadCloud size={18} className="text-[#5B7BFE]" /> 导入工具
              </h3>

              <div
                className={`rounded-[24px] border p-4 transition-colors cursor-pointer group mb-4 xl:mb-5 ${
                  clientImportDropZone === 'buffer'
                    ? 'border-[#5B7BFE] bg-blue-50/70'
                    : 'border-gray-200 bg-gray-50/70 hover:border-[#C7D5FF] hover:bg-gray-50'
                }`}
                onDragEnter={handleClientImportDragEnter('buffer')}
                onDragOver={handleClientImportDragOver('buffer')}
                onDragLeave={handleClientImportDragLeave('buffer')}
                onDrop={handleClientImportDrop('buffer')}
              >
                {(() => {
                  const latestJobProcessed = latestKnowledgeJob?.processedItems || 0;
                  const latestJobTotal = latestKnowledgeJob?.totalItems || 0;
                  const hasImportActivity = isImportSubmitting || isTemplateFilling || Boolean((knowledgeStatus?.pendingJobs || 0) + (knowledgeStatus?.runningJobs || 0));
                  const progressRatio = latestJobTotal > 0
                    ? Math.max(0, Math.min(1, latestJobProcessed / latestJobTotal))
                    : hasImportActivity
                      ? 0.18
                      : 0;
                  const progressPercent = Math.max(Math.round(progressRatio * 100), hasImportActivity ? 18 : 0);
                  const importStatusLabel = isTemplateFilling
                    ? '填写模板'
                    : isImportSubmitting
                      ? '加入队列'
                      : hasImportActivity
                        ? '后台建库'
                        : null;
                  return (
                    <>
                      <div className="grid grid-cols-3 gap-3">
                        <button
                          type="button"
                          className="aspect-square rounded-[24px] border border-gray-200 bg-white text-slate-600 shadow-sm transition hover:border-[#C7D5FF] hover:text-[#4A63CF] hover:shadow-[0_8px_20px_rgba(91,123,254,0.08)] disabled:cursor-not-allowed disabled:opacity-50"
                          disabled={isBackendBlocked}
                          onClick={() => void handleSelectImportFolder()}
                          title="导入文件夹"
                          aria-label="导入文件夹"
                        >
                          <span className="flex h-full w-full items-center justify-center">
                            <FolderOpen size={23} />
                          </span>
                        </button>
                        <button
                          type="button"
                          className="aspect-square rounded-[24px] border border-gray-200 bg-white text-slate-600 shadow-sm transition hover:border-[#C7D5FF] hover:text-[#4A63CF] hover:shadow-[0_8px_20px_rgba(91,123,254,0.08)] disabled:cursor-not-allowed disabled:opacity-50"
                          disabled={isBackendBlocked}
                          onClick={() => void handleSelectImportFiles()}
                          title="导入文件"
                          aria-label="导入文件"
                        >
                          <span className="flex h-full w-full items-center justify-center">
                            <UploadCloud size={23} />
                          </span>
                        </button>
                        <button
                          type="button"
                          className="aspect-square rounded-[24px] border border-gray-200 bg-white text-slate-600 shadow-sm transition hover:border-[#C7D5FF] hover:text-[#4A63CF] hover:shadow-[0_8px_20px_rgba(91,123,254,0.08)] disabled:cursor-not-allowed disabled:opacity-50"
                          disabled={isBackendBlocked || isTemplateFilling}
                          onClick={() => void handleFillTemplate()}
                          title="填写模板"
                          aria-label="填写模板"
                        >
                          <span className="flex h-full w-full items-center justify-center">
                            <LayoutTemplate size={23} />
                          </span>
                        </button>
                        <button
                          type="button"
                          className="aspect-square rounded-[24px] border border-gray-200 bg-white text-slate-600 shadow-sm transition hover:border-[#C7D5FF] hover:text-[#4A63CF] hover:shadow-[0_8px_20px_rgba(91,123,254,0.08)] disabled:cursor-not-allowed disabled:opacity-50"
                          disabled={isBackendBlocked}
                          onClick={openClientTextDocumentOverlay}
                          title="粘贴生成文档"
                          aria-label="粘贴生成文档"
                        >
                          <span className="flex h-full w-full items-center justify-center">
                            <PenTool size={23} />
                          </span>
                        </button>
                        {/* 资料速记、结构导入 — 功能待实现，暂不显示入口 */}
                      </div>

                      <div className="mt-3 flex items-center justify-between gap-3 text-[10px] leading-4 text-gray-400">
                        <span>{knowledgeStatus?.totalChunks || 0} 个向量块</span>
                        <span>{(workspace?.recentMessages || []).length} 条最近问答</span>
                      </div>

                      {hasImportActivity && (
                        <div className="mt-3 flex items-center gap-2">
                          <span className="min-w-[32px] text-right text-[10px] font-bold tabular-nums text-[#5B7BFE]">
                            {progressPercent}%
                          </span>
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#E8EEFF]">
                            <div
                              className="h-full rounded-full bg-[#5B7BFE] transition-all duration-500"
                              style={{ width: `${Math.min(progressPercent, 100)}%` }}
                            />
                          </div>
                          <span className="text-[10px] leading-4 text-gray-400">
                            {importStatusLabel || `${latestJobProcessed}/${latestJobTotal || '…'}`}
                          </span>
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>

            </div>

            <div className="flex-1 overflow-y-auto p-5 xl:p-6 bg-white">
              <div className="flex items-center justify-between mb-4 xl:mb-5">
                <h3 className="text-[13px] xl:text-[14px] font-bold text-gray-900 flex items-center gap-2">
                  <FileBadge size={18} className="text-amber-500" />
                  {activeMessageId ? '当前回答引证' : '默认背景线索'}
                </h3>
              </div>

              <div className="space-y-3">
                {activeEvidence.map((ev, index) => (
                  <div key={ev.id} className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-[0_2px_8px_rgba(0,0,0,0.02)] hover:shadow-md transition-shadow group relative">
                    <div className="absolute left-0 top-0 bottom-0 w-[4px] bg-amber-400" />
                    <div className="p-3.5 pl-5">
                      <div className="flex items-start gap-2 mb-2">
                        <span className="bg-amber-100 text-amber-700 text-[10px] px-1.5 py-0.5 rounded-md font-bold mt-0.5 shrink-0">{index + 1}</span>
                        <p className="text-[12px] xl:text-[13px] font-bold text-gray-800 leading-snug line-clamp-2" title={ev.title}>
                          {ev.title}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2 mb-2.5">
                        {typeof ev.score === 'number' && (
                          <span className="text-[10px] font-bold text-sky-700 bg-sky-50 px-2 py-1 rounded-full">
                            相关度 {Math.round(ev.score * 100)}%
                          </span>
                        )}
                        {ev.sectionLabel && (
                          <span className="text-[10px] font-bold text-gray-600 bg-gray-100 px-2 py-1 rounded-full">
                            {ev.sectionLabel}
                          </span>
                        )}
                        {ev.retrievalStage && (
                          <span className="text-[10px] font-bold text-violet-700 bg-violet-50 px-2 py-1 rounded-full">
                            {ev.retrievalStage === 'master_index' ? '目录概览' : ev.retrievalStage === 'surrogate' ? '背景摘要' : '原文片段'}
                          </span>
                        )}
                      </div>
                      {ev.matchedTerms.length > 0 && (
                        <div className="mb-2.5 flex flex-wrap gap-2">
                          {ev.matchedTerms.slice(0, 4).map((term: string) => (
                            <span key={`${ev.id}-${term}`} className="text-[10px] font-bold text-[#5B7BFE] bg-blue-50 px-2 py-1 rounded-full">
                              {term}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="flex justify-end gap-2">
                        {ev.path && (
                          <button
                            className="text-[10px] xl:text-[11px] font-bold text-gray-500 hover:text-[#5B7BFE] bg-gray-50 hover:bg-blue-50 px-2.5 py-1.5 rounded-lg transition-colors flex items-center gap-1"
                            onClick={() =>
                              void openPathBridge(ev.path || '').then((opened) => {
                                if (!opened) flash('error', '原文路径不存在或当前无法打开');
                              })
                            }
                          >
                            <ExternalLink size={12} /> 查看原文
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

            </div>
          </div>
        </div>

        {clientOverlayMode && (
          <div className="fixed inset-0 bg-black/30 backdrop-blur-md z-50 flex items-center justify-center animate-in fade-in">
            <div className="bg-white rounded-[28px] shadow-[0_20px_60px_rgba(0,0,0,0.15)] w-[760px] max-h-[88vh] overflow-hidden transform animate-in zoom-in-95 border border-gray-100" onClick={(event) => event.stopPropagation()}>
              <div className="px-8 py-6 border-b border-gray-100 flex items-center gap-4 bg-white">
                <button
                  type="button"
                  className="rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700"
                  onClick={() => setClientOverlayMode(null)}
                  aria-label={`关闭${terminology.workspaceLabel}弹窗`}
                >
                  <X size={16} />
                </button>
                <h3 className="text-[18px] font-bold text-gray-900 flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-blue-50 text-[#5B7BFE] flex items-center justify-center">
                    {clientOverlayMode === 'meeting' && <Layers size={16} strokeWidth={2.5} />}
                    {clientOverlayMode === 'goal' && <Flag size={16} strokeWidth={2.5} />}
                    {clientOverlayMode === 'dna' && <Target size={16} strokeWidth={2.5} />}
                    {clientOverlayMode === 'paste_document' && <PenTool size={16} strokeWidth={2.5} />}
                  </div>
                  {clientOverlayMode === 'meeting'
                    ? '客户会议流'
                    : clientOverlayMode === 'goal'
                      ? '目标地图'
                      : clientOverlayMode === 'paste_document'
                        ? '粘贴新增文档'
                        : clientDnaDisplayLabel}
                </h3>
              </div>
              <div className="p-8 overflow-y-auto max-h-[calc(88vh-96px)]">
                {clientOverlayMode === 'meeting' && (
                  <div className="space-y-6">
                    <div className="flex gap-3">
                      <input value={meetingTitle} onChange={(event) => setMeetingTitle(event.target.value)} placeholder="会议标题" className="flex-1 bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[14px] font-medium outline-none focus:bg-white focus:border-[#5B7BFE]" />
                      <Button
                        primary
                        onClick={() => {
                          if (!currentClientId || !meetingTitle.trim()) return;
                          void createMeeting(currentClientId, meetingTitle.trim())
                            .then(async (result) => {
                              setWorkspaceSelectedMeetingId(result.meeting.id);
                              setWorkspaceMeetingTranscript(result.meeting.transcriptText || '');
                              setWorkspaceMeetingNotes(result.meeting.notes || '');
                              await refreshWorkspace(currentClientId);
                              flash('success', result.message);
                            })
                            .catch((error) => flash('error', error instanceof Error ? error.message : '会议创建失败'));
                        }}
                      >
                        <Plus size={16} /> 新建会议
                      </Button>
                    </div>
                    <div className="grid grid-cols-[240px_1fr] gap-4">
                      <div className="space-y-3">
                        {(workspace?.meetings || []).map((meeting) => (
                          <button
                            key={meeting.id}
                            onClick={() => setWorkspaceSelectedMeetingId(meeting.id)}
                            className={`w-full text-left p-4 rounded-2xl border transition-all ${workspaceSelectedMeetingId === meeting.id ? 'border-[#5B7BFE] bg-blue-50/50' : 'border-gray-200 bg-white hover:border-blue-200'}`}
                          >
                            <p className="text-[13px] font-bold text-gray-800">{meeting.title}</p>
                            <p className="text-[11px] text-gray-400 mt-1">{meeting.stage}</p>
                          </button>
                        ))}
                      </div>
                      <div className="space-y-4">
                        {selectedMeeting ? (
                          <>
                            <textarea value={workspaceMeetingTranscript} onChange={(event) => setWorkspaceMeetingTranscript(event.target.value)} placeholder="贴入会议原文..." className="w-full bg-gray-50 border border-gray-200 rounded-2xl p-4 text-[13px] min-h-[140px]" />
                            <textarea value={workspaceMeetingNotes} onChange={(event) => setWorkspaceMeetingNotes(event.target.value)} placeholder="补充笔记..." className="w-full bg-gray-50 border border-gray-200 rounded-2xl p-4 text-[13px] min-h-[120px]" />
                            <div className="flex flex-wrap gap-3">
                              <Button
                                onClick={() =>
                                  currentClientId &&
                                  selectedMeeting &&
                                  void syncMeetingFromPipeline(
                                    () => ingestMeeting(currentClientId, selectedMeeting.id, workspaceMeetingTranscript, workspaceMeetingNotes),
                                  ).catch((error) => flash('error', error instanceof Error ? error.message : '会议入库失败'))
                                }
                              >
                                入库
                              </Button>
                              <Button
                                onClick={() =>
                                  currentClientId &&
                                  selectedMeeting &&
                                  void syncMeetingFromPipeline(() => extractMeeting(currentClientId, selectedMeeting.id)).catch((error) =>
                                    flash('error', error instanceof Error ? error.message : '会议抽取失败'),
                                  )
                                }
                              >
                                抽取
                              </Button>
                              <Button
                                onClick={() =>
                                  currentClientId &&
                                  selectedMeeting &&
                                  void syncMeetingFromPipeline(() => resolveMeeting(currentClientId, selectedMeeting.id)).catch((error) =>
                                    flash('error', error instanceof Error ? error.message : '会议消歧失败'),
                                  )
                                }
                              >
                                消歧
                              </Button>
                              <Button
                                primary
                                onClick={() =>
                                  currentClientId &&
                                  selectedMeeting &&
                                  void syncMeetingFromPipeline(() => publishMeeting(currentClientId, selectedMeeting.id), {
                                    refreshTasks: true,
                                    verifyPublished: true,
                                  }).catch((error) => flash('error', error instanceof Error ? error.message : '会议发布失败'))
                                }
                              >
                                发布
                              </Button>
                            </div>
                          </>
                        ) : (
                          <div className="text-center text-gray-400 py-16">先创建或选择一个会议。</div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {clientOverlayMode === 'goal' && (
                  <div className="space-y-5">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {(workspace?.goals || []).map((goal) => (
                        <div key={goal.id} className="bg-white border border-gray-200 rounded-2xl p-4">
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="text-[14px] font-bold text-gray-900">{goal.title}</h4>
                            <span className="text-[11px] font-bold text-[#5B7BFE]">{goal.progress}%</span>
                          </div>
                          <p className="text-[12px] text-gray-500">{goal.quarter} · {goal.ownerName}</p>
                        </div>
                      ))}
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <input value={goalDraft.title} onChange={(event) => setGoalDraft((prev) => ({ ...prev, title: event.target.value }))} placeholder="新增目标标题" className="bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3" />
                      <input value={goalDraft.quarter} onChange={(event) => setGoalDraft((prev) => ({ ...prev, quarter: event.target.value }))} placeholder="季度" className="bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3" />
                      <input type="number" value={goalDraft.progress} onChange={(event) => setGoalDraft((prev) => ({ ...prev, progress: Number(event.target.value) || 0 }))} placeholder="进度" className="bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3" />
                      <input value={goalDraft.ownerName} onChange={(event) => setGoalDraft((prev) => ({ ...prev, ownerName: event.target.value }))} placeholder="负责人" className="bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3" />
                    </div>
                    <Button
                      primary
                      onClick={() => {
                        if (!currentClientId || !goalDraft.title.trim()) return;
                        void createGoal(currentClientId, goalDraft).then(async () => {
                          await refreshWorkspace(currentClientId);
                          setGoalDraft({
                            title: '',
                            quarter: clientWorkspaceSettingsState.defaultGoalQuarter || '2026 Q2',
                            progress: 50,
                            ownerName: currentOperatorName,
                          });
                          flash('success', '目标已添加');
                        });
                      }}
                    >
                      <Plus size={16} /> 添加目标
                    </Button>
                  </div>
                )}

                {clientOverlayMode === 'paste_document' && (
                  <div className="space-y-5">
                    <div className="rounded-2xl border border-blue-100 bg-blue-50/40 px-4 py-3">
                      <p className="text-[13px] font-semibold text-[#33449a]">直接粘贴成{terminology.singularLabel}文档</p>
                      <p className="mt-1 text-[12px] leading-6 text-[#5d6aa6]">
                        当前会自动关联到 {currentClient?.name || `当前${terminology.singularLabel}`}，系统会根据正文先生成一个标题，你也可以手动修改，保存后会直接生成 Word 并进入这个{terminology.singularLabel}的文档库。
                      </p>
                    </div>

                    <div className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3">
                      <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">当前关联{terminology.singularLabel}</p>
                      <p className="mt-2 text-[14px] font-bold text-gray-900">{currentClient?.name || `未选择${terminology.singularLabel}`}</p>
                    </div>

                    <div className="space-y-4">
                      <div>
                        <label className="mb-2 block text-[12px] font-bold text-gray-700">文档标题</label>
                        <input
                          value={clientTextDocumentDraft.title}
                          onChange={(event) =>
                            setClientTextDocumentDraft((prev) => ({
                              ...prev,
                              title: event.target.value,
                              titleEdited: true,
                            }))
                          }
                          placeholder="系统会根据正文自动生成标题"
                          className="w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[14px] font-medium text-gray-900 outline-none transition focus:border-[#5B7BFE] focus:bg-white"
                        />
                      </div>

                      <div>
                        <label className="mb-2 block text-[12px] font-bold text-gray-700">粘贴正文</label>
                        <textarea
                          value={clientTextDocumentDraft.content}
                          onChange={(event) => handleClientTextDocumentContentChange(event.target.value)}
                          placeholder="把文档内容直接贴在这里，支持多段正文。"
                          className="min-h-[320px] w-full rounded-[24px] border border-gray-200 bg-gray-50 px-4 py-4 text-[14px] leading-7 text-gray-900 outline-none transition focus:border-[#5B7BFE] focus:bg-white"
                        />
                      </div>
                    </div>

                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[12px] leading-6 text-gray-500">
                        标题会随着正文自动生成；一旦你手动修改，系统就不再自动覆盖。
                      </p>
                      <Button
                        primary
                        className="shrink-0"
                        disabled={isCreatingClientTextDocument || !clientTextDocumentDraft.content.trim()}
                        onClick={() => void handleCreateClientTextDocument()}
                      >
                        {isCreatingClientTextDocument ? <RefreshCw size={16} className="animate-spin" /> : <FileBadge size={16} />}
                        {isCreatingClientTextDocument ? '生成中…' : '生成 Word 并入库'}
                      </Button>
                    </div>
                  </div>
                )}

                {clientOverlayMode === 'dna' && (
                  <div className="space-y-5">
                    <div className="rounded-2xl border border-blue-100 bg-blue-50/40 px-4 py-3">
                      <p className="text-[13px] font-semibold text-[#33449a]">{`${terminology.singularLabel} DNA 四文档`}</p>
                      <p className="mt-1 text-[12px] leading-6 text-[#5d6aa6]">
                        组织介绍、项目介绍、团队介绍、市场背景介绍会在问答时先作为背景底稿进入思考过程，用来帮助理解当前{terminology.singularLabel}，但不会作为正式引证。
                      </p>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {CLIENT_DNA_MODULES.map((meta) => {
                        const module = workspace?.dnaModules?.find((item) => item.moduleKey === meta.moduleKey);
                        return (
                          <div key={meta.moduleKey} className="bg-white border border-gray-200 rounded-2xl p-4">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <h4 className="text-[14px] font-bold text-gray-900">{meta.title}</h4>
                                <p className="mt-1 text-[12px] leading-5 text-gray-500">{meta.helper}</p>
                              </div>
                              <span className={`text-[10px] font-bold px-2 py-1 rounded-full ${module?.hasDocument ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-500'}`}>
                                {module?.hasDocument ? '已上传' : '未上传'}
                              </span>
                            </div>
                            <div className="mt-3 rounded-2xl bg-gray-50 border border-gray-100 p-3">
                              <p className="text-[12px] text-gray-600 leading-6">
                                {module?.summary || '上传后，这里会显示该模块的摘要，供问答作为背景底稿优先参考。'}
                              </p>
                              {module?.fileName && (
                                <p className="mt-2 text-[11px] font-medium text-gray-400">
                                  {module.fileName}
                                </p>
                              )}
                            </div>
                            <div className="mt-3 flex items-center justify-between gap-3">
                              <span className="text-[11px] text-gray-400">
                                {module?.updatedAt ? `更新于 ${module.updatedAt.replace('T', ' ')}` : '先复制 AI 指令生成 Markdown，再上传 MD'}
                              </span>
                              <div className="flex items-center gap-2">
                                <Button onClick={() => void handleCopyClientDnaPrompt(meta.moduleKey)}>
                                  <Copy size={16} />
                                  复制 AI 指令
                                </Button>
                                <Button onClick={() => void handleUploadClientDna(meta.moduleKey)} disabled={!currentClientId || clientDnaSavingKey === meta.moduleKey}>
                                  {clientDnaSavingKey === meta.moduleKey ? <RefreshCw size={16} className="animate-spin" /> : <UploadCloud size={16} />}
                                  {module?.hasDocument ? '替换 MD' : '上传 MD'}
                                </Button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div className="pt-2">
                      <h4 className="text-[13px] font-bold text-gray-800 mb-3">补充词条</h4>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {(workspace?.dnaTerms || []).map((term) => (
                        <div key={term.id} className="bg-white border border-gray-200 rounded-2xl p-4">
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="text-[14px] font-bold text-gray-900">{term.canonicalName}</h4>
                            <span className="text-[11px] font-bold text-[#5B7BFE]">{term.category}</span>
                          </div>
                          <p className="text-[12px] text-gray-500">{term.description}</p>
                        </div>
                      ))}
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <input value={dnaDraft.category} onChange={(event) => setDnaDraft((prev) => ({ ...prev, category: event.target.value }))} placeholder="分类" className="bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3" />
                      <input value={dnaDraft.canonicalName} onChange={(event) => setDnaDraft((prev) => ({ ...prev, canonicalName: event.target.value }))} placeholder="词条名" className="bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3" />
                      <input value={dnaDraft.aliases} onChange={(event) => setDnaDraft((prev) => ({ ...prev, aliases: event.target.value }))} placeholder="别名，逗号分隔" className="bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3" />
                      <input value={dnaDraft.description} onChange={(event) => setDnaDraft((prev) => ({ ...prev, description: event.target.value }))} placeholder="说明" className="bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3" />
                    </div>
                    <Button
                      primary
                      onClick={() => {
                        if (!currentClientId || !dnaDraft.canonicalName.trim()) return;
                        void upsertDna(currentClientId, {
                          category: dnaDraft.category,
                          canonicalName: dnaDraft.canonicalName,
                          aliases: dnaDraft.aliases.split(/[，,]/).map((item) => item.trim()).filter(Boolean),
                          description: dnaDraft.description,
                        }).then(async () => {
                          await refreshWorkspace(currentClientId);
                          setDnaDraft({ category: '组织习惯', canonicalName: '', aliases: '', description: '' });
                          flash('success', `${clientDnaDisplayLabel} 已更新`);
                        });
                      }}
                    >
                      <Plus size={16} /> 添加词条
                    </Button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {templateFillDialog?.open && (
          <div
            className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/25 px-4 py-6 backdrop-blur-md md:py-10"
          >
            <div
              className="my-auto flex max-h-[calc(100vh-48px)] w-full max-w-[1120px] flex-col overflow-hidden rounded-[30px] border border-[#DDE7FF] bg-white shadow-[0_24px_80px_rgba(15,23,42,0.18)] md:max-h-[calc(100vh-80px)]"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-center justify-between border-b border-gray-100 px-8 py-6">
                <div className="flex items-center gap-4">
                  <button
                    type="button"
                    onClick={() => {
                      if (!isTemplateFilling) setTemplateFillDialog(null);
                    }}
                    disabled={isTemplateFilling}
                    className="rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                    aria-label="关闭模板填写进度"
                  >
                    <X size={16} />
                  </button>
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#EEF3FF] text-[#5B7BFE]">
                    <LayoutTemplate size={20} />
                  </div>
                  <div>
                    <p className="text-[18px] font-bold text-gray-900">AI 正在填写模板</p>
                    <p className="mt-1 text-[12px] text-gray-500">{templateFillDialog.templateName}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">当前进度</p>
                  <p className="mt-1 text-[22px] font-bold text-[#5B7BFE]">{templateFillDialog.percent}%</p>
                </div>
              </div>

              <div className="min-h-0 overflow-y-auto px-8 py-6">
                <div className="rounded-[22px] border border-[#DCE6FF] bg-[#F8FAFF] px-5 py-4">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                    <p className="text-[15px] font-bold text-gray-900">{templateFillDialog.statusLabel}</p>
                      <p className="mt-1 text-[12px] leading-6 text-gray-500">{templateFillDialog.hint}</p>
                      {templateFillDialog.fieldCount > 0 && (
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-gray-400">
                          <span>已处理 {Math.min(templateFillDialog.processedCount, templateFillDialog.fieldCount)}/{templateFillDialog.fieldCount} 个字段</span>
                          {templateFillDialog.currentFieldLabel && (
                            <span className="rounded-full bg-white px-2 py-1 text-gray-500">
                              当前字段：{templateFillDialog.currentFieldLabel}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    <p className="shrink-0 text-[12px] font-semibold text-gray-400">
                      {Math.max(1, Math.round((Date.now() - templateFillDialog.startedAt) / 1000))} 秒
                    </p>
                  </div>
                  <div className="mt-4 h-2 overflow-hidden rounded-full bg-[#E8EEFF]">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        templateFillDialog.stage === 'failed' ? 'bg-rose-500' : 'bg-[#5B7BFE]'
                      }`}
                      style={{ width: `${Math.min(templateFillDialog.percent, 100)}%` }}
                    />
                  </div>
                </div>

                <div className="mt-5 rounded-[22px] border border-gray-200 bg-white px-5 py-4">
                  <div className="flex flex-wrap gap-2">
                    {buildTemplateFillStepStatuses(templateFillDialog).map(([label, status]) => (
                      <span
                        key={label}
                        className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-[11px] font-bold ${
                          status === 'done'
                            ? 'bg-emerald-50 text-emerald-700'
                            : status === 'failed'
                              ? 'bg-rose-50 text-rose-700'
                            : status === 'active'
                              ? 'bg-blue-50 text-[#4A63CF]'
                              : 'bg-gray-100 text-gray-400'
                        }`}
                      >
                        {status === 'done'
                          ? <CheckCircle2 size={12} />
                          : status === 'failed'
                            ? <AlertCircle size={12} />
                            : status === 'active'
                              ? <Activity size={12} />
                              : <Circle size={10} />}
                        {label}
                      </span>
                    ))}
                    {templateFillDialog.backendStatus === 'failed' && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-3 py-1 text-[11px] font-bold text-rose-700">
                        <AlertCircle size={12} />
                        已失败
                      </span>
                    )}
                  </div>
                  <p className="mt-3 text-[11px] leading-6 text-gray-400">
                    系统会依次识别模板字段、检索{terminology.singularLabel}资料、生成字段答案，并写回一份新的文档版本。
                  </p>
                </div>

                <div className="mt-5 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
                  <div className="rounded-[22px] border border-gray-200 bg-white px-5 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <h4 className="text-[14px] font-bold text-gray-900">本次动用资料</h4>
                      <span className="text-[11px] text-gray-400">最多展示 8 条</span>
                    </div>
                    {templateFillDialog.evidenceTitles.length > 0 ? (
                      <div className="mt-3 space-y-2">
                        {templateFillDialog.evidenceTitles.map((title, index) => (
                          <div key={`${title}-${index}`} className="rounded-2xl border border-gray-100 bg-gray-50/80 px-3 py-2 text-[12px] leading-6 text-gray-600">
                            {index + 1}. {title}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-3 text-[12px] leading-6 text-gray-400">
                        {templateFillDialog.stage === 'completed'
                          ? '这次没有返回明确的资料标题。'
                          : '完成字段检索后，这里会列出本次填写实际参考的资料。'}
                      </p>
                    )}
                  </div>

                  <div className="rounded-[22px] border border-gray-200 bg-white px-5 py-4">
                    <h4 className="text-[14px] font-bold text-gray-900">填写结果</h4>
                    <div className="mt-3 grid grid-cols-3 gap-2">
                      <div className="rounded-2xl bg-[#F8FAFF] px-3 py-3 text-center">
                        <p className="text-[22px] font-bold text-gray-900">{templateFillDialog.fieldCount}</p>
                        <p className="mt-1 text-[11px] text-gray-400">字段总数</p>
                      </div>
                      <div className="rounded-2xl bg-emerald-50 px-3 py-3 text-center">
                        <p className="text-[22px] font-bold text-emerald-700">{templateFillDialog.filledCount}</p>
                        <p className="mt-1 text-[11px] text-emerald-500">已填写</p>
                      </div>
                      <div className="rounded-2xl bg-amber-50 px-3 py-3 text-center">
                        <p className="text-[22px] font-bold text-amber-700">{templateFillDialog.missingCount}</p>
                        <p className="mt-1 text-[11px] text-amber-500">待确认</p>
                      </div>
                    </div>
                    {templateFillDialog.errorMessage && (
                      <div className="mt-3 rounded-2xl border border-rose-100 bg-rose-50/80 px-3 py-3 text-[12px] leading-6 text-rose-700">
                        {templateFillDialog.errorMessage}
                      </div>
                    )}
                    {templateFillDialog.outputPath && (
                      <p className="mt-3 text-[11px] leading-5 text-gray-400">
                        已生成新文档：{templateFillDialog.outputPath.split('/').slice(-2).join('/')}
                      </p>
                    )}
                    {!!templateFillDialog.attachmentChecklist.length && (
                      <p className="mt-2 text-[11px] leading-5 text-gray-400">
                        已同步识别 {templateFillDialog.attachmentChecklist.length} 项附件/材料要求，可继续用于补件整理。
                      </p>
                    )}
                  </div>
                </div>

                {(templateFillDialog.fields.length > 0 || templateFillDialog.stage === 'completed') && (
                  <div className="mt-4 grid gap-4 lg:grid-cols-[1.08fr_0.92fr]">
                    <div className="rounded-[22px] border border-amber-200 bg-amber-50/50 px-5 py-4">
                      <div className="flex items-center justify-between gap-3">
                        <h4 className="text-[14px] font-bold text-amber-900">待确认字段</h4>
                        <span className="text-[11px] text-amber-600">最多展示 8 项</span>
                      </div>
                      {templateFillDialog.fields.filter((field) => field.status === 'missing').length > 0 ? (
                        <div className="mt-3 space-y-3">
                          {templateFillDialog.fields
                            .filter((field) => field.status === 'missing')
                            .slice(0, 8)
                            .map((field) => (
                              <div key={`pending-${field.label}`} className="rounded-2xl border border-amber-100 bg-white/90 px-4 py-3">
                                <p className="text-[13px] font-bold text-amber-900">{field.label}</p>
                                <p className="mt-1 text-[12px] leading-6 text-amber-700">{field.value}</p>
                                {field.basisSummary && (
                                  <p className="mt-2 text-[11px] leading-5 text-amber-900/80">{field.basisSummary}</p>
                                )}
                                {field.followUpQuestion && (
                                  <div className="mt-2 rounded-xl bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-800">
                                    {field.followUpQuestion}
                                  </div>
                                )}
                                {field.evidenceTitles.length > 0 && (
                                  <div className="mt-2 flex flex-wrap gap-1.5">
                                    {field.evidenceTitles.slice(0, 3).map((title, index) => (
                                      <span key={`${field.label}-${index}`} className="rounded-full bg-amber-100 px-2 py-1 text-[10px] font-semibold text-amber-700">
                                        {title}
                                      </span>
                                    ))}
                                  </div>
                                )}
                                {!!field.webSourceTitles?.length && (
                                  <div className="mt-2 flex flex-wrap gap-1.5">
                                    {field.webSourceTitles.slice(0, 2).map((title, index) => (
                                      <span key={`${field.label}-web-${index}`} className="rounded-full border border-sky-100 bg-white px-2 py-1 text-[10px] font-semibold text-sky-700">
                                        网页：{title}
                                      </span>
                                    ))}
                                  </div>
                                )}
                                {!!field.suggestedSources?.length && (
                                  <p className="mt-2 text-[10px] leading-5 text-amber-700/90">
                                    建议补充：{field.suggestedSources.slice(0, 4).join('、')}
                                  </p>
                                )}
                              </div>
                            ))}
                        </div>
                      ) : (
                        <p className="mt-3 text-[12px] leading-6 text-amber-700">
                          {templateFillDialog.stage === 'completed'
                            ? '这次所有字段都已自动填写完成，没有待确认项。'
                            : '如果资料不足，这里会列出需要人工补充确认的字段。'}
                        </p>
                      )}
                    </div>

                    <div className="rounded-[22px] border border-emerald-200 bg-emerald-50/40 px-5 py-4">
                      <div className="flex items-center justify-between gap-3">
                        <h4 className="text-[14px] font-bold text-emerald-900">已填写字段示例</h4>
                        <span className="text-[11px] text-emerald-600">最多展示 6 项</span>
                      </div>
                      {templateFillDialog.fields.filter((field) => field.status === 'filled').length > 0 ? (
                        <div className="mt-3 space-y-3">
                          {templateFillDialog.fields
                            .filter((field) => field.status === 'filled')
                            .slice(0, 6)
                            .map((field) => (
                              <div key={`filled-${field.label}`} className="rounded-2xl border border-emerald-100 bg-white/90 px-4 py-3">
                                <p className="text-[13px] font-bold text-emerald-900">{field.label}</p>
                                <p className="mt-1 text-[12px] leading-6 text-gray-700 line-clamp-3">{field.value}</p>
                                {field.basisSummary && (
                                  <p className="mt-2 text-[11px] leading-5 text-gray-500">{field.basisSummary}</p>
                                )}
                                {field.evidenceTitles.length > 0 && (
                                  <div className="mt-2 flex flex-wrap gap-1.5">
                                    {field.evidenceTitles.slice(0, 3).map((title, index) => (
                                      <span key={`${field.label}-filled-${index}`} className="rounded-full bg-emerald-100 px-2 py-1 text-[10px] font-semibold text-emerald-700">
                                        {title}
                                      </span>
                                    ))}
                                  </div>
                                )}
                                {!!field.webSourceTitles?.length && (
                                  <div className="mt-2 flex flex-wrap gap-1.5">
                                    {field.webSourceTitles.slice(0, 2).map((title, index) => (
                                      <span key={`${field.label}-filled-web-${index}`} className="rounded-full bg-sky-50 px-2 py-1 text-[10px] font-semibold text-sky-700">
                                        网页：{title}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            ))}
                        </div>
                      ) : (
                        <p className="mt-3 text-[12px] leading-6 text-emerald-700">
                          {templateFillDialog.stage === 'completed'
                            ? '这次没有生成可展示的已填写字段示例。'
                            : '完成填写后，这里会展示本次自动写入的字段示例。'}
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {((templateFillDialog.fields.some((field) => field.status === 'missing' || field.reviewRequired))
                  || templateFillDialog.attachmentChecklist.length > 0) && (
                  <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <div className="rounded-[22px] border border-rose-200 bg-rose-50/40 px-5 py-4">
                      <div className="flex items-center justify-between gap-3">
                        <h4 className="text-[14px] font-bold text-rose-900">缺资料清单</h4>
                        <span className="text-[11px] text-rose-600">按待核验字段收口</span>
                      </div>
                      {buildTemplateMissingMaterialItems(templateFillDialog.fields).length > 0 ? (
                        <div className="mt-3 space-y-3">
                          {buildTemplateMissingMaterialItems(templateFillDialog.fields).slice(0, 8).map((item) => (
                            <div key={`missing-${item.label}`} className="rounded-2xl border border-rose-100 bg-white/90 px-4 py-3">
                              <p className="text-[13px] font-bold text-rose-900">{item.label}</p>
                              <p className="mt-1 text-[12px] leading-6 text-rose-700">{item.reason}</p>
                              {!!item.suggestedSources.length && (
                                <p className="mt-2 text-[10px] leading-5 text-rose-700/90">
                                  可补来源：{item.suggestedSources.join('、')}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="mt-3 text-[12px] leading-6 text-rose-700">
                          当前没有新增缺资料项。
                        </p>
                      )}
                    </div>

                    <div className="rounded-[22px] border border-slate-200 bg-slate-50/70 px-5 py-4">
                      <div className="flex items-center justify-between gap-3">
                        <h4 className="text-[14px] font-bold text-slate-900">附件清单</h4>
                        <span className="text-[11px] text-slate-500">模板识别结果</span>
                      </div>
                      {templateFillDialog.attachmentChecklist.length > 0 ? (
                        <div className="mt-3 space-y-2">
                          {templateFillDialog.attachmentChecklist.slice(0, 10).map((item, index) => (
                            <div key={`attachment-${index}-${item}`} className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-3 text-[12px] leading-6 text-slate-700">
                              {index + 1}. {item}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="mt-3 text-[12px] leading-6 text-slate-500">
                          当前模板中没有识别出明确的附件/材料清单。
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className="flex items-center justify-end gap-3 border-t border-gray-100 bg-gray-50/60 px-8 py-5">
                {templateFillDialog.outputPath && (
                  <>
                    <button
                      type="button"
                      onClick={() => {
                        void revealInFinderBridge(templateFillDialog.outputPath!);
                      }}
                      className="rounded-2xl border border-gray-200 bg-white px-4 py-2 text-[13px] font-bold text-gray-600 transition-colors hover:border-gray-300 hover:text-gray-900"
                    >
                      在 Finder 中显示
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const sourcePath = templateFillDialog.outputPath!;
                        const suggestedName = sourcePath.split('/').pop() || undefined;
                        void saveFileAsBridge(sourcePath, suggestedName).then((savedPath) => {
                          if (savedPath) {
                            flash('success', '已导出填写结果');
                          }
                        });
                      }}
                      className="rounded-2xl border border-gray-200 bg-white px-4 py-2 text-[13px] font-bold text-gray-600 transition-colors hover:border-gray-300 hover:text-gray-900"
                    >
                      另存为
                    </button>
                    <Button
                      primary
                      onClick={() => void openPathBridge(templateFillDialog.outputPath!)}
                      className="px-5 shadow-md"
                    >
                      打开结果文档
                    </Button>
                  </>
                )}
                <button
                  type="button"
                  onClick={() => setTemplateFillDialog(null)}
                  className="rounded-2xl px-5 py-2 text-[13px] font-bold text-gray-500 transition-colors hover:text-gray-800"
                  disabled={isTemplateFilling}
                >
                  {templateFillDialog.stage === 'completed' || templateFillDialog.stage === 'failed' ? '关闭' : '处理中…'}
                </button>
              </div>
            </div>
          </div>
        )}

        {isClientModalOpen && (
          <div
            className="fixed inset-0 z-[130] flex items-center justify-center bg-black/30 backdrop-blur-md animate-in fade-in"
          >
            <div className="bg-white rounded-[28px] shadow-[0_20px_60px_rgba(0,0,0,0.15)] w-[580px] overflow-hidden transform animate-in zoom-in-95 border border-gray-100" onClick={(event) => event.stopPropagation()}>
              <div className="px-8 py-6 border-b border-gray-100 flex items-center gap-4 bg-white">
                <button
                  type="button"
                  className="rounded-2xl border border-gray-200 bg-white p-2 text-gray-400 transition hover:text-gray-700"
                  onClick={() => closeClientModal({ resumeEventLine: true })}
                  aria-label={`关闭${terminology.singularLabel}弹窗`}
                >
                  <X size={16} />
                </button>
                <h3 className="text-[18px] font-bold text-gray-900 flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-blue-50 text-[#5B7BFE] flex items-center justify-center">
                    <Briefcase size={16} strokeWidth={2.5} />
                  </div>
                  {editingClientId ? `编辑${terminology.singularLabel}` : `创建${terminology.singularLabel}`}
                </h3>
              </div>
              <div className="p-8 space-y-5">
                <div className="grid grid-cols-1 gap-4">
                  <input value={clientDraft.name} onKeyDown={handleClientModalKeyDown} onChange={(event) => setClientDraft((prev) => ({ ...prev, name: event.target.value }))} placeholder={`${terminology.singularLabel}名称`} className="bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none" />
                  <input value={clientDraft.alias} onKeyDown={handleClientModalKeyDown} onChange={(event) => setClientDraft((prev) => ({ ...prev, alias: event.target.value }))} placeholder={`${terminology.singularLabel}别名（选填）`} className="bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none" />
                </div>
                <div className="rounded-[22px] border border-blue-100 bg-blue-50/70 px-4 py-4">
                  <p className="text-[13px] font-bold text-gray-900">创建后会立刻发生什么</p>
                  <div className="mt-2 space-y-1.5 text-[12px] leading-6 text-gray-600">
                    <p>1. 这个{terminology.singularLabel}会立刻出现在{terminology.workspaceLabel}搜索里。</p>
                    <p>2. 创建成功后会直接进入资料导入引导页。</p>
                    <p>3. 下一步先导入已有资料，系统会自动分析归档并建立{terminology.singularLabel}上下文。</p>
                  </div>
                </div>
                <p className="text-[11px] text-gray-400">按 Enter 可直接创建；创建后先导入已有资料即可开始正式建库。</p>
              </div>
              <div className="px-8 py-5 border-t border-gray-100 bg-gray-50/50 flex items-center justify-between gap-3">
                <div>
                  {editingClientId && (
                    <button
                      onClick={() => void handleDeleteClient()}
                      className="text-[13px] font-bold text-rose-500 hover:text-rose-600 px-3 py-2 transition-colors"
                    >
                      删除{terminology.singularLabel}
                    </button>
                  )}
                </div>
                <div className="flex items-center gap-3">
                <button
                  onClick={() => closeClientModal({ resumeEventLine: true })}
                  className="text-[13px] font-bold text-gray-500 hover:text-gray-800 px-5 py-2 transition-colors"
                >
                  取消
                </button>
                <Button primary onClick={() => void submitClientModal()} className="px-6 shadow-md">
                  {editingClientId ? `保存${terminology.singularLabel}` : `创建${terminology.singularLabel}`}
                </Button>
                </div>
              </div>
            </div>
          </div>
        )}
        {isClientModalOpen && isDeleteClientConfirmOpen && (
          <div className="fixed inset-0 z-[135] flex items-center justify-center bg-black/35 animate-in fade-in">
            <div className="w-[440px] rounded-[24px] bg-white border border-rose-100 shadow-[0_24px_80px_rgba(0,0,0,0.18)] overflow-hidden" onClick={(event) => event.stopPropagation()}>
              <div className="px-7 py-5 border-b border-rose-100 bg-rose-50/70">
                <div className="flex items-center gap-4">
                  <button
                    type="button"
                    className="rounded-2xl border border-rose-200 bg-white p-2 text-rose-400 transition hover:text-rose-700"
                    onClick={() => {
                      setIsDeleteClientConfirmOpen(false);
                      setDeleteClientConfirmInput('');
                    }}
                    aria-label="关闭删除确认"
                  >
                    <X size={16} />
                  </button>
                  <div className="text-[16px] font-bold text-rose-700">确认删除{terminology.singularLabel}</div>
                </div>
                <p className="mt-2 text-[12px] leading-6 text-rose-600">
                  这会删除当前{terminology.singularLabel}的资料、{terminology.workspaceLabel}、问答记录和知识索引，且无法恢复。
                </p>
              </div>
              <div className="px-7 py-6 space-y-4">
                <p className="text-[13px] font-medium text-gray-600">
                  请输入{terminology.singularLabel}名称
                  <span className="mx-1 font-bold text-gray-900">"{clients.find((client) => client.id === editingClientId)?.name || clientDraft.name.trim() || `该${terminology.singularLabel}`}"</span>
                  以确认删除。
                </p>
                <input
                  autoFocus
                  value={deleteClientConfirmInput}
                  onChange={(event) => setDeleteClientConfirmInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      void confirmDeleteClient();
                    }
                  }}
                  placeholder={`输入${terminology.singularLabel}名称`}
                  className="w-full rounded-2xl border border-rose-200 bg-rose-50/40 px-4 py-3 text-[13px] font-bold outline-none focus:border-rose-300"
                />
              </div>
              <div className="px-7 py-5 border-t border-gray-100 bg-gray-50/50 flex items-center justify-end gap-3">
                <button
                  onClick={() => {
                    setIsDeleteClientConfirmOpen(false);
                    setDeleteClientConfirmInput('');
                  }}
                  className="px-4 py-2 text-[13px] font-bold text-gray-500 hover:text-gray-800 transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={() => void confirmDeleteClient()}
                  className="px-5 py-2 rounded-2xl bg-rose-500 text-white text-[13px] font-bold shadow-[0_12px_30px_rgba(244,63,94,0.28)] hover:bg-rose-600 transition-colors"
                >
                  确认删除
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  const SettingsView = () => {
    const importableLegacyEntries = legacyScanResult?.entries.filter((entry) => entry.importable) || [];
    const canManageTaskTag = (tag: TaskTag) => (tag.scope === 'self' ? tag.ownerUserId === currentSessionUser?.id : currentSessionUser?.primaryRole === 'admin');
    const canManageOrgTaskList = currentSessionUser?.primaryRole === 'admin';
    const canManageSensitiveSettings = currentSessionUser?.primaryRole === 'admin';
    const isLocalSession = authState.sessionMode !== 'cloud';
    const canEditBusinessSettings = canManageSensitiveSettings || systemAdminSettingsState.allowBusinessSettingsForEmployees;
    const canEditOrgDna = canManageSensitiveSettings || systemAdminSettingsState.allowOrgDnaForEmployees;
    const hasBrandLogoDraftChange = (systemAdminDraft.brandLogoDataUrl || null) !== (systemAdminSettingsState.brandLogoDataUrl || null);
    const resetTagManager = () => {
      setEditingTagId(null);
      setTagManageDraft({ name: '', scope: defaultTagScope, color: TASK_COLOR_OPTIONS[0] });
    };
    const resetListManager = () => {
      setEditingListId(null);
      setListManageDraft({ name: '', description: '' });
    };

    const handleImportLegacyEntries = async () => {
      if (!legacyImportClientId) {
        flash('error', `请先选择一个${terminology.singularLabel}用于接收旧数据导入`);
        return;
      }
      if (!importableLegacyEntries.length) {
        flash('info', '当前扫描结果中没有可导入的 JSON 或 CSV 文件');
        return;
      }
      setIsImportingLegacy(true);
      try {
        const imported = await importPaths(
          legacyImportClientId,
          'file',
          importableLegacyEntries.map((entry) => entry.path),
          { allowLegacy: true },
        );
        await Promise.all([loadLogsBlock(), legacyImportClientId === currentClientId ? refreshWorkspace(legacyImportClientId) : Promise.resolve()]);
        flash('success', `已向目标${terminology.singularLabel}导入 ${imported.reduce((sum, item) => sum + item.importedCount, 0)} 份旧数据文件`);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '旧数据导入失败');
      } finally {
        setIsImportingLegacy(false);
      }
    };

    const handleSaveTag = async () => {
      const trimmedName = tagManageDraft.name.trim();
      if (!trimmedName) {
        flash('error', '请先填写标签名称');
        return;
      }
      if (!canManagePublicTaskTaxonomy && tagManageDraft.scope === 'org') {
        flash('error', '只有管理员可以维护公共标签');
        return;
      }
      try {
        if (editingTagId) {
          await updateTaskTag(editingTagId, { name: trimmedName, scope: tagManageDraft.scope, color: tagManageDraft.color });
        } else {
          await createTaskTag({ name: trimmedName, scope: tagManageDraft.scope, color: tagManageDraft.color });
        }
        await loadTaskBlock();
        resetTagManager();
        flash('success', editingTagId ? '标签已更新' : '标签已创建');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : editingTagId ? '更新标签失败' : '创建标签失败');
      }
    };

    const handleArchiveTag = async (tag: TaskTag, archived: boolean) => {
      if (!canManageTaskTag(tag)) {
        flash('error', '你没有权限调整这个标签');
        return;
      }
      try {
        await updateTaskTag(tag.id, { name: tag.name, scope: tag.scope, color: tag.color, archived });
        await loadTaskBlock();
        flash('success', archived ? '标签已归档' : '标签已恢复');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : archived ? '归档失败' : '恢复失败');
      }
    };

    const handleSaveTaskSettings = async () => {
      try {
        const next = await updateTaskSettings({
          defaultListId: null,
          defaultPriority: taskSettingsDraft.defaultPriority,
          defaultDueDatePreset: taskSettingsDraft.defaultDueDatePreset,
          defaultViewMode: taskSettingsDraft.defaultViewMode,
          listSortMode: taskSettingsDraft.listSortMode,
          showCompletedTasks: taskSettingsDraft.showCompletedTasks,
          defaultReviewScope: taskSettingsDraft.defaultReviewScope,
          autoAssignSelf: taskSettingsDraft.autoAssignSelf,
        });
        setTaskSettingsState(next);
        await loadTaskBlock();
        flash('success', '任务与日程设置已保存');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '任务设置保存失败');
      }
    };

    const handleSaveReviewGovernance = async () => {
      setIsSavingReviewGovernance(true);
      try {
        const next = await updateReviewGovernanceSettings({ departments: reviewGovernanceDraft.departments });
        setReviewGovernanceState(next);
        await loadReviewBlock();
        if (currentSessionUser?.primaryRole === 'admin') {
          await loadEmployeeReviewBlock();
        }
        flash('success', '周复盘聚合治理已保存');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '治理设置保存失败');
      } finally {
        setIsSavingReviewGovernance(false);
      }
    };

    const handleSaveOrgModel = async (nextDraft: OrgModelSettings = orgModelDraft) => {
      setOrgModelDraft(nextDraft);
      setIsSavingOrgModel(true);
      try {
        const next = await updateOrgModelProfile(nextDraft);
        setOrgModelState(next);
        setOrgModelDraft(next);
        await Promise.all([
          loadEmployeeReviewBlock(),
          loadTaskBlock(),
          loadReviewBlock(reviewDashboard?.currentReview?.weekLabel),
        ]);
        try {
          const backfill = await backfillOrgTaskLinks();
          const touchedCount = backfill.createdLinks + backfill.updatedLinks;
          flash('success', touchedCount > 0 ? `组织底盘已保存，已同步 ${touchedCount} 条任务关联` : '组织底盘已保存，任务关联已校准');
        } catch (error) {
          flash('error', error instanceof Error ? `组织底盘已保存，但任务关联回填失败：${error.message}` : '组织底盘已保存，但任务关联回填失败');
        }
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '组织底盘保存失败');
      } finally {
        setIsSavingOrgModel(false);
      }
    };

    const handleSaveTaskList = async () => {
      if (!canManageOrgTaskList) {
        flash('error', '只有管理员可以维护组织清单');
        return;
      }
      const trimmedName = listManageDraft.name.trim();
      if (!trimmedName) {
        flash('error', '请先填写清单名称');
        return;
      }
      try {
        if (editingListId) {
          await updateTaskList(editingListId, {
            name: trimmedName,
            description: listManageDraft.description.trim() || null,
            scope: 'org',
          });
        } else {
          await createTaskList({
            name: trimmedName,
            description: listManageDraft.description.trim() || null,
            scope: 'org',
          });
        }
        await Promise.all([loadTaskBlock(), loadTaskSettingsBlock()]);
        resetListManager();
        flash('success', editingListId ? '清单已更新' : '清单已创建');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : editingListId ? '更新清单失败' : '创建清单失败');
      }
    };

    const handleToggleTaskListArchived = async (list: TaskList) => {
      if (!canManageOrgTaskList) {
        flash('error', '只有管理员可以维护组织清单');
        return;
      }
      try {
        await updateTaskList(list.id, {
          name: list.name,
          description: list.description || null,
          archived: !list.archivedAt,
          scope: 'org',
        });
        await Promise.all([loadTaskBlock(), loadTaskSettingsBlock()]);
        flash('success', list.archivedAt ? '清单已恢复' : '清单已归档');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '清单状态更新失败');
      }
    };

    const handleDeleteTaskList = async (list: TaskList) => {
      if (!canManageOrgTaskList) {
        flash('error', '只有管理员可以删除组织清单');
        return;
      }
      if (!window.confirm(`确认删除清单“${list.name}”？相关任务会移除与该清单的关联；删除后不会再自动补任何默认清单。`)) {
        return;
      }
      try {
        await deleteTaskList(list.id);
        await Promise.all([loadTaskBlock(), loadTaskSettingsBlock()]);
        if (editingListId === list.id) {
          resetListManager();
        }
        flash('success', '清单已删除');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '删除清单失败');
      }
    };

    const handleDeleteTag = async (tag: TaskTag) => {
      if (!canManageTaskTag(tag)) {
        flash('error', '你没有权限删除这个标签');
        return;
      }
      if (!window.confirm(`确认删除标签"${tag.name}"？相关任务会同步移除这个标签。`)) {
        return;
      }
      try {
        await deleteTaskTag(tag.id);
        await loadTaskBlock();
        if (editingTagId === tag.id) {
          resetTagManager();
        }
        flash('success', '标签已删除');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '删除标签失败');
      }
    };

    const requestDeleteTaskRecord = (
      task: { id: string; title: string; clientId?: string | null; eventLineId?: string | null },
      options?: { closeEditor?: boolean },
    ) => {
      setPendingTaskDelete({
        id: task.id,
        title: task.title,
        clientId: task.clientId || null,
        eventLineId: task.eventLineId || null,
        closeEditor: options?.closeEditor || false,
      });
    };

    const handleDeleteTaskRecord = async (
      task: { id: string; title: string; clientId?: string | null; eventLineId?: string | null },
      options?: { closeEditor?: boolean },
    ) => {
      if (options?.closeEditor || editingTask.id === task.id) {
        closeTaskModal('delete-started');
        resetTaskDraft();
      }
      const deletedId = task.id;
      setTasks((prev) => prev.filter((t) => t.id !== deletedId));
      flash('success', '任务已删除');
      void (async () => {
        try {
          await deleteTask(deletedId);
          // Wait for cloud to process before refreshing
          await new Promise((r) => setTimeout(r, 2000));
          await loadTaskBlock();
          // Ensure deleted task stays deleted even if cloud returned stale data
          setTasks((prev) => prev.filter((t) => t.id !== deletedId));
          if (reviewDashboard?.weekLabel) void loadReviewBlock(reviewDashboard.weekLabel);
          void refreshWorkspace(task.clientId || undefined);
          if (task.eventLineId && activeEventLine?.eventLine.id === task.eventLineId) void openEventLineDetail(task.eventLineId);
        } catch {
          // Delete already removed locally — don't restore
        }
      })();
    };

    const confirmDeleteTaskRecord = async () => {
      if (!pendingTaskDelete) return;
      const payload = pendingTaskDelete;
      setPendingTaskDelete(null);
      await handleDeleteTaskRecord(
        {
          id: payload.id,
          title: payload.title,
          clientId: payload.clientId || null,
          eventLineId: payload.eventLineId || null,
        },
        { closeEditor: payload.closeEditor },
      );
    };

    const handleSaveOperatorSelection = async () => {
      try {
        await updateSettings({ currentOperatorId: draft.currentOperatorId });
        await Promise.all([loadSettingsBlock(), loadLogsBlock()]);
        flash('success', '当前操作者已更新');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '保存失败');
      }
    };

    const handleSaveAiSettings = async () => {
      try {
        await updateSettings({
          aiProvider: draft.aiProvider as AiProvider,
          aiModel: draft.aiModel,
          apiKey: draft.apiKey.trim() || undefined,
        });
        const nextLocalInputMemory = await saveAiInputMemory({
          rememberApiKey: rememberAiInputKey,
          apiKey: draft.apiKey.trim() || undefined,
        });
        setLocalInputMemoryState(nextLocalInputMemory);
        await Promise.all([loadSettingsBlock(), loadLogsBlock()]);
        setDraft((prev) => ({
          ...prev,
          apiKey: nextLocalInputMemory.aiSettings.rememberApiKey ? nextLocalInputMemory.aiSettings.apiKey : '',
        }));
        flash('success', 'AI 设置已保存');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '保存失败');
      }
    };

    const handleSaveProfile = async () => {
      setProfileSubmitting(true);
      setProfileMessage('');
      try {
        const response = await updateProfile({
          fullName: profileDraft.fullName?.trim() || undefined,
          email: profileDraft.email?.trim() || undefined,
        });
        setAuthState(response);
        await loadAll();
        setProfileMessage('基本信息已更新');
      } catch (error) {
        setProfileMessage(error instanceof Error ? error.message : '基本信息更新失败');
      } finally {
        setProfileSubmitting(false);
      }
    };

    const handleUploadOrgDna = async (moduleKey: OrganizationDnaModule['moduleKey']) => {
      const paths = await selectFilesBridge();
      const filePath = paths[0];
      if (!filePath) return;
      setOrgDnaSavingKey(moduleKey);
      try {
        await updateOrganizationDnaModule(moduleKey, { filePath });
        await Promise.all([loadSettingsSectionBlock('org_dna', true), loadLogsBlock()]);
        flash('success', '组织 DNA 已更新');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '组织 DNA 上传失败');
      } finally {
        setOrgDnaSavingKey(null);
      }
    };

    const handleSaveClientWorkspaceSettings = async () => {
      try {
        const next = await updateClientWorkspaceSettings(clientWorkspaceDraft);
        setClientWorkspaceSettingsState(next);
        await loadLogsBlock();
        flash('success', `${terminology.workspaceLabel}设置已保存`);
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '保存失败');
      }
    };

    const handleSaveTopicsSettings = async () => {
      try {
        const next = await updateTopicsSettings(topicsDraft);
        setTopicsSettingsState(next);
        await Promise.all([loadLogsBlock(), loadTopicsBlock()]);
        flash('success', '资讯情报站设置已保存');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '保存失败');
      }
    };

    const handleSaveHandbookSettings = async () => {
      try {
        const next = await updateHandbookSettings({
          defaultTags: handbookDraft.defaultTagsText.split(/[，,]/).map((item) => item.trim()).filter(Boolean),
          defaultCategory: handbookDraft.defaultCategory,
          allowTaskSource: handbookDraft.allowTaskSource,
          allowAnalysisSource: handbookDraft.allowAnalysisSource,
          visibilityBoundary: handbookDraft.visibilityBoundary,
        });
        setHandbookSettingsState(next);
        await loadLogsBlock();
        flash('success', '成长手册设置已保存');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '保存失败');
      }
    };

    const handleSaveSystemAdminSettings = async () => {
      try {
        const next = await updateSystemAdminSettings(systemAdminDraft);
        setSystemAdminSettingsState(next);
        await loadLogsBlock();
        flash('success', '系统权限规则已保存');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '保存失败');
      }
    };

    const handlePickBrandLogo = async (file: File) => {
      const normalized = await normalizeBrandLogoFile(file);
      setSystemAdminDraft((prev) => ({ ...prev, brandLogoDataUrl: normalized }));
    };

    const handleSaveBrandLogo = async () => {
      setIsSavingBrandLogo(true);
      try {
        const next = await updateSystemAdminSettings({
          brandLogoDataUrl: systemAdminDraft.brandLogoDataUrl || '',
        });
        setSystemAdminSettingsState(next);
        setSystemAdminDraft(next);
        await loadLogsBlock();
        flash('success', next.brandLogoDataUrl ? '品牌 Logo 已保存' : '品牌 Logo 已清空');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '品牌 Logo 保存失败');
      } finally {
        setIsSavingBrandLogo(false);
      }
    };

    const handleSaveOrgFeishuIntegration = async (payload: OrgFeishuIntegrationPayload) => {
      setIsSavingOrgFeishuIntegration(true);
      try {
        const next = await saveOrgFeishuIntegration(payload);
        setOrgFeishuIntegrationState(next);
        await Promise.all([
          loadOrgMembershipBlock().catch(() => DEFAULT_ORG_MEMBERSHIP_SUMMARY),
          loadFeishuDeliveryProfileBlock().catch(() => DEFAULT_FEISHU_DELIVERY_PROFILE),
          loadLogsBlock(),
        ]);
        flash('success', next.enabled ? '组织飞书接入已验证并生效' : (next.lastValidationMessage || '组织飞书接入保存完成'));
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '组织飞书接入保存失败');
        throw error;
      } finally {
        setIsSavingOrgFeishuIntegration(false);
      }
    };

    const handleSaveOrgDingtalkFinanceIntegration = async (payload: OrgDingtalkFinanceIntegrationPayload) => {
      setIsSavingOrgDingtalkFinanceIntegration(true);
      try {
        const next = await saveOrgDingtalkFinanceIntegration(payload);
        setOrgDingtalkFinanceIntegrationState(next);
        await loadLogsBlock();
        flash('success', next.enabled ? '组织钉钉财务接入已验证并保存' : (next.lastValidationMessage || '组织钉钉财务接入已保存'));
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '组织钉钉财务接入保存失败');
        throw error;
      } finally {
        setIsSavingOrgDingtalkFinanceIntegration(false);
      }
    };

    const handleSaveFeishuInputMemory = async (payload: LocalInputMemory['feishuIntegration']) => {
      const nextLocalInputMemory = await saveFeishuInputMemory({
        rememberInputs: payload.rememberInputs,
        appId: payload.appId,
        appSecret: payload.appSecret,
      });
      setLocalInputMemoryState(nextLocalInputMemory);
    };

    const handleSaveFeishuDeliveryProfile = async (payload: { mobile?: string | null }) => {
      setIsSavingFeishuDeliveryProfile(true);
      try {
        const next = await saveFeishuDeliveryProfile(payload);
        setFeishuDeliveryProfileState(next);
        await loadLogsBlock();
        flash('success', next.readyForNotifications ? '飞书接收手机号已保存并匹配成功' : '飞书接收手机号已保存');
        return next;
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '保存飞书接收手机号失败');
        throw error;
      } finally {
        setIsSavingFeishuDeliveryProfile(false);
      }
    };

    const handleSaveWorkObjectMode = async (mode: 'client' | 'project') => {
      if (hasOrganizationTerminologyScope && currentSessionUser?.primaryRole !== 'admin') {
        flash('info', '加入组织后，只有管理员可以调整术语模式。当前界面已按组织配置生效。');
        return;
      }
      const target = hasOrganizationTerminologyScope ? 'organization' : 'local';
      try {
        await updateWorkObjectTerminology({ mode, target });
        await Promise.all([loadSettingsBlock(), loadWorkObjectTerminologyBlock()]);
        flash('success', target === 'organization' ? '组织术语已更新' : '本机术语已更新');
      } catch (error) {
        flash('error', error instanceof Error ? error.message : '保存术语模式失败');
      }
    };

    const sectionGroups: Array<{ group: string; items: Array<{ key: SettingsSectionKey; label: string; icon: typeof Settings; helper: string }> }> = [
      {
        group: '账户与服务',
        items: [
          { key: 'overview', label: '账户与AI', icon: Settings, helper: '云端接入、AI 模型、飞书协作、备份与日志' },
        ],
      },
      {
        group: '组织管理',
        items: [
          { key: 'system_admin', label: '组织与权限', icon: ShieldAlert, helper: '组织架构、邀请码、负责人绑定' },
          { key: 'org_dna', label: '组织 DNA', icon: FileBadge, helper: '组织级知识底座' },
        ],
      },
      {
        group: '功能设置',
        items: [
          { key: 'tasks', label: '任务与日程', icon: CheckSquare, helper: '任务清单、复盘规则' },
          { key: 'client_workspace', label: terminology.workspaceLabel, icon: Briefcase, helper: '聊天、会议、目标' },
          { key: 'topics', label: '资讯情报站', icon: Newspaper, helper: '抓取与转任务' },
          { key: 'handbook', label: '成长手册', icon: BookOpen, helper: '沉淀规则' },
        ],
      },
      {
        group: '运维与排查',
        items: [
          { key: 'system_logs', label: '系统日志', icon: Activity, helper: '运行日志、错误排查、导出' },
        ],
      },
    ];
    // Flatten for backward compatibility
    const sectionItems = sectionGroups.flatMap((g) => g.items);

    const orgSectionMeta: Record<Extract<SettingsSectionKey, 'org_overview' | 'org_departments' | 'org_people' | 'org_rules'>, { tab: OrgModelTab }> = {
      org_overview: {
        tab: 'overview',
      },
      org_departments: {
        tab: 'departments',
      },
      org_people: {
        tab: 'people',
      },
      org_rules: {
        tab: 'rules',
      },
    };

    const ChangePasswordCard = ({ flash: flashMsg }: { flash: (type: 'success' | 'error', msg: string) => void }) => {
      const newPwValid = changePwForm.newPassword.length >= 8;
      const confirmMatch = changePwForm.newPassword === changePwForm.confirmPassword;
      const canSubmit = changePwForm.currentPassword.trim() && newPwValid && confirmMatch && !changePwSubmitting;
      const handleChangePw = async () => {
        setChangePwError('');
        setChangePwSubmitting(true);
        try {
          await changePassword({ currentPassword: changePwForm.currentPassword, newPassword: changePwForm.newPassword });
          flashMsg('success', '密码修改成功');
          setChangePwForm({ currentPassword: '', newPassword: '', confirmPassword: '' });
        } catch (error) {
          setChangePwError(error instanceof Error ? error.message : '密码修改失败');
        } finally {
          setChangePwSubmitting(false);
        }
      };
      const pwInputType = changePwShowPassword ? 'text' : 'password';
      return (
        <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-4">
          <div>
            <h2 className="text-[16px] font-bold text-gray-900">修改密码</h2>
            <p className="text-[12px] text-gray-500 mt-1">修改当前账号的登录密码。新密码至少 8 位。</p>
          </div>
          <input type={pwInputType} value={changePwForm.currentPassword} onChange={(e) => setChangePwForm((p) => ({ ...p, currentPassword: e.target.value }))} placeholder="当前密码" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] outline-none" />
          <div>
            <input type={pwInputType} value={changePwForm.newPassword} onChange={(e) => setChangePwForm((p) => ({ ...p, newPassword: e.target.value }))} placeholder="新密码（至少 8 位）" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] outline-none" />
            {changePwForm.newPassword && !newPwValid && <p className="text-[12px] text-red-500 mt-1 px-1">密码至少需要 8 位</p>}
          </div>
          <div>
            <input type={pwInputType} value={changePwForm.confirmPassword} onChange={(e) => setChangePwForm((p) => ({ ...p, confirmPassword: e.target.value }))} placeholder="确认新密码" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] outline-none" />
            {changePwForm.confirmPassword && !confirmMatch && <p className="text-[12px] text-red-500 mt-1 px-1">两次输入的密码不一致</p>}
          </div>
          <label className="flex items-center gap-2 text-[13px] font-medium text-gray-700">
            <input type="checkbox" checked={changePwShowPassword} onChange={(e) => setChangePwShowPassword(e.target.checked)} />
            显示密码
          </label>
          {changePwError && <p className="text-[13px] text-red-600 bg-red-50 border border-red-100 rounded-2xl px-4 py-3">{changePwError}</p>}
          <Button primary onClick={() => void handleChangePw()} disabled={!canSubmit}>
            {changePwSubmitting ? <RefreshCw size={16} className="animate-spin" /> : <ShieldAlert size={16} />}
            确认修改密码
          </Button>
        </div>
      );
    };

    const AccountProfileCard = () => {
      const cardIsLocal = isLocalSession;
      const canSubmit =
        !cardIsLocal
        && !profileSubmitting
        && Boolean(profileDraft.fullName?.trim())
        && Boolean(profileDraft.email?.trim())
        && (
          profileDraft.fullName?.trim() !== (currentSessionUser?.fullName || '')
          || profileDraft.email?.trim() !== (currentSessionUser?.email || '')
        );
      return (
        <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-4">
          <div>
            <h2 className="text-[16px] font-bold text-gray-900">基本信息</h2>
            <p className="text-[12px] text-gray-500 mt-1">
              {cardIsLocal
                ? '当前还是本机模式。连接云端后，这里会显示并允许修改姓名 / 昵称、邮箱等账号信息。'
                : '登录云端后，你可以在这里维护姓名 / 昵称和邮箱，密码修改放在下面单独处理。'}
            </p>
          </div>
          <input
            value={cardIsLocal ? '' : (profileDraft.fullName || '')}
            onChange={(event) => setProfileDraft((prev) => ({ ...prev, fullName: event.target.value }))}
            placeholder={cardIsLocal ? '登录后显示姓名 / 昵称' : '姓名 / 昵称'}
            className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] outline-none disabled:text-gray-400 disabled:bg-gray-100"
            disabled={cardIsLocal}
          />
          <input
            value={cardIsLocal ? '' : (profileDraft.email || '')}
            onChange={(event) => setProfileDraft((prev) => ({ ...prev, email: event.target.value }))}
            placeholder={cardIsLocal ? '登录后显示邮箱' : '邮箱'}
            className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] outline-none disabled:text-gray-400 disabled:bg-gray-100"
            disabled={cardIsLocal}
          />
          {!cardIsLocal && profileMessage && (
            <p className={`rounded-2xl border px-4 py-3 text-[13px] ${profileMessage.includes('已更新') ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-red-200 bg-red-50 text-red-600'}`}>
              {profileMessage}
            </p>
          )}
          {cardIsLocal ? (
            <Button primary onClick={() => openCloudAuthModal('login')}>
              <ShieldAlert size={16} /> 注册 / 登录
            </Button>
          ) : (
            <Button primary onClick={() => void handleSaveProfile()} disabled={!canSubmit}>
              {profileSubmitting ? <RefreshCw size={16} className="animate-spin" /> : <User size={16} />}
              保存基本信息
            </Button>
          )}
        </div>
      );
    };

    const renderOverviewSection = () => (
      <div className="space-y-6">
        {(() => {
          const configuredCloudUrl = settingsState?.cloudApiUrl?.trim() || '';
          const cloudVendorLabel = inferCloudVendorLabel(configuredCloudUrl);
          const cloudStatusLabel = isLocalSession ? '未接入云端' : '已接入云端';
          const cloudStatusTone = isLocalSession
            ? 'bg-amber-50 text-amber-700 border border-amber-100'
            : 'bg-emerald-50 text-emerald-700 border border-emerald-100';
          const cloudStatusDescription = isLocalSession
            ? (configuredCloudUrl
              ? '当前仍是本机模式。下面显示的是已配置的云端目标，但这不代表已经接入成功。'
              : '当前仍是本机模式，且还没有可识别的云端目标。')
            : '当前账号已经接入云端，任务协作、组织能力与跨设备同步都会优先走云端链路。';
          const cloudOrgLabel = !isLocalSession
            ? (orgMembershipState.organizationName || currentSessionUser?.organizationId || '已连接组织')
            : '接入云端后显示';
          return (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-[16px] font-bold text-gray-900">接入云端</h2>
                <p className="text-[12px] text-gray-500 mt-1">{cloudStatusDescription}</p>
              </div>
              <span className={`shrink-0 rounded-full px-3 py-1.5 text-[11px] font-bold ${cloudStatusTone}`}>
                {cloudStatusLabel}
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
                <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">{isLocalSession ? '已配置云厂商' : '已接入厂商'}</p>
                <p className="text-[13px] font-bold text-slate-900">{cloudVendorLabel}</p>
                <p className="text-[12px] text-slate-600 mt-1">
                  {configuredCloudUrl ? '这表示当前软件准备连接到哪一类云端服务。' : '当前还没有读取到明确的云端地址。'}
                </p>
              </div>
              <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
                <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">当前组织</p>
                <p className="text-[13px] font-bold text-slate-900">{cloudOrgLabel}</p>
                <p className="text-[12px] text-slate-600 mt-1">
                  {isLocalSession ? '仅在真正接入云端后，才会出现组织上下文。' : '当前这套云端会话所属的组织环境。'}
                </p>
              </div>
            </div>
            <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
              <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">云服务器地址</p>
              <p className="text-[12px] text-slate-700 break-all font-medium">{configuredCloudUrl || '未配置'}</p>
            </div>
          </div>

          <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-[16px] font-bold text-gray-900">接入AI</h2>
                <p className="text-[12px] text-gray-500 mt-1">这里只处理模型与 API Key，不代表已经接入云端。只有管理员可写。</p>
              </div>
              <Button primary onClick={() => void handleSaveAiSettings()} disabled={!canManageSensitiveSettings}>
                <Bot size={16} /> 保存AI接入
              </Button>
            </div>
            <select
              value={draft.aiProvider}
              onChange={(event) => {
                const nextProvider = event.target.value as keyof typeof providerDefaultModels;
                setDraft((prev) => ({ ...prev, aiProvider: nextProvider, aiModel: providerDefaultModels[nextProvider] }));
              }}
              className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none"
              disabled={!canManageSensitiveSettings}
            >
              <option value="doubao">豆包 Seed 2.0 Pro（火山方舟）</option>
            </select>
            <input value={draft.aiModel} onChange={(event) => setDraft((prev) => ({ ...prev, aiModel: event.target.value }))} placeholder="模型名" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none" disabled={!canManageSensitiveSettings} />
            <input type="password" value={draft.apiKey} onChange={(event) => setDraft((prev) => ({ ...prev, apiKey: event.target.value }))} placeholder="API Key" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none" disabled={!canManageSensitiveSettings} />
            <label className="flex items-center gap-2 text-[12px] font-medium text-gray-700">
              <input
                type="checkbox"
                checked={rememberAiInputKey}
                onChange={(event) => setRememberAiInputKey(event.target.checked)}
                disabled={!canManageSensitiveSettings}
              />
              记住当前 API Key（仅本机）
            </label>
            {!canManageSensitiveSettings && <p className="text-[12px] text-amber-700 bg-amber-50 border border-amber-100 rounded-2xl px-4 py-3">当前账号只能查看 AI 接入状态，不能修改密钥和模型配置。</p>}
          </div>
        </div>
          );
        })()}

        <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-[16px] font-bold text-gray-900">工作对象术语</h2>
              <p className="text-[12px] text-gray-500 mt-1">
                {hasOrganizationTerminologyScope
                  ? (canEditWorkObjectMode
                    ? '当前术语会作用于整个组织。保存后，所有组织成员都会统一看到同一种叫法。'
                    : '当前已加入组织，术语由组织管理员统一维护。你这里看到的是组织当前正在生效的叫法。')
                  : '当前默认按项目制显示；如需改成客户制，可以在这里手动切换。'}
              </p>
            </div>
            <span className={`shrink-0 rounded-full px-3 py-1.5 text-[11px] font-bold ${hasOrganizationTerminologyScope ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' : 'bg-slate-50 text-slate-700 border border-slate-200'}`}>
              {hasOrganizationTerminologyScope ? (canEditWorkObjectMode ? '组织配置' : '组织配置（只读）') : '本机配置'}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <button
              type="button"
              onClick={() => void handleSaveWorkObjectMode('client')}
              disabled={!canEditWorkObjectMode}
              className={`rounded-2xl border p-4 text-left transition ${terminology.effectiveMode === 'client' ? 'border-blue-200 bg-blue-50/60' : 'border-gray-200 bg-gray-50 hover:border-gray-300'} disabled:opacity-60`}
            >
              <p className="text-[13px] font-bold text-gray-900">客户制</p>
              <p className="mt-2 text-[12px] text-gray-500">适合围绕服务对象、合作对象来组织资料、事件线和任务。</p>
            </button>
            <button
              type="button"
              onClick={() => void handleSaveWorkObjectMode('project')}
              disabled={!canEditWorkObjectMode}
              className={`rounded-2xl border p-4 text-left transition ${terminology.effectiveMode === 'project' ? 'border-blue-200 bg-blue-50/60' : 'border-gray-200 bg-gray-50 hover:border-gray-300'} disabled:opacity-60`}
            >
              <p className="text-[13px] font-bold text-gray-900">项目制</p>
              <p className="mt-2 text-[12px] text-gray-500">适合围绕项目、计划、行动单元来组织资料与任务，也是当前默认模式。</p>
            </button>
          </div>
          <p className="text-[12px] text-gray-500">
            当前界面会显示为：{terminology.workspaceLabel}、{terminology.associateLabel}、{terminology.recentLabel}。
          </p>
          {hasOrganizationTerminologyScope && !canEditWorkObjectMode && (
            <p className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-[12px] text-amber-700">
              你已经加入组织，术语模式只能由管理员统一调整，本机不会再单独覆盖组织配置。
            </p>
          )}
        </div>

        {isLocalSession ? (
          AccountProfileCard()
        ) : (
          <>
            {AccountProfileCard()}
            {ChangePasswordCard({ flash })}
          </>
        )}

        <FeishuOrgIntegrationPanel
          sessionMode={authState.sessionMode === 'cloud' ? 'cloud' : 'local'}
          membership={orgMembershipState}
          integration={orgFeishuIntegrationState}
          deliveryProfile={feishuDeliveryProfileState}
          currentUserName={currentSessionUser?.fullName || null}
          saveBusy={isSavingOrgFeishuIntegration}
          savePhoneBusy={isSavingFeishuDeliveryProfile}
          rememberedInputs={localInputMemoryState.feishuIntegration}
          onSaveIntegration={handleSaveOrgFeishuIntegration}
          onSaveRememberedInputs={handleSaveFeishuInputMemory}
          onSaveDeliveryProfile={handleSaveFeishuDeliveryProfile}
          onOpenOrganizationSetup={() => setSettingsSection('system_admin')}
          onOpenCloudAuth={() => openCloudAuthModal('login')}
        />

        <DingtalkFinanceIntegrationPanel
          sessionMode={authState.sessionMode === 'cloud' ? 'cloud' : 'local'}
          membership={orgMembershipState}
          integration={orgDingtalkFinanceIntegrationState}
          saveBusy={isSavingOrgDingtalkFinanceIntegration}
          canManage={canManageSensitiveSettings}
          onSaveIntegration={handleSaveOrgDingtalkFinanceIntegration}
          onOpenOrganizationSetup={() => setSettingsSection('system_admin')}
          onOpenCloudAuth={() => openCloudAuthModal('login')}
        />

        <BrandLogoSettingsCard
          logoDataUrl={systemAdminDraft.brandLogoDataUrl || null}
          canManage={canManageSensitiveSettings}
          busy={isSavingBrandLogo}
          hasUnsavedChange={hasBrandLogoDraftChange}
          onPickLogo={handlePickBrandLogo}
          onClearDraft={() => setSystemAdminDraft((prev) => ({ ...prev, brandLogoDataUrl: null }))}
          onSave={handleSaveBrandLogo}
        />

        <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
          <h2 className="text-[16px] font-bold text-gray-900 mb-4">系统概况</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <div className="rounded-2xl bg-gray-50 border border-gray-100 p-4">
              <p className="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-2">AI 状态</p>
              <p className="text-[12px] text-gray-700">{health?.ai.detail || '未加载'}</p>
            </div>
            <div className="rounded-2xl bg-gray-50 border border-gray-100 p-4">
              <p className="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-2">{terminology.statsLabel} / 任务</p>
              <p className="text-[12px] text-gray-700">{health?.stats.workObjects || health?.stats.clients || 0} 个{terminology.statsLabel}，{health?.stats.tasks || 0} 条任务</p>
            </div>
            <div className="rounded-2xl bg-gray-50 border border-gray-100 p-4">
              <p className="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-2">资讯 / 手册</p>
              <p className="text-[12px] text-gray-700">{health?.stats.topics || 0} 条资讯候选，{health?.stats.handbookEntries || 0} 条沉淀</p>
            </div>
            <div className="rounded-2xl bg-gray-50 border border-gray-100 p-4">
              <p className="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-2">最近备份</p>
              <p className="text-[12px] text-gray-700">{settingsState?.lastBackupAt || '尚未备份'}</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
            <h2 className="text-[16px] font-bold text-gray-900 mb-4">备份与旧数据导入</h2>
            <div className="flex flex-wrap gap-3 mb-4">
              <Button onClick={() => { void createBackup().then(async (backup) => { await loadSettingsBlock(); flash('success', `已生成备份：${backup.backupPath.split('/').pop()}`); }).catch((error) => flash('error', error instanceof Error ? error.message : '备份失败')); }}>
                <Database size={16} /> 立即备份
              </Button>
              <Button onClick={() => { void selectFolderBridge().then((folder) => { if (!folder) return; void scanLegacy(folder).then((result) => setLegacyScanResult(result)).catch((error) => flash('error', error instanceof Error ? error.message : '扫描失败')); }); }}>
                <FolderOpen size={16} /> 扫描旧数据
              </Button>
            </div>
            {legacyScanResult && (
              <div className="space-y-3">
                <p className="text-[12px] font-bold text-gray-900">{legacyScanResult.path}</p>
                <p className="text-[12px] text-gray-500">{legacyScanResult.message}</p>
                <div className="flex flex-col md:flex-row gap-3">
                  <select value={legacyImportClientId} onChange={(event) => setLegacyImportClientId(event.target.value)} className="flex-1 bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none">
                    <option value="">{`选择导入目标${terminology.singularLabel}`}</option>
                    {clients.map((client) => (
                      <option key={client.id} value={client.id}>{client.name}</option>
                    ))}
                  </select>
                  <Button onClick={() => void handleImportLegacyEntries()} disabled={isImportingLegacy || !importableLegacyEntries.length}>
                    {isImportingLegacy ? <RefreshCw size={16} className="animate-spin" /> : <UploadCloud size={16} />}
                    导入可导入文件
                  </Button>
                </div>
              </div>
            )}
          </div>

          <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-[16px] font-bold text-gray-900">演示数据</h2>
                <p className="text-[12px] text-gray-500 mt-1">只在需要演示时手动载入，正式使用可以随时清空。</p>
              </div>
              <span className={`text-[11px] font-bold px-3 py-1.5 rounded-full ${settingsState?.demoDataLoaded ? 'bg-amber-50 text-amber-700' : 'bg-gray-100 text-gray-500'}`}>
                {settingsState?.demoDataLoaded ? '已载入演示数据' : '未载入演示数据'}
              </span>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => { void loadDemoData().then(async () => { await loadAll('client_cffc'); flash('success', '演示数据已载入'); }).catch((error) => flash('error', error instanceof Error ? error.message : '载入失败')); }}>
                <Sparkles size={16} /> 载入演示数据
              </Button>
              <Button onClick={() => { void clearDemoData().then(async () => { await loadAll(); flash('success', '演示数据已清空'); }).catch((error) => flash('error', error instanceof Error ? error.message : '清空失败')); }}>
                <X size={16} /> 清空演示数据
              </Button>
            </div>
          </div>
        </div>

        <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
          <h2 className="text-[16px] font-bold text-gray-900 mb-4">最近操作日志</h2>
          <div className="space-y-3 max-h-[420px] overflow-y-auto">
            {logs.map((log) => (
              <div key={log.id} className="border border-gray-100 rounded-2xl p-4">
                <div className="flex justify-between items-center gap-4 mb-2">
                  <p className="text-[13px] font-bold text-gray-900">{log.action}</p>
                  <span className="text-[10px] font-bold text-gray-400">{new Date(log.createdAt).toLocaleString('zh-CN', { hour12: false })}</span>
                </div>
                <p className="text-[12px] text-gray-500">{log.actorName} · {log.entityType} · {log.entityId}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    );

    const renderOrgDnaSection = () => (
      <div className="space-y-6">
        <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
          <h2 className="text-[16px] font-bold text-gray-900">组织 DNA</h2>
          <p className="text-[12px] text-gray-500 mt-2 leading-relaxed">
            这里是整个软件的组织级知识主库。系统在 AI 型能力中会优先注入这层上下文，再叠加{terminology.singularLabel}补充 DNA 和当前模块材料。
          </p>
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {ORGANIZATION_DNA_MODULES.map((meta) => {
            const module = organizationDnaModules.find((item) => item.moduleKey === meta.moduleKey);
            return (
              <div key={meta.moduleKey} className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-[16px] font-bold text-gray-900">{meta.title}</h3>
                    <p className="text-[12px] text-gray-500 mt-1">{meta.helper}</p>
                  </div>
                  <Button onClick={() => void handleUploadOrgDna(meta.moduleKey)} disabled={!canEditOrgDna || orgDnaSavingKey === meta.moduleKey}>
                    {orgDnaSavingKey === meta.moduleKey ? <RefreshCw size={16} className="animate-spin" /> : <UploadCloud size={16} />}
                    {module?.hasDocument ? '替换文档' : '上传文档'}
                  </Button>
                </div>
                <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4 text-[12px] text-slate-700 space-y-2">
                  <p><span className="font-bold text-slate-900">状态：</span>{module?.hasDocument ? '已上传当前生效稿' : '尚未上传'}</p>
                  <p><span className="font-bold text-slate-900">文件：</span>{module?.fileName || '未上传'}</p>
                  <p><span className="font-bold text-slate-900">更新：</span>{module?.updatedAt || '未更新'}{module?.updatedBy ? ` · ${module.updatedBy}` : ''}</p>
                </div>
                <div className="rounded-2xl bg-blue-50/60 border border-blue-100 p-4">
                  <p className="text-[12px] font-bold text-[#335CFF] mb-2">摘要</p>
                  <p className="text-[12px] text-slate-700 leading-relaxed whitespace-pre-wrap">{module?.summary || '上传后，这里会显示提炼后的摘要。'}</p>
                </div>
                <details className="rounded-2xl border border-gray-100 bg-gray-50 px-4 py-3">
                  <summary className="cursor-pointer text-[12px] font-bold text-gray-700">查看原文内容</summary>
                  <pre className="mt-3 whitespace-pre-wrap text-[12px] text-gray-600 max-h-[220px] overflow-y-auto">{module?.markdownContent || '暂无原文'}</pre>
                </details>
                <details className="rounded-2xl border border-gray-100 bg-gray-50 px-4 py-3">
                  <summary className="cursor-pointer text-[12px] font-bold text-gray-700">查看解析后的纯文本</summary>
                  <div className="mt-3 whitespace-pre-wrap text-[12px] text-gray-600 max-h-[220px] overflow-y-auto">{module?.normalizedText || '暂无解析文本'}</div>
                </details>
              </div>
            );
          })}
        </div>
      </div>
    );

    const renderTasksSection = () => (
      <div className="space-y-6">
        <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
          <div className="flex items-start justify-between gap-4 mb-5">
            <div>
              <h2 className="text-[16px] font-bold text-gray-900">任务默认规则</h2>
              <p className="text-[12px] text-gray-500 mt-1">统一任务优先级、日期策略、视图偏好和复盘入口。</p>
            </div>
            <Button primary onClick={() => void handleSaveTaskSettings()} disabled={!canEditBusinessSettings}>
              <Settings size={16} /> 保存任务设置
            </Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <select value={taskSettingsDraft.defaultPriority} onChange={(event) => setTaskSettingsDraft((prev) => ({ ...prev, defaultPriority: event.target.value as TaskSettings['defaultPriority'] }))} className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none" disabled={!canEditBusinessSettings}>
              <option value="low">默认低优先级</option>
              <option value="normal">默认普通优先级</option>
              <option value="high">默认高优先级</option>
            </select>
            <select value={taskSettingsDraft.defaultDueDatePreset} onChange={(event) => setTaskSettingsDraft((prev) => ({ ...prev, defaultDueDatePreset: event.target.value as TaskSettings['defaultDueDatePreset'] }))} className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none" disabled={!canEditBusinessSettings}>
              <option value="today">默认日期：今天</option>
              <option value="none">默认日期：无日期</option>
            </select>
            <select value={taskSettingsDraft.defaultViewMode} onChange={(event) => setTaskSettingsDraft((prev) => ({ ...prev, defaultViewMode: event.target.value as TaskSettings['defaultViewMode'] }))} className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none" disabled={!canEditBusinessSettings}>
              <option value="inbox">默认打开：协作收件箱</option>
              <option value="list">默认打开：清单列表</option>
              <option value="calendar">默认打开：我的月历</option>
              <option value="event_lines">默认打开：事件线</option>
              <option value="review">默认打开：周复盘</option>
            </select>
            <select value={taskSettingsDraft.listSortMode} onChange={(event) => setTaskSettingsDraft((prev) => ({ ...prev, listSortMode: event.target.value as TaskSettings['listSortMode'] }))} className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none" disabled={!canEditBusinessSettings}>
              <option value="manual">清单排序：按时间先后</option>
              <option value="dueDate">清单排序：按截止时间</option>
              <option value="priority">清单排序：按优先级</option>
            </select>
            <select value={taskSettingsDraft.defaultReviewScope} onChange={(event) => setTaskSettingsDraft((prev) => ({ ...prev, defaultReviewScope: event.target.value as TaskSettings['defaultReviewScope'] }))} className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none" disabled={!canEditBusinessSettings}>
              <option value="work">周复盘默认进入组织复盘</option>
              <option value="personal">周复盘默认进入成长复盘</option>
            </select>
            <select value={taskSettingsDraft.showCompletedTasks ? 'show' : 'hide'} onChange={(event) => setTaskSettingsDraft((prev) => ({ ...prev, showCompletedTasks: event.target.value === 'show' }))} className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none" disabled={!canEditBusinessSettings}>
              <option value="hide">清单默认隐藏已完成</option>
              <option value="show">清单默认显示已完成</option>
            </select>
            <select value={taskSettingsDraft.autoAssignSelf ? 'self' : 'empty'} onChange={(event) => setTaskSettingsDraft((prev) => ({ ...prev, autoAssignSelf: event.target.value === 'self' }))} className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none" disabled={!canEditBusinessSettings}>
              <option value="self">未选协作者时默认给自己</option>
              <option value="empty">未选协作者时先留空</option>
            </select>
          </div>
        </div>

        {currentSessionUser?.primaryRole === 'admin' && (
          <ReviewGovernanceSettingsPanel
            value={reviewGovernanceDraft}
            canEdit={canManageSensitiveSettings}
            availableMembers={availableReviewGovernanceMembers}
            isSaving={isSavingReviewGovernance}
            onChange={setReviewGovernanceDraft}
            onSave={() => void handleSaveReviewGovernance()}
          />
        )}

        <div className="space-y-6">
          <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
            <div className="flex items-start justify-between gap-4 mb-4">
              <div>
                <h2 className="text-[16px] font-bold text-gray-900">清单管理</h2>
                <p className="text-[12px] text-gray-500 mt-1">这里只维护任务清单名称和简介。删除清单后，其下任务会自动变成无清单。</p>
              </div>
              {editingListId && <button type="button" className="text-[12px] font-bold text-gray-400 hover:text-gray-700" onClick={resetListManager}>取消编辑</button>}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-[1fr_1.2fr_auto] gap-3">
              <input value={listManageDraft.name} onChange={(event) => setListManageDraft((prev) => ({ ...prev, name: event.target.value }))} placeholder="输入清单名称" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none" />
              <input value={listManageDraft.description} onChange={(event) => setListManageDraft((prev) => ({ ...prev, description: event.target.value }))} placeholder="输入清单简介（选填）" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none" />
              <Button
                primary
                className="rounded-2xl"
                onClick={() => void handleSaveTaskList()}
                disabled={!canManageOrgTaskList}
              >
                {editingListId ? '保存清单' : '新建清单'}
              </Button>
            </div>
            <div className="mt-5 space-y-3 max-h-[320px] overflow-y-auto pr-1">
              {taskLists.filter((list) => (list.scope || 'org') === 'org').map((list) => (
                <div key={list.id} className="border border-gray-100 rounded-2xl p-4 flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-[14px] font-bold text-gray-900">{list.name}</p>
                      {list.archivedAt && <span className="text-[10px] font-bold px-2 py-1 rounded-full bg-gray-100 text-gray-500">已归档</span>}
                    </div>
                    <p className="text-[12px] text-gray-500 mt-2">{list.description?.trim() || '暂无简介。'}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Button onClick={() => { setEditingListId(list.id); setListManageDraft({ name: list.name, description: list.description || '' }); }} disabled={!canManageOrgTaskList}>编辑</Button>
                    <Button onClick={() => void handleToggleTaskListArchived(list)} disabled={!canManageOrgTaskList}>{list.archivedAt ? '恢复' : '归档'}</Button>
                    <Button onClick={() => void handleDeleteTaskList(list)} disabled={!canManageOrgTaskList}>删除</Button>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    );

    const renderClientWorkspaceSection = () => (
      <div className="space-y-6">
        <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
          <div className="flex items-start justify-between gap-4 mb-5">
            <div>
              <h2 className="text-[16px] font-bold text-gray-900">{terminology.workspaceLabel}全局规则</h2>
              <p className="text-[12px] text-gray-500 mt-1">控制{terminology.workspaceLabel}聊天、会议发布到任务和{terminology.singularLabel}补充 DNA 的组织级规则。</p>
            </div>
            <Button primary onClick={() => void handleSaveClientWorkspaceSettings()} disabled={!canEditBusinessSettings}>
              <Settings size={16} /> 保存{terminology.workspaceLabel}设置
            </Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium flex items-center justify-between">
              聊天默认注入组织 DNA
              <input type="checkbox" checked={clientWorkspaceDraft.useOrgDnaInChat} onChange={(event) => setClientWorkspaceDraft((prev) => ({ ...prev, useOrgDnaInChat: event.target.checked }))} disabled={!canEditBusinessSettings} />
            </label>
            <label className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium flex items-center justify-between">
              知识问答默认注入组织 DNA
              <input type="checkbox" checked={clientWorkspaceDraft.useOrgDnaInKnowledgeQa} onChange={(event) => setClientWorkspaceDraft((prev) => ({ ...prev, useOrgDnaInKnowledgeQa: event.target.checked }))} disabled={!canEditBusinessSettings} />
            </label>
            <input value={clientWorkspaceDraft.defaultMeetingTitlePrefix} onChange={(event) => setClientWorkspaceDraft((prev) => ({ ...prev, defaultMeetingTitlePrefix: event.target.value }))} placeholder="会议标题默认前缀" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none" disabled={!canEditBusinessSettings} />
            <input value={clientWorkspaceDraft.defaultGoalQuarter} onChange={(event) => setClientWorkspaceDraft((prev) => ({ ...prev, defaultGoalQuarter: event.target.value }))} placeholder="目标默认季度，例如 2026 Q2" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none" disabled={!canEditBusinessSettings} />
            <select value={clientWorkspaceDraft.meetingPublishDefaultListId || ''} onChange={(event) => setClientWorkspaceDraft((prev) => ({ ...prev, meetingPublishDefaultListId: event.target.value || null }))} className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none" disabled={!canEditBusinessSettings}>
              <option value="">不额外指定清单</option>
              {activeTaskLists.map((list) => (
                <option key={list.id} value={list.id}>{list.name}</option>
              ))}
            </select>
            <select value={clientWorkspaceDraft.meetingPublishDefaultPriority} onChange={(event) => setClientWorkspaceDraft((prev) => ({ ...prev, meetingPublishDefaultPriority: event.target.value as ClientWorkspaceSettings['meetingPublishDefaultPriority'] }))} className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none" disabled={!canEditBusinessSettings}>
              <option value="low">会议任务默认低优先级</option>
              <option value="normal">会议任务默认普通优先级</option>
              <option value="high">会议任务默认高优先级</option>
            </select>
            <input value={clientWorkspaceDraft.clientDnaModeLabel} onChange={(event) => setClientWorkspaceDraft((prev) => ({ ...prev, clientDnaModeLabel: event.target.value }))} placeholder={`${terminology.singularLabel} DNA 显示文案`} className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none md:col-span-2" disabled={!canEditBusinessSettings} />
          </div>
        </div>
      </div>
    );

    const renderTopicsSection = () => (
      <div className="space-y-6">
        <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
          <div className="flex items-start justify-between gap-4 mb-5">
            <div>
              <h2 className="text-[16px] font-bold text-gray-900">资讯情报站规则</h2>
              <p className="text-[12px] text-gray-500 mt-1">集中管理抓取中文化、解析 gating、默认时间窗和任务指派策略。</p>
            </div>
            <Button primary onClick={() => void handleSaveTopicsSettings()} disabled={!canEditBusinessSettings}>
              <Settings size={16} /> 保存资讯设置
            </Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium flex items-center justify-between">
              抓回内容默认中文化
              <input type="checkbox" checked={topicsDraft.chineseOnly} onChange={(event) => setTopicsDraft((prev) => ({ ...prev, chineseOnly: event.target.checked }))} disabled={!canEditBusinessSettings} />
            </label>
            <label className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium flex items-center justify-between">
              解析完成前禁止查看解析 / 转任务
              <input type="checkbox" checked={topicsDraft.requireInsightBeforeActions} onChange={(event) => setTopicsDraft((prev) => ({ ...prev, requireInsightBeforeActions: event.target.checked }))} disabled={!canEditBusinessSettings} />
            </label>
            <label className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium flex items-center justify-between">
              候选解析默认注入组织 DNA
              <input type="checkbox" checked={topicsDraft.useOrgDnaForInsight} onChange={(event) => setTopicsDraft((prev) => ({ ...prev, useOrgDnaForInsight: event.target.checked }))} disabled={!canEditBusinessSettings} />
            </label>
            <label className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium flex items-center justify-between">
              转任务提炼默认注入组织 DNA
              <input type="checkbox" checked={topicsDraft.useOrgDnaForTaskPlan} onChange={(event) => setTopicsDraft((prev) => ({ ...prev, useOrgDnaForTaskPlan: event.target.checked }))} disabled={!canEditBusinessSettings} />
            </label>
            <select value={topicsDraft.defaultTimeRange} onChange={(event) => setTopicsDraft((prev) => ({ ...prev, defaultTimeRange: event.target.value }))} className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none" disabled={!canEditBusinessSettings}>
              <option value="1_day">默认时间窗：1 天</option>
              <option value="3_days">默认时间窗：3 天</option>
              <option value="7_days">默认时间窗：7 天</option>
              <option value="14_days">默认时间窗：14 天</option>
            </select>
            <select value={topicsDraft.defaultTaskOwnerMode} onChange={(event) => setTopicsDraft((prev) => ({ ...prev, defaultTaskOwnerMode: event.target.value as TopicsSettings['defaultTaskOwnerMode'] }))} className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none" disabled={!canEditBusinessSettings}>
              <option value="self">转任务默认指派给自己</option>
              <option value="empty">转任务默认不带负责人</option>
            </select>
            <input value={topicsDraft.defaultSourceStrategy} onChange={(event) => setTopicsDraft((prev) => ({ ...prev, defaultSourceStrategy: event.target.value }))} placeholder="默认来源策略" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none md:col-span-2" disabled={!canEditBusinessSettings} />
          </div>
        </div>
      </div>
    );

    const renderHandbookSection = () => (
      <div className="space-y-6">
        <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
          <div className="flex items-start justify-between gap-4 mb-5">
            <div>
              <h2 className="text-[16px] font-bold text-gray-900">成长手册规则</h2>
              <p className="text-[12px] text-gray-500 mt-1">统一默认标签、默认分类和组织沉淀 / 个人沉淀边界说明。</p>
            </div>
            <Button primary onClick={() => void handleSaveHandbookSettings()} disabled={!canEditBusinessSettings}>
              <Settings size={16} /> 保存成长手册设置
            </Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <input value={handbookDraft.defaultTagsText} onChange={(event) => setHandbookDraft((prev) => ({ ...prev, defaultTagsText: event.target.value }))} placeholder="默认标签，逗号分隔" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none" disabled={!canEditBusinessSettings} />
            <input value={handbookDraft.defaultCategory} onChange={(event) => setHandbookDraft((prev) => ({ ...prev, defaultCategory: event.target.value }))} placeholder="默认分类" className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-medium outline-none" disabled={!canEditBusinessSettings} />
            <label className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium flex items-center justify-between">
              允许从任务沉淀进入成长手册
              <input type="checkbox" checked={handbookDraft.allowTaskSource} onChange={(event) => setHandbookDraft((prev) => ({ ...prev, allowTaskSource: event.target.checked }))} disabled={!canEditBusinessSettings} />
            </label>
            <label className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] font-medium flex items-center justify-between">
              允许从分析结论沉淀进入成长手册
              <input type="checkbox" checked={handbookDraft.allowAnalysisSource} onChange={(event) => setHandbookDraft((prev) => ({ ...prev, allowAnalysisSource: event.target.checked }))} disabled={!canEditBusinessSettings} />
            </label>
            <select value={handbookDraft.visibilityBoundary} onChange={(event) => setHandbookDraft((prev) => ({ ...prev, visibilityBoundary: event.target.value }))} className="w-full bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 text-[13px] font-bold outline-none md:col-span-2" disabled={!canEditBusinessSettings}>
              <option value="organization_and_personal">组织沉淀与个人沉淀分开展示</option>
              <option value="organization_first">优先显示组织沉淀</option>
              <option value="personal_first">优先显示个人沉淀</option>
            </select>
          </div>
        </div>
      </div>
    );

    const EmployeeReviewPanel = () => {
      const pendingList = employeeReviews.filter((e) => e.accountStatus === 'pending');
      const rejectedList = employeeReviews.filter((e) => e.accountStatus === 'rejected');
      const disabledList = employeeReviews.filter((e) => e.accountStatus === 'disabled');

      const handleApprove = async (id: string) => {
        setEmployeeReviewBusyId(id);
        try {
          await approveEmployee(id, { role: 'employee' });
          flash('success', '已批准该员工注册');
          await loadEmployeeReviewBlock();
        } catch (error) {
          flash('error', error instanceof Error ? error.message : '操作失败');
        } finally {
          setEmployeeReviewBusyId(null);
        }
      };
      const handleReject = async (id: string) => {
        setEmployeeReviewBusyId(id);
        try {
          await rejectEmployeeReview(id, { reason: employeeRejectReason || '账号未通过审核，请联系管理员。' });
          flash('success', '已驳回该注册申请');
          setRejectingEmployeeId(null);
          setEmployeeRejectReason('');
          await loadEmployeeReviewBlock();
        } catch (error) {
          flash('error', error instanceof Error ? error.message : '操作失败');
        } finally {
          setEmployeeReviewBusyId(null);
        }
      };
      const handleDisable = async (id: string) => {
        if (!window.confirm('确定要停用该账号吗？')) return;
        setEmployeeReviewBusyId(id);
        try {
          await disableEmployee(id);
          flash('success', '已停用该账号');
          await loadEmployeeReviewBlock();
        } catch (error) {
          flash('error', error instanceof Error ? error.message : '操作失败');
        } finally {
          setEmployeeReviewBusyId(null);
        }
      };
      const handleResetPw = async (id: string) => {
        if (resetPwValue.length < 8) { flash('error', '新密码至少 8 位'); return; }
        setEmployeeReviewBusyId(id);
        try {
          await adminResetPassword(id, { newPassword: resetPwValue });
          flash('success', '密码已重置');
          setResetPwEmployeeId(null);
          setResetPwValue('');
        } catch (error) {
          flash('error', error instanceof Error ? error.message : '操作失败');
        } finally {
          setEmployeeReviewBusyId(null);
        }
      };

      const renderEmployeeRow = (employee: typeof employeeReviews[number], actions: React.ReactNode) => (
        <div key={employee.id} className="flex items-center justify-between gap-4 rounded-2xl border border-gray-100 bg-gray-50 px-4 py-3">
          <div className="min-w-0">
            <p className="text-[13px] font-bold text-gray-900 truncate">{employee.fullName}</p>
            <p className="text-[12px] text-gray-500 truncate">{employee.email}{employee.departmentName ? ` · ${employee.departmentName}` : ''}{employee.jobTitle ? ` · ${employee.jobTitle}` : ''}</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>
        </div>
      );

      if (pendingList.length === 0 && rejectedList.length === 0 && disabledList.length === 0) return null;

      return (
        <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-5">
          <div>
            <h2 className="text-[16px] font-bold text-gray-900">员工账号审核</h2>
            <p className="text-[12px] text-gray-500 mt-1">审批注册申请、驳回、停用或重置密码。</p>
          </div>
          {pendingList.length > 0 && (
            <div className="space-y-2">
              <p className="text-[12px] font-bold text-amber-600 uppercase tracking-widest">待审核 ({pendingList.length})</p>
              {pendingList.map((employee) => renderEmployeeRow(employee, (
                <>
                  <button type="button" disabled={employeeReviewBusyId === employee.id} onClick={() => void handleApprove(employee.id)} className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-[12px] font-bold text-emerald-700 hover:bg-emerald-100 disabled:opacity-50">批准</button>
                  {rejectingEmployeeId === employee.id ? (
                    <div className="flex items-center gap-1">
                      <input value={employeeRejectReason} onChange={(e) => setEmployeeRejectReason(e.target.value)} placeholder="驳回原因（可选）" className="w-40 rounded-xl border border-gray-200 bg-white px-2 py-1.5 text-[12px] outline-none" />
                      <button type="button" disabled={employeeReviewBusyId === employee.id} onClick={() => void handleReject(employee.id)} className="rounded-xl border border-red-200 bg-red-50 px-3 py-1.5 text-[12px] font-bold text-red-700 hover:bg-red-100 disabled:opacity-50">确认驳回</button>
                      <button type="button" onClick={() => { setRejectingEmployeeId(null); setEmployeeRejectReason(''); }} className="rounded-xl border border-gray-200 bg-white px-2 py-1.5 text-[12px] text-gray-500">取消</button>
                    </div>
                  ) : (
                    <button type="button" onClick={() => setRejectingEmployeeId(employee.id)} className="rounded-xl border border-red-200 bg-red-50 px-3 py-1.5 text-[12px] font-bold text-red-700 hover:bg-red-100">驳回</button>
                  )}
                </>
              )))}
            </div>
          )}
          {rejectedList.length > 0 && (
            <div className="space-y-2">
              <p className="text-[12px] font-bold text-red-500 uppercase tracking-widest">已驳回 ({rejectedList.length})</p>
              {rejectedList.map((employee) => renderEmployeeRow(employee, (
                <span className="text-[12px] text-red-400">{employee.rejectedReason || '未通过'}</span>
              )))}
            </div>
          )}
          {disabledList.length > 0 && (
            <div className="space-y-2">
              <p className="text-[12px] font-bold text-gray-400 uppercase tracking-widest">已停用 ({disabledList.length})</p>
              {disabledList.map((employee) => renderEmployeeRow(employee, (
                <span className="text-[12px] text-gray-400">已停用</span>
              )))}
            </div>
          )}
          {employeeReviews.filter((e) => e.accountStatus === 'approved' && e.primaryRole !== 'admin').length > 0 && (
            <div className="space-y-2">
              <p className="text-[12px] font-bold text-gray-500 uppercase tracking-widest">在职员工管理</p>
              {employeeReviews.filter((e) => e.accountStatus === 'approved' && e.primaryRole !== 'admin').map((employee) => renderEmployeeRow(employee, (
                <>
                  {resetPwEmployeeId === employee.id ? (
                    <div className="flex items-center gap-1">
                      <input type="password" value={resetPwValue} onChange={(e) => setResetPwValue(e.target.value)} placeholder="新密码（≥8位）" className="w-36 rounded-xl border border-gray-200 bg-white px-2 py-1.5 text-[12px] outline-none" />
                      <button type="button" disabled={employeeReviewBusyId === employee.id || resetPwValue.length < 8} onClick={() => void handleResetPw(employee.id)} className="rounded-xl border border-blue-200 bg-blue-50 px-3 py-1.5 text-[12px] font-bold text-blue-700 hover:bg-blue-100 disabled:opacity-50">确认</button>
                      <button type="button" onClick={() => { setResetPwEmployeeId(null); setResetPwValue(''); }} className="rounded-xl border border-gray-200 bg-white px-2 py-1.5 text-[12px] text-gray-500">取消</button>
                    </div>
                  ) : (
                    <button type="button" onClick={() => setResetPwEmployeeId(employee.id)} className="rounded-xl border border-blue-200 bg-blue-50 px-3 py-1.5 text-[12px] font-bold text-blue-700 hover:bg-blue-100">重置密码</button>
                  )}
                  <button type="button" disabled={employeeReviewBusyId === employee.id} onClick={() => void handleDisable(employee.id)} className="rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-[12px] font-bold text-red-500 hover:bg-red-50 disabled:opacity-50">停用</button>
                </>
              )))}
            </div>
          )}
        </div>
      );
    };

    const renderSystemAdminSection = (initialAdvancedTab: OrgModelTab | null = null) => (
      <div className="space-y-6">
        {currentSessionUser?.primaryRole === 'admin' && (
          <>{EmployeeReviewPanel()}</>
        )}
        {authState.sessionMode === 'cloud' ? (
          <OrganizationSetupCenter
            value={orgModelDraft}
            organizationDnaModules={organizationDnaModules}
            departmentCatalog={departmentOptions}
            employees={employeeReviews}
            canEdit
            isSaving={isSavingOrgModel}
            activeWeekLabel={currentWeekLabel()}
            initialAdvancedTab={initialAdvancedTab}
            onChange={setOrgModelDraft}
            onSave={(nextDraft) => handleSaveOrgModel(nextDraft)}
            onOpenSection={(section) => setSettingsSection(section)}
          />
        ) : (
          <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm text-[13px] text-gray-600 leading-6">
            连接云端并加入或创建组织后，才能继续配置组织结构、邀请码与飞书协作底座。
          </div>
        )}

      </div>
    );

    const renderSectionContent = () => {
      if (!settingsSectionLoaded[settingsSection] && !['overview', 'tasks', 'system_logs'].includes(settingsSection)) {
        return (
          <div className="bg-white border border-gray-100 rounded-3xl p-8 shadow-sm text-[13px] text-gray-500 flex items-center gap-3">
            <RefreshCw size={16} className="animate-spin" />
            正在加载该模块设置…
          </div>
        );
      }
      switch (settingsSection) {
        case 'overview':
          return renderOverviewSection();
        case 'org_dna':
          return renderOrgDnaSection();
        case 'tasks':
          return renderTasksSection();
        case 'client_workspace':
          return renderClientWorkspaceSection();
        case 'topics':
          return renderTopicsSection();
        case 'handbook':
          return renderHandbookSection();
        case 'system_admin':
          return renderSystemAdminSection();
        case 'org_overview':
          return renderSystemAdminSection(orgSectionMeta.org_overview.tab);
        case 'org_departments':
          return renderSystemAdminSection(orgSectionMeta.org_departments.tab);
        case 'org_people':
          return renderSystemAdminSection(orgSectionMeta.org_people.tab);
        case 'org_rules':
          return renderSystemAdminSection(orgSectionMeta.org_rules.tab);
        case 'system_logs':
          return (
            <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm">
              <h2 className="text-[16px] font-bold text-gray-900 mb-1">系统日志</h2>
              <p className="text-[12px] text-gray-500 mb-5">记录所有 API 请求、错误和业务操作。导出后交给 Claude Code 或 Codex 即可快速定位问题。</p>
              <SystemLogPanel />
            </div>
          );
        default:
          return null;
      }
    };

    return (
      <div className="mx-auto w-full min-w-0 h-full min-h-0 flex flex-col pt-6 pb-20 max-w-7xl px-5 lg:px-8">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-[20px] lg:text-[24px] font-bold text-gray-900 tracking-tight">系统设置</h1>
            <p className="text-[12px] text-gray-500 mt-1">把整个软件的默认规则、权限边界和组织级知识底座收口到一个设置中心。</p>
          </div>
          {isLocalSession ? (
            <Button onClick={() => openCloudAuthModal('login')}>
              <ShieldAlert size={16} /> 注册 / 登录
            </Button>
          ) : (
            <Button onClick={() => {
              if (!window.confirm('确定要退出登录吗？')) return;
              void logout()
                .then(async (response) => {
                  resetCloudBoundTaskViews();
                  setAuthState(response);
                  await loadAll();
                })
                .catch((error) => flash('error', error instanceof Error ? error.message : '退出失败'));
            }}>
              <ShieldAlert size={16} /> 退出登录
            </Button>
          )}
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto">
          <div className={`grid grid-cols-1 gap-6 ${settingsSidebarCollapsed ? 'xl:grid-cols-[92px_minmax(0,1fr)]' : 'xl:grid-cols-[260px_minmax(0,1fr)]'}`}>
            <div className={`bg-white border border-gray-100 rounded-3xl shadow-sm h-fit ${settingsSidebarCollapsed ? 'p-3' : 'p-4'}`}>
              <div className={`mb-3 flex items-center ${settingsSidebarCollapsed ? 'justify-center' : 'justify-between gap-3'}`}>
                {!settingsSidebarCollapsed && (
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gray-400">设置导航</p>
                    <p className="mt-1 text-[12px] text-gray-500">收起后仅保留图标，右侧内容区会自动拉宽。</p>
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => setSettingsSidebarCollapsed((prev) => !prev)}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-gray-200 bg-gray-50 text-gray-600 transition-colors hover:border-blue-100 hover:bg-blue-50 hover:text-[#335CFF]"
                  title={settingsSidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
                  aria-label={settingsSidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
                >
                  {settingsSidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
                </button>
              </div>
              <div className="space-y-4">
                {sectionGroups.map((group) => {
                  const visibleItems = group.items.filter((section) => currentSessionUser?.primaryRole === 'admin' || !['system_admin', 'org_overview', 'org_departments', 'org_people', 'org_rules'].includes(section.key));
                  if (visibleItems.length === 0) return null;
                  return (
                    <div key={group.group}>
                      {!settingsSidebarCollapsed && (
                        <p className="mb-1.5 px-4 text-[10px] font-bold uppercase tracking-[0.12em] text-gray-400">{group.group}</p>
                      )}
                      <div className="space-y-1">
                        {visibleItems.map((section) => {
                          const Icon = section.icon;
                          const isActive = settingsSection === section.key;
                          return (
                            <button
                              key={section.key}
                              type="button"
                              title={settingsSidebarCollapsed ? section.label : undefined}
                              onClick={() => {
                                setSettingsSection(section.key);
                              }}
                              className={`w-full rounded-2xl border transition-all ${settingsSidebarCollapsed ? 'px-0 py-2.5 text-center' : 'px-4 py-2.5 text-left'} ${isActive ? 'border-blue-200 bg-blue-50/60 text-[#335CFF]' : 'border-transparent hover:border-gray-100 hover:bg-gray-50 text-gray-700'}`}
                            >
                              <div className={`flex ${settingsSidebarCollapsed ? 'justify-center' : 'items-center gap-3'}`}>
                                <Icon size={15} />
                                {!settingsSidebarCollapsed && (
                                  <p className="text-[12px] font-bold">{section.label}</p>
                                )}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="min-w-0">{renderSectionContent()}</div>
          </div>
        </div>
      </div>
    );
  };

  const viewMap: Record<NavKey, React.ReactNode> = {
    tasks: <TasksView />,
    client_workspace: <ClientWorkspaceView />,
    strategic_accompaniment: (
      <StrategicBrainView
        clients={clients}
        currentClientId={currentClientId}
        onClientChange={(clientId) => {
          setCurrentClientId(clientId);
          void refreshWorkspace(clientId);
        }}
        onCreateTaskFromThought={(payload) => {
          const descParts = [`【系统建议 · ${payload.thoughtLine}】\n${payload.suggestion}`];
          if (payload.ceoComment) {
            descParts.push(`\n\n【补充看法 · ${currentSessionUser.fullName || 'CEO'}】\n${payload.ceoComment}`);
          }
          requestCreateTaskEditor(payload.dueDate || undefined);
          setEditingTask((prev) => ({
            ...prev,
            desc: descParts.join(''),
            clientId: payload.clientId,
            clientTouched: Boolean(payload.clientId),
            clientConfidence: payload.clientId ? 'manual' : 'none',
            clientReason: payload.clientId ? `来自战略研判「${payload.thoughtLine}」` : '可选：手动选择项目，或先关联事件线后自动回填。',
          }));
        }}
      />
    ),
    topics_management: (
      <TopicsManagementView
        radars={radars}
        candidates={candidates}
        tasks={tasks}
        activeTaskLists={activeTaskLists}
        effectiveTaskSettings={effectiveTaskSettings}
        topicsSettingsState={topicsSettingsState}
        currentSessionUser={currentSessionUser}
        currentOperatorName={currentOperatorName}
        flash={flash}
        onTopicsReload={loadTopicsBlock}
        onTasksReload={loadTaskBlock}
      />
    ),
    growth_handbook: (
      <GrowthCenterView />
    ),
    settings: SettingsView(),
  };

  const [splashMessageTick, setSplashMessageTick] = useState(0);
  useEffect(() => {
    if (!loading) return;
    const timer = window.setInterval(() => setSplashMessageTick((t) => t + 1), 3000);
    return () => window.clearInterval(timer);
  }, [loading]);

  if (loading) {
    const VALUE_MESSAGES = [
      '让每一天的工作都留下痕迹，变成成长',
      `任务、${terminology.singularLabel}、会议、复盘——一个界面掌控全局`,
      '本地优先，断网也能正常工作',
      'AI 不是替代你，是陪你一起想、一起做',
      '从经验到方法，从方法到可复用的组织资产',
      '每一次推进都被记住，每一个判断都有依据',
      '不只是管理工具，是你的成长搭档',
    ];
    const PHASE_PROGRESS: Record<string, number> = {
      '正在初始化桌面界面…': 5,
      '正在连接本地后端…': 12,
      '正在恢复登录状态…': 20,
      '正在读取系统设置…': 30,
      '正在载入核心模块数据…': 45,
      [`正在载入${terminology.workspaceLabel}…`]: 70,
      '正在读取员工与组织数据…': 85,
      '正在切换到登录态…': 90,
      '启动完成': 100,
    };
    const baseProgress = PHASE_PROGRESS[loadingPhase] ?? (loadingPhase.includes('受阻') ? 0 : 50);
    const progressPercent = loadingPhase === '正在载入核心模块数据…'
      ? 45 + Math.round(loadingSubProgress * 0.25)
      : baseProgress;
    const valueIndex = splashMessageTick % VALUE_MESSAGES.length;
    const isError = loadingPhase.includes('受阻');
    return (
      <div
        className="min-h-screen flex flex-col items-center justify-center px-6 relative overflow-hidden select-none"
        style={{ background: 'linear-gradient(160deg, #1E293B 0%, #334155 30%, #F8FAFC 100%)' }}
      >
        <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
          {[...Array(6)].map((_, i) => (
            <div
              key={i}
              className="absolute rounded-full opacity-[0.07]"
              style={{
                width: `${60 + i * 40}px`,
                height: `${60 + i * 40}px`,
                background: 'radial-gradient(circle, #5B7BFE 0%, transparent 70%)',
                left: `${10 + i * 15}%`,
                top: `${20 + (i % 3) * 25}%`,
                animation: `splash-float ${6 + i * 2}s ease-in-out infinite alternate`,
                animationDelay: `${i * 0.8}s`,
              }}
            />
          ))}
        </div>
        <style>{`
          @keyframes splash-float { 0% { transform: translateY(0) scale(1); } 100% { transform: translateY(-20px) scale(1.1); } }
          @keyframes splash-breathe { 0%,100% { opacity:.9; transform:scale(1); } 50% { opacity:1; transform:scale(1.04); } }
          @keyframes splash-fade-up { 0% { opacity:0; transform:translateY(12px); } 100% { opacity:1; transform:translateY(0); } }
          @keyframes splash-glow { 0%,100% { box-shadow:0 0 8px rgba(91,123,254,.3); } 50% { box-shadow:0 0 16px rgba(91,123,254,.6); } }
        `}</style>

        <div className="flex flex-col items-center gap-5 z-10" style={{ animation: 'splash-breathe 3s ease-in-out infinite' }}>
          <div className="w-20 h-20 rounded-2xl bg-white/95 shadow-lg flex items-center justify-center backdrop-blur-sm">
            <BrandLogoMark logoDataUrl={systemAdminSettingsState?.brandLogoDataUrl || null} className="w-14 h-14" />
          </div>
          <div className="text-center">
            <h1 className="text-[28px] font-bold text-white tracking-wide" style={{ textShadow: '0 2px 12px rgba(0,0,0,.15)' }}>益语智库</h1>
            <p className="mt-1 text-[13px] text-white/50 tracking-widest">YIYU THINKTANK WORKBENCH</p>
          </div>
        </div>

        <div className="mt-10 h-[48px] flex items-center justify-center z-10">
          <p
            key={valueIndex}
            className="text-[16px] text-white/80 text-center font-light tracking-wide leading-relaxed"
            style={{ animation: 'splash-fade-up 0.6s ease-out both' }}
          >
            {isError ? loadingPhase : VALUE_MESSAGES[valueIndex]}
          </p>
        </div>

        <div className="mt-8 w-[280px] z-10">
          <div className="h-[3px] rounded-full bg-white/10 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700 ease-out"
              style={{
                width: `${progressPercent}%`,
                background: isError ? 'linear-gradient(90deg,#EF4444,#F87171)' : 'linear-gradient(90deg,#5B7BFE,#818CF8)',
                animation: isError ? 'none' : 'splash-glow 2s ease-in-out infinite',
              }}
            />
          </div>
          <p className="mt-3 text-[11px] text-white/30 text-center">{loadingPhase}</p>
        </div>
      </div>
    );
  }

  if (!authState.authenticated || !currentSessionUser) {
    return <AuthShell />;
  }

  const isLocalSession = authState.sessionMode !== 'cloud';

  return (
    <GrowthProvider>
      <div className="window-drag window-drag-strip" aria-hidden="true" />
      <div className="min-h-screen bg-[#F9FAFB] flex font-sans overflow-hidden text-gray-800 antialiased selection:bg-blue-100 selection:text-[#5B7BFE]">
      <aside
        className={`w-[60px] ${isSidebarCollapsed ? 'md:w-[88px]' : 'md:w-[240px]'} bg-white border-r border-gray-100 flex flex-col fixed z-20 shrink-0 overflow-hidden shadow-[4px_0_24px_rgba(0,0,0,0.02)] transition-[width] duration-300`}
        style={{
          top: 'var(--window-drag-strip-height)',
          height: 'calc(100vh - var(--window-drag-strip-height))',
        }}
      >
        <div className={`px-4 py-6 md:py-7 ${isSidebarCollapsed ? 'md:px-3' : 'md:px-6'}`}>
          <div className={`flex items-center gap-3 md:gap-4 justify-center ${isSidebarCollapsed ? 'md:justify-center' : 'md:justify-start'}`}>
            <BrandLogoMark logoDataUrl={systemAdminSettingsState.brandLogoDataUrl || null} className={`w-8 h-8 ${isSidebarCollapsed ? 'md:w-10 md:h-10' : 'md:w-11 md:h-11'}`} />
            <span className={`font-bold text-[18px] md:text-[20px] text-gray-900 tracking-tight ${isSidebarCollapsed ? 'hidden' : 'hidden md:block'}`}>益语智库</span>
          </div>
          <div className={`mt-3 hidden md:flex ${isSidebarCollapsed ? 'justify-center' : 'justify-start pl-[2px]'}`}>
            <button
              type="button"
              onClick={() => setIsSidebarCollapsed((current) => !current)}
              className="inline-flex h-6 items-center justify-center text-gray-400 transition-colors hover:text-[#5B7BFE]"
              title={isSidebarCollapsed ? '展开侧栏' : '收起侧栏'}
              aria-label={isSidebarCollapsed ? '展开侧栏' : '收起侧栏'}
            >
              {isSidebarCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
            </button>
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain">
          <nav className={`px-2 mt-2 space-y-2 overflow-visible ${isSidebarCollapsed ? 'md:px-3' : 'md:px-4'}`}>
            {navItems.map((item) => {
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  aria-label={item.label}
                  onClick={() => setActiveTab(item.id)}
                  className={`relative w-full flex items-center justify-center px-2 py-3 md:py-3.5 rounded-2xl text-[14px] transition-all duration-300 font-bold group ${isSidebarCollapsed ? 'md:justify-center md:px-2' : 'md:justify-start md:px-4'} ${isActive ? 'bg-[#5B7BFE]/10 text-[#5B7BFE]' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900'}`}
                >
                  <div className="flex items-center gap-3.5 relative">
                    <item.icon size={20} strokeWidth={isActive ? 2.5 : 2} className={`shrink-0 transition-colors ${isActive ? 'text-[#5B7BFE]' : 'text-gray-400 group-hover:text-gray-700'}`} />
                    <span className={`${isSidebarCollapsed ? 'hidden' : 'hidden md:block'} truncate tracking-wide`}>{item.label}</span>
                  </div>
                  {isSidebarCollapsed && (
                    <span className="pointer-events-none absolute left-full top-1/2 z-30 ml-3 hidden -translate-y-1/2 whitespace-nowrap rounded-xl border border-gray-200 bg-white px-3 py-2 text-[12px] font-bold text-gray-700 shadow-[0_12px_30px_rgba(15,23,42,0.12)] opacity-0 transition-all duration-200 group-hover:translate-x-1 group-hover:opacity-100 md:block">
                      {item.label}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          <div className={`px-3 pb-3 ${isSidebarCollapsed ? 'md:px-3' : 'md:px-4'} hidden md:block`}>
            <CollabSyncCard
              collapsed={isSidebarCollapsed}
              status={collabStatus}
              loading={isCollabStatusLoading}
              busyAction={collabBusyAction}
              onRevealRepo={() => {
                const targetPath = collabStatus?.repoPath || collabStatus?.suggestedRepoPath;
                if (!targetPath) {
                  flash('error', '当前没有可定位的源码目录。');
                  return;
                }
                void revealInFinderBridge(targetPath);
              }}
              onPreviewPush={() => {
                void handlePreviewPush();
              }}
              onPreviewPull={() => {
                void handlePreviewPull();
              }}
            />
          </div>

          <div className={`px-4 pb-5 ${isSidebarCollapsed ? 'hidden' : 'hidden md:block'}`}>
            <div className="bg-gray-50 rounded-2xl p-4 border border-gray-100">
              <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2">当前登录</p>
              <p className="text-[13px] font-bold text-gray-800">{isLocalSession ? '本机模式' : currentSessionUser.fullName}</p>
              <p className="text-[11px] text-gray-500 mt-1">{isLocalSession ? `未连接云端 · ${settingsState?.aiProvider || 'mock'} · ${health?.stats.workObjects ?? health?.stats.clients ?? 0} ${terminology.pluralLabel}` : `${currentSessionUser.primaryRole} · ${settingsState?.aiProvider || 'mock'} · ${health?.stats.workObjects ?? health?.stats.clients ?? 0} ${terminology.pluralLabel}`}</p>
              {isLocalSession ? (
                <button
                  className="mt-3 text-[12px] font-bold text-[#5B7BFE]"
                  onClick={() => openCloudAuthModal('login')}
                >
                  注册 / 登录
                </button>
              ) : (
                <button
                  className="mt-3 text-[12px] font-bold text-[#5B7BFE]"
                  onClick={() => {
                    if (!window.confirm('确定要退出登录吗？')) return;
                    void logout()
                      .then(async (response) => {
                        resetCloudBoundTaskViews();
                        setAuthState(response);
                        await loadAll();
                      })
                      .catch((error) => flash('error', error instanceof Error ? error.message : '退出失败'));
                  }}
                >
                  退出登录
                </button>
              )}
            </div>
          </div>
        </div>
      </aside>

      <main
        className={`flex-1 ml-[60px] ${isSidebarCollapsed ? 'md:ml-[88px]' : 'md:ml-[240px]'} bg-[#F9FAFB] flex flex-col relative overflow-hidden transition-[margin-left] duration-300`}
        style={{
          marginTop: 'var(--window-drag-strip-height)',
          height: 'calc(100vh - var(--window-drag-strip-height))',
        }}
      >
        {backendCompatibilityError && (
          <div className="absolute top-4 left-4 z-50 max-w-[460px] px-4 py-3 rounded-2xl text-[12px] font-bold shadow-sm bg-rose-50 text-rose-600 border border-rose-200">
            {backendCompatibilityError}
          </div>
        )}
        <GlobalBannerHost />
        {viewMap[activeTab]}
      </main>
      <CollabPreviewDialog
        open={Boolean(collabDialogState)}
        mode={collabDialogState?.mode || 'push'}
        preview={collabDialogState?.preview || null}
        selectedPaths={collabSelectedPaths}
        message={collabCommitMessage}
        errorMessage={collabDialogError}
        busy={collabBusyAction === 'push' || collabBusyAction === 'pull'}
        onClose={() => {
          if (collabBusyAction === 'push' || collabBusyAction === 'pull') return;
          setCollabDialogState(null);
          setCollabDialogError(null);
        }}
        onTogglePath={toggleCollabPath}
        onToggleEffectPaths={toggleCollabEffectPaths}
        onMessageChange={handleCollabMessageChange}
        onConfirm={() => {
          void handleConfirmCollabAction();
        }}
      />
      {CloudAuthModal()}
      </div>
    </GrowthProvider>
  );
}
