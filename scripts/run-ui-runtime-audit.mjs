#!/usr/bin/env node

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '..');
const outputDir = path.join(projectRoot, 'output', 'ui-consistency-audit');
const specPath = path.join(outputDir, 'runtime_surface_spec.json');
const outputPath = path.join(outputDir, 'runtime_surface_hits.json');

function fail(message) {
  console.error(`[run-ui-runtime-audit] ${message}`);
  process.exit(1);
}

if (!fs.existsSync(specPath)) {
  fail(`missing runtime surface spec at ${specPath}. Run node scripts/audit-ui-consistency.mjs first.`);
}

const buildMainPath = path.join(projectRoot, 'build', 'main', 'main.js');
const buildRendererIndex = path.join(projectRoot, 'dist', 'renderer', 'index.html');
if (!fs.existsSync(buildMainPath) || !fs.existsSync(buildRendererIndex)) {
  fail('missing built Electron artifacts. Run npm run build:main && npm run build:renderer first.');
}

const child = spawn('node', ['scripts/run-local-electron.mjs', '.'], {
  cwd: projectRoot,
  stdio: 'inherit',
  env: {
    ...process.env,
    YIYU_UI_RUNTIME_AUDIT_SPEC: specPath,
    YIYU_UI_RUNTIME_AUDIT_OUTPUT: outputPath,
    YIYU_UI_RUNTIME_AUDIT_AUTOQUIT: '1',
  },
});

child.on('exit', (code, signal) => {
  if (signal) {
    fail(`electron exited via signal ${signal}`);
  }
  if ((code ?? 1) !== 0) {
    fail(`electron exited with code ${code}`);
  }
  if (!fs.existsSync(outputPath)) {
    fail(`runtime audit finished without output ${outputPath}`);
  }
  console.log(`[run-ui-runtime-audit] wrote ${outputPath}`);
});
