#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  RUNTIME_BACKEND_REQUIREMENTS_FILE,
  RUNTIME_PYTHON_SEED_DIR,
  RUNTIME_SEED_MANIFEST_FILE,
  RUNTIME_WHEELHOUSE_DIR,
  sha256Directory,
  sha256File,
  writeJsonFile,
} from './app-manifest.mjs';

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const runtimeRoot = path.join(projectRoot, 'dist', 'packaged-runtime');
const pythonSeedDir = path.join(runtimeRoot, RUNTIME_PYTHON_SEED_DIR);
const wheelhouseDir = path.join(runtimeRoot, RUNTIME_WHEELHOUSE_DIR);
const requirementsPath = path.join(runtimeRoot, RUNTIME_BACKEND_REQUIREMENTS_FILE);
const binaryRequirementsPath = path.join(runtimeRoot, 'backend-requirements-binary.txt');
const manifestPath = path.join(runtimeRoot, RUNTIME_SEED_MANIFEST_FILE);
const sourceWheelPackages = new Set(['crcmod', 'tos']);
const extraBinaryWheelSpecs = ['sherpa-onnx-core==1.13.1'];

function run(command, args, options = {}) {
  return execFileSync(command, args, {
    cwd: options.cwd ?? projectRoot,
    env: options.env ?? process.env,
    encoding: 'utf8',
    stdio: options.stdio ?? 'pipe',
  });
}

function requireMacArm64() {
  if (process.platform !== 'darwin' || process.arch !== 'arm64') {
    throw new Error(`packaged runtime seed currently supports macOS arm64 only; got ${process.platform}/${process.arch}`);
  }
}

function resolveUvManagedPython() {
  const raw = run('uv', ['python', 'find', '3.11']).trim();
  if (!raw) {
    throw new Error('uv did not return a CPython 3.11 path');
  }
  const pythonPath = fs.realpathSync(raw);
  if (!pythonPath.endsWith('/bin/python3.11')) {
    throw new Error(`expected uv-managed python3.11 executable, got: ${pythonPath}`);
  }
  const seedRoot = path.dirname(path.dirname(pythonPath));
  if (!fs.existsSync(path.join(seedRoot, 'lib', 'python3.11'))) {
    throw new Error(`invalid uv-managed CPython seed root: ${seedRoot}`);
  }
  return {
    pythonPath,
    seedRoot,
    version: run(pythonPath, ['--version']).trim(),
  };
}

function countFiles(rootPath, predicate = () => true) {
  if (!fs.existsSync(rootPath)) return 0;
  let count = 0;
  const visit = (entryPath) => {
    const stat = fs.lstatSync(entryPath);
    if (stat.isSymbolicLink()) {
      count += predicate(entryPath) ? 1 : 0;
      return;
    }
    if (stat.isDirectory()) {
      for (const child of fs.readdirSync(entryPath)) {
        visit(path.join(entryPath, child));
      }
      return;
    }
    count += predicate(entryPath) ? 1 : 0;
  };
  visit(rootPath);
  return count;
}

function requirementName(line) {
  const match = line.match(/^([A-Za-z0-9_.-]+)\s*(?:==|~=|>=|<=|>|<|!=)/);
  return match ? match[1].toLowerCase().replaceAll('_', '-') : null;
}

function writeBinaryOnlyRequirements() {
  const lines = fs.readFileSync(requirementsPath, 'utf8').split(/\r?\n/);
  const output = [];
  const sourceSpecs = [];
  let skippingSourceOnlyBlock = false;
  for (const line of lines) {
    const name = requirementName(line);
    if (name) {
      skippingSourceOnlyBlock = sourceWheelPackages.has(name);
      if (skippingSourceOnlyBlock) {
        sourceSpecs.push(line);
        continue;
      }
    } else if (skippingSourceOnlyBlock && (line.startsWith(' ') || line.startsWith('\t'))) {
      continue;
    } else if (line.trim() !== '') {
      skippingSourceOnlyBlock = false;
    }
    output.push(line);
  }
  fs.writeFileSync(binaryRequirementsPath, output.join('\n'));
  return sourceSpecs;
}

