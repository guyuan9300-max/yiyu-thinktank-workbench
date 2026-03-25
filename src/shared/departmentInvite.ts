function toInviteSeed(value: string) {
  let hash = 0;
  for (const char of value) {
    hash = (hash * 131 + char.charCodeAt(0)) % 1_000_000;
  }
  return String(hash).padStart(6, '0');
}

export function buildDepartmentInviteCode(departmentId: string) {
  return toInviteSeed(departmentId);
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

  const inviteCodeMatch = value.match(/\b(\d{6})\b/);
  if (inviteCodeMatch) {
    return inviteCodeMatch[1];
  }

  return value;
}
