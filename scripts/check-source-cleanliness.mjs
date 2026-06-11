#!/usr/bin/env node

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

const repoRoot = process.cwd();

const blockedTextPatterns = [
  {
    label: 'real customer/org name',
    pattern: /日慈|广东省日慈|为爱黔行|黔行公益|为爱前行|黔行|心盛计划|心盛|心灵魔法学院|南沙公益创投|善加|华润|CFFC|中国基金会发展论坛|青禾|黄河基金会/u,
  },
  { label: 'real cloud backend IP', pattern: /101\.126\.34\.232/u },
  { label: 'private key block', pattern: /-----BEGIN (?:RSA |OPENSSH |EC |DSA |PRIVATE )?KEY-----/u },
  { label: 'OpenAI-style API key', pattern: /\bsk-[A-Za-z0-9_-]{20,}\b/u },
  { label: 'Google API key', pattern: /\bAIza[0-9A-Za-z_-]{20,}\b/u },
  { label: 'AWS access key', pattern: /\bAKIA[0-9A-Z]{16}\b/u },
];

const blockedPathPatterns = [
  { label: 'certificate or private key file', pattern: /\.(?:pem|p8|p12|cer|certSigningRequest)$/iu },
  { label: 'sqlite/db runtime file', pattern: /\.(?:sqlite|sqlite3|db)(?:$|[-.])/iu },
  {
    label: 'real customer/org filename',
    pattern: /日慈|广东省日慈|为爱黔行|黔行公益|为爱前行|黔行|心盛计划|心盛|心灵魔法学院|南沙公益创投|善加|华润|CFFC|中国基金会发展论坛|青禾|黄河基金会/u,
  },
];

const ignoredDirs = new Set([
  '.git',
  '.claude',
  '.codex',
  '.playwright-cli',
  'node_modules',
  'dist',
  'build',
  'coverage',
  '.expo',
  '.turbo',
  '.cache',
  '__pycache__',
  '.pytest_cache',
  '.venv',
  'output',
  'tmp',
  'test-results',
]);

const ignoredPathFragments = [
  '/node_modules/',
  '/dist/',
  '/build/',
  '/coverage/',
  '/.expo/',
  '/.turbo/',
  '/.cache/',
  '/.git/',
  '/.claude/',
  '/官网/',
];

const textExtensions = new Set([
  '.css',
  '.cjs',
  '.cfg',
  '.gradle',
  '.html',
  '.ini',
  '.js',
  '.json',
  '.jsx',
  '.md',
  '.mjs',
  '.plist',
  '.properties',
  '.py',
  '.sh',
  '.toml',
  '.ts',
  '.tsx',
  '.txt',
  '.xml',
  '.yaml',
  '.yml',
]);

function isIgnoredPath(relativePath) {
  const normalized = `/${relativePath.split(path.sep).join('/')}`;
  return ignoredPathFragments.some((fragment) => normalized.includes(fragment));
}

function isLikelyTextFile(filePath) {
  const ext = path.extname(filePath);
  if (textExtensions.has(ext)) return true;
  const name = path.basename(filePath);
  if (name.startsWith('.env')) return true;
  return name === '.gitignore' || name === 'README' || name === 'Dockerfile';
}

function listGitVisibleFiles() {
  const raw = execFileSync(
    'git',
    ['ls-files', '--cached', '--others', '--exclude-standard', '-z'],
    { cwd: repoRoot },
  );
  return raw
    .toString('utf8')
    .split('\0')
    .filter(Boolean)
    .filter((relativePath) => !isIgnoredPath(relativePath))
    .filter((relativePath) => relativePath !== 'scripts/check-source-cleanliness.mjs')
    .map((relativePath) => ({
      relativePath,
      fullPath: path.join(repoRoot, relativePath),
    }))
    .filter((file) => existsSync(file.fullPath));
}

function isPrivateEnvPath(normalizedPath) {
  const baseName = path.posix.basename(normalizedPath);
  if (!baseName.startsWith('.env')) return false;
  return !baseName.endsWith('.example');
}

const findings = [];

for (const file of listGitVisibleFiles()) {
  const normalizedPath = file.relativePath.split(path.sep).join('/');
  if (isPrivateEnvPath(normalizedPath)) {
    findings.push(`${normalizedPath}: path matches private env file`);
  }
  for (const rule of blockedPathPatterns) {
    if (rule.pattern.test(normalizedPath)) {
      findings.push(`${normalizedPath}: path matches ${rule.label}`);
    }
  }
  if (!isLikelyTextFile(file.fullPath)) continue;
  let content = '';
  try {
    content = readFileSync(file.fullPath, 'utf8');
  } catch {
    continue;
  }
  for (const rule of blockedTextPatterns) {
    if (rule.pattern.test(content)) {
      findings.push(`${normalizedPath}: content matches ${rule.label}`);
    }
  }
}

if (findings.length > 0) {
  console.error('Source cleanliness check failed:');
  for (const item of findings.slice(0, 200)) {
    console.error(`- ${item}`);
  }
  if (findings.length > 200) {
    console.error(`... and ${findings.length - 200} more`);
  }
  process.exit(1);
}

console.log('Source cleanliness check passed.');
