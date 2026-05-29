import { useCallback, useEffect, useState } from 'react';
import {
  Loader2,
  RefreshCw,
} from 'lucide-react';
import {
  getMaintenanceModeMembers,
  updateMaintenanceModeMembers,
} from '../../lib/api';
import type {
  MaintenanceModeStatus,
  MaintenanceMemberPermission,
} from '../../../shared/types';

type MaintenanceSyncPanelProps = {
  maintenanceModeStatus: MaintenanceModeStatus | null;
  maintenanceModeError: string | null;
  maintenanceModeLoading: boolean;
  maintenanceModeBusyAction: 'enter' | 'exit' | null;
  onRefreshMaintenanceMode: () => void;
  onEnterMaintenanceMode: () => void;
  onExitMaintenanceMode: () => void;
};

function statusLabel(status: MaintenanceModeStatus | null, error: string | null) {
  if (error) return error;
  if (!status) return '状态未加载';
  if (status.active) return '推送同步已打开';
  if (!status.available) return status.reason || '推送同步不可用';
  if (!status.canEnter) return status.reason || '当前账号没有维护权限';
  return '推送同步已关闭';
}

export function MaintenanceSyncPanel({
  maintenanceModeStatus,
  maintenanceModeError,
  maintenanceModeLoading,
  maintenanceModeBusyAction,
  onRefreshMaintenanceMode,
  onEnterMaintenanceMode,
  onExitMaintenanceMode,
}: MaintenanceSyncPanelProps) {
  const [members, setMembers] = useState<MaintenanceMemberPermission[]>([]);
  const [isMembersLoading, setIsMembersLoading] = useState(false);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [savingMemberId, setSavingMemberId] = useState<string | null>(null);

  const canManagePermissions = Boolean(maintenanceModeStatus?.canManagePermissions);
  const isActive = Boolean(maintenanceModeStatus?.active);
  const canEnter = Boolean(
    maintenanceModeStatus?.available
    && maintenanceModeStatus.canEnter
    && !maintenanceModeStatus.active,
  );

  const loadMembers = useCallback(async () => {
    setIsMembersLoading(true);
    setMembersError(null);
    try {
      const list = await getMaintenanceModeMembers();
      setMembers(list);
    } catch (error) {
      setMembersError(error instanceof Error ? error.message : '员工授权列表加载失败');
    } finally {
      setIsMembersLoading(false);
    }
  }, []);

  useEffect(() => {
    if (canManagePermissions) {
      void loadMembers();
    } else {
      setMembers([]);
    }
  }, [canManagePermissions, loadMembers]);

  const handleToggleAuthorized = useCallback(async (member: MaintenanceMemberPermission, nextAuthorized: boolean) => {
    if (member.primaryRole === 'admin') return;
    setSavingMemberId(member.userId);
    setMembersError(null);
    try {
      const updated = await updateMaintenanceModeMembers({
        members: [
          {
            userId: member.userId,
            authorized: nextAuthorized,
            canManagePermissions: nextAuthorized ? member.canManagePermissions : false,
          },
        ],
      });
      setMembers(updated);
    } catch (error) {
      setMembersError(error instanceof Error ? error.message : '保存失败');
    } finally {
      setSavingMemberId(null);
    }
  }, []);

  // toggle 行为:由后端 canEnter / canExit 决定。
  // 「admin 直通」语义 = admin 不需要走员工授权列表,后端已直接给 canEnter=true,
  // 前端这里不该再额外把 isAdmin 当 disable / 拦截点击,否则 admin 反而点不动开关。
  const toggleDisabled = maintenanceModeLoading
    || maintenanceModeBusyAction !== null
    || (!isActive && !canEnter);
  const handleToggle = () => {
    if (isActive) {
      onExitMaintenanceMode();
    } else {
      onEnterMaintenanceMode();
    }
  };
  const isBusy = maintenanceModeBusyAction !== null;

  return (
    <div className="space-y-7">
      {/* ──── 维护模式 toggle ──── */}
      <div>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={handleToggle}
              disabled={toggleDisabled}
              title={isActive ? '点击关闭维护模式' : (canEnter ? '点击打开维护模式' : '当前账号无维护权限')}
              className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500/30 ${
                isActive ? 'bg-emerald-500' : 'bg-gray-300'
              } ${toggleDisabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer hover:opacity-90'}`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  isActive ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
              {isBusy && (
                <Loader2 size={10} className="absolute right-1.5 top-1.5 animate-spin text-white" />
              )}
            </button>
            <div className="min-w-0">
              <p className="text-[13px] font-medium text-gray-900">维护模式</p>
              <p className="mt-0.5 text-[11px] text-gray-500 truncate">{statusLabel(maintenanceModeStatus, maintenanceModeError)}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onRefreshMaintenanceMode}
            disabled={maintenanceModeLoading || isBusy}
            className="shrink-0 inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-[11px] font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            <RefreshCw size={12} className={maintenanceModeLoading ? 'animate-spin' : ''} />
            刷新
          </button>
        </div>
      </div>

      {/* ──── 授权同事区 ── 仅 admin / 可管理者可见 ──── */}
      {canManagePermissions && (
        <div className="border-t border-gray-100 pt-5">
          <div className="flex items-start justify-between gap-3 mb-3">
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gray-400">授权同事</p>
              <p className="mt-1.5 text-[11px] text-gray-500 leading-relaxed">勾选后该同事可在自己的应用里打开推送同步,把代码改动同步给你。管理员默认拥有权限。</p>
            </div>
            <button
              type="button"
              onClick={() => void loadMembers()}
              disabled={isMembersLoading}
              className="shrink-0 inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-[11px] font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              <RefreshCw size={12} className={isMembersLoading ? 'animate-spin' : ''} />
              刷新
            </button>
          </div>

          {membersError && (
            <p className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-[11px] text-rose-600 mb-3">{membersError}</p>
          )}

          {isMembersLoading && members.length === 0 ? (
            <p className="text-[11px] text-gray-400 py-3">加载中…</p>
          ) : members.length === 0 ? (
            <p className="text-[11px] text-gray-400 py-3 text-center">暂无可授权的同事</p>
          ) : (
            <div>
              {members.map((member) => {
                const memberIsAdmin = member.primaryRole === 'admin';
                const isSaving = savingMemberId === member.userId;
                return (
                  <label
                    key={member.userId}
                    className={`flex items-center gap-3 -mx-2 px-2 py-2.5 rounded-md transition-colors ${
                      memberIsAdmin ? '' : 'cursor-pointer hover:bg-gray-50/70'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={memberIsAdmin || member.authorized}
                      onChange={(e) => {
                        if (memberIsAdmin) return;
                        void handleToggleAuthorized(member, e.target.checked);
                      }}
                      disabled={memberIsAdmin || isSaving}
                      className="h-4 w-4 rounded border-gray-300 text-[#5B7BFE] focus:ring-[#5B7BFE]/30 disabled:opacity-50"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[13px] font-medium text-gray-900 truncate">{member.fullName}</span>
                        {memberIsAdmin && (
                          <span className="rounded-full bg-[#5B7BFE]/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em] text-[#5B7BFE]">管理员</span>
                        )}
                        {!memberIsAdmin && member.canManagePermissions && (
                          <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em] text-emerald-700">可代管理</span>
                        )}
                      </div>
                      <p className="mt-0.5 text-[11px] text-gray-400 truncate">{member.email}</p>
                    </div>
                    {isSaving && <Loader2 size={12} className="animate-spin text-gray-400 shrink-0" />}
                  </label>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default MaintenanceSyncPanel;
