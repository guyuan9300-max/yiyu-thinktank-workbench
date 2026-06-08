import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';

import type { DesktopAppInfo } from '../shared/types.js';
import {
  evaluateDesktopStartupGate,
  type BackendFeatureStatus,
  type BackendManifestStatus,
  type BackendRuntimeModeStatus,
  type BackendSchemaStatus,
  type InstallReceiptStatus,
  type InstallSmokeStatus,
  type ManifestStatus,
} from '../shared/desktopRuntimeGuard.js';
import { computeBundleManifestId, type BundleVersionManifest } from '../shared/versionManifest.js';

export const DEFAULT_RUNTIME_EVIDENCE_DIR = path.join(
  os.homedir(),
  'Library',
  'Application Support',
  'YiyuThinkTankWorkbench2',
  'runtime',
  'main-chain-rc',
  'v0.3.4',
);
export const DEFAULT_INSTALL_RECEIPT_PATH = path.join(DEFAULT_RUNTIME_EVIDENCE_DIR, 'install-receipt.json');
export const DEFAULT_INSTALL_SMOKE_PATH = path.join(DEFAULT_RUNTIME_EVIDENCE_DIR, 'install-smoke.json');
export const DEFAULT_WORKSPACE_CHAT_SMOKE_PATH = path.join(DEFAULT_RUNTIME_EVIDENCE_DIR, 'workspace-chat-smoke.json');

export type BackendHealthPayload = {
  featureFlags?: string[];
  backendBuildHash?: string;
  backendSourceHash?: string;
  backendSchemaVersion?: number;
  bundleManifestId?: string | null;
  frontendRendererEntry?: string | null;
  frontendRendererHash?: string | null;
  installPathStatus?: string | null;
  runtimeMode?: 'packaged' | 'dev';
};

export type AppManifestInspection = {
  exists: boolean;
  manifestStatus: ManifestStatus;
  manifest: BundleVersionManifest | null;
  bundleManifestId: string | null;
  currentRendererEntry: string | null;
  currentRendererHash: string | null;
};

function readJsonFile(targetPath: string): Record<string, unknown> | null {
  if (!fs.existsSync(targetPath)) {
    return null;
  }
  try {
    const payload = JSON.parse(fs.readFileSync(targetPath, 'utf8')) as Record<string, unknown>;
    return payload && typeof payload === 'object' ? payload : null;
  } catch {
    return null;
  }
}

function sha256File(targetPath: string): string | null {
  if (!fs.existsSync(targetPath)) {
    return null;
  }
  return createHash('sha256').update(fs.readFileSync(targetPath)).digest('hex');
}

function resolveAppManifestPath(appBundlePath: string) {
  return path.join(appBundlePath, 'Contents', 'Resources', 'app', 'dist', 'version-manifest.json');
}

export function pickRendererEntry(assetDir: string): string | null {
  if (!fs.existsSync(assetDir)) {
    return null;
  }
  const files = fs.readdirSync(assetDir)
    .filter((name) => /^(main|index)-.*\.js$/.test(name))
    .sort();
  return files.find((name) => name.startsWith('main-')) || files[0] || null;
}

