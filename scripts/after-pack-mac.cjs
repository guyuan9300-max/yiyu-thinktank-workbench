const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const MACHO_MAGICS = new Set([
  'feedface',
  'cefaedfe',
  'feedfacf',
  'cffaedfe',
  'cafebabe',
  'bebafeca',
  'cafebabf',
  'bfbafeca',
]);

function isMachO(filePath) {
  try {
    const fd = fs.openSync(filePath, 'r');
    const buffer = Buffer.alloc(4);
    fs.readSync(fd, buffer, 0, 4, 0);
    fs.closeSync(fd);
    return MACHO_MAGICS.has(buffer.toString('hex'));
  } catch {
    return false;
  }
}

function clearXattrs(targetPath) {
  spawnSync('xattr', ['-cr', targetPath], { stdio: 'ignore' });
}

function findAppBundle(appOutDir) {
  for (const name of fs.readdirSync(appOutDir)) {
    if (name.endsWith('.app')) return path.join(appOutDir, name);
  }
  return null;
}

function normalizeUrl(rawUrl) {
  const value = String(rawUrl || '').trim();
  return value ? value.replace(/\/+$/, '') : '';
}

function writeOfficialCloudConfig(appPath) {
  const cloudApiUrl = normalizeUrl(process.env.YIYU_PACKAGED_REMOTE_CLOUD_API_URL);
  if (!cloudApiUrl) return false;
  const resourcesDir = path.join(appPath, 'Contents', 'Resources');
  fs.writeFileSync(
    path.join(resourcesDir, 'official-cloud.json'),
    `${JSON.stringify({ cloudApiUrl }, null, 2)}\n`,
    'utf8',
  );
  return true;
}

function isRuntimeVenvEntrypoint(filePath) {
  if (!filePath.includes(`${path.sep}Contents${path.sep}Resources${path.sep}runtime${path.sep}backend-venv-prebuilt${path.sep}bin${path.sep}`)) {
    return false;
  }
  try {
    const firstBytes = fs.readFileSync(filePath, 'utf8').slice(0, 64);
    return firstBytes.startsWith('#!');
  } catch {
    return false;
  }
}

function walk(entryPath, counters) {
  const stat = fs.lstatSync(entryPath);
  if (stat.isSymbolicLink()) return;

  if (stat.isDirectory()) {
    if (path.basename(entryPath) === '__pycache__') {
      fs.rmSync(entryPath, { recursive: true, force: true });
      counters.removed += 1;
      return;
    }
    fs.chmodSync(entryPath, 0o755);
    for (const child of fs.readdirSync(entryPath)) {
      walk(path.join(entryPath, child), counters);
    }
    return;
  }

  if (
    entryPath.endsWith('.pyc')
    || entryPath.endsWith('.pyo')
    || entryPath.endsWith('.cstemp')
    || entryPath.endsWith('.map')
  ) {
    fs.rmSync(entryPath, { force: true });
    counters.removed += 1;
    return;
  }

  const executable = isMachO(entryPath)
    || entryPath.includes(`${path.sep}Contents${path.sep}MacOS${path.sep}`)
    || isRuntimeVenvEntrypoint(entryPath);
  fs.chmodSync(entryPath, executable ? 0o755 : 0o644);
  if (executable) counters.executable += 1;
  counters.files += 1;
}

module.exports = async function afterPack(context) {
  if (context.electronPlatformName !== 'darwin') return;
  const appPath = findAppBundle(context.appOutDir);
  if (!appPath) throw new Error(`afterPack could not find .app in ${context.appOutDir}`);
  const wroteCloudConfig = writeOfficialCloudConfig(appPath);

  const counters = { files: 0, executable: 0, removed: 0 };
  walk(appPath, counters);
  clearXattrs(appPath);
  console.log(
    `[after-pack-mac] normalized ${counters.files} files; kept ${counters.executable} executable Mach-O files; removed ${counters.removed} transient files`,
  );
  if (wroteCloudConfig) {
    console.log('[after-pack-mac] embedded official cloud config');
  }
};
