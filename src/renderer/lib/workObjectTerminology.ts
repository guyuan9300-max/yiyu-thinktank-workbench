import type { ResolvedTerminologyConfig, WorkObjectTerminologyState } from '../../shared/types';

const DEFAULT_STATE: WorkObjectTerminologyState = {
  localMode: null,
  organizationMode: null,
  effectiveMode: 'project',
  source: 'default',
  lockedByOrganization: false,
  needsOnboarding: false,
  updatedAt: '',
};

export function resolveWorkObjectTerminology(
  state: WorkObjectTerminologyState | null | undefined,
): ResolvedTerminologyConfig {
  const base = state ?? DEFAULT_STATE;
  const mode = base.effectiveMode === 'client' ? 'client' : 'project';
  const singularLabel = mode === 'client' ? '客户' : '项目';
  const pluralLabel = mode === 'client' ? '客户' : '项目';
  const workspaceLabel = `${singularLabel}工作台`;
  const recentLabel = `近期${pluralLabel}`;
  const statsLabel = pluralLabel;
  const associateLabel = `关联${singularLabel}`;
  return {
    ...base,
    effectiveMode: mode,
    singularLabel,
    pluralLabel,
    workspaceLabel,
    recentLabel,
    statsLabel,
    associateLabel,
    structureLabel: '模块与流程',
  };
}