export function inspectAppManifest(appBundlePath: string): AppManifestInspection {
  const resolvedAppPath = path.resolve(appBundlePath);
  if (!fs.existsSync(resolvedAppPath)) {
    return {
      exists: false,
      manifestStatus: 'missing',
      manifest: null,
      bundleManifestId: null,
      currentRendererEntry: null,
      currentRendererHash: null,
    };
  }

  const manifestPath = resolveAppManifestPath(resolvedAppPath);
  if (!fs.existsSync(manifestPath)) {
    return {
      exists: true,
      manifestStatus: 'missing',
      manifest: null,
      bundleManifestId: null,
      currentRendererEntry: null,
      currentRendererHash: null,
    };
  }

  const manifest = readJsonFile(manifestPath) as BundleVersionManifest | null;
  if (!manifest || typeof manifest.rendererEntry !== 'string' || typeof manifest.rendererHash !== 'string') {
    return {
      exists: true,
      manifestStatus: 'invalid',
      manifest: null,
      bundleManifestId: null,
      currentRendererEntry: null,
      currentRendererHash: null,
    };
  }

  const rendererPath = path.join(
    resolvedAppPath,
    'Contents',
    'Resources',
    'app',
    'dist',
    'renderer',
    'assets',
    manifest.rendererEntry,
  );
  const currentRendererHash = sha256File(rendererPath);
  if (!currentRendererHash || currentRendererHash !== manifest.rendererHash) {
    return {
      exists: true,
      manifestStatus: 'invalid',
      manifest,
      bundleManifestId: computeBundleManifestId(manifest),
      currentRendererEntry: manifest.rendererEntry,
      currentRendererHash,
    };
  }
  return {
    exists: true,
    manifestStatus: 'ok',
    manifest,
    bundleManifestId: computeBundleManifestId(manifest),
    currentRendererEntry: manifest.rendererEntry,
    currentRendererHash,
  };
}

function evaluateInstallReceiptStatus(receiptPath: string, currentBundleManifestId: string | null): InstallReceiptStatus {
  const payload = readJsonFile(receiptPath);
  if (!payload) {
    return 'missing';
  }
  const targetBundleManifestId = typeof payload.targetBundleManifestId === 'string' ? payload.targetBundleManifestId : null;
  const sourceBundleManifestId = typeof payload.sourceBundleManifestId === 'string' ? payload.sourceBundleManifestId : null;
  const bundleManifestMatch = payload.bundleManifestMatch;
  if (
    currentBundleManifestId
    && targetBundleManifestId === currentBundleManifestId
    && sourceBundleManifestId === currentBundleManifestId
    && bundleManifestMatch === true
  ) {
    return 'ok';
  }
  return 'mismatch';
}

function evaluateInstallSmokeStatus(smokePath: string, currentBundleManifestId: string | null): InstallSmokeStatus {
  const payload = readJsonFile(smokePath);
  if (!payload) {
    return 'missing';
  }
  const readyToOpenWorkbench = payload.readyToOpenWorkbench === true || payload.readyToResumeA0 === true;
  const targetBundleManifestId = typeof payload.targetBundleManifestId === 'string' ? payload.targetBundleManifestId : null;
  const sourceBundleManifestId = typeof payload.sourceBundleManifestId === 'string' ? payload.sourceBundleManifestId : null;
  const bundleManifestMatch = payload.bundleManifestMatch !== false;
  if (
    readyToOpenWorkbench
    && bundleManifestMatch
    && currentBundleManifestId
    && targetBundleManifestId === currentBundleManifestId
    && sourceBundleManifestId === currentBundleManifestId
  ) {
    return 'ok';
  }
  return 'failed';
}

function evaluateBackendManifestStatus(
  health: BackendHealthPayload | null,
  manifest: BundleVersionManifest | null,
  currentBundleManifestId: string | null,
): BackendManifestStatus {
  if (!health || !manifest || !currentBundleManifestId) {
    return 'missing';
  }
  if (!health.bundleManifestId || !health.frontendRendererEntry || !health.frontendRendererHash || !health.backendSourceHash) {
    return 'missing';
  }
  if (
    health.bundleManifestId === currentBundleManifestId
    && health.frontendRendererEntry === manifest.rendererEntry
    && health.frontendRendererHash === manifest.rendererHash
    && health.backendSourceHash === manifest.backendSourceHash
  ) {
    return 'ok';
  }
  return 'mismatch';
}

