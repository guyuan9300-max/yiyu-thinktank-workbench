export type StartupGateStatus = 'ok' | 'warning' | 'blocked';
export type InstallReceiptStatus = 'ok' | 'missing' | 'mismatch';
export type InstallSmokeStatus = 'ok' | 'missing' | 'failed';
export type InstallPathStatus = 'recommended' | 'unexpected';
export type ManifestStatus = 'ok' | 'missing' | 'invalid';
export type BackendManifestStatus = 'ok' | 'missing' | 'mismatch';
export type BackendFeatureStatus = 'ok' | 'missing';
export type BackendSchemaStatus = 'ok' | 'stale';
export type BackendRuntimeModeStatus = 'ok' | 'mismatch';

export type DesktopStartupGateInput = {
  isPackaged: boolean;
  installPathStatus: InstallPathStatus;
  manifestStatus: ManifestStatus;
  installReceiptStatus: InstallReceiptStatus;
  installSmokeStatus: InstallSmokeStatus;
  backendManifestStatus: BackendManifestStatus;
  backendFeatureStatus: BackendFeatureStatus;
  backendSchemaStatus: BackendSchemaStatus;
  backendRuntimeModeStatus: BackendRuntimeModeStatus;
  legacyAppCount: number;
  duplicateAppCount: number;
};

export type DesktopStartupGateResult = {
  status: StartupGateStatus;
  reason: string | null;
  installStatus: 'ok' | 'warning';
  installWarning: string | null;
};

function duplicateWarning(input: DesktopStartupGateInput): string | null {
  if (input.legacyAppCount > 0) {
    return `检测到 ${input.legacyAppCount} 个旧入口，容易误开历史包。`;
  }
  if (input.duplicateAppCount > 0) {
    return `检测到 ${input.duplicateAppCount} 个重复安装包，请保留单一入口。`;
  }
  return null;
}

export function evaluateDesktopStartupGate(input: DesktopStartupGateInput): DesktopStartupGateResult {
  const installWarning = duplicateWarning(input);
  if (!input.isPackaged) {
    return {
      status: installWarning ? 'warning' : 'ok',
      reason: null,
      installStatus: installWarning ? 'warning' : 'ok',
      installWarning,
    };
  }

  let reason: string | null = null;
  if (input.installPathStatus !== 'recommended') {
    reason = '当前运行包不在唯一建议安装位置，请改从 ~/Applications/益语智库自用平台 V2.0.app 打开。';
  } else if (input.manifestStatus === 'missing') {
    reason = '当前安装包缺少 version-manifest.json，无法确认前后端是否同一版。';
  } else if (input.manifestStatus === 'invalid') {
    reason = '当前安装包的 version-manifest.json 已损坏，无法确认运行身份。';
  } else if (input.installReceiptStatus === 'missing') {
    reason = '安装收据缺失，请重新执行安装流程后再打开客户工作台。';
  } else if (input.installReceiptStatus === 'mismatch') {
    reason = '安装收据与当前安装包不一致，说明你正在运行旧包或装错包。';
  } else if (input.installSmokeStatus === 'missing') {
    reason = '安装后最小冒烟结果缺失，请先完成安装校验再进入客户工作台。';
  } else if (input.installSmokeStatus === 'failed') {
    reason = '安装后最小冒烟失败，当前包不允许继续进入客户工作台。';
  } else if (input.backendManifestStatus === 'missing') {
    reason = '后端没有返回 bundle 身份，无法确认当前运行态是否和安装包一致。';
  } else if (input.backendManifestStatus === 'mismatch') {
    reason = '后端返回的 bundle 身份与当前安装包不一致，源码修改可能只在一端生效。';
  } else if (input.backendFeatureStatus === 'missing') {
    reason = '后端缺少客户工作台必需能力，请重新安装同一版本的桌面包。';
  } else if (input.backendSchemaStatus === 'stale') {
    reason = '后端 schema 版本过低，当前安装包不能安全进入客户工作台。';
  } else if (input.backendRuntimeModeStatus === 'mismatch') {
    reason = '当前桌面处于打包态，但后端运行模式不匹配。';
  }

  if (reason) {
    return {
      status: 'blocked',
      reason,
      installStatus: 'warning',
      installWarning: reason,
    };
  }

  return {
    status: installWarning ? 'warning' : 'ok',
    reason: null,
    installStatus: installWarning ? 'warning' : 'ok',
    installWarning,
  };
}
