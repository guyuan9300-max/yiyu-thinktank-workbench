import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';

export const APP_NAME = '益语智库自用平台 V2.0.app';
export const APP_DISPLAY_NAME = '益语智库自用平台 V2.0';
export const DEFAULT_PACKAGED_REMOTE_CLOUD_API_URL = 'http://101.126.34.232';
export const VERSION_MANIFEST_RELATIVE_PATH = path.join('dist', 'version-manifest.json');
export const BANNED_RENDERER_COPY = [
  '已基于命中的资料生成简版可用回答',
  '完整长文扩写未完成',
  '根据当前已入库资料',
  '可以先这样介绍',
  '正式长回答未完成',
];
export const REQUIRED_BACKEND_CAPABILITY_SYMBOLS = [
  'consultant_synthesis',
  'workspace_rule_consultant_synthesis',
  'build_consultant_synthesis_material_pack',
];
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

const HASH_EXTENSIONS = new Set(['.py', '.toml', '.json', '.yaml', '.yml', '.lock']);

function stableSerialize(value) {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableSerialize(item)).join(',')}]`;
  }
  if (value && typeof value === 'object') {
    return `{${Object.entries(value)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${stableSerialize(item)}`)
      .join(',')}}`;
  }
  return JSON.stringify(value);
}

function sha256Buffer(buffer) {
  return createHash('sha256').update(buffer).digest('hex');
}

export function computeManifestId(manifest) {
  return sha256Buffer(Buffer.from(stableSerialize(manifest), 'utf8'));
}

export function readJsonFile(targetPath) {
  return JSON.parse(fs.readFileSync(targetPath, 'utf8'));
}

