/**
 * 顾源源 5/24 大型任务 · 组织搭建中心机器人同事最小 UI
 *
 * 3 子面板:
 *   1. BotMembersList    — 机器人列表 + 添加按钮
 *   2. BotMemberFormDialog — 添加机器人表单 (含汇报线 + 权限)
 *   3. AIPlanApprovalList  — 待审批 AI 任务计划 + approve/reject/revise 按钮
 *
 * 最低工程标准: 可打开 / 可看见 / 可刷新 / 可处理.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { X } from 'lucide-react';
import {
  BOT_CAPABILITY_KEYS,
  createBotMember,
  listBotMembers,
  updateBotMember,
  listBotTaskPlans,
  decideBotTaskPlan,
  type BotCapabilityKey,
  type BotMemberRecord,
  type AITaskPlanRecord,
} from '../../lib/api.js';

const CAPABILITY_LABELS: Record<BotCapabilityKey, { label: string; desc: string }> = {
  'workspace_file_write.request': {
    label: '可申请写入客户工作台正式文件',
    desc: '机器人可以把生成的文档、报告、说明提交为客户工作台文件,但必须经汇报对象审批后才正式写入',
  },
  'data_center_parse.request': {
    label: '可申请触发数据中心解析',
    desc: '机器人可以申请将已确认文件送入数据中心解析,必须审批后执行',
  },
  'external_material_draft.create': {
    label: '可生成对外材料草稿',
    desc: '机器人可以起草对外汇报、合同说明、品牌报告、提案等. 草稿可生成,正式使用必须审批',
  },
  'external_send.request': {
    label: '可申请对外发送',
    desc: '机器人可申请把已确认内容发到飞书、邮件等外部渠道,不能直接发送,必须审批',
  },
  'clarification_resolution.propose': {
    label: '可提出待澄清处理建议',
    desc: '机器人阅读客户待澄清事项,提出采纳/忽略/补充材料/追问建议,最终确认必须由人类完成',
  },
  'inline_approval.allow_from_supervisor': {
    label: '允许主管在指令中直接授权执行',
    desc: '汇报对象在智能指令中说"不用审批,直接执行"时,系统记录为一次正式 inline_approval. 高风险动作仍单独审批.',
  },
};

interface BotMembersPanelProps {
  defaultDepartmentId?: string;
}

export function BotMembersPanel({ defaultDepartmentId }: BotMembersPanelProps = {}): JSX.Element {
  const [tab, setTab] = useState<'members' | 'pending'>('members');
  const [bots, setBots] = useState<BotMemberRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await listBotMembers();
      setBots(resp.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700">
          机器人同事 / AI Member
        </h3>
        <div className="flex items-center gap-2 text-xs">
          <button
            onClick={() => setTab('members')}
            className={`rounded px-2 py-0.5 ${tab === 'members' ? 'bg-blue-100 text-blue-700' : 'text-gray-500'}`}
          >
            成员 ({bots.length})
          </button>
          <button
            onClick={() => setTab('pending')}
            className={`rounded px-2 py-0.5 ${tab === 'pending' ? 'bg-blue-100 text-blue-700' : 'text-gray-500'}`}
          >
            AI 计划待审批
          </button>
          <button
            onClick={() => setShowForm(true)}
            className="rounded bg-blue-600 px-3 py-0.5 text-white hover:bg-blue-700"
          >
            + 添加机器人同事
          </button>
        </div>
      </div>

      {error && <div className="rounded bg-red-50 p-2 text-xs text-red-700">加载失败: {error}</div>}

      {tab === 'members' && (
        <BotMembersList
          bots={bots}
          loading={loading}
          onRefresh={reload}
          onToggleStatus={async (bot) => {
            try {
              await updateBotMember(bot.id, {
                status: bot.status === 'active' ? 'disabled' : 'active',
              });
              await reload();
            } catch (err: unknown) {
              setError(err instanceof Error ? err.message : String(err));
            }
          }}
        />
      )}

      {tab === 'pending' && <AIPlanApprovalList bots={bots} />}

      {showForm && (
        <BotMemberFormDialog
          defaultDepartmentId={defaultDepartmentId}
          onClose={() => setShowForm(false)}
          onCreated={async () => {
            setShowForm(false);
            await reload();
          }}
        />
      )}
    </div>
  );
}

// ────────────── BotMembersList ─────────────

interface BotMembersListProps {
  bots: BotMemberRecord[];
  loading: boolean;
  onRefresh: () => Promise<void>;
  onToggleStatus: (bot: BotMemberRecord) => Promise<void>;
}

function BotMembersList({ bots, loading, onRefresh, onToggleStatus }: BotMembersListProps): JSX.Element {
  if (loading) return <div className="py-4 text-center text-xs text-gray-400">加载中...</div>;
  if (bots.length === 0) {
    return (
      <div className="py-6 text-center text-xs text-gray-400">
        还没有机器人同事 — 点 右上 "+ 添加机器人同事"
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2 text-xs">
      <div className="flex items-center justify-between text-gray-500">
        <span>共 {bots.length} 个机器人</span>
        <button
          onClick={() => void onRefresh()}
          className="rounded border border-gray-200 px-2 py-0.5 hover:bg-gray-50"
        >
          🔄 刷新
        </button>
      </div>
      {bots.map((bot) => {
        const enabledCaps = (bot.capabilities || []).filter((c) => c.enabled);
        return (
          <div
            key={bot.id}
            className={`rounded border p-2 ${bot.status === 'active' ? 'border-gray-200' : 'border-gray-100 bg-gray-50 opacity-70'}`}
          >
            <div className="flex items-center gap-2">
              <span className="rounded bg-purple-100 px-1.5 py-0.5 text-[10px] font-medium text-purple-700">
                AI 同事
              </span>
              <span className="font-medium">{bot.display_name}</span>
              <code className="text-gray-500">@{bot.handle}</code>
              <span className="text-gray-400">· {bot.department_name || '(未设部门)'}</span>
              <span className="ml-auto text-gray-400">{bot.status}</span>
              <button
                onClick={() => void onToggleStatus(bot)}
                className="rounded border border-gray-200 px-2 py-0.5 text-gray-700 hover:bg-gray-100"
              >
                {bot.status === 'active' ? '停用' : '启用'}
              </button>
            </div>
            <div className="mt-1 text-gray-500">
              actor_id: <code>{bot.actor_id}</code>
            </div>
            {bot.description && <div className="mt-1 text-gray-600">{bot.description}</div>}
            <div className="mt-1 text-gray-500">
              汇报: {bot.reporting?.report_to_department_lead ? '本部门领导' : ''}
              {bot.reporting?.report_to_department_lead && bot.reporting?.report_to_ceo ? ' · ' : ''}
              {bot.reporting?.report_to_ceo ? 'CEO' : ''}
              {!bot.reporting?.report_to_department_lead && !bot.reporting?.report_to_ceo && '(未配置)'}
            </div>
            <div className="mt-1 text-gray-500">
              已授权能力 ({enabledCaps.length}):
            </div>
            <div className="ml-2 mt-0.5 flex flex-wrap gap-1">
              {enabledCaps.map((c) => (
                <span key={c.capability_key} className="rounded bg-green-50 px-1.5 py-0.5 text-[10px] text-green-700">
                  {CAPABILITY_LABELS[c.capability_key as BotCapabilityKey]?.label || c.capability_key}
                </span>
              ))}
              {enabledCaps.length === 0 && <span className="text-gray-400">无</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ────────────── BotMemberFormDialog ─────────────

export interface DepartmentChoice {
  id: string;
  name: string;
  color?: string;
}

export interface BotMemberFormDialogProps {
  defaultDepartmentId?: string;
  defaultDepartmentName?: string;
  /** 顾源源 P1 修: 部门必须下拉, 不允许手填 */
  departments?: DepartmentChoice[];
  /** 顾源源 P1 修: 创建人 user_id (汇报给创建人时用) */
  currentUserId?: string;
  currentUserName?: string;
  onClose: () => void;
  onCreated: () => Promise<void> | void;
}

