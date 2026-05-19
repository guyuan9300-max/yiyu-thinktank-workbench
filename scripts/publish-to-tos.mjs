#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const distRoot = path.join(projectRoot, 'dist');
const dryRun = process.argv.includes('--dry-run');

const BUCKET = 'yiyu-thinktank-releases';
const PREFIX = 'desktop/mac/';
const PUBLIC_BASE = `https://${BUCKET}.tos-cn-beijing.volces.com/${PREFIX}`;

function readPackageVersion() {
  const pkgPath = path.join(projectRoot, 'package.json');
  const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
  return pkg.version;
}

function commandAvailable(command) {
  const result = spawnSync(command, ['--help'], { encoding: 'utf8' });
  return !result.error;
}

function assertTosutil() {
  if (!commandAvailable('tosutil')) {
    console.error('[publish] 缺少 tosutil 命令。');
    console.error('         安装方式: https://www.volcengine.com/docs/6349/148777');
    console.error('         首次使用前: tosutil config -i <AK> -k <SK> -e tos-cn-beijing.volces.com');
    process.exit(2);
  }
}

function resolveArtifacts(version) {
  const arch = process.arch === 'arm64' ? 'arm64' : 'x64';
  const stem = `yiyu-workbench-${version}-${arch}`;
  const required = [
    { localName: `${stem}.dmg`, remoteName: `${stem}.dmg` },
    { localName: `${stem}.zip`, remoteName: `${stem}.zip` },
    { localName: `${stem}.zip.blockmap`, remoteName: `${stem}.zip.blockmap` },
    { localName: 'latest-mac.yml', remoteName: 'latest-mac.yml' },
  ];
  return required.map((item) => ({
    ...item,
    localPath: path.join(distRoot, item.localName),
    remoteKey: `tos://${BUCKET}/${PREFIX}${item.remoteName}`,
    publicUrl: `${PUBLIC_BASE}${encodeURIComponent(item.remoteName)}`,
  }));
}

function uploadOne(artifact) {
  if (!fs.existsSync(artifact.localPath)) {
    console.error(`[publish] 缺失产物: ${artifact.localPath}`);
    console.error('         先跑 npm run release:mac 完成构建+签名+公证再发布');
    process.exit(3);
  }
  console.log(`[publish] 上传 ${artifact.localName} -> ${artifact.remoteKey}`);
  if (dryRun) {
    console.log('         [dry-run] 跳过实际上传');
    return;
  }
  const result = spawnSync('tosutil', ['cp', artifact.localPath, artifact.remoteKey, '-f'], {
    stdio: 'inherit',
  });
  if (result.status !== 0) {
    console.error(`[publish] 上传失败: ${artifact.localName} (exit ${result.status})`);
    process.exit(4);
  }
}

function main() {
  assertTosutil();
  const version = readPackageVersion();
  console.log(`[publish] 准备发布版本 ${version}`);
  console.log(`[publish] 目标 bucket: tos://${BUCKET}/${PREFIX}`);
  if (dryRun) console.log('[publish] DRY-RUN 模式,不会真的上传');

  const artifacts = resolveArtifacts(version);
  for (const artifact of artifacts) uploadOne(artifact);

  console.log('');
  console.log('[publish] 全部上传完成。可访问的链接:');
  for (const artifact of artifacts) {
    console.log(`         ${artifact.publicUrl}`);
  }
  console.log('');
  console.log('[publish] 用户首次下载入口(DMG):');
  const dmgArtifact = artifacts.find((a) => a.localName.endsWith('.dmg'));
  if (dmgArtifact) console.log(`         ${dmgArtifact.publicUrl}`);
}

main();
