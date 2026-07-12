export const CLOUD_API_URL_PREFIX = 'https://';

export function cloudApiHostValue(rawUrl?: string | null) {
  return String(rawUrl || '')
    .trim()
    .replace(/^https?:\/\//i, '')
    .replace(/\/.*$/, '');
}

function isLocalDevelopmentHost(rawHost: string) {
  const host = rawHost.replace(/^\[|\]$/g, '').toLowerCase();
  return host === 'localhost' || host === '::1' || host.startsWith('127.');
}

export function cloudApiUrlFromHost(rawHost?: string | null) {
  const rawValue = String(rawHost || '').trim();
  if (/^https?:\/\//i.test(rawValue)) {
    try {
      const parsed = new URL(rawValue);
      if (parsed.username || parsed.password) return '';
      if (parsed.protocol === 'http:' && !isLocalDevelopmentHost(parsed.hostname)) {
        parsed.protocol = 'https:';
      }
      return parsed.origin;
    } catch {
      return '';
    }
  }
  const host = cloudApiHostValue(rawHost);
  if (!host) return '';
  const parsedHost = host.startsWith('[')
    ? host.replace(/^\[([^\]]+)\].*$/, '$1').toLowerCase()
    : host.split(':')[0].toLowerCase();
  const scheme = isLocalDevelopmentHost(parsedHost)
    ? 'http://'
    : CLOUD_API_URL_PREFIX;
  return `${scheme}${host}`;
}
