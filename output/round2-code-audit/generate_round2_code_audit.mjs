import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';

const repoRoot = '/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench';
const mobileRoot = path.join(repoRoot, 'mobile');
const outDir = path.join(repoRoot, 'output', 'round2-code-audit');

function ensureDir(target) {
  fs.mkdirSync(target, { recursive: true });
}

function read(filePath) {
  return fs.readFileSync(filePath, 'utf8');
}

function write(filePath, content) {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, content);
}

function writeJson(filePath, value) {
  write(filePath, JSON.stringify(value, null, 2));
}

function listFiles(root, predicate) {
  const results = [];
  function walk(current) {
    const entries = fs.readdirSync(current, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === 'node_modules' || entry.name === 'dist' || entry.name === 'build' || entry.name === '.git' || entry.name === '.expo') continue;
        walk(fullPath);
      } else if (!predicate || predicate(fullPath)) {
        results.push(fullPath);
      }
    }
  }
  walk(root);
  return results.sort();
}

function rel(filePath, base = repoRoot) {
  return path.relative(base, filePath).replace(/\\/g, '/');
}

function isTsLike(filePath) {
  return /\.(ts|tsx|js|jsx|mjs|cjs)$/.test(filePath);
}

function extractImports(source) {
  const deps = [];
  const patterns = [
    /\bimport\s+(?:type\s+)?[\s\S]*?from\s*['"]([^'"]+)['"]/g,
    /\bexport\s+(?:type\s+)?[\s\S]*?from\s*['"]([^'"]+)['"]/g,
    /\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
  ];
  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(source))) {
      deps.push(match[1]);
    }
  }
  return deps;
}

function resolveLocalImport(fromFile, specifier) {
  if (!specifier.startsWith('.')) return null;
  const base = path.resolve(path.dirname(fromFile), specifier);
  const candidates = [
    base,
    `${base}.ts`,
    `${base}.tsx`,
    `${base}.js`,
    `${base}.jsx`,
    `${base}.mjs`,
    path.join(base, 'index.ts'),
    path.join(base, 'index.tsx'),
    path.join(base, 'index.js'),
    path.join(base, 'index.jsx'),
    path.join(base, 'index.mjs'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return path.resolve(candidate);
  }
  return null;
}

function buildImportGraph(files) {
  const fileSet = new Set(files.map((filePath) => path.resolve(filePath)));
  const graph = new Map();
  const reverse = new Map();
  for (const filePath of fileSet) {
    const source = read(filePath);
    const deps = [];
    for (const specifier of extractImports(source)) {
      const resolved = resolveLocalImport(filePath, specifier);
      if (resolved && fileSet.has(resolved)) {
        deps.push(resolved);
        const current = reverse.get(resolved) || [];
        current.push(filePath);
        reverse.set(resolved, current);
      }
    }
    graph.set(filePath, deps);
  }
  return { graph, reverse };
}

function walkReachable(graph, roots) {
  const seen = new Set();
  const queue = [...roots];
  while (queue.length > 0) {
    const current = queue.shift();
    if (!current || seen.has(current)) continue;
    seen.add(current);
    for (const next of graph.get(current) || []) {
      if (!seen.has(next)) queue.push(next);
    }
  }
  return seen;
}

function parseUnionStrings(source, typeName) {
  const match = source.match(new RegExp(`type\\s+${typeName}\\s*=\\s*([^;]+);`, 'm'));
  if (!match) return [];
  return [...match[1].matchAll(/'([^']+)'/g)].map((item) => item[1]);
}

function parseConstStringArray(source, constName) {
  const match = source.match(new RegExp(`const\\s+${constName}\\s*:[^=]*=\\s*\\[([\\s\\S]*?)\\]`, 'm'));
  if (!match) return [];
  return [...match[1].matchAll(/'([^']+)'/g)].map((item) => item[1]);
}

function parseSectionRootMap(appSource) {
  const renderMap = {};
  const switchBlock = appSource.match(/const renderSectionContent = \(\) => \{([\s\S]*?)default:\s+return null;/m);
  if (!switchBlock) return renderMap;
  for (const match of switchBlock[1].matchAll(/case '([^']+)':\s+return(?:\s*\(|\s+)([A-Za-z0-9_]+)(?:\(|\s*<)/g)) {
    renderMap[match[1]] = match[2];
  }
  if (switchBlock[1].includes("case 'system_logs':")) {
    renderMap.system_logs = 'SystemLogPanel + DataCenterProposalInboxPanel + DataCenterOpsPanel';
  }
  return renderMap;
}

function parseNavRootMap(appSource) {
  const result = {};
  const match = appSource.match(/const viewMap:[\s\S]*?= \{([\s\S]*?)\n  \};/m);
  if (!match) return result;
  for (const item of match[1].matchAll(/\s+([a-z_]+):\s*evidenceMode === 'cockpit'[\s\S]*?<([A-Za-z0-9_]+)/g)) {
    result[item[1]] = `${item[2]} | StrategicBrainView`;
  }
  for (const item of match[1].matchAll(/\s+([a-z_]+):\s*<([A-Za-z0-9_]+)/g)) {
    if (!result[item[1]]) result[item[1]] = item[2];
  }
  return result;
}

function parseAppSurfaceInventory(appFile) {
  const source = read(appFile);
  const navKeys = parseUnionStrings(source, 'NavKey');
  const settingsKeys = parseConstStringArray(source, 'SETTINGS_SECTION_KEYS');
  const evidenceModes = parseUnionStrings(source, 'EvidenceMode');
  const sectionRootMap = parseSectionRootMap(source);
  const navRootMap = parseNavRootMap(source);
  const surfaces = [];
  for (const key of navKeys) {
    surfaces.push({
      surfaceId: `tab:${key}`,
      entryType: 'tab',
      reachableFrom: 'main_nav',
      roleConstraint: key === 'settings' ? 'authenticated' : 'authenticated',
      queryParamGate: null,
      rootComponent: navRootMap[key] || 'unknown',
      loaderFunction: null,
      expectedApiCalls: [],
    });
  }
  for (const key of settingsKeys) {
    surfaces.push({
      surfaceId: `settings:${key}`,
      entryType: 'settings_section',
      reachableFrom: 'tab:settings',
      roleConstraint: ['system_admin', 'org_overview', 'org_departments', 'org_people', 'org_rules'].includes(key) ? 'admin' : 'authenticated',
      queryParamGate: `settingsSection=${key}`,
      rootComponent: sectionRootMap[key] || 'unknown',
      loaderFunction: key === 'system_logs' ? 'eager' : 'loadSettingsSectionBlock',
      expectedApiCalls: [],
    });
  }
  for (const key of evidenceModes) {
    surfaces.push({
      surfaceId: `evidence:${key}`,
      entryType: 'query_param',
      reachableFrom: key === 'cockpit' ? 'tab:strategic_accompaniment' : 'tab:tasks|tab:client_workspace',
      roleConstraint: 'authenticated',
      queryParamGate: `evidenceMode=${key}`,
      rootComponent: key === 'cockpit' ? 'CockpitEvidenceView' : 'Task AI Evidence View',
      loaderFunction: null,
      expectedApiCalls: [],
    });
  }
  return surfaces;
}

function extractApiExports(apiFile) {
  const source = read(apiFile);
  const lines = source.split(/\r?\n/);
  const exports = [];
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const match = line.match(/^export\s+(?:async\s+)?function\s+([A-Za-z0-9_]+)/)
      || line.match(/^export\s+const\s+([A-Za-z0-9_]+)/)
      || line.match(/^export\s+type\s+([A-Za-z0-9_]+)/)
      || line.match(/^export\s+interface\s+([A-Za-z0-9_]+)/);
    if (!match) continue;
    exports.push({ name: match[1], line: index + 1, kind: line.includes('type ') ? 'type' : line.includes('interface') ? 'interface' : 'value' });
  }
  return { source, exports };
}

