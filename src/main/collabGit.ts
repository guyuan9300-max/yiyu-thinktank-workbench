import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import type {
  CollabActionResult,
  CollabChangeGroup,
  CollabChangeGroupKey,
  CollabConflictRisk,
  CollabEffectExplanationRequest,
  CollabEffectPreview,
  CollabFileChange,
  CollabFileChangeType,
  CollabPreviewSession,
  CollabRemoteBranch,
  CollabRemoteCommit,
  CollabRepoStatus,
  FastForwardMainPayload,
  PullPreview,
  PublishCollabBranchPayload,
  PushMainPayload,
  PushPreview,
  StartCollabPreviewPayload,
  StopCollabPreviewPayload,
} from '../shared/types.js';

type RunCommandOptions = {
  cwd?: string;
  allowNonZero?: boolean;
  input?: string;
};

type RunCommandResult = {
  stdout: string;
  stderr: string;
  exitCode: number;
};

type ParsedStatusEntry = {
  path: string;
  previousPath?: string | null;
  type: CollabFileChangeType;
  x: string;
  y: string;
  isUnmerged: boolean;
};

type ParsedDiffEntry = {
  path: string;
  previousPath?: string | null;
  type: Exclude<CollabFileChangeType, 'untracked'>;
};

type RepoSnapshot = {
  repoPath: string | null;
  repoName: string | null;
  suggestedRepoPath: string | null;
  gitRepoPath: string | null;
  scopeRelativePath: string | null;
  isConfigured: boolean;
  isValid: boolean;
  branch: string | null;
  isMainBranch: boolean;
  aheadCount: number;
  behindCount: number;
  hasUnmergedPaths: boolean;
  localEntries: ParsedStatusEntry[];
  remoteEntries: ParsedDiffEntry[];
  localBranchEntries: ParsedDiffEntry[];
  localChangeCount: number;
  remoteChangeCount: number;
  remoteTargetRevision: string;
  statusText: string;
  // P1-1: fetch origin 是否失败 (网络/认证). true 时 push 必须阻断,
  // 否则可能用过期 origin/main 算出 behindCount=0 跳过 merge 强推覆盖远端.
  fetchFailed: boolean;
  fetchErrorMessage: string;
};

type RepoOptions = {
  repoPath?: string | null;
  suggestedCandidates: string[];
  fetchRemote?: boolean;
  appDbPath?: string | null;
  targetCommit?: string | null;
  effectExplainer?: CollabEffectExplainer | null;
};

type CollabEffectExplainer = (request: CollabEffectExplanationRequest) => Promise<CollabEffectPreview[] | null | undefined>;

type RepoWorkContext = {
  repoPath: string;
  gitRepoPath: string;
  scopeRelativePath: string | null;
};

type SharedSettingsTarget = {
  settingKey: 'settings.system_admin';
  repoRelativePath: '.yiyu-sync/settings.system_admin.json';
  groupKey: CollabChangeGroupKey;
  defaultValue: () => Record<string, unknown>;
};

type SharedSettingsRecord = Record<string, unknown>;

type EffectDraft = {
  id: string;
  title: string;
  summary: string;
  visibility: CollabEffectPreview['visibility'];
  scopeLabel: string;
  details: string[];
  relatedPaths: Set<string>;
  beforeLabel?: string | null;
  afterLabel?: string | null;
};

const COLLAB_AI_EXPLANATION_UNAVAILABLE_REASON = 'AI 功能说明尚未生成；下面只是按路径和提交信息推断的规则兜底，不能当作完整功能评审。';
const MAX_EFFECT_DIFF_PREVIEW_CHARS = 8000;

const GROUP_LABELS: Record<CollabChangeGroupKey, string> = {
  shared_settings: '共享设置',
  renderer: '界面',
  desktop_shell: '桌面壳',
  local_backend: '本地 backend',
  cloud_backend: '共享 backend',
  scripts_docs: '脚本/文档/配置',
  other: '其他',
};

const GROUP_ORDER: CollabChangeGroupKey[] = [
  'shared_settings',
  'renderer',
  'desktop_shell',
  'local_backend',
  'cloud_backend',
  'scripts_docs',
  'other',
];

const SHARED_SETTINGS_TARGETS: SharedSettingsTarget[] = [
  {
    settingKey: 'settings.system_admin',
    repoRelativePath: '.yiyu-sync/settings.system_admin.json',
    groupKey: 'shared_settings',
    defaultValue: () => ({
      allowBusinessSettingsForEmployees: true,
      allowOrgDnaForEmployees: true,
      protectEmployeeAdmin: true,
      protectAiAndCloud: true,
      protectCloudSecurity: true,
      updatedAt: new Date().toISOString(),
    }),
  },
];

const SHARED_SETTING_LABELS: Record<string, string> = {
  allowBusinessSettingsForEmployees: '员工业务设置权限',
  allowOrgDnaForEmployees: '员工组织 DNA 权限',
  protectEmployeeAdmin: '员工管理保护',
  protectAiAndCloud: 'AI 与云端保护',
  protectCloudSecurity: '云端安全保护',
  updatedAt: '更新时间',
};

const BINARY_EXTENSIONS = new Set([
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.webp',
  '.ico',
  '.icns',
  '.pdf',
  '.zip',
  '.gz',
  '.mp4',
  '.mov',
  '.mp3',
  '.wav',
  '.ttf',
  '.otf',
  '.woff',
  '.woff2',
  '.dmg',
]);

const IGNORABLE_LOCAL_STATUS_PATHS = new Set([
  '.yiyu-sync/settings.system_admin.json',
]);

const IGNORABLE_LOCAL_STATUS_PREFIXES = [
  'mobile/',
  '.playwright-cli/',
  'dist/',
  'build/',
  'coverage/',
  'test-results/',
  'temp-renderer/',
  'tmp/',
];

const GENERATED_LOCAL_STATUS_SEGMENTS = new Set([
  '__pycache__',
  '.pytest_cache',
]);

const GENERATED_LOCAL_STATUS_SUFFIXES = [
  '.pyc',
  '.pyo',
  '.pyd',
  '.DS_Store',
  '.tsbuildinfo',
  '.db',
  '.db-shm',
  '.db-wal',
  '.sqlite',
  '.sqlite3',
  '.sqlite-shm',
  '.sqlite-wal',
];

const COLLAB_PRIMARY_REPO_NAME = 'yiyu-thinktank-workbench';
const COLLAB_LEGACY_REPO_NAME = 'yiyu-thinktank-workbench-main-sync';
const COLLAB_VISIBLE_WORKSPACE_SEGMENT = `${path.sep}openclaw${path.sep}workspace`;
const COLLAB_HIDDEN_WORKSPACE_SEGMENT = `${path.sep}.openclaw${path.sep}workspace`;

const activePreviewSessions = new Map<string, { pid: number; session: CollabPreviewSession }>();

function normalizeCollabRepoBindingPath(targetPath: string) {
  let normalized = path.resolve(targetPath).replace(/[\\/]+$/, '');
  try {
    normalized = fs.realpathSync.native(normalized).replace(/[\\/]+$/, '');
  } catch {
    // Keep the resolved path when the target does not exist yet.
  }
  if (normalized.includes(COLLAB_HIDDEN_WORKSPACE_SEGMENT)) {
    normalized = normalized.replace(COLLAB_HIDDEN_WORKSPACE_SEGMENT, COLLAB_VISIBLE_WORKSPACE_SEGMENT);
  }
  const legacySuffix = `${path.sep}${COLLAB_LEGACY_REPO_NAME}`;
  if (normalized.endsWith(legacySuffix)) {
    return normalized.slice(0, -COLLAB_LEGACY_REPO_NAME.length) + COLLAB_PRIMARY_REPO_NAME;
  }
  if (path.basename(normalized) === 'workspace') {
    return path.join(normalized, COLLAB_PRIMARY_REPO_NAME);
  }
  return normalized;
}

function formatSyncedJson(value: Record<string, unknown>) {
  return `${JSON.stringify(value, null, 2)}\n`;
}

function readSharedSettingRecord(appDbPath: string, settingKey: string, defaultValue: () => Record<string, unknown>) {
  const db = new DatabaseSync(appDbPath);
  try {
    const row = db.prepare('SELECT value FROM settings WHERE key = ?').get(settingKey) as { value?: string } | undefined;
    if (row?.value) {
      const parsed = JSON.parse(row.value);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>;
      }
    }
  } catch {
    // Fall back to a stable default snapshot when local settings are missing or malformed.
  } finally {
    db.close();
  }
  return defaultValue();
}

function writeSharedSettingRecord(appDbPath: string, settingKey: string, value: Record<string, unknown>) {
  const db = new DatabaseSync(appDbPath);
  try {
    db.prepare('INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)').run(settingKey, JSON.stringify(value));
  } finally {
    db.close();
  }
}

function stripUnsupportedSharedSettings(record: Record<string, unknown>) {
  const safeRecord = { ...record };
  delete safeRecord.brandLogoDataUrl;
  delete safeRecord.brandLogoDataUrlOmitted;
  return safeRecord;
}

async function exportSharedSettingsToRepo(repoPath: string, appDbPath?: string | null) {
  if (!appDbPath) return;
  const stat = await fs.promises.stat(appDbPath).catch(() => null);
  if (!stat?.isFile()) return;
  for (const target of SHARED_SETTINGS_TARGETS) {
    const nextRecord = stripUnsupportedSharedSettings(readSharedSettingRecord(appDbPath, target.settingKey, target.defaultValue));
    const targetPath = path.join(repoPath, target.repoRelativePath);
    const nextContent = formatSyncedJson(nextRecord);
    const currentContent = await fs.promises.readFile(targetPath, 'utf8').catch(() => null);
    if (currentContent === nextContent) continue;
    await fs.promises.mkdir(path.dirname(targetPath), { recursive: true });
    await fs.promises.writeFile(targetPath, nextContent, 'utf8');
  }
}

async function importSelectedSharedSettingsFromRepo(repoPath: string, appDbPath: string | null | undefined, selectedPaths: string[]) {
  if (!appDbPath) return;
  const stat = await fs.promises.stat(appDbPath).catch(() => null);
  if (!stat?.isFile()) return;
  const selectedSet = new Set(selectedPaths);
  for (const target of SHARED_SETTINGS_TARGETS) {
    if (!selectedSet.has(target.repoRelativePath)) continue;
    const targetPath = path.join(repoPath, target.repoRelativePath);
    const rawContent = await fs.promises.readFile(targetPath, 'utf8').catch(() => null);
    if (!rawContent) {
      writeSharedSettingRecord(appDbPath, target.settingKey, target.defaultValue());
      continue;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(rawContent);
    } catch (error) {
      throw new Error(`${target.repoRelativePath} 不是有效 JSON，无法同步到本机设置。`);
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error(`${target.repoRelativePath} 内容格式不正确，无法同步到本机设置。`);
    }
    writeSharedSettingRecord(appDbPath, target.settingKey, stripUnsupportedSharedSettings(parsed as Record<string, unknown>));
  }
}

