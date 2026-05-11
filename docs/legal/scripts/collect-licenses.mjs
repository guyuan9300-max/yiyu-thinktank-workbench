#!/usr/bin/env node
/**
 * 自动收集 npm 与 pip 依赖的 license 信息，生成：
 *   - docs/legal/generated/NOTICE.txt        完整归属清单（在 App 关于面板里给用户看）
 *   - docs/legal/generated/license-summary.csv 摘要表格
 *   - docs/legal/generated/license-warnings.txt 高风险 license 警告
 *
 * 用法：
 *   node docs/legal/scripts/collect-licenses.mjs
 *   node docs/legal/scripts/collect-licenses.mjs --detect-network-libs   额外扫描发起网络请求的包
 *
 * 退出码：0 全部合规；2 检测到高风险 license（GPL / AGPL / 未知）
 */

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const projectRoot = path.resolve(fileURLToPath(new URL('../../..', import.meta.url)));
const outputDir = path.join(projectRoot, 'docs', 'legal', 'generated');
const args = process.argv.slice(2);
const detectNetworkLibs = args.includes('--detect-network-libs');

// 高风险 license 黑名单（启用 strict 模式时这些 license 会失败）
const RISKY = new Set([
  'GPL-1.0', 'GPL-2.0', 'GPL-3.0', 'GPL-2.0-only', 'GPL-3.0-only',
  'GPL-2.0+', 'GPL-3.0+', 'GPL-2.0-or-later', 'GPL-3.0-or-later',
  'AGPL-1.0', 'AGPL-3.0', 'AGPL-3.0-only', 'AGPL-3.0-or-later',
  'LGPL-3.0', 'LGPL-3.0-only', 'LGPL-3.0-or-later',
  'EUPL-1.1', 'EUPL-1.2',
  'SSPL-1.0',
  'CC-BY-NC-4.0', 'CC-BY-NC-SA-4.0',
  'UNKNOWN', 'UNLICENSED', 'NONE',
]);

const ATTENTION = new Set([
  'MPL-1.1', 'MPL-2.0',
  'LGPL-2.0', 'LGPL-2.1', 'LGPL-2.1-only', 'LGPL-2.1-or-later',
  'CDDL-1.0', 'CDDL-1.1',
  'EPL-1.0', 'EPL-2.0',
]);

function log(msg) { console.log(`[collect-licenses] ${msg}`); }
function warn(msg) { console.warn(`[collect-licenses] WARN: ${msg}`); }
function err(msg) { console.error(`[collect-licenses] ERROR: ${msg}`); }

function run(command) {
  return execSync(command, { cwd: projectRoot, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] });
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function classifyLicense(license) {
  if (!license) return 'unknown';
  const normalized = license.toUpperCase();
  if (RISKY.has(normalized)) return 'risky';
  for (const r of RISKY) if (normalized.includes(r.toUpperCase())) return 'risky';
  if (ATTENTION.has(normalized)) return 'attention';
  return 'ok';
}

// ============ npm 依赖 ============
function collectNpmLicenses() {
  log('收集 npm 依赖 license...');
  try {
    // 优先用 license-checker（需要安装：npm i -g license-checker）
    const out = run('npx --yes license-checker --production --json --excludePackages "yiyu-thinktank-workbench@*"');
    return JSON.parse(out);
  } catch (e) {
    warn('license-checker 不可用，尝试用 npm ls --json 兜底');
    try {
      const out = run('npm ls --all --production --json');
      const tree = JSON.parse(out);
      const result = {};
      const visit = (deps) => {
        if (!deps) return;
        for (const [name, info] of Object.entries(deps)) {
          const key = `${name}@${info.version || 'unknown'}`;
          if (!result[key]) {
            result[key] = {
              licenses: info.license || 'UNKNOWN',
              repository: info.resolved,
              path: info.path,
            };
          }
          visit(info.dependencies);
        }
      };
      visit(tree.dependencies);
      return result;
    } catch (e2) {
      err(`npm 依赖收集失败：${e2.message}`);
      return {};
    }
  }
}

