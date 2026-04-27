# src/shared/types.ts:470-1010

```typescript
  id: string;
  clientId: string;
  label: string;
  path: string;
  fileCount: number;
  lastScannedAt?: string | null;
}

export interface DocumentRecord {
  id: string;
  clientId: string;
  folderId?: string | null;
  title: string;
  path: string;
  kind: string;
  source: 'folder' | 'file' | 'meeting';
  excerpt: string;
  tags: string[];
  importedAt: string;
}

export interface KnowledgeStatus {
  totalDocuments: number;
  totalChunks: number;
  vectorizedDocuments: number;
  dedupedDocuments: number;
  reviewPendingDocuments: number;
  surrogateCount: number;
  memoryDocCount: number;
  masterIndexCount: number;
  reclassifiedDocumentCount: number;
  qdrantReady: boolean;
  lastUpdatedAt?: string | null;
  pendingJobs: number;
  runningJobs: number;
  lastJobStatus: 'idle' | 'queued' | 'running' | 'completed' | 'failed';
  lastJobError?: string | null;
  lastSuccessfulRunAt?: string | null;
  embeddingMode: string;
  embeddingModel?: string | null;
  embeddingError?: string | null;
  embeddingProvider?: string | null;
  embeddingDimension?: number | null;
  embeddingSignature?: string | null;
  activeVectorCollection?: string | null;
  vectorIndexStatus?: 'ready' | 'stale' | 'building' | 'failed' | null;
  routerEnabled?: boolean;
  routerModel?: string | null;
  rerankEnabled?: boolean;
}

export interface OrganizationNotebookSnapshot {
  id: string;
  clientId: string;
  organizationIntro: string;
  collaborationRelationship: string;
  currentStage: string;
  businessModules: string[];
  keyPeople: string[];
  keyProducts: string[];
  currentChallenges: string[];
  collaborationGoals: string[];
  recentFacts: string[];
  informationGaps: string[];
  updatedAt: string;
  confidence: number;
}

export interface EventLineMemorySnapshot {
  id: string;
  eventLineId: string;
  lineName: string;
  currentStage: string;
  currentWork: string;
  currentBlocker: string;
  recentDecision: string;
  nextStep: string;
  evidenceRefs: string[];
  clarificationNeeds: string[];
  analysisSignals: string[];
  predictionReadiness: number;
  updatedAt: string;
  confidence: number;
}

export interface MemoryFact {
  id: string;
  scopeType: 'client' | 'person' | 'product' | 'event_line' | 'task';
  scopeId: string;
  factKey: string;
  factValue: string;
  sourceType: string;
  sourceId: string;
  confidence: number;
  freshness: number;
  evidenceRefs: string[];
  createdAt: string;
  updatedAt: string;
}

export interface ClarificationRecord {
  id: string;
  scopeType: 'client' | 'person' | 'product' | 'event_line' | 'task';
  scopeId: string;
  slotKey: string;
  question: string;
  status: 'pending' | 'answered';
  answerText?: string | null;
  writeScope: string[];
  resolvedFactIds: string[];
  reusable: boolean;
  createdAt: string;
  answeredAt?: string | null;
  updatedAt: string;
}

export interface MemoryStatus {
  clientId: string;
  notebookCompleteness: number;
  notebookConfidence: number;
  eventLineCoverage: number;
  totalEventLines: number;
  coveredEventLines: number;
  pendingClarifications: number;
  lowEvidenceJudgments: number;
  updatedAt: string;
}

export interface BackgroundReadiness {
  score: number;
  level: 'low' | 'medium' | 'high';
  missingSlots: string[];
  backgroundSources: string[];
}

export interface DocumentCard {
  id: string;
  docId: string;
  clientId: string;
  documentId: string;
  title: string;
  originalPath: string;
  sourcePath: string;
  logicalCategory?: string | null;
  logicalSubcategory?: string | null;
  classificationReason?: string | null;
  importSourcePath?: string | null;
  currentHumanPath?: string | null;
  humanFolderCategory?: string | null;
  normalizedPath?: string | null;
  surrogateMdPath?: string | null;
  kind: string;
  primaryCategory: string;
  secondaryCategory: string;
  shortSummary: string;
  summary: string;
  retrievalSummary: string;
  documentRole: string;
  queryHints: string[];
  distinctFindings: string[];
  coreQuestions: string[];
  keywords: string[];
  tags: string[];
  entities: string[];
  dateRange?: string | null;
  classificationConfidence: number;
  needsReview: boolean;
  deepRead: boolean;
  lastHitQuestion?: string | null;
  dedupStatus: string;
  vectorStatus: string;
  version: number;
  chunkCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface ImportRecord {
  id: string;
  clientId: string;
  sourcePath: string;
  mode: 'folder' | 'file';
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'scanned';
  importedCount: number;
  skippedCount: number;
  createdAt: string;
}

export interface WorkspaceImportBackfillResponse {
  importId: string;
  jobId: string;
  sourceRoot: string;
  discovered: number;
  imported: number;
  skipped: number;
}

export interface ClientTemplateFillField {
  label: string;
  value: string;
  status: 'filled' | 'missing';
  evidenceTitles: string[];
  webSourceTitles?: string[];
  fieldType?: 'precise_fact' | 'structural_summary' | 'governance_mechanism' | 'quantitative_result' | 'attachment_material' | 'general' | null;
  valueKind?: 'fact' | 'summary' | 'inference' | 'missing' | null;
  confidence?: number | null;
  basisSummary?: string | null;
  followUpQuestion?: string | null;
  suggestedSources?: string[];
  reviewRequired?: boolean;
}

export interface ClientTemplateFillResponse {
  path: string;
  fileName: string;
  fieldCount: number;
  filledCount: number;
  missingCount: number;
  reviewFieldCount?: number;
  attachmentChecklist?: string[];
  fields: ClientTemplateFillField[];
}

export interface ClientTemplateFillRun {
  id: string;
  clientId: string;
  templateName: string;
  templatePath: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  phase: 'queued' | 'parsing' | 'retrieving' | 'writing' | 'completed' | 'failed';
  progress: number;
  stageLabel?: string | null;
  elapsedMs: number;
  fieldCount: number;
  processedCount: number;
  filledCount: number;
  missingCount: number;
  reviewFieldCount?: number;
  currentFieldLabel?: string | null;
  evidenceTitles: string[];
  attachmentChecklist?: string[];
  fields: ClientTemplateFillField[];
  outputPath?: string | null;
  errorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface GoalRecord {
  id: string;
  clientId: string;
  title: string;
  quarter: string;
  progress: number;
  ownerName: string;
}

export interface DnaTerm {
  id: string;
  clientId: string;
  category: string;
  canonicalName: string;
  aliases: string[];
  description: string;
  sourceLevel: DnaSourceLevel;
}

export interface EvidenceItem {
  id: string;
  title: string;
  excerpt: string;
  sourceType: string;
  documentId?: string | null;
  path?: string | null;
  score?: number | null;
  coverage?: number | null;
  sectionLabel?: string | null;
  retrievalStage?: 'master_index' | 'surrogate' | 'raw_chunk' | null;
  isFallback?: boolean;
  matchedTerms: string[];
}

export interface AiStructuredResponse {
  content: string;
  judgment: string;
  analysis: string;
  actions: string;
  timeline: string;
}

export type JudgmentQueryMode = 'registry_only' | 'hybrid' | 'evidence_based_synthesis';

export type EvidenceSupportMode =
  | 'none'
  | 'linked_state_evidence'
  | 'evidence_cards'
  | 'raw_doc_drilldown'
  | 'generic_retrieval_fallback';

export type WorkspaceAnswerIntent =
  | 'intro_profile'
  | 'project_intro'
  | 'meeting_summary'
  | 'next_actions'
  | 'official_judgment_registry'
  | 'evidence_question'
  | 'status_progress'
  | 'general';

export type RetrievalDecisionReason =
  | 'state_first_default'
  | 'document_drilldown_requested'
  | 'search_cache_requested'
  | 'intro_query_needs_evidence'
  | 'identity_query_needs_evidence'
  | 'project_intro_needs_evidence'
  | 'meeting_summary_needs_evidence'
  | 'next_actions_needs_evidence'
  | 'evidence_question_needs_evidence'
  | 'official_registry_requested'
  | 'status_progress_needs_hybrid_evidence'
  | 'default_hybrid_evidence'
  | 'state_pool_insufficient'
  | 'state_pool_empty';

export type PageContextPage =
  | 'client_workspace'
  | 'workspace_chat'
  | 'task_detail'
  | 'task_ai'
  | 'meeting_detail'
  | 'mobile_consult'
  | 'topic_radar'
  | 'strategic_cockpit';

export type PageIntentType =
  | 'intro_profile'
  | 'project_intro'
  | 'meeting_summary'
  | 'next_actions'
  | 'official_judgment_registry'
  | 'evidence_question'
  | 'status_progress'
  | 'task_context'
  | 'task_next_action'
  | 'general';

export type AnswerLevel = 'official' | 'candidate' | 'evidence_based' | 'fallback' | 'insufficient';
export type ContextQualityLevel = 'none' | 'weak' | 'usable' | 'strong';

export interface PageIntent {
  rawPrompt: string;
  intent: PageIntentType;
  requiresOfficialJudgment: boolean;
  requiresRawEvidence: boolean;
  requiresNextActions: boolean;
  requiresIntroProfile: boolean;
  requiresTaskContext: boolean;
  routeReason: string;
}

export interface ContextQuality {
  stateObjectCount: number;
  approvedJudgmentCount: number;
  candidateJudgmentCount: number;
  evidenceCardCount: number;
  rawEvidenceCount: number;
  openQuestionCount: number;
  taskCount: number;
  meetingCount: number;
  contextQuality: ContextQualityLevel;
  canUseAnalysisFirst: boolean;
  mustFallbackToLegacy: boolean;
}

export type RouteMode =
  | 'registry_only'
  | 'raw_doc_drilldown'
  | 'meeting_evidence'
  | 'task_context'
  | 'state_first'
  | 'hybrid';

export interface RetrievalModelSettings {
  embeddingProvider: string;
  embeddingModel: string;
  embeddingDimension: number;
  embeddingMode: 'local' | 'doubao' | 'hash_fallback';
  routerEnabled: boolean;
  routerProvider: string;
  routerModel: string;
  rerankEnabled: boolean;
  rerankProvider: string;
  shadowMode: boolean;
  updatedAt: string;
}

export type RetrievalMode = 'state_only' | 'raw_only' | 'hybrid' | 'deferred';

export interface RouteDecision {
  intent: PageIntentType;
  routeMode: RouteMode;
  dataSources: string[];
  retrievalMode: RetrievalMode;
  judgmentQueryMode?: JudgmentQueryMode | null;
  evidenceSupportMode?: EvidenceSupportMode | null;
  shouldUseRawEvidence: boolean;
  shouldUseStatePool: boolean;
  shouldUseTaskContext: boolean;
  shouldUseMeetingContext: boolean;
  shouldCreateProposal: boolean;
  queryPlan: string[];
  embeddingProfile: string;
  rerankNeeded: boolean;
  answerLevelHint: 'auto' | AnswerLevel;
  confidence: number;
  routeReason: string;
  routerSource: 'rules' | 'smart_router' | 'fallback';
  fallbackUsed: boolean;
}

export interface RetrievalTrace {
  routeDecision: RouteDecision;
  embeddingProvider: string;
  embeddingModel: string;
  embeddingDimension: number;
  embeddingSignature: string;
  vectorCollection?: string | null;
  lexicalHitCount: number;
  vectorHitCount: number;
  mergedHitCount: number;
  rerankHitCount: number;
  rawChunkHitCount: number;
  fallbackUsed: boolean;
  latencyMs: Record<string, number>;
}

export interface RetrievalHealthComponent {
  provider: string;
  model: string;
  dimension?: number | null;
  signature?: string | null;
  ready: boolean;
  error?: string | null;
}

export interface RetrievalHealth {
  embedding: RetrievalHealthComponent;
  router: RetrievalHealthComponent;
  rerank: {
    enabled?: boolean;
    provider?: string;
  };
  shadowMode: boolean;
}

export interface RetrievalShadowRun {
  id: string;
  clientId: string;
  page: string;
  prompt: string;
  baselineSummary: Record<string, unknown>;
  candidateSummary: Record<string, unknown>;
  overlapRate: number;
  candidateBetter: boolean;
  failureReason?: string | null;
  createdAt: string;
}

export interface RetrievalShadowSummary {
  total: number;
  candidateBetterRate: number;
  overlapRateAvg: number;
  latencyDeltaMsAvg: number;
  failures: number;
}

export interface AnswerPolicy {
  canAnswer: boolean;
  answerLevel: AnswerLevel;
  mustDiscloseCandidateBoundary: boolean;
  mustUseRawEvidence: boolean;
  shouldCreateProposal: boolean;
  fallbackToLegacyRetrieval: boolean;
  reason: string;
}

export interface PageContextPack {
  page: PageContextPage;
  scopeType: string;
  scopeId: string;
  clientId?: string | null;
  intent: PageIntentType;
  officialJudgments: Array<Record<string, unknown>>;
  candidateJudgments: Array<Record<string, unknown>>;
  overlayJudgments: Array<Record<string, unknown>>;
  evidenceCards: Array<Record<string, unknown>>;
  rawEvidence: Array<Record<string, unknown>>;
  openQuestions: Array<Record<string, unknown>>;
  conflicts: Array<Record<string, unknown>>;
  themeClusters: Array<Record<string, unknown>>;
  relatedTasks: Array<Record<string, unknown>>;
  relatedMeetings: Array<Record<string, unknown>>;
  relatedDocuments: Array<Record<string, unknown>>;
  notebookSummary?: Record<string, unknown> | null;
  memoryFacts: string[];
  contextPack?: Record<string, unknown> | null;
  judgmentBundle?: Record<string, unknown> | null;
  resolutionTrace?: Record<string, unknown> | null;
  stateProjection?: Record<string, unknown> | null;
  missingContext: string[];
  boundaryNotes: string[];
  sourceSummary: Record<string, number>;
  answerPolicy: AnswerPolicy;
  retrievalPlan: Record<string, unknown>;
  quality: ContextQuality;
  routeDecision?: RouteDecision | null;
  retrievalTrace?: RetrievalTrace | null;
}

export type FallbackPresentationMode = 'state_cards_only' | 'compact_user_answer' | 'full_answer';

export interface StateAnswerSections {
  official: string[];
  candidate: string[];
  draftFindings: string[];
  evidenceSupport: string[];
  actions: string[];
  risks: string[];
  unknowns: string[];
}

export interface StateSourceSummary {
  judgments: number;
  meetings: number;
  tasks: number;
  openQuestions: number;
  conflicts: number;
  documents: number;
}
```