export function buildDesktopAppInfo(input: {
  appVersion: string;
  frontendBuildVersion?: string | null;
  frontendGitCommit?: string | null;
  runtimeMode?: 'packaged' | 'dev';
  collabPreviewMode?: boolean;
  isPackaged: boolean;
  platform: string;
  arch: string;
  appBundlePath: string;
  executablePath: string;
  releasePlanPath: string;
  releaseArtifactsPath: string;
  cloudBackendUrl?: string | null;
  updateChannel: 'stable' | 'beta';
  updaterPhase: 'planning' | 'preparing_release' | 'ready_for_feed' | 'ready_for_in_app_update';
  recommendedInstallPath: string;
  detectedAppPaths: string[];
  legacyAppPaths: string[];
  health?: BackendHealthPayload | null;
  requiredFeatures: string[];
  requiredSchemaVersion: number;
  installReceiptPath?: string;
  installSmokePath?: string;
}): DesktopAppInfo {
  const manifestInspection = inspectAppManifest(input.appBundlePath);
  const installReceiptStatus = evaluateInstallReceiptStatus(
    input.installReceiptPath || DEFAULT_INSTALL_RECEIPT_PATH,
    manifestInspection.bundleManifestId,
  );
  const installSmokeStatus = evaluateInstallSmokeStatus(
    input.installSmokePath || DEFAULT_INSTALL_SMOKE_PATH,
    manifestInspection.bundleManifestId,
  );
  const health = input.health || null;
  const featureFlags = Array.isArray(health?.featureFlags) ? health?.featureFlags : [];
  const backendFeatureStatus: BackendFeatureStatus = input.requiredFeatures.every((item) => featureFlags.includes(item))
    ? 'ok'
    : 'missing';
  const backendSchemaStatus: BackendSchemaStatus = Number(health?.backendSchemaVersion || 0) >= input.requiredSchemaVersion
    ? 'ok'
    : 'stale';
  const backendRuntimeModeStatus: BackendRuntimeModeStatus = (
    !input.isPackaged || health?.runtimeMode === 'packaged'
  )
    ? 'ok'
    : 'mismatch';
  const backendManifestStatus = evaluateBackendManifestStatus(
    health,
    manifestInspection.manifest,
    manifestInspection.bundleManifestId,
  );
  const gate = evaluateDesktopStartupGate({
    isPackaged: input.isPackaged,
    installPathStatus: input.appBundlePath === input.recommendedInstallPath ? 'recommended' : 'unexpected',
    manifestStatus: manifestInspection.manifestStatus,
    installReceiptStatus,
    installSmokeStatus,
    backendManifestStatus,
    backendFeatureStatus,
    backendSchemaStatus,
    backendRuntimeModeStatus,
    legacyAppCount: input.legacyAppPaths.length,
    duplicateAppCount: Math.max(0, input.detectedAppPaths.length - input.legacyAppPaths.length - 1),
  });

  return {
    appVersion: input.appVersion,
    frontendBuildVersion: input.frontendBuildVersion ?? manifestInspection.manifest?.buildVersion ?? null,
    frontendGitCommit: input.frontendGitCommit ?? manifestInspection.manifest?.gitCommit ?? null,
    bundleManifestId: manifestInspection.bundleManifestId,
    runtimeMode: input.runtimeMode,
    collabPreviewMode: Boolean(input.collabPreviewMode),
    isPackaged: input.isPackaged,
    platform: input.platform,
    arch: input.arch,
    appBundlePath: input.appBundlePath,
    executablePath: input.executablePath,
    releasePlanPath: input.releasePlanPath,
    releaseArtifactsPath: input.releaseArtifactsPath,
    cloudBackendUrl: input.cloudBackendUrl || null,
    updateChannel: input.updateChannel,
    updaterPhase: input.updaterPhase,
    recommendedInstallPath: input.recommendedInstallPath,
    installStatus: gate.installStatus,
    installWarning: gate.installWarning,
    currentRendererEntry: manifestInspection.currentRendererEntry,
    currentRendererHash: manifestInspection.currentRendererHash,
    backendSourceHash: health?.backendSourceHash || health?.backendBuildHash || manifestInspection.manifest?.backendSourceHash || null,
    startupGateStatus: gate.status,
    startupGateReason: gate.reason,
    installReceiptStatus,
    installSmokeStatus,
    detectedAppPaths: input.detectedAppPaths,
    legacyAppPaths: input.legacyAppPaths,
  };
}
