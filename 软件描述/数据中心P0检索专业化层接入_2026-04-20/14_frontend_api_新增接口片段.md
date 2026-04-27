# src/renderer/lib/api.ts:90-170

```typescript
  LegacyScanReport,
  MentionCandidate,
  OrganizationDnaModule,
  OrgModelSettings,
  OrganizationDnaResponse,
  OrganizationDnaUploadPayload,
  MeetingPipelineResult,
  Operator,
  ProjectFlow,
  ProjectFlowDetail,
  ProjectFlowPayload,
  ProjectModule,
  ProjectModuleDetail,
  ProjectModulePayload,
  ProjectStructureResponse,
  PrepPackCard,
  ProposalExecutionResponse,
  ProposalRecord,
  SettingsPayload,
  SystemAdminSettings,
  SystemAdminSettingsPayload,
  TaskOrgBackfillResult,
  Task,
  TaskActivityRecord,
  TaskContextPreview,
  PageContextPack,
  RetrievalHealth,
  RetrievalModelSettings,
  RetrievalShadowRun,
  RetrievalShadowSummary,
  TaskSmartBrief,
  TaskTag,
  TaskTagMutationPayload,
  TaskTagSuggestionPayload,
  TaskMutationPayload,
  TaskListMutationPayload,
  TaskList,
  TaskSettings,
  TaskSettingsPayload,
  TopicsSettings,
  TopicsSettingsPayload,
  UpdateProfilePayload,
  HandbookSettings,
  HandbookSettingsPayload,
  CoachCaseRecord,
  CoachReminderRule,
  TopicCaptureBatchResult,
  TopicCandidate,
  TopicCandidateChatPayload,
  TopicCandidateChatResponse,
  TopicCandidateInsight,
  TopicCandidatePayload,
  TopicTaskPlanResult,
  TopicTaskPromotionDraft,
  TopicTaskPromotionResult,
  TopicRadar,
  TopicRadarPayload,
  ReviewDashboard,
  ReviewHistoryResponse,
  ReviewGovernanceSettings,
  ReviewGovernanceSettingsPayload,
  RedeemOrgInvitationPayload,
  JudgmentConfirmPayload,
  JudgmentVersion,
  ConflictGroup,
  OpenQuestion,
  OrgWritingNorm,
  OrgFeishuIntegration,
  OrgFeishuIntegrationPayload,
  OrgMembershipSummary,
  RunComparison,
  RuntimeRunLog,
  SupportRequestCreatePayload,
  SupportRequestResolvePayload,
  SupportRequestRecord,
  StrategicCockpitConfirmPayload,
  StrategicCockpitSnapshot,
  StrategicThought,
  StrategicThoughtReview,
  StrategicThoughtReviewPayload,
  StrategicThoughtsResponse,
```

---

# src/renderer/lib/api.ts:1050-1135

```typescript
}

export async function createProjectFlow(clientId: string, payload: ProjectFlowPayload) {
  return request<ProjectFlow>(`/api/v1/clients/${clientId}/project-flows`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateProjectFlow(clientId: string, flowId: string, payload: ProjectFlowPayload) {
  return request<ProjectFlow>(`/api/v1/clients/${clientId}/project-flows/${flowId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function getClientKnowledgeStatus(clientId: string) {
  return request<KnowledgeStatus>(`/api/v1/clients/${clientId}/knowledge/status`);
}

export async function getRetrievalSettings() {
  return request<RetrievalModelSettings>('/api/v1/retrieval/settings');
}

export async function updateRetrievalSettings(payload: Partial<RetrievalModelSettings>) {
  return request<RetrievalModelSettings>('/api/v1/retrieval/settings', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getRetrievalHealth() {
  return request<RetrievalHealth>('/api/v1/retrieval/health');
}

export async function getRetrievalShadowSummary(clientId?: string) {
  const query = new URLSearchParams();
  if (clientId) query.set('clientId', clientId);
  const suffix = query.toString();
  const url = suffix ? `/api/v1/retrieval/shadow-summary?${suffix}` : '/api/v1/retrieval/shadow-summary';
  return request<RetrievalShadowSummary>(url);
}

export async function getRetrievalShadowRuns(clientId?: string, limit = 60) {
  const query = new URLSearchParams();
  if (clientId) query.set('clientId', clientId);
  query.set('limit', String(limit));
  return request<RetrievalShadowRun[]>(`/api/v1/retrieval/shadow-runs?${query.toString()}`);
}

export async function reindexClientVector(clientId: string) {
  return request<{
    clientId: string;
    embeddingSignature: string;
    masterIndexed: number;
    chunkIndexed: number;
    fallbackUsed: boolean;
    status: string;
  }>(`/api/v1/clients/${clientId}/knowledge/reindex-vector`, {
    method: 'POST',
  });
}

export async function searchClientKnowledge(clientId: string, prompt: string, threadId?: string) {
  return request<KnowledgeSearchResult>(`/api/v1/clients/${clientId}/knowledge/search`, {
    method: 'POST',
    body: JSON.stringify({ prompt, threadId }),
  });
}

export async function rebuildClientKnowledge(clientId: string) {
  return request<KnowledgeJob>(`/api/v1/clients/${clientId}/knowledge/rebuild`, {
    method: 'POST',
  });
}

export async function generateClientDnaCandidates(clientId: string, payload?: { refreshGenerated?: boolean }) {
  return request<KnowledgeJob>(`/api/v1/clients/${clientId}/dna-documents/generate`, {
    method: 'POST',
    body: JSON.stringify({ refreshGenerated: payload?.refreshGenerated ?? false }),
  });
}

export async function importPaths(clientId: string, mode: 'folder' | 'file', paths: string[], options?: { allowLegacy?: boolean }) {
  return request<ImportRecord[]>('/api/v1/imports', {
    method: 'POST',
```
