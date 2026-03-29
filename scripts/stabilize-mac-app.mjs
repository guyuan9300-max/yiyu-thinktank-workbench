#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const inputAppPath = process.argv[2];
const appPath = inputAppPath ? path.resolve(inputAppPath) : '';

function fail(message) {
  console.error(`[stabilize-mac-app] ${message}`);
  process.exit(1);
}

function info(message) {
  console.log(`[stabilize-mac-app] ${message}`);
}

function run(command, args, { allowFailure = false, stdio = 'inherit' } = {}) {
  const result = spawnSync(command, args, { stdio, encoding: 'utf8' });
  if (result.error) {
    if (allowFailure) return result;
    fail(`${command} failed: ${result.error.message}`);
  }
  if (result.status !== 0 && !allowFailure) {
    const detail = (result.stderr || result.stdout || '').trim();
    fail(`${command} ${args.join(' ')} exited with status ${result.status}${detail ? `: ${detail}` : ''}`);
  }
  return result;
}

function clearAllAttributesRecursive(targetPath) {
  run('xattr', ['-cr', targetPath], { allowFailure: true, stdio: 'ignore' });
}

function removeSigningTempFiles(rootPath) {
  const visit = (entryPath) => {
    const stat = fs.lstatSync(entryPath);
    if (stat.isSymbolicLink()) return;
    if (stat.isDirectory()) {
      for (const child of fs.readdirSync(entryPath)) {
        visit(path.join(entryPath, child));
      }
      return;
    }
    if (entryPath.endsWith('.cstemp')) {
      fs.rmSync(entryPath, { force: true });
    }
  };

  visit(rootPath);
}

if (process.platform !== 'darwin') {
  fail('This script only supports macOS.');
}

if (!appPath || !fs.existsSync(appPath) || !appPath.endsWith('.app')) {
  fail(`App bundle not found: ${appPath || '(missing path)'}`);
}

info(`stabilizing ${appPath}`);
removeSigningTempFiles(appPath);
clearAllAttributesRecursive(appPath);

info('re-signing app bundle');
run('codesign', ['--force', '--deep', '--sign', '-', '--timestamp=none', appPath]);

removeSigningTempFiles(appPath);
clearAllAttributesRecursive(appPath);

info('verifying code signature');
run('codesign', ['--verify', '--deep', '--strict', '--verbose=2', appPath]);

const assessment = run('spctl', ['--assess', '--type', 'open', '-vv', appPath], {
  allowFailure: true,
  stdio: 'pipe',
});
const assessmentOutput = `${assessment.stdout || ''}${assessment.stderr || ''}`.trim();
if (assessment.status === 0) {
  info(`gatekeeper assessment passed: ${assessmentOutput || 'ok'}`);
} else if (assessmentOutput) {
  info(`gatekeeper assessment note: ${assessmentOutput}`);
}

info('stabilization complete');
