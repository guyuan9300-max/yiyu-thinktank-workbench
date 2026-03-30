import type { DemoDataReport, LegacyScanReport } from '../../../src/shared/types';

const baseUrl = window.yiyuWorkbench.backendBaseUrl;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || '请求失败');
  }
  return response.json() as Promise<T>;
}

export async function scanLegacy(path: string) {
  return request<LegacyScanReport>('/api/v1/settings/legacy-scan', {
    method: 'POST',
    body: JSON.stringify({ path }),
  });
}

export async function loadDemoData() {
  return request<DemoDataReport>('/api/v1/settings/demo-data/load', { method: 'POST' });
}

export async function clearDemoData() {
  return request<DemoDataReport>('/api/v1/settings/demo-data/clear', { method: 'POST' });
}
