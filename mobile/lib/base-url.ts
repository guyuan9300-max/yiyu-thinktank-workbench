export interface ResolvedBaseUrl {
  baseUrl: string;
  shouldDeleteSaved: boolean;
  source: "saved" | "default" | "invalid_saved";
}

export function isPrivateOrLocalHostname(hostname: string): boolean {
  const value = hostname.trim().toLowerCase();
  if (!value) return true;
  if (value === "localhost" || value.endsWith(".local")) return true;

  if (!/^\d{1,3}(?:\.\d{1,3}){3}$/.test(value)) {
    return false;
  }

  const [a, b] = value.split(".").map((part) => Number(part));
  if (Number.isNaN(a) || Number.isNaN(b)) {
    return false;
  }

  return (
    a === 10 ||
    a === 127 ||
    (a === 169 && b === 254) ||
    (a === 172 && b >= 16 && b <= 31) ||
    (a === 192 && b === 168)
  );
}

export function normalizeBaseUrl(url: string): string {
  const trimmed = url.trim();
  if (!trimmed) {
    throw new Error("empty-base-url");
  }
  const withProtocol = /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`;
  const parsed = new URL(withProtocol);
  return parsed.toString().replace(/\/+$/, "");
}

export function resolveStoredBaseUrl(
  savedUrl: string | null | undefined,
  fallbackUrl: string,
): ResolvedBaseUrl {
  if (!savedUrl?.trim()) {
    return {
      baseUrl: fallbackUrl.trim() ? normalizeBaseUrl(fallbackUrl) : "",
      shouldDeleteSaved: false,
      source: "default",
    };
  }

  try {
    return {
      baseUrl: normalizeBaseUrl(savedUrl),
      shouldDeleteSaved: false,
      source: "saved",
    };
  } catch {
    return {
      baseUrl: fallbackUrl.trim() ? normalizeBaseUrl(fallbackUrl) : "",
      shouldDeleteSaved: true,
      source: "invalid_saved",
    };
  }
}

export function isValidBaseUrl(value: string): boolean {
  try {
    normalizeBaseUrl(value);
    return true;
  } catch {
    return false;
  }
}
