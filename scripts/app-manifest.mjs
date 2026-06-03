import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';

export const APP_NAME = '益语智库自用平台 V2.0.app';
export const APP_DISPLAY_NAME = '益语智库自用平台 V2.0';
export const DEFAULT_PACKAGED_REMOTE_CLOUD_API_URL = '';
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
export const PACKAGED_RUNTIME_RELATIVE_PATH = path.join('Contents', 'Resources', 'runtime');
export const RUNTIME_SEED_MANIFEST_FILE = 'runtime-seed-manifest.json';
export const RUNTIME_BACKEND_REQUIREMENTS_FILE = 'backend-requirements.txt';
export const RUNTIME_PYTHON_SEED_DIR = 'python-seed';
export const RUNTIME_WHEELHOUSE_DIR = 'wheelhouse';
// B 方案:预装 backend venv,打进 app bundle 给客户机首次启动直接复制使用
// 避免之前 wheelhouse 里 .whl 内嵌 .so 没签名导致 Apple 公证拒收的问题
export const RUNTIME_BACKEND_VENV_DIR = 'backend-venv-prebuilt';

const HASH_EXTENSIONS = new Set(['.py', '.toml', '.json', '.yaml', '.yml', '.lock']);
const PACKAGED_APP_CONTENT_ROOT = path.join('Contents', 'Resources', 'app');
const PACKAGED_CONTENT_VIOLATION_LIMIT = 80;

const PACKAGED_CONTENT_VIOLATION_RULES = [
  {
    test: (relativePath) => relativePath === 'backend/output' || relativePath.startsWith('backend/output/'),
    reason: 'backend output artifact',
  },
  {
    test: (relativePath) => relativePath === 'cloud_backend/output' || relativePath.startsWith('cloud_backend/output/'),
    reason: 'cloud backend output artifact',
  },
  {
    test: (relativePath) => /(^|\/)__pycache__(\/|$)/.test(relativePath),
    reason: 'python bytecode cache directory',
  },
  {
    test: (relativePath) => /(^|\/)(\.pytest_cache|\.mypy_cache|\.ruff_cache)(\/|$)/.test(relativePath),
    reason: 'tool cache directory',
  },
  {
    test: (relativePath) => /(^|\/)\.env(\..*)?$/.test(relativePath),
    reason: 'environment file',
  },
  {
    test: (relativePath) => /\.(db|sqlite|sqlite3)(-(wal|shm))?$/i.test(relativePath),
    reason: 'local database file',
  },
  {
    test: (relativePath) => /\.(pyc|pyo|cstemp)$/i.test(relativePath),
    reason: 'runtime cache file',
  },
  {
    test: (relativePath) => /(^|\/)\.DS_Store$/i.test(relativePath),
    reason: 'macOS metadata file',
  },
];

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