function isPlainRecord(value: unknown): value is SharedSettingsRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function parseSharedSettingsContent(rawContent: string | null | undefined) {
  if (!rawContent) return null;
  try {
    const parsed = JSON.parse(rawContent);
    return isPlainRecord(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function areJsonValuesEqual(left: unknown, right: unknown) {
  return JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
}

function createEffectDraft(
  id: string,
  title: string,
  summary: string,
  visibility: CollabEffectPreview['visibility'],
  scopeLabel: string,
  relatedPaths: string[],
  details: string[] = [],
): EffectDraft {
  return {
    id,
    title,
    summary,
    visibility,
    scopeLabel,
    details,
    relatedPaths: new Set(relatedPaths),
  };
}

function finalizeEffectDrafts(drafts: EffectDraft[]): CollabEffectPreview[] {
  return drafts
    .map((draft) => ({
      id: draft.id,
      title: draft.title,
      summary: draft.summary,
      visibility: draft.visibility,
      scopeLabel: draft.scopeLabel,
      details: Array.from(new Set(draft.details.filter(Boolean))),
      relatedPaths: Array.from(draft.relatedPaths),
      beforeLabel: draft.beforeLabel ?? null,
      afterLabel: draft.afterLabel ?? null,
      explanationSource: 'user_feature_rules' as const,
      aiUnavailableReason: COLLAB_AI_EXPLANATION_UNAVAILABLE_REASON,
    }))
    .filter((draft) => draft.relatedPaths.length > 0);
}

function limitText(value: string, maxChars: number) {
  if (value.length <= maxChars) return value;
  return `${value.slice(0, maxChars)}\n\n[已截断：剩余 ${value.length - maxChars} 字符未发送给 AI]`;
}

function safeOneLine(value: unknown, fallback = '') {
  return String(value ?? fallback).replace(/\s+/g, ' ').trim();
}

function normalizeAiEffectText(value: unknown, fallback: string) {
  const text = safeOneLine(value, fallback);
  return text || fallback;
}

function effectLooksCodeMechanical(effect: Pick<CollabEffectPreview, 'title' | 'summary' | 'details'>) {
  const text = [effect.title, effect.summary, ...(effect.details || [])].join('\n');
  return /\b(src|backend|cloud_backend|scripts|docs)\//.test(text)
    || /\.(tsx?|jsx?|py|mjs|cjs|json|md|ya?ml|sql)\b/.test(text)
    || /文件|代码路径|组件文件|模块文件/.test(text);
}

function markEffectsAsAiUnavailable(effects: CollabEffectPreview[], reason = COLLAB_AI_EXPLANATION_UNAVAILABLE_REASON) {
  return effects.map((effect) => ({
    ...effect,
    explanationSource: 'unavailable' as const,
    aiUnavailableReason: reason,
  }));
}

function normalizeAiEffectPreviews(rawEffects: CollabEffectPreview[], fallbackEffects: CollabEffectPreview[], files: CollabFileChange[]) {
  const validPaths = new Set(files.map((file) => file.path));
  const fallbackById = new Map(fallbackEffects.map((effect) => [effect.id, effect]));
  const fallbackPaths = Array.from(new Set(fallbackEffects.flatMap((effect) => effect.relatedPaths)));
  const normalized = rawEffects
    .slice(0, 8)
    .map((effect, index) => {
      const fallback = fallbackById.get(effect.id) || fallbackEffects[index] || fallbackEffects[0] || null;
      const relatedPaths = Array.from(new Set((effect.relatedPaths || []).filter((targetPath) => validPaths.has(targetPath))));
      const nextRelatedPaths = relatedPaths.length ? relatedPaths : (fallback?.relatedPaths || fallbackPaths).filter((targetPath) => validPaths.has(targetPath));
      const details = Array.isArray(effect.details)
        ? effect.details.map((detail) => safeOneLine(detail)).filter(Boolean).slice(0, 6)
        : [];
      const normalizedEffect: CollabEffectPreview = {
        id: safeOneLine(effect.id, fallback?.id || `ai-effect-${index + 1}`).replace(/[^a-z0-9._-]+/gi, '-').replace(/^-+|-+$/g, '') || `ai-effect-${index + 1}`,
        title: normalizeAiEffectText(effect.title, fallback?.title || '功能影响待确认'),
        summary: normalizeAiEffectText(effect.summary, fallback?.summary || '这次修改会影响软件功能或后台规则，建议先预览再决定是否接收。'),
        visibility: effect.visibility === 'visible' || effect.visibility === 'mixed' || effect.visibility === 'background'
          ? effect.visibility
          : (fallback?.visibility || 'mixed'),
        scopeLabel: normalizeAiEffectText(effect.scopeLabel, fallback?.scopeLabel || '功能影响'),
        details,
        relatedPaths: nextRelatedPaths,
        beforeLabel: safeOneLine(effect.beforeLabel, fallback?.beforeLabel || '') || null,
        afterLabel: safeOneLine(effect.afterLabel, fallback?.afterLabel || '') || null,
        explanationSource: 'ai',
        aiUnavailableReason: null,
      };
      return normalizedEffect;
    })
    .filter((effect) => effect.title && effect.summary && effect.relatedPaths.length > 0 && !effectLooksCodeMechanical(effect));
  return normalized.length ? normalized : null;
}

async function collectEffectCommitSummaries(context: RepoWorkContext, mode: 'push' | 'pull', snapshot: RepoSnapshot) {
  const revisionRange = mode === 'push' ? 'origin/main..HEAD' : `HEAD..${snapshot.remoteTargetRevision}`;
  const scopedGitArgs = context.scopeRelativePath ? ['--', context.scopeRelativePath] : [];
  const result = await runGit(
    context.gitRepoPath,
    ['log', '--reverse', '--format=%h %aI %s', revisionRange, ...scopedGitArgs],
    { allowNonZero: true },
  );
  return result.stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 20);
}

async function collectEffectDiffPreview(context: RepoWorkContext, mode: 'push' | 'pull', snapshot: RepoSnapshot, files: CollabFileChange[]) {
  const scopedPaths = Array.from(new Set(files
    .map((file) => toScopedGitPath(context.scopeRelativePath, file.path))
    .filter(Boolean)))
    .slice(0, 80);
  const pathArgs = scopedPaths.length ? ['--', ...scopedPaths] : [];
  const pieces: string[] = [];
  if (mode === 'push') {
    if (snapshot.aheadCount > 0) {
      const aheadResult = await runGit(
        context.gitRepoPath,
        ['diff', '--unified=2', '--no-ext-diff', 'origin/main...HEAD', ...pathArgs],
        { allowNonZero: true },
      );
      if (aheadResult.stdout.trim()) pieces.push(`[本地已提交但未推送的差异]\n${aheadResult.stdout}`);
    }
    const worktreeResult = await runGit(
      context.gitRepoPath,
      ['diff', '--unified=2', '--no-ext-diff', 'HEAD', ...pathArgs],
      { allowNonZero: true },
    );
    if (worktreeResult.stdout.trim()) pieces.push(`[本地未提交差异]\n${worktreeResult.stdout}`);
    const untracked = files.filter((file) => file.type === 'untracked').map((file) => file.path).slice(0, 30);
    if (untracked.length) pieces.push(`[新增未跟踪文件]\n${untracked.join('\n')}`);
  } else {
    const remoteResult = await runGit(
      context.gitRepoPath,
      ['diff', '--unified=2', '--no-ext-diff', 'HEAD', snapshot.remoteTargetRevision, ...pathArgs],
      { allowNonZero: true },
    );
    if (remoteResult.stdout.trim()) pieces.push(`[远端 main 到当前预览点的差异]\n${remoteResult.stdout}`);
  }
  return limitText(pieces.join('\n\n'), MAX_EFFECT_DIFF_PREVIEW_CHARS);
}

function buildFunctionalSuggestedMessage(prefix: 'push' | 'pull', groups: CollabChangeGroup[], effects: CollabEffectPreview[]) {
  const titles = effects
    .filter((effect) => effect.explanationSource === 'ai' || effect.explanationSource === 'user_feature_rules')
    .map((effect) => effect.title
      .replace(/会变化/g, '')
      .replace(/可能调整/g, '')
      .replace(/相关/g, '')
      .trim())
    .filter(Boolean)
    .slice(0, 2);
  if (titles.length) {
    return prefix === 'push'
      ? `sync: ${titles.join('、')}`
      : `sync: 从 main 同步${titles.join('、')}`;
  }
  return buildSuggestedMessage(prefix, groups);
}

function labelSharedSettingKey(settingKey: string) {
  return SHARED_SETTING_LABELS[settingKey] || settingKey;
}

async function readGitObject(context: RepoWorkContext, revision: string, targetPath: string) {
  const gitTargetPath = toScopedGitPath(context.scopeRelativePath, targetPath);
  const result = await runGit(context.gitRepoPath, ['show', `${revision}:${gitTargetPath}`], { allowNonZero: true });
  if (result.exitCode !== 0) return null;
  return result.stdout;
}

async function readWorkingTreeText(context: RepoWorkContext, targetPath: string) {
  return fs.promises.readFile(path.join(context.repoPath, targetPath), 'utf8').catch(() => null);
}

function normalizeRepoPath(targetPath: string) {
  return normalizeCollabRepoBindingPath(targetPath);
}

function normalizeRelativePath(targetPath: string) {
  return targetPath.replace(/\\/g, '/').replace(/^\.\//, '').replace(/^\/+/, '');
}

function computeScopeRelativePath(gitRepoPath: string, repoPath: string) {
  const relativePath = normalizeRelativePath(path.relative(gitRepoPath, repoPath));
  return relativePath && relativePath !== '.' ? relativePath : null;
}

function toScopedGitPath(scopeRelativePath: string | null, targetPath: string) {
  const normalizedTargetPath = normalizeRelativePath(targetPath);
  if (!scopeRelativePath) return normalizedTargetPath;
  return normalizedTargetPath ? `${scopeRelativePath}/${normalizedTargetPath}` : scopeRelativePath;
}

function stripScopePrefix(targetPath: string, scopeRelativePath: string | null) {
  const normalizedTargetPath = normalizeRelativePath(targetPath);
  if (!scopeRelativePath) return normalizedTargetPath;
  if (normalizedTargetPath === scopeRelativePath) return '';
  const prefix = `${scopeRelativePath}/`;
  if (!normalizedTargetPath.startsWith(prefix)) return null;
  return normalizedTargetPath.slice(prefix.length);
}

function mapStatusEntryToScope(entry: ParsedStatusEntry, scopeRelativePath: string | null): ParsedStatusEntry | null {
  const scopedPath = stripScopePrefix(entry.path, scopeRelativePath);
  const scopedPreviousPath = entry.previousPath ? stripScopePrefix(entry.previousPath, scopeRelativePath) : null;
  if (scopedPath === null) {
    if (entry.type === 'renamed' && scopedPreviousPath) {
      return {
        ...entry,
        path: scopedPreviousPath,
        previousPath: scopedPreviousPath,
      };
    }
    return null;
  }
  return {
    ...entry,
    path: scopedPath,
    previousPath: scopedPreviousPath,
  };
}

function mapDiffEntryToScope(entry: ParsedDiffEntry, scopeRelativePath: string | null): ParsedDiffEntry | null {
  const scopedPath = stripScopePrefix(entry.path, scopeRelativePath);
  const scopedPreviousPath = entry.previousPath ? stripScopePrefix(entry.previousPath, scopeRelativePath) : null;
  if (scopedPath === null) {
    if (entry.type === 'renamed' && scopedPreviousPath) {
      return {
        ...entry,
        path: scopedPreviousPath,
        previousPath: scopedPreviousPath,
      };
    }
    return null;
  }
  return {
    ...entry,
    path: scopedPath,
    previousPath: scopedPreviousPath,
  };
}

function createRepoWorkContext(repoPath: string, gitRepoPath: string, scopeRelativePath: string | null): RepoWorkContext {
  return { repoPath, gitRepoPath, scopeRelativePath };
}

function parseFileChangeTypeFromStatus(x: string, y: string, remainder: string): CollabFileChangeType {
  if (x === '?' && y === '?') return 'untracked';
  if (remainder.includes(' -> ') || x === 'R' || y === 'R') return 'renamed';
  if (x === 'D' || y === 'D') return 'deleted';
  if (x === 'A' || y === 'A') return 'added';
  return 'modified';
}

function isUnmergedStatus(x: string, y: string) {
  const pair = `${x}${y}`;
  return x === 'U' || y === 'U' || ['DD', 'AU', 'UD', 'UA', 'DU', 'AA', 'UU'].includes(pair);
}

function parseBranchHeader(rawLine: string) {
  const header = rawLine.replace(/^##\s*/, '').trim();
  if (!header) {
    return { branch: null, aheadCount: 0, behindCount: 0 };
  }
  if (header.startsWith('HEAD ')) {
    return { branch: 'HEAD', aheadCount: 0, behindCount: 0 };
  }
  const statusMatch = header.match(/^([^\s.]+)(?:\.\.\.[^\s]+)?(?: \[(.+)\])?$/);
  const branch = statusMatch?.[1] || header.split('...')[0] || header;
  const trailer = statusMatch?.[2] || '';
  const aheadCount = Number(trailer.match(/ahead (\d+)/)?.[1] || 0);
  const behindCount = Number(trailer.match(/behind (\d+)/)?.[1] || 0);
  return { branch, aheadCount, behindCount };
}

function parseStatusEntries(rawOutput: string) {
  const lines = rawOutput
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter(Boolean);
  const branchHeader = lines[0]?.startsWith('##') ? lines.shift() || '' : '';
  const parsedEntries: ParsedStatusEntry[] = [];
  for (const line of lines) {
    const x = line[0] || ' ';
    const y = line[1] || ' ';
    const remainder = line.slice(3);
    const type = parseFileChangeTypeFromStatus(x, y, remainder);
    if (type === 'renamed') {
      const [previousPath, nextPath] = remainder.split(' -> ');
      parsedEntries.push({
        path: (nextPath || previousPath || '').trim(),
        previousPath: previousPath?.trim() || null,
        type,
        x,
        y,
        isUnmerged: isUnmergedStatus(x, y),
      });
      continue;
    }
    parsedEntries.push({
      path: remainder.trim(),
      type,
      x,
      y,
      isUnmerged: isUnmergedStatus(x, y),
    });
  }
  return { branchHeader, parsedEntries };
}

function parseDiffEntries(rawOutput: string) {
  return rawOutput
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .flatMap((line) => {
      const parts = line.split('\t');
      const code = parts[0] || '';
      if (code.startsWith('R')) {
        const previousPath = parts[1]?.trim();
        const nextPath = parts[2]?.trim();
        if (!nextPath) return [];
        return [{
          path: nextPath,
          previousPath: previousPath || null,
          type: 'renamed' as const,
        }];
      }
      const targetPath = parts[1]?.trim();
      if (!targetPath) return [];
      const typeMap: Record<string, ParsedDiffEntry['type']> = {
        A: 'added',
        D: 'deleted',
        M: 'modified',
        T: 'modified',
      };
      return [{
        path: targetPath,
        type: typeMap[code[0] || 'M'] || 'modified',
      }];
    });
}

function classifyChangeGroup(targetPath: string) {
  const normalized = targetPath.replace(/\\/g, '/');
  if (normalized.startsWith('.yiyu-sync/')) {
    return { key: 'shared_settings' as const, label: GROUP_LABELS.shared_settings };
  }
  if (normalized.startsWith('src/renderer/')) return { key: 'renderer' as const, label: GROUP_LABELS.renderer };
  if (normalized.startsWith('src/main/') || normalized.startsWith('build-resources/')) {
    return { key: 'desktop_shell' as const, label: GROUP_LABELS.desktop_shell };
  }
  if (normalized.startsWith('backend/')) return { key: 'local_backend' as const, label: GROUP_LABELS.local_backend };
  if (normalized.startsWith('cloud_backend/')) return { key: 'cloud_backend' as const, label: GROUP_LABELS.cloud_backend };
  if (
    normalized.startsWith('scripts/') ||
    normalized.startsWith('docs/') ||
    normalized === 'README.md' ||
    normalized.endsWith('.md') ||
    normalized.endsWith('.docx') ||
    normalized.endsWith('.json') ||
    normalized.endsWith('.yaml') ||
    normalized.endsWith('.yml') ||
    normalized.endsWith('.toml') ||
    normalized.endsWith('.config.ts') ||
    normalized.endsWith('.config.js') ||
    normalized.startsWith('.')
  ) {
    return { key: 'scripts_docs' as const, label: GROUP_LABELS.scripts_docs };
  }
  return { key: 'other' as const, label: GROUP_LABELS.other };
}

function formatChangeSummary(type: CollabFileChangeType, previousPath?: string | null) {
  switch (type) {
    case 'added':
      return '新增';
    case 'deleted':
      return '删除';
    case 'renamed':
      return previousPath ? `重命名自 ${previousPath}` : '重命名';
    case 'untracked':
      return '未跟踪';
    default:
      return '修改';
  }
}

function hasBinaryExtension(targetPath: string) {
  return BINARY_EXTENSIONS.has(path.extname(targetPath).toLowerCase());
}

function isIgnorableLocalStatusPath(targetPath: string) {
  const normalizedPath = normalizeRelativePath(targetPath).replace(/\/+$/, '');
  const pathSegments = normalizedPath.split('/').filter(Boolean);
  const basename = pathSegments[pathSegments.length - 1] || normalizedPath;
  return IGNORABLE_LOCAL_STATUS_PATHS.has(normalizedPath)
    || IGNORABLE_LOCAL_STATUS_PREFIXES.some((prefix) => normalizedPath === prefix.slice(0, -1) || normalizedPath.startsWith(prefix))
    || pathSegments.some((segment) => GENERATED_LOCAL_STATUS_SEGMENTS.has(segment))
    || GENERATED_LOCAL_STATUS_SUFFIXES.some((suffix) => normalizedPath.endsWith(suffix))
    || basename === '.env'
    || basename.startsWith('.env.');
}

function isSharedSettingsRepoPath(targetPath: string) {
  const normalizedPath = normalizeRelativePath(targetPath).replace(/\/+$/, '');
  return SHARED_SETTINGS_TARGETS.some((target) => target.repoRelativePath === normalizedPath);
}

function addPathsToSet(targetSet: Set<string>, targetPath: string, previousPath?: string | null) {
  targetSet.add(targetPath);
  if (previousPath) targetSet.add(previousPath);
}

function countGroups(files: CollabFileChange[]): CollabChangeGroup[] {
  const counts = new Map<CollabChangeGroupKey, number>();
  for (const file of files) {
    counts.set(file.groupKey, (counts.get(file.groupKey) || 0) + 1);
  }
  return GROUP_ORDER
    .filter((groupKey) => counts.has(groupKey))
    .map((groupKey) => ({
      key: groupKey,
      label: GROUP_LABELS[groupKey],
      fileCount: counts.get(groupKey) || 0,
    }));
}

function buildSuggestedMessage(prefix: 'push' | 'pull', groups: CollabChangeGroup[]) {
  const labels = groups.slice(0, 3).map((group) => group.label).join('、') || '代码';
  return prefix === 'push' ? `sync: 更新${labels}` : `sync: 从 main 同步${labels}`;
}

function summarizeRendererEffect(targetPath: string) {
  const normalized = targetPath.replace(/\\/g, '/');
  if (
    normalized.includes('feishu')
    || normalized.includes('Feishu')
    || normalized.includes('document')
    || normalized.includes('documents')
  ) {
    return {
      id: 'feature-feishu-documents',
      title: '飞书云文档同步和创建能力会变化',
      summary: '这会影响任务、资料或工作台内容同步到飞书云文档的入口、创建流程或状态展示。',
      visibility: 'visible' as const,
      scopeLabel: '飞书联动',
      detail: '同步后建议检查飞书授权、文档创建按钮、同步状态和失败提示。',
    };
  }
  if (
    normalized.includes('auth')
    || normalized.includes('Auth')
    || normalized.includes('login')
    || normalized.includes('register')
    || normalized.includes('membership')
  ) {
    return {
      id: 'feature-auth-and-membership',
      title: '注册登录、本地模式或加入组织流程会变化',
      summary: '这会影响新电脑首次打开、账号登录、云端绑定、邀请码或组织身份识别。',
      visibility: 'visible' as const,
      scopeLabel: '账号与组织',
      detail: '同步后建议用新设备场景检查本地注册、登录、填写云地址和加入组织。',
    };
  }
  if (
    normalized.includes('Admin')
    || normalized.includes('admin')
    || normalized.includes('employees')
    || normalized.includes('permission')
  ) {
    return {
      id: 'feature-org-admin',
      title: '组织权限、成员管理或管理员操作会变化',
      summary: '这会影响管理员看到成员、审核成员、管理权限或处理组织内账号的方式。',
      visibility: 'visible' as const,
      scopeLabel: '组织管理',
      detail: '同步后建议用管理员账号检查成员列表、权限入口和普通成员可见范围。',
    };
  }
  if (normalized === 'src/renderer/App.tsx' || normalized.startsWith('src/renderer/components/collab/')) {
    return {
      id: 'renderer-collab-shell',
      title: '推送/同步按钮的合并方式会变化',
      summary: '同步按钮会先解释和预览双方修改；复杂改动不再由软件自动合并，避免静默覆盖或跳过功能。',
      visibility: 'visible' as const,
      scopeLabel: '界面可见',
      detail: '协作同步入口、确认弹窗、冲突决策和主要提示文案会更新。',
    };
  }
  if (normalized.startsWith('src/renderer/components/settings/')) {
    return {
      id: 'renderer-settings',
      title: '系统设置页的结构或文案会变化',
      summary: '你会在系统设置里直接看到布局、卡片或说明文字的调整。',
      visibility: 'visible' as const,
      scopeLabel: '界面可见',
      detail: '系统设置相关组件有改动，进入设置页时能直接看到变化。',
    };
  }
  if (normalized.startsWith('src/renderer/components/tasks/')) {
    return {
      id: 'renderer-tasks',
      title: '任务与日程模块会变化',
      summary: '任务与日程页面的结构、流程或操作入口会调整。',
      visibility: 'visible' as const,
      scopeLabel: '界面可见',
      detail: '任务相关组件有改动，建议同步后直接进入“任务与日程”确认。',
    };
  }
  if (normalized.startsWith('src/renderer/components/client_workspace/')) {
    return {
      id: 'renderer-client-workspace',
      title: '客户工作台的页面表现会变化',
      summary: '客户工作台里的区域结构、入口或交互可能会更新。',
      visibility: 'visible' as const,
      scopeLabel: '界面可见',
      detail: '客户工作台相关组件有改动，同步后建议优先打开该模块确认。',
    };
  }
  if (normalized.startsWith('src/renderer/components/strategic_accompaniment/')) {
    return {
      id: 'renderer-strategic',
      title: '战略陪伴模块会变化',
      summary: '战略陪伴页面的结构或操作流程可能会更新。',
      visibility: 'visible' as const,
      scopeLabel: '界面可见',
      detail: '战略陪伴相关组件有改动。',
    };
  }
  return {
    id: 'renderer-general',
    title: '软件界面会变化',
    summary: '同步后，至少会有一处你能直接看到的界面变化。',
    visibility: 'visible' as const,
    scopeLabel: '界面可见',
    detail: '前端界面文件有改动，建议同步后打开对应模块核对前后差别。',
  };
}

function summarizeDesktopEffect(targetPath: string) {
  const normalized = targetPath.replace(/\\/g, '/');
  if (normalized.includes('autoUpdater') || normalized.includes('release') || normalized.includes('version')) {
    return {
      id: 'feature-release-update',
      title: '软件检查更新或版本发布链路会变化',
      summary: '这会影响软件如何发现新版本、下载安装包、识别组织定向版本或展示更新状态。',
      visibility: 'mixed' as const,
      scopeLabel: '软件更新',
      detail: '同步后建议检查版本号、检查更新按钮、中央更新接口和下载安装提示。',
    };
  }
  if (normalized.includes('collabGit') || normalized.includes('preload') || normalized === 'src/shared/types.ts') {
    return {
      id: 'feature-collab-merge',
      title: '推送/同步按钮的底层合并规则会变化',
      summary: '这会影响你和同事如何把各自修改合并到同一个 main，目标是不再遗漏双方功能。',
      visibility: 'mixed' as const,
      scopeLabel: '协作同步',
      detail: '同步后建议分别测试协作分支发布、main 快进接收和隔离预览。',
    };
  }
  if (normalized.startsWith('src/main/') || normalized === 'src/renderer/lib/api.ts' || normalized === 'src/shared/types.ts') {
    return {
      id: 'desktop-collab-runtime',
      title: '桌面端运行或桥接行为会变化',
      summary: '按钮背后的本地服务、桌面桥接、Git 同步或安装版更新流程会变化。',
      visibility: 'mixed' as const,
      scopeLabel: '桌面行为',
      detail: '这类变化不一定马上体现在单个页面上，但会直接影响按钮怎么工作。',
    };
  }
  return {
    id: 'desktop-general',
    title: '桌面端行为会变化',
    summary: '安装版的本地行为、桥接能力或启动逻辑会更新。',
    visibility: 'mixed' as const,
    scopeLabel: '桌面行为',
    detail: '这类变化更多影响软件怎么运行，而不是单个界面长什么样。',
  };
}

function summarizeBackendEffect(groupKey: CollabChangeGroupKey) {
  if (groupKey === 'local_backend') {
    return {
      id: 'backend-local',
      title: '本机数据处理和本地接口会变化',
      summary: '这会影响本机账号、任务、文档、飞书、AI 或设置数据在本机如何保存和处理。',
      visibility: 'background' as const,
      scopeLabel: '后台逻辑',
      detail: '这类改动通常体现在任务结果、数据状态或接口响应上。',
    };
  }
  if (groupKey === 'cloud_backend') {
    return {
      id: 'backend-cloud',
      title: '组织云端共享规则会变化',
      summary: '这会影响成员入组、组织权限、共享数据、云端 AI 配置或定向推送等跨设备能力。',
      visibility: 'background' as const,
      scopeLabel: '后台逻辑',
      detail: '这类变化更偏业务规则和共享数据处理。',
    };
  }
  return {
    id: 'docs-config',
    title: '脚本、文档或配置会变化',
    summary: '你未必马上在界面看到差别，但后续构建、安装或说明文档会更新。',
    visibility: 'background' as const,
    scopeLabel: '配置与文档',
    detail: '这类变化通常影响协作方式、构建流程或说明文档。',
  };
}

function addEffectDetail(effectMap: Map<string, EffectDraft>, nextDraft: ReturnType<typeof createEffectDraft>, detail?: string | null) {
  const existing = effectMap.get(nextDraft.id);
  if (existing) {
    nextDraft.relatedPaths.forEach((targetPath) => existing.relatedPaths.add(targetPath));
    if (detail) existing.details.push(detail);
    return;
  }
  if (detail) nextDraft.details.push(detail);
  effectMap.set(nextDraft.id, nextDraft);
}

async function buildSharedSettingsEffect(
  mode: 'push' | 'pull',
  context: RepoWorkContext,
  files: CollabFileChange[],
) {
  const target = SHARED_SETTINGS_TARGETS[0];
  const matchedFiles = files.filter((file) => file.path === target.repoRelativePath);
  if (!matchedFiles.length) return null;
  const beforeRevision = mode === 'push' ? 'origin/main' : 'HEAD';
  const beforeRecord = stripUnsupportedSharedSettings(parseSharedSettingsContent(await readGitObject(context, beforeRevision, target.repoRelativePath)) || target.defaultValue());
  const afterRecord = mode === 'push'
    ? stripUnsupportedSharedSettings(parseSharedSettingsContent(await readWorkingTreeText(context, target.repoRelativePath)) || target.defaultValue())
    : stripUnsupportedSharedSettings(parseSharedSettingsContent(await readGitObject(context, 'origin/main', target.repoRelativePath)) || target.defaultValue());
  const changedKeys = Array.from(new Set([
    ...Object.keys(beforeRecord),
    ...Object.keys(afterRecord),
  ])).filter((settingKey) => !areJsonValuesEqual(beforeRecord[settingKey], afterRecord[settingKey]));
  if (!changedKeys.length) return null;
  const changedLabels = changedKeys.slice(0, 4).map(labelSharedSettingKey);
  const draft = createEffectDraft(
    'shared-settings-system-admin',
    '系统级共享设置会变化',
    '同步后，系统级共享设置会变化，并影响这台机器对保护规则的理解。',
    'mixed',
    '共享设置',
    matchedFiles.map((file) => file.path),
    changedLabels.map((label) => `${label} 会更新`),
  );
  draft.beforeLabel = mode === 'push' ? 'main 当前效果' : '你本地当前效果';
  draft.afterLabel = mode === 'push' ? '推送到 main 后' : '从 main 同步后';
  return draft;
}

async function buildEffectPreviews(
  mode: 'push' | 'pull',
  snapshot: RepoSnapshot,
  files: CollabFileChange[],
) {
  if (!snapshot.repoPath || !snapshot.gitRepoPath) return [];
  const context = createRepoWorkContext(snapshot.repoPath, snapshot.gitRepoPath, snapshot.scopeRelativePath);
  const effectMap = new Map<string, EffectDraft>();
  const sharedEffect = await buildSharedSettingsEffect(mode, context, files);
  if (sharedEffect) effectMap.set(sharedEffect.id, sharedEffect);
  for (const file of files) {
    const normalized = file.path.replace(/\\/g, '/');
    if (normalized === '.yiyu-sync/settings.system_admin.json') continue;
    if (normalized === '.yiyu-sync/intelligence-demo.json') {
      addEffectDetail(
        effectMap,
        createEffectDraft(
          'shared-intelligence-demo',
          '资讯情报站讨论样例会同步',
          '同步后，同事的资讯情报站会导入日慈画像和南沙公益创投情报，用于本轮模块对齐。',
          'visible',
          '共享样例',
          [file.path],
        ),
        '包含 5 个情报画像、1 条南沙公益创投情报和完整顾问 memo。',
      );
      continue;
    }
    if (file.groupKey === 'renderer') {
      const effect = summarizeRendererEffect(normalized);
      addEffectDetail(
        effectMap,
        createEffectDraft(effect.id, effect.title, effect.summary, effect.visibility, effect.scopeLabel, [file.path]),
        effect.detail,
      );
      continue;
    }
    if (file.groupKey === 'desktop_shell' || normalized === 'src/renderer/lib/api.ts' || normalized === 'src/shared/types.ts') {
      const effect = summarizeDesktopEffect(normalized);
      addEffectDetail(
        effectMap,
        createEffectDraft(effect.id, effect.title, effect.summary, effect.visibility, effect.scopeLabel, [file.path]),
        effect.detail,
      );
      continue;
    }
    if (file.groupKey === 'local_backend' || file.groupKey === 'cloud_backend' || file.groupKey === 'scripts_docs' || file.groupKey === 'other') {
      const effect = summarizeBackendEffect(file.groupKey === 'other' ? 'scripts_docs' : file.groupKey);
      addEffectDetail(
        effectMap,
        createEffectDraft(effect.id, effect.title, effect.summary, effect.visibility, effect.scopeLabel, [file.path]),
        effect.detail,
      );
    }
  }
  return finalizeEffectDrafts(Array.from(effectMap.values()));
}

async function explainEffectPreviews(
  mode: 'push' | 'pull',
  snapshot: RepoSnapshot,
  groups: CollabChangeGroup[],
  files: CollabFileChange[],
  fallbackEffects: CollabEffectPreview[],
  suggestedMessage: string,
  options: {
    effectExplainer?: CollabEffectExplainer | null;
    commitSummaries?: string[];
    syncTargetLabel?: string | null;
  } = {},
) {
  if (!files.length || !snapshot.repoPath || !snapshot.gitRepoPath) return fallbackEffects;
  if (!options.effectExplainer) return markEffectsAsAiUnavailable(fallbackEffects);
  const context = createRepoWorkContext(snapshot.repoPath, snapshot.gitRepoPath, snapshot.scopeRelativePath);
  try {
    const commitSummaries = options.commitSummaries?.length
      ? options.commitSummaries
      : await collectEffectCommitSummaries(context, mode, snapshot);
    const diffPreview = await collectEffectDiffPreview(context, mode, snapshot, files);
    const aiEffects = await options.effectExplainer({
      mode,
      suggestedMessage,
      syncTargetLabel: options.syncTargetLabel || null,
      commitSummaries,
      diffPreview,
      groups,
      files,
      fallbackEffects,
    });
    const normalized = normalizeAiEffectPreviews(aiEffects || [], fallbackEffects, files);
    if (normalized) return normalized;
    return markEffectsAsAiUnavailable(
      fallbackEffects,
      'AI 功能说明返回内容仍偏代码路径或没有覆盖真实改动，已降级为规则兜底。',
    );
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    return markEffectsAsAiUnavailable(
      fallbackEffects,
      `AI 功能说明生成失败：${detail}`,
    );
  }
}

async function runCommand(command: string, args: string[], options: RunCommandOptions = {}): Promise<RunCommandResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      stdio: [options.input === undefined ? 'ignore' : 'pipe', 'pipe', 'pipe'],
      env: process.env,
    });
    let stdout = '';
    let stderr = '';
    const childStdout = child.stdout;
    const childStderr = child.stderr;
    const childStdin = child.stdin;
    if (!childStdout || !childStderr || (options.input !== undefined && !childStdin)) {
      child.kill();
      reject(new Error(`${command} stdio is not available`));
      return;
    }
    if (options.input !== undefined) {
      if (!childStdin) {
        child.kill();
        reject(new Error(`${command} stdin is not available`));
        return;
      }
      childStdin.write(options.input);
      childStdin.end();
    }
    childStdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });
    childStderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });
    child.on('error', reject);
    child.on('close', (exitCode) => {
      const normalizedExitCode = exitCode ?? 0;
      if (!options.allowNonZero && normalizedExitCode !== 0) {
        reject(new Error((stderr || stdout || `${command} exited with status ${normalizedExitCode}`).trim()));
        return;
      }
      resolve({
        stdout,
        stderr,
        exitCode: normalizedExitCode,
      });
    });
  });
}

