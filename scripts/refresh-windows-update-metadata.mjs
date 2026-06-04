#!/usr/bin/env node

import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const yaml = require('js-yaml');
const { appBuilderPath } = require('app-builder-bin');

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const distRoot = path.join(projectRoot, 'dist');

function usage() {
  console.log(`Usage:
  node scripts/refresh-windows-update-metadata.mjs --exe dist/yiyu-workbench-0.3.1-x64-setup.exe [--latest dist/latest.yml]

Refreshes latest.yml and .blockmap from the final signed Windows installer.
Run this after Authenticode/SignPath signing because signing changes the installer hash.`);
}

function parseArgs(argv) {
  const args = {
    exe: null,
    latest: path.join(distRoot, 'latest.yml'),
    skipBlockmap: false,
  };
  for (let index = 2; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') {
      args.help = true;
    } else if (arg === '--exe') {
      args.exe = argv[++index];
    } else if (arg === '--latest') {
      args.latest = argv[++index];
    } else if (arg === '--skip-blockmap') {
      args.skipBlockmap = true;
    } else {
      throw new Error(`unknown argument: ${arg}`);
    }
  }
  return args;
}

function resolvePath(inputPath) {
  if (!inputPath) return null;
  return path.isAbsolute(inputPath) ? inputPath : path.resolve(projectRoot, inputPath);
}

function findDefaultExe() {
  if (!fs.existsSync(distRoot)) return null;
  const candidates = fs.readdirSync(distRoot)
    .filter((name) => /^yiyu-workbench-.+-x64-setup\.exe$/i.test(name))
    .map((name) => path.join(distRoot, name))
    .sort((left, right) => fs.statSync(right).mtimeMs - fs.statSync(left).mtimeMs);
  return candidates[0] ?? null;
}

function sha512Base64(filePath) {
  return crypto.createHash('sha512').update(fs.readFileSync(filePath)).digest('base64');
}

function generateBlockmap(exePath, blockmapPath) {
  const result = spawnSync(
    appBuilderPath,
    ['blockmap', '--input', exePath, '--output', blockmapPath],
    { stdio: 'inherit' },
  );
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`app-builder blockmap failed with exit code ${result.status}`);
  }
}

function updateLatestYml(latestPath, exePath, blockmapSize) {
  if (!fs.existsSync(latestPath)) {
    throw new Error(`latest.yml not found: ${latestPath}`);
  }

  const exeName = path.basename(exePath);
  const exeSize = fs.statSync(exePath).size;
  const exeSha512 = sha512Base64(exePath);
  const updateInfo = yaml.load(fs.readFileSync(latestPath, 'utf8')) ?? {};

  updateInfo.path = exeName;
  updateInfo.sha512 = exeSha512;

  if (!Array.isArray(updateInfo.files)) {
    updateInfo.files = [];
  }
  const existingIndex = updateInfo.files.findIndex((file) => {
    const candidate = String(file?.url ?? file?.path ?? '');
    return candidate.toLowerCase().endsWith('.exe');
  });
  const fileInfo = existingIndex >= 0 ? updateInfo.files[existingIndex] : {};
  fileInfo.url = exeName;
  fileInfo.sha512 = exeSha512;
  fileInfo.size = exeSize;
  if (Number.isFinite(blockmapSize)) {
    fileInfo.blockMapSize = blockmapSize;
  }

  if (existingIndex >= 0) {
    updateInfo.files[existingIndex] = fileInfo;
  } else {
    updateInfo.files.unshift(fileInfo);
  }

  if (!updateInfo.releaseDate) {
    updateInfo.releaseDate = new Date().toISOString();
  }

  fs.writeFileSync(
    latestPath,
    `${yaml.dump(updateInfo, { lineWidth: -1, noRefs: true, sortKeys: false })}`,
  );
}

function main() {
  const args = parseArgs(process.argv);
  if (args.help) {
    usage();
    return;
  }

  const exePath = resolvePath(args.exe) ?? findDefaultExe();
  const latestPath = resolvePath(args.latest);
  if (!exePath) {
    throw new Error('no Windows installer found; pass --exe dist/<installer>.exe');
  }
  if (!fs.existsSync(exePath)) {
    throw new Error(`Windows installer not found: ${exePath}`);
  }

  const blockmapPath = `${exePath}.blockmap`;
  if (!args.skipBlockmap) {
    console.log(`[refresh-windows-update] generating blockmap: ${blockmapPath}`);
    generateBlockmap(exePath, blockmapPath);
  }

  const blockmapSize = fs.existsSync(blockmapPath) ? fs.statSync(blockmapPath).size : null;
  console.log(`[refresh-windows-update] updating ${latestPath}`);
  updateLatestYml(latestPath, exePath, blockmapSize);
  console.log('[refresh-windows-update] done');
}

main();