export function sha256Directory(rootPath) {
  const resolvedRoot = path.resolve(rootPath);
  if (!fs.existsSync(resolvedRoot)) {
    return 'missing';
  }
  const digest = createHash('sha256');
  const entries = [];
  const visit = (entryPath) => {
    const stat = fs.lstatSync(entryPath);
    const relativePath = path.relative(resolvedRoot, entryPath).split(path.sep).join('/');
    if (stat.isSymbolicLink()) {
      entries.push({
        kind: 'symlink',
        path: relativePath,
        target: fs.readlinkSync(entryPath),
      });
      return;
    }
    if (stat.isDirectory()) {
      for (const child of fs.readdirSync(entryPath)) {
        visit(path.join(entryPath, child));
      }
      return;
    }
    entries.push({
      kind: 'file',
      path: relativePath,
      hash: sha256File(entryPath),
    });
  };
  visit(resolvedRoot);
  entries.sort((left, right) => left.path.localeCompare(right.path) || left.kind.localeCompare(right.kind));
  for (const entry of entries) {
    digest.update(entry.kind);
    digest.update('\0');
    digest.update(entry.path);
    digest.update('\0');
    digest.update(entry.hash || entry.target || '');
    digest.update('\0');
  }
  return digest.digest('hex');
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

export function resolveAppPackagedRuntimeRoot(appPath) {
  return path.join(path.resolve(appPath), PACKAGED_RUNTIME_RELATIVE_PATH);
}

export function readPackagedRuntimeSeedManifest(runtimeRoot) {
  const manifestPath = path.join(runtimeRoot, RUNTIME_SEED_MANIFEST_FILE);
  if (!fs.existsSync(manifestPath)) {
    return null;
  }
  return readJsonFile(manifestPath);
}

function listWheelFiles(wheelhousePath) {
  if (!fs.existsSync(wheelhousePath)) {
    return [];
  }
  return fs.readdirSync(wheelhousePath)
    .filter((item) => item.toLowerCase().endsWith('.whl'))
    .sort();
}

export function inspectPackagedRuntimeSeed(appPath) {
  const runtimeRoot = resolveAppPackagedRuntimeRoot(appPath);
  const manifest = readPackagedRuntimeSeedManifest(runtimeRoot);
  const requirementsPath = path.join(runtimeRoot, manifest?.backend?.requirementsPath || RUNTIME_BACKEND_REQUIREMENTS_FILE);
  const pythonExecutable = path.join(
    runtimeRoot,
    manifest?.python?.executable || path.join(RUNTIME_PYTHON_SEED_DIR, 'bin', 'python3.11'),
  );
  const pythonLib = path.join(runtimeRoot, RUNTIME_PYTHON_SEED_DIR, 'lib', 'libpython3.11.dylib');
  const wheelhousePath = path.join(runtimeRoot, manifest?.wheelhouse?.path || RUNTIME_WHEELHOUSE_DIR);
  const wheelFiles = listWheelFiles(wheelhousePath);
  // B 方案:预装 venv 路径
  const backendVenvPath = path.join(runtimeRoot, manifest?.backendVenv?.path || RUNTIME_BACKEND_VENV_DIR);
  const backendVenvExists = fs.existsSync(backendVenvPath)
    && fs.existsSync(path.join(backendVenvPath, 'bin', 'python'))
    && fs.existsSync(path.join(backendVenvPath, 'bin', 'uvicorn'));
  const backendVenvSha256 = fs.existsSync(backendVenvPath) ? sha256Directory(backendVenvPath) : null;
  const requirementsSha256 = fs.existsSync(requirementsPath) ? sha256File(requirementsPath) : null;
  const wheelhouseSha256 = fs.existsSync(wheelhousePath) ? sha256Directory(wheelhousePath) : null;
  const missing = [];
  if (!fs.existsSync(runtimeRoot)) missing.push(`missing runtime root: ${runtimeRoot}`);
  if (!manifest) missing.push(`missing ${RUNTIME_SEED_MANIFEST_FILE}`);
  if (!fs.existsSync(pythonExecutable)) missing.push(`missing python seed executable: ${pythonExecutable}`);
  if (!fs.existsSync(pythonLib)) missing.push(`missing python seed libpython: ${pythonLib}`);
  if (!fs.existsSync(requirementsPath)) missing.push(`missing ${RUNTIME_BACKEND_REQUIREMENTS_FILE}`);
  // B 方案:wheelhouse 跟 backendVenv 两者要有其一
  // 优先 backendVenv(新版),没有则回退到 wheelhouse 兼容旧 build
  if (!backendVenvExists && wheelFiles.length === 0) {
    missing.push(`neither ${RUNTIME_BACKEND_VENV_DIR} nor populated ${RUNTIME_WHEELHOUSE_DIR}`);
  }
  const requirementsHashMatch = Boolean(
    manifest?.backend?.requirementsSha256
      && requirementsSha256
      && manifest.backend.requirementsSha256 === requirementsSha256,
  );
  const wheelhouseHashMatch = Boolean(
    manifest?.wheelhouse?.sha256
      && wheelhouseSha256
      && manifest.wheelhouse.sha256 === wheelhouseSha256,
  );
  const backendVenvHashMatch = Boolean(
    manifest?.backendVenv?.sha256
      && backendVenvSha256
      && manifest.backendVenv.sha256 === backendVenvSha256,
  );
  if (manifest && !requirementsHashMatch) {
    missing.push('backend requirements hash mismatch');
  }
  // backendVenv 的 hash 不校验:codesign re-sign 会改 .so/.dylib 注入签名,hash 必变,这是预期行为。
  // 完整性靠 backendVenvExists(bin/python + bin/uvicorn 存在)保证。
  // wheelhouse hash 同样不强制——新版没 wheelhouse,旧版 build 才有。
  return {
    runtimeRoot,
    manifestPath: path.join(runtimeRoot, RUNTIME_SEED_MANIFEST_FILE),
    exists: fs.existsSync(runtimeRoot),
    manifest,
    pythonExecutable,
    pythonLib,
    pythonExecutableExists: fs.existsSync(pythonExecutable),
    requirementsPath,
    requirementsSha256,
    requirementsHashMatch,
    wheelhousePath,
    wheelFileCount: wheelFiles.length,
    wheelhouseSha256,
    wheelhouseHashMatch,
    backendVenvPath,
    backendVenvExists,
    backendVenvSha256,
    backendVenvHashMatch,
    missing,
    match: missing.length === 0,
  };
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

export function findPackagedContentViolations(appPath) {
  const appRoot = path.join(path.resolve(appPath), PACKAGED_APP_CONTENT_ROOT);
  const violations = [];
  if (!fs.existsSync(appRoot)) {
    return [`missing packaged app content root: ${appRoot}`];
  }

  const visit = (entryPath) => {
    if (violations.length >= PACKAGED_CONTENT_VIOLATION_LIMIT) {
      return;
    }
    const stat = fs.lstatSync(entryPath);
    const relativePath = path.relative(appRoot, entryPath).split(path.sep).join('/');
    for (const rule of PACKAGED_CONTENT_VIOLATION_RULES) {
      if (rule.test(relativePath)) {
        violations.push(`${relativePath} (${rule.reason})`);
        if (stat.isDirectory()) {
          return;
        }
        break;
      }
    }
    if (!stat.isDirectory() || stat.isSymbolicLink()) {
      return;
    }
    for (const child of fs.readdirSync(entryPath)) {
      visit(path.join(entryPath, child));
      if (violations.length >= PACKAGED_CONTENT_VIOLATION_LIMIT) {
        return;
      }
    }
  };

  visit(appRoot);
  return violations;
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