async function runGit(repoPath: string, args: string[], options: RunCommandOptions = {}) {
  return runCommand('git', args, {
    cwd: repoPath,
    allowNonZero: options.allowNonZero,
    input: options.input,
  });
}

async function getGitIgnoredPathSet(repoRoot: string, targetPaths: string[]) {
  const normalizedPaths = Array.from(new Set(
    targetPaths
      .map((targetPath) => normalizeRelativePath(targetPath))
      .filter(Boolean),
  ));
  if (!normalizedPaths.length) return new Set<string>();
  const result = await runGit(repoRoot, ['check-ignore', '--stdin'], {
    allowNonZero: true,
    input: `${normalizedPaths.join('\n')}\n`,
  });
  return new Set(
    result.stdout
      .split(/\r?\n/)
      .map((line) => normalizeRelativePath(line.trim()))
      .filter(Boolean),
  );
}

async function resolveGitRepoTopLevel(targetPath: string) {
  const stat = await fs.promises.stat(targetPath).catch(() => null);
  if (!stat?.isDirectory()) return null;
  const result = await runCommand('git', ['rev-parse', '--show-toplevel'], {
    cwd: targetPath,
    allowNonZero: true,
  });
  if (result.exitCode !== 0) return null;
  const repoRoot = result.stdout.trim();
  return repoRoot ? normalizeRepoPath(repoRoot) : null;
}

