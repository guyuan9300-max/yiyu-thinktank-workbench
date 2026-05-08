import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import process from 'node:process';

const projectRoot = path.resolve(import.meta.dirname, '..');
const iconPath = path.join(projectRoot, 'build-resources', 'icon.icns');
const entitlementsPath = path.join(projectRoot, 'build-resources', 'entitlements.mac.plist');
const inheritedEntitlementsPath = path.join(projectRoot, 'build-resources', 'entitlements.mac.inherit.plist');

function parseDeveloperIdIdentities(output) {
  return output
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.includes('Developer ID Application:'));
}

function readCodeSigningIdentities() {
  const result = spawnSync('security', ['find-identity', '-v', '-p', 'codesigning'], {
    encoding: 'utf-8',
  });

  if (result.error) {
    return {
      identities: [],
      error: result.error.message,
    };
  }

  return {
    identities: parseDeveloperIdIdentities(result.stdout),
    error: result.status === 0 ? null : (result.stderr || result.stdout || `security exited with code ${result.status ?? 'unknown'}`),
  };
}

function hasNotarizationCredentials(env) {
  const hasAppleIdFlow = Boolean(env.APPLE_ID && env.APPLE_APP_SPECIFIC_PASSWORD && env.APPLE_TEAM_ID);
  const hasApiKeyFlow = Boolean(env.APPLE_API_KEY && env.APPLE_API_KEY_ID && env.APPLE_API_ISSUER);
  return hasAppleIdFlow || hasApiKeyFlow;
}

function commandAvailable(command, args = ['--version']) {
  const result = spawnSync(command, args, { encoding: 'utf-8' });
  return !result.error && result.status === 0;
}

const failures = [];
const warnings = [];

if (!existsSync(iconPath)) {
  failures.push(`缺少发布图标：${iconPath}`);
}

if (!existsSync(entitlementsPath)) {
  failures.push(`缺少 hardened runtime entitlements：${entitlementsPath}`);
}

if (!existsSync(inheritedEntitlementsPath)) {
  failures.push(`缺少 inherited entitlements：${inheritedEntitlementsPath}`);
}

const signing = readCodeSigningIdentities();
if (signing.error && signing.identities.length === 0) {
  failures.push(`无法读取代码签名身份：${signing.error}`);
} else if (signing.identities.length === 0) {
  failures.push('当前钥匙串中没有可用的 Developer ID Application 证书。');
}

if (!hasNotarizationCredentials(process.env)) {
  failures.push('当前环境没有 notarization 凭据。请配置 APPLE_ID/APPLE_APP_SPECIFIC_PASSWORD/APPLE_TEAM_ID，或 APPLE_API_KEY/APPLE_API_KEY_ID/APPLE_API_ISSUER。');
}

if (!commandAvailable('xcrun', ['-f', 'notarytool'])) {
  failures.push('当前环境无法使用 xcrun notarytool。请先安装并启用 Xcode Command Line Tools。');
}

if (!commandAvailable('xcrun', ['-f', 'stapler'])) {
  failures.push('当前环境无法使用 xcrun stapler。请先安装并启用 Xcode Command Line Tools。');
}

if (process.env.CSC_IDENTITY_AUTO_DISCOVERY === 'false') {
  warnings.push('检测到 CSC_IDENTITY_AUTO_DISCOVERY=false，这会阻止正式签名发现身份。');
}

if (failures.length > 0) {
  console.error('Mac 官网发布包前置检查失败：');
  for (const item of failures) {
    console.error(`- ${item}`);
  }
  if (warnings.length > 0) {
    console.error('');
    console.error('附加提醒：');
    for (const item of warnings) {
      console.error(`- ${item}`);
    }
  }
  console.error('');
  console.error('当前环境不满足官网分发版打包要求。');
  console.error('如果你只是需要本机自测包，请改用：npm run dist:mac-local');
  process.exit(1);
}

console.log('Mac 官网发布包前置检查通过。');
console.log(`- Developer ID Application 身份数量：${signing.identities.length}`);
console.log(`- 发布图标：${iconPath}`);
console.log(`- entitlements：${entitlementsPath}`);
console.log(`- inherited entitlements：${inheritedEntitlementsPath}`);
console.log('- notarization 凭据：已检测到');
