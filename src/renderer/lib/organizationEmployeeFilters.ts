import type { EmployeeRecord } from '../../shared/types';

type OrganizationIdentity = Pick<EmployeeRecord, 'id' | 'email' | 'fullName'>;

const CURRENT_REAL_ORG_NAMES = new Set(['顾源源', '乐乐', '林佳维']);

const LEGACY_SIMULATION_NAMES = new Set([
  '益语管理员',
  '庆华',
  '嘉宁',
  '一朔',
  '佳乐',
  '大周',
]);

const LEGACY_SIMULATION_IDS = new Set([
  'user_admin',
  'user_qinghua',
  'user_jianing',
  'user_yishuo',
  'user_jiale',
  'user_dazhou',
]);

const LEGACY_SIMULATION_EMAILS = new Set([
  'admin@yiyu-system.com',
  'qinghua@yiyu-system.com',
  'jianing@yiyu-system.com',
  'yishuo@yiyu-system.com',
  'jiale@yiyu-system.com',
  'dazhou@yiyu-system.com',
]);

function normalizeName(value: string | null | undefined) {
  return (value || '').trim();
}

export function isLegacyOrganizationPersonName(value: string | null | undefined) {
  const fullName = normalizeName(value);
  if (!fullName) return false;
  if (CURRENT_REAL_ORG_NAMES.has(fullName)) return false;
  return LEGACY_SIMULATION_NAMES.has(fullName);
}

export function isLegacyOrganizationEmployee(employee: OrganizationIdentity) {
  const fullName = normalizeName(employee.fullName);
  const email = (employee.email || '').trim().toLowerCase();
  const id = (employee.id || '').trim().toLowerCase();

  if (CURRENT_REAL_ORG_NAMES.has(fullName)) return false;
  if (isLegacyOrganizationPersonName(fullName)) return true;
  if (LEGACY_SIMULATION_IDS.has(id)) return true;
  if (LEGACY_SIMULATION_EMAILS.has(email)) return true;
  if (email.endsWith('@yiyu-system.com')) return true;
  return false;
}

export function isAssignableOrganizationEmployee(employee: EmployeeRecord) {
  if (isLegacyOrganizationEmployee(employee)) return false;
  if (employee.accountStatus === 'disabled') return false;
  return employee.accountStatus === 'approved' || employee.primaryRole === 'admin';
}