async function listFilesRecursively(targetPath: string): Promise<string[]> {
  const stat = await fs.promises.stat(targetPath).catch(() => null);
  if (!stat) return [];
  if (stat.isFile()) return [targetPath];
  if (!stat.isDirectory()) return [];
  const entries = await fs.promises.readdir(targetPath, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async (entry) => {
    const nextPath = path.join(targetPath, entry.name);
    if (entry.isDirectory()) return listFilesRecursively(nextPath);
    if (entry.isFile()) return [nextPath];
    return [];
  }));
  return nested.flat();
}

async function expandUntrackedDirectoryEntries(repoRoot: string, entries: ParsedStatusEntry[]) {
  const expandedEntries: ParsedStatusEntry[] = [];
  for (const entry of entries) {
    if (entry.type !== 'untracked') {
      expandedEntries.push(entry);
      continue;
    }
    const normalizedPath = entry.path.replace(/\\/g, '/');
    const looksLikeDirectory = normalizedPath.endsWith('/');
    const absolutePath = path.join(repoRoot, normalizedPath.replace(/\/$/, ''));
    const stat = await fs.promises.stat(absolutePath).catch(() => null);
    if (!looksLikeDirectory && !stat?.isDirectory()) {
      expandedEntries.push(entry);
      continue;
    }
    const files = await listFilesRecursively(absolutePath);
    if (!files.length) {
      const collapsedPath = normalizedPath.replace(/\/$/, '');
      expandedEntries.push({ ...entry, path: collapsedPath });
      continue;
    }
    for (const filePath of files) {
      expandedEntries.push({
        ...entry,
        path: path.relative(repoRoot, filePath).replace(/\\/g, '/'),
      });
    }
  }
  const ignoredPaths = await getGitIgnoredPathSet(repoRoot, expandedEntries.map((entry) => entry.path));
  return expandedEntries.filter((entry) => {
    const normalizedPath = normalizeRelativePath(entry.path);
    return !ignoredPaths.has(normalizedPath) && !isIgnorableLocalStatusPath(normalizedPath);
  });
}

