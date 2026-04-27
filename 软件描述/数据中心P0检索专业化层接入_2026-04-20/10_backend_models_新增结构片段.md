# backend/app/models.py:650-760

```python
class ImportPayload(BaseModel):
    clientId: str
    mode: Literal["folder", "file"]
    paths: list[str]
    allowLegacy: bool = False


class WorkspaceImportBackfillResponse(BaseModel):
    importId: str
    jobId: str
    sourceRoot: str
    discovered: int
    imported: int
    skipped: int


class DocumentRecord(BaseModel):
    id: str
    clientId: str
    folderId: str | None = None
    title: str
    path: str
    kind: str
    source: str
    excerpt: str
    tags: list[str]
    importedAt: str


class KnowledgeStatusRecord(BaseModel):
    totalDocuments: int
    totalChunks: int
    vectorizedDocuments: int
    dedupedDocuments: int
    reviewPendingDocuments: int
    surrogateCount: int = 0
    memoryDocCount: int = 0
    masterIndexCount: int = 0
    reclassifiedDocumentCount: int = 0
    qdrantReady: bool = False
    lastUpdatedAt: str | None = None
    pendingJobs: int = 0
    runningJobs: int = 0
    lastJobStatus: Literal["idle", "queued", "running", "completed", "failed"] = "idle"
    lastJobError: str | None = None
    lastSuccessfulRunAt: str | None = None
    embeddingMode: str = "hash_fallback"
    embeddingModel: str | None = None
    embeddingError: str | None = None
    embeddingProvider: str | None = None
    embeddingDimension: int | None = None
    embeddingSignature: str | None = None
    activeVectorCollection: str | None = None
    vectorIndexStatus: Literal["ready", "stale", "building", "failed"] | None = None
    routerEnabled: bool | None = None
    routerModel: str | None = None
    rerankEnabled: bool | None = None


class DocumentCardRecord(BaseModel):
    id: str
    docId: str
    clientId: str
    documentId: str
    title: str
    originalPath: str
    importSourcePath: str | None = None
    currentHumanPath: str | None = None
    humanFolderCategory: str | None = None
    sourcePath: str
    logicalCategory: str | None = None
    logicalSubcategory: str | None = None
    classificationReason: str | None = None
    normalizedPath: str | None = None
    surrogateMdPath: str | None = None
    kind: str
    primaryCategory: str
    secondaryCategory: str
    shortSummary: str
    summary: str
    retrievalSummary: str = ""
    documentRole: str = "资料"
    queryHints: list[str] = Field(default_factory=list)
    distinctFindings: list[str] = Field(default_factory=list)
    coreQuestions: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    dateRange: str | None = None
    classificationConfidence: float
    needsReview: bool
    deepRead: bool
    lastHitQuestion: str | None = None
    dedupStatus: str
    vectorStatus: str
    version: int
    chunkCount: int = 0
    createdAt: str
    updatedAt: str


class GoalRecord(BaseModel):
    id: str
    clientId: str
    title: str
    quarter: str
    progress: int
    ownerName: str


class GoalPayload(BaseModel):
```

---

# backend/app/models.py:2680-2845

