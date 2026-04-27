import React, { useEffect, useMemo, useState } from 'react';

import type {
  DataCenterArtifactStatus,
  DataCenterOperationalStatus,
  DataCenterSchemaStatus,
  EvidenceQualityFeedbackSnapshot,
  ExecutionRetryMetrics,
  ExecutionTicket,
  ExecutionTicketLog,
  KernelPrimaryRolloutRun,
  ProposalRecord,
  RollbackDrillResult,
} from '../../../shared/types';
import {
  approveProposal,
  batchApproveProposals,
  batchRejectProposals,
  completeKernelPrimaryRollout,
  createEvidenceQualitySnapshot,
  createProposalExecutionTicket,
  ensureDataCenterSchema,
  executeExecutionTicket,
  getDataCenterArtifactStatus,
  getDataCenterOperationalStatus,
  getDataCenterSchemaStatus,
  getExecutionRetryMetrics,
  getExecutionTicketLogs,
  getExecutionTickets,
  listEvidenceQualitySnapshots,
  listKernelPrimaryRollouts,
  getProposalExecutionPreview,
  getProposals,
  rejectProposal,
  rollbackKernelPrimaryRollout,
  retryExecutionTicket,
  runDataCenterRollbackDrill,
  startKernelPrimaryRollout,
} from '../../lib/api';
import { DataCenterReadinessPanel } from '../settings/DataCenterReadinessPanel';
import { DataCenterDiagnosticsPanel } from '../settings/DataCenterDiagnosticsPanel';
import { WorkspaceAnswerValuePanel } from './WorkspaceAnswerValuePanel';

type ProposalStatusFilter = 'all' | ProposalRecord['status'];
type ProposalKindFilter = 'all' | ProposalRecord['kind'];
type TicketStatusFilter = 'all' | ExecutionTicket['status'];

function statusClass(status: string) {
  if (status === 'approved' || status === 'executed') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (status === 'rejected' || status === 'failed') return 'border-rose-200 bg-rose-50 text-rose-700';
  if (status === 'execution_pending' || status === 'running') return 'border-amber-200 bg-amber-50 text-amber-700';
  return 'border-gray-200 bg-gray-100 text-gray-700';
}

