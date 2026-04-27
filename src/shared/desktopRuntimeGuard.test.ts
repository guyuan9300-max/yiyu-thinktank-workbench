import test from 'node:test';
import assert from 'node:assert/strict';

import { evaluateDesktopStartupGate } from './desktopRuntimeGuard.js';

function fixture(overrides: Partial<Parameters<typeof evaluateDesktopStartupGate>[0]> = {}) {
  return {
    isPackaged: true,
    installPathStatus: 'recommended' as const,
    manifestStatus: 'ok' as const,
    installReceiptStatus: 'ok' as const,
    installSmokeStatus: 'ok' as const,
    backendManifestStatus: 'ok' as const,
    backendFeatureStatus: 'ok' as const,
    backendSchemaStatus: 'ok' as const,
    backendRuntimeModeStatus: 'ok' as const,
    legacyAppCount: 0,
    duplicateAppCount: 0,
    ...overrides,
  };
}

test('startup gate blocks when app runs outside recommended path', () => {
  const result = evaluateDesktopStartupGate(
    fixture({ installPathStatus: 'unexpected' }),
  );

  assert.equal(result.status, 'blocked');
  assert.match(result.reason || '', /唯一建议安装位置/);
});

test('startup gate blocks when install evidence is missing', () => {
  const result = evaluateDesktopStartupGate(
    fixture({ installReceiptStatus: 'missing' }),
  );

  assert.equal(result.status, 'blocked');
  assert.match(result.reason || '', /安装收据缺失/);
});

test('startup gate warns on duplicate entries when runtime itself is valid', () => {
  const result = evaluateDesktopStartupGate(
    fixture({ duplicateAppCount: 2 }),
  );

  assert.equal(result.status, 'warning');
  assert.match(result.installWarning || '', /重复安装包/);
});

test('startup gate passes when packaged runtime is internally consistent', () => {
  const result = evaluateDesktopStartupGate(fixture());

  assert.equal(result.status, 'ok');
  assert.equal(result.reason, null);
});
