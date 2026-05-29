#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const EXAMPLE_ENV_FILES = new Set(['.env.example', '.env.release.example']);
const BLOCKED_EXTENSIONS = new Set([
  '.db', '.sqlite', '.sqlite3', '.db-shm', '.db-wal', '.sqlite-shm', '.sqlite-wal',
  '.p8', '.p12', '.pem', '.key', '.cer', '.certsigningrequest', '.mobileprovision',
  '.log',
]);
const WARNING_EXTENSIONS = new Set(['.dmg', '.zip']);
const REVIEW_EXTENSIONS = new Set(['.docx', '.xlsx', '.pptx', '.pdf', '.png', '.jpg', '.jpeg']);
const BLOCKED_PREFIXES = [
  '.yiyu-sync/',
  'release-secrets/',
  'dist/',
  'output/',
  'backend/output/',
  'logs/',
  'dogfood_real/',
];
const SKIP_PREFIXES = [
  '.git/',
  'node_modules/',
  '.venv/',
  'backend/.venv/',
  'cloud_backend/.venv/',
];
const SECRET_KEYWORDS = /(?:secret|token|api[_-]?key|access[_-]?key|secret[_-]?key|app[_-]?secret|client[_-]?secret|private[_-]?key|tos[_-]?ak|tos[_-]?sk)/i;
const SECRET_VALUE_PATTERN = /(?:secret|token|api[_-]?key|access[_-]?key|secret[_-]?key|app[_-]?secret|client[_-]?secret|private[_-]?key|tos[_-]?ak|tos[_-]?sk)\s*[:=]\s*["']?([^"'\s#`]+)["']?/i;
const TOKEN_PATTERNS = [
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/,
  /\bgh[pousr]_[A-Za-z0-9_]{20,}\b/,
  /\bgithub_pat_[A-Za-z0-9_]{40,}\b/,
  /\bsk-[A-Za-z0-9_-]{24,}\b/,
  /\bxox[baprs]-[A-Za-z0-9-]{20,}\b/,
  /\b(?:AKIA|ASIA)[A-Z0-9]{16}\b/,
];
const CONFIG_EXTENSIONS = new Set(['.json', '.yaml', '.yml', '.toml', '.ini', '.conf', '.config']);

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { encoding: 'utf8', ...options });
  if (result.error) throw result.error;
  if (result.status !== 0 && !options.allowNonZero) {
    throw new Error(`${command} ${args.join(' ')} failed: ${result.stderr || result.stdout}`);
  }
  return result.stdout || '';
}

function gitRoot() {
  return run('git', ['rev-parse', '--show-toplevel']).trim();
}

function normalizePath(targetPath) {
  return targetPath.replace(/\\/g, '/').replace(/^\/+/, '');
}

function parseArgs(argv) {
  const args = {
    format: 'text',
    paths: [],
    failOnWarnings: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === '--format') {
      args.format = argv[index + 1] || 'text';
      index += 1;
    } else if (item === '--paths') {
      for (let cursor = index + 1; cursor < argv.length; cursor += 1) {
        args.paths.push(argv[cursor]);
      }
      break;
    } else if (item === '--fail-on-warnings') {
      args.failOnWarnings = true;
    }
  }
  return args;
}

function isExampleEnvPath(targetPath) {
  return EXAMPLE_ENV_FILES.has(path.basename(targetPath));
}