export async function findSuggestedCollabRepoPath(candidates: string[]) {
  const seen = new Set<string>();
  for (const candidate of candidates) {
    if (!candidate) continue;
    const normalized = normalizeRepoPath(candidate);
    if (seen.has(normalized)) continue;
    seen.add(normalized);
    const repoRoot = await resolveGitRepoTopLevel(normalized);
    if (repoRoot) return normalized;
  }
  return null;
}

function createStatusText(
  snapshot: Pick<RepoSnapshot, 'isConfigured' | 'isValid' | 'branch' | 'isMainBranch' | 'hasUnmergedPaths' | 'behindCount' | 'aheadCount' | 'localChangeCount'>,
  suggestedRepoPath?: string | null,
) {
  if (!snapshot.isConfigured) return '先绑定源码目录，按钮才会生效。';
  if (!snapshot.isValid) return '当前目录不是有效 Git 仓库。';
  if (snapshot.hasUnmergedPaths) return '检测到 Git 冲突，请先手工收口。';
  if (!snapshot.isMainBranch) {
    if (suggestedRepoPath) {
      return `当前工作目录在 ${snapshot.branch || '未知'} 分支，系统会改用 main 基线仓库继续。`;
    }
    return `当前分支是 ${snapshot.branch || '未知'}，请先切回 main。`;
  }
  if (snapshot.behindCount > 0 && snapshot.localChangeCount > 0) {
    return `main 落后 ${snapshot.behindCount} 个提交，且本地还有 ${snapshot.localChangeCount} 项改动。`;
  }
  if (snapshot.behindCount > 0) return `main 落后 ${snapshot.behindCount} 个提交，请先同步。`;
  if (snapshot.localChangeCount > 0) return `本地有 ${snapshot.localChangeCount} 项待处理改动。`;
  if (snapshot.aheadCount > 0) return `本地有 ${snapshot.aheadCount} 个已提交未推送变更。`;
  return '当前已与 origin/main 对齐。';
}

async function resolvePullTargetRevision(context: RepoWorkContext, targetCommit?: string | null) {
  const trimmed = targetCommit?.trim();
  if (!trimmed) return 'origin/main';
  if (!/^[0-9a-f]{7,40}$/i.test(trimmed)) {
    throw new Error(`同步目标不是有效提交号：${trimmed}`);
  }
  const verifyResult = await runGit(context.gitRepoPath, ['rev-parse', '--verify', `${trimmed}^{commit}`], { allowNonZero: true });
  if (verifyResult.exitCode !== 0) {
    throw new Error(`找不到要同步的提交：${trimmed}`);
  }
  const resolvedHash = verifyResult.stdout.trim();
  const headAncestorResult = await runGit(context.gitRepoPath, ['merge-base', '--is-ancestor', 'HEAD', resolvedHash], { allowNonZero: true });
  if (headAncestorResult.exitCode !== 0) {
    throw new Error(`提交 ${trimmed} 不在当前本地版本之后，不能作为同步截止点。`);
  }
  const remoteAncestorResult = await runGit(context.gitRepoPath, ['merge-base', '--is-ancestor', resolvedHash, 'origin/main'], { allowNonZero: true });
  if (remoteAncestorResult.exitCode !== 0) {
    throw new Error(`提交 ${trimmed} 不属于当前 origin/main，不能从协作同步入口拉取。`);
  }
  return resolvedHash;
}

async function collectRepoSnapshot(options: RepoOptions): Promise<RepoSnapshot> {
  const repoPath = options.repoPath ? normalizeRepoPath(options.repoPath) : null;
  const suggestedRepoPath = await findSuggestedCollabRepoPath(options.suggestedCandidates);
  if (!repoPath) {
    return {
      repoPath: null,
      repoName: null,
      suggestedRepoPath,
      gitRepoPath: null,
      scopeRelativePath: null,
      isConfigured: false,
      isValid: false,
      branch: null,
      isMainBranch: false,
      aheadCount: 0,
      behindCount: 0,
      hasUnmergedPaths: false,
      localEntries: [],
      remoteEntries: [],
      localBranchEntries: [],
      localChangeCount: 0,
      remoteChangeCount: 0,
      remoteTargetRevision: 'origin/main',
      statusText: '先绑定源码目录，按钮才会生效。',
      fetchFailed: false,
      fetchErrorMessage: '',
    };
  }
  const repoRoot = await resolveGitRepoTopLevel(repoPath);
  if (!repoRoot) {
    return {
      repoPath,
      repoName: path.basename(repoPath),
      suggestedRepoPath,
      gitRepoPath: null,
      scopeRelativePath: null,
      isConfigured: true,
      isValid: false,
      branch: null,
      isMainBranch: false,
      aheadCount: 0,
      behindCount: 0,
      hasUnmergedPaths: false,
      localEntries: [],
      remoteEntries: [],
      localBranchEntries: [],
      localChangeCount: 0,
      remoteChangeCount: 0,
      remoteTargetRevision: 'origin/main',
      statusText: '当前目录不是有效 Git 仓库。',
      fetchFailed: false,
      fetchErrorMessage: '',
    };
  }
  const scopeRelativePath = computeScopeRelativePath(repoRoot, repoPath);
  const gitContext = createRepoWorkContext(repoPath, repoRoot, scopeRelativePath);

  await exportSharedSettingsToRepo(repoPath, options.appDbPath);

  // P1-1 修复: fetch origin 失败旧版被 allowNonZero 静默吞,
  // 后续 behindCount 用过期 origin/main 算成 0 → 跳过 merge 直接 push,
  // 强行覆盖远端新提交 → 代码丢失. 失败时记录到 snapshot 让 UI 阻断后续推送.
  let fetchFailed = false;
  let fetchErrorMessage = '';
  if (options.fetchRemote) {
    const fetchResult = await runGit(gitContext.gitRepoPath, ['fetch', 'origin'], { allowNonZero: true });
    if (fetchResult.exitCode !== 0) {
      fetchFailed = true;
      fetchErrorMessage = (fetchResult.stderr || '').trim().slice(0, 500)
        || `git fetch origin 失败(exitCode=${fetchResult.exitCode})`;
      // 不直接 throw,先继续走完 snapshot 让 UI 拿到完整状态,
      // 在 snapshot 末尾通过 fetchFailed 字段告诉 UI 阻断 push.
    }
  }
  const remoteTargetRevision = await resolvePullTargetRevision(gitContext, options.targetCommit);

  const scopedGitArgs = scopeRelativePath ? ['--', scopeRelativePath] : [];
  const statusResult = await runGit(gitContext.gitRepoPath, ['status', '--porcelain=v1', '--branch', ...scopedGitArgs]);
  const { branchHeader, parsedEntries } = parseStatusEntries(statusResult.stdout);
  const expandedLocalEntries = await expandUntrackedDirectoryEntries(gitContext.gitRepoPath, parsedEntries);
  const scopedLocalEntries = expandedLocalEntries
    .map((entry) => mapStatusEntryToScope(entry, gitContext.scopeRelativePath))
    .filter((entry): entry is ParsedStatusEntry => Boolean(entry));
  const collabVisibleLocalEntries = scopedLocalEntries.filter((entry) => !isIgnorableLocalStatusPath(entry.path));
  const parsedHeader = parseBranchHeader(branchHeader);
  const { branch } = parsedHeader;
  let { aheadCount, behindCount } = parsedHeader;
  // Fallback: when local main has no upstream tracking (e.g. branch recreated, git config wiped),
  // `git status --branch` won't report ahead/behind. Re-derive via rev-list against origin/main so
  // we never silently treat "behind" as 0 and skip the merge before pushing.
  if (branch === 'main' && aheadCount === 0 && behindCount === 0) {
    try {
      const counts = await runGit(
        gitContext.gitRepoPath,
        ['rev-list', '--left-right', '--count', 'origin/main...HEAD'],
        { allowNonZero: true },
      );
      const [behindStr, aheadStr] = counts.stdout.trim().split(/\s+/);
      const behindFallback = Number(behindStr) || 0;
      const aheadFallback = Number(aheadStr) || 0;
      if (behindFallback > 0 || aheadFallback > 0) {
        behindCount = behindFallback;
        aheadCount = aheadFallback;
      }
    } catch {
      // origin/main may not exist yet (no remote); keep zeros.
    }
  }
  const remoteDiffResult = await runGit(gitContext.gitRepoPath, ['diff', '--name-status', '--find-renames=50%', `HEAD..${remoteTargetRevision}`, ...scopedGitArgs], {
    allowNonZero: true,
  });
  const localBranchDiffResult = await runGit(gitContext.gitRepoPath, ['diff', '--name-status', '--find-renames=50%', 'origin/main...HEAD', ...scopedGitArgs], {
    allowNonZero: true,
  });
  const remoteEntries = parseDiffEntries(remoteDiffResult.stdout)
    .map((entry) => mapDiffEntryToScope(entry, gitContext.scopeRelativePath))
    .filter((entry): entry is ParsedDiffEntry => Boolean(entry));
  const localBranchEntries = parseDiffEntries(localBranchDiffResult.stdout)
    .map((entry) => mapDiffEntryToScope(entry, gitContext.scopeRelativePath))
    .filter((entry): entry is ParsedDiffEntry => Boolean(entry));
  const hasUnmergedPaths = scopedLocalEntries.some((entry) => entry.isUnmerged);
  const snapshotBase = {
    isConfigured: true,
    isValid: true,
    branch,
    isMainBranch: branch === 'main',
    hasUnmergedPaths,
    behindCount,
    aheadCount,
    localChangeCount: collabVisibleLocalEntries.length,
  };
  return {
    repoPath,
    repoName: path.basename(repoPath),
    suggestedRepoPath,
    gitRepoPath: gitContext.gitRepoPath,
    scopeRelativePath: gitContext.scopeRelativePath,
    ...snapshotBase,
    localEntries: collabVisibleLocalEntries,
    remoteEntries,
    localBranchEntries,
    remoteChangeCount: remoteEntries.length,
    remoteTargetRevision,
    statusText: createStatusText(snapshotBase, suggestedRepoPath && suggestedRepoPath !== repoRoot ? suggestedRepoPath : null),
    fetchFailed,
    fetchErrorMessage,
  };
}

function snapshotToStatus(snapshot: RepoSnapshot): CollabRepoStatus {
  return {
    repoPath: snapshot.repoPath,
    repoName: snapshot.repoName,
    suggestedRepoPath: snapshot.suggestedRepoPath,
    workingRepoPath: snapshot.gitRepoPath,
    workingBranch: snapshot.branch,
    workingChangeCount: snapshot.localChangeCount,
    isConfigured: snapshot.isConfigured,
    isValid: snapshot.isValid,
    branch: snapshot.branch,
    isMainBranch: snapshot.isMainBranch,
    hasLocalChanges: snapshot.localChangeCount > 0,
    hasUnmergedPaths: snapshot.hasUnmergedPaths,
    aheadCount: snapshot.aheadCount,
    behindCount: snapshot.behindCount,
    localChangeCount: snapshot.localChangeCount,
    remoteChangeCount: snapshot.remoteChangeCount,
    statusText: snapshot.statusText,
  };
}

function createConflictRisk(kind: CollabConflictRisk['kind'], message: string): CollabConflictRisk {
  return { kind, message };
}

function createLocalFileChanges(snapshot: RepoSnapshot) {
  const remotePaths = new Set<string>();
  const remoteTypeByPath = new Map<string, ParsedDiffEntry['type']>();
  for (const entry of snapshot.remoteEntries) {
    addPathsToSet(remotePaths, entry.path, entry.previousPath);
    remoteTypeByPath.set(entry.path, entry.type);
    if (entry.previousPath) remoteTypeByPath.set(entry.previousPath, entry.type);
  }
  return snapshot.localEntries.map((entry) => {
    const group = classifyChangeGroup(entry.path);
    let risk: CollabConflictRisk | null = null;
    if (entry.isUnmerged) {
      risk = createConflictRisk('unmerged', '这个文件当前已处于 Git 冲突态，需先手工确认。');
    } else if (remotePaths.has(entry.path) || (entry.previousPath && remotePaths.has(entry.previousPath))) {
      const remoteType = remoteTypeByPath.get(entry.path) || (entry.previousPath ? remoteTypeByPath.get(entry.previousPath) : null);
      risk = entry.type === 'deleted' || remoteType === 'deleted'
        ? createConflictRisk('delete_replace', '这个文件在远端 main 也有删除/替换动作，直接推送时很可能互相覆盖。')
        : createConflictRisk('overlap', '这个文件在远端 main 也发生了变化，推送时很可能覆盖对方版本。');
    } else if (entry.type === 'renamed') {
      risk = createConflictRisk('rename', '这个文件涉及重命名，覆盖 main 时要特别留意路径变化。');
    } else if (hasBinaryExtension(entry.path)) {
      risk = createConflictRisk('binary', '这个文件看起来是二进制资源，无法做细粒度合并。');
    }
    return {
      path: entry.path,
      previousPath: entry.previousPath || null,
      type: entry.type,
      groupKey: group.key,
      groupLabel: group.label,
      summary: formatChangeSummary(entry.type, entry.previousPath),
      risk,
    } satisfies CollabFileChange;
  });
}