function extractExportBlocks(apiFile, exportRecords) {
  const source = read(apiFile);
  const lines = source.split(/\r?\n/);
  const blocks = new Map();
  for (let index = 0; index < exportRecords.length; index += 1) {
    const current = exportRecords[index];
    const start = current.line - 1;
    const end = index + 1 < exportRecords.length ? exportRecords[index + 1].line - 2 : lines.length - 1;
    const block = lines.slice(start, Math.max(start, end + 1)).join('\n');
    blocks.set(current.name, block);
  }
  return blocks;
}

function normalizeTemplatePaths(content) {
  return content.replace(/\$\{[^}]+\}/g, '{param}');
}

function extractApiPathsFromBlock(block) {
  const normalized = normalizeTemplatePaths(block);
  return [...normalized.matchAll(/\/api\/v1\/[A-Za-z0-9_{}\-/.]+/g)].map((item) => item[0]);
}

function countWordOccurrencesInFiles(name, files) {
  const pattern = new RegExp(`\\b${name}\\b`, 'g');
  let count = 0;
  for (const filePath of files) {
    const source = read(filePath);
    const matches = source.match(pattern);
    if (matches) count += matches.length;
  }
  return count;
}

function parsePreloadBridge(preloadFile) {
  const source = read(preloadFile);
  const bridge = [];
  const blockMatch = source.match(/contextBridge\.exposeInMainWorld\('yiyuWorkbench', \{([\s\S]*?)\n\}\);/m);
  if (!blockMatch) return bridge;
  for (const line of blockMatch[1].split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Za-z0-9_]+):/);
    if (match) bridge.push(match[1]);
  }
  return bridge;
}