export function DataCenterOpsPanel({ clientId }: { clientId?: string | null }) {
  const [proposals, setProposals] = useState<ProposalRecord[]>([]);
  const [tickets, setTickets] = useState<ExecutionTicket[]>([]);
  const [ticketLogs, setTicketLogs] = useState<Record<string, ExecutionTicketLog[]>>({});
  const [rolloutRuns, setRolloutRuns] = useState<KernelPrimaryRolloutRun[]>([]);
  const [retryMetrics, setRetryMetrics] = useState<ExecutionRetryMetrics | null>(null);
  const [qualitySnapshots, setQualitySnapshots] = useState<EvidenceQualityFeedbackSnapshot[]>([]);
  const [rollbackDrill, setRollbackDrill] = useState<RollbackDrillResult | null>(null);
  const [operationalStatusRemote, setOperationalStatusRemote] = useState<DataCenterOperationalStatus | null>(null);
  const [artifactStatus, setArtifactStatus] = useState<DataCenterArtifactStatus | null>(null);
  const [schemaStatus, setSchemaStatus] = useState<DataCenterSchemaStatus | null>(null);
  const [expandedTicketId, setExpandedTicketId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [rolloutClientIdsInput, setRolloutClientIdsInput] = useState('');
  const [proposalStatus, setProposalStatus] = useState<ProposalStatusFilter>('all');
  const [proposalKind, setProposalKind] = useState<ProposalKindFilter>('all');
  const [ticketStatus, setTicketStatus] = useState<TicketStatusFilter>('all');
  const [selectedProposalIds, setSelectedProposalIds] = useState<Set<string>>(new Set());
  const [previewedProposalIds, setPreviewedProposalIds] = useState<Set<string>>(new Set());
  const [proposalsError, setProposalsError] = useState('');
  const [ticketsError, setTicketsError] = useState('');
  const [rolloutError, setRolloutError] = useState('');
  const [retryMetricsError, setRetryMetricsError] = useState('');
  const [snapshotsError, setSnapshotsError] = useState('');
  const [operationalStatusError, setOperationalStatusError] = useState('');
  const [artifactStatusError, setArtifactStatusError] = useState('');
  const [schemaStatusError, setSchemaStatusError] = useState('');

  const canLoad = Boolean(clientId && clientId.trim());

  const refresh = async () => {
    if (!canLoad || !clientId) return;
    setLoading(true);
    const [
      proposalRows,
      ticketRows,
      rolloutRows,
      retryMetricsRow,
      snapshotRows,
      operationalStatusRow,
      artifactStatusRow,
      schemaStatusRow,
    ] = await Promise.allSettled([
      getProposals({
        clientId,
        status: proposalStatus === 'all' ? undefined : proposalStatus,
        kind: proposalKind === 'all' ? undefined : proposalKind,
        limit: 80,
      }),
      getExecutionTickets({
        clientId,
        status: ticketStatus === 'all' ? undefined : ticketStatus,
        limit: 80,
      }),
      listKernelPrimaryRollouts(20),
      getExecutionRetryMetrics({ clientId, days: 7 }),
      listEvidenceQualitySnapshots(20),
      getDataCenterOperationalStatus({ clientId }),
      getDataCenterArtifactStatus(),
      getDataCenterSchemaStatus(),
    ]);
    setProposalsError(proposalRows.status === 'rejected' ? (proposalRows.reason instanceof Error ? proposalRows.reason.message : '读取 proposals 失败') : '');
    setTicketsError(ticketRows.status === 'rejected' ? (ticketRows.reason instanceof Error ? ticketRows.reason.message : '读取 tickets 失败') : '');
    setRolloutError(rolloutRows.status === 'rejected' ? (rolloutRows.reason instanceof Error ? rolloutRows.reason.message : '读取 rollout 失败') : '');
    setRetryMetricsError(retryMetricsRow.status === 'rejected' ? (retryMetricsRow.reason instanceof Error ? retryMetricsRow.reason.message : '读取 retry metrics 失败') : '');
    setSnapshotsError(snapshotRows.status === 'rejected' ? (snapshotRows.reason instanceof Error ? snapshotRows.reason.message : '读取 snapshots 失败') : '');
    setOperationalStatusError(operationalStatusRow.status === 'rejected' ? (operationalStatusRow.reason instanceof Error ? operationalStatusRow.reason.message : '读取 operational status 失败') : '');
    setArtifactStatusError(artifactStatusRow.status === 'rejected' ? (artifactStatusRow.reason instanceof Error ? artifactStatusRow.reason.message : '读取 artifact status 失败') : '');
    setSchemaStatusError(schemaStatusRow.status === 'rejected' ? (schemaStatusRow.reason instanceof Error ? schemaStatusRow.reason.message : '读取 schema status 失败') : '');

    if (proposalRows.status === 'fulfilled') setProposals(proposalRows.value);
    if (ticketRows.status === 'fulfilled') setTickets(ticketRows.value);
    if (rolloutRows.status === 'fulfilled') setRolloutRuns(rolloutRows.value);
    if (retryMetricsRow.status === 'fulfilled') setRetryMetrics(retryMetricsRow.value);
    if (snapshotRows.status === 'fulfilled') setQualitySnapshots(snapshotRows.value);
    if (operationalStatusRow.status === 'fulfilled') setOperationalStatusRemote(operationalStatusRow.value);
    if (artifactStatusRow.status === 'fulfilled') setArtifactStatus(artifactStatusRow.value);
    if (schemaStatusRow.status === 'fulfilled') setSchemaStatus(schemaStatusRow.value);
    setLoading(false);
  };

  useEffect(() => {
    void refresh();
  }, [clientId, proposalStatus, proposalKind, ticketStatus]);

  useEffect(() => {
    setRolloutClientIdsInput(clientId ? clientId.trim() : '');
  }, [clientId]);

  const proposalMap = useMemo(() => {
    const map = new Map<string, ProposalRecord>();
    proposals.forEach((item) => map.set(item.id, item));
    return map;
  }, [proposals]);

  const latestRollout = useMemo(() => rolloutRuns[0] ?? null, [rolloutRuns]);
  const latestSnapshot = useMemo(() => qualitySnapshots[0] ?? null, [qualitySnapshots]);
  const operationalStatusView = useMemo<DataCenterOperationalStatus>(() => {
    return {
      rolloutStage: operationalStatusRemote?.rolloutStage ?? latestRollout?.stage ?? 'not_started',
      rolloutVerdict: operationalStatusRemote?.rolloutVerdict ?? latestRollout?.verdict ?? 'hold',
      executionRetryAlertCount:
        operationalStatusRemote?.executionRetryAlertCount ?? retryMetrics?.alerts?.length ?? 0,
      latestSnapshotAt: operationalStatusRemote?.latestSnapshotAt ?? latestSnapshot?.createdAt ?? null,
      rollbackDrillStatus: rollbackDrill
        ? (rollbackDrill.applied ? 'applied' : 'dry_run')
        : (operationalStatusRemote?.rollbackDrillStatus ?? 'not_run'),
      fullRegressionVerdict: operationalStatusRemote?.fullRegressionVerdict ?? 'unknown',
    };
  }, [operationalStatusRemote, latestRollout, latestSnapshot, retryMetrics, rollbackDrill]);
  const rolloutClientIds = useMemo(
    () => rolloutClientIdsInput.split(',').map((item) => item.trim()).filter(Boolean),
    [rolloutClientIdsInput],
  );
  const staleArtifactCount = useMemo(
    () => artifactStatus?.items.filter((item) => item.stale).length ?? 0,
    [artifactStatus],
  );
  const schemaHealthy = useMemo(
    () => Boolean(schemaStatus && schemaStatus.missingTables.length === 0 && schemaStatus.errors.length === 0),
    [schemaStatus],
  );
  const stageClientCountValid = useMemo(
    () => ({
      stage_1_client: rolloutClientIds.length === 1,
      stage_3_clients: rolloutClientIds.length >= 3,
      stage_10_clients: rolloutClientIds.length >= 10,
    }),
    [rolloutClientIds],
  );

  const allVisibleSelected = proposals.length > 0 && proposals.every((item) => selectedProposalIds.has(item.id));

  const toggleAllVisible = () => {
    setSelectedProposalIds((prev) => {
      const next = new Set(prev);
      if (allVisibleSelected) {
        proposals.forEach((item) => next.delete(item.id));
      } else {
        proposals.forEach((item) => next.add(item.id));
      }
      return next;
    });
  };

  const toggleProposal = (proposalId: string) => {
    setSelectedProposalIds((prev) => {
      const next = new Set(prev);
      if (next.has(proposalId)) next.delete(proposalId);
      else next.add(proposalId);
      return next;
    });
  };

  const runProposalAction = async (
    proposalId: string,
    action: 'approve' | 'reject' | 'preview' | 'createTicket',
  ) => {
    if (!proposalId) return;
    setBusyId(proposalId);
    try {
      if (action === 'approve') {
        await approveProposal(proposalId, { decidedBy: 'user', note: '人工批准' });
        setMessage('proposal 已批准');
      } else if (action === 'reject') {
        await rejectProposal(proposalId, { decidedBy: 'user', note: '人工驳回' });
        setMessage('proposal 已驳回');
      } else if (action === 'preview') {
        const preview = await getProposalExecutionPreview(proposalId);
        setPreviewedProposalIds((prev) => new Set(prev).add(proposalId));
        setMessage(`preview: ${preview.summary}`);
      } else {
        const result = await createProposalExecutionTicket(proposalId, { requestedBy: 'user', dryRun: false });
        setMessage(result.executionTicket ? `execution ticket 已创建：${result.executionTicket.id}` : 'dry-run 完成，无落库');
      }
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'proposal 操作失败');
    } finally {
      setBusyId(null);
    }
  };

  const runBatchProposalAction = async (action: 'approve' | 'reject') => {
    const proposalIds = Array.from(selectedProposalIds);
    if (proposalIds.length === 0) {
      setMessage('请先选择至少一条 proposal');
      return;
    }
    setBusyId(action);
    try {
      const result = action === 'approve'
        ? await batchApproveProposals({ proposalIds, decidedBy: 'user', note: '批量人工批准' })
        : await batchRejectProposals({ proposalIds, decidedBy: 'user', note: '批量人工驳回' });
      setMessage(`批量${action === 'approve' ? '批准' : '驳回'}完成：成功 ${result.succeeded} / 失败 ${result.failed}`);
      setSelectedProposalIds(new Set());
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '批量 proposal 操作失败');
    } finally {
      setBusyId(null);
    }
  };

  const runTicketExecute = async (ticket: ExecutionTicket) => {
    const linkedProposal = proposalMap.get(ticket.proposalId);
    if (linkedProposal?.riskLevel === 'high') {
      setMessage('高风险 proposal 默认禁用执行，请人工线下复核后再处理。');
      return;
    }
    if (!previewedProposalIds.has(ticket.proposalId)) {
      setMessage('请先查看 execution preview，再执行。');
      return;
    }
    if (!window.confirm(`确认执行 ticket ${ticket.id} 吗？`)) return;
    setBusyId(ticket.id);
    try {
      const response = await executeExecutionTicket(ticket.id, { requestedBy: 'user', dryRun: false });
      setMessage(response.executionTicket ? `执行完成：${response.executionTicket.status}` : '执行完成');
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'ticket 执行失败');
    } finally {
      setBusyId(null);
    }
  };

  const runTicketRetry = async (ticket: ExecutionTicket) => {
    if (!window.confirm(`确认重试 ticket ${ticket.id} 吗？`)) return;
    setBusyId(`retry:${ticket.id}`);
    try {
      const response = await retryExecutionTicket(ticket.id, { requestedBy: 'user', dryRun: false });
      setMessage(response.executionTicket ? `ticket 已重试并回到 ${response.executionTicket.status}` : 'ticket 已重试');
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'ticket 重试失败');
    } finally {
      setBusyId(null);
    }
  };

  const toggleTicketLogs = async (ticketId: string) => {
    if (expandedTicketId === ticketId) {
      setExpandedTicketId(null);
      return;
    }
    setExpandedTicketId(ticketId);
    if (!ticketLogs[ticketId]) {
      try {
        const logs = await getExecutionTicketLogs(ticketId, 120);
        setTicketLogs((prev) => ({ ...prev, [ticketId]: logs }));
      } catch (error) {
        setMessage(error instanceof Error ? error.message : '读取 execution logs 失败');
      }
    }
  };

  const runStartRollout = async (stage: 'stage_1_client' | 'stage_3_clients' | 'stage_10_clients') => {
    if (!clientId) return;
    if (stage === 'stage_1_client' && rolloutClientIds.length !== 1) {
      setMessage('stage_1_client 必须只填写 1 个 clientId');
      return;
    }
    if (stage === 'stage_3_clients' && rolloutClientIds.length < 3) {
      setMessage('stage_3_clients 至少需要 3 个 clientId');
      return;
    }
    if (stage === 'stage_10_clients' && rolloutClientIds.length < 10) {
      setMessage('stage_10_clients 至少需要 10 个 clientId');
      return;
    }
    setBusyId(`rollout:start:${stage}`);
    try {
      const started = await startKernelPrimaryRollout({
        stage,
        clientIds: rolloutClientIds,
        note: `ops panel start ${stage}`,
      });
      setMessage(`rollout 已启动：${started.id}`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '启动 rollout 失败');
    } finally {
      setBusyId(null);
    }
  };

  const runEnsureSchema = async () => {
    setBusyId('schema:ensure');
    try {
      const ensured = await ensureDataCenterSchema();
      setSchemaStatus(ensured);
      setSchemaStatusError('');
      setMessage(`schema ensure 完成：ensured=${ensured.ensuredTables.length} missing=${ensured.missingTables.length}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'schema ensure 失败');
    } finally {
      setBusyId(null);
    }
  };

  const runCompleteRollout = async (runId: string) => {
    setBusyId(`rollout:complete:${runId}`);
    try {
      const completed = await completeKernelPrimaryRollout(runId);
      setMessage(`rollout 完成：${completed.status} / ${completed.verdict ?? 'n/a'}`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '完成 rollout 失败');
    } finally {
      setBusyId(null);
    }
  };

  const runRollbackRollout = async (runId: string) => {
    if (!window.confirm(`确认回滚 rollout ${runId} 吗？`)) return;
    setBusyId(`rollout:rollback:${runId}`);
    try {
      const rolledBack = await rollbackKernelPrimaryRollout(runId, { reason: 'manual rollback from ops panel' });
      setMessage(`rollout 已回滚：${rolledBack.id}`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '回滚 rollout 失败');
    } finally {
      setBusyId(null);
    }
  };

  const runCreateQualitySnapshot = async () => {
    setBusyId('quality:snapshot');
    try {
      const snapshot = await createEvidenceQualitySnapshot(7);
      setMessage(`已生成质量快照：${snapshot.id}`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '生成质量快照失败');
    } finally {
      setBusyId(null);
    }
  };

  const runRollbackDrillAction = async (dryRun: boolean) => {
    setBusyId(`rollback-drill:${dryRun ? 'dry' : 'apply'}`);
    try {
      const result = await runDataCenterRollbackDrill({
        clientIds: clientId ? [clientId] : [],
        dryRun,
      });
      setRollbackDrill(result);
      setMessage(
        dryRun
          ? 'rollback drill dry-run 已完成'
          : (result.applied ? 'rollback drill 已执行' : 'rollback drill 未执行'),
      );
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'rollback drill 失败');
    } finally {
      setBusyId(null);
    }
  };

  const copyCommand = async (command: string, successMessage: string) => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(command);
        setMessage(successMessage);
        return;
      }
    } catch {
      // fall through to show command in message
    }
    setMessage(`${successMessage}：${command}`);
  };

  if (!canLoad || !clientId) return null;

  return (
    <div className="space-y-4">
      <DataCenterReadinessPanel clientId={clientId} />
      <DataCenterDiagnosticsPanel clientId={clientId} />
      <WorkspaceAnswerValuePanel clientId={clientId} />

      <div className="rounded-2xl border border-gray-100 bg-white p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="text-[12px] font-bold text-gray-800">Data Center Operational Status</p>
            <p className="text-[11px] text-gray-500">灰度阶段、重试告警、快照与回滚演练状态</p>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1 text-[10px] font-semibold text-gray-700 hover:bg-gray-100"
          >
            refresh status
          </button>
        </div>
        <div className="grid grid-cols-2 gap-2 text-[11px] text-gray-700">
          <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">
            rollout stage: {operationalStatusView.rolloutStage}
          </div>
          <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">
            rollout verdict: {operationalStatusView.rolloutVerdict}
          </div>
          <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">
            retry alerts: {operationalStatusView.executionRetryAlertCount}
          </div>
          <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">
            latest snapshot: {operationalStatusView.latestSnapshotAt ?? 'n/a'}
          </div>
          <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">
            rollback drill: {operationalStatusView.rollbackDrillStatus}
          </div>
          <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">
            full regression verdict: {operationalStatusView.fullRegressionVerdict}
          </div>
          <div className={`rounded-md border px-2 py-1 ${staleArtifactCount > 0 ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>
            artifact freshness: {staleArtifactCount > 0 ? `hold · stale(${staleArtifactCount})` : 'pass'}
          </div>
          <div className={`rounded-md border px-2 py-1 ${schemaHealthy ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
            schema registry: {schemaHealthy ? 'pass' : 'hold'}
          </div>
        </div>
        {artifactStatus?.items?.length ? (
          <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-[11px] text-gray-700 space-y-1">
            <div className="font-semibold">artifact status</div>
            <div className="flex flex-wrap gap-2">
              {artifactStatus.items.map((item) => (
                <span
                  key={item.key}
                  className={`rounded-full border px-2 py-1 text-[10px] font-semibold ${
                    item.stale || item.verdict !== 'pass'
                      ? 'border-amber-200 bg-amber-50 text-amber-700'
                      : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  }`}
                >
                  {item.label}: {item.verdict}{item.stale ? ' · stale' : ''}
                </span>
              ))}
            </div>
          </div>
        ) : null}
        {schemaStatus ? (
          <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-[11px] text-gray-700 space-y-1">
            <div className="font-semibold">schema status</div>
            <div>ensured: {schemaStatus.ensuredTables.length}</div>
            <div>missing: {schemaStatus.missingTables.length}</div>
            {schemaStatus.errors.length ? <div className="text-rose-600">errors: {schemaStatus.errors.join(' | ')}</div> : null}
          </div>
        ) : null}
        {(operationalStatusError || artifactStatusError || schemaStatusError) ? (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700 space-y-1">
            {operationalStatusError ? <div>operational status: {operationalStatusError}</div> : null}
            {artifactStatusError ? <div>artifact status: {artifactStatusError}</div> : null}
            {schemaStatusError ? <div>schema status: {schemaStatusError}</div> : null}
          </div>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void copyCommand(
              'cd backend && uv run python scripts/run_data_center_full_regression_p25.py',
              '已复制 full regression 命令',
            )}
            className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-[10px] font-semibold text-indigo-700 hover:bg-indigo-100"
          >
            Run full regression report
          </button>
          <button
            type="button"
            onClick={() => void copyCommand(
              'cd backend && uv run python scripts/generate_data_center_rc2_release_report.py',
              '已复制 RC2 report 命令',
            )}
            className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-[10px] font-semibold text-indigo-700 hover:bg-indigo-100"
          >
            Generate RC2 report
          </button>
          <button
            type="button"
            onClick={() => void runEnsureSchema()}
            disabled={busyId === 'schema:ensure'}
            className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] font-semibold text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
          >
            {busyId === 'schema:ensure' ? 'ensuring…' : 'Ensure schema'}
          </button>
        </div>
      </div>

      <div className="rounded-2xl border border-gray-100 bg-white p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="text-[12px] font-bold text-gray-800">Proposals</p>
            <p className="text-[11px] text-gray-500">审批、预览、批量操作与执行票据创建</p>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading}
            className="rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1.5 text-[11px] font-semibold text-gray-700 hover:bg-gray-100 disabled:opacity-50"
          >
            {loading ? '刷新中…' : '刷新'}
          </button>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <select
            value={proposalStatus}
            onChange={(event) => setProposalStatus(event.target.value as ProposalStatusFilter)}
            className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-[11px] text-gray-700"
          >
            <option value="all">proposal 状态：全部</option>
            <option value="pending_review">pending_review</option>
            <option value="approved">approved</option>
            <option value="rejected">rejected</option>
            <option value="execution_pending">execution_pending</option>
            <option value="executed">executed</option>
            <option value="failed">failed</option>
          </select>
          <select
            value={proposalKind}
            onChange={(event) => setProposalKind(event.target.value as ProposalKindFilter)}
            className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-[11px] text-gray-700"
          >
            <option value="all">proposal 类型：全部</option>
            <option value="meeting_followup">meeting_followup</option>
            <option value="task_prep">task_prep</option>
            <option value="meeting_prep">meeting_prep</option>
            <option value="evidence_request">evidence_request</option>
            <option value="judgment_review">judgment_review</option>
            <option value="context_refresh">context_refresh</option>
          </select>
          <select
            value={ticketStatus}
            onChange={(event) => setTicketStatus(event.target.value as TicketStatusFilter)}
            className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-[11px] text-gray-700"
          >
            <option value="all">ticket 状态：全部</option>
            <option value="pending">pending</option>
            <option value="running">running</option>
            <option value="executed">executed</option>
            <option value="failed">failed</option>
          </select>
        </div>

        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-gray-100 bg-gray-50 px-2 py-2">
          <label className="flex items-center gap-2 text-[11px] text-gray-700">
            <input type="checkbox" checked={allVisibleSelected} onChange={toggleAllVisible} />
            全选当前列表
          </label>
          <button
            type="button"
            disabled={busyId === 'approve' || selectedProposalIds.size === 0}
            onClick={() => void runBatchProposalAction('approve')}
            className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] font-semibold text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
          >
            batch approve
          </button>
          <button
            type="button"
            disabled={busyId === 'reject' || selectedProposalIds.size === 0}
            onClick={() => void runBatchProposalAction('reject')}
            className="rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-[10px] font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-50"
          >
            batch reject
          </button>
        </div>

        <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
          {proposalsError ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">
              proposals: {proposalsError}
            </div>
          ) : null}
          {proposals.map((item) => {
            const disabled = busyId === item.id;
            const canApprove = item.status === 'pending_review';
            const canReject = item.status === 'pending_review' || item.status === 'approved';
            const canCreateTicket = item.status === 'approved' || item.status === 'execution_pending' || item.status === 'executed';
            const checked = selectedProposalIds.has(item.id);
            return (
              <div key={item.id} className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <label className="flex items-center gap-2">
                      <input type="checkbox" checked={checked} onChange={() => toggleProposal(item.id)} />
                      <p className="text-[12px] font-semibold text-gray-800 truncate">{item.title}</p>
                    </label>
                    <p className="text-[11px] text-gray-500 line-clamp-2">{item.summary || item.rationale}</p>
                  </div>
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusClass(item.status)}`}>
                    {item.status}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={disabled || !canApprove}
                    onClick={() => void runProposalAction(item.id, 'approve')}
                    className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] font-semibold text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
                  >
                    approve
                  </button>
                  <button
                    type="button"
                    disabled={disabled || !canReject}
                    onClick={() => void runProposalAction(item.id, 'reject')}
                    className="rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-[10px] font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-50"
                  >
                    reject
                  </button>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => void runProposalAction(item.id, 'preview')}
                    className="rounded-md border border-gray-200 bg-white px-2 py-1 text-[10px] font-semibold text-gray-700 hover:bg-gray-100 disabled:opacity-50"
                  >
                    execution preview
                  </button>
                  <button
                    type="button"
                    disabled={disabled || !canCreateTicket}
                    onClick={() => void runProposalAction(item.id, 'createTicket')}
                    className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-[10px] font-semibold text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                  >
                    create ticket
                  </button>
                </div>
              </div>
            );
          })}
          {proposals.length === 0 && !loading ? (
            <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-3 py-4 text-[11px] text-gray-500">
              当前筛选条件下没有 proposal
            </div>
          ) : null}
        </div>
      </div>

      <div className="rounded-2xl border border-gray-100 bg-white p-4 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[12px] font-bold text-gray-800">Execution Tickets</p>
          <p className="text-[11px] text-gray-500">执行动作需确认，失败可重试</p>
        </div>
        <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
          {ticketsError ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">
              tickets: {ticketsError}
            </div>
          ) : null}
          {tickets.map((ticket) => {
            const linkedProposal = proposalMap.get(ticket.proposalId);
            const disabled = busyId === ticket.id;
            const highRisk = linkedProposal?.riskLevel === 'high';
            const executable = ticket.status === 'pending' || ticket.status === 'running';
            const retryable = ticket.status === 'failed' && (ticket.retryCount ?? 0) < (ticket.maxRetries ?? 3);
            const showLogs = expandedTicketId === ticket.id;
            const previewReady = previewedProposalIds.has(ticket.proposalId);
            return (
              <div key={ticket.id} className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-[11px] font-semibold text-gray-800 truncate">{ticket.executionType} · {ticket.id}</p>
                    <p className="text-[10px] text-gray-500 truncate">
                      proposal: {ticket.proposalId} · retry {ticket.retryCount ?? 0}/{ticket.maxRetries ?? 3}
                    </p>
                  </div>
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusClass(ticket.status)}`}>
                    {ticket.status}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={disabled || !executable || highRisk || !previewReady}
                    onClick={() => void runTicketExecute(ticket)}
                    className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] font-semibold text-amber-700 hover:bg-amber-100 disabled:opacity-50"
                  >
                    确认执行
                  </button>
                  <button
                    type="button"
                    disabled={busyId === `retry:${ticket.id}` || !retryable}
                    onClick={() => void runTicketRetry(ticket)}
                    className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-[10px] font-semibold text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                  >
                    retry
                  </button>
                  <button
                    type="button"
                    onClick={() => void toggleTicketLogs(ticket.id)}
                    className="rounded-md border border-gray-200 bg-white px-2 py-1 text-[10px] font-semibold text-gray-700 hover:bg-gray-100"
                  >
                    {showLogs ? '隐藏 logs' : 'execution logs'}
                  </button>
                </div>
                {showLogs ? (
                  <div className="rounded-md border border-gray-200 bg-white px-2 py-2 space-y-1">
                    {(ticketLogs[ticket.id] || []).map((log) => (
                      <div key={log.id} className="text-[10px] text-gray-600">
                        [{log.stage}] {log.status} · {log.message || 'ok'}
                      </div>
                    ))}
                    {!(ticketLogs[ticket.id] || []).length ? (
                      <p className="text-[10px] text-gray-500">暂无 execution logs</p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })}
          {tickets.length === 0 && !loading ? (
            <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-3 py-4 text-[11px] text-gray-500">
              当前没有 execution ticket
            </div>
          ) : null}
        </div>
      </div>

      <div className="rounded-2xl border border-gray-100 bg-white p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="text-[12px] font-bold text-gray-800">Kernel Rollout Runs</p>
            <p className="text-[11px] text-gray-500">灰度发布阶段控制与回滚入口</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busyId === 'rollout:start:stage_1_client' || !stageClientCountValid.stage_1_client}
              onClick={() => void runStartRollout('stage_1_client')}
              className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-[10px] font-semibold text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
            >
              start stage_1
            </button>
            <button
              type="button"
              disabled={busyId === 'rollout:start:stage_3_clients' || !stageClientCountValid.stage_3_clients}
              onClick={() => void runStartRollout('stage_3_clients')}
              className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-[10px] font-semibold text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
            >
              start stage_3
            </button>
            <button
              type="button"
              disabled={busyId === 'rollout:start:stage_10_clients' || !stageClientCountValid.stage_10_clients}
              onClick={() => void runStartRollout('stage_10_clients')}
              className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-[10px] font-semibold text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
            >
              start stage_10
            </button>
          </div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-3 space-y-2">
          <label className="block text-[11px] font-semibold text-gray-700">
            rollout clientIds
          </label>
          <input
            type="text"
            value={rolloutClientIdsInput}
            onChange={(event) => setRolloutClientIdsInput(event.target.value)}
            placeholder="client_a, client_b, client_c"
            className="w-full rounded-md border border-gray-200 bg-white px-2 py-1.5 text-[11px] text-gray-700"
          />
          <div className="grid grid-cols-3 gap-2 text-[10px] text-gray-600">
            <div className={`rounded-md border px-2 py-1 ${stageClientCountValid.stage_1_client ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
              stage_1: 需要 1 个，当前 {rolloutClientIds.length}
            </div>
            <div className={`rounded-md border px-2 py-1 ${stageClientCountValid.stage_3_clients ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
              stage_3: 需要 ≥3 个，当前 {rolloutClientIds.length}
            </div>
            <div className={`rounded-md border px-2 py-1 ${stageClientCountValid.stage_10_clients ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
              stage_10: 需要 ≥10 个，当前 {rolloutClientIds.length}
            </div>
          </div>
          {rolloutError ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">
              rollout: {rolloutError}
            </div>
          ) : null}
        </div>
        <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
          {rolloutRuns.map((run) => (
            <div key={run.id} className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <p className="text-[11px] font-semibold text-gray-800">{run.stage} · {run.id}</p>
                <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusClass(run.status)}`}>
                  {run.status}
                </span>
              </div>
              <p className="text-[10px] text-gray-500">
                verdict: {run.verdict ?? 'n/a'} · recommended: {run.recommendedAction ?? 'n/a'}
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busyId === `rollout:complete:${run.id}` || !(run.status === 'running' || run.status === 'planned')}
                  onClick={() => void runCompleteRollout(run.id)}
                  className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] font-semibold text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
                >
                  complete
                </button>
                <button
                  type="button"
                  disabled={busyId === `rollout:rollback:${run.id}`}
                  onClick={() => void runRollbackRollout(run.id)}
                  className="rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-[10px] font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-50"
                >
                  rollback
                </button>
              </div>
            </div>
          ))}
          {rolloutRuns.length === 0 ? (
            <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-3 py-3 text-[11px] text-gray-500">
              暂无 rollout run
            </div>
          ) : null}
        </div>
      </div>

      <div className="rounded-2xl border border-gray-100 bg-white p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[12px] font-bold text-gray-800">Execution Retry Metrics</p>
          <button
            type="button"
            onClick={() => void refresh()}
            className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1 text-[10px] font-semibold text-gray-700 hover:bg-gray-100"
          >
            refresh metrics
          </button>
        </div>
        {retryMetrics ? (
          <div className="grid grid-cols-2 gap-2 text-[11px] text-gray-700">
            <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">total: {retryMetrics.totalTickets}</div>
            <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">failed: {retryMetrics.failedTickets}</div>
            <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">retried: {retryMetrics.retriedTickets}</div>
            <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">retry exhausted: {retryMetrics.retryExhaustedTickets}</div>
            <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">
              retry success rate: {((retryMetrics.retrySuccessRate ?? 0) * 100).toFixed(1)}%
            </div>
            <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">
              avg retry count: {(retryMetrics.avgRetryCount ?? 0).toFixed(2)}
            </div>
            <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1">
              oldest failed age(h): {(retryMetrics.oldestFailedTicketAgeHours ?? 0).toFixed(1)}
            </div>
          </div>
        ) : null}
        <div className="grid grid-cols-2 gap-3">
          {retryMetricsError ? (
            <div className="col-span-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">
              retry metrics: {retryMetricsError}
            </div>
          ) : null}
          <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-2">
            <p className="text-[10px] font-semibold text-gray-700">failure reason TopN</p>
            {(retryMetrics?.failureReasonTopN || []).map((item) => (
              <p key={item.key} className="text-[10px] text-gray-600">{item.key} · {item.count}</p>
            ))}
          </div>
          <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-2">
            <p className="text-[10px] font-semibold text-gray-700">failed stage TopN</p>
            {(retryMetrics?.failedStageTopN || []).map((item) => (
              <p key={item.key} className="text-[10px] text-gray-600">{item.key} · {item.count}</p>
            ))}
          </div>
        </div>
        {(retryMetrics?.alerts || []).length ? (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-2 py-2 space-y-1">
            {(retryMetrics?.alerts || []).map((alert, index) => (
              <p key={`${alert.level}-${index}`} className="text-[10px] text-amber-700">{alert.message}</p>
            ))}
          </div>
        ) : null}
      </div>

      <div className="rounded-2xl border border-gray-100 bg-white p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[12px] font-bold text-gray-800">Evidence Quality Snapshots</p>
          <button
            type="button"
            disabled={busyId === 'quality:snapshot'}
            onClick={() => void runCreateQualitySnapshot()}
            className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-[10px] font-semibold text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
          >
            create snapshot
          </button>
        </div>
        <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
          {snapshotsError ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">
              snapshots: {snapshotsError}
            </div>
          ) : null}
          {qualitySnapshots.map((snapshot) => (
            <div key={snapshot.id} className="rounded-md border border-gray-200 bg-gray-50 px-2 py-2">
              <p className="text-[10px] font-semibold text-gray-700">{snapshot.id}</p>
              <p className="text-[10px] text-gray-600">
                useful:{snapshot.labelCounts?.useful ?? 0} · noise:{snapshot.labelCounts?.noise ?? 0} · needs_review:{snapshot.labelCounts?.needs_review ?? 0}
              </p>
            </div>
          ))}
          {qualitySnapshots.length === 0 ? (
            <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-3 py-3 text-[11px] text-gray-500">
              暂无 feedback snapshot
            </div>
          ) : null}
        </div>
      </div>

      <div className="rounded-2xl border border-gray-100 bg-white p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[12px] font-bold text-gray-800">Rollback Drill</p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busyId === 'rollback-drill:dry'}
              onClick={() => void runRollbackDrillAction(true)}
              className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1 text-[10px] font-semibold text-gray-700 hover:bg-gray-100 disabled:opacity-50"
            >
              rollback drill (dry-run)
            </button>
            <button
              type="button"
              disabled={busyId === 'rollback-drill:apply'}
              onClick={() => void runRollbackDrillAction(false)}
              className="rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-[10px] font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-50"
            >
              apply rollback
            </button>
          </div>
        </div>
        {rollbackDrill ? (
          <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-2 space-y-1 text-[10px] text-gray-700">
            <p>dryRun: {String(rollbackDrill.dryRun)} · applied: {String(rollbackDrill.applied)}</p>
            <p>wouldDisableWorkspacePrimary: {String(rollbackDrill.wouldDisableWorkspacePrimary)}</p>
            <p>wouldClearAllowlist: {String(rollbackDrill.wouldClearAllowlist)}</p>
            {(rollbackDrill.warnings || []).map((warning, index) => (
              <p key={`${warning}-${index}`} className="text-amber-700">{warning}</p>
            ))}
          </div>
        ) : null}
      </div>

      {message ? <p className="text-[11px] text-gray-600">{message}</p> : null}
      <p className="text-[10px] text-gray-500">执行前请先查看 execution preview，且所有高风险 proposal 默认禁用执行按钮。</p>
    </div>
  );
}