function createRemoteFileChanges(snapshot: RepoSnapshot) {
  const localChangedPaths = new Set<string>();
  for (const entry of snapshot.localEntries) {
    addPathsToSet(localChangedPaths, entry.path, entry.previousPath);
  }
  for (const entry of snapshot.localBranchEntries) {
    addPathsToSet(localChangedPaths, entry.path, entry.previousPath);
  }
  return snapshot.remoteEntries.map((entry) => {
    const group = classifyChangeGroup(entry.path);
    let risk: CollabConflictRisk | null = null;
    if (entry.type === 'renamed') {
      risk = createConflictRisk('rename', '这个文件在 main 中发生了重命名，覆盖本地时要注意新旧路径。');
    } else if (hasBinaryExtension(entry.path)) {
      risk = createConflictRisk('binary', '这个文件看起来是二进制资源，只能整体覆盖本地版本。');
    } else if (localChangedPaths.has(entry.path) || (entry.previousPath && localChangedPaths.has(entry.previousPath))) {
      risk = entry.type === 'deleted'
        ? createConflictRisk('delete_replace', 'main 准备删除这个文件，但本地也改过它，覆盖时要特别确认。')
        : createConflictRisk('overlap', '这个文件在本地和 main 都发生了变化，同步时很可能互相覆盖。');
    }
    return {
      path: entry.path,
      previousPath: entry.previousPath || null,
      type: entry.type,
      groupKey: group.key,
      groupLabel: group.label,
      summary: formatChangeSummary(entry.type, entry.previousPath),
      risk,
    } satisfies CollabFileChange;
  });
}

function createCommitIdentityLabel(name: string, email: string) {
  const cleanName = name.trim() || '未知提交人';
  const cleanEmail = email.trim();
  return cleanEmail ? `${cleanName} <${cleanEmail}>` : cleanName;
}

function createCommitSourceLabel(authorName: string, authorEmail: string, committerName: string, committerEmail: string) {
  const committer = createCommitIdentityLabel(committerName || authorName, committerEmail || authorEmail);
  if (/noreply\.github\.com$/i.test(committerEmail.trim())) {
    return `GitHub · ${committer}`;
  }
  return `Git 账号/设备线索 · ${committer}`;
}

function mapRepoPathToScope(repoPath: string, scopeRelativePath: string | null) {
  return stripScopePrefix(repoPath, scopeRelativePath);
}

async function getRemoteCommits(context: RepoWorkContext): Promise<CollabRemoteCommit[]> {
  const scopedGitArgs = context.scopeRelativePath ? ['--', context.scopeRelativePath] : [];
  const logResult = await runGit(
    context.gitRepoPath,
    ['log', '--reverse', '--format=%H%x1f%h%x1f%aI%x1f%an%x1f%ae%x1f%cI%x1f%cn%x1f%ce%x1f%s', 'HEAD..origin/main', ...scopedGitArgs],
    { allowNonZero: true },
  );
  const commits = logResult.stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const fields = line.split('\x1f');
      const [
        hash = '',
        shortHash = '',
        authoredAt = '',
        authorName = '',
        authorEmail = '',
        committedAt = '',
        committerName = '',
        committerEmail = '',
        ...subjectParts
      ] = fields;
      const subject = subjectParts.join('\x1f').trim();
      return {
        hash,
        shortHash,
        authoredAt,
        committedAt,
        authorName,
        authorEmail,
        committerName,
        committerEmail,
        subject,
      };
    })
    .filter((commit) => commit.hash && commit.shortHash);

  const result: CollabRemoteCommit[] = [];
  for (const commit of commits) {
    const diffArgs = ['diff-tree', '--no-commit-id', '--name-only', '-r', commit.hash];
    if (context.scopeRelativePath) {
      diffArgs.push('--', context.scopeRelativePath);
    }
    const diffResult = await runGit(context.gitRepoPath, diffArgs, { allowNonZero: true });
    const changedPaths = diffResult.stdout
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((repoPath) => mapRepoPathToScope(repoPath, context.scopeRelativePath))
      .filter((repoPath): repoPath is string => repoPath !== null && repoPath.length > 0);
    result.push({
      ...commit,
      identityLabel: createCommitIdentityLabel(commit.authorName, commit.authorEmail),
      sourceLabel: createCommitSourceLabel(commit.authorName, commit.authorEmail, commit.committerName, commit.committerEmail),
      changedPaths,
      fileCount: changedPaths.length,
    });
  }
  return result;
}

function formatCollabTimestamp(date = new Date()) {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}