// ============ pip 依赖 ============
function collectPipLicenses() {
  log('收集 Python 依赖 license...');
  const result = {};

  // 找 backend/requirements 或 backend/pyproject.toml
  const reqFile = path.join(projectRoot, 'backend', 'requirements.txt');
  const lockFile = path.join(projectRoot, 'backend', 'requirements.lock');
  const candidate = fs.existsSync(lockFile) ? lockFile : reqFile;

  if (!fs.existsSync(candidate)) {
    warn(`找不到 backend/requirements.txt 或 requirements.lock`);
    return result;
  }

  try {
    // pip-licenses 工具优先
    try {
      const out = run('pip-licenses --format=json --with-urls --with-license-file --no-license-path');
      const arr = JSON.parse(out);
      for (const pkg of arr) {
        const key = `${pkg.Name}@${pkg.Version}`;
        result[key] = {
          licenses: pkg.License || 'UNKNOWN',
          repository: pkg.URL,
          source: 'pip',
        };
      }
      return result;
    } catch (e) {
      warn('pip-licenses 不可用，尝试 pip show 兜底');
    }

    // 兜底：读 requirements 文件，对每个包跑 pip show
    const lines = fs.readFileSync(candidate, 'utf-8').split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      const match = trimmed.match(/^([a-zA-Z0-9_-]+)/);
      if (!match) continue;
      const name = match[1];
      try {
        const info = run(`pip show ${name}`);
        const licenseMatch = info.match(/^License:\s*(.+)$/m);
        const versionMatch = info.match(/^Version:\s*(.+)$/m);
        const urlMatch = info.match(/^Home-page:\s*(.+)$/m);
        result[`${name}@${versionMatch?.[1] || 'unknown'}`] = {
          licenses: licenseMatch?.[1]?.trim() || 'UNKNOWN',
          repository: urlMatch?.[1]?.trim(),
          source: 'pip',
        };
      } catch (e) {
        result[`${name}@unknown`] = { licenses: 'UNKNOWN', repository: null, source: 'pip' };
      }
    }
  } catch (e) {
    err(`Python 依赖收集失败：${e.message}`);
  }

  return result;
}

// ============ 生成 NOTICE.txt ============
function generateNotice(npmLicenses, pipLicenses) {
  const lines = [];
  lines.push('=================================================================');
  lines.push('  益语智库自用平台 V2.0 - 开源软件归属与许可声明');
  lines.push('  Open Source Software Notice and Attribution');
  lines.push('=================================================================');
  lines.push('');
  lines.push(`生成时间：${new Date().toISOString()}`);
  lines.push('');
  lines.push('本软件使用了下列开源软件。我们对这些项目的作者表示感谢。');
  lines.push('This software incorporates open source software listed below.');
  lines.push('We are grateful to the authors of these projects.');
  lines.push('');
  lines.push('=================================================================');
  lines.push('  Node.js / npm 依赖');
  lines.push('=================================================================');
  lines.push('');
  for (const [key, info] of Object.entries(npmLicenses).sort()) {
    lines.push(`* ${key}`);
    lines.push(`  License: ${info.licenses}`);
    if (info.repository) lines.push(`  Source:  ${info.repository}`);
    lines.push('');
  }
  lines.push('=================================================================');
  lines.push('  Python / pip 依赖');
  lines.push('=================================================================');
  lines.push('');
  for (const [key, info] of Object.entries(pipLicenses).sort()) {
    lines.push(`* ${key}`);
    lines.push(`  License: ${info.licenses}`);
    if (info.repository) lines.push(`  Source:  ${info.repository}`);
    lines.push('');
  }
  return lines.join('\n');
}

// ============ 生成 CSV 摘要 ============
function generateCsv(allLicenses) {
  const lines = ['package,version,license,risk_level,source,repository'];
  for (const [key, info] of Object.entries(allLicenses).sort()) {
    const [name, version] = key.split('@');
    const risk = classifyLicense(info.licenses);
    lines.push([
      JSON.stringify(name),
      JSON.stringify(version || ''),
      JSON.stringify(info.licenses || ''),
      risk,
      info.source || 'npm',
      JSON.stringify(info.repository || ''),
    ].join(','));
  }
  return lines.join('\n');
}

