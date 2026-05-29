#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const skipPull = process.argv.includes('--skip-pull');
const dryPublishOnly = process.argv.includes('--dry-publish-only');

function run(command, args, options = {}) {
  const label = `${command} ${args.join(' ')}`;
  console.log(`\n[release:mac:tos] $ ${label}`);
  const result = spawnSync(command, args, {
    cwd: projectRoot,
    stdio: options.capture ? 'pipe' : 'inherit',
    encoding: 'utf8',
    env: process.env,
  });
  if (result.error) {
    throw new Error(`${label} failed: ${result.error.message}`);
  }
  if (result.status !== 0) {
    const detail = options.capture ? `${result.stdout || ''}${result.stderr || ''}`.trim() : '';
    throw new Error(`${label} exited with ${result.status}${detail ? `\n${detail}` : ''}`);
  }
  return result.stdout || '';
}

function runGit(args, options = {}) {
  return run('git', args, options);
}

function ensureMainBranch() {
  const branch = runGit(['branch', '--show-current'], { capture: true }).trim();
  if (branch !== 'main') {
    throw new Error(`当前分支是 ${branch || '(detached)'}，正式发布必须在 main 上执行。`);
  }
}

function ensureNoTrackedDirtyFiles() {
  const trackedDirty = runGit(['status', '--porcelain', '--untracked-files=no'], { capture: true }).trim();
  if (trackedDirty) {
    throw new Error(`当前存在已跟踪文件未提交修改，禁止发布半成品:\n${trackedDirty}`);
  }
  const untracked = runGit(['status', '--porcelain', '--untracked-files=normal'], { capture: true })
    .split('\n')
    .filter((line) => line.startsWith('?? '))
    .join('\n');
  if (untracked) {
    console.log('\n[release:mac:tos] 提醒：检测到未跟踪文件，不会阻止发布，但请确认它们不会影响构建:');
    console.log(untracked);
  }
}

function readPackageVersion() {
  const pkg = JSON.parse(fs.readFileSync(path.join(projectRoot, 'package.json'), 'utf8'));
  return pkg.version;
}

function ensureDistFeedExists() {
  const latestMacPath = path.join(projectRoot, 'dist', 'latest-mac.yml');
  if (!fs.existsSync(latestMacPath)) {
    throw new Error(`缺少 ${latestMacPath}，请先确认 release:mac 已生成 electron-updater 更新清单。`);
  }
}

async function main() {
  console.log('[release:mac:tos] 开始执行益语智库 Mac 正式发布流水线');
  ensureMainBranch();
  ensureNoTrackedDirtyFiles();

  if (!skipPull) {
    runGit(['pull', '--ff-only', 'origin', 'main']);
    ensureNoTrackedDirtyFiles();
  }

  const version = readPackageVersion();
  console.log(`\n[release:mac:tos] 待发布版本: ${version}`);
  console.log('[release:mac:tos] 如果本次应发布新版本，请确认 package.json version 已在提交中递增。');

  if (!dryPublishOnly) {
    run(npmCommand, ['run', 'release:mac:doctor:strict']);
    run(npmCommand, ['run', 'release:mac']);
    ensureDistFeedExists();
    run(npmCommand, ['run', 'release:mac:verify-dmg']);
  } else {
    console.log('[release:mac:tos] --dry-publish-only: 跳过构建和 DMG 验证，只检查发布上传预演。');
  }

  run(npmCommand, ['run', 'release:mac:publish:dry']);
  run(npmCommand, ['run', 'release:mac:publish']);

  console.log('\n[release:mac:tos] 发布完成。请用旧版安装包点击“检查更新”，确认能发现、下载并安装新版。');
}

main().catch((error) => {
  console.error(`\n[release:mac:tos] 发布失败：${error instanceof Error ? error.message : String(error)}`);
  console.error('[release:mac:tos] 不要宣布发布完成。请按 docs/codex-release-runbook.md 的 Failure Handling 处理。');
  process.exit(1);
});