function sanitizeBranchSegment(value: string) {
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/@.*$/, '')
    .replace(/[^a-z0-9._-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .replace(/\.+$/g, '');
  return normalized || 'member';
}

async function suggestedCollabBranchName(context: RepoWorkContext) {
  const email = await runGit(context.gitRepoPath, ['config', '--get', 'user.email'], { allowNonZero: true });
  const name = await runGit(context.gitRepoPath, ['config', '--get', 'user.name'], { allowNonZero: true });
  const rawOwner = (email.stdout || name.stdout || os.userInfo().username || 'member').trim();
  return `collab/${sanitizeBranchSegment(rawOwner)}/${formatCollabTimestamp()}`;
}

function normalizeCollabBranchName(branchName: string) {
  const trimmed = branchName.trim();
  if (!trimmed) throw new Error('缺少协作分支名。');
  if (!/^collab\/[a-z0-9._-]+\/[a-z0-9._/-]+$/i.test(trimmed) || trimmed.includes('..') || trimmed.endsWith('/')) {
    throw new Error(`协作分支名不安全：${trimmed}`);
  }
  return trimmed;
}

async function getRemoteCollabBranches(context: RepoWorkContext): Promise<CollabRemoteBranch[]> {
  const separator = '\x1f';
  const result = await runGit(
    context.gitRepoPath,
    [
      'for-each-ref',
      '--sort=-committerdate',
      `--format=%(refname:short)${separator}%(objectname)${separator}%(objectname:short)${separator}%(committerdate:iso-strict)${separator}%(subject)`,
      'refs/remotes/origin/collab/',
    ],
    { allowNonZero: true },
  );
  const branches = result.stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [ref = '', hash = '', shortHash = '', authoredAt = '', ...subjectParts] = line.split('\x1f');
      const branchName = ref.replace(/^origin\//, '');
      return {
        ref,
        branchName,
        shortName: branchName.replace(/^collab\//, ''),
        hash,
        shortHash,
        subject: subjectParts.join('\x1f').trim(),
        authoredAt,
        authorName: '',
        authorEmail: '',
      };
    })
    .filter((branch) => branch.ref && branch.hash);

  const output: CollabRemoteBranch[] = [];
  for (const branch of branches) {
    const authorResult = await runGit(
      context.gitRepoPath,
      ['show', '-s', '--format=%an%x1f%ae', branch.hash],
      { allowNonZero: true },
    );
    const [authorName = '', authorEmail = ''] = authorResult.stdout.trim().split('\x1f');
    const diffResult = await runGit(
      context.gitRepoPath,
      ['diff', '--name-only', '--find-renames=50%', 'origin/main...', branch.ref],
      { allowNonZero: true },
    );
    const changedPaths = diffResult.stdout
      .split(/\r?\n/)
      .map((line) => mapRepoPathToScope(line.trim(), context.scopeRelativePath))
      .filter((repoPath): repoPath is string => Boolean(repoPath));
    output.push({
      ...branch,
      authorName,
      authorEmail,
      changedPaths,
      fileCount: changedPaths.length,
    });
  }
  return output;
}

function normalizeSelectedPaths(
  selectedPaths: string[],
  allFiles: CollabFileChange[],
  options: { allowSharedSettings?: boolean; allowRemoteGeneratedDeletion?: boolean } = {},
) {
  const allowedPaths = new Set(allFiles.map((file) => file.path));
  const fileByPath = new Map(allFiles.map((file) => [file.path, file]));
  const normalizedSelectedPaths = Array.from(new Set(selectedPaths.map((item) => item.trim()).filter(Boolean)));
  for (const targetPath of normalizedSelectedPaths) {
    const allowedSharedSettings = options.allowSharedSettings === true && isSharedSettingsRepoPath(targetPath);
    const selectedFile = fileByPath.get(targetPath);
    const allowedRemoteGeneratedDeletion =
      options.allowRemoteGeneratedDeletion === true
      && selectedFile?.type === 'deleted'
      && isIgnorableLocalStatusPath(targetPath);
    if (!allowedSharedSettings && !allowedRemoteGeneratedDeletion && isIgnorableLocalStatusPath(targetPath)) {
      throw new Error(`已勾选的文件属于生成物或忽略路径，不能从协作同步提交：${targetPath}`);
    }
    if (!allowedPaths.has(targetPath)) {
      throw new Error(`已勾选的文件不在当前预览列表中：${targetPath}`);
    }
  }
  return normalizedSelectedPaths;
}

function collectStatusEntryPaths(entry: ParsedStatusEntry) {
  const paths = [entry.path];
  if (entry.previousPath && entry.previousPath !== entry.path) {
    paths.push(entry.previousPath);
  }
  return paths;
}

async function discardLocalPath(context: RepoWorkContext, file: CollabFileChange) {
  const targetPath = path.join(context.repoPath, file.path);
  if (file.type === 'untracked' || file.type === 'added') {
    await removePathsFromIndex(context, [file.path]);
    await fs.promises.rm(targetPath, { force: true, recursive: true }).catch(() => {
      // Untracked files may already be gone; ignore.
    });
    return;
  }
  if (file.type === 'renamed') {
    await removePathsFromIndex(context, [file.path]);
    await fs.promises.rm(targetPath, { force: true, recursive: true }).catch(() => {
      // Renamed targets may already be gone; ignore.
    });
    if (file.previousPath) {
      await checkoutPathFromRevision(context, 'HEAD', file.previousPath);
    }
    return;
  }
  await checkoutPathFromRevision(context, 'HEAD', file.path);
}

async function discardParsedStatusEntry(context: RepoWorkContext, entry: ParsedStatusEntry) {
  await discardLocalPath(context, {
    path: entry.path,
    previousPath: entry.previousPath || null,
    type: entry.type,
    groupKey: classifyChangeGroup(entry.path).key,
    groupLabel: classifyChangeGroup(entry.path).label,
    summary: formatChangeSummary(entry.type, entry.previousPath),
    risk: null,
  });
}

async function pushPartialStash(context: RepoWorkContext, targetPaths: string[], label: string) {
  if (!targetPaths.length) return false;
  const gitTargetPaths = targetPaths.map((targetPath) => toScopedGitPath(context.scopeRelativePath, targetPath));
  const before = await runGit(context.gitRepoPath, ['stash', 'list'], { allowNonZero: true });
  await runGit(context.gitRepoPath, ['stash', 'push', '-u', '-m', label, '--', ...gitTargetPaths], { allowNonZero: true });
  const after = await runGit(context.gitRepoPath, ['stash', 'list'], { allowNonZero: true });
  return before.stdout !== after.stdout;
}

// P1-2: stash pop 失败旧版被 caller `.catch(() => {})` 静默吞掉.
// stash pop 在 stash 与新 checkout 内容冲突时会失败, 此时 stash 条目仍在栈中
// 但工作区未恢复 - 用户看到"同步成功",实际未选中的本地改动被 stash 锁住永远找不回.
// 改为返回 {ok, stderr} 让 caller 能识别并提示用户手动恢复.
type StashPopResult = { ok: boolean; stderr: string };
async function popLatestStash(context: RepoWorkContext): Promise<StashPopResult> {
  const result = await runGit(context.gitRepoPath, ['stash', 'pop'], { allowNonZero: true });
  if (result.exitCode !== 0) {
    return { ok: false, stderr: (result.stderr || '').trim().slice(0, 500) };
  }
  return { ok: true, stderr: '' };
}

async function addPathsToIndex(context: RepoWorkContext, targetPaths: string[]) {
  const blockedLocalPaths = targetPaths.filter((targetPath) => isIgnorableLocalStatusPath(targetPath) && !isSharedSettingsRepoPath(targetPath));
  if (blockedLocalPaths.length > 0) {
    throw new Error(`协作同步不允许提交生成物或忽略路径：${blockedLocalPaths.join('、')}`);
  }
  const gitTargetPaths = targetPaths.map((targetPath) => toScopedGitPath(context.scopeRelativePath, targetPath));
  const ignoredGitPaths = await getGitIgnoredPathSet(context.gitRepoPath, gitTargetPaths);
  const ignoredLocalPaths = targetPaths.filter((targetPath) => ignoredGitPaths.has(toScopedGitPath(context.scopeRelativePath, targetPath)));
  if (ignoredLocalPaths.length > 0) {
    throw new Error(`协作同步不允许提交 .gitignore 已忽略的路径：${ignoredLocalPaths.join('、')}`);
  }
  await runGit(context.gitRepoPath, ['add', '--sparse', '-A', '--', ...gitTargetPaths]);
}

async function removePathsFromIndex(context: RepoWorkContext, targetPaths: string[]) {
  const gitTargetPaths = targetPaths.map((targetPath) => toScopedGitPath(context.scopeRelativePath, targetPath));
  await runGit(context.gitRepoPath, ['rm', '--sparse', '-f', '--ignore-unmatch', '--', ...gitTargetPaths], { allowNonZero: true });
}

async function checkoutPathFromRevision(context: RepoWorkContext, revision: 'HEAD' | 'origin/main', targetPath: string) {
  await runGit(context.gitRepoPath, ['checkout', '--ignore-skip-worktree-bits', revision, '--', toScopedGitPath(context.scopeRelativePath, targetPath)], { allowNonZero: true });
}

async function checkoutOursPath(context: RepoWorkContext, targetPath: string) {
  await runGit(context.gitRepoPath, ['checkout', '--ignore-skip-worktree-bits', '--ours', '--', toScopedGitPath(context.scopeRelativePath, targetPath)], { allowNonZero: true });
}

function uniquePaths(paths: string[]) {
  return Array.from(new Set(paths.map((item) => normalizeRelativePath(item)).filter(Boolean)));
}

function collectPreviewPaths(files: CollabFileChange[]) {
  return uniquePaths(files.flatMap((file) => {
    const paths = [file.path];
    if (file.previousPath && file.previousPath !== file.path) paths.push(file.previousPath);
    return paths;
  }));
}

async function hasStagedChanges(context: RepoWorkContext) {
  const result = await runGit(context.gitRepoPath, ['diff', '--cached', '--quiet'], { allowNonZero: true });
  return result.exitCode !== 0;
}

async function addAllPreviewFilesToIndex(context: RepoWorkContext, files: CollabFileChange[]) {
  const paths = collectPreviewPaths(files);
  if (!paths.length) return [];
  await addPathsToIndex(context, paths);
  return paths;
}

async function commitStagedChangesIfAny(context: RepoWorkContext, message: string) {
  if (!(await hasStagedChanges(context))) return false;
  await runGit(context.gitRepoPath, ['commit', '-m', message]);
  return true;
}

async function ensureNoConflictMarkers(context: RepoWorkContext) {
  const changed = await runGit(context.gitRepoPath, ['diff', '--cached', '--name-only'], { allowNonZero: true });
  const paths = uniquePaths(
    changed.stdout
      .split(/\r?\n/)
      .map((line) => stripScopePrefix(line.trim(), context.scopeRelativePath))
      .filter((line): line is string => Boolean(line)),
  );
  const markedPaths: string[] = [];
  for (const targetPath of paths) {
    if (hasBinaryExtension(targetPath)) continue;
    const raw = await fs.promises.readFile(path.join(context.repoPath, targetPath), 'utf8').catch(() => null);
    if (!raw) continue;
    if (/^<<<<<<< |^=======$|^>>>>>>> /m.test(raw)) {
      markedPaths.push(targetPath);
    }
  }
  if (markedPaths.length > 0) {
    throw new Error(`仍有冲突标记未清理：${markedPaths.join('、')}`);
  }
}

export async function getCollabRepoStatus(options: RepoOptions): Promise<CollabRepoStatus> {
  const snapshot = await collectRepoSnapshot(options);
  return snapshotToStatus(snapshot);
}

export async function previewPushToMain(options: RepoOptions): Promise<PushPreview> {
  const snapshot = await collectRepoSnapshot({
    ...options,
    fetchRemote: true,
  });
  const status = snapshotToStatus(snapshot);
  const files = createLocalFileChanges(snapshot);
  const groups = countGroups(files);
  const fallbackEffects = await buildEffectPreviews('push', snapshot, files);
  const initialSuggestedMessage = buildSuggestedMessage('push', groups);
  const effects = await explainEffectPreviews('push', snapshot, groups, files, fallbackEffects, initialSuggestedMessage, {
    effectExplainer: options.effectExplainer,
  });
  const suggestedMessage = buildFunctionalSuggestedMessage('push', groups, effects);
  const context = snapshot.repoPath && snapshot.gitRepoPath
    ? createRepoWorkContext(snapshot.repoPath, snapshot.gitRepoPath, snapshot.scopeRelativePath)
    : null;
  const suggestedBranchName = context ? await suggestedCollabBranchName(context) : null;
  let executionBlockReason: string | null = null;
  const notices: string[] = [];
  if (!snapshot.isConfigured) executionBlockReason = '还没有绑定源码目录，先选一个 Git 仓库后再继续。';
  else if (!snapshot.isValid) executionBlockReason = '当前目录不是有效 Git 仓库，请重新绑定源码目录。';
  else if (!snapshot.isMainBranch) executionBlockReason = '当前不在 main 分支，先切回 main 再继续。';
  else if (snapshot.hasUnmergedPaths) executionBlockReason = '检测到 Git 冲突，先手工收口后再执行。';
  // P1-1: fetch origin 失败时阻断 push,防止用过期 origin/main 算 behindCount=0 强推覆盖远端
  else if (snapshot.fetchFailed) executionBlockReason = `无法连上 origin (${snapshot.fetchErrorMessage || 'fetch failed'}),先确认 GitHub 网络/凭据再推送。`;
  else if (!files.length && snapshot.aheadCount === 0) executionBlockReason = snapshot.behindCount > 0
    ? '本地没有要推送的修改，但远端 main 有新提交；请使用同步按钮合并到本机。'
    : '当前没有可提交的本地文件改动。';
  if (!executionBlockReason && snapshot.aheadCount > 0) {
    notices.push(`你本地还有 ${snapshot.aheadCount} 个已提交但未推送的 commit。确认后会和本次本地改动一起推送到 GitHub main。`);
  }
  if (!executionBlockReason && snapshot.behindCount > 0) {
    notices.push(`main 最新版本比你本地多 ${snapshot.behindCount} 个提交。确认后会先尝试自动 rebase 到最新 main；成功后推送 main，失败则不改远端 main，并提示改用预览/协作分支兜底。`);
  }
  return {
    status,
    suggestedMessage,
    effects,
    groups,
    files,
    suggestedCollabBranchName: suggestedBranchName,
    notice: notices.join(' '),
    executionBlockReason,
  };
}

export async function pushSafelyToMain(
  payload: PushMainPayload,
  suggestedCandidates: string[],
  appDbPath?: string | null,
): Promise<CollabActionResult> {
  const preview = await previewPushToMain({
    repoPath: payload.repoPath,
    suggestedCandidates,
    appDbPath,
  });
  if (!preview.status.repoPath) {
    throw new Error('请先绑定源码目录。');
  }
  if (preview.executionBlockReason) {
    throw new Error(preview.executionBlockReason);
  }
  const message = payload.message.trim();
  if (!message && preview.files.length > 0) {
    throw new Error('请填写本次提交说明。');
  }
  const repoPath = preview.status.repoPath;
  const gitRepoPath = preview.status.workingRepoPath || repoPath;
  const scopeRelativePath = computeScopeRelativePath(gitRepoPath, repoPath);
  const context = createRepoWorkContext(repoPath, gitRepoPath, scopeRelativePath);
  const changedPaths = collectPreviewPaths(preview.files);
  const fallbackBranchName = preview.suggestedCollabBranchName || await suggestedCollabBranchName(context);
  let createdCommit = false;

  try {
    if (preview.files.length > 0) {
      await addAllPreviewFilesToIndex(context, preview.files);
      createdCommit = await commitStagedChangesIfAny(context, message);
    }
    await ensureNoConflictMarkers(context);

    const fetchResult = await runGit(context.gitRepoPath, ['fetch', 'origin'], { allowNonZero: true });
    if (fetchResult.exitCode !== 0) {
      throw new Error((fetchResult.stderr || fetchResult.stdout || 'git fetch origin 失败').trim());
    }

    const rebaseResult = await runGit(context.gitRepoPath, ['rebase', 'origin/main'], { allowNonZero: true });
    if (rebaseResult.exitCode !== 0) {
      await runGit(context.gitRepoPath, ['rebase', '--abort'], { allowNonZero: true });
      const detail = (rebaseResult.stderr || rebaseResult.stdout || 'git rebase origin/main 失败').trim();
      throw new Error(`${detail}。main 没有被推送；可先用同步预览查看远端变化，或发布协作分支 ${fallbackBranchName} 作为备份后交给 Codex/Claude 收口。`);
    }

    await ensureNoConflictMarkers(context);
    await runGit(context.gitRepoPath, ['-c', 'http.version=HTTP/1.1', 'push', 'origin', 'HEAD:main']);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`安全推送 main 失败：${detail}`);
  }

  const status = await getCollabRepoStatus({
    repoPath,
    suggestedCandidates,
    appDbPath,
  });
  return {
    status,
    changedPaths,
    createdCommit,
    commitMessage: createdCommit ? message : undefined,
    mergeStatus: 'pushed',
    explanation: '已安全推送到 GitHub main。后续对方同步/拉取 main 即可看到这次修改。',
  };
}

export async function publishCollabBranch(
  payload: PublishCollabBranchPayload,
  suggestedCandidates: string[],
  appDbPath?: string | null,
): Promise<CollabActionResult> {
  const preview = await previewPushToMain({
    repoPath: payload.repoPath,
    suggestedCandidates,
    appDbPath,
  });
  if (!preview.status.repoPath) {
    throw new Error('请先绑定源码目录。');
  }
  if (preview.executionBlockReason) {
    throw new Error(preview.executionBlockReason);
  }
  const message = payload.message.trim();
  if (!message && preview.files.length > 0) {
    throw new Error('请填写本次提交说明。');
  }
  const repoPath = preview.status.repoPath;
  const gitRepoPath = preview.status.workingRepoPath || repoPath;
  const scopeRelativePath = computeScopeRelativePath(gitRepoPath, repoPath);
  const context = createRepoWorkContext(repoPath, gitRepoPath, scopeRelativePath);
  const changedPaths = collectPreviewPaths(preview.files);
  const branchName = normalizeCollabBranchName(payload.branchName || preview.suggestedCollabBranchName || await suggestedCollabBranchName(context));
  let createdCommit = false;
  try {
    if (preview.files.length > 0) {
      await addAllPreviewFilesToIndex(context, preview.files);
      createdCommit = await commitStagedChangesIfAny(context, message);
    }
    await ensureNoConflictMarkers(context);
    await runGit(context.gitRepoPath, ['push', 'origin', `HEAD:refs/heads/${branchName}`]);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`发布协作分支失败：${detail}`);
  }
  const status = await getCollabRepoStatus({
    repoPath,
    suggestedCandidates,
    appDbPath,
  });
  return {
    status,
    changedPaths,
    createdCommit,
    commitMessage: createdCommit ? message : undefined,
    mergeStatus: 'collabBranchPublished',
    collabBranchName: branchName,
    collabBranchRef: `origin/${branchName}`,
    explanation: `已发布到协作分支 ${branchName}。GitHub main 未改变。`,
  };
}

