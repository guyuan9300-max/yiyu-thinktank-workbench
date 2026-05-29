#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const strict = process.argv.includes('--strict');
const packageJson = JSON.parse(fs.readFileSync(path.join(projectRoot, 'package.json'), 'utf8'));

function run(command, args = []) {
  const result = spawnSync(command, args, {
    cwd: projectRoot,
    encoding: 'utf8',
  });
  return {
    ok: !result.error && result.status === 0,
    status: result.status,
    stdout: result.stdout || '',
    stderr: result.stderr || '',
    error: result.error?.message || null,
  };
}

function commandExists(command, args = ['--version']) {
  return run(command, args).ok;
}

function commandPath(command) {
  const result = run('xcrun', ['-f', command]);
  return result.ok ? result.stdout.trim() : `${command} not found`;
}

function parseDeveloperIdIdentities(output) {
  return output
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.includes('Developer ID Application:'));
}

function hasApiKeyCredentials(env) {
  return Boolean(env.APPLE_API_KEY && env.APPLE_API_KEY_ID && env.APPLE_API_ISSUER);
}

function hasAppleIdCredentials(env) {
  return Boolean(env.APPLE_ID && env.APPLE_APP_SPECIFIC_PASSWORD && env.APPLE_TEAM_ID);
}

function formatBytes(bytes) {
  const gib = bytes / 1024 / 1024 / 1024;
  return `${gib.toFixed(1)} GiB`;
}

const signing = run('security', ['find-identity', '-v', '-p', 'codesigning']);
const developerIdIdentities = signing.ok ? parseDeveloperIdIdentities(signing.stdout) : [];
const buildConfig = packageJson.build || {};
const macConfig = buildConfig.mac || {};
const checks = [];

function addCheck(name, ok, detail, required = true) {
  checks.push({ name, ok, detail, required });
}

addCheck('macOS host', process.platform === 'darwin', `${process.platform}/${process.arch}`);
addCheck('Xcode notarytool', commandExists('xcrun', ['-f', 'notarytool']), commandPath('notarytool'));
addCheck('Xcode stapler', commandExists('xcrun', ['-f', 'stapler']), commandPath('stapler'));
addCheck('Developer ID Application identity', developerIdIdentities.length > 0, developerIdIdentities[0] || 'no Developer ID Application identity in keychain');
addCheck('notarization credentials', hasApiKeyCredentials(process.env) || hasAppleIdCredentials(process.env), hasApiKeyCredentials(process.env) ? 'App Store Connect API key env detected' : hasAppleIdCredentials(process.env) ? 'Apple ID notarization env detected' : 'missing APPLE_API_KEY/APPLE_API_KEY_ID/APPLE_API_ISSUER or Apple ID fallback');
addCheck('appId configured', Boolean(buildConfig.appId), buildConfig.appId || 'missing package.json build.appId');
addCheck('productName configured', Boolean(buildConfig.productName), buildConfig.productName || 'missing package.json build.productName');
addCheck('hardened runtime enabled', macConfig.hardenedRuntime === true, String(macConfig.hardenedRuntime));
addCheck('force code signing enabled', macConfig.forceCodeSigning === true, String(macConfig.forceCodeSigning));
addCheck('notarize enabled', macConfig.notarize === true, String(macConfig.notarize));

for (const [label, relativePath] of [
  ['icon.icns', 'build-resources/icon.icns'],
  ['main entitlements', macConfig.entitlements],
  ['inherited entitlements', macConfig.entitlementsInherit],
]) {
  const resolved = relativePath ? path.join(projectRoot, relativePath) : '';
  addCheck(label, Boolean(relativePath && fs.existsSync(resolved)), relativePath || 'not configured');
}

const releaseEnvExample = path.join(projectRoot, '.env.release.example');
addCheck('.env.release.example', fs.existsSync(releaseEnvExample), '.env.release.example');

try {
  const availableBytes = os.freemem();
  addCheck('system memory snapshot', availableBytes > 512 * 1024 * 1024, `free memory now: ${formatBytes(availableBytes)}`, false);
} catch {
  addCheck('system memory snapshot', true, 'unavailable', false);
}

if (process.platform === 'darwin') {
  const df = run('df', ['-Pk', projectRoot]);
  const line = df.stdout.trim().split('\n').at(-1);
  const parts = line?.split(/\s+/) || [];
  const availableKb = Number(parts[3] || 0);
  const availableBytes = availableKb * 1024;
  addCheck('disk space for release build', availableBytes > 8 * 1024 * 1024 * 1024, `${formatBytes(availableBytes)} available; 8 GiB+ recommended`, false);
}

const failedRequired = checks.filter((check) => check.required && !check.ok);
const failedRecommended = checks.filter((check) => !check.required && !check.ok);

console.log(`Mac Developer ID release readiness for ${buildConfig.productName || packageJson.name} ${packageJson.version}`);
console.log('');
for (const check of checks) {
  const marker = check.ok ? 'OK ' : check.required ? 'ERR' : 'WARN';
  console.log(`[${marker}] ${check.name}: ${check.detail}`);
}
console.log('');
console.log(`Release command after required checks pass: npm run dist:mac`);
console.log(`Local unsigned test command: npm run dist:mac-local`);

if (failedRequired.length > 0) {
  console.log('');
  console.log('Required blockers:');
  for (const check of failedRequired) console.log(`- ${check.name}: ${check.detail}`);
}

if (failedRecommended.length > 0) {
  console.log('');
  console.log('Recommended fixes before a full build:');
  for (const check of failedRecommended) console.log(`- ${check.name}: ${check.detail}`);
}

if (strict && failedRequired.length > 0) {
  process.exit(1);
}