function main() {
  requireMacArm64();
  const python = resolveUvManagedPython();
  fs.rmSync(runtimeRoot, { recursive: true, force: true });
  fs.mkdirSync(runtimeRoot, { recursive: true });

  console.log(`[build-packaged-runtime] copying CPython seed from ${python.seedRoot}`);
  fs.cpSync(python.seedRoot, pythonSeedDir, {
    recursive: true,
    force: true,
    verbatimSymlinks: true,
  });

  console.log('[build-packaged-runtime] exporting backend locked requirements');
  run(
    'uv',
    [
      'export',
      '--project',
      'backend',
      '--locked',
      '--format',
      'requirements.txt',
      '--no-hashes',
      '--no-dev',
      '--no-emit-project',
      '--output-file',
      requirementsPath,
    ],
    { stdio: 'inherit' },
  );

  console.log('[build-packaged-runtime] downloading offline wheelhouse');
  const sourceSpecs = writeBinaryOnlyRequirements();
  fs.mkdirSync(wheelhouseDir, { recursive: true });
  run(
    python.pythonPath,
    [
      '-m',
      'pip',
      'download',
      '--only-binary=:all:',
      '--no-deps',
      '--dest',
      wheelhouseDir,
      '--requirement',
      binaryRequirementsPath,
    ],
    { stdio: 'inherit' },
  );
  if (extraBinaryWheelSpecs.length > 0) {
    console.log(`[build-packaged-runtime] downloading extra runtime wheels: ${extraBinaryWheelSpecs.join(', ')}`);
    run(
      python.pythonPath,
      [
        '-m',
        'pip',
        'download',
        '--only-binary=:all:',
        '--no-deps',
        '--dest',
        wheelhouseDir,
        ...extraBinaryWheelSpecs,
      ],
      { stdio: 'inherit' },
    );
  }
  for (const requirementSpec of sourceSpecs) {
    const packageName = requirementName(requirementSpec);
    console.log(`[build-packaged-runtime] building source-only wheel: ${requirementSpec}`);
    run(
      python.pythonPath,
      [
        '-m',
        'pip',
        'wheel',
        '--no-deps',
        '--no-binary',
        packageName ?? ':all:',
        '--wheel-dir',
        wheelhouseDir,
        requirementSpec,
      ],
      { stdio: 'inherit' },
    );
  }

  const manifest = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    platform: process.platform,
    arch: process.arch,
    python: {
      sourcePath: python.seedRoot,
      seedPath: RUNTIME_PYTHON_SEED_DIR,
      executable: path.join(RUNTIME_PYTHON_SEED_DIR, 'bin', 'python3.11'),
      version: python.version,
      platform: `${process.platform}-${process.arch}`,
      treeSha256: sha256Directory(pythonSeedDir),
      fileCount: countFiles(pythonSeedDir),
    },
    backend: {
      requirementsPath: RUNTIME_BACKEND_REQUIREMENTS_FILE,
      requirementsSha256: sha256File(requirementsPath),
      pyprojectSha256: sha256File(path.join(projectRoot, 'backend', 'pyproject.toml')),
      uvLockSha256: sha256File(path.join(projectRoot, 'backend', 'uv.lock')),
    },
    wheelhouse: {
      path: RUNTIME_WHEELHOUSE_DIR,
      sha256: sha256Directory(wheelhouseDir),
      fileCount: countFiles(wheelhouseDir, (entryPath) => entryPath.toLowerCase().endsWith('.whl')),
    },
  };

  writeJsonFile(manifestPath, manifest);
  console.log(JSON.stringify({
    runtimeRoot,
    manifestPath,
    pythonVersion: manifest.python.version,
    pythonFileCount: manifest.python.fileCount,
    wheelFileCount: manifest.wheelhouse.fileCount,
    requirementsSha256: manifest.backend.requirementsSha256,
    wheelhouseSha256: manifest.wheelhouse.sha256,
    size: run('du', ['-sh', runtimeRoot]).trim(),
  }, null, 2));
}

try {
  main();
} catch (error) {
  console.error(`[build-packaged-runtime] ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
}