function looksLikePlaceholder(value) {
  const normalized = value.trim().replace(/^["']|["']$/g, '').toLowerCase();
  if (!normalized) return true;
  if (normalized.startsWith('<') && normalized.endsWith('>')) return true;
  if (normalized.includes('${') || normalized.includes('process.env') || normalized.includes('os.environ')) return true;
  if (['str', 'string', 'bool', 'boolean', 'true', 'false', 'none', 'null', 'undefined', 'optional'].includes(normalized)) return true;
  if (normalized.length < 10) return true;
  return [
    'example', 'placeholder', 'changeme', 'change_me', 'your_', 'xxx', 'xxxx',
    'dummy', 'test', 'todo', '填入', '替换', 'replace-with',
  ].some((marker) => normalized.includes(marker));
}

function listCandidatePaths(root, explicitPaths) {
  if (explicitPaths.length > 0) return explicitPaths.map(normalizePath);
  const output = run('git', ['ls-files', '-z', '--cached', '--others', '--exclude-standard'], { cwd: root });
  return output.split('\0').map(normalizePath).filter(Boolean);
}

function readSmallText(root, targetPath) {
  const absolutePath = path.join(root, targetPath);
  try {
    const stat = fs.statSync(absolutePath);
    if (!stat.isFile() || stat.size > 512 * 1024) return '';
    const buffer = fs.readFileSync(absolutePath);
    if (buffer.includes(0)) return '';
    return buffer.toString('utf8');
  } catch {
    return '';
  }
}

function issue(severity, category, targetPath, message, recommendation) {
  return { severity, category, path: targetPath, message, recommendation };
}

function scanPath(root, rawPath) {
  const targetPath = normalizePath(rawPath);
  if (!targetPath || SKIP_PREFIXES.some((prefix) => targetPath.startsWith(prefix))) return [];
  const basename = path.basename(targetPath);
  const lowerPath = targetPath.toLowerCase();
  const extension = path.extname(lowerPath);
  const issues = [];

  if ((basename === '.env' || basename.startsWith('.env.')) && !isExampleEnvPath(targetPath)) {
    issues.push(issue('block', 'env_file', targetPath, '环境配置文件可能包含密钥或账号信息。', '提交 .env.example，占位模板以外的真实配置留在本机。'));
    return issues;
  }
  if (isExampleEnvPath(targetPath)) return issues;

  if (BLOCKED_PREFIXES.some((prefix) => lowerPath === prefix.slice(0, -1) || lowerPath.startsWith(prefix))) {
    issues.push(issue('block', 'runtime_or_secret_path', targetPath, '运行时数据、发布密钥或内部同步目录不应进入公开源码仓库。', '移出仓库或改走发布/对象存储流程。'));
    return issues;
  }
  if (BLOCKED_EXTENSIONS.has(extension)) {
    issues.push(issue('block', 'sensitive_file_type', targetPath, '数据库、日志、证书或私钥类文件可能包含敏感信息。', '提交脱敏样例或 .example 文件；真实密钥需轮换并移出仓库。'));
    return issues;
  }
  if (WARNING_EXTENSIONS.has(extension)) {
    issues.push(issue('warn', 'installer_artifact', targetPath, '安装包不建议作为普通源码文件提交。', '请优先通过 GitHub Release 或火山云 TOS 发布。'));
  } else if (REVIEW_EXTENSIONS.has(extension)) {
    issues.push(issue('warn', 'review_binary_document', targetPath, '文档、截图或图片可能包含真实客户、账号或内部材料。', '确认脱敏后再提交。'));
  }

  const content = readSmallText(root, targetPath);
  if (!content) return issues;
  if (TOKEN_PATTERNS.some((pattern) => pattern.test(content))) {
    issues.push(issue('block', 'secret_pattern', targetPath, '文件内容疑似包含私钥、访问令牌或 API Key。', '删除真实密钥，改用环境变量或密钥管理；已泄露密钥需要轮换。'));
    return issues;
  }
  const match = content.match(SECRET_VALUE_PATTERN);
  if (CONFIG_EXTENSIONS.has(extension) && match && SECRET_KEYWORDS.test(content) && !looksLikePlaceholder(match[1] || '')) {
    issues.push(issue('block', 'secret_assignment', targetPath, '文件内容疑似包含真实密钥配置。', '提交占位配置，真实值放在本机、云端密钥或系统钥匙串。'));
  }
  return issues;
}

function printText(issues) {
  if (issues.length === 0) {
    console.log('[security-scan] OK: no blocking security issues found.');
    return;
  }
  const blocks = issues.filter((item) => item.severity === 'block');
  const warnings = issues.filter((item) => item.severity === 'warn');
  console.log(`[security-scan] blocking=${blocks.length} warnings=${warnings.length}`);
  for (const item of issues) {
    const tag = item.severity === 'block' ? 'BLOCK' : 'WARN';
    console.log(`${tag} ${item.category} ${item.path}`);
    console.log(`  ${item.message}`);
    console.log(`  ${item.recommendation}`);
  }
}

const args = parseArgs(process.argv.slice(2));
const root = gitRoot();
const paths = listCandidatePaths(root, args.paths);
const issues = paths.flatMap((targetPath) => scanPath(root, targetPath));

if (args.format === 'json') {
  console.log(JSON.stringify({ issues }, null, 2));
} else {
  printText(issues);
}

const hasBlocks = issues.some((item) => item.severity === 'block');
const hasWarnings = issues.some((item) => item.severity === 'warn');
if (hasBlocks || (args.failOnWarnings && hasWarnings)) {
  process.exit(1);
}
