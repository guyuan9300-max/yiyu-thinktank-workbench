#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import {
  APP_NAME,
  computeManifestId,
  findBannedRendererCopyViolations,
  findPackagedContentViolations,
  inspectAppBundle,
  inspectBackendCapabilities,
  inspectPackagedRuntimeSeed,
  resolveAppManifestPath,
  sha256File,
} from './app-manifest.mjs';

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const targetApp = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(projectRoot, 'dist', 'mac-arm64', APP_NAME);
const PYTHON_STARTUP_SMOKE_TIMEOUT_MS = 60_000;
const PYTHON_VENV_CREATE_TIMEOUT_MS = 60_000;

const COLLAB_REQUIRED_RENDERER_TEXT = [
  '发布我的修改到协作分支',
  '预览 main 和协作分支修改',
];

function sanitizedPythonEnv(extra = {}) {
  const env = { ...process.env, PYTHONDONTWRITEBYTECODE: '1', ...extra };
  delete env.PYTHONHOME;
  delete env.PYTHONPATH;
  delete env.PYTHONEXECUTABLE;
  delete env.__PYVENV_LAUNCHER__;
  return env;
}

function summarizeOutput(value, maxLength = 1600) {
  const text = String(value || '').trim().replace(/\s+/g, ' ');
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength)}...`;
}

function summarizeSpawnFailure(result, detail = '') {
  const suffix = detail ? `; ${detail}` : '';
  if (result.error) {
    const signal = result.signal ? `; signal=${result.signal}` : '; signal=none';
    return `${result.error.message}${signal}${suffix}`;
  }
  const status = typeof result.status === 'number' ? result.status : 'unknown';
  const signal = result.signal ? String(result.signal) : 'none';
  return `exit=${status}; signal=${signal}; stderr=${summarizeOutput(result.stderr)}; stdout=${summarizeOutput(result.stdout)}${suffix}`;
}

function verifyCodeSignature(appPath) {
  if (process.platform !== 'darwin') {
    return {
      ok: true,
      skipped: true,
    };
  }

  const result = spawnSync('codesign', ['--verify', '--deep', '--strict', '--verbose=2', appPath], {
    encoding: 'utf8',
    timeout: 30_000,
  });
  if (result.error || result.status !== 0) {
    return {
      ok: false,
      error: summarizeSpawnFailure(result),
    };
  }
  return {
    ok: true,
    skipped: false,
    output: summarizeOutput(`${result.stdout || ''}${result.stderr || ''}`),
  };
}

function runPythonSmoke(pythonExecutable, env) {
  const startedAt = Date.now();
  const result = spawnSync(
    pythonExecutable,
    ['-B', '-c', 'import encodings, sys; print(sys.prefix); print(sys.base_prefix)'],
    {
      cwd: projectRoot,
      env,
      encoding: 'utf8',
      timeout: PYTHON_STARTUP_SMOKE_TIMEOUT_MS,
    },
  );
  if (result.error || result.status !== 0) {
    return {
      ok: false,
      error: summarizeSpawnFailure(
        result,
        `timeoutMs=${PYTHON_STARTUP_SMOKE_TIMEOUT_MS}; elapsedMs=${Date.now() - startedAt}`,
      ),
    };
  }
  return { ok: true, stdout: String(result.stdout || '').trim() };
}

function readPyVenvConfigValue(venvPath, key) {
  const configPath = path.join(venvPath, 'pyvenv.cfg');
  if (!fs.existsSync(configPath)) {
    return null;
  }
  const expectedKey = key.toLowerCase();
  for (const line of fs.readFileSync(configPath, 'utf8').split(/\r?\n/)) {
    const match = line.match(/^\s*([^=]+?)\s*=\s*(.*)$/);
    if (match && match[1].trim().toLowerCase() === expectedKey) {
      return match[2].trim();
    }
  }
  return null;
}

function verifyRuntimePythonStartup(runtimeSeed) {
  const seedSmoke = runPythonSmoke(runtimeSeed.pythonExecutable, sanitizedPythonEnv());
  if (!seedSmoke.ok) {
    return {
      match: false,
      missing: [`seed python failed startup smoke: ${seedSmoke.error}`],
    };
  }

  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'yiyu-packaged-runtime-'));
  const venvPath = path.join(tempRoot, 'backend-venv');
  try {
    const createResult = spawnSync(
      runtimeSeed.pythonExecutable,
      ['-B', '-m', 'venv', '--without-pip', '--copies', venvPath],
      {
        cwd: projectRoot,
        env: sanitizedPythonEnv(),
        encoding: 'utf8',
        timeout: PYTHON_VENV_CREATE_TIMEOUT_MS,
      },
    );
    if (createResult.error || createResult.status !== 0) {
      return {
        match: false,
        missing: [`venv creation failed: ${summarizeSpawnFailure(createResult, `timeoutMs=${PYTHON_VENV_CREATE_TIMEOUT_MS}`)}`],
      };
    }

    const venvLibDir = path.join(venvPath, 'lib');
    fs.mkdirSync(venvLibDir, { recursive: true });
    if (fs.existsSync(runtimeSeed.pythonLib)) {
      fs.copyFileSync(runtimeSeed.pythonLib, path.join(venvLibDir, path.basename(runtimeSeed.pythonLib)));
    }

    const venvPython = path.join(venvPath, 'bin', 'python');
    const venvSmoke = runPythonSmoke(venvPython, sanitizedPythonEnv({ VIRTUAL_ENV: venvPath }));
    if (!venvSmoke.ok) {
      return {
        match: false,
        missing: [`venv python failed startup smoke: ${venvSmoke.error}`],
      };
    }

    return {
      match: true,
      missing: [],
      seedSmokeStdout: seedSmoke.stdout,
      venvSmokeStdout: venvSmoke.stdout,
      venvHome: readPyVenvConfigValue(venvPath, 'home'),
      venvExecutable: readPyVenvConfigValue(venvPath, 'executable'),
    };
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
}

function inspectInternalCollabPackaging(appPath) {
  const appRoot = path.join(appPath, 'Contents', 'Resources', 'app');
  const collabMainModule = path.join(appRoot, 'build', 'main', 'collabGit.js');
  const missing = [];
  if (!fs.existsSync(collabMainModule)) {
    missing.push(`missing collaboration sync main module: ${collabMainModule}`);
  }

  const foundRendererText = new Set();
  const rendererAssetsDir = path.join(appRoot, 'dist', 'renderer', 'assets');
  if (!fs.existsSync(rendererAssetsDir)) {
    missing.push(`missing renderer assets directory: ${rendererAssetsDir}`);
    return { match: false, missing };
  }
  for (const name of fs.readdirSync(rendererAssetsDir)) {
    if (!name.endsWith('.js')) continue;
    const assetPath = path.join(rendererAssetsDir, name);
    const text = fs.readFileSync(assetPath, 'utf8');
    for (const marker of COLLAB_REQUIRED_RENDERER_TEXT) {
      if (text.includes(marker)) {
        foundRendererText.add(marker);
      }
    }
  }
  for (const marker of COLLAB_REQUIRED_RENDERER_TEXT) {
    if (!foundRendererText.has(marker)) {
      missing.push(`missing collaboration sync renderer copy: ${marker}`);
    }
  }
  return { match: missing.length === 0, missing };
}

if (!fs.existsSync(targetApp)) {
  console.error(`[verify-packaged-app] app bundle not found: ${targetApp}`);
  process.exit(1);
}

const codeSignature = verifyCodeSignature(targetApp);
if (!codeSignature.ok) {
  console.error(`[verify-packaged-app] invalid macOS code signature: ${codeSignature.error}`);
  process.exit(1);
}

const inspection = inspectAppBundle(targetApp);
if (!inspection.manifest) {
  console.error(`[verify-packaged-app] missing version manifest: ${resolveAppManifestPath(targetApp)}`);
  process.exit(1);
}

const rendererPath = path.join(
  targetApp,
  'Contents',
  'Resources',
  'app',
  'dist',
  'renderer',
  'assets',
  inspection.manifest.rendererEntry,
);
if (!fs.existsSync(rendererPath)) {
  console.error(`[verify-packaged-app] renderer entry missing: ${rendererPath}`);
  process.exit(1);
}

const rendererHash = sha256File(rendererPath);
if (rendererHash !== inspection.manifest.rendererHash) {
  console.error(
    `[verify-packaged-app] renderer hash mismatch: manifest=${inspection.manifest.rendererHash} actual=${rendererHash}`,
  );
  process.exit(1);
}

const bannedCopyViolations = findBannedRendererCopyViolations(targetApp);
if (bannedCopyViolations.length > 0) {
  console.error('[verify-packaged-app] bundled renderer contains banned legacy copy:');
  for (const item of bannedCopyViolations) {
    console.error(` - ${item}`);
  }
  process.exit(1);
}

const packagedContentViolations = findPackagedContentViolations(targetApp);
if (packagedContentViolations.length > 0) {
  console.error('[verify-packaged-app] bundled app contains local data or generated artifacts:');
  for (const item of packagedContentViolations) {
    console.error(` - ${item}`);
  }
  process.exit(1);
}

const internalCollabPackaging = inspectInternalCollabPackaging(targetApp);
if (!internalCollabPackaging.match) {
  console.error('[verify-packaged-app] bundled app is missing collaboration sync runtime or UI copy:');
  for (const item of internalCollabPackaging.missing) {
    console.error(` - ${item}`);
  }
  process.exit(1);
}

const backendCapability = inspectBackendCapabilities(targetApp);
if (!backendCapability.match) {
  console.error('[verify-packaged-app] bundled backend is missing required workspace consultant synthesis symbols:');
  for (const item of backendCapability.missingSymbols) {
    console.error(` - ${item}`);
  }
  process.exit(1);
}

const runtimeSeed = inspectPackagedRuntimeSeed(targetApp);
if (!runtimeSeed.match) {
  console.error('[verify-packaged-app] packaged runtime seed is incomplete or stale:');
  for (const item of runtimeSeed.missing) {
    console.error(` - ${item}`);
  }
  process.exit(1);
}

const runtimeStartup = verifyRuntimePythonStartup(runtimeSeed);
if (!runtimeStartup.match) {
  console.error('[verify-packaged-app] packaged runtime cannot start Python or create a backend venv:');
  for (const item of runtimeStartup.missing) {
    console.error(` - ${item}`);
  }
  process.exit(1);
}

console.log(
  JSON.stringify(
    {
      appPath: targetApp,
      bundleManifestId: computeManifestId(inspection.manifest),
      rendererEntry: inspection.manifest.rendererEntry,
      rendererHash,
      packagedContentClean: true,
      internalCollabAvailable: true,
      backendCapabilityMatch: backendCapability.match,
      runtimeSeedManifest: runtimeSeed.manifestPath,
      runtimeSeedPython: runtimeSeed.pythonExecutable,
      runtimeSeedWheelFileCount: runtimeSeed.wheelFileCount,
      runtimeSeedRequirementsHashMatch: runtimeSeed.requirementsHashMatch,
      runtimeSeedWheelhouseHashMatch: runtimeSeed.wheelhouseHashMatch,
      codeSignatureValid: true,
      codeSignatureCheckSkipped: Boolean(codeSignature.skipped),
      runtimePythonStartupSmoke: true,
      runtimeSeedSmokeStdout: runtimeStartup.seedSmokeStdout,
      runtimeVenvSmokeStdout: runtimeStartup.venvSmokeStdout,
      runtimeVenvHome: runtimeStartup.venvHome,
      runtimeVenvExecutable: runtimeStartup.venvExecutable,
    },
    null,
    2,
  ),
);
