import type { ReviewDepartmentConfig, ReviewDepartmentMember, ReviewGovernanceSettings } from '../../../shared/types';

const GOVERNANCE_COLORS = ['#5B7BFE', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#14B8A6'];

type ReviewGovernanceSettingsPanelProps = {
  value: ReviewGovernanceSettings;
  canEdit: boolean;
  availableMembers: ReviewDepartmentMember[];
  isSaving?: boolean;
  onChange: (next: ReviewGovernanceSettings) => void;
  onSave: () => void;
};

function dedupeMembers(members: ReviewDepartmentMember[]) {
  const seen = new Set<string>();
  const next: ReviewDepartmentMember[] = [];
  members.forEach((member) => {
    const fullName = member.fullName.trim();
    if (!fullName) return;
    const key = fullName.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    next.push({ ...member, fullName });
  });
  return next;
}

function parseMembers(text: string, availableMembers: ReviewDepartmentMember[]) {
  const byName = new Map(availableMembers.map((member) => [member.fullName.trim().toLowerCase(), member]));
  const names = text
    .split(/[\n,，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
  return dedupeMembers(
    names.map((name) => {
      const matched = byName.get(name.toLowerCase());
      return matched ? { ...matched } : { id: '', fullName: name };
    }),
  );
}

function toggleMember(members: ReviewDepartmentMember[], candidate: ReviewDepartmentMember) {
  const key = candidate.fullName.trim().toLowerCase();
  const exists = members.some((member) => member.fullName.trim().toLowerCase() === key);
  if (exists) {
    return members.filter((member) => member.fullName.trim().toLowerCase() !== key);
  }
  return dedupeMembers([...members, candidate]);
}

export function ReviewGovernanceSettingsPanel({
  value,
  canEdit,
  availableMembers,
  isSaving = false,
  onChange,
  onSave,
}: ReviewGovernanceSettingsPanelProps) {
  const updateDepartment = (index: number, updater: (current: ReviewDepartmentConfig) => ReviewDepartmentConfig) => {
    onChange({
      ...value,
      departments: value.departments.map((department, departmentIndex) => (departmentIndex === index ? updater(department) : department)),
    });
  };

  return (
    <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[16px] font-bold text-gray-900">周复盘聚合治理</h2>
          <p className="text-[12px] text-gray-500 mt-1">部门目录已固定为四个：咨询策略部、科技发展部、信息数据部、客户服务部。这里维护部门负责人、月度 DNA 和本周重点计划，成员归属默认跟随邀请码加入的部门。</p>
        </div>
        <button
          type="button"
          className="rounded-2xl bg-[#5B7BFE] px-4 py-2 text-[12px] font-bold text-white shadow-[0_10px_30px_rgba(91,123,254,0.24)] disabled:cursor-not-allowed disabled:opacity-50"
          onClick={onSave}
          disabled={!canEdit || isSaving}
        >
          {isSaving ? '保存中...' : '保存治理设置'}
        </button>
      </div>

      <div className="rounded-[24px] border border-blue-100 bg-blue-50/70 px-4 py-3 text-[12px] leading-6 text-[#4256C5]">
        普通同事不能新增部门，只能从机构已有四部门中选择自己的所属部门。CEO 在这里维护四部门的负责人、月度 DNA 和本周重点计划，周复盘部门聚合会直接使用这套配置。
      </div>

      <div className="space-y-4">
        {value.departments.map((department, index) => (
          <div key={department.id} className="rounded-[28px] border border-gray-200 bg-gray-50/70 p-5 space-y-4">
            <div className="flex items-center gap-3">
              <span className="h-3 w-3 rounded-full" style={{ backgroundColor: department.color || GOVERNANCE_COLORS[index % GOVERNANCE_COLORS.length] }} />
              <div>
                <p className="text-[14px] font-bold text-gray-900">{department.name || `部门 ${index + 1}`}</p>
                <p className="mt-1 text-[11px] text-gray-500">固定部门目录，不支持新增、删除或改名。</p>
              </div>
            </div>

            <textarea
              value={department.monthlyDna}
              onChange={(event) => updateDepartment(index, (current) => ({ ...current, monthlyDna: event.target.value }))}
              placeholder="填写这个部门本月主要做什么、为什么做、什么算偏离计划。"
              className="min-h-[96px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 outline-none resize-none"
              disabled={!canEdit}
            />

            <textarea
              value={department.weeklyFocus}
              onChange={(event) => updateDepartment(index, (current) => ({ ...current, weeklyFocus: event.target.value }))}
              placeholder="填写这个部门本周最重要的 3-5 条重点计划、关键动作或必须收口的事项。"
              className="min-h-[88px] w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-[13px] leading-6 outline-none resize-none"
              disabled={!canEdit}
            />

            <div className="space-y-3 rounded-[24px] border border-gray-200 bg-white p-4">
              <div>
                <p className="text-[12px] font-bold text-gray-900">部门负责人</p>
                <p className="mt-1 text-[11px] leading-5 text-gray-500">这里配置的人可以在周复盘里看到“我的总结 + 本部门总结”。</p>
              </div>
              <textarea
                value={department.leaders.map((member) => member.fullName).join('、')}
                onChange={(event) => updateDepartment(index, (current) => ({ ...current, leaders: parseMembers(event.target.value, availableMembers) }))}
                placeholder="部门负责人，支持逗号、顿号或换行分隔。"
                className="min-h-[72px] w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-[13px] leading-6 outline-none resize-none"
                disabled={!canEdit}
              />
              {availableMembers.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {availableMembers.map((member) => {
                    const active = department.leaders.some((item) => item.fullName.trim().toLowerCase() === member.fullName.trim().toLowerCase());
                    return (
                      <button
                        key={`leader:${department.id}:${member.id}:${member.fullName}`}
                        type="button"
                        className={`rounded-full px-3 py-1.5 text-[11px] font-bold transition ${
                          active ? 'bg-emerald-500 text-white' : 'bg-gray-50 text-gray-600 border border-gray-200'
                        }`}
                        onClick={() => updateDepartment(index, (current) => ({ ...current, leaders: toggleMember(current.leaders, member) }))}
                        disabled={!canEdit}
                      >
                        {member.fullName}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="space-y-3 rounded-[24px] border border-gray-200 bg-white p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[12px] font-bold text-gray-900">部门成员</p>
                  <p className="mt-1 text-[11px] leading-5 text-gray-500">成员归属默认跟随邀请码加入的部门，不在这里手工输入。</p>
                </div>
                <span className="rounded-full bg-gray-100 px-3 py-1 text-[11px] font-bold text-gray-600">{department.members.length} 人</span>
              </div>
              {department.members.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {department.members.map((member) => (
                    <span key={`${department.id}:${member.id}:${member.fullName}`} className="rounded-full border border-gray-200 bg-gray-50 px-3 py-1.5 text-[11px] font-medium text-gray-700">
                      {member.fullName}
                    </span>
                  ))}
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-4 py-3 text-[12px] leading-6 text-gray-500">
                  当前还没有员工归属到这个部门。请先邀请成员通过对应部门的邀请码加入。
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {value.departments.length === 0 && (
        <div className="rounded-3xl border border-dashed border-gray-200 bg-gray-50 px-5 py-6 text-[13px] leading-6 text-gray-500">
          还没有加载到部门治理配置。请先检查当前机构部门目录是否可用。
        </div>
      )}
    </div>
  );
}