```python
    canUseAnalysisFirst: bool = False
    mustFallbackToLegacy: bool = False


class AnswerPolicyRecord(BaseModel):
    canAnswer: bool = True
    answerLevel: AnswerLevel = "insufficient"
    mustDiscloseCandidateBoundary: bool = False
    mustUseRawEvidence: bool = False
    shouldCreateProposal: bool = False
    fallbackToLegacyRetrieval: bool = False
    reason: str = ""


class RetrievalModelSettingsRecord(BaseModel):
    embeddingProvider: str = "local_fastembed"
    embeddingModel: str = "BAAI/bge-small-zh-v1.5"
    embeddingDimension: int = 256
    embeddingMode: Literal["local", "doubao", "hash_fallback"] = "local"
    routerEnabled: bool = False
    routerProvider: str = "rules"
    routerModel: str = ""
    rerankEnabled: bool = False
    rerankProvider: str = "rules"
    shadowMode: bool = True
    updatedAt: str = ""


class RetrievalModelSettingsPayload(BaseModel):
    embeddingProvider: str | None = None
    embeddingModel: str | None = None
    embeddingDimension: int | None = None
    embeddingMode: Literal["local", "doubao", "hash_fallback"] | None = None
    routerEnabled: bool | None = None
    routerProvider: str | None = None
    routerModel: str | None = None
    rerankEnabled: bool | None = None
    rerankProvider: str | None = None
    shadowMode: bool | None = None


class RouteDecisionRecord(BaseModel):
    intent: PageIntentType = "general"
    routeMode: RouteMode = "state_first"
    dataSources: list[str] = Field(default_factory=list)
    retrievalMode: Literal["state_only", "raw_only", "hybrid", "deferred"] = "deferred"
    judgmentQueryMode: JudgmentQueryMode | None = None
    evidenceSupportMode: EvidenceSupportMode | None = None
    shouldUseRawEvidence: bool = False
    shouldUseStatePool: bool = True
    shouldUseTaskContext: bool = False
    shouldUseMeetingContext: bool = False
    shouldCreateProposal: bool = False
    queryPlan: list[str] = Field(default_factory=list)
    embeddingProfile: str = "default"
    rerankNeeded: bool = False
    answerLevelHint: Literal["auto", "official", "candidate", "evidence_based", "fallback", "insufficient"] = "auto"
    confidence: float = 0.0
    routeReason: str = ""
    routerSource: Literal["rules", "smart_router", "fallback"] = "rules"
    fallbackUsed: bool = False


class RetrievalTraceRecord(BaseModel):
    routeDecision: RouteDecisionRecord
    embeddingProvider: str = "local_fastembed"
    embeddingModel: str = "BAAI/bge-small-zh-v1.5"
    embeddingDimension: int = 256
    embeddingSignature: str = "local_fastembed:BAAI/bge-small-zh-v1.5:256"
    vectorCollection: str | None = None
    lexicalHitCount: int = 0
    vectorHitCount: int = 0
    mergedHitCount: int = 0
    rerankHitCount: int = 0
    rawChunkHitCount: int = 0
    fallbackUsed: bool = False
    latencyMs: dict[str, float] = Field(default_factory=dict)


class RetrievalHealthComponentRecord(BaseModel):
    provider: str
    model: str
    dimension: int | None = None
    signature: str | None = None
    ready: bool
    error: str | None = None


class RetrievalHealthRecord(BaseModel):
    embedding: RetrievalHealthComponentRecord
    router: RetrievalHealthComponentRecord
    rerank: dict[str, object] = Field(default_factory=dict)
    shadowMode: bool = True


class RetrievalShadowRunRecord(BaseModel):
    id: str
    clientId: str
    page: str
    prompt: str
    baselineSummary: dict[str, object] = Field(default_factory=dict)
    candidateSummary: dict[str, object] = Field(default_factory=dict)
    overlapRate: float = 0.0
    candidateBetter: bool = False
    failureReason: str | None = None
    createdAt: str


class RetrievalShadowSummaryRecord(BaseModel):
    total: int = 0
    candidateBetterRate: float = 0.0
    overlapRateAvg: float = 0.0
    latencyDeltaMsAvg: float = 0.0
    failures: int = 0


class PageContextPackRecord(BaseModel):
    page: PageContextPage
    scopeType: str
    scopeId: str
    clientId: str | None = None
    intent: PageIntentType = "general"
    officialJudgments: list[dict[str, object]] = Field(default_factory=list)
    candidateJudgments: list[dict[str, object]] = Field(default_factory=list)
    overlayJudgments: list[dict[str, object]] = Field(default_factory=list)
    evidenceCards: list[dict[str, object]] = Field(default_factory=list)
    rawEvidence: list[dict[str, object]] = Field(default_factory=list)
    openQuestions: list[dict[str, object]] = Field(default_factory=list)
    conflicts: list[dict[str, object]] = Field(default_factory=list)
    themeClusters: list[dict[str, object]] = Field(default_factory=list)
    relatedTasks: list[dict[str, object]] = Field(default_factory=list)
    relatedMeetings: list[dict[str, object]] = Field(default_factory=list)
    relatedDocuments: list[dict[str, object]] = Field(default_factory=list)
    notebookSummary: dict[str, object] | None = None
    memoryFacts: list[str] = Field(default_factory=list)
    contextPack: dict[str, object] | None = None
    judgmentBundle: dict[str, object] | None = None
    resolutionTrace: dict[str, object] | None = None
    stateProjection: dict[str, object] | None = None
    missingContext: list[str] = Field(default_factory=list)
    boundaryNotes: list[str] = Field(default_factory=list)
    sourceSummary: dict[str, int] = Field(default_factory=dict)
    answerPolicy: AnswerPolicyRecord = Field(default_factory=AnswerPolicyRecord)
    retrievalPlan: dict[str, object] = Field(default_factory=dict)
    quality: ContextQualityRecord = Field(default_factory=ContextQualityRecord)
    routeDecision: RouteDecisionRecord | None = None
    retrievalTrace: RetrievalTraceRecord | None = None


class PrepPackMaterialRecord(BaseModel):
    sourceType: str
    sourceId: str
    title: str
    summary: str
    authorityLevel: str = ""


class PrepPackCardRecord(BaseModel):
    taskId: str
    title: str
    summary: str
    materials: list[PrepPackMaterialRecord] = Field(default_factory=list)
    openQuestions: list[str] = Field(default_factory=list)
    judgments: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    boundaryNotes: list[str] = Field(default_factory=list)
```