export function writeJsonFile(targetPath, payload) {
  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
  fs.writeFileSync(targetPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

export function pickRendererEntry(assetDir) {
  if (!fs.existsSync(assetDir)) {
    return null;
  }
  const entries = fs.readdirSync(assetDir)
    .filter((name) => /^(main|index)-.*\.js$/.test(name))
    .sort();
  return entries.find((name) => name.startsWith('main-')) || entries[0] || null;
}

export function resolveProjectManifestPath(projectRoot) {
  return path.join(projectRoot, VERSION_MANIFEST_RELATIVE_PATH);
}

export function resolveAppManifestPath(appPath) {
  return path.join(path.resolve(appPath), 'Contents', 'Resources', 'app', VERSION_MANIFEST_RELATIVE_PATH);
}

export function readProjectManifest(projectRoot) {
  const manifestPath = resolveProjectManifestPath(projectRoot);
  if (!fs.existsSync(manifestPath)) {
    return null;
  }
  return readJsonFile(manifestPath);
}

export function readAppManifest(appPath) {
  const manifestPath = resolveAppManifestPath(appPath);
  if (!fs.existsSync(manifestPath)) {
    return null;
  }
  return readJsonFile(manifestPath);
}

export function sha256File(targetPath) {
  return sha256Buffer(fs.readFileSync(targetPath));
}

export function computeBackendSourceHash(rootPath) {
  const resolvedRoot = path.resolve(rootPath);
  if (!fs.existsSync(resolvedRoot)) {
    return 'missing';
  }
  const digest = createHash('sha256');
  const files = [];
  const visit = (entryPath) => {
    const stat = fs.lstatSync(entryPath);
    if (stat.isSymbolicLink()) {
      return;
    }
    if (stat.isDirectory()) {
      if (path.basename(entryPath) === '__pycache__') {
        return;
      }
      for (const child of fs.readdirSync(entryPath)) {
        visit(path.join(entryPath, child));
      }
      return;
    }
    if (HASH_EXTENSIONS.has(path.extname(entryPath).toLowerCase())) {
      files.push(entryPath);
    }
  };
  visit(resolvedRoot);
  files.sort();
  if (files.length === 0) {
    return 'empty';
  }
  for (const filePath of files) {
    const rel = path.relative(resolvedRoot, filePath);
    digest.update(rel);
    digest.update('\n');
    digest.update(fs.readFileSync(filePath));
    digest.update('\n');
  }
  return digest.digest('hex');
}

function parseSchemaVersion(projectRoot) {
  const dbPath = path.join(projectRoot, 'backend', 'app', 'db.py');
  const text = fs.readFileSync(dbPath, 'utf8');
  const match = text.match(/BACKEND_SCHEMA_VERSION\s*=\s*(\d+)/);
  if (!match) {
    throw new Error(`unable to parse BACKEND_SCHEMA_VERSION from ${dbPath}`);
  }
  return Number(match[1]);
}

function gitCommit(projectRoot) {
  const envCommit = String(process.env.YIYU_GIT_COMMIT || '').trim();
  if (envCommit) {
    return envCommit;
  }
  const result = spawnSync('git', ['-C', projectRoot, 'rev-parse', '--short=12', 'HEAD'], {
    encoding: 'utf8',
    stdio: 'pipe',
  });
  if (result.status === 0) {
    return (result.stdout || '').trim() || null;
  }
  return null;
}

function formatBuildVersion(timestamp, commit) {
  const year = timestamp.getFullYear();
  const month = String(timestamp.getMonth() + 1).padStart(2, '0');
  const day = String(timestamp.getDate()).padStart(2, '0');
  const hour = String(timestamp.getHours()).padStart(2, '0');
  const minute = String(timestamp.getMinutes()).padStart(2, '0');
  const second = String(timestamp.getSeconds()).padStart(2, '0');
  const suffix = commit ? `-${String(commit).slice(0, 12)}` : '';
  return `${year}.${month}.${day}-${hour}${minute}${second}${suffix}`;
}

export function buildVersionManifest(projectRoot) {
  const packageJson = readJsonFile(path.join(projectRoot, 'package.json'));
  const assetDir = path.join(projectRoot, 'dist', 'renderer', 'assets');
  const rendererEntry = pickRendererEntry(assetDir);
  if (!rendererEntry) {
    throw new Error(`renderer entry not found under ${assetDir}`);
  }
  const rendererPath = path.join(assetDir, rendererEntry);
  const builtAt = new Date().toISOString();
  const commit = gitCommit(projectRoot);
  return {
    appVersion: String(packageJson.version || '').trim() || '0.0.0',
    buildVersion: formatBuildVersion(new Date(builtAt), commit),
    gitCommit: commit,
    builtAt,
    rendererEntry,
    rendererHash: sha256File(rendererPath),
    backendSourceHash: computeBackendSourceHash(path.join(projectRoot, 'backend')),
    schemaVersionMin: parseSchemaVersion(projectRoot),
  };
}

export function inspectAppBundle(appPath) {
  const resolvedPath = path.resolve(appPath);
  const exists = fs.existsSync(resolvedPath);
  const manifest = exists ? readAppManifest(resolvedPath) : null;
  const rendererPath = manifest?.rendererEntry
    ? path.join(
      resolvedPath,
      'Contents',
      'Resources',
      'app',
      'dist',
      'renderer',
      'assets',
      manifest.rendererEntry,
    )
    : null;
  return {
    path: resolvedPath,
    exists,
    modifiedAt: exists ? new Date(fs.statSync(resolvedPath).mtimeMs).toISOString() : null,
    manifest,
    bundleManifestId: manifest ? computeManifestId(manifest) : null,
    rendererEntry: manifest?.rendererEntry || null,
    rendererHash: rendererPath && fs.existsSync(rendererPath) ? sha256File(rendererPath) : null,
  };
}

function collectPythonFiles(rootPath) {
  const resolvedRoot = path.resolve(rootPath);
  const files = [];
  if (!fs.existsSync(resolvedRoot)) {
    return files;
  }
  const visit = (entryPath) => {
    const stat = fs.lstatSync(entryPath);
    if (stat.isSymbolicLink()) {
      return;
    }
    if (stat.isDirectory()) {
      if (path.basename(entryPath) === '__pycache__') {
        return;
      }
      for (const child of fs.readdirSync(entryPath)) {
        visit(path.join(entryPath, child));
      }
      return;
    }
    if (path.extname(entryPath).toLowerCase() === '.py') {
      files.push(entryPath);
    }
  };
  visit(resolvedRoot);
  files.sort();
  return files;
}

export function inspectBackendCapabilityDirectory(
  backendAppPath,
  symbols = REQUIRED_BACKEND_CAPABILITY_SYMBOLS,
) {
  const resolvedRoot = path.resolve(backendAppPath);
  const files = collectPythonFiles(resolvedRoot);
  const present = new Set();
  for (const filePath of files) {
    const text = fs.readFileSync(filePath, 'utf8');
    for (const symbol of symbols) {
      if (!present.has(symbol) && text.includes(symbol)) {
        present.add(symbol);
      }
    }
    if (present.size === symbols.length) {
      break;
    }
  }
  const presentSymbols = symbols.filter((symbol) => present.has(symbol));
  const missingSymbols = symbols.filter((symbol) => !present.has(symbol));
  return {
    rootPath: resolvedRoot,
    exists: fs.existsSync(resolvedRoot),
    scannedFileCount: files.length,
    requiredSymbols: [...symbols],
    presentSymbols,
    missingSymbols,
    match: missingSymbols.length === 0,
  };
}

export function inspectBackendCapabilities(appPath, symbols = REQUIRED_BACKEND_CAPABILITY_SYMBOLS) {
  const backendAppPath = path.join(
    path.resolve(appPath),
    'Contents',
    'Resources',
    'app',
    'backend',
    'app',
  );
  return inspectBackendCapabilityDirectory(backendAppPath, symbols);
}

export function findBannedRendererCopyViolations(appPath) {
  const manifest = readAppManifest(appPath);
  if (!manifest?.rendererEntry) {
    return ['missing rendererEntry in version-manifest.json'];
  }
  const rendererPath = path.join(
    path.resolve(appPath),
    'Contents',
    'Resources',
    'app',
    'dist',
    'renderer',
    'assets',
    manifest.rendererEntry,
  );
  if (!fs.existsSync(rendererPath)) {
    return [`missing renderer asset: ${rendererPath}`];
  }
  const text = fs.readFileSync(rendererPath, 'utf8');
  return BANNED_RENDERER_COPY.filter((phrase) => text.includes(phrase));
}

export function readEvidenceJson(targetPath) {
  if (!fs.existsSync(targetPath)) {
    return null;
  }
  try {
    return readJsonFile(targetPath);
  } catch {
    return null;
  }
}
