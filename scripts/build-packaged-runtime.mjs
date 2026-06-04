#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  RUNTIME_BACKEND_REQUIREMENTS_FILE,
  RUNTIME_BACKEND_VENV_DIR,
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
// B 方案:预装 venv 路径,build 阶段就 install 好所有依赖
const backendVenvDir = path.join(runtimeRoot, RUNTIME_BACKEND_VENV_DIR);
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

function requireSupportedRuntimePlatform() {
  const supported = (
    (process.platform === 'darwin' && process.arch === 'arm64')
    || (process.platform === 'win32' && process.arch === 'x64')
  );
  if (!supported) {
    throw new Error(`packaged runtime seed supports darwin/arm64 and win32/x64; got ${process.platform}/${process.arch}`);
  }
}

function findDeveloperIdCert(teamId) {
  try {
    const out = execFileSync('security', ['find-identity', '-p', 'codesigning', '-v'], { encoding: 'utf8' });
    const line = out.split('\n').find((l) => l.includes('Developer ID Application') && l.includes(teamId));
    if (!line) return null;
    const m = line.match(/"(Developer ID Application:[^"]+)"/);
    return m ? m[1] : null;
  } catch {
    return null;
  }
}

function findMachoFiles(rootDir) {
  // 递归查 .so / .dylib;不签 bin/ 内可执行(留给 electron-builder + python launcher 处理)
  const out = [];
  const stack = [rootDir];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isSymbolicLink()) continue;
      if (entry.isDirectory()) {
        stack.push(full);
        continue;
      }
      if (entry.isFile() && (entry.name.endsWith('.so') || entry.name.endsWith('.dylib'))) {
        out.push(full);
      }
    }
  }
  return out;
}

function resolveUvManagedPython() {
  const raw = run('uv', ['python', 'find', '3.11']).trim();
  if (!raw) {
    throw new Error('uv did not return a CPython 3.11 path');
  }
  const pythonPath = fs.realpathSync(raw);
  let seedRoot;
  let executableRelative;
  let stdlibCheckRelative;
  let dynamicLibraryRelative = null;
  if (process.platform === 'win32') {
    const baseName = path.basename(pythonPath).toLowerCase();
    if (baseName !== 'python.exe') {
      throw new Error(`expected uv-managed python.exe executable, got: ${pythonPath}`);
    }
    const exeDir = path.dirname(pythonPath);
    seedRoot = fs.existsSync(path.join(exeDir, 'Lib', 'encodings', '__init__.py'))
      ? exeDir
      : path.dirname(exeDir);
    executableRelative = path.relative(seedRoot, pythonPath) || 'python.exe';
    stdlibCheckRelative = path.join('Lib', 'encodings', '__init__.py');
    const pythonDll = fs.readdirSync(seedRoot).find((name) => /^python3\d+\.dll$/i.test(name));
    if (pythonDll) dynamicLibraryRelative = pythonDll;
  } else {
    if (!pythonPath.endsWith('/bin/python3.11')) {
      throw new Error(`expected uv-managed python3.11 executable, got: ${pythonPath}`);
    }
    seedRoot = path.dirname(path.dirname(pythonPath));
    executableRelative = path.join('bin', 'python3.11');
    stdlibCheckRelative = path.join('lib', 'python3.11', 'encodings', '__init__.py');
    dynamicLibraryRelative = path.join('lib', 'libpython3.11.dylib');
  }
  if (!fs.existsSync(path.join(seedRoot, stdlibCheckRelative))) {
    throw new Error(`invalid uv-managed CPython seed root: ${seedRoot}`);
  }
  return {
    pythonPath,
    seedRoot,
    executableRelative,
    stdlibCheckRelative,
    dynamicLibraryRelative,
    version: run(pythonPath, ['--version']).trim(),
  };
}

function venvPythonRelative() {
  return process.platform === 'win32' ? path.join('Scripts', 'python.exe') : path.join('bin', 'python');
}

function venvUvicornRelative() {
  return process.platform === 'win32' ? path.join('Scripts', 'uvicorn.exe') : path.join('bin', 'uvicorn');
}