// ============ 生成警告 ============
function generateWarnings(allLicenses) {
  const lines = [];
  lines.push('# License 风险扫描报告');
  lines.push(`生成时间：${new Date().toISOString()}\n`);

  const risky = [];
  const attention = [];
  const unknown = [];

  for (const [key, info] of Object.entries(allLicenses)) {
    const license = info.licenses || 'UNKNOWN';
    const risk = classifyLicense(license);
    if (risk === 'risky') {
      if (license.toUpperCase().includes('UNKNOWN') || license === '' || license === 'UNLICENSED') {
        unknown.push({ key, license });
      } else {
        risky.push({ key, license });
      }
    } else if (risk === 'attention') {
      attention.push({ key, license });
    }
  }

  if (risky.length === 0 && attention.length === 0 && unknown.length === 0) {
    lines.push('✅ 未发现高风险 license。');
    return { content: lines.join('\n'), exitCode: 0 };
  }

  if (unknown.length > 0) {
    lines.push('## 🔴 未知 license（最高风险，必须处理）\n');
    lines.push('这些包没有声明 license 或我们无法识别。继续使用存在法律风险。\n');
    for (const item of unknown) lines.push(`  - ${item.key}: ${item.license}`);
    lines.push('');
  }

  if (risky.length > 0) {
    lines.push('## 🟠 高风险 license（GPL / AGPL / SSPL 等传染性协议）\n');
    lines.push('这些 license 可能要求您将整个 App 开源。请评估替换或获取商业授权。\n');
    for (const item of risky) lines.push(`  - ${item.key}: ${item.license}`);
    lines.push('');
  }

  if (attention.length > 0) {
    lines.push('## 🟡 需关注 license（MPL / LGPL 等弱传染）\n');
    lines.push('这些 license 不强制 App 开源，但对该依赖本身的修改需开源。请确认未修改源代码。\n');
    for (const item of attention) lines.push(`  - ${item.key}: ${item.license}`);
    lines.push('');
  }

  lines.push('## 处理建议\n');
  lines.push('1. 未知 license：联系包作者获取明确授权，或替换为有明确 license 的等价包');
  lines.push('2. GPL/AGPL：评估是否可替换；如不可替换且商业上可接受，咨询律师');
  lines.push('3. LGPL/MPL：保持依赖以原样使用，不修改源代码');

  return { content: lines.join('\n'), exitCode: 2 };
}

// ============ 检测网络库 ============
function detectNetworkRequestingPackages(npmLicenses) {
  if (!detectNetworkLibs) return null;
  log('扫描发起网络请求的 npm 包...');
  const networkPatterns = [
    /axios/i, /fetch/i, /request/i, /superagent/i, /got/i,
    /node-fetch/i, /undici/i, /https?-proxy/i, /websocket/i,
    /socket\.io/i, /grpc/i, /apollo/i, /urql/i, /graphql/i,
  ];
  const matches = [];
  for (const key of Object.keys(npmLicenses)) {
    const name = key.split('@')[0];
    if (networkPatterns.some(p => p.test(name))) {
      matches.push(key);
    }
  }
  return matches;
}

// ============ 主流程 ============
async function main() {
  ensureDir(outputDir);

  const npmLicenses = collectNpmLicenses();
  const pipLicenses = collectPipLicenses();
  const allLicenses = { ...npmLicenses, ...pipLicenses };

  log(`扫描完成。npm: ${Object.keys(npmLicenses).length}, pip: ${Object.keys(pipLicenses).length}`);

  const noticePath = path.join(outputDir, 'NOTICE.txt');
  fs.writeFileSync(noticePath, generateNotice(npmLicenses, pipLicenses), 'utf-8');
  log(`✓ ${noticePath}`);

  const csvPath = path.join(outputDir, 'license-summary.csv');
  fs.writeFileSync(csvPath, generateCsv(allLicenses), 'utf-8');
  log(`✓ ${csvPath}`);

  const warnings = generateWarnings(allLicenses);
  const warningsPath = path.join(outputDir, 'license-warnings.txt');
  fs.writeFileSync(warningsPath, warnings.content, 'utf-8');
  log(`✓ ${warningsPath}`);

  if (detectNetworkLibs) {
    const networkPkgs = detectNetworkRequestingPackages(npmLicenses);
    const netPath = path.join(outputDir, 'network-libs.txt');
    fs.writeFileSync(netPath, networkPkgs.join('\n'), 'utf-8');
    log(`✓ ${netPath} (${networkPkgs.length} 个发起网络请求的包，请逐一评估是否在 App Privacy 中申报)`);
  }

  console.log('');
  console.log('===========================================');
  if (warnings.exitCode === 0) {
    console.log('✅ License 扫描通过');
  } else {
    console.log('⚠️  发现高风险 license，请查看 license-warnings.txt');
  }
  console.log('===========================================');

  process.exit(warnings.exitCode);
}

main().catch(e => {
  err(`脚本执行失败：${e.message}`);
  console.error(e.stack);
  process.exit(1);
});
