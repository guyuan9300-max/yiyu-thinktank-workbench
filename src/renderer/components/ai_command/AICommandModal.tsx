/**
 * AICommandModal · AI 工作指令入口 (顾源源 5/24 §5)
 *
 * 替代 SmartTaskParseModal 入口. 内含 2 mode:
 *   - quick_task: 走原 ai-parse 链路 (保留原能力, 顾源源原则一)
 *   - ai_command: 新链路 (@机器人 → 解析 → 计划 → 创建 AI 任务 → 审批)
 *
 * 路径选择:
 *   - 默认: 自动识别 (parseSmartCommand)
 *   - 用户可手动切换
 *
 * 安全边界 (顾源源 §12):
 *   - 不直接写 db
 *   - 不绕过 approval_queue
 *   - 不让机器人自审批
 *   - 全程带 actor_id 留痕
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Sparkles, X, Loader2, Bot, AlertCircle, CheckCircle2, ChevronRight } from 'lucide-react';

import {
  aiParseTask,
  resolveBotByHandle,
  getBotPermissions,
  createBotTaskPlan,
  type TaskAiParseResult,
  type BotPermissionsResponse,
} from '../../lib/api';

// A 写的 resolveBotByHandle 返回类型 (inline, 避免 import 错)
type BotResolveResult = Awaited<ReturnType<typeof resolveBotByHandle>>;
import { useBackdropClickClose } from '../../lib/useBackdropClickClose';
import {
  parseSmartCommand,
  recommendModulesForIntent,
  MODULE_CAPABILITY_MANIFEST_V1,
  type AICommandMode,
  type ParsedSmartCommand,
} from '../../lib/aiCommand';

type AICommandModalProps = {
  open: boolean;
  onClose: () => void;
  onQuickTaskParsed: (result: TaskAiParseResult, originalText: string) => void;
  knownClientNames?: string[];
  defaultClientId?: string;
};

type Stage = 'input' | 'parsing' | 'bot_resolved' | 'plan_preview' | 'submitting' | 'submitted' | 'error';

export function AICommandModal({
  open,
  onClose,
  onQuickTaskParsed,
  knownClientNames = [],
  defaultClientId,
}: AICommandModalProps) {
  const [text, setText] = useState('');
  const [stage, setStage] = useState<Stage>('input');
  const [mode, setMode] = useState<AICommandMode>('ai_command');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [parsed, setParsed] = useState<ParsedSmartCommand | null>(null);
  const [bot, setBot] = useState<BotResolveResult | null>(null);
  const [permissions, setPermissions] = useState<BotPermissionsResponse | null>(null);
  const [submitResult, setSubmitResult] = useState<{ task_id: string; ai_task_plan_id: string; status: string } | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (open) {
      setErrorMessage(null);
      window.setTimeout(() => textareaRef.current?.focus(), 80);
    } else {
      // 关闭时重置全部状态
      setText('');
      setStage('input');
      setMode('ai_command');
      setErrorMessage(null);
      setParsed(null);
      setBot(null);
      setPermissions(null);
      setSubmitResult(null);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && stage !== 'parsing' && stage !== 'submitting') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose, stage]);

  const backdropHandlers = useBackdropClickClose(onClose, stage === 'input');

  if (!open) return null;

  // ── 主动作 1: 解析 + 走对应链路 ──────────────

  const handleParse = async () => {
    const trimmed = text.trim();
    if (!trimmed) {
      setErrorMessage('请先输入文字');
      return;
    }
    setErrorMessage(null);
    const parsed = parseSmartCommand(trimmed, knownClientNames);
    setParsed(parsed);

    // 用户手动指定 mode 优先, 否则用 parsed.mode
    const finalMode = mode === 'quick_task' ? 'quick_task' : parsed.mode;

    if (finalMode === 'quick_task') {
      // Quick Task 链路: 直接调原 ai-parse, 跟旧 SmartTaskParseModal 一致
      setStage('parsing');
      try {
        const today = new Date();
        const currentDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
        const result = await aiParseTask({ text: trimmed, currentDate });
        onQuickTaskParsed(result, trimmed);
      } catch (e) {
        const detail = e instanceof Error ? e.message : 'AI 解析失败';
        setErrorMessage(detail);
        setStage('input');
      }
      return;
    }

    // AI Command 链路: 必须有 @机器人
    if (!parsed.bot_handle) {
      setErrorMessage('AI 工作指令需要 @机器人同事. 例如: @庆华 帮我...');
      setStage('input');
      return;
    }

    setStage('parsing');
    try {
      const botData = await resolveBotByHandle(parsed.bot_handle);
      setBot(botData);
      const permData = await getBotPermissions(botData.bot_member_id);
      setPermissions(permData);
      setStage('bot_resolved');
    } catch (e) {
      const detail = e instanceof Error ? e.message : '解析失败';
      setErrorMessage(detail.includes('404') ? `没找到 "@${parsed.bot_handle}" 这个 AI 同事. 请先在组织搭建中心添加.` : detail);
      setStage('error');
    }
  };

  // ── 主动作 2: 进入计划预览 ──────────────

  const handleEnterPlan = () => {
    setStage('plan_preview');
  };

  // ── 主动作 3: 提交 AI 任务计划 ──────────────

  const handleSubmitPlan = async () => {
    if (!bot || !parsed) return;
    setStage('submitting');
    try {
      // 推荐模块 (基于 intent)
      const recommendedModules = recommendModulesForIntent(parsed.intent);
      const moduleNames = recommendedModules
        .map((k) => MODULE_CAPABILITY_MANIFEST_V1.find((m) => m.moduleKey === k)?.moduleName)
        .filter(Boolean) as string[];

      // 任务标题: 取原文前 30 字
      const planTitle = text.length > 30 ? `${text.slice(0, 30)}...` : text;

      const result = await createBotTaskPlan(bot.bot_member_id, {
        plan_title: planTitle,
        plan_text: text,
        client_id: defaultClientId,
        required_modules: moduleNames,
        steps: [],
        expected_outputs: parsed.requested_outputs,
        approval_required: true,
        inline_authorization: parsed.inline_authorization_detected,
        inline_authorization_text: parsed.inline_authorization_text || undefined,
      });
      setSubmitResult({
        task_id: result.task_id || '',
        ai_task_plan_id: result.ai_task_plan_id,
        status: result.approval_status || result.status || 'pending_approval',
      });
      setStage('submitted');
    } catch (e) {
      const detail = e instanceof Error ? e.message : '提交失败';
      setErrorMessage(detail);
      setStage('error');
    }
  };

  // ── 主动作 4: 切回 Quick Task ──────────────

  const handleSwitchToQuickTask = async () => {
    setMode('quick_task');
    setStage('input');
    setErrorMessage(null);
    setParsed(null);
    setBot(null);
    setPermissions(null);
  };

  // ── 渲染 ──────────────

  const recommendedModules = useMemo(() => {
    if (!parsed) return [];
    return recommendModulesForIntent(parsed.intent).map((k) =>
      MODULE_CAPABILITY_MANIFEST_V1.find((m) => m.moduleKey === k),
    ).filter(Boolean);
  }, [parsed]);

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-gray-900/15 backdrop-blur-md transition-opacity"
      {...backdropHandlers}
    >
      <div className="w-[min(720px,92vw)] max-h-[88vh] overflow-y-auto rounded-2xl bg-white shadow-[0_24px_70px_rgba(15,23,42,0.18)] ring-1 ring-inset ring-gray-100">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 px-6 pt-5 pb-3 border-b border-gray-100">
          <div>
            <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.18em] text-gray-400">
              <Sparkles size={11} className="text-[#5B7BFE]" strokeWidth={2.2} />
              AI Command Center
            </div>
            <div className="mt-1 text-[16px] font-light tracking-tight text-gray-900">
              AI 工作指令
            </div>
            <p className="mt-0.5 text-[11.5px] text-gray-500">
              可以快速建任务, 也可以 @AI 同事让它帮你推进复杂工作.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={stage === 'parsing' || stage === 'submitting'}
            className="shrink-0 inline-flex h-8 w-8 items-center justify-center rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-40"
            aria-label="关闭"
          >
            <X size={16} />
          </button>
        </div>

        {/* Stage: input — 用户输入 */}
        {stage === 'input' && (
          <div className="px-6 py-4 space-y-3">
            {/* mode toggle */}
            <div className="flex items-center gap-2 text-[11px]">
              <span className="text-gray-400">模式:</span>
              <button
                type="button"
                onClick={() => setMode('ai_command')}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  mode === 'ai_command'
                    ? 'bg-[#5B7BFE] text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                <Bot size={11} className="inline mr-1" /> AI 同事推进
              </button>
              <button
                type="button"
                onClick={() => setMode('quick_task')}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  mode === 'quick_task'
                    ? 'bg-[#5B7BFE] text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                快速建任务
              </button>
              <span className="ml-auto text-[10px] text-gray-400">
                {mode === 'ai_command' ? '复杂任务 → AI 拆解+审批' : '一句话 → 直接建任务'}
              </span>
            </div>

            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                  e.preventDefault();
                  void handleParse();
                }
              }}
              placeholder={
                mode === 'ai_command'
                  ? '例如: @庆华 帮我为安然集团生成一份集团介绍, 并申请放入客户工作台.\n如果我说不用审批, 直接执行第一步, 就按我的授权先开始.'
                  : '例如: 明天下午三点提醒我联系日慈发补充协议.'
              }
              className="w-full h-32 px-3 py-2.5 text-[13px] text-gray-900 placeholder:text-gray-400 bg-gray-50 rounded-lg border border-gray-200 focus:bg-white focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/15 outline-none resize-none"
            />

            {errorMessage && (
              <div className="flex items-start gap-2 px-3 py-2 bg-red-50 border border-red-100 rounded-md text-[12px] text-red-700">
                <AlertCircle size={13} className="mt-0.5 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            <div className="flex items-center justify-between pt-1">
              <span className="text-[10px] text-gray-400">Cmd/Ctrl + Enter 提交</span>
              <button
                type="button"
                onClick={handleParse}
                disabled={!text.trim()}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 text-[12.5px] font-medium text-white bg-[#5B7BFE] hover:bg-[#4A63CF] disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                <Sparkles size={13} strokeWidth={2.2} />
                {mode === 'ai_command' ? '让 AI 同事来推进' : '解析任务字段'}
              </button>
            </div>
          </div>
        )}

        {/* Stage: parsing — 解析中 */}
        {stage === 'parsing' && (
          <div className="px-6 py-12 flex flex-col items-center gap-3">
            <Loader2 size={28} className="text-[#5B7BFE] animate-spin" />
            <div className="text-[13px] text-gray-600">正在解析指令...</div>
            {parsed?.bot_handle && (
              <div className="text-[11px] text-gray-400">@{parsed.bot_handle} · {parsed.intent}</div>
            )}
          </div>
        )}

        {/* Stage: bot_resolved — 显示 bot card + 进入计划按钮 */}
        {stage === 'bot_resolved' && bot && parsed && (
          <div className="px-6 py-4 space-y-3">
            <div className="rounded-lg border border-[#5B7BFE]/20 bg-gradient-to-br from-[#5B7BFE]/5 to-transparent p-4">
              <div className="flex items-center gap-2">
                <Bot size={16} className="text-[#5B7BFE]" />
                <span className="text-[14px] font-medium text-gray-900">{bot.display_name}</span>
                <span className="text-[10px] text-gray-400 ml-1">· AI 同事</span>
              </div>
              <div className="mt-1 text-[11.5px] text-gray-600">
                {bot.department_name || '未分配部门'} · actor_id=<code className="text-[10px] bg-gray-100 px-1 rounded">{bot.actor_id}</code>
              </div>
              <div className="mt-2 text-[11px] text-gray-500">
                汇报给: {bot.reporting_approvers.map((a) => a.role).join(' / ')}
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                {bot.enabled_capabilities.map((cap) => (
                  <span key={cap} className="text-[9.5px] px-1.5 py-0.5 bg-[#5B7BFE]/10 text-[#3B5BCF] rounded">{cap}</span>
                ))}
              </div>
            </div>

            <div className="rounded-md bg-gray-50 px-3 py-2 text-[11.5px] text-gray-700">
              <div className="font-medium mb-1">我理解的任务</div>
              <div className="text-gray-600">{parsed.original_text.slice(0, 200)}{parsed.original_text.length > 200 ? '...' : ''}</div>
              <div className="mt-2 text-[10.5px] text-gray-500">
                Intent: <code className="bg-white px-1 rounded">{parsed.intent}</code>
                {parsed.inline_authorization_detected && (
                  <span className="ml-2 text-amber-600">★ 检测到指令内授权: "{parsed.inline_authorization_text}"</span>
                )}
              </div>
            </div>

            {errorMessage && (
              <div className="flex items-start gap-2 px-3 py-2 bg-red-50 border border-red-100 rounded-md text-[12px] text-red-700">
                <AlertCircle size={13} className="mt-0.5 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            <div className="flex items-center justify-between pt-1 gap-2">
              <button type="button" onClick={handleSwitchToQuickTask} className="text-[11px] text-gray-500 hover:text-gray-700">
                作为普通任务创建
              </button>
              <button
                type="button"
                onClick={handleEnterPlan}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 text-[12.5px] font-medium text-white bg-[#5B7BFE] hover:bg-[#4A63CF] rounded-lg transition-colors"
              >
                查看执行计划 <ChevronRight size={13} />
              </button>
            </div>
          </div>
        )}

        {/* Stage: plan_preview — 执行计划卡 */}
        {stage === 'plan_preview' && bot && parsed && (
          <div className="px-6 py-4 space-y-3">
            <div className="text-[14px] font-medium text-gray-900">{bot.display_name} 的执行计划</div>

            {/* 模块调用计划 */}
            <div>
              <div className="text-[11px] font-medium text-gray-700 mb-1.5">需要调用的模块</div>
              <div className="space-y-1.5">
                {recommendedModules.map((m) => m && (
                  <div key={m.moduleKey} className="flex items-center gap-2 px-2.5 py-1.5 bg-gray-50 rounded-md text-[11.5px]">
                    <span className={`w-1.5 h-1.5 rounded-full ${m.enabled ? 'bg-emerald-500' : 'bg-gray-300'}`} />
                    <span className="font-medium text-gray-800">{m.moduleName}</span>
                    <span className="text-gray-500">— {m.description.slice(0, 35)}...</span>
                    {!m.enabled && <span className="ml-auto text-[10px] text-amber-600">未启用</span>}
                  </div>
                ))}
              </div>
            </div>

            {/* 预期产出 */}
            {parsed.requested_outputs.length > 0 && (
              <div>
                <div className="text-[11px] font-medium text-gray-700 mb-1.5">预期产出</div>
                <ul className="space-y-0.5 text-[11.5px] text-gray-600">
                  {parsed.requested_outputs.map((o, i) => (
                    <li key={i} className="flex items-center gap-1.5">
                      <CheckCircle2 size={11} className="text-emerald-500" /> {o}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 当前限制 */}
            <div className="rounded-md bg-amber-50 border border-amber-100 px-3 py-2 text-[11px] text-amber-800">
              <div className="font-medium mb-0.5">当前限制</div>
              <ul className="list-disc list-inside space-y-0.5">
                <li>合同草稿 / 模板生成 endpoint 未暴露 (V3.0 P0-1/P0-2 blocked_by_A)</li>
                <li>写入客户工作台正式文件需经审批 (不直写)</li>
                <li>触发数据中心解析需经审批</li>
                <li>AI 生成内容不会自动标为客户官方资料</li>
              </ul>
            </div>

            {/* inline authorization 提示 */}
            {parsed.inline_authorization_detected && (
              <div className="rounded-md bg-emerald-50 border border-emerald-100 px-3 py-2 text-[11px] text-emerald-800">
                <div className="font-medium">✓ 检测到指令内授权</div>
                <div className="text-emerald-700 mt-0.5">
                  你的原话: "{parsed.inline_authorization_text}". 后端将校验你是否为 {bot.display_name} 的审批人, 通过后直接 inline approve.
                </div>
              </div>
            )}

            {errorMessage && (
              <div className="flex items-start gap-2 px-3 py-2 bg-red-50 border border-red-100 rounded-md text-[12px] text-red-700">
                <AlertCircle size={13} className="mt-0.5 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            <div className="flex items-center justify-between pt-1 gap-2 flex-wrap">
              <button type="button" onClick={() => setStage('bot_resolved')} className="text-[11px] text-gray-500 hover:text-gray-700">
                返回
              </button>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setStage('input')}
                  className="text-[11px] text-gray-600 hover:text-gray-900 px-2 py-1"
                >
                  修改计划
                </button>
                <button
                  type="button"
                  onClick={handleSubmitPlan}
                  className="inline-flex items-center gap-1.5 px-4 py-1.5 text-[12.5px] font-medium text-white bg-[#5B7BFE] hover:bg-[#4A63CF] rounded-lg transition-colors"
                >
                  {parsed.inline_authorization_detected
                    ? '按指令授权创建并执行第一步'
                    : '创建 AI 任务并提交审批'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Stage: submitting */}
        {stage === 'submitting' && (
          <div className="px-6 py-12 flex flex-col items-center gap-3">
            <Loader2 size={28} className="text-[#5B7BFE] animate-spin" />
            <div className="text-[13px] text-gray-600">正在提交 AI 任务计划...</div>
          </div>
        )}

        {/* Stage: submitted */}
        {stage === 'submitted' && submitResult && (
          <div className="px-6 py-6 space-y-3">
            <div className="flex items-center gap-2 text-[14px] font-medium text-emerald-700">
              <CheckCircle2 size={18} /> AI 任务已创建
            </div>
            <div className="rounded-md bg-emerald-50 border border-emerald-100 px-3 py-2.5 text-[11.5px] text-emerald-800 space-y-1">
              <div>task_id: <code className="bg-white px-1 rounded text-[10px]">{submitResult.task_id}</code></div>
              <div>ai_task_plan_id: <code className="bg-white px-1 rounded text-[10px]">{submitResult.ai_task_plan_id}</code></div>
              <div>status: <span className="font-medium">{submitResult.status}</span></div>
            </div>
            <div className="text-[11.5px] text-gray-600 leading-relaxed">
              {submitResult.status === 'approved'
                ? `inline 授权已生效, ${bot?.display_name} 可以开始执行第一步.`
                : `等待审批 (${bot?.reporting_approvers.map((a) => a.role).join(' / ')}). 审批通过后, ${bot?.display_name} 才会开始执行.`}
            </div>
            <div className="text-[10.5px] text-gray-400">
              所有动作将带 actor_id=<code className="bg-gray-50 px-1 rounded">{bot?.actor_id}</code> 写入 agent_run_log.
            </div>
            <button type="button" onClick={onClose} className="w-full mt-2 px-4 py-2 text-[12.5px] font-medium text-white bg-[#5B7BFE] hover:bg-[#4A63CF] rounded-lg transition-colors">
              完成
            </button>
          </div>
        )}

        {/* Stage: error */}
        {stage === 'error' && (
          <div className="px-6 py-6 space-y-3">
            <div className="flex items-center gap-2 text-[14px] font-medium text-red-700">
              <AlertCircle size={18} /> 出错了
            </div>
            <div className="rounded-md bg-red-50 border border-red-100 px-3 py-2 text-[12px] text-red-700">
              {errorMessage || '未知错误'}
            </div>
            <div className="flex items-center justify-between gap-2">
              <button type="button" onClick={handleSwitchToQuickTask} className="text-[11px] text-gray-500 hover:text-gray-700">
                作为普通任务创建
              </button>
              <button type="button" onClick={() => setStage('input')} className="px-4 py-1.5 text-[12.5px] font-medium text-white bg-[#5B7BFE] hover:bg-[#4A63CF] rounded-lg transition-colors">
                重新尝试
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