export function BotMemberFormDialog({
  defaultDepartmentId,
  defaultDepartmentName,
  departments,
  currentUserId,
  currentUserName,
  onClose,
  onCreated,
}: BotMemberFormDialogProps): JSX.Element {
  const [displayName, setDisplayName] = useState('');
  // 部门改下拉 — 找当前选中的 dept 对象
  const initialDept = useMemo(() => {
    const list = departments || [];
    return (
      list.find((d) => d.id === defaultDepartmentId) ||
      (defaultDepartmentId && defaultDepartmentName
        ? { id: defaultDepartmentId, name: defaultDepartmentName }
        : null)
    );
  }, [defaultDepartmentId, defaultDepartmentName, departments]);
  const [selectedDept, setSelectedDept] = useState<DepartmentChoice | null>(initialDept || null);
  const [description, setDescription] = useState('');
  // 3 平权汇报线: 创建人 / 本部门领导 / CEO
  const [reportCreator, setReportCreator] = useState(true);
  const [reportDeptLead, setReportDeptLead] = useState(false);
  const [reportCEO, setReportCEO] = useState(false);
  const [enabledCaps, setEnabledCaps] = useState<Set<BotCapabilityKey>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleCap = (cap: BotCapabilityKey) => {
    const next = new Set(enabledCaps);
    if (next.has(cap)) next.delete(cap);
    else next.add(cap);
    setEnabledCaps(next);
  };

  const submit = async () => {
    if (!displayName.trim()) {
      setError('请填机器人名称');
      return;
    }
    if (!selectedDept) {
      setError('请选择所属部门');
      return;
    }
    if (!reportCreator && !reportDeptLead && !reportCEO) {
      setError('至少选择一类汇报对象 (创建人 / 本部门领导 / CEO)');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await createBotMember({
        display_name: displayName.trim(),
        department_id: selectedDept.id,
        department_name: selectedDept.name,
        description: description.trim() || undefined,
        created_by_user_id: currentUserId || undefined,
        report_to_creator: reportCreator,
        report_to_department_lead: reportDeptLead,
        report_to_ceo: reportCEO,
        // 不传 department_leader_user_ids / ceo_user_ids
        // 后端从 mirror_departments / mirror_users 动态 resolve
        enabled_capabilities: Array.from(enabledCaps),
      });
      await onCreated();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-gray-900/30 p-4 backdrop-blur-sm">
      <div className="max-h-[90vh] w-full max-w-[640px] overflow-y-auto rounded-3xl bg-white shadow-2xl ring-1 ring-black/5">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-gray-100 px-8 py-6">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">
              ADD MEMBER · 添加机器人同事
            </p>
            <h3 className="mt-2 text-[18px] font-bold text-gray-900">添加机器人同事</h3>
            <p className="mt-1.5 text-[12px] text-gray-500">
              机器人同事拥有独立身份, 进入运行日志和审批队列, 不能自己审批自己。
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-full text-gray-400 transition hover:bg-gray-100 hover:text-gray-700"
          >
            <X size={16} />
          </button>
        </div>

        {error && (
          <div className="mx-8 mt-5 rounded-xl border border-rose-100 bg-rose-50 px-4 py-2.5 text-[12px] text-rose-700">
            {error}
          </div>
        )}

        <div className="space-y-7 px-8 py-6 text-[13px]">
          {/* 基础信息 */}
          <section>
            <p className="mb-3 text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">基础信息</p>
            <Field label="姓名" required hint="例: 庆华、蔚来、研究员、品牌顾问">
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="庆华"
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-[13px] text-gray-800 outline-none transition placeholder:text-gray-300 focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/15"
              />
            </Field>
            {/* 部门 — 下拉, 从真组织部门列表选, 不允许手填(避免 ID 对不上) */}
            <Field label="所属部门" required hint={departments && departments.length === 0 ? '（当前组织无部门, 请先到组织搭建中心添加部门）' : undefined}>
              <select
                value={selectedDept?.id || ''}
                onChange={(e) => {
                  const dept = (departments || []).find((d) => d.id === e.target.value);
                  setSelectedDept(dept || null);
                }}
                className="w-full appearance-none rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-[13px] text-gray-800 outline-none transition focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/15"
              >
                <option value="">请选择部门…</option>
                {(departments || []).map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
                {selectedDept && !(departments || []).find((d) => d.id === selectedDept.id) ? (
                  <option value={selectedDept.id}>{selectedDept.name}（已选）</option>
                ) : null}
              </select>
            </Field>
            <Field label="职责描述" hint="可选">
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="负责战略陪伴资料整理、报告草稿生成、任务复盘"
                rows={2}
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-[13px] text-gray-800 outline-none transition placeholder:text-gray-300 focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/15"
              />
            </Field>
          </section>

          {/* 汇报线 — 3 类平权, 任一勾选 → 同时通知/审批; user_id 系统自动 resolve */}
          <section>
            <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">汇报与审批人</p>
            <p className="mb-3 text-[12px] text-gray-500">
              勾选的对象同时是该机器人的审批人, 任一人批准即视为通过。系统自动从组织信息读取对应的人, 无需手填 ID。
            </p>
            <div className="space-y-2">
              <label className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-gray-100 bg-gray-50/60 px-3 py-2.5 transition hover:border-gray-200 hover:bg-gray-50">
                <input
                  type="checkbox"
                  checked={reportCreator}
                  onChange={(e) => setReportCreator(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-[#5B7BFE] focus:ring-[#5B7BFE]"
                />
                <span className="text-[13px] text-gray-700">
                  汇报给创建人
                  {currentUserName ? (
                    <span className="ml-1.5 text-[12px] text-gray-400">（{currentUserName}）</span>
                  ) : null}
                </span>
              </label>
              <label className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-gray-100 bg-gray-50/60 px-3 py-2.5 transition hover:border-gray-200 hover:bg-gray-50">
                <input
                  type="checkbox"
                  checked={reportDeptLead}
                  onChange={(e) => setReportDeptLead(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-[#5B7BFE] focus:ring-[#5B7BFE]"
                />
                <span className="text-[13px] text-gray-700">
                  汇报给本部门领导
                  {selectedDept ? (
                    <span className="ml-1.5 text-[12px] text-gray-400">（自动取「{selectedDept.name}」当前领导）</span>
                  ) : null}
                </span>
              </label>
              <label className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-gray-100 bg-gray-50/60 px-3 py-2.5 transition hover:border-gray-200 hover:bg-gray-50">
                <input
                  type="checkbox"
                  checked={reportCEO}
                  onChange={(e) => setReportCEO(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-[#5B7BFE] focus:ring-[#5B7BFE]"
                />
                <span className="text-[13px] text-gray-700">
                  汇报给 CEO
                  <span className="ml-1.5 text-[12px] text-gray-400">（自动取组织 CEO / admin）</span>
                </span>
              </label>
            </div>
          </section>

          {/* 权限 */}
          <section>
            <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">能力授权</p>
            <p className="mb-3 text-[12px] text-gray-500">
              只列涉及正式写入、数据中心解析或对外影响的能力。读取被授权资料、创建自己的任务、写复盘、生成草稿等默认允许。
            </p>
            <div className="flex flex-col gap-2">
              {BOT_CAPABILITY_KEYS.map((cap) => (
                <label
                  key={cap}
                  className={`flex cursor-pointer items-start gap-3 rounded-xl border px-3.5 py-3 transition ${
                    enabledCaps.has(cap)
                      ? 'border-[#5B7BFE]/30 bg-[#5B7BFE]/5'
                      : 'border-gray-100 bg-white hover:border-gray-200 hover:bg-gray-50/60'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={enabledCaps.has(cap)}
                    onChange={() => toggleCap(cap)}
                    className="mt-0.5 h-4 w-4 rounded border-gray-300 text-[#5B7BFE] focus:ring-[#5B7BFE]"
                  />
                  <div className="flex-1">
                    <div className="font-medium">{CAPABILITY_LABELS[cap].label}</div>
                    <div className="text-gray-500">{CAPABILITY_LABELS[cap].desc}</div>
                  </div>
                </label>
              ))}
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t border-gray-100 bg-gray-50/60 px-8 py-4">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white px-5 py-2.5 text-[13px] font-bold text-gray-600 transition hover:border-gray-300 hover:bg-gray-50 disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={() => void submit()}
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-full bg-[#5B7BFE] px-6 py-2.5 text-[13px] font-bold text-white shadow-[0_12px_30px_rgba(91,123,254,0.25)] transition hover:bg-[#4A63CF] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy ? '创建中…' : '创建机器人同事'}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, hint, required, children }: { label: string; hint?: string; required?: boolean; children: React.ReactNode }): JSX.Element {
  return (
    <div className="mt-3 first:mt-0">
      <label className="mb-1.5 flex items-baseline gap-1.5 text-[12px] font-medium text-gray-700">
        <span>{label}</span>
        {required ? <span className="text-rose-400">*</span> : null}
        {hint ? <span className="text-[11px] font-normal text-gray-400">{hint}</span> : null}
      </label>
      <div>{children}</div>
    </div>
  );
}

// ────────────── AIPlanApprovalList ─────────────

function AIPlanApprovalList({ bots }: { bots: BotMemberRecord[] }): JSX.Element {
  const [plans, setPlans] = useState<AITaskPlanRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Record<string, string>>({});

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const all: AITaskPlanRecord[] = [];
      for (const bot of bots) {
        try {
          const resp = await listBotTaskPlans(bot.id, { status: 'pending_approval', limit: 20 });
          all.push(...resp.items);
        } catch {
          /* skip */
        }
      }
      setPlans(all.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')));
    } finally {
      setLoading(false);
    }
  }, [bots]);

  useEffect(() => {
    if (bots.length > 0) void reload();
  }, [bots, reload]);

  const decide = async (planId: string, decision: 'approve' | 'reject' | 'revise') => {
    setBusy(planId);
    try {
      await decideBotTaskPlan(planId, decision, 'human:ui', {
        feedback: feedback[planId] || '',
      });
      await reload();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  const botByMember = useMemo(
    () => new Map(bots.map((b) => [b.id, b])),
    [bots],
  );

  if (loading) return <div className="py-4 text-center text-xs text-gray-400">加载中...</div>;
  if (plans.length === 0) {
    return <div className="py-6 text-center text-xs text-gray-400">无待审批 AI 计划</div>;
  }

  return (
    <div className="flex flex-col gap-2 text-xs">
      <div className="flex items-center justify-between text-gray-500">
        <span>{plans.length} 条待审批 AI 计划</span>
        <button
          onClick={() => void reload()}
          className="rounded border border-gray-200 px-2 py-0.5 hover:bg-gray-50"
        >
          🔄 刷新
        </button>
      </div>
      {error && <div className="rounded bg-red-50 p-2 text-red-700">{error}</div>}
      {plans.map((plan) => {
        const bot = botByMember.get(plan.bot_member_id);
        return (
          <div key={plan.id} className="rounded border border-yellow-200 bg-yellow-50 p-3">
            <div className="flex items-center gap-2">
              <span className="rounded bg-yellow-200 px-1.5 py-0.5 text-[10px] font-medium text-yellow-800">
                AI 执行计划待审批
              </span>
              <span className="font-medium">{plan.plan_title}</span>
            </div>
            <div className="mt-1 text-gray-600">
              机器人: <code>{bot?.display_name || plan.bot_member_id}</code>
              <span className="text-gray-400"> · {bot?.department_name || '?'}</span>
            </div>
            {plan.client_id && (
              <div className="text-gray-500">
                关联客户: <code>{plan.client_id}</code>
              </div>
            )}
            <div className="mt-2 whitespace-pre-wrap text-gray-700">{plan.plan_text}</div>
            {plan.required_modules_json && (
              <div className="mt-1 text-gray-500">
                调用模块: {plan.required_modules_json}
              </div>
            )}
            {plan.expected_outputs_json && (
              <div className="text-gray-500">
                预期产物: {plan.expected_outputs_json}
              </div>
            )}

            <textarea
              value={feedback[plan.id] || ''}
              onChange={(e) => setFeedback((s) => ({ ...s, [plan.id]: e.target.value }))}
              placeholder="(可选) 审批反馈,例如要求重写时说明改什么"
              rows={2}
              className="mt-2 w-full rounded border border-gray-300 px-2 py-1 text-gray-700"
            />

            <div className="mt-2 flex gap-2">
              <button
                onClick={() => void decide(plan.id, 'approve')}
                disabled={busy === plan.id}
                className="rounded bg-green-600 px-3 py-0.5 text-white hover:bg-green-700 disabled:opacity-50"
              >
                批准执行
              </button>
              <button
                onClick={() => void decide(plan.id, 'revise')}
                disabled={busy === plan.id}
                className="rounded bg-yellow-500 px-3 py-0.5 text-white hover:bg-yellow-600 disabled:opacity-50"
              >
                要求重写
              </button>
              <button
                onClick={() => void decide(plan.id, 'reject')}
                disabled={busy === plan.id}
                className="rounded bg-gray-200 px-3 py-0.5 text-gray-700 hover:bg-gray-300 disabled:opacity-50"
              >
                驳回
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
