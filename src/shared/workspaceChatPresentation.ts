export type WorkspaceFallbackNotice = {
  tone: 'amber' | 'rose' | 'blue';
  title: string;
  detail: string;
};

export function getWorkspaceFallbackNotice(input: {
  answerMode?: string | null;
  failureReason?: string | null;
  fallbackTemplateUsed?: boolean;
  finalFailureStage?: string | null;
  partialGenerationPreserved?: boolean;
  generationPolicy?: Record<string, unknown> | null;
}): WorkspaceFallbackNotice | null {
  const answerMode = String(input.answerMode || '').trim();
  if (answerMode !== 'grounded_fallback' && answerMode !== 'system_failure') {
    return null;
  }
  const failureReason = String(input.failureReason || '').trim();
  const finalFailureStage = String(input.finalFailureStage || '').trim();
  const generationPolicyReason = String(input.generationPolicy?.reason || '').trim();
  const generationPolicy = input.generationPolicy || null;
  const cooldownLike = Boolean(generationPolicy?.cooldownActive)
    || generationPolicyReason.includes('cooldown')
    || Boolean(generationPolicy?.shouldUseLocalOnly);

  if (input.fallbackTemplateUsed) {
    return {
      tone: 'amber',
      title: '当前启用了 legacy fallback',
      detail: '以下内容来自旧模板兜底结果，不代表新的数据中心主链回答。',
    };
  }

  if (input.partialGenerationPreserved || failureReason === 'llm_partial_preserved_after_retry') {
    return {
      tone: 'blue',
      title: '本轮模型生成中断，但已保留有效内容',
      detail: '系统保留了部分可用回答和来源诊断；如需完整回答，请稍后重试。',
    };
  }

  if (cooldownLike) {
    return {
      tone: 'amber',
      title: '模型近期连续超时，当前处于冷却保护',
      detail: '建议先重置 runtime 状态或检查模型连通性，再重新发起回答。',
    };
  }

  if (answerMode === 'system_failure' || finalFailureStage === 'compact_retry_failed' || failureReason === 'llm_generation_failed') {
    return {
      tone: 'rose',
      title: '本轮模型没有成功完成回答',
      detail: '系统已命中相关资料，但没有生成可交付文本。你可以重试，或先处理资料缺口和候选动作。',
    };
  }

  return {
    tone: 'amber',
    title: '本轮回答未完整完成',
    detail: '系统已保留可用内容、来源诊断和修复建议。你可以重试，或先处理右侧资料缺口和候选动作。',
  };
}

export function getWorkspaceRuntimeMismatchNotice(input: {
  sourceIntegrityMatch?: boolean | null;
  sourceIntegrityWarning?: string | null;
  backendBuildVersion?: string | null;
  backendGitCommit?: string | null;
  frontendBuildVersion?: string | null;
  frontendGitCommit?: string | null;
}): string | null {
  if (input.sourceIntegrityMatch === false) {
    return input.sourceIntegrityWarning || '当前运行的是旧打包版，源码修改可能尚未生效。请重新构建或切换到最新运行后端。';
  }
  if (
    input.backendGitCommit
    && input.frontendGitCommit
    && input.backendGitCommit !== input.frontendGitCommit
  ) {
    return '当前前后端 Git 指纹不一致，客户工作台可能仍在运行旧包。';
  }
  if (
    input.backendBuildVersion
    && input.frontendBuildVersion
    && input.backendBuildVersion !== input.frontendBuildVersion
  ) {
    return '当前前后端 buildVersion 不一致，源码修改可能只在一端生效。';
  }
  return null;
}
