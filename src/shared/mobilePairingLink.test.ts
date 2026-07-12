import assert from 'node:assert/strict';
import test from 'node:test';

import {
  TRUSTED_MOBILE_PAIRING_ORIGIN,
  buildMobilePairingLink,
  resolveCurrentMobilePairingQrDataUrl,
  normalizeMobilePairingEndpoint,
  resolveVerifiedMobilePairingInput,
} from './mobilePairingLink.js';

const READY_PAIRING_CONTEXT = {
  activeSandboxId: 'sandbox-star',
  runtimeStatus: 'ready',
  authenticated: true,
  sessionMode: 'cloud',
  user: {
    email: 'teammate@example.com',
    organizationId: 'org_star',
  },
  workspace: {
    id: 'sandbox-star',
    kind: 'organization',
    status: 'active',
    name: '星丛组织',
    cloudApiUrl: TRUSTED_MOBILE_PAIRING_ORIGIN,
    cloudConnected: true,
    cloudConnectionStatus: 'connected',
    cloudNeedsLogin: false,
    requiresLogin: false,
    cloudInstanceId: 'cli_star',
    identityState: 'verified',
    runtimeStatus: 'ready',
    cloudUserEmail: 'teammate@example.com',
    organizationId: 'org_star',
  },
} as const;

test('resolves only the verified current runtime on the exact trusted HTTPS origin', () => {
  assert.deepEqual(resolveVerifiedMobilePairingInput(READY_PAIRING_CONTEXT), {
    endpoint: TRUSTED_MOBILE_PAIRING_ORIGIN,
    email: 'teammate@example.com',
    workspace: '星丛组织',
    cloudInstanceId: 'cli_star',
    organizationId: 'org_star',
  });
  assert.equal(normalizeMobilePairingEndpoint(`${TRUSTED_MOBILE_PAIRING_ORIGIN}/`), TRUSTED_MOBILE_PAIRING_ORIGIN);
});

test('fails closed during switches, stale identity windows, and any non-exact endpoint', () => {
  const rejected = [
    { runtimeStatus: 'switching' },
    { activeSandboxId: 'sandbox-other' },
    { workspace: { ...READY_PAIRING_CONTEXT.workspace, runtimeStatus: 'switching' } },
    { workspace: { ...READY_PAIRING_CONTEXT.workspace, cloudConnected: false } },
    { workspace: { ...READY_PAIRING_CONTEXT.workspace, cloudConnectionStatus: 'needs_login' } },
    { workspace: { ...READY_PAIRING_CONTEXT.workspace, identityState: 'mismatch' } },
    { workspace: { ...READY_PAIRING_CONTEXT.workspace, cloudInstanceId: '' } },
    { workspace: { ...READY_PAIRING_CONTEXT.workspace, cloudApiUrl: 'http://118.145.244.188' } },
    { workspace: { ...READY_PAIRING_CONTEXT.workspace, cloudApiUrl: 'https://118.145.244.188:443' } },
    { workspace: { ...READY_PAIRING_CONTEXT.workspace, cloudApiUrl: 'https://118.145.244.188/api' } },
    { workspace: { ...READY_PAIRING_CONTEXT.workspace, cloudApiUrl: 'https://other.example.com' } },
    { user: { ...READY_PAIRING_CONTEXT.user, organizationId: 'org_old' } },
    { user: { ...READY_PAIRING_CONTEXT.user, email: 'old@example.com' } },
  ];

  for (const override of rejected) {
    assert.equal(resolveVerifiedMobilePairingInput({ ...READY_PAIRING_CONTEXT, ...override }), null);
  }
});

test('builds the exact v2 trusted HTTPS login QR without endpoint query', () => {
  const link = buildMobilePairingLink({
    endpoint: TRUSTED_MOBILE_PAIRING_ORIGIN,
    email: ' teammate@example.com ',
    workspace: ' 星丛组织 ',
    cloudInstanceId: 'cli_star',
    organizationId: 'org_star',
  });

  assert.equal(
    link,
    `${TRUSTED_MOBILE_PAIRING_ORIGIN}/login?v=2&email=teammate%40example.com&workspace=%E6%98%9F%E4%B8%9B%E7%BB%84%E7%BB%87&cloudInstanceId=cli_star&organizationId=org_star`,
  );
});

test('returns null when metadata is missing or endpoint is not exact', () => {
  const valid = {
    endpoint: TRUSTED_MOBILE_PAIRING_ORIGIN,
    email: 'a@example.com',
    workspace: '星丛',
    cloudInstanceId: 'cli_star',
    organizationId: 'org_star',
  };
  for (const override of [
    { endpoint: '' },
    { endpoint: 'http://118.145.244.188' },
    { endpoint: 'https://other.example.com' },
    { email: '' },
    { workspace: '' },
    { cloudInstanceId: '' },
    { organizationId: '' },
    { workspace: '星丛\n组织' },
    { email: `${'a'.repeat(243)}@example.com` },
    { workspace: '工'.repeat(121) },
  ]) {
    assert.equal(buildMobilePairingLink({ ...valid, ...override }), null);
  }
});

test('emits only the required non-secret allowlist', () => {
  const link = buildMobilePairingLink({
    endpoint: TRUSTED_MOBILE_PAIRING_ORIGIN,
    email: 'member+tag@example.com&token=not-a-real-secret',
    workspace: '星丛&password=not-a-real-secret',
    cloudInstanceId: 'cli_star',
    organizationId: 'org_star',
  });
  const parsed = new URL(link || '');

  assert.deepEqual([...parsed.searchParams.keys()], ['v', 'email', 'workspace', 'cloudInstanceId', 'organizationId']);
  for (const secretKey of ['endpoint', 'token', 'password', 'apiKey', 'invite']) {
    assert.equal(parsed.searchParams.has(secretKey), false);
  }
});

test('never exposes a QR generated for a previous pairing link', () => {
  const previousLink = `${TRUSTED_MOBILE_PAIRING_ORIGIN}/login?v=2&email=old%40example.com`;
  const currentLink = `${TRUSTED_MOBILE_PAIRING_ORIGIN}/login?v=2&email=current%40example.com`;
  const previousQr = {
    sourceLink: previousLink,
    status: 'ready' as const,
    dataUrl: 'data:image/png;base64,previous-account',
  };

  assert.equal(resolveCurrentMobilePairingQrDataUrl(previousQr, previousLink), previousQr.dataUrl);
  assert.equal(resolveCurrentMobilePairingQrDataUrl(previousQr, currentLink), null);
  assert.equal(resolveCurrentMobilePairingQrDataUrl(previousQr, null), null);
});