function venvScriptsDirRelative() {
  return process.platform === 'win32' ? 'Scripts' : 'bin';
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

function directorySizeBytes(rootPath) {
  if (!fs.existsSync(rootPath)) return 0;
  let size = 0;
  const visit = (entryPath) => {
    const stat = fs.lstatSync(entryPath);
    if (stat.isSymbolicLink()) return;
    if (stat.isDirectory()) {
      for (const child of fs.readdirSync(entryPath)) {
        visit(path.join(entryPath, child));
      }
      return;
    }
    size += stat.size;
  };
  visit(rootPath);
  return size;
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
  requireSupportedRuntimePlatform();
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

  // B 方案根治:在 build 阶段就预装完整 venv,不再依赖客户机首次启动跑 pip install。
  // 这样 .whl 不会被打进 .app,Apple 公证不会再因为 wheel 内嵌 .so 没签名被拒。
  // venv 用 --copies (而不是 symlink) + seed python,客户机 cp -r 后改一下 pyvenv.cfg 即可使用。
  console.log('[build-packaged-runtime] creating pre-built backend-venv');
  // 用 packaged-runtime 里拷过来的 seed python 创建 venv —— 保证版本一致
  const seedPythonPath = path.join(pythonSeedDir, python.executableRelative);
  if (!fs.existsSync(seedPythonPath)) {
    throw new Error(`seed python missing after copy: ${seedPythonPath}`);
  }
  fs.rmSync(backendVenvDir, { recursive: true, force: true });
  run(seedPythonPath, ['-m', 'venv', '--copies', '--without-pip', backendVenvDir], { stdio: 'inherit' });

  // macOS 的 python-build-standalone 需要把 libpython 带进 venv lib/。
  if (process.platform === 'darwin' && python.dynamicLibraryRelative) {
    const seedLibPython = path.join(pythonSeedDir, python.dynamicLibraryRelative);
    const venvLibPython = path.join(backendVenvDir, 'lib', path.basename(python.dynamicLibraryRelative));
    if (fs.existsSync(seedLibPython)) {
      fs.mkdirSync(path.dirname(venvLibPython), { recursive: true });
      fs.copyFileSync(seedLibPython, venvLibPython);
    }
  }

  const venvPython = path.join(backendVenvDir, venvPythonRelative());
  // ensurepip 装 pip,然后 offline install 所有依赖到 venv site-packages
  run(venvPython, ['-m', 'ensurepip', '--upgrade', '--default-pip'], {
    stdio: 'inherit',
    env: { ...process.env, VIRTUAL_ENV: backendVenvDir },
  });
  console.log('[build-packaged-runtime] installing dependencies into pre-built venv');
  run(
    venvPython,
    [
      '-m',
      'pip',
      'install',
      '--no-index',
      '--find-links',
      wheelhouseDir,
      '--requirement',
      requirementsPath,
    ],
    {
      stdio: 'inherit',
      env: { ...process.env, VIRTUAL_ENV: backendVenvDir },
    },
  );

  // 关键:venv 的 pyvenv.cfg 此时 home= 指向 dist/packaged-runtime/python-seed/bin。
  // 客户机解压后这个绝对路径不存在,runtime 端会重写它。这里只清理 build 机硬编码痕迹。
  const pyvenvCfgPath = path.join(backendVenvDir, 'pyvenv.cfg');
  if (fs.existsSync(pyvenvCfgPath)) {
    const original = fs.readFileSync(pyvenvCfgPath, 'utf8');
    // 用一个占位符,runtime 端 ensurePackagedBackendRuntime 启动时再改成绝对路径
    const seedHomePlaceholder = process.platform === 'win32'
      ? '__YIYU_RUNTIME_HOME__'
      : '__YIYU_RUNTIME_HOME__';
    const replaced = original
      .replace(/^home = .*$/m, `home = ${seedHomePlaceholder}`)
      .replace(/^executable = .*$/m, 'executable = __YIYU_RUNTIME_EXECUTABLE__')
      .replace(/^command = .*$/m, 'command = __YIYU_RUNTIME_COMMAND__');
    fs.writeFileSync(pyvenvCfgPath, replaced);
  }

  // B 方案核心:venv 已经预装好,wheelhouse 不再需要进 .app。
  // 删 wheelhouse 目录,避免 .whl 内嵌的未签名 .so/.dylib 让 Apple 公证拒收。
  console.log('[build-packaged-runtime] removing wheelhouse (already installed into pre-built venv)');
  fs.rmSync(wheelhouseDir, { recursive: true, force: true });

  // B 方案关键:清理 venv 里所有 __pycache__/*.pyc 文件。
  // 不删的话,electron-builder 会逐个 codesign .pyc 文件(几万个),
  // 每个 codesign 调用要 100-500ms 走 timestamp 服务器,加起来要几小时,根本跑不完。
  // .pyc 是缓存,客户机首次 import 时 Python 会自动重新生成,无功能损失。
  // 顺带省 ~150MB 体积。
  console.log('[build-packaged-runtime] removing __pycache__ from venv (avoid codesign storm)');
  function rmPycacheDirs(rootDir) {
    if (!fs.existsSync(rootDir)) return 0;
    let removed = 0;
    const stack = [rootDir];
    while (stack.length) {
      const dir = stack.pop();
      let entries;
      try {
        entries = fs.readdirSync(dir, { withFileTypes: true });
      } catch {
        continue;
      }
      for (const entry of entries) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          if (entry.name === '__pycache__') {
            fs.rmSync(full, { recursive: true, force: true });
            removed++;
          } else {
            stack.push(full);
          }
        } else if (entry.name.endsWith('.pyc')) {
          // 顶层散落 .pyc(罕见,稳妥处理)
          try { fs.rmSync(full, { force: true }); } catch {}
        }
      }
    }
    return removed;
  }
  const removedPycacheCount = rmPycacheDirs(backendVenvDir);
  console.log(`[build-packaged-runtime] removed ${removedPycacheCount} __pycache__ dirs from venv`);

  // Apple 公证关键:venv 内 .so/.dylib 是 pip 装时由 macOS ld 自动加的 ad-hoc/linker-signed,
  // Apple notary 会拒(无 Developer ID + 无 secure timestamp),触发 In Progress 卡死。
  // 在 build 阶段就用 Developer ID 重签,electron-builder 后续打包不会破坏内部签名。
  // 仅当显式提供了证书时才签——开发本地构建 (dist:mac-local) 不需要,跳过即可。
  const devIdCert = process.platform === 'darwin' ? (process.env.APPLE_DEVELOPER_ID_APPLICATION
    || process.env.CSC_NAME
    || (process.env.APPLE_TEAM_ID ? findDeveloperIdCert(process.env.APPLE_TEAM_ID) : null)) : null;
  if (devIdCert) {
    console.log(`[build-packaged-runtime] signing venv .so/.dylib with: ${devIdCert}`);
    const machos = findMachoFiles(backendVenvDir);
    console.log(`[build-packaged-runtime] found ${machos.length} Mach-O files to sign`);
    let signedCount = 0;
    let failedCount = 0;
    const failedSamples = [];
    for (const file of machos) {
      try {
        execFileSync(
          'codesign',
          [
            '--force',
            '--timestamp',
            '--options', 'runtime',
            '--sign', devIdCert,
            file,
          ],
          { stdio: 'pipe', encoding: 'utf8' },
        );
        signedCount++;
        if (signedCount % 25 === 0) {
          console.log(`[build-packaged-runtime]   signed ${signedCount}/${machos.length}`);
        }
      } catch (error) {
        failedCount++;
        if (failedSamples.length < 5) {
          failedSamples.push(`${file}: ${error.message?.split('\n')[0] || error}`);
        }
      }
    }
    console.log(`[build-packaged-runtime] signing done: ${signedCount} signed, ${failedCount} failed`);
    if (failedCount > 0) {
      console.error('[build-packaged-runtime] signing failures (sample):');
      for (const s of failedSamples) console.error('  ' + s);
      throw new Error(`Developer ID signing failed for ${failedCount} files`);
    }
  } else {
    console.log('[build-packaged-runtime] no APPLE_DEVELOPER_ID_APPLICATION/CSC_NAME/APPLE_TEAM_ID; skipping .so/.dylib signing (local-only build path)');
  }

  const manifest = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    platform: process.platform,
    arch: process.arch,
    python: {
      sourcePath: python.seedRoot,
      seedPath: RUNTIME_PYTHON_SEED_DIR,
      executable: path.join(RUNTIME_PYTHON_SEED_DIR, python.executableRelative),
      stdlibCheck: path.join(RUNTIME_PYTHON_SEED_DIR, python.stdlibCheckRelative),
      dynamicLibrary: python.dynamicLibraryRelative ? path.join(RUNTIME_PYTHON_SEED_DIR, python.dynamicLibraryRelative) : null,
      venvPython: venvPythonRelative(),
      venvUvicorn: venvUvicornRelative(),
      venvScriptsDir: venvScriptsDirRelative(),
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
    // B 方案:预装 venv 元数据,客户机首次启动按这个 hash 校验完整性
    backendVenv: {
      path: RUNTIME_BACKEND_VENV_DIR,
      sha256: sha256Directory(backendVenvDir),
      fileCount: countFiles(backendVenvDir),
    },
  };

  writeJsonFile(manifestPath, manifest);
  console.log(JSON.stringify({
    runtimeRoot,
    manifestPath,
    pythonVersion: manifest.python.version,
    pythonFileCount: manifest.python.fileCount,
    wheelFileCount: manifest.wheelhouse.fileCount,
    backendVenvFileCount: manifest.backendVenv.fileCount,
    backendVenvSha256: manifest.backendVenv.sha256,
    requirementsSha256: manifest.backend.requirementsSha256,
    wheelhouseSha256: manifest.wheelhouse.sha256,
    sizeBytes: directorySizeBytes(runtimeRoot),
  }, null, 2));
}

try {
  main();
} catch (error) {
  console.error(`[build-packaged-runtime] ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
}
