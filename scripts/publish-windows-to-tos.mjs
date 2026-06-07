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
const tosutil = process.env.YIYU_TOSUTIL_BIN || 'tosutil';

const BUCKET = process.env.YIYU_TOS_BUCKET || 'yiyu-thinktank-releases';
const PREFIX = process.env.YIYU_TOS_WINDOWS_PREFIX || 'desktop/windows/';
const PUBLIC_BASE = process.env.YIYU_TOS_PUBLIC_BASE_URL || `https://${BUCKET}.tos-cn-beijing.volces.com/${PREFIX}`;
const LATEST_WINDOWS_FILE = 'latest.yml';

function readPackageVersion() {
  const pkgPath = path.join(projectRoot, 'package.json');
  return JSON.parse(fs.readFileSync(pkgPath, 'utf8')).version;
}

function commandAvailable(command) {
  const result = spawnSync(command, ['--help'], { encoding: 'utf8' });
  return !result.error;
}

function assertTosutil() {
  if (!commandAvailable(tosutil)) {
    console.error('[publish:windows] 缺少 tosutil 命令。');
    console.error('                  请先在 Windows 真机配置火山云 TOS 最小权限凭据。');
    process.exit(2);
  }
}

function resolveArtifacts(version) {
  const setupName = `yiyu-workbench-${version}-x64-setup.exe`;
  const blockmapName = `${setupName}.blockmap`;
  return [
    { localName: setupName, remoteName: setupName },
    { localName: blockmapName, remoteName: blockmapName },
    { localName: LATEST_WINDOWS_FILE, remoteName: LATEST_WINDOWS_FILE, isUpdateFeed: true },
  ].map((item) => ({
    ...item,
    localPath: path.join(distRoot, item.localName),
    remoteKey: `tos://${BUCKET}/${PREFIX}${item.remoteName}`,
    publicUrl: `${PUBLIC_BASE.replace(/\/$/, '')}/${encodeURIComponent(item.remoteName)}`,
  }));
}

function assertArtifactsExist(artifacts) {
  const missing = artifacts.filter((artifact) => !fs.existsSync(artifact.localPath));
  if (missing.length === 0) return;
  console.error('[publish:windows] 缺失发布产物:');
  for (const artifact of missing) console.error(`                  ${artifact.localPath}`);
  console.error('                  请先在 Windows 真机运行 npm run release:windows，并完成 Authenticode 签名。');
  process.exit(3);
}

function assertLatestYml(artifacts, version) {
  const latest = artifacts.find((artifact) => artifact.isUpdateFeed);
  const setup = artifacts.find((artifact) => artifact.localName.endsWith('.exe'));
  if (!latest || !setup) return;
  const content = fs.readFileSync(latest.localPath, 'utf8');
  const missing = [];
  if (!content.includes(`version: ${version}`) && !content.includes(`version: '${version}'`) && !content.includes(`version: "${version}"`)) {
    missing.push(`version ${version}`);
  }
  if (!content.includes(setup.localName)) missing.push(setup.localName);
  if (missing.length > 0) {
    console.error(`[publish:windows] ${LATEST_WINDOWS_FILE} 看起来不是当前版本的更新清单，缺少: ${missing.join(', ')}`);
    process.exit(3);
  }
}

function uploadOne(artifact) {
  console.log(`[publish:windows] 上传 ${artifact.localName} -> ${artifact.remoteKey}`);
  if (dryRun) {
    console.log('                  [dry-run] 跳过实际上传');
    return;
  }
  const result = spawnSync(tosutil, ['cp', artifact.localPath, artifact.remoteKey], { stdio: 'inherit' });
  if (result.status !== 0) {
    console.error(`[publish:windows] 上传失败: ${artifact.localName}`);
    process.exit(result.status || 4);
  }
}

function requestUrl(url, method = 'HEAD') {
  return new Promise((resolve) => {
    const req = https.request(url, { method, timeout: 15_000 }, (res) => {
      res.resume();
      res.on('end', () => {
        resolve({ ok: Boolean(res.statusCode && res.statusCode >= 200 && res.statusCode < 400), statusCode: res.statusCode || 0 });
      });
    });
    req.on('timeout', () => req.destroy(new Error('timeout')));
    req.on('error', (error) => resolve({ ok: false, statusCode: 0, error: error.message }));
    req.end();
  });
}

async function verifyPublicUrls(artifacts) {
  if (dryRun || skipVerify) return;
  for (const artifact of artifacts) {
    let result = await requestUrl(artifact.publicUrl, 'HEAD');
    if (!result.ok && result.statusCode === 405) result = await requestUrl(artifact.publicUrl, 'GET');
    if (!result.ok) {
      console.error(`[publish:windows] 公网 URL 验证失败: ${artifact.publicUrl}`);
      process.exit(5);
    }
  }
}

async function main() {
  assertTosutil();
  const version = readPackageVersion();
  console.log(`[publish:windows] 准备发布版本 ${version}`);
  if (dryRun) console.log('[publish:windows] DRY-RUN 模式,不会真的上传');

  const artifacts = resolveArtifacts(version);
  assertArtifactsExist(artifacts);
  assertLatestYml(artifacts, version);

  for (const artifact of artifacts.filter((artifact) => !artifact.isUpdateFeed)) uploadOne(artifact);
  console.log('[publish:windows] 安装包与 blockmap 已上传，最后发布 latest.yml。');
  const updateFeed = artifacts.find((artifact) => artifact.isUpdateFeed);
  if (updateFeed) uploadOne(updateFeed);
  await verifyPublicUrls(artifacts);
  console.log(dryRun ? '[publish:windows] dry-run 完成。' : '[publish:windows] 发布完成。');
}

main().catch((error) => {
  console.error(`[publish:windows] 发布异常: ${error instanceof Error ? error.message : String(error)}`);
  process.exit(5);
});
