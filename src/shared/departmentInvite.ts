const ORGANIZATION_ALIAS_MAP: Record<string, string> = {
  '益语智库': 'YIYU',
  '益语': 'YIYU',
};

const DEPARTMENT_ALIAS_MAP: Record<string, string> = {
  '咨询部': 'ZX',
  '咨询策略部': 'ZX',
  '运营部': 'YY',
  '客户服务部': 'KF',
  '科技发展部': 'KJ',
  '信息数据部': 'SJ',
};

function toInviteSeed(value: string) {
  let hash = 0;
  for (const char of value) {
    hash = (hash * 131 + char.charCodeAt(0)) % 1_000_000;
  }
  return String(hash).padStart(6, '0');
}

function toBase36Seed(value: string, modulo = 36 ** 4) {
  let hash = 0;
  for (const char of value) {
    hash = (hash * 131 + char.charCodeAt(0)) % modulo;
  }
  return hash.toString(36).toUpperCase();
}

function normalizeInviteSegment(
  rawValue: string | null | undefined,
  limit: number,
  aliasMap?: Record<string, string>,
) {
  const value = rawValue?.trim();
  if (!value) return '';
  if (aliasMap && aliasMap[value]) {
    return aliasMap[value].slice(0, limit).toUpperCase();
  }
  const asciiOnly = value.replace(/[^A-Za-z0-9]+/g, '').toUpperCase();
  if (asciiOnly) {
    return asciiOnly.slice(0, limit);
  }
  return toBase36Seed(value, 36 ** limit).padStart(limit, '0').slice(0, limit);
}

export type DepartmentInviteCodeOptions = {
  organizationName?: string | null;
  departmentName?: string | null;
  order?: number | null;
};

export function buildDepartmentInviteCode(
  departmentId: string,
  options: DepartmentInviteCodeOptions = {},
) {
  const { organizationName, departmentName, order } = options;
  if (!organizationName && !departmentName && typeof order !== 'number') {
    return toInviteSeed(departmentId);
  }

  const orgPrefix = normalizeInviteSegment(organizationName, 4, ORGANIZATION_ALIAS_MAP) || 'ORGX';
  const deptPrefix = normalizeInviteSegment(departmentName, 2, DEPARTMENT_ALIAS_MAP) || 'BM';
  const orderValue = typeof order === 'number' && Number.isFinite(order)
    ? Math.max(1, order + 1)
    : (parseInt(toInviteSeed(departmentId).slice(-2), 10) % 99) + 1;
  const orderSegment = String(orderValue).padStart(2, '0');
  return `${orgPrefix}-${deptPrefix}${orderSegment}`;
}

export function buildDepartmentInviteShareText(departmentName: string, inviteCode: string) {
  return `${departmentName} 邀请码 ${inviteCode}`;
}

export function parseDepartmentInviteCode(rawValue: string) {
  const value = rawValue.trim();
  if (!value) return '';

  try {
    const directUrl = new URL(value);
    const invite = directUrl.searchParams.get('invite');
    if (invite) return parseDepartmentInviteCode(decodeURIComponent(invite));
    const departmentId = directUrl.searchParams.get('departmentId');
    if (departmentId) return departmentId.trim();
  } catch {}

  const inviteMatch = value.match(/invite=([^&]+)/i);
  if (inviteMatch) {
    try {
      return parseDepartmentInviteCode(decodeURIComponent(inviteMatch[1]));
    } catch {
      return parseDepartmentInviteCode(inviteMatch[1]);
    }
  }

  const departmentMatch = value.match(/departmentId=([^&]+)/i);
  if (departmentMatch) {
    return decodeURIComponent(departmentMatch[1]).trim();
  }

  if (value.startsWith('dept:')) {
    return value.slice(5).trim();
  }

  const formattedInviteCodeMatch = value.match(/\b([A-Z0-9]{2,8}-[A-Z0-9]{2,8})\b/i);
  if (formattedInviteCodeMatch) {
    return formattedInviteCodeMatch[1].toUpperCase();
  }

  const inviteCodeMatch = value.match(/\b(\d{6})\b/);
  if (inviteCodeMatch) {
    return inviteCodeMatch[1];
  }

  return value;
}
