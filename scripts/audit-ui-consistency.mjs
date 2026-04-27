#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '..');
const outputDir = path.join(projectRoot, 'output', 'ui-consistency-audit');
const appPath = path.join(projectRoot, 'src', 'renderer', 'App.tsx');
const apiPath = path.join(projectRoot, 'src', 'renderer', 'lib', 'api.ts');
const preloadPath = path.join(projectRoot, 'src', 'main', 'preload.ts');
const backendMainPath = path.join(projectRoot, 'backend', 'app', 'main.py');
const tsConfigPath = path.join(projectRoot, 'tsconfig.json');

const EXCLUDED_DIRS = new Set(['build', 'dist', 'node_modules']);
const SETTINGS_ADMIN_ONLY_KEYS = new Set(['system_admin', 'org_overview', 'org_departments', 'org_people', 'org_rules']);
const LOW_FREQUENCY_ENTRY_TYPES = new Set(['deep_link', 'evidence', 'admin']);

function posixRelative(targetPath) {
  return path.relative(projectRoot, targetPath).split(path.sep).join('/');
}

function ensureDir(targetPath) {
  fs.mkdirSync(targetPath, { recursive: true });
}

function readText(targetPath) {
  return fs.readFileSync(targetPath, 'utf8');
}

function writeJson(targetPath, value) {
  fs.writeFileSync(targetPath, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

function writeText(targetPath, value) {
  fs.writeFileSync(targetPath, value.endsWith('\n') ? value : `${value}\n`, 'utf8');
}

function csvEscape(value) {
  const text = String(value ?? '');
  if (!/[,"\n]/.test(text)) return text;
  return `"${text.replace(/"/g, '""')}"`;
}

function writeCsv(targetPath, rows) {
  if (!rows.length) {
    writeText(targetPath, '');
    return;
  }
  const headers = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  const lines = [
    headers.join(','),
    ...rows.map((row) => headers.map((header) => csvEscape(row[header] ?? '')).join(',')),
  ];
  writeText(targetPath, lines.join('\n'));
}

function isTestFile(targetPath) {
  const normalized = targetPath.split(path.sep).join('/');
  return normalized.includes('/__tests__/') || /\.test\.[jt]sx?$/.test(normalized) || /\.spec\.[jt]sx?$/.test(normalized);
}

function isExcludedPath(targetPath) {
  const relative = posixRelative(targetPath);
  return relative.split('/').some((segment) => EXCLUDED_DIRS.has(segment));
}

function collectFiles(rootDir, predicate) {
  const items = [];
  const stack = [rootDir];
  while (stack.length > 0) {
    const current = stack.pop();
    if (!current || !fs.existsSync(current)) continue;
    const stat = fs.statSync(current);
    if (stat.isDirectory()) {
      for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
        const nextPath = path.join(current, entry.name);
        if (isExcludedPath(nextPath)) continue;
        stack.push(nextPath);
      }
      continue;
    }
    if (predicate(current)) items.push(current);
  }
  return items.sort();
}

function parseTsConfig(targetPath) {
  const config = ts.readConfigFile(targetPath, ts.sys.readFile);
  if (config.error) {
    throw new Error(ts.flattenDiagnosticMessageText(config.error.messageText, '\n'));
  }
  return ts.parseJsonConfigFileContent(config.config, ts.sys, path.dirname(targetPath));
}

function createProgram() {
  const config = parseTsConfig(tsConfigPath);
  const relevantFiles = config.fileNames.filter((fileName) => {
    const relative = posixRelative(fileName);
    return (
      relative.startsWith('src/renderer/')
      || relative.startsWith('src/shared/')
      || relative === 'src/main/preload.ts'
      || relative === 'src/main/main.ts'
    );
  });
  return ts.createProgram({
    rootNames: relevantFiles,
    options: {
      ...config.options,
      noEmit: true,
    },
  });
}

function findNamedDeclarations(sourceFile) {
  const result = new Map();
  function visit(node) {
    if (ts.isFunctionDeclaration(node) && node.name?.text) {
      result.set(node.name.text, node);
    } else if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      if (ts.isArrowFunction(node.initializer) || ts.isFunctionExpression(node.initializer)) {
        result.set(node.name.text, node);
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return result;
}

function getFunctionLikeBody(node) {
  if (!node) return null;
  if (ts.isFunctionDeclaration(node) || ts.isFunctionExpression(node) || ts.isArrowFunction(node)) {
    return node.body || null;
  }
  if (ts.isVariableDeclaration(node) && node.initializer) {
    return getFunctionLikeBody(node.initializer);
  }
  return null;
}

function getFunctionNode(nameMap, name) {
  return nameMap.get(name) || null;
}

function getImportedBindings(sourceFile, moduleMatcher) {
  const bindings = new Map();
  for (const statement of sourceFile.statements) {
    if (!ts.isImportDeclaration(statement)) continue;
    const moduleName = statement.moduleSpecifier.getText(sourceFile).slice(1, -1);
    if (!moduleMatcher(moduleName)) continue;
    const clause = statement.importClause;
    if (!clause) continue;
    if (clause.name) {
      bindings.set(clause.name.text, 'default');
    }
    if (clause.namedBindings && ts.isNamedImports(clause.namedBindings)) {
      for (const element of clause.namedBindings.elements) {
        bindings.set(element.name.text, element.propertyName?.text || element.name.text);
      }
    }
  }
  return bindings;
}

function stringFromLiteral(node) {
  if (!node) return null;
  if (ts.isStringLiteralLike(node)) return node.text;
  if (ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  return null;
}

function collectStringUnionValues(sourceFile, aliasName) {
  const values = [];
  for (const statement of sourceFile.statements) {
    if (!ts.isTypeAliasDeclaration(statement) || statement.name.text !== aliasName) continue;
    if (!ts.isUnionTypeNode(statement.type)) continue;
    for (const typeNode of statement.type.types) {
      if (ts.isLiteralTypeNode(typeNode) && ts.isStringLiteral(typeNode.literal)) {
        values.push(typeNode.literal.text);
      }
    }
  }
  return values;
}

function collectConstArrayStringValues(sourceFile, constName) {
  for (const statement of sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (!ts.isIdentifier(declaration.name) || declaration.name.text !== constName) continue;
      if (!declaration.initializer || !ts.isArrayLiteralExpression(declaration.initializer)) return [];
      return declaration.initializer.elements
        .map((element) => {
          if (ts.isAsExpression(element)) return stringFromLiteral(element.expression);
          return stringFromLiteral(element);
        })
        .filter(Boolean);
    }
  }
  return [];
}

function collectConstObjectLiteral(sourceFile, constName) {
  let found = null;
  function visit(node) {
    if (found) return;
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === constName) {
      if (node.initializer && ts.isObjectLiteralExpression(node.initializer)) {
        found = node.initializer;
        return;
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return found;
}

function collectConstArrayLiteral(sourceFile, constName) {
  let found = null;
  function visit(node) {
    if (found) return;
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === constName) {
      if (node.initializer && ts.isArrayLiteralExpression(node.initializer)) {
        found = node.initializer;
        return;
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return found;
}

function normalizeWhitespace(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function getReadableExpressionName(expression, sourceFile) {
  if (!expression) return null;
  if (ts.isJsxSelfClosingElement(expression)) return expression.tagName.getText(sourceFile);
  if (ts.isJsxElement(expression)) return expression.openingElement.tagName.getText(sourceFile);
  if (ts.isCallExpression(expression)) return expression.expression.getText(sourceFile);
  if (ts.isIdentifier(expression)) return expression.text;
  if (ts.isConditionalExpression(expression)) {
    return `${getReadableExpressionName(expression.whenTrue, sourceFile) || expression.whenTrue.getText(sourceFile)}|${getReadableExpressionName(expression.whenFalse, sourceFile) || expression.whenFalse.getText(sourceFile)}`;
  }
  return normalizeWhitespace(expression.getText(sourceFile));
}

function collectFunctionMarkers(nameMap, functionName, cache = new Map()) {
  if (cache.has(functionName)) return cache.get(functionName);
  const node = getFunctionNode(nameMap, functionName);
  const body = getFunctionLikeBody(node);
  const markers = [];
  if (!body) {
    cache.set(functionName, markers);
    return markers;
  }
  function visit(current) {
    if (ts.isStringLiteralLike(current) || ts.isNoSubstitutionTemplateLiteral(current)) {
      const text = normalizeWhitespace(current.text);
      if (
        text.length >= 4
        && text.length <= 48
        && /[\u4e00-\u9fffA-Za-z]/.test(text)
        && !text.startsWith('http')
        && !text.includes('className')
        && !/(^| )(space-y|grid|flex|rounded|border|bg-|text-\[|px-|py-|mt-|mb-|gap-|items-|justify-|leading-)/.test(text)
      ) {
        markers.push(text);
      }
    } else if (ts.isJsxText(current)) {
      const text = normalizeWhitespace(current.text);
      if (
        text.length >= 4
        && text.length <= 48
        && /[\u4e00-\u9fffA-Za-z]/.test(text)
        && !/(^| )(space-y|grid|flex|rounded|border|bg-|text-\[|px-|py-|mt-|mb-|gap-|items-|justify-|leading-)/.test(text)
      ) {
        markers.push(text);
      }
    }
    ts.forEachChild(current, visit);
  }
  visit(body);
  const unique = [...new Set(markers)].slice(0, 8);
  cache.set(functionName, unique);
  return unique;
}

function collectCallGraphAndApiUsage(sourceFile) {
  const apiBindings = getImportedBindings(sourceFile, (moduleName) => moduleName.endsWith('/lib/api') || moduleName === './lib/api');
  const namedDeclarations = findNamedDeclarations(sourceFile);
  const data = new Map();
  for (const [name] of namedDeclarations.entries()) {
    data.set(name, { directApiCalls: new Set(), directLocalCalls: new Set() });
  }
  for (const [name, declaration] of namedDeclarations.entries()) {
    const body = getFunctionLikeBody(declaration);
    if (!body) continue;
    function visit(node) {
      if (ts.isCallExpression(node)) {
        if (ts.isIdentifier(node.expression)) {
          const called = node.expression.text;
          if (apiBindings.has(called)) {
            data.get(name).directApiCalls.add(apiBindings.get(called));
          } else if (namedDeclarations.has(called) && called !== name) {
            data.get(name).directLocalCalls.add(called);
          }
        }
      }
      ts.forEachChild(node, visit);
    }
    visit(body);
  }
  const apiCache = new Map();
  function collectTransitive(functionName, stack = new Set()) {
    if (apiCache.has(functionName)) return apiCache.get(functionName);
    if (stack.has(functionName)) return [];
    stack.add(functionName);
    const entry = data.get(functionName);
    if (!entry) return [];
    const result = new Set(entry.directApiCalls);
    for (const localCall of entry.directLocalCalls) {
      for (const nested of collectTransitive(localCall, stack)) {
        result.add(nested);
      }
    }
    const sorted = [...result].sort();
    apiCache.set(functionName, sorted);
    stack.delete(functionName);
    return sorted;
  }
  return { apiBindings, namedDeclarations, collectTransitive };
}

function extractNavItems(sourceFile) {
  const items = [];
  const navItemsNode = collectConstArrayLiteral(sourceFile, 'navItems');
  if (!navItemsNode) return items;
  for (const element of navItemsNode.elements) {
    if (!ts.isObjectLiteralExpression(element)) continue;
    const row = {};
    for (const property of element.properties) {
      if (!ts.isPropertyAssignment(property) || !ts.isIdentifier(property.name)) continue;
      const key = property.name.text;
      const value = property.initializer;
      if (key === 'id') {
        row.id = ts.isAsExpression(value) ? stringFromLiteral(value.expression) : stringFromLiteral(value);
      } else if (key === 'label') {
        row.label = stringFromLiteral(value);
      }
    }
    if (row.id) items.push(row);
  }
  return items;
}

function extractSettingsGroups(sourceFile) {
  const result = new Map();
  function visit(node) {
    if (!ts.isVariableDeclaration(node) || !ts.isIdentifier(node.name) || node.name.text !== 'sectionGroups') {
      ts.forEachChild(node, visit);
      return;
    }
    if (!node.initializer || !ts.isArrayLiteralExpression(node.initializer)) return;
    for (const element of node.initializer.elements) {
      if (!ts.isObjectLiteralExpression(element)) continue;
      let groupLabel = '';
      let itemsExpression = null;
      for (const property of element.properties) {
        if (!ts.isPropertyAssignment(property) || !ts.isIdentifier(property.name)) continue;
        if (property.name.text === 'group') groupLabel = stringFromLiteral(property.initializer) || '';
        if (property.name.text === 'items' && ts.isArrayLiteralExpression(property.initializer)) itemsExpression = property.initializer;
      }
      if (!itemsExpression) continue;
      for (const item of itemsExpression.elements) {
        if (!ts.isObjectLiteralExpression(item)) continue;
        let key = '';
        const entry = { group: groupLabel, label: '', helper: '' };
        for (const property of item.properties) {
          if (!ts.isPropertyAssignment(property) || !ts.isIdentifier(property.name)) continue;
          const propertyName = property.name.text;
          if (propertyName === 'key') key = stringFromLiteral(property.initializer) || '';
          if (propertyName === 'label') entry.label = stringFromLiteral(property.initializer) || '';
          if (propertyName === 'helper') entry.helper = stringFromLiteral(property.initializer) || '';
        }
        if (key) result.set(key, entry);
      }
    }
  }
  visit(sourceFile);
  return result;
}

function extractViewMap(sourceFile) {
  const mapNode = collectConstObjectLiteral(sourceFile, 'viewMap');
  const result = new Map();
  if (!mapNode) return result;
  for (const property of mapNode.properties) {
    if (!ts.isPropertyAssignment(property)) continue;
    const key = ts.isIdentifier(property.name) ? property.name.text : stringFromLiteral(property.name);
    if (!key) continue;
    result.set(key, getReadableExpressionName(property.initializer, sourceFile));
  }
  return result;
}

function collectSwitchCaseMap(sourceFile, functionName, callback) {
  const namedDeclarations = findNamedDeclarations(sourceFile);
  const node = getFunctionNode(namedDeclarations, functionName);
  const body = getFunctionLikeBody(node);
  const result = new Map();
  if (!body || !ts.isBlock(body)) return result;
  function visit(current) {
    if (!ts.isSwitchStatement(current)) {
      ts.forEachChild(current, visit);
      return;
    }
    for (const clause of current.caseBlock.clauses) {
      if (!ts.isCaseClause(clause)) continue;
      const caseValue = stringFromLiteral(clause.expression);
      if (!caseValue) continue;
      const extracted = callback(clause, sourceFile);
      if (extracted) result.set(caseValue, extracted);
    }
  }
  visit(body);
  return result;
}

function extractSettingsLoadMap(sourceFile) {
  return collectSwitchCaseMap(sourceFile, 'loadSettingsSectionBlock', (clause) => {
    const calls = [];
    function visit(node) {
      if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
        calls.push(node.expression.text);
      }
      ts.forEachChild(node, visit);
    }
    clause.forEachChild(visit);
    return [...new Set(calls)].filter((name) => name.startsWith('load') || name.startsWith('get') || name.startsWith('refresh'));
  });
}

function extractSettingsRenderMap(sourceFile) {
  return collectSwitchCaseMap(sourceFile, 'renderSectionContent', (clause, currentSourceFile) => {
    for (const statement of clause.statements) {
      if (ts.isReturnStatement(statement) && statement.expression) {
        return getReadableExpressionName(statement.expression, currentSourceFile);
      }
    }
    return null;
  });
}

function buildUiSurfaceInventory(program) {
  const sourceFile = program.getSourceFile(appPath);
  if (!sourceFile) throw new Error(`Missing source file ${appPath}`);
  const { namedDeclarations, collectTransitive } = collectCallGraphAndApiUsage(sourceFile);
  const markerCache = new Map();
  const navKeys = collectStringUnionValues(sourceFile, 'NavKey');
  const settingsKeys = collectStringUnionValues(sourceFile, 'SettingsSectionKey');
  const navItems = extractNavItems(sourceFile);
  const navLabelByKey = new Map(navItems.map((item) => [item.id, item.label]));
  const settingsGroups = extractSettingsGroups(sourceFile);
  const viewMap = extractViewMap(sourceFile);
  const settingsLoadMap = extractSettingsLoadMap(sourceFile);
  const settingsRenderMap = extractSettingsRenderMap(sourceFile);
  const tabParam = collectConstArrayStringValues(sourceFile, 'NAV_KEYS').length ? 'tab' : 'tab';
  const surfaces = [];

  for (const navKey of navKeys) {
    const rootExpression = viewMap.get(navKey) || null;
    const rootComponent = rootExpression || null;
    const componentNames = String(rootExpression || '')
      .split('|')
      .map((value) => value.replace(/[<>\(\)\s].*/g, '').trim())
      .filter(Boolean);
    const expectedApiCalls = [...new Set(componentNames.flatMap((name) => collectTransitive(name) || []))].sort();
    const domMarkers = [...new Set(componentNames.flatMap((name) => collectFunctionMarkers(namedDeclarations, name, markerCache)))].slice(0, 8);
    surfaces.push({
      surfaceId: `nav/${navKey}`,
      entryType: 'nav',
      reachableFrom: 'sidebar',
      roleConstraint: 'any',
      queryParamGate: { [tabParam]: navKey },
      rootComponent,
      loaderFunction: null,
      expectedApiCalls,
      domMarkers,
      label: navLabelByKey.get(navKey) || navKey,
    });
  }

  for (const settingsKey of settingsKeys) {
    const rootExpression = settingsRenderMap.get(settingsKey) || null;
    const rootComponent = rootExpression || null;
    const componentNames = String(rootExpression || '')
      .split('|')
      .map((value) => value.replace(/[<>\(\)\s].*/g, '').trim())
      .filter(Boolean);
    const loaderFunctions = settingsLoadMap.get(settingsKey) || [];
    const expectedApiCalls = [...new Set([
      ...loaderFunctions.flatMap((name) => collectTransitive(name) || []),
      ...componentNames.flatMap((name) => collectTransitive(name) || []),
    ])].sort();
    const domMarkers = [...new Set([
      ...(settingsGroups.get(settingsKey) ? [settingsGroups.get(settingsKey).label, settingsGroups.get(settingsKey).helper] : []),
      ...componentNames.flatMap((name) => collectFunctionMarkers(namedDeclarations, name, markerCache)),
    ])]
      .map(normalizeWhitespace)
      .filter(Boolean)
      .slice(0, 8);
    surfaces.push({
      surfaceId: `settings/${settingsKey}`,
      entryType: SETTINGS_ADMIN_ONLY_KEYS.has(settingsKey) ? 'admin' : 'settings_section',
      reachableFrom: SETTINGS_ADMIN_ONLY_KEYS.has(settingsKey) ? 'query_param_or_admin' : 'settings_sidebar',
      roleConstraint: SETTINGS_ADMIN_ONLY_KEYS.has(settingsKey) ? 'admin_only_or_deep_link' : 'any',
      queryParamGate: { tab: 'settings', settingsSection: settingsKey },
      rootComponent,
      loaderFunction: loaderFunctions,
      expectedApiCalls,
      domMarkers,
      label: settingsGroups.get(settingsKey)?.label || settingsKey,
      helper: settingsGroups.get(settingsKey)?.helper || '',
    });
  }

  const tasksApiCalls = collectTransitive('TasksView') || [];
  surfaces.push({
    surfaceId: 'evidence/task-ai',
    entryType: 'evidence',
    reachableFrom: 'query_param',
    roleConstraint: 'any',
    queryParamGate: { tab: 'tasks', evidenceMode: 'task-ai', taskId: '{taskId}' },
    rootComponent: 'TasksView(task-ai evidence)',
    loaderFunction: null,
    expectedApiCalls: tasksApiCalls,
    domMarkers: ['任务 AI 页面证据', 'RC Evidence', 'evidenceMode=task-ai'],
    label: '任务 AI 证据页',
  });
  const cockpitCalls = [
    ...(collectTransitive('CockpitEvidenceView') || []),
    ...(collectTransitive('StrategicBrainView') || []),
  ];
  surfaces.push({
    surfaceId: 'evidence/cockpit',
    entryType: 'evidence',
    reachableFrom: 'query_param',
    roleConstraint: 'any',
    queryParamGate: { tab: 'strategic_accompaniment', evidenceMode: 'cockpit', clientId: '{clientId}' },
    rootComponent: 'CockpitEvidenceView',
    loaderFunction: null,
    expectedApiCalls: [...new Set(cockpitCalls)].sort(),
    domMarkers: ['战略 cockpit 页面证据', 'RC Evidence', 'evidenceMode=cockpit'],
    label: '战略 cockpit 证据页',
  });
  return surfaces;
}

function resolveImportTarget(program, fromFile, specifier) {
  const compilerOptions = program.getCompilerOptions();
  const result = ts.resolveModuleName(specifier, fromFile, compilerOptions, ts.sys);
  const resolved = result.resolvedModule?.resolvedFileName;
  if (!resolved) return null;
  return resolved.endsWith('.d.ts') ? null : path.resolve(resolved);
}

function buildImportGraph(program) {
  const sourceFiles = program.getSourceFiles().filter((sourceFile) => {
    const fileName = path.resolve(sourceFile.fileName);
    const relative = posixRelative(fileName);
    return (
      !sourceFile.isDeclarationFile
      && !isExcludedPath(fileName)
      && (relative.startsWith('src/renderer/') || relative.startsWith('src/shared/') || relative === 'src/main/preload.ts' || relative === 'src/main/main.ts')
    );
  });
  const graph = new Map();
  const reverseGraph = new Map();
  for (const sourceFile of sourceFiles) {
    const sourcePath = path.resolve(sourceFile.fileName);
    const imports = new Set();
    for (const statement of sourceFile.statements) {
      if (!ts.isImportDeclaration(statement) && !ts.isExportDeclaration(statement)) continue;
      if (!statement.moduleSpecifier) continue;
      const specifier = stringFromLiteral(statement.moduleSpecifier);
      if (!specifier || (!specifier.startsWith('.') && !specifier.startsWith('/'))) continue;
      const target = resolveImportTarget(program, sourcePath, specifier);
      if (!target) continue;
      imports.add(target);
      if (!reverseGraph.has(target)) reverseGraph.set(target, new Set());
      reverseGraph.get(target).add(sourcePath);
    }
    graph.set(sourcePath, imports);
  }
  return { sourceFiles: sourceFiles.map((file) => path.resolve(file.fileName)), graph, reverseGraph };
}

function traverseReachable(graph, roots) {
  const visited = new Set();
  const stack = [...roots];
  while (stack.length > 0) {
    const current = stack.pop();
    if (!current || visited.has(current)) continue;
    visited.add(current);
    for (const next of graph.get(current) || []) {
      if (!visited.has(next)) stack.push(next);
    }
  }
  return visited;
}

function buildRendererComponentReachability(program, uiInventory) {
  const { graph, reverseGraph, sourceFiles } = buildImportGraph(program);
  const rendererRoots = [
    path.join(projectRoot, 'src', 'renderer', 'main.tsx'),
    path.join(projectRoot, 'src', 'renderer', 'App.tsx'),
  ].map((item) => path.resolve(item));
  const productReachable = traverseReachable(graph, rendererRoots);
  const componentFiles = collectFiles(path.join(projectRoot, 'src', 'renderer', 'components'), (targetPath) => /\.(ts|tsx)$/.test(targetPath));
  const surfaceRootNames = new Map(uiInventory.map((surface) => [surface.rootComponent, surface.surfaceId]));
  const rows = [];
  for (const componentFile of componentFiles) {
    const fullPath = path.resolve(componentFile);
    const productImporters = [...(reverseGraph.get(fullPath) || new Set())].filter((importer) => !isTestFile(importer));
    const testImporters = [...(reverseGraph.get(fullPath) || new Set())].filter((importer) => isTestFile(importer));
    const classification = productReachable.has(fullPath)
      ? 'reachable'
      : testImporters.length > 0 && productImporters.length === 0
        ? 'test_only'
        : productImporters.length === 0
          ? 'orphan_component'
          : 'unreachable_component';
    rows.push({
      file: posixRelative(fullPath),
      classification,
      productReachable: productReachable.has(fullPath),
      productImporterCount: productImporters.length,
      testImporterCount: testImporters.length,
      productImporters: productImporters.map(posixRelative).join(' | '),
      testImporters: testImporters.map(posixRelative).join(' | '),
      surfaceHint: surfaceRootNames.get(path.basename(fullPath, path.extname(fullPath))) || '',
    });
  }
  return { rows, productReachable, graph, reverseGraph, sourceFiles };
}

function collectApiExports(sourceFile) {
  const exports = new Map();
  for (const statement of sourceFile.statements) {
    if (ts.isFunctionDeclaration(statement) && statement.modifiers?.some((modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword) && statement.name?.text) {
      exports.set(statement.name.text, { exportName: statement.name.text, kind: 'function', requestPath: '' });
      continue;
    }
    if (ts.isVariableStatement(statement) && statement.modifiers?.some((modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword)) {
      for (const declaration of statement.declarationList.declarations) {
        if (!ts.isIdentifier(declaration.name)) continue;
        exports.set(declaration.name.text, { exportName: declaration.name.text, kind: 'variable', requestPath: '' });
      }
    }
    if (ts.isTypeAliasDeclaration(statement) && statement.modifiers?.some((modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword)) {
      exports.set(statement.name.text, { exportName: statement.name.text, kind: 'type', requestPath: '' });
    }
  }
  return exports;
}

function normalizeApiPath(rawPath) {
  if (!rawPath) return '';
  return rawPath.replace(/\$\{[^}]+\}/g, '{param}').replace(/\/+/g, '/');
}

function collectRequestPath(expression, sourceFile) {
  let result = '';
  function visit(node) {
    if (result) return;
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'request') {
      const firstArgument = node.arguments[0];
      if (firstArgument) {
        if (ts.isStringLiteralLike(firstArgument) || ts.isNoSubstitutionTemplateLiteral(firstArgument)) {
          result = normalizeApiPath(firstArgument.text);
          return;
        }
        if (ts.isTemplateExpression(firstArgument)) {
          result = normalizeApiPath(firstArgument.getText(sourceFile).slice(1, -1));
          return;
        }
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(expression);
  return result;
}

function buildApiExportUsage(program, uiInventory) {
  const apiSourceFile = program.getSourceFile(apiPath);
  if (!apiSourceFile) throw new Error(`Missing source file ${apiPath}`);
  const exports = collectApiExports(apiSourceFile);
  const namedDeclarations = findNamedDeclarations(apiSourceFile);
  for (const [exportName, metadata] of exports.entries()) {
    const declaration = getFunctionNode(namedDeclarations, exportName);
    if (declaration) {
      const body = getFunctionLikeBody(declaration);
      if (body) metadata.requestPath = collectRequestPath(body, apiSourceFile);
    }
  }

  const productFiles = collectFiles(path.join(projectRoot, 'src', 'renderer'), (targetPath) => /\.(ts|tsx)$/.test(targetPath));
  const rows = [];
  const usageByExport = new Map();
  for (const exportName of exports.keys()) {
    usageByExport.set(exportName, {
      exportName,
      kind: exports.get(exportName).kind,
      requestPath: exports.get(exportName).requestPath,
      productCallCount: 0,
      productCallerFiles: new Set(),
      testCallCount: 0,
      testCallerFiles: new Set(),
    });
  }

  for (const targetPath of productFiles) {
    const sourceFile = program.getSourceFile(path.resolve(targetPath));
    if (!sourceFile) continue;
    const importMap = new Map();
    for (const statement of sourceFile.statements) {
      if (!ts.isImportDeclaration(statement)) continue;
      const specifier = stringFromLiteral(statement.moduleSpecifier);
      if (!specifier || !(specifier.endsWith('/lib/api') || specifier === './lib/api' || specifier === '../lib/api')) continue;
      const clause = statement.importClause;
      if (!clause?.namedBindings || !ts.isNamedImports(clause.namedBindings)) continue;
      for (const element of clause.namedBindings.elements) {
        importMap.set(element.name.text, element.propertyName?.text || element.name.text);
      }
    }
    if (!importMap.size) continue;
    function visit(node) {
      if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && importMap.has(node.expression.text)) {
        const exportName = importMap.get(node.expression.text);
        const usage = usageByExport.get(exportName);
        if (!usage) return;
        if (isTestFile(targetPath)) {
          usage.testCallCount += 1;
          usage.testCallerFiles.add(posixRelative(targetPath));
        } else {
          usage.productCallCount += 1;
          usage.productCallerFiles.add(posixRelative(targetPath));
        }
      }
      ts.forEachChild(node, visit);
    }
    visit(sourceFile);
  }

  const surfaceBindingMap = new Map();
  for (const surface of uiInventory) {
    for (const apiCall of surface.expectedApiCalls || []) {
      if (!surfaceBindingMap.has(apiCall)) surfaceBindingMap.set(apiCall, []);
      surfaceBindingMap.get(apiCall).push(surface);
    }
  }

  for (const usage of usageByExport.values()) {
    const boundSurfaces = surfaceBindingMap.get(usage.exportName) || [];
    let classification = 'unused_api_wrapper';
    if (usage.kind === 'type') {
      classification = 'type_export';
    } else if (usage.productCallCount > 0) {
      classification = (
        boundSurfaces.length > 0
          && boundSurfaces.every((surface) => surface.entryType === 'admin')
            ? 'hidden_but_reachable_admin'
            : boundSurfaces.length > 0 && boundSurfaces.every((surface) => LOW_FREQUENCY_ENTRY_TYPES.has(surface.entryType))
              ? 'hidden_but_reachable'
              : 'ui_bound'
      );
    } else if (usage.testCallCount > 0) {
      classification = 'test_only';
    } else if (boundSurfaces.length > 0) {
      classification = 'hidden_but_reachable';
    }
    rows.push({
      exportName: usage.exportName,
      kind: usage.kind,
      requestPath: usage.requestPath,
      productCallCount: usage.productCallCount,
      productCallerFiles: [...usage.productCallerFiles].sort().join(' | '),
      testCallCount: usage.testCallCount,
      testCallerFiles: [...usage.testCallerFiles].sort().join(' | '),
      boundSurfaces: boundSurfaces.map((surface) => surface.surfaceId).join(' | '),
      classification,
    });
  }

  return { rows, usageByExport };
}

function buildIpcUsage(program) {
  const preloadSourceFile = ts.createSourceFile(
    preloadPath,
    readText(preloadPath),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
  const channels = [];
  function visit(node) {
    if (ts.isCallExpression(node)
      && ts.isPropertyAccessExpression(node.expression)
      && node.expression.expression.getText(preloadSourceFile) === 'contextBridge'
      && node.expression.name.text === 'exposeInMainWorld'
    ) {
      const objectArgument = node.arguments[1];
      if (!objectArgument || !ts.isObjectLiteralExpression(objectArgument)) return;
      for (const property of objectArgument.properties) {
        if (!ts.isPropertyAssignment(property) || !property.name || !property.initializer) continue;
        const methodName = ts.isIdentifier(property.name) ? property.name.text : stringFromLiteral(property.name);
        const invokeCalls = [];
        function collectInvokes(current) {
          if (ts.isCallExpression(current)
            && ts.isPropertyAccessExpression(current.expression)
            && current.expression.expression.getText(preloadSourceFile) === 'ipcRenderer'
          ) {
            invokeCalls.push({
              method: current.expression.name.text,
              channel: stringFromLiteral(current.arguments[0]) || '',
            });
          }
          ts.forEachChild(current, collectInvokes);
        }
        collectInvokes(property.initializer);
        channels.push({
          methodName,
          ipcMethod: invokeCalls[0]?.method || '',
          channel: invokeCalls[0]?.channel || '',
        });
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(preloadSourceFile);

  const rendererFiles = collectFiles(path.join(projectRoot, 'src', 'renderer'), (targetPath) => /\.(ts|tsx)$/.test(targetPath));
  const usageCounts = new Map(channels.map((entry) => [entry.methodName, { count: 0, callers: new Set() }]));
  for (const rendererFile of rendererFiles) {
    const sourceText = readText(rendererFile);
    for (const entry of channels) {
      const matches = sourceText.match(new RegExp(`window\\.yiyuWorkbench\\.${entry.methodName}\\b`, 'g')) || [];
      if (matches.length > 0) {
        usageCounts.get(entry.methodName).count += matches.length;
        usageCounts.get(entry.methodName).callers.add(posixRelative(rendererFile));
      }
    }
  }

  return channels.map((entry) => {
    const usage = usageCounts.get(entry.methodName);
    const classification = usage.count > 0 ? 'renderer_bound' : 'unused_ipc_bridge';
    return {
      methodName: entry.methodName,
      ipcMethod: entry.ipcMethod,
      channel: entry.channel,
      rendererCallCount: usage.count,
      callerFiles: [...usage.callers].sort().join(' | '),
      classification,
    };
  });
}

function normalizeBackendPath(rawPath) {
  return rawPath.replace(/\{[^}]+\}/g, '{param}');
}

function buildBackendEndpointBinding(apiRows, uiInventory) {
  const backendSource = readText(backendMainPath);
  const endpointRegex = /@app\.(get|post|put|patch|delete)\(\s*["']([^"']+)["']/g;
  const endpoints = [];
  let match = endpointRegex.exec(backendSource);
  while (match) {
    endpoints.push({
      method: match[1].toUpperCase(),
      path: match[2],
      normalizedPath: normalizeBackendPath(match[2]),
    });
    match = endpointRegex.exec(backendSource);
  }

  const apiByPath = new Map();
  for (const row of apiRows) {
    if (!row.requestPath) continue;
    const normalizedPath = normalizeBackendPath(row.requestPath);
    if (!apiByPath.has(normalizedPath)) apiByPath.set(normalizedPath, []);
    apiByPath.get(normalizedPath).push(row);
  }

  const surfaceByApi = new Map();
  for (const surface of uiInventory) {
    for (const apiCall of surface.expectedApiCalls || []) {
      if (!surfaceByApi.has(apiCall)) surfaceByApi.set(apiCall, []);
      surfaceByApi.get(apiCall).push(surface);
    }
  }

  return endpoints.map((endpoint) => {
    const wrappers = apiByPath.get(endpoint.normalizedPath) || [];
    const boundSurfaces = [...new Set(wrappers.flatMap((wrapper) => surfaceByApi.get(wrapper.exportName) || []))];
    let classification = 'backend_only_no_ui_binding';
    if (wrappers.length > 0) {
      if (wrappers.some((wrapper) => wrapper.classification === 'ui_bound')) {
        if (boundSurfaces.length > 0 && boundSurfaces.every((surface) => surface.entryType === 'admin')) {
          classification = 'admin_only';
        } else if (boundSurfaces.length > 0 && boundSurfaces.every((surface) => LOW_FREQUENCY_ENTRY_TYPES.has(surface.entryType))) {
          classification = 'deep_link_only';
        } else {
          classification = 'ui_bound';
        }
      } else if (wrappers.every((wrapper) => wrapper.classification === 'unused_api_wrapper' || wrapper.classification === 'test_only')) {
        classification = 'api_wrapper_orphan';
      } else {
        classification = 'uncertain_needs_runtime_check';
      }
    }
    return {
      method: endpoint.method,
      endpointPath: endpoint.path,
      normalizedPath: endpoint.normalizedPath,
      classification,
      apiWrappers: wrappers.map((wrapper) => wrapper.exportName).join(' | '),
      wrapperRequestPaths: wrappers.map((wrapper) => wrapper.requestPath).join(' | '),
      boundSurfaces: boundSurfaces.map((surface) => surface.surfaceId).join(' | '),
    };
  });
}

function buildRuntimeSpec(uiInventory) {
  return uiInventory.map((surface) => ({
    surfaceId: surface.surfaceId,
    entryType: surface.entryType,
    roleConstraint: surface.roleConstraint,
    queryParamGate: surface.queryParamGate,
    domMarkers: surface.domMarkers || [],
    rootComponent: surface.rootComponent,
  }));
}

function readRuntimeAudit(targetPath) {
  if (!fs.existsSync(targetPath)) {
    return {
      hits: new Map(),
      error: null,
      generatedAt: null,
    };
  }
  try {
    const value = JSON.parse(readText(targetPath));
    const hits = Array.isArray(value?.hits) ? value.hits : [];
    return {
      hits: new Map(hits.map((hit) => [hit.surfaceId, hit])),
      error: typeof value?.error === 'string' ? value.error : null,
      generatedAt: typeof value?.generatedAt === 'string' ? value.generatedAt : null,
    };
  } catch {
    return {
      hits: new Map(),
      error: 'runtime_audit_result_parse_failed',
      generatedAt: null,
    };
  }
}

function buildUnusedAuditReport({ uiInventory, componentRows, apiRows, ipcRows, backendRows, runtimeAudit }) {
  const runtimeHitSet = new Set([...runtimeAudit.hits.values()].filter((hit) => hit.hit).map((hit) => hit.surfaceId));
  const orphanComponents = componentRows.filter((row) => row.classification === 'orphan_component');
  const unusedApiRows = apiRows.filter((row) => row.classification === 'unused_api_wrapper');
  const unusedIpcRows = ipcRows.filter((row) => row.classification === 'unused_ipc_bridge');
  const lowFrequencySurfaces = uiInventory.filter((surface) => LOW_FREQUENCY_ENTRY_TYPES.has(surface.entryType) || surface.roleConstraint !== 'any');
  const backendResidualRows = backendRows.filter((row) => row.classification === 'backend_only_no_ui_binding' || row.classification === 'api_wrapper_orphan');
  const uncertainRows = [
    ...componentRows.filter((row) => row.classification === 'unreachable_component'),
    ...apiRows.filter((row) => row.classification === 'hidden_but_reachable' || row.classification === 'hidden_but_reachable_admin'),
    ...backendRows.filter((row) => row.classification === 'uncertain_needs_runtime_check'),
  ];

  const lines = [];
  lines.push('# Unused Code Audit');
  lines.push('');
  lines.push(`- UI surfaces: ${uiInventory.length}`);
  lines.push(`- API exports with zero product callers: ${unusedApiRows.length}`);
  lines.push(`- Backend endpoints without UI binding: ${backendRows.filter((row) => row.classification === 'backend_only_no_ui_binding').length}`);
  lines.push(`- IPC bridges without renderer callers: ${unusedIpcRows.length}`);
  if (runtimeAudit.error) {
    lines.push(`- Runtime verification: blocked (${runtimeAudit.error})`);
  } else if (runtimeAudit.generatedAt) {
    lines.push(`- Runtime verification: available (${runtimeAudit.generatedAt})`);
  } else {
    lines.push('- Runtime verification: not run');
  }
  lines.push('');
  if (runtimeAudit.error) {
    lines.push('## Runtime Gate');
    lines.push('');
    lines.push('- 当前 `runtime_surface_hits.json` 是失败产物，不能把 “runtime 未命中” 直接当成死代码证据。');
    lines.push(`- 失败原因：${runtimeAudit.error}`);
    lines.push('- 这轮报告里的 `A 类` 仅对“静态无绑定”成立；若要升级成“可直接删除”，仍需补一次成功的 runtime surface hit。');
    lines.push('');
  }
  lines.push('## A 类：高置信度无用');
  lines.push('');
  if (orphanComponents.length === 0 && unusedApiRows.length === 0 && unusedIpcRows.length === 0) {
    lines.push('- 暂无。');
  } else {
    for (const row of orphanComponents) {
      lines.push(`- 组件 ${row.file}: 不在 UI surface 树、无 product importer、无 runtime 证据。`);
    }
    for (const row of unusedApiRows) {
      lines.push(`- API wrapper ${row.exportName}: 无 renderer 产品调用，路径 ${row.requestPath || '(none)'}`);
    }
    for (const row of unusedIpcRows) {
      lines.push(`- IPC bridge ${row.methodName}: channel=${row.channel || '(none)'}，renderer 无调用。`);
    }
  }
  lines.push('');
  lines.push('## B 类：低频但在用');
  lines.push('');
  if (lowFrequencySurfaces.length === 0) {
    lines.push('- 暂无。');
  } else {
    for (const surface of lowFrequencySurfaces) {
      const runtimeState = runtimeHitSet.has(surface.surfaceId) ? 'runtime_hit' : 'runtime_not_hit';
      lines.push(`- ${surface.surfaceId}: entry=${surface.entryType}, role=${surface.roleConstraint}, query=${JSON.stringify(surface.queryParamGate)}, ${runtimeState}`);
    }
  }
  lines.push('');
  lines.push('## C 类：后端或运维残留');
  lines.push('');
  if (backendResidualRows.length === 0) {
    lines.push('- 暂无。');
  } else {
    for (const row of backendResidualRows) {
      lines.push(`- ${row.method} ${row.endpointPath}: ${row.classification}, wrappers=${row.apiWrappers || '(none)'}`);
    }
  }
  lines.push('');
  lines.push('## D 类：证据不足待人工确认');
  lines.push('');
  if (uncertainRows.length === 0) {
    lines.push('- 暂无。');
  } else {
    for (const row of uncertainRows) {
      if ('file' in row) {
        lines.push(`- 组件 ${row.file}: ${row.classification}`);
      } else if ('exportName' in row) {
        lines.push(`- API wrapper ${row.exportName}: ${row.classification}`);
      } else {
        lines.push(`- Endpoint ${row.method} ${row.endpointPath}: ${row.classification}`);
      }
    }
  }
  return lines.join('\n');
}

function buildCleanupBacklog({ componentRows, apiRows, ipcRows, backendRows }) {
  const aClassComponents = componentRows.filter((row) => row.classification === 'orphan_component');
  const aClassApi = apiRows.filter((row) => row.classification === 'unused_api_wrapper');
  const aClassIpc = ipcRows.filter((row) => row.classification === 'unused_ipc_bridge');
  const backendCandidates = backendRows.filter((row) => row.classification === 'api_wrapper_orphan' || row.classification === 'backend_only_no_ui_binding');

  const lines = [];
  lines.push('# Cleanup Backlog');
  lines.push('');
  lines.push('## P0: 先确认再删');
  lines.push('');
  lines.push('- 对照 `runtime_surface_hits.json` 复核所有 `A 类` 组件 / API / IPC。');
  lines.push('- 对照 `backend_endpoint_binding.csv` 复核所有 `backend_only_no_ui_binding` endpoint 是否仍被脚本、运维或移动端使用。');
  lines.push('');
  lines.push('## P1: 前端孤儿组件');
  lines.push('');
  if (aClassComponents.length === 0) {
    lines.push('- 暂无。');
  } else {
    for (const row of aClassComponents) {
      lines.push(`- ${row.file}`);
    }
  }
  lines.push('');
  lines.push('## P1: 无调用 API wrapper');
  lines.push('');
  if (aClassApi.length === 0) {
    lines.push('- 暂无。');
  } else {
    for (const row of aClassApi) {
      lines.push(`- ${row.exportName} (${row.requestPath || 'no request path'})`);
    }
  }
  lines.push('');
  lines.push('## P1: 无调用 IPC');
  lines.push('');
  if (aClassIpc.length === 0) {
    lines.push('- 暂无。');
  } else {
    for (const row of aClassIpc) {
      lines.push(`- ${row.methodName} (${row.channel || 'no channel'})`);
    }
  }
  lines.push('');
  lines.push('## P2: 后端残留候选');
  lines.push('');
  if (backendCandidates.length === 0) {
    lines.push('- 暂无。');
  } else {
    for (const row of backendCandidates) {
      lines.push(`- ${row.method} ${row.endpointPath} -> ${row.classification}`);
    }
  }
  return lines.join('\n');
}

function main() {
  ensureDir(outputDir);
  const runtimeHitsPath = path.join(outputDir, 'runtime_surface_hits.json');
  const program = createProgram();
  const uiInventory = buildUiSurfaceInventory(program);
  const { rows: componentRows } = buildRendererComponentReachability(program, uiInventory);
  const { rows: apiRows } = buildApiExportUsage(program, uiInventory);
  const ipcRows = buildIpcUsage(program);
  const backendRows = buildBackendEndpointBinding(apiRows, uiInventory);
  const runtimeSpec = buildRuntimeSpec(uiInventory);
  const runtimeAudit = readRuntimeAudit(runtimeHitsPath);

  writeJson(path.join(outputDir, 'ui_surface_inventory.json'), uiInventory);
  writeJson(path.join(outputDir, 'runtime_surface_spec.json'), runtimeSpec);
  writeCsv(path.join(outputDir, 'renderer_component_reachability.csv'), componentRows);
  writeCsv(path.join(outputDir, 'renderer_api_export_usage.csv'), apiRows);
  writeCsv(path.join(outputDir, 'ipc_channel_usage.csv'), ipcRows);
  writeCsv(path.join(outputDir, 'backend_endpoint_binding.csv'), backendRows);
  writeText(
    path.join(outputDir, 'unused_code_audit.md'),
    buildUnusedAuditReport({ uiInventory, componentRows, apiRows, ipcRows, backendRows, runtimeAudit }),
  );
  writeText(
    path.join(outputDir, 'cleanup_backlog.md'),
    buildCleanupBacklog({ componentRows, apiRows, ipcRows, backendRows }),
  );

  const summary = {
    outputDir: posixRelative(outputDir),
    uiSurfaceCount: uiInventory.length,
    zeroProductApiExportCount: apiRows.filter((row) => row.classification === 'unused_api_wrapper').length,
    backendOnlyEndpointCount: backendRows.filter((row) => row.classification === 'backend_only_no_ui_binding').length,
    unusedIpcBridgeCount: ipcRows.filter((row) => row.classification === 'unused_ipc_bridge').length,
    orphanComponentCount: componentRows.filter((row) => row.classification === 'orphan_component').length,
    runtimeAuditError: runtimeAudit.error,
    runtimeHitCount: [...runtimeAudit.hits.values()].filter((row) => row.hit).length,
  };
  writeJson(path.join(outputDir, 'summary.json'), summary);
  console.log(JSON.stringify(summary, null, 2));
}

main();
