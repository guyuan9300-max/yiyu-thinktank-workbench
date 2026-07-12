export const TRUSTED_MOBILE_PAIRING_ORIGIN = 'https://118.145.244.188';

export type MobilePairingLinkInput = {
  endpoint: string | null | undefined;
  email: string | null | undefined;
  workspace: string | null | undefined;
  cloudInstanceId: string | null | undefined;
  organizationId: string | null | undefined;
};

export type MobilePairingRuntimeContext = {
  activeSandboxId: string | null | undefined;
  runtimeStatus: string | null | undefined;
  authenticated: boolean;
  sessionMode: string | null | undefined;
  user: {
    email?: string | null;
    organizationId?: string | null;
  } | null | undefined;
  workspace: {
    id?: string | null;
    kind?: string | null;
    status?: string | null;
    name?: string | null;
    cloudApiUrl?: string | null;
    cloudConnected?: boolean;
    cloudConnectionStatus?: string | null;
    cloudNeedsLogin?: boolean;
    requiresLogin?: boolean;
    cloudInstanceId?: string | null;
    identityState?: string | null;
    runtimeStatus?: string | null;
    cloudUserEmail?: string | null;
    organizationId?: string | null;
  } | null | undefined;
};

export type MobilePairingQrResult =
  | { sourceLink: string; status: 'ready'; dataUrl: string }
  | { sourceLink: string; status: 'error' };

const CONTROL_CHARACTER_PATTERN = /[\u0000-\u001f\u007f]/;
const NON_SECRET_IDENTIFIER_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]*$/;

function normalizedField(value: string | null | undefined, maxLength: number) {
  const normalized = String(value || '').trim();
  if (!normalized || normalized.length > maxLength || CONTROL_CHARACTER_PATTERN.test(normalized)) return null;
  return normalized;
}

function normalizedIdentifier(value: string | null | undefined) {
  const normalized = normalizedField(value, 200);
  return normalized && NON_SECRET_IDENTIFIER_PATTERN.test(normalized) ? normalized : null;
}

/** Only the exact trusted HTTPS origin can produce a phone setup QR. */
export function normalizeMobilePairingEndpoint(rawEndpoint: string | null | undefined) {
  const endpoint = normalizedField(rawEndpoint, 2048);
  if (!endpoint) return null;
  if (endpoint !== TRUSTED_MOBILE_PAIRING_ORIGIN && endpoint !== `${TRUSTED_MOBILE_PAIRING_ORIGIN}/`) {
    return null;
  }

  try {
    const parsed = new URL(endpoint);
    if (
      parsed.origin !== TRUSTED_MOBILE_PAIRING_ORIGIN
      || parsed.protocol !== 'https:'
      || parsed.hostname !== '118.145.244.188'
      || parsed.port
      || parsed.username
      || parsed.password
      || (parsed.pathname !== '/' && parsed.pathname !== '')
      || parsed.search
      || parsed.hash
    ) {
      return null;
    }
    return TRUSTED_MOBILE_PAIRING_ORIGIN;
  } catch {
    return null;
  }
}

/** Resolve metadata only from one fully verified active Starcluster runtime. */
export function resolveVerifiedMobilePairingInput(
  context: MobilePairingRuntimeContext,
): MobilePairingLinkInput | null {
  const workspace = context.workspace;
  const user = context.user;
  if (
    !workspace
    || !user
    || !context.authenticated
    || context.sessionMode !== 'cloud'
    || context.runtimeStatus !== 'ready'
    || workspace.runtimeStatus !== 'ready'
    || workspace.id !== context.activeSandboxId
    || workspace.kind !== 'organization'
    || workspace.status !== 'active'
    || workspace.cloudConnected !== true
    || workspace.cloudConnectionStatus !== 'connected'
    || workspace.cloudNeedsLogin === true
    || workspace.requiresLogin === true
    || workspace.identityState !== 'verified'
  ) {
    return null;
  }

  const endpoint = normalizeMobilePairingEndpoint(workspace.cloudApiUrl);
  const email = normalizedField(user.email, 254);
  const workspaceEmail = normalizedField(workspace.cloudUserEmail, 254);
  const workspaceName = normalizedField(workspace.name, 120);
  const cloudInstanceId = normalizedIdentifier(workspace.cloudInstanceId);
  const userOrganizationId = normalizedIdentifier(user.organizationId);
  const workspaceOrganizationId = normalizedIdentifier(workspace.organizationId);
  if (
    !endpoint
    || !email
    || !workspaceEmail
    || !workspaceName
    || !cloudInstanceId
    || !userOrganizationId
    || !workspaceOrganizationId
    || email.toLocaleLowerCase('en-US') !== workspaceEmail.toLocaleLowerCase('en-US')
    || userOrganizationId !== workspaceOrganizationId
  ) {
    return null;
  }

  return {
    endpoint,
    email,
    workspace: workspaceName,
    cloudInstanceId,
    organizationId: userOrganizationId,
  };
}

/** Build the non-authenticating v2 QR payload; endpoint is derived from its URL origin. */
export function buildMobilePairingLink(input: MobilePairingLinkInput) {
  const endpoint = normalizeMobilePairingEndpoint(input.endpoint);
  const email = normalizedField(input.email, 254);
  const workspace = normalizedField(input.workspace, 120);
  const cloudInstanceId = normalizedIdentifier(input.cloudInstanceId);
  const organizationId = normalizedIdentifier(input.organizationId);
  if (!endpoint || !email || !workspace || !cloudInstanceId || !organizationId) return null;

  const link = new URL('/login', TRUSTED_MOBILE_PAIRING_ORIGIN);
  link.searchParams.set('v', '2');
  link.searchParams.set('email', email);
  link.searchParams.set('workspace', workspace);
  link.searchParams.set('cloudInstanceId', cloudInstanceId);
  link.searchParams.set('organizationId', organizationId);
  return link.toString();
}

/**
 * Never render an asynchronously generated QR unless it belongs to the exact
 * pairing link in the current render. React effects run after paint, so merely
 * clearing state in an effect can otherwise expose the previous account's QR
 * for one frame while the visible account/workspace labels have already moved.
 */
export function resolveCurrentMobilePairingQrDataUrl(
  result: MobilePairingQrResult | null,
  currentLink: string | null,
) {
  return result?.status === 'ready' && result.sourceLink === currentLink
    ? result.dataUrl
    : null;
}

export function hasCurrentMobilePairingQrError(
  result: MobilePairingQrResult | null,
  currentLink: string | null,
) {
  return result?.status === 'error' && result.sourceLink === currentLink;
}
