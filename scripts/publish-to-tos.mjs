#!/usr/bin/env node
import fs from 'node:fs';
import https from 'node:https';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const distRoot = path.join(projectRoot, 'dist');
const dryRun = process.argv.includes('--dry-run');
const skipVerify = process.argv.includes('--skip-verify');

const BUCKET = 'yiyu-thinktank-releases';
const PREFIX = 'desktop/mac/';
const PUBLIC_BASE = `https://${BUCKET}.tos-cn-beijing.volces.com/${PREFIX}`;
const LATEST_MAC_FILE = 'latest-mac.yml';

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
    { localName: LATEST_MAC_FILE, remoteName: LATEST_MAC_FILE, isUpdateFeed: true },
  ];
  return required.map((item) => ({
    ...item,
    localPath: path.join(distRoot, item.localName),
    remoteKey: `tos://${BUCKET}/${PREFIX}${item.remoteName}`,
    publicUrl: `${PUBLIC_BASE}${encodeURIComponent(item.remoteName)}`,
  }));
}

function assertArtifactsExist(artifacts) {
  const missing = artifacts.filter((artifact) => !fs.existsSync(artifact.localPath));
  if (missing.length > 0) {
    console.error('[publish] 缺失发布产物:');
    for (const artifact of missing) console.error(`         ${artifact.localPath}`);
    console.error('         先跑 npm run release:mac 完成构建+签名+公证再发布');
    process.exit(3);
  }
}

function assertLatestMacYml(artifacts, version) {
  const latest = artifacts.find((artifact) => artifact.isUpdateFeed);
  const zip = artifacts.find((artifact) => artifact.localName.endsWith('.zip'));
  if (!latest || !zip) return;
  const content = fs.readFileSync(latest.localPath, 'utf8');
  const missing = [];
  if (!content.includes(`version: ${version}`) && !content.includes(`version: '${version}'`) && !content.includes(`version: "${version}"`)) {
    missing.push(`version ${version}`);
  }
  if (!content.includes(zip.localName)) {
    missing.push(zip.localName);
  }
  if (missing.length > 0) {
    console.error(`[publish] ${LATEST_MAC_FILE} 看起来不是当前版本的更新清单，缺少: ${missing.join(', ')}`);
    console.error(`         文件位置: ${latest.localPath}`);
    process.exit(3);
  }
}

function uploadOne(artifact) {
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

function requestUrl(url, method = 'HEAD') {
  return new Promise((resolve) => {
    const req = https.request(url, { method, timeout: 15_000 }, (res) => {
      res.resume();
      res.on('end', () => {
        resolve({
          ok: Boolean(res.statusCode && res.statusCode >= 200 && res.statusCode < 400),
          statusCode: res.statusCode || 0,
        });
      });
    });
    req.on('timeout', () => {
      req.destroy(new Error('timeout'));
    });
    req.on('error', (error) => {
      resolve({ ok: false, statusCode: 0, error: error.message });
    });
    req.end();
  });
}

async function verifyPublicUrls(artifacts) {
  if (dryRun || skipVerify) {
    if (skipVerify) console.log('[publish] 已按 --skip-verify 跳过公网 URL 验证');
    return;
  }
  console.log('');
  console.log('[publish] 验证公网更新源可访问性...');
  for (const artifact of artifacts) {
    let result = await requestUrl(artifact.publicUrl, 'HEAD');
    if (!result.ok && result.statusCode === 405) {
      result = await requestUrl(artifact.publicUrl, 'GET');
    }
    if (!result.ok) {
      console.error(`[publish] 公网 URL 验证失败: ${artifact.publicUrl}`);
      console.error(`         status=${result.statusCode || 'unknown'}${result.error ? ` error=${result.error}` : ''}`);
      console.error(`         如果失败项是 ${LATEST_MAC_FILE}，客户端会显示找不到更新源。请先修复 TOS 权限或重新上传。`);
      process.exit(5);
    }
    console.log(`         OK ${artifact.publicUrl}`);
  }
}

async function main() {
  assertTosutil();
  const version = readPackageVersion();
  console.log(`[publish] 准备发布版本 ${version}`);
  console.log(`[publish] 目标 bucket: tos://${BUCKET}/${PREFIX}`);
  if (dryRun) console.log('[publish] DRY-RUN 模式,不会真的上传');

  const artifacts = resolveArtifacts(version);
  assertArtifactsExist(artifacts);
  assertLatestMacYml(artifacts, version);

  const updateFeed = artifacts.find((artifact) => artifact.isUpdateFeed);
  const installArtifacts = artifacts.filter((artifact) => !artifact.isUpdateFeed);
  for (const artifact of installArtifacts) uploadOne(artifact);
  if (updateFeed) {
    console.log('[publish] 安装包与 blockmap 已上传，最后发布更新清单。');
    uploadOne(updateFeed);
  }

  console.log('');
  console.log('[publish] 全部上传完成。可访问的链接:');
  for (const artifact of artifacts) {
    console.log(`         ${artifact.publicUrl}`);
  }
  console.log('');
  console.log('[publish] 用户首次下载入口(DMG):');
  const dmgArtifact = artifacts.find((a) => a.localName.endsWith('.dmg'));
  if (dmgArtifact) console.log(`         ${dmgArtifact.publicUrl}`);

  await verifyPublicUrls(artifacts);
}

main().catch((error) => {
  console.error(`[publish] 发布异常: ${error instanceof Error ? error.message : String(error)}`);
  process.exit(5);
});