export async function previewPullFromMain(options: RepoOptions): Promise<PullPreview> {
  const snapshot = await collectRepoSnapshot({
    ...options,
    fetchRemote: true,
  });
  const status = snapshotToStatus(snapshot);
  const files = createRemoteFileChanges(snapshot);
  const groups = countGroups(files);
  let executionBlockReason: string | null = null;
  let notice: string | null = null;
  if (!snapshot.isConfigured) executionBlockReason = '还没有绑定源码目录，先选一个 Git 仓库后再继续。';
  else if (!snapshot.isValid) executionBlockReason = '当前目录不是有效 Git 仓库，请重新绑定源码目录。';
  else if (!snapshot.isMainBranch) executionBlockReason = '当前不在 main 分支，先切回 main 再继续。';
  else if (snapshot.hasUnmergedPaths) executionBlockReason = '检测到 Git 冲突，先手工收口后再执行。';
  else if (!files.length) executionBlockReason = 'main 当前已经是最新。';
  const generatedCleanupCount = files.filter((file) => file.type === 'deleted' && isIgnorableLocalStatusPath(file.path)).length;
  const context = snapshot.repoPath && snapshot.gitRepoPath
    ? createRepoWorkContext(snapshot.repoPath, snapshot.gitRepoPath, snapshot.scopeRelativePath)
    : null;
  const remoteCommits = context ? await getRemoteCommits(context) : [];
  const remoteBranches = context ? await getRemoteCollabBranches(context) : [];
  const selectedCommit = remoteCommits.find((commit) => commit.hash === snapshot.remoteTargetRevision);
  const syncTargetLabel = selectedCommit
    ? `${selectedCommit.shortHash} · ${selectedCommit.authoredAt.slice(0, 10)} ${selectedCommit.authoredAt.slice(11, 16)} · ${selectedCommit.subject}`
    : snapshot.remoteTargetRevision === 'origin/main'
      ? 'origin/main 最新提交'
      : snapshot.remoteTargetRevision;
  const directReceiveBlockReason = (() => {
    if (executionBlockReason) return executionBlockReason;
    if (snapshot.remoteTargetRevision !== 'origin/main') return '按日期截断的同步范围只用于预览，不能直接接收。';
    if (snapshot.localChangeCount > 0) return `本地还有 ${snapshot.localChangeCount} 项未提交改动，不能自动接收 main。`;
    if (snapshot.aheadCount > 0) return `本地已有 ${snapshot.aheadCount} 个未推提交，不能自动接收 main。`;
    if (snapshot.behindCount <= 0) return 'main 当前已经是最新。';
    return null;
  })();
  const canFastForwardMain = !directReceiveBlockReason;
  if (!executionBlockReason && snapshot.remoteChangeCount > 0) {
    notice = snapshot.localChangeCount > 0
      ? `当前同步截止点是 ${syncTargetLabel}，包含 ${snapshot.remoteChangeCount} 项可查看变化。你本地还有 ${snapshot.localChangeCount} 项未提交改动，本次不会自动合并。`
      : `当前同步截止点是 ${syncTargetLabel}，包含 ${snapshot.remoteChangeCount} 项可查看变化。只有安全快进场景才允许直接接收。`;
    if (generatedCleanupCount > 0) {
      notice += ` 其中 ${generatedCleanupCount} 项是 main 对历史生成物或数据库文件的清理，保留勾选即可让本地也清掉这些旧文件，不代表要把 4 月 27 日前的代码带回来。`;
    }
  }
  const commitSummaries = remoteCommits.map((commit) => (
    `${commit.shortHash} ${commit.authoredAt.slice(0, 10)} ${commit.authoredAt.slice(11, 16)} ${commit.subject}`
  ));
  const fallbackEffects = await buildEffectPreviews('pull', snapshot, files);
  const initialSuggestedMessage = buildSuggestedMessage('pull', groups);
  const effects = await explainEffectPreviews('pull', snapshot, groups, files, fallbackEffects, initialSuggestedMessage, {
    effectExplainer: options.effectExplainer,
    commitSummaries,
    syncTargetLabel,
  });
  const suggestedMessage = buildFunctionalSuggestedMessage('pull', groups, effects);
  return {
    status,
    suggestedMessage,
    commitSummaries,
    remoteCommits,
    remoteBranches,
    syncTargetCommit: snapshot.remoteTargetRevision === 'origin/main' ? null : snapshot.remoteTargetRevision,
    syncTargetLabel,
    canFastForwardMain,
    directReceiveBlockReason,
    effects,
    groups,
    files,
    notice,
    executionBlockReason,
  };
}

async function resolvePullChoice(context: RepoWorkContext, file: CollabFileChange, takeRemote: boolean) {
  if (takeRemote) {
    if (file.type === 'deleted') {
      await removePathsFromIndex(context, [file.path]);
      return;
    }
    await checkoutPathFromRevision(context, 'origin/main', file.path);
    if (file.type === 'renamed' && file.previousPath && file.previousPath !== file.path) {
      await removePathsFromIndex(context, [file.previousPath]);
    }
    return;
  }

  if (file.type === 'added') {
    await removePathsFromIndex(context, [file.path]);
    return;
  }
  if (file.type === 'renamed') {
    await removePathsFromIndex(context, [file.path]);
    if (file.previousPath) {
      await checkoutPathFromRevision(context, 'HEAD', file.previousPath);
    }
    return;
  }
  await checkoutPathFromRevision(context, 'HEAD', file.path);
}

export async function fastForwardMain(
  payload: FastForwardMainPayload,
  suggestedCandidates: string[],
  appDbPath?: string | null,
): Promise<CollabActionResult> {
  const preview = await previewPullFromMain({
    repoPath: payload.repoPath,
    suggestedCandidates,
    appDbPath,
  });
  if (!preview.status.repoPath) {
    throw new Error('请先绑定源码目录。');
  }
  if (preview.executionBlockReason) {
    throw new Error(preview.executionBlockReason);
  }
  if (!preview.canFastForwardMain) {
    throw new Error(preview.directReceiveBlockReason || '当前 main 不能安全快进接收。');
  }
  const repoPath = preview.status.repoPath;
  const gitRepoPath = preview.status.workingRepoPath || repoPath;
  const scopeRelativePath = computeScopeRelativePath(gitRepoPath, repoPath);
  const context = createRepoWorkContext(repoPath, gitRepoPath, scopeRelativePath);
  try {
    await runGit(context.gitRepoPath, ['merge', '--ff-only', 'origin/main']);
    await importSelectedSharedSettingsFromRepo(context.repoPath, appDbPath, collectPreviewPaths(preview.files));
    await ensureNoConflictMarkers(context);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`快进接收 main 失败：${detail}`);
  }

  const status = await getCollabRepoStatus({
    repoPath,
    suggestedCandidates,
    appDbPath,
  });
  return {
    status,
    changedPaths: collectPreviewPaths(preview.files),
    createdCommit: false,
    mergeStatus: 'mainFastForwarded',
    explanation: '远端 main 已通过快进方式接收到本机源码。',
  };
}

function normalizePreviewTargetRef(targetRef: string) {
  const trimmed = targetRef.trim();
  if (trimmed === 'origin/main') return trimmed;
  if (/^origin\/collab\/[a-z0-9._/-]+$/i.test(trimmed) && !trimmed.includes('..') && !trimmed.endsWith('/')) return trimmed;
  if (/^[0-9a-f]{7,40}$/i.test(trimmed)) return trimmed;
  throw new Error(`不能预览不受控的 Git 目标：${trimmed || '(empty)'}`);
}

async function resolvePreviewTarget(context: RepoWorkContext, targetRef: string) {
  const normalized = normalizePreviewTargetRef(targetRef);
  const result = await runGit(context.gitRepoPath, ['rev-parse', '--verify', `${normalized}^{commit}`], { allowNonZero: true });
  if (result.exitCode !== 0 || !result.stdout.trim()) {
    throw new Error(`找不到要预览的 Git 目标：${normalized}`);
  }
  return { targetRef: normalized, revision: result.stdout.trim() };
}

function safeSymlink(sourcePath: string, targetPath: string) {
  if (!fs.existsSync(sourcePath) || fs.existsSync(targetPath)) return;
  fs.symlinkSync(sourcePath, targetPath, 'dir');
}

export async function startCollabPreview(
  payload: StartCollabPreviewPayload,
  suggestedCandidates: string[],
  appDbPath: string | null | undefined,
  previewRoot: string,
): Promise<CollabActionResult> {
  const snapshot = await collectRepoSnapshot({
    repoPath: payload.repoPath,
    suggestedCandidates,
    appDbPath,
    fetchRemote: true,
  });
  if (!snapshot.repoPath || !snapshot.gitRepoPath) throw new Error('请先绑定源码目录。');
  if (!snapshot.isValid) throw new Error('当前目录不是有效 Git 仓库，请重新绑定源码目录。');
  const context = createRepoWorkContext(snapshot.repoPath, snapshot.gitRepoPath, snapshot.scopeRelativePath);
  const target = await resolvePreviewTarget(context, payload.targetRef);
  const previewId = `${formatCollabTimestamp()}-${Math.random().toString(16).slice(2, 8)}`;
  const sessionRoot = path.join(previewRoot, previewId);
  const repoDir = path.join(sessionRoot, 'repo');
  const dataDir = path.join(sessionRoot, 'data');
  const logPath = path.join(sessionRoot, 'preview.log');
  fs.mkdirSync(sessionRoot, { recursive: true });
  fs.mkdirSync(dataDir, { recursive: true });
  await runGit(context.gitRepoPath, ['worktree', 'add', '--detach', repoDir, target.revision]);
  safeSymlink(path.join(context.gitRepoPath, 'node_modules'), path.join(repoDir, 'node_modules'));
  if (appDbPath && fs.existsSync(appDbPath)) {
    fs.copyFileSync(appDbPath, path.join(dataDir, 'app.db'));
  }
  const logStream = fs.createWriteStream(logPath, { flags: 'a' });
  const child = spawn('npm', ['run', 'dev:lab'], {
    cwd: repoDir,
    detached: true,
    stdio: ['ignore', logStream, logStream],
    env: {
      ...process.env,
      YIYU_COLLAB_PREVIEW_MODE: '1',
      YIYU_COLLAB_PREVIEW_ID: previewId,
      YIYU_COLLAB_PREVIEW_TARGET: target.targetRef,
      YIYU_WORKBENCH_DATA_DIR: dataDir,
      VITE_NO_HMR: '1',
    },
  });
  child.unref();
  const session: CollabPreviewSession = {
    previewId,
    targetRef: target.targetRef,
    label: payload.label || target.targetRef,
    repoPath: repoDir,
    dataDir,
    logPath,
    pid: child.pid || null,
  };
  if (child.pid) activePreviewSessions.set(previewId, { pid: child.pid, session });
  const status = snapshotToStatus(snapshot);
  return {
    status,
    changedPaths: [],
    createdCommit: false,
    mergeStatus: 'previewStarted',
    previewSession: session,
    explanation: `已开启协作预览：${session.label}。正式源码和正式数据未改变。`,
  };
}

export async function stopCollabPreview(
  payload: StopCollabPreviewPayload,
  suggestedCandidates: string[],
): Promise<CollabActionResult> {
  const record = activePreviewSessions.get(payload.previewId);
  if (!record) {
    throw new Error('找不到正在运行的协作预览进程，可能已经关闭。');
  }
  try {
    process.kill(-record.pid, 'SIGTERM');
  } catch {
    try {
      process.kill(record.pid, 'SIGTERM');
    } catch {
      // Process may already be gone.
    }
  }
  activePreviewSessions.delete(payload.previewId);
  const status = await getCollabRepoStatus({
    repoPath: record.session.repoPath,
    suggestedCandidates,
    fetchRemote: false,
  });
  return {
    status,
    changedPaths: [],
    createdCommit: false,
    mergeStatus: 'previewStopped',
    previewSession: record.session,
    explanation: '协作预览进程已停止。',
  };
}
