#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import { APP_DISPLAY_NAME, APP_NAME, sha256File } from './app-manifest.mjs';

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const packageJsonPath = path.join(projectRoot, 'package.json');
const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));

const appCandidates = [
  path.join(projectRoot, 'dist', `mac-${process.arch}`, APP_NAME),
  path.join(projectRoot, 'dist', 'mac-arm64', APP_NAME),
  path.join(projectRoot, 'dist', 'mac', APP_NAME),
];
const inputAppPath = process.argv[2] ? path.resolve(process.argv[2]) : appCandidates.find((item) => fs.existsSync(item));
const outputDmgPath = process.argv[3]
  ? path.resolve(process.argv[3])
  : path.join(projectRoot, 'dist', `${APP_DISPLAY_NAME}-${packageJson.version}-${process.arch}.dmg`);

function fail(message) {
  console.error(`[package-local-mac-dmg] ${message}`);
  process.exit(1);
}

function run(command, args, { stdio = 'inherit', allowFailure = false } = {}) {
  const result = spawnSync(command, args, { stdio, encoding: 'utf8' });
  if (result.error) {
    if (allowFailure) return result;
    fail(`${command} failed: ${result.error.message}`);
  }
  if (result.status !== 0 && !allowFailure) {
    const detail = `${result.stdout || ''}${result.stderr || ''}`.trim();
    fail(`${command} ${args.join(' ')} exited with status ${result.status}${detail ? `: ${detail}` : ''}`);
  }
  return result;
}

if (process.platform !== 'darwin') {
  fail('This script only supports macOS.');
}

if (!inputAppPath || !fs.existsSync(inputAppPath) || !inputAppPath.endsWith('.app')) {
  fail(`App bundle not found: ${inputAppPath || appCandidates.join(', ')}`);
}

fs.mkdirSync(path.dirname(outputDmgPath), { recursive: true });
if (fs.existsSync(outputDmgPath)) {
  fs.rmSync(outputDmgPath, { force: true });
}

const stagingRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'yiyu-local-dmg-'));
try {
  const stagedAppPath = path.join(stagingRoot, APP_NAME);
  run('ditto', [inputAppPath, stagedAppPath]);
  run(process.execPath, [path.join(projectRoot, 'scripts', 'stabilize-mac-app.mjs'), stagedAppPath]);
  run(process.execPath, [path.join(projectRoot, 'scripts', 'verify-packaged-app.mjs'), stagedAppPath]);
  fs.symlinkSync('/Applications', path.join(stagingRoot, 'Applications'));

  run('hdiutil', [
    'create',
    '-volname',
    APP_DISPLAY_NAME,
    '-srcfolder',
    stagingRoot,
    '-ov',
    '-format',
    'UDZO',
    outputDmgPath,
  ]);
  run('xattr', ['-cr', outputDmgPath], { allowFailure: true, stdio: 'ignore' });
  run('hdiutil', ['verify', outputDmgPath]);

  console.log(
    JSON.stringify(
      {
        dmgPath: outputDmgPath,
        sha256: sha256File(outputDmgPath),
        sourceAppPath: inputAppPath,
      },
      null,
      2,
    ),
  );
} finally {
  fs.rmSync(stagingRoot, { recursive: true, force: true });
}
