#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import { APP_DISPLAY_NAME, APP_NAME, sha256File } from './app-manifest.mjs';

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const packageJson = JSON.parse(fs.readFileSync(path.join(projectRoot, 'package.json'), 'utf8'));
const targetDmg = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(projectRoot, 'dist', `${APP_DISPLAY_NAME}-${packageJson.version}-${process.arch}.dmg`);

function fail(message) {
  console.error(`[verify-mac-dmg] ${message}`);
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

if (!fs.existsSync(targetDmg)) {
  fail(`DMG not found: ${targetDmg}`);
}

run('hdiutil', ['verify', targetDmg]);

const mountPoint = fs.mkdtempSync(path.join(os.tmpdir(), 'yiyu-dmg-mount-'));
let attached = false;
try {
  run('hdiutil', ['attach', '-nobrowse', '-readonly', '-mountpoint', mountPoint, targetDmg]);
  attached = true;

  const mountedAppPath = path.join(mountPoint, APP_NAME);
  if (!fs.existsSync(mountedAppPath)) {
    fail(`Mounted DMG does not contain app bundle: ${mountedAppPath}`);
  }
  run(process.execPath, [path.join(projectRoot, 'scripts', 'verify-packaged-app.mjs'), mountedAppPath]);

  console.log(
    JSON.stringify(
      {
        dmgPath: targetDmg,
        sha256: sha256File(targetDmg),
        mountedAppVerified: true,
      },
      null,
      2,
    ),
  );
} finally {
  if (attached) {
    run('hdiutil', ['detach', mountPoint], { allowFailure: true });
  }
  fs.rmSync(mountPoint, { recursive: true, force: true });
}
