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
  writeFile(path.join(seedPath, 'src.txt'), 'one\ntwo\nthree\n');
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

async function testPublishCollabBranch(mod) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'yiyu-collab-branch-'));
  const remotePath = path.join(root, 'remote.git');
  setupRepo(path.join(root, 'seed'), remotePath);
  const localPath = path.join(root, 'local');
  const peerPath = path.join(root, 'peer');
  cloneRepo(remotePath, localPath, 'Local');
  cloneRepo(remotePath, peerPath, 'Peer');
  const initialMain = git(localPath, ['rev-parse', 'origin/main']).trim();

  writeFile(path.join(localPath, 'src.txt'), 'one\ntwo local\nthree\n');
  const preview = await mod.previewPushToMain({ repoPath: localPath, suggestedCandidates: [], appDbPath: null });
  if (!preview.suggestedCollabBranchName?.startsWith('collab/local/')) {
    throw new Error(`expected suggested collab branch, got ${preview.suggestedCollabBranchName}`);
  }
  const result = await mod.publishCollabBranch({ repoPath: localPath, message: 'sync: local feature' }, [], null);
  if (result.mergeStatus !== 'collabBranchPublished' || !result.collabBranchName) {
    throw new Error(`publish did not create collab branch: ${JSON.stringify(result)}`);
  }

  git(peerPath, ['fetch', 'origin']);
  const remoteMain = git(peerPath, ['rev-parse', 'origin/main']).trim();
  if (remoteMain !== initialMain) {
    throw new Error('publishing a collab branch unexpectedly moved origin/main');
  }
  const branchText = git(peerPath, ['show', `origin/${result.collabBranchName}:src.txt`]);
  if (!branchText.includes('two local')) {
    throw new Error(`collab branch did not include local change:\n${branchText}`);
  }
}

async function testFastForwardMainAndBlocksDirty(mod) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'yiyu-collab-ff-'));
  const remotePath = path.join(root, 'remote.git');
  setupRepo(path.join(root, 'seed'), remotePath);
  const localPath = path.join(root, 'local');
  const peerPath = path.join(root, 'peer');
  cloneRepo(remotePath, localPath, 'Local');
  cloneRepo(remotePath, peerPath, 'Peer');

  writeFile(path.join(peerPath, 'src.txt'), 'one\ntwo remote\nthree\n');
  git(peerPath, ['commit', '-am', 'remote feature']);
  git(peerPath, ['push']);

  const preview = await mod.previewPullFromMain({ repoPath: localPath, suggestedCandidates: [], appDbPath: null });
  if (!preview.canFastForwardMain) {
    throw new Error(`expected fast-forward to be available: ${preview.directReceiveBlockReason}`);
  }
  const result = await mod.fastForwardMain({ repoPath: localPath }, [], null);
  if (result.mergeStatus !== 'mainFastForwarded') {
    throw new Error(`fast-forward failed: ${JSON.stringify(result)}`);
  }
  const localText = fs.readFileSync(path.join(localPath, 'src.txt'), 'utf8');
  if (!localText.includes('two remote')) {
    throw new Error(`fast-forward did not update local file:\n${localText}`);
  }

  writeFile(path.join(localPath, 'local-only.txt'), 'dirty\n');
  writeFile(path.join(peerPath, 'extra.txt'), 'remote extra\n');
  git(peerPath, ['add', '.']);
  git(peerPath, ['commit', '-m', 'remote extra']);
  git(peerPath, ['push']);
  const dirtyPreview = await mod.previewPullFromMain({ repoPath: localPath, suggestedCandidates: [], appDbPath: null });
  if (dirtyPreview.canFastForwardMain || !dirtyPreview.directReceiveBlockReason?.includes('未提交改动')) {
    throw new Error(`dirty local worktree should block direct receive: ${JSON.stringify(dirtyPreview)}`);
  }
}

async function testPullPreviewListsCollabBranches(mod) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'yiyu-collab-list-'));
  const remotePath = path.join(root, 'remote.git');
  setupRepo(path.join(root, 'seed'), remotePath);
  const localPath = path.join(root, 'local');
  const peerPath = path.join(root, 'peer');
  cloneRepo(remotePath, localPath, 'Local');
  cloneRepo(remotePath, peerPath, 'Peer');

  writeFile(path.join(localPath, 'src.txt'), 'one\ncollab branch\nthree\n');
  const published = await mod.publishCollabBranch({ repoPath: localPath, message: 'sync: collab branch' }, [], null);
  const preview = await mod.previewPullFromMain({ repoPath: peerPath, suggestedCandidates: [], appDbPath: null });
  const found = preview.remoteBranches?.some((branch) => branch.branchName === published.collabBranchName);
  if (!found) {
    throw new Error(`pull preview did not list collab branch ${published.collabBranchName}`);
  }
}

const mod = await import(pathToFileURL(path.resolve('build/main/collabGit.js')).href);
await testPublishCollabBranch(mod);
await testFastForwardMainAndBlocksDirty(mod);
await testPullPreviewListsCollabBranches(mod);
console.log('[collab-merge] collab branch publish and safe main fast-forward ok');
