import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '..');
const mainSourcePath = path.join(projectRoot, 'src', 'main', 'main.ts');
const source = fs.readFileSync(mainSourcePath, 'utf8');

function indexOfRequired(pattern, label) {
  const index = source.indexOf(pattern);
  assert.notEqual(index, -1, `missing ${label}: ${pattern}`);
  return index;
}

indexOfRequired("`${path.basename(venvPath)}.tmp-${process.pid}-${Date.now()}`", 'temporary runtime directory naming');
indexOfRequired("'robocopy'", 'Windows robocopy copy path');
indexOfRequired("'/MIR'", 'robocopy mirror flag');
indexOfRequired("'/R:2'", 'robocopy retry limit');
indexOfRequired("(code) => code >= 0 && code <= 7", 'robocopy success exit-code range');

const copyIndex = indexOfRequired('await copyPrebuiltBackendVenv(seed, tempVenvPath);', 'copy into temporary venv');
const replaceIndex = indexOfRequired('replaceRuntimeVenv(tempVenvPath, venvPath);', 'atomic final replacement');
const finalSmokeIndex = indexOfRequired("await assertPythonRuntimeUsable(pythonPath, 'backend:packaged-python-smoke'", 'final runtime smoke test');
const metadataIndex = indexOfRequired('writeRuntimeSyncMetadata(metadataPath, {', 'metadata write');

assert(copyIndex < replaceIndex, 'runtime must copy into temp before replacing final venv');
assert(replaceIndex < finalSmokeIndex, 'runtime must be moved to final path before final smoke test');
assert(finalSmokeIndex < metadataIndex, 'metadata must be written only after final smoke test');

console.log('[test-windows-runtime-copy] OK');
