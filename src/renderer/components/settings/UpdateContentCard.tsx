import React from 'react';
import { Sparkles, Wrench, Gauge, AlertTriangle } from 'lucide-react';

/**
 * 「查看更新内容」展示卡。本阶段为纯界面 mock,数据后续由 release 记录的
 * 用户版 changelog 驱动(GET /api/v1/app/update-policy 的 changelogUser)。
 */

interface ChangelogGroup {
  readonly key: 'feature' | 'fix' | 'polish' | 'known';
  readonly label: string;
  readonly icon: typeof Sparkles;
  readonly tone: string;
  readonly items: readonly string[];
}

const MOCK_VERSION = '0.2.3';

const MOCK_GROUPS: readonly ChangelogGroup[] = [
  {
    key: 'feature',
    label: '新增',
    icon: Sparkles,
    tone: 'text-indigo-600',
    items: ['软件内「报错 / 建议」入口', '更新内容查看页'],
  },
  {
    key: 'fix',
    label: '修复',
    icon: Wrench,
    tone: 'text-emerald-600',
    items: ['战略陪伴状态显示异常', '工作台文件数量不一致'],
  },
  {
    key: 'polish',
    label: '优化',
    icon: Gauge,
    tone: 'text-sky-600',
    items: ['更新提醒更克制,默认静默不打扰'],
  },
  {
    key: 'known',
    label: '已知问题',
    icon: AlertTriangle,
    tone: 'text-amber-600',
    items: ['导入超大文件偶发卡顿(下个版本修复)'],
  },
];

interface UpdateContentCardProps {
  version?: string;
}

export function UpdateContentCard({ version = MOCK_VERSION }: UpdateContentCardProps): React.ReactElement {
  return (
    <div className="mt-4 rounded-xl border border-gray-100 bg-gray-50/60 p-4">
      <p className="text-[12px] font-medium text-gray-900">
        本次更新 · v{version}
      </p>
      <div className="mt-3 space-y-3">
        {MOCK_GROUPS.map((group) => {
          const Icon = group.icon;
          return (
            <div key={group.key} className="flex gap-2.5">
              <Icon size={14} className={`mt-[2px] shrink-0 ${group.tone}`} />
              <div className="min-w-0">
                <p className="text-[12px] font-medium text-gray-700">{group.label}</p>
                <ul className="mt-1 space-y-0.5">
                  {group.items.map((item) => (
                    <li key={item} className="text-[12px] leading-relaxed text-gray-500">
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-[10px] text-gray-400">示例内容 · 接入数据后由本次发版的更新说明自动填充</p>
    </div>
  );
}
