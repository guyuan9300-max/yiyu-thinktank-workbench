import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const gitBin = process.env.GIT_BIN || (fs.existsSync('/usr/bin/git') ? '/usr/bin/git' : 'git');

function git(cwd, args) {
  return execFileSync(gitBin, args, {
    cwd,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
}

function writeFile(filePath, content) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
}

function setupRepo(seedPath, remotePath) {
  fs.mkdirSync(seedPath, { recursive: true });
  fs.mkdirSync(remotePath, { recursive: true });
  git(seedPath, ['init', '-b', 'main']);
  git(seedPath, ['config', 'user.email', 'seed@example.com']);
  git(seedPath, ['config', 'user.name', 'Seed']);
  writeFile(path.join(seedPath, 'package.json'), '{"name":"yiyu-thinktank-workbench"}\n');
  writeFile(path.join(seedPath, 'src.txt'), 'one\ntwo\nthree\nfour\nfive\n');
  git(seedPath, ['add', '.']);
  git(seedPath, ['commit', '-m', 'initial']);
  git(remotePath, ['init', '--bare', '-b', 'main']);
  git(seedPath, ['remote', 'add', 'origin', remotePath]);
  git(seedPath, ['push', '-u', 'origin', 'main']);
}

function cloneRepo(remotePath, targetPath, name) {
  git(path.dirname(targetPath), ['clone', remotePath, targetPath]);
  git(targetPath, ['config', 'user.email', `${name}@example.com`]);
  git(targetPath, ['config', 'user.name', name]);
}

async function testAutoMerge(mod) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'yiyu-collab-auto-'));
  const remotePath = path.join(root, 'remote.git');
  setupRepo(path.join(root, 'seed'), remotePath);
  const localPath = path.join(root, 'local');
  const peerPath = path.join(root, 'peer');
  cloneRepo(remotePath, localPath, 'Local');
  cloneRepo(remotePath, peerPath, 'Peer');

  writeFile(path.join(peerPath, 'src.txt'), 'one\ntwo\nthree\nfour remote\nfive\n');
  git(peerPath, ['commit', '-am', 'remote feature']);
  git(peerPath, ['push']);

  writeFile(path.join(localPath, 'src.txt'), 'one\ntwo local\nthree\nfour\nfive\n');
  const result = await mod.commitAndPushToMain({ repoPath: localPath, message: 'sync: local feature' }, [], null);
  if (result.mergeStatus !== 'pushed') {
    throw new Error(`auto merge did not push, got ${result.mergeStatus}`);
  }

  git(peerPath, ['pull', '--ff-only']);
  const merged = fs.readFileSync(path.join(peerPath, 'src.txt'), 'utf8');
  if (!merged.includes('two local') || !merged.includes('four remote')) {
    throw new Error(`auto merge lost one side:\n${merged}`);
  }
}

async function testConflictResolution(mod) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'yiyu-collab-conflict-'));
  const remotePath = path.join(root, 'remote.git');
  setupRepo(path.join(root, 'seed'), remotePath);
  const localPath = path.join(root, 'local');
  const peerPath = path.join(root, 'peer');
  cloneRepo(remotePath, localPath, 'Local');
  cloneRepo(remotePath, peerPath, 'Peer');

  writeFile(path.join(peerPath, 'src.txt'), 'one\ntwo remote\nthree\nfour\nfive\n');
  git(peerPath, ['commit', '-am', 'remote line']);
  git(peerPath, ['push']);

  writeFile(path.join(localPath, 'src.txt'), 'one\ntwo local\nthree\nfour\nfive\n');
  const conflict = await mod.commitAndPushToMain({ repoPath: localPath, message: 'sync: local line' }, [], null);
  if (conflict.mergeStatus !== 'conflictsNeedResolution' || !conflict.conflictGroups?.length) {
    throw new Error(`expected conflict groups, got ${JSON.stringify(conflict)}`);
  }

  await mod.resolveCollabMergeConflicts({
    repoPath: localPath,
    mode: 'push',
    message: 'sync: resolve by keeping both',
    decisions: conflict.conflictGroups.map((group) => ({ groupId: group.id, choice: 'keep_both' })),
  }, [], null, async () => 'one\ntwo local\ntwo remote\nthree\nfour\nfive\n');

  git(peerPath, ['pull', '--ff-only']);
  const resolved = fs.readFileSync(path.join(peerPath, 'src.txt'), 'utf8');
  if (!resolved.includes('two local') || !resolved.includes('two remote') || resolved.includes('<<<<<<<')) {
    throw new Error(`conflict resolution failed:\n${resolved}`);
  }
}

const mod = await import(pathToFileURL(path.resolve('build/main/collabGit.js')).href);
await testAutoMerge(mod);
await testConflictResolution(mod);
console.log('[collab-merge] auto merge ok; keep-both conflict resolution ok');