function extractEndpoints(pyFile) {
  const source = read(pyFile);
  const endpoints = [];
  const pattern = /@app\.(get|post|put|delete|patch)\("([^"]+)"/g;
  let match;
  while ((match = pattern.exec(source))) {
    const prefix = source.slice(0, match.index);
    const line = prefix.split(/\r?\n/).length;
    endpoints.push({ method: match[1].toUpperCase(), path: match[2], line, file: pyFile });
  }
  return endpoints;
}

function normalizeEndpointPath(endpointPath) {
  return endpointPath.replace(/\{[^}]+\}/g, '{param}');
}

function getPackageScripts(packageJsonPath) {
  return JSON.parse(read(packageJsonPath)).scripts || {};
}

function collectScriptRefs(scriptMap) {
  const refs = new Set();
  for (const value of Object.values(scriptMap)) {
    const matches = String(value).match(/scripts\/[A-Za-z0-9_./-]+/g) || [];
    for (const item of matches) refs.add(item.replace(/['"]/g, ''));
  }
  return [...refs].sort();
}

function shell(command, cwd) {
  return execSync(command, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
}

function safeShell(command, cwd) {
  try {
    return { ok: true, output: shell(command, cwd) };
  } catch (error) {
    return {
      ok: false,
      output: String(error.stdout || '').trim(),
      stderr: String(error.stderr || '').trim(),
      code: error.status || 1,
    };
  }
}

function csvEscape(value) {
  const stringValue = value == null ? '' : String(value);
  if (/[",\n]/.test(stringValue)) return `"${stringValue.replace(/"/g, '""')}"`;
  return stringValue;
}

function writeCsv(filePath, rows, headers) {
  const lines = [headers.join(',')];
  for (const row of rows) {
    lines.push(headers.map((header) => csvEscape(row[header])).join(','));
  }
  write(filePath, `${lines.join('\n')}\n`);
}

function summarizeGitStatus(statusOutput) {
  const lines = statusOutput.split(/\r?\n/).filter(Boolean);
  return {
    total: lines.length,
    modifiedTracked: lines.filter((line) => /^[ MARCUD][MD]/.test(line) || /^M /.test(line) || /^ M/.test(line)).length,
    untracked: lines.filter((line) => /^\?\? /.test(line)).length,
    nestedRepo: lines.filter((line) => /^ m /.test(line)).length,
    deleted: lines.filter((line) => /^ D/.test(line) || /^D /.test(line)).length,
  };
}

function buildMainAudit() {
  const rendererFiles = listFiles(path.join(repoRoot, 'src', 'renderer'), isTsLike);
  const sharedFiles = listFiles(path.join(repoRoot, 'src', 'shared'), isTsLike);
  const mainFiles = listFiles(path.join(repoRoot, 'src', 'main'), isTsLike);
  const scriptFiles = listFiles(path.join(repoRoot, 'scripts'), (filePath) => /\.(mjs|js|py|sh)$/.test(filePath));
  const allTsFiles = [...rendererFiles, ...sharedFiles, ...mainFiles];
  const { graph, reverse } = buildImportGraph(allTsFiles);
  const rendererRoots = [path.join(repoRoot, 'src', 'renderer', 'main.tsx')].filter((filePath) => fs.existsSync(filePath));
  const reachable = walkReachable(graph, rendererRoots);
  const componentFiles = rendererFiles.filter((filePath) => rel(filePath).startsWith('src/renderer/components/'));
  const componentRows = componentFiles.map((filePath) => {
    const importers = (reverse.get(filePath) || []).map((item) => rel(item));
    const reachableImporters = importers.filter((item) => reachable.has(path.join(repoRoot, item)));
    let classification = 'reachable';
    if (!reachable.has(filePath)) {
      if (importers.length === 0) classification = 'orphan_component';
      else classification = 'blocked_by_runtime_issue';
    }
    return {
      file: rel(filePath),
      reachable: reachable.has(filePath),
      importers: importers.join(' | '),
      reachableImporters: reachableImporters.join(' | '),
      classification,
    };
  });

  const appFile = path.join(repoRoot, 'src', 'renderer', 'App.tsx');
  const uiSurfaceInventory = parseAppSurfaceInventory(appFile);

  const apiFile = path.join(repoRoot, 'src', 'renderer', 'lib', 'api.ts');
  const apiInfo = extractApiExports(apiFile);
  const apiBlocks = extractExportBlocks(apiFile, apiInfo.exports);
  const productRendererFiles = rendererFiles.filter((filePath) => filePath !== apiFile && !/\.test\./.test(filePath));
  const apiRows = apiInfo.exports.map((record) => {
    const usageCount = countWordOccurrencesInFiles(record.name, productRendererFiles);
    const block = apiBlocks.get(record.name) || '';
    const paths = extractApiPathsFromBlock(block);
    const classification = record.kind !== 'value'
      ? 'type_only'
      : usageCount === 0
        ? 'unused_api_wrapper'
        : 'used_api_wrapper';
    return {
      exportName: record.name,
      kind: record.kind,
      line: record.line,
      usageCount,
      paths: paths.join(' | '),
      classification,
    };
  });

  const preloadFile = path.join(repoRoot, 'src', 'main', 'preload.ts');
  const bridgeKeys = parsePreloadBridge(preloadFile);
  const rendererUsageFiles = rendererFiles.filter((filePath) => !/\.test\./.test(filePath));
  const ipcRows = bridgeKeys.map((key) => {
    const usageCount = rendererUsageFiles.reduce((count, filePath) => {
      const source = read(filePath);
      const matches = source.match(new RegExp(`(?:window\\.yiyuWorkbench\\.|yiyuWorkbench\\.)${key}\\b`, 'g')) || [];
      return count + matches.length;
    }, 0);
    return {
      bridgeKey: key,
      usageCount,
      classification: usageCount === 0 ? 'unused_ipc_bridge' : 'used_ipc_bridge',
    };
  });

  const backendEndpoints = extractEndpoints(path.join(repoRoot, 'backend', 'app', 'main.py'));
  const cloudEndpoints = extractEndpoints(path.join(repoRoot, 'cloud_backend', 'app', 'main.py'));
  const allWrappers = apiRows.filter((row) => row.kind === 'value' && row.paths);
  const backendRows = [...backendEndpoints, ...cloudEndpoints].map((endpoint) => {
    const normalized = normalizeEndpointPath(endpoint.path);
    const matchingWrappers = allWrappers.filter((row) => row.paths.split(' | ').some((item) => normalizeEndpointPath(item) === normalized));
    let classification = 'backend_only_no_ui_binding';
    if (matchingWrappers.some((row) => row.classification === 'used_api_wrapper')) classification = 'active_bound';
    else if (matchingWrappers.some((row) => row.classification === 'unused_api_wrapper')) classification = 'api_wrapper_orphan';
    else if (/^(\/health|\/api\/v1\/auth\/|\/api\/v1\/integrations\/feishu\/|\/api\/v1\/system\/health)/.test(endpoint.path)) classification = 'hidden_but_reachable';
    else if (endpoint.file.includes('cloud_backend') && /\/api\/v1\/(reviews|tasks|auth|consultation|mobile)/.test(endpoint.path)) classification = 'compatibility_only';
    return {
      file: rel(endpoint.file),
      method: endpoint.method,
      path: endpoint.path,
      normalizedPath: normalized,
      line: endpoint.line,
      matchingWrappers: matchingWrappers.map((row) => row.exportName).join(' | '),
      classification,
    };
  });

  const mainPackageScripts = getPackageScripts(path.join(repoRoot, 'package.json'));
  const referencedScripts = collectScriptRefs(mainPackageScripts);
  const scriptRows = scriptFiles.map((filePath) => {
    const shortPath = rel(filePath);
    const referencedByPackage = referencedScripts.includes(shortPath);
    let classification = referencedByPackage ? 'active_bound' : 'script_or_ops_only';
    if (/deploy-cloud-backend|smoke-cloud-backend|test-template-save|sync-local-event-lines-to-cloud/.test(shortPath)) classification = 'script_or_ops_only';
    return {
      file: shortPath,
      referencedByPackage,
      classification,
    };
  });

  const mainStatus = safeShell('git status --short', repoRoot);
  const mainBranch = safeShell('git branch --show-current', repoRoot);
  const mainHead = safeShell('git rev-parse --short HEAD', repoRoot);
  const missingRuntimeManifest = !fs.existsSync(path.join(repoRoot, 'src', 'main', 'runtimeManifest.ts'));
  const missingMainChainPresentation = !fs.existsSync(path.join(repoRoot, 'src', 'shared', 'mainChainPresentation.ts'));
  const missingEmbeddingProvider = !fs.existsSync(path.join(repoRoot, 'backend', 'app', 'services', 'embedding_provider.py'));

  return {
    uiSurfaceInventory,
    componentRows,
    apiRows,
    ipcRows,
    backendRows,
    scriptRows,
    baseline: {
      branch: mainBranch.output,
      head: mainHead.output,
      gitStatusSummary: summarizeGitStatus(mainStatus.output),
      packageScripts: mainPackageScripts,
      referencedScripts,
      knownMissingFiles: {
        runtimeManifestTs: missingRuntimeManifest,
        mainChainPresentationTs: missingMainChainPresentation,
        embeddingProviderPy: missingEmbeddingProvider,
      },
    },
  };
}

function buildMobileAudit() {
  const appFiles = listFiles(path.join(mobileRoot, 'app'), isTsLike);
  const componentFiles = listFiles(path.join(mobileRoot, 'components'), isTsLike);
  const libFiles = listFiles(path.join(mobileRoot, 'lib'), isTsLike);
  const scriptFiles = listFiles(path.join(mobileRoot, 'scripts'), isTsLike);
  const mobileFiles = [...appFiles, ...componentFiles, ...libFiles, ...scriptFiles];
  const { graph, reverse } = buildImportGraph(mobileFiles);
  const routeRoots = appFiles.filter((filePath) => !/\/_(layout)\./.test(filePath));
  const allRoots = [...appFiles];
  const reachable = walkReachable(graph, allRoots);
  const testFiles = libFiles.filter((filePath) => filePath.includes('/__tests__/'));
  const packageScripts = getPackageScripts(path.join(mobileRoot, 'package.json'));
  const referencedScripts = collectScriptRefs(packageScripts);

  const routeRows = appFiles.map((filePath) => ({
    file: rel(filePath, mobileRoot),
    classification: filePath.includes('/_layout.') ? 'route_shell' : 'route_bound',
  }));

  const componentRows = componentFiles.map((filePath) => {
    const importers = (reverse.get(filePath) || []).map((item) => rel(item, mobileRoot));
    const testImporters = importers.filter((item) => item.includes('/__tests__/'));
    let classification = 'route_bound';
    if (!reachable.has(filePath)) {
      if (testImporters.length > 0 && importers.length === testImporters.length) classification = 'test_guarded';
      else if (/calendar-screen|tasks-screen|WorkspaceLiteSheet|TaskSyncBadge|UnderstandingCard|WeekSignalCard|FocusBar|EventLineDrawer/.test(filePath)) classification = 'migration_active';
      else if (importers.length === 0) classification = 'orphan_candidate';
      else classification = 'migration_residue';
    } else if (/calendar-screen|tasks-screen/.test(filePath)) {
      classification = 'migration_active';
    }
    return {
      file: rel(filePath, mobileRoot),
      reachable: reachable.has(filePath),
      importers: importers.join(' | '),
      classification,
    };
  });

  const libRows = libFiles.map((filePath) => {
    const importers = (reverse.get(filePath) || []).map((item) => rel(item, mobileRoot));
    const testImporters = importers.filter((item) => item.includes('/__tests__/'));
    if (filePath.includes('/__tests__/')) {
      return {
        file: rel(filePath, mobileRoot),
        reachable: false,
        importers: importers.join(' | '),
        classification: 'test_guarded',
      };
    }
    let classification = 'store_bound';
    if (!reachable.has(filePath)) {
      if (testImporters.length > 0 && importers.length === testImporters.length) classification = 'test_guarded';
      else if (/legacy|pseudo-op|sync-freeze|-core\.ts$|runtime|scope-storage|sync-engine|smart-input-recovery/.test(filePath)) classification = 'migration_active';
      else if (importers.length === 0) classification = 'orphan_candidate';
      else classification = 'migration_residue';
    } else if (/legacy|pseudo-op|sync-freeze|-core\.ts$|runtime|sync-engine|smart-input-recovery/.test(filePath)) {
      classification = 'migration_active';
    }
    return {
      file: rel(filePath, mobileRoot),
      reachable: reachable.has(filePath),
      importers: importers.join(' | '),
      classification,
    };
  });

  const scriptRows = scriptFiles.map((filePath) => {
    const shortPath = rel(filePath, mobileRoot);
    return {
      file: shortPath,
      referencedByPackage: referencedScripts.includes(shortPath),
      classification: referencedScripts.includes(shortPath) ? 'migration_active' : 'script_or_ops_only',
    };
  });

  const mobileStatus = safeShell('git status --short', mobileRoot);
  const mobileBranch = safeShell('git branch --show-current', mobileRoot);
  const mobileHead = safeShell('git rev-parse --short HEAD', mobileRoot);

  return {
    routeRows,
    componentRows,
    libRows,
    scriptRows,
    baseline: {
      branch: mobileBranch.output,
      head: mobileHead.output,
      gitStatusSummary: summarizeGitStatus(mobileStatus.output),
      packageScripts,
      referencedScripts,
    },
  };
}

function buildVerificationMatrix() {
  return {
    main: {
      buildMain: safeShell('npm run build:main', repoRoot),
      buildRenderer: safeShell('npm run build:renderer', repoRoot),
      backendPytest: safeShell('uv run --project backend python -m pytest backend/tests/test_knowledge_v2.py -q', repoRoot),
      cloudPytest: safeShell('uv run --project cloud_backend python -m pytest cloud_backend/tests/test_auth_tasks.py cloud_backend/tests/test_simulation_seed.py -q', repoRoot),
    },
    mobile: {
      directApiInventory: safeShell('npm run inventory:direct-api-usage', mobileRoot),
      directTaskGuard: safeShell('npm run check:no-direct-task-api-writes', mobileRoot),
      coreTests: safeShell('npm run test:core', mobileRoot),
    },
  };
}

function buildMarkdownArtifacts(mainAudit, mobileAudit, verificationMatrix) {
  const mainBaselineLines = [
    '# Main Repo Baseline',
    '',
    `- Repo: ${repoRoot}`,
    `- Branch: ${mainAudit.baseline.branch}`,
    `- HEAD: ${mainAudit.baseline.head}`,
    `- Dirty tracked/untracked/nested/deleted: ${mainAudit.baseline.gitStatusSummary.modifiedTracked}/${mainAudit.baseline.gitStatusSummary.untracked}/${mainAudit.baseline.gitStatusSummary.nestedRepo}/${mainAudit.baseline.gitStatusSummary.deleted}`,
    `- Known missing files: runtimeManifest.ts=${mainAudit.baseline.knownMissingFiles.runtimeManifestTs}, mainChainPresentation.ts=${mainAudit.baseline.knownMissingFiles.mainChainPresentationTs}, embedding_provider.py=${mainAudit.baseline.knownMissingFiles.embeddingProviderPy}`,
    '',
    '## Build/Test Entry Points',
    '',
    '- Desktop main build: `npm run build:main`',
    '- Desktop renderer build: `npm run build:renderer`',
    '- Backend minimal pytest: `uv run --project backend python -m pytest backend/tests/test_knowledge_v2.py -q`',
    '- Cloud minimal pytest: `uv run --project cloud_backend python -m pytest cloud_backend/tests/test_auth_tasks.py cloud_backend/tests/test_simulation_seed.py -q`',
    '',
    '## Audit Hooks Present',
    '',
    `- Package-referenced scripts: ${mainAudit.baseline.referencedScripts.join(', ')}`,
    '- Runtime UI proof remains blocked until source build is fixed.',
    '',
  ];

  const mobileBaselineLines = [
    '# Mobile Repo Baseline',
    '',
    `- Repo: ${mobileRoot}`,
    `- Branch: ${mobileAudit.baseline.branch}`,
    `- HEAD: ${mobileAudit.baseline.head}`,
    `- Dirty tracked/untracked/nested/deleted: ${mobileAudit.baseline.gitStatusSummary.modifiedTracked}/${mobileAudit.baseline.gitStatusSummary.untracked}/${mobileAudit.baseline.gitStatusSummary.nestedRepo}/${mobileAudit.baseline.gitStatusSummary.deleted}`,
    '',
    '## Build/Test Entry Points',
    '',
    '- Direct API inventory: `npm run inventory:direct-api-usage`',
    '- Guardrail: `npm run check:no-direct-task-api-writes`',
    '- Core tests: `npm run test:core`',
    '',
    '## Audit Hooks Present',
    '',
    `- Package-referenced scripts: ${mobileAudit.baseline.referencedScripts.join(', ')}`,
    '- Mobile is treated as an independent repo and ledger.',
    '',
  ];

  const verificationLines = [
    '# Verification Matrix',
    '',
    '| Repo | Check | Status | Evidence |',
    '| --- | --- | --- | --- |',
  ];
  const addRow = (repo, check, result) => {
    const status = result.ok ? 'pass' : 'fail';
    const evidence = (result.ok ? result.output : `${result.stderr || result.output}`).replace(/\|/g, '\\|').split(/\r?\n/)[0];
    verificationLines.push(`| ${repo} | ${check} | ${status} | ${evidence} |`);
  };
  addRow('main', 'build:main', verificationMatrix.main.buildMain);
  addRow('main', 'build:renderer', verificationMatrix.main.buildRenderer);
  addRow('main', 'backend minimal pytest', verificationMatrix.main.backendPytest);
  addRow('main', 'cloud minimal pytest', verificationMatrix.main.cloudPytest);
  addRow('mobile', 'inventory:direct-api-usage', verificationMatrix.mobile.directApiInventory);
  addRow('mobile', 'check:no-direct-task-api-writes', verificationMatrix.mobile.directTaskGuard);
  addRow('mobile', 'test:core', verificationMatrix.mobile.coreTests);

  const errorLedgerLines = [
    '# Round 2 Error Ledger',
    '',
    '## P0 / P1 Runtime and Contract Blockers',
    '',
    '| Repo | Classification | Path / Symbol | Current Binding | Runtime Status | Test Status | Recommended Action | Blocking Dependency |',
    '| --- | --- | --- | --- | --- | --- | --- | --- |',
    `| main | startup_blocker | src/main/main.ts -> ./runtimeManifest.js | build:main hard dependency | fail: missing runtimeManifest.ts/js import target | fail | restore or rewire runtime manifest module before any runtime UI proof | source build blocked |`,
    `| main | startup_blocker | src/renderer/App.tsx -> ../shared/mainChainPresentation | renderer root import | fail: build:renderer unresolved module | fail | restore or rewire shared presentation module before runtime UI audit | source build blocked |`,
    `| main | contract_mismatch | backend/app/services/knowledge_base.py -> app.services.embedding_provider | backend test import chain | fail: ModuleNotFoundError during pytest collection | fail | restore module or update imports before backend dead-code conclusions | backend test collection blocked |`,
    `| cloud_backend | runtime_divergence | auth/review/task org control flows | cloud API mainline | fail: 6 targeted tests under auth/review/simulation seed | fail | treat current cloud auth/task behavior as unstable; do not infer dead code from failed paths | cloud state diverges from tests |`,
    `| mobile | migration_residue | direct API writes in lib/sync-engine.ts, lib/calendar-repository.ts, lib/record-note-service.ts | local-first migration support path | pass guard on task surfaces, but inventory still reports direct writes | mixed | keep as explicit migration ledger; do not delete while local-first boundary is still active | migration not complete |`,
  ];

  const highConfidenceMainOrphans = mainAudit.componentRows.filter((row) => row.classification === 'orphan_component');
  const unusedApiRows = mainAudit.apiRows.filter((row) => row.classification === 'unused_api_wrapper');
  const unusedIpcRows = mainAudit.ipcRows.filter((row) => row.classification === 'unused_ipc_bridge');
  const mainBlockedRows = mainAudit.componentRows.filter((row) => row.classification === 'blocked_by_runtime_issue');
  const mobileOrphans = [...mobileAudit.componentRows, ...mobileAudit.libRows].filter((row) => row.classification === 'orphan_candidate');
  const mobileMigration = [...mobileAudit.componentRows, ...mobileAudit.libRows].filter((row) => row.classification === 'migration_active');
  const mobileTestGuarded = [...mobileAudit.componentRows, ...mobileAudit.libRows].filter((row) => row.classification === 'test_guarded');
  const mainScriptOpsRows = mainAudit.scriptRows.filter((row) => row.classification === 'script_or_ops_only');
  const backendOnlyRows = mainAudit.backendRows.filter((row) => row.classification === 'backend_only_no_ui_binding');
  const compatibilityRows = mainAudit.backendRows.filter((row) => row.classification === 'compatibility_only');

  const deadCodeLines = [
    '# Round 2 Dead Code Ledger',
    '',
    '## A. High-confidence unused or low-binding candidates',
    '',
    '### Main repo component candidates',
    '',
    ...highConfidenceMainOrphans.map((row) => `- \`${row.file}\` -> orphan_component`),
    '',
    '### Main repo API wrappers with zero product usage',
    '',
    ...unusedApiRows.slice(0, 60).map((row) => `- \`${row.exportName}\` -> ${row.paths || 'no endpoint string captured'}`),
    '',
    '### Main repo IPC bridges with zero renderer usage',
    '',
    ...unusedIpcRows.map((row) => `- \`${row.bridgeKey}\``),
    '',
    '## B. Candidates blocked by runtime/source build issues',
    '',
    ...mainBlockedRows.map((row) => `- \`${row.file}\` imported only from currently unreachable renderer branches; keep blocked_by_runtime_issue until source build runs`),
    '',
    '## C. Mobile orphan candidates',
    '',
    ...mobileOrphans.map((row) => `- \`${row.file}\``),
    '',
    '## D. Main repo script_or_ops_only candidates',
    '',
    ...mainScriptOpsRows.map((row) => `- \`${row.file}\``),
    '',
    '## E. Backend/cloud low-binding endpoint inventories',
    '',
    '### backend_only_no_ui_binding',
    '',
    ...backendOnlyRows.slice(0, 25).map((row) => `- \`${row.file}:${row.line}\` ${row.method} ${row.path}`),
    '',
    '### compatibility_only',
    '',
    ...compatibilityRows.map((row) => `- \`${row.file}:${row.line}\` ${row.method} ${row.path}`),
    '',
    '## F. Mobile test-guarded files',
    '',
    ...mobileTestGuarded.map((row) => `- \`${row.file}\``),
    '',
    '## G. Mobile migration-active files (do not delete yet)',
    '',
    ...mobileMigration.slice(0, 80).map((row) => `- \`${row.file}\``),
    '',
  ];

  const cleanupLines = [
    '# Round 2 Cleanup Backlog',
    '',
    '## P0',
    '',
    '- Fix main source build blockers: missing `src/main/runtimeManifest.ts` binding and missing `src/shared/mainChainPresentation.ts` binding.',
    '- Fix backend import chain so minimal pytest can collect: `app.services.embedding_provider` missing from current tree.',
    '- Triage cloud auth/task/review regressions before using cloud runtime failures as evidence for dead-code removal.',
    '',
    '## P1',
    '',
    '- Re-run runtime UI audit after main source build is restored; promote `blocked_by_runtime_issue` candidates only after runtime proof remains empty.',
    '- Review main repo zero-use API wrappers and unused IPC bridges for safe deletion or consolidation.',
    '- Review mobile direct API write sites as migration-active technical debt, not dead code.',
    '',
    '## P2',
    '',
    '- Review script_or_ops_only scripts under `scripts/` and `mobile/scripts/` for publish-chain relevance.',
    '- Review compatibility-only backend/cloud endpoints for admin-only or install-only retention rules.',
    '',
  ];

  return {
    mainRepoBaseline: `${mainBaselineLines.join('\n')}\n`,
    mobileRepoBaseline: `${mobileBaselineLines.join('\n')}\n`,
    verificationMatrix: `${verificationLines.join('\n')}\n`,
    errorLedger: `${errorLedgerLines.join('\n')}\n`,
    deadCodeLedger: `${deadCodeLines.join('\n')}\n`,
    cleanupBacklog: `${cleanupLines.join('\n')}\n`,
  };
}

function main() {
  ensureDir(outDir);
  const mainAudit = buildMainAudit();
  const mobileAudit = buildMobileAudit();
  const verificationMatrix = buildVerificationMatrix();
  const docs = buildMarkdownArtifacts(mainAudit, mobileAudit, verificationMatrix);

  writeJson(path.join(outDir, 'ui_surface_inventory.json'), mainAudit.uiSurfaceInventory);
  writeCsv(path.join(outDir, 'renderer_component_reachability.csv'), mainAudit.componentRows, ['file', 'reachable', 'importers', 'reachableImporters', 'classification']);
  writeCsv(path.join(outDir, 'renderer_api_export_usage.csv'), mainAudit.apiRows, ['exportName', 'kind', 'line', 'usageCount', 'paths', 'classification']);
  writeCsv(path.join(outDir, 'ipc_channel_usage.csv'), mainAudit.ipcRows, ['bridgeKey', 'usageCount', 'classification']);
  writeCsv(path.join(outDir, 'backend_endpoint_binding.csv'), mainAudit.backendRows, ['file', 'method', 'path', 'normalizedPath', 'line', 'matchingWrappers', 'classification']);
  writeCsv(path.join(outDir, 'main_script_inventory.csv'), mainAudit.scriptRows, ['file', 'referencedByPackage', 'classification']);
  writeCsv(path.join(outDir, 'mobile_route_inventory.csv'), mobileAudit.routeRows, ['file', 'classification']);
  writeCsv(path.join(outDir, 'mobile_component_inventory.csv'), mobileAudit.componentRows, ['file', 'reachable', 'importers', 'classification']);
  writeCsv(path.join(outDir, 'mobile_lib_inventory.csv'), mobileAudit.libRows, ['file', 'reachable', 'importers', 'classification']);
  writeCsv(path.join(outDir, 'mobile_script_inventory.csv'), mobileAudit.scriptRows, ['file', 'referencedByPackage', 'classification']);

  write(path.join(outDir, 'main_repo_baseline.md'), docs.mainRepoBaseline);
  write(path.join(outDir, 'mobile_repo_baseline.md'), docs.mobileRepoBaseline);
  write(path.join(outDir, 'verification_matrix.md'), docs.verificationMatrix);
  write(path.join(outDir, 'round2_error_ledger.md'), docs.errorLedger);
  write(path.join(outDir, 'round2_dead_code_ledger.md'), docs.deadCodeLedger);
  write(path.join(outDir, 'round2_cleanup_backlog.md'), docs.cleanupBacklog);

  writeJson(path.join(outDir, 'summary.json'), {
    main: {
      uiSurfaceCount: mainAudit.uiSurfaceInventory.length,
      orphanComponents: mainAudit.componentRows.filter((row) => row.classification === 'orphan_component').length,
      blockedByRuntimeIssue: mainAudit.componentRows.filter((row) => row.classification === 'blocked_by_runtime_issue').length,
      unusedApiWrappers: mainAudit.apiRows.filter((row) => row.classification === 'unused_api_wrapper').length,
      unusedIpcBridges: mainAudit.ipcRows.filter((row) => row.classification === 'unused_ipc_bridge').length,
      backendOnlyEndpoints: mainAudit.backendRows.filter((row) => row.classification === 'backend_only_no_ui_binding').length,
      apiWrapperOrphanEndpoints: mainAudit.backendRows.filter((row) => row.classification === 'api_wrapper_orphan').length,
      scriptOrOpsOnly: mainAudit.scriptRows.filter((row) => row.classification === 'script_or_ops_only').length,
    },
    mobile: {
      routes: mobileAudit.routeRows.length,
      orphanCandidates: [...mobileAudit.componentRows, ...mobileAudit.libRows].filter((row) => row.classification === 'orphan_candidate').length,
      migrationActive: [...mobileAudit.componentRows, ...mobileAudit.libRows, ...mobileAudit.scriptRows].filter((row) => row.classification === 'migration_active').length,
      testGuarded: [...mobileAudit.componentRows, ...mobileAudit.libRows].filter((row) => row.classification === 'test_guarded').length,
    },
  });

  writeJson(path.join(outDir, 'verification_results.json'), verificationMatrix);
}

main();
