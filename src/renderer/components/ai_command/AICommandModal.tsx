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
  listBotMembers,
  getBotTaskPlanProgress,
  type TaskAiParseResult,
  type BotPermissionsResponse,
  type BotMemberRecord,
  type PlanProgressRecord,
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
  /** 已知客户名列表 (用于 parseSmartCommand 命中匹配). */
  knownClientNames?: string[];
  /** 上下文默认客户 id (如果是从客户详情触发); ai_command 模式优先用解析到的 client_name 反查 id. */
  defaultClientId?: string;
  /** 客户 id 反查表: parsed.client_name → client_id; AICommandModal 自动用. */
  clientsForResolve?: Array<{ id: string; name: string }>;
  /** 当前登录用户 id, 用于 inline_authorization 时作为 human_initiator (审批人本人). */
  currentUserId?: string;
};

type Stage = 'input' | 'parsing' | 'bot_resolved' | 'plan_preview' | 'submitting' | 'submitted' | 'error';

export function AICommandModal({
  open,
  onClose,
  onQuickTaskParsed,
  knownClientNames = [],
  defaultClientId,
  clientsForResolve = [],
  currentUserId,
}: AICommandModalProps) {
  const [text, setText] = useState('');
  const [stage, setStage] = useState<Stage>('input');
  const [mode, setMode] = useState<AICommandMode>('ai_command');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [parsed, setParsed] = useState<ParsedSmartCommand | null>(null);
  const [bot, setBot] = useState<BotResolveResult | null>(null);
  const [permissions, setPermissions] = useState<BotPermissionsResponse | null>(null);
  const [submitResult, setSubmitResult] = useState<{ task_id: string; ai_task_plan_id: string; status: string } | null>(null);
  const [availableBots, setAvailableBots] = useState<BotMemberRecord[]>([]);
  // M10 (A, 2026-05-25) · plan 执行进度轮询 (2s)
  const [planProgress, setPlanProgress] = useState<PlanProgressRecord | null>(null);
  const [progressError, setProgressError] = useState<string | null>(null);
  const progressTimerRef = useRef<number | null>(null);
  // ── M7: inline @mention picker 状态 (顾源源 5/25: 微信群那种弹窗) ──
  // mentionState: 仅当 textarea 当前 cursor 紧跟在 @<query> 后才 open.
  //   - atPos: '@' 在 text 里的下标
  //   - query: '@' 后到 cursor 之间的字符串 (filter 关键字)
  const [mentionState, setMentionState] = useState<{ open: boolean; query: string; atPos: number } | null>(null);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  // 中文 IME composition 中不弹 picker, end 后再检测一次
  const isComposingRef = useRef(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // ★ open 时拉 active 机器人列表 (顾源源 5/24: @ 下拉支持)
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    void listBotMembers({ status: 'active' }).then((data) => {
      if (cancelled) return;
      setAvailableBots(data.items || []);
    }).catch(() => {
      // 拉失败不阻塞 modal, 用户仍能手动输 @庆华
    });
    return () => { cancelled = true; };
  }, [open]);

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
      setPlanProgress(null);
      setProgressError(null);
    }
  }, [open]);

  // M10 · 进度轮询: submitted + approved 时, 每 2s GET 一次, 终态停止
  useEffect(() => {
    const planId = submitResult?.ai_task_plan_id;
    const isApproved = submitResult?.status === 'approved';
    if (stage !== 'submitted' || !planId || !isApproved) {
      return;
    }
    let cancelled = false;
    setPlanProgress(null);
    setProgressError(null);
    const tick = async () => {
      if (cancelled) return;
      try {
        const result = await getBotTaskPlanProgress(planId);
        if (cancelled) return;
        setPlanProgress(result);
        // 终态停轮询
        if (
          result.execution_status === 'success' ||
          result.execution_status === 'failed' ||
          result.execution_status === 'partial'
        ) {
          if (progressTimerRef.current !== null) {
            window.clearInterval(progressTimerRef.current);
            progressTimerRef.current = null;
          }
        }
      } catch (err: unknown) {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : '进度查询失败';
        setProgressError(msg);
      }
    };
    void tick(); // 立即拉一次, 不等 2s
    progressTimerRef.current = window.setInterval(() => {
      void tick();
    }, 2000);
    return () => {
      cancelled = true;
      if (progressTimerRef.current !== null) {
        window.clearInterval(progressTimerRef.current);
        progressTimerRef.current = null;
      }
    };
  }, [stage, submitResult?.ai_task_plan_id, submitResult?.status]);

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

  // ★ useMemo 必须在 if (!open) return null 之前 — React Hooks Rule:
  // 所有 hooks 每次 render 必须按相同顺序调用. 早期 return 后的 hook
  // 会导致 "Rendered more hooks than during the previous render".
  const recommendedModules = useMemo(() => {
    if (!parsed) return [];
    return recommendModulesForIntent(parsed.intent).map((k) =>
      MODULE_CAPABILITY_MANIFEST_V1.find((m) => m.moduleKey === k),
    ).filter(Boolean);
  }, [parsed]);

  if (!open) return null;

  // ── 选 AI 同事: 自动 prepend "@<handle> " 到 textarea start (顾源源 5/24, 旧入口) ──
  // 注: M7 把 UI 入口换成 inline @mention picker 后, picker 走 insertMentionFromPicker.
  // 本方法保留, 供未来其它代码路径 (如 quick fill) 调用, 不在 render 树中触发.
  const handleSelectBot = (bot: BotMemberRecord) => {
    const mention = `@${bot.handle} `;
    setText((prev) => {
      // 如果开头已经是 @xxx (任何 @), 替换它; 否则 prepend
      const reMention = /^@[^\s]+\s*/;
      if (reMention.test(prev)) {
        return prev.replace(reMention, mention);
      }
      return mention + prev;
    });
    setMode('ai_command');
    // focus 回输入框, 光标到末尾
    window.setTimeout(() => {
      const ta = textareaRef.current;
      if (ta) {
        ta.focus();
        ta.selectionStart = ta.selectionEnd = ta.value.length;
      }
    }, 30);
  };

  // ── M7: inline mention 检测 (顾源源 5/25 微信群弹窗体验) ──
  // 从 cursor 往回找最近的 '@'; 若 '@' 后到 cursor 之间是合法 mention 字符 (中文/英文/数字/下划线, 无空白),
  // 且 '@' 前是 空白/换行/字符串开头 → 触发 picker.
  const MENTION_TOKEN_RE = /^[一-龥A-Za-z0-9_]*$/;

  const detectMention = (value: string, cursor: number) => {
    if (isComposingRef.current) return; // IME 中不弹
    // 从 cursor-1 往回扫
    let atPos = -1;
    for (let i = cursor - 1; i >= 0; i--) {
      const ch = value[i];
      if (ch === '@') {
        atPos = i;
        break;
      }
      // 命中空白/换行 → 视为离开 mention 范围
      if (ch === ' ' || ch === '\n' || ch === '\t' || ch === '\r') {
        break;
      }
    }
    if (atPos < 0) {
      setMentionState(null);
      return;
    }
    // '@' 前必须是 空白/换行/字符串开头
    const prevCh = atPos === 0 ? '' : value[atPos - 1];
    if (prevCh && prevCh !== ' ' && prevCh !== '\n' && prevCh !== '\t' && prevCh !== '\r') {
      setMentionState(null);
      return;
    }
    const query = value.slice(atPos + 1, cursor);
    if (!MENTION_TOKEN_RE.test(query)) {
      setMentionState(null);
      return;
    }
    setMentionState({ open: true, query, atPos });
    setHighlightedIndex(0);
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newText = e.target.value;
    const cursor = e.target.selectionStart || 0;
    setText(newText);
    detectMention(newText, cursor);
  };

  // 给 picker 用的过滤后列表 (大小写不敏感; 中文直接 includes)
  const filteredBots: BotMemberRecord[] = (() => {
    if (!mentionState?.open) return [];
    const q = mentionState.query.toLowerCase();
    if (!q) return availableBots;
    return availableBots.filter((b) => {
      const handle = (b.handle || '').toLowerCase();
      const name = (b.display_name || '').toLowerCase();
      return handle.includes(q) || name.includes(q) || b.display_name.includes(mentionState.query);
    });
  })();

  const insertMentionFromPicker = (bot: BotMemberRecord) => {
    if (!mentionState) return;
    const ta = textareaRef.current;
    if (!ta) return;
    const cursor = ta.selectionStart || 0;
    const before = text.slice(0, mentionState.atPos);
    const after = text.slice(cursor);
    const insert = `@${bot.handle} `;
    const newText = before + insert + after;
    setText(newText);
    setMentionState(null);
    setMode('ai_command');
    const newCursor = mentionState.atPos + insert.length;
    window.setTimeout(() => {
      const t = textareaRef.current;
      if (t) {
        t.focus();
        t.setSelectionRange(newCursor, newCursor);
      }
    }, 0);
  };

  const handleTextareaKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // picker 打开时拦截方向键 / Enter / Tab / Esc
    if (mentionState?.open && filteredBots.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlightedIndex((i) => (i + 1) % filteredBots.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlightedIndex((i) => (i - 1 + filteredBots.length) % filteredBots.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        const target = filteredBots[highlightedIndex] || filteredBots[0];
        if (target) insertMentionFromPicker(target);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setMentionState(null);
        return;
      }
    } else if (mentionState?.open && filteredBots.length === 0 && e.key === 'Escape') {
      e.preventDefault();
      setMentionState(null);
      return;
    }
    // 默认: Cmd/Ctrl+Enter 提交
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      void handleParse();
    }
  };

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

      // 顾源源 5/24 真用反馈洞察: "确认这个流程 = 审批本身"
      // 用户点"我审批通过"那一刻, 就是他作为审批人在 inline auth.
      // 所以总是传 inline_authorization=true + human_initiator_id (= 当前 user).
      // backend 会校验 user 是否是 bot 审批人, 通过则直接 approved, 不通过仍 pending.
      // 反查 client_id: 优先用 parsed.client_name 命中 clientsForResolve, 否则用 defaultClientId.
      // 顾源源 5/24 反馈: 真用指令带"安然集团", AICommandModal 之前没接 clientsForResolve,
      // → plan.client_id=空 → 庆华 (M7 接好后) 也不知道该写哪个客户工作台.
      const resolvedClientId =
        (parsed.client_name && clientsForResolve.find((c) => c.name === parsed.client_name)?.id) ||
        defaultClientId;

      const result = await createBotTaskPlan(bot.bot_member_id, {
        plan_title: planTitle,
        plan_text: text,
        client_id: resolvedClientId,
        required_modules: moduleNames,
        steps: [],
        expected_outputs: parsed.requested_outputs,
        approval_required: true,
        inline_authorization: true,
        inline_authorization_text:
          parsed.inline_authorization_text || `${bot.display_name} 由我本人 (审批人) 当场确认执行`,
        human_initiator_id: currentUserId || 'user_guyuan',
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
  // (recommendedModules useMemo 已上移到 if (!open) 之前, 避免 Hooks Rule 违反)

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

            {/* M7: textarea + inline @mention picker — 顾源源 5/25 微信群体验 */}
            <div className="relative">
              <textarea
                ref={textareaRef}
                value={text}
                onChange={handleTextareaChange}
                onKeyDown={handleTextareaKeyDown}
                onCompositionStart={() => { isComposingRef.current = true; }}
                onCompositionEnd={(e) => {
                  isComposingRef.current = false;
                  // composition 结束后再跑一次检测 (例如刚输完 "@庆华")
                  detectMention(e.currentTarget.value, e.currentTarget.selectionStart || 0);
                }}
                placeholder={
                  mode === 'ai_command'
                    ? '例如: @庆华 帮我为安然集团生成一份集团介绍, 并申请放入客户工作台.\n如果我说不用审批, 直接执行第一步, 就按我的授权先开始.'
                    : '例如: 明天下午三点提醒我联系日慈发补充协议.'
                }
                className="w-full h-32 px-3 py-2.5 text-[13px] text-gray-900 placeholder:text-gray-400 bg-gray-50 rounded-lg border border-gray-200 focus:bg-white focus:border-[#5B7BFE] focus:ring-2 focus:ring-[#5B7BFE]/15 outline-none resize-none"
              />
              {mode === 'ai_command' && mentionState?.open && (
                <MentionPicker
                  bots={availableBots}
                  query={mentionState.query}
                  highlightedIndex={highlightedIndex}
                  onHover={setHighlightedIndex}
                  onSelect={insertMentionFromPicker}
                />
              )}
            </div>

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
                  title="点击=我作为审批人当场确认这个流程 (你本人就是审批人, 不会再去审批中心走二次流程)"
                >
                  ✓ 确认执行 — 我审批通过
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

        {/* Stage: submitted - 顾源源 5/24 真用反馈: "确认这个流程 = 审批本身; 任务结束要类似邮件通知" */}
        {/* M10 (A, 2026-05-25) · approved 路径加进度轮询展示 */}
        {stage === 'submitted' && submitResult && (
          <div className="px-6 py-6 space-y-3">
            {submitResult.status === 'approved' ? (
              <>
                <div className="flex items-center gap-2 text-[14px] font-medium text-emerald-700">
                  <CheckCircle2 size={18} /> 你已确认 — {bot?.display_name} 开始执行
                </div>
                <PlanProgressView
                  progress={planProgress}
                  error={progressError}
                  botName={bot?.display_name || '机器人'}
                />
              </>
            ) : (
              <>
                <div className="flex items-center gap-2 text-[14px] font-medium text-amber-700">
                  <AlertCircle size={18} /> 还差一步审批
                </div>
                <div className="rounded-md bg-amber-50 border border-amber-100 px-3 py-2.5 text-[11.5px] text-amber-800 leading-relaxed">
                  你不在 {bot?.display_name} 的审批人列表 ({(bot?.reporting_approvers || []).map((a) => a.role).join(' / ') || '未配置'}),
                  系统已转交真正的审批人. 通过后 {bot?.display_name} 才会执行.
                </div>
              </>
            )}
            <div className="rounded-md bg-gray-50 border border-gray-100 px-3 py-2 text-[10.5px] text-gray-500 space-y-0.5 font-mono">
              <div>task_id: {submitResult.task_id || '(无关联任务)'}</div>
              <div>plan_id: {submitResult.ai_task_plan_id}</div>
              <div>actor: {bot?.actor_id}</div>
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

// ── M10 (A, 2026-05-25) · plan 执行进度展示 (顾源源 5/24: "复杂任务 5-30 min 必须看得到进度") ──
type PlanProgressViewProps = {
  progress: PlanProgressRecord | null;
  error: string | null;
  botName: string;
};

function PlanProgressView({ progress, error, botName }: PlanProgressViewProps) {
  if (error) {
    return (
      <div className="rounded-md bg-red-50 border border-red-100 px-3 py-2 text-[11.5px] text-red-700 leading-relaxed">
        进度查询失败: {error}
      </div>
    );
  }
  if (!progress) {
    return (
      <div className="rounded-md bg-emerald-50 border border-emerald-100 px-3 py-2.5 text-[11.5px] text-emerald-800 leading-relaxed flex items-center gap-2">
        <Loader2 size={12} className="animate-spin" />
        <span>正在准备执行... {botName} 已收到指令</span>
      </div>
    );
  }

  const exec = progress.execution_status;
  const pct = Math.max(0, Math.min(100, progress.progress?.percent ?? 0));
  const total = progress.progress?.total ?? 0;
  const completed = progress.progress?.completed ?? 0;
  const current = progress.progress?.current || '';
  const subtasks = progress.subtasks || [];

  let headerEl: React.ReactNode = null;
  if (exec === 'not_started' || exec === 'pending_execute') {
    headerEl = (
      <div className="text-[11.5px] text-emerald-800 flex items-center gap-2">
        <Loader2 size={12} className="animate-spin" />
        <span>等待执行... {botName} 已接收, 即将开跑</span>
      </div>
    );
  } else if (exec === 'running') {
    headerEl = (
      <div className="text-[11.5px] text-emerald-800 flex items-center gap-2">
        <Loader2 size={12} className="animate-spin" />
        <span>{current || '正在执行'} ({completed}/{total})</span>
      </div>
    );
  } else if (exec === 'success') {
    headerEl = (
      <div className="text-[11.5px] text-emerald-800 flex items-center gap-2">
        <CheckCircle2 size={12} />
        <span>已完成 ({completed}/{total} 个子任务)</span>
      </div>
    );
  } else if (exec === 'partial') {
    headerEl = (
      <div className="text-[11.5px] text-amber-700 flex items-center gap-2">
        <AlertCircle size={12} />
        <span>部分完成 ({completed}/{total} 成功, {(progress.errors || []).length} 失败)</span>
      </div>
    );
  } else if (exec === 'failed') {
    headerEl = (
      <div className="text-[11.5px] text-red-700 flex items-center gap-2">
        <AlertCircle size={12} />
        <span>执行失败 (0/{total} 成功)</span>
      </div>
    );
  }

  const barColor =
    exec === 'success' ? 'bg-emerald-500'
    : exec === 'failed' ? 'bg-red-400'
    : exec === 'partial' ? 'bg-amber-400'
    : 'bg-[#5B7BFE]';

  return (
    <div className="space-y-2">
      <div className="rounded-md bg-emerald-50 border border-emerald-100 px-3 py-2.5 space-y-2">
        {headerEl}
        {total > 0 && (
          <div className="w-full h-1 bg-emerald-100 rounded-full overflow-hidden ring-1 ring-inset ring-emerald-200/50">
            <div
              className={`h-full ${barColor} transition-all duration-300`}
              style={{ width: `${pct}%` }}
            />
          </div>
        )}
        <div className="text-[10px] text-emerald-700/80">{pct}%</div>
      </div>

      {subtasks.length > 0 && (
        <div className="rounded-md bg-white border border-gray-200 ring-1 ring-inset ring-gray-100 divide-y divide-gray-100">
          {subtasks.map((st) => {
            const iconColor =
              st.status === 'success' ? 'text-emerald-600'
              : st.status === 'failed' ? 'text-red-500'
              : st.status === 'running' ? 'text-[#5B7BFE]'
              : 'text-gray-400';
            const iconEl =
              st.status === 'success' ? <CheckCircle2 size={11} className={iconColor} />
              : st.status === 'failed' ? <AlertCircle size={11} className={iconColor} />
              : st.status === 'running' ? <Loader2 size={11} className={`${iconColor} animate-spin`} />
              : <ChevronRight size={11} className={iconColor} />;
            return (
              <div key={st.index} className="px-3 py-1.5 flex items-start gap-2 text-[11px]">
                <div className="mt-0.5">{iconEl}</div>
                <div className="flex-1 min-w-0">
                  <div className="text-gray-700 font-medium truncate">
                    <span className="text-gray-400 mr-1">#{st.index + 1}</span>{st.tool}
                  </div>
                  {st.output_summary && (
                    <div className="text-[10.5px] text-gray-500 mt-0.5 leading-relaxed break-words">
                      {st.output_summary}
                    </div>
                  )}
                  {st.error && (
                    <div className="text-[10.5px] text-red-600 mt-0.5 leading-relaxed break-words">
                      错误: {st.error}
                    </div>
                  )}
                </div>
                {typeof st.duration_ms === 'number' && (
                  <div className="text-[9.5px] text-gray-400 shrink-0 mt-0.5 tabular-nums">
                    {st.duration_ms}ms
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── M7: inline @mention picker (顾源源 5/25 微信群体验) ──
// 注: inline 在本文件, 不单独建文件 (顾源源 hard rule).
// 风格对齐 LeaderPicker: ring-1 inset, rounded-lg, shadow-lg, 主色 #5B7BFE.
type MentionPickerProps = {
  bots: BotMemberRecord[];
  query: string;
  highlightedIndex: number;
  onHover: (i: number) => void;
  onSelect: (bot: BotMemberRecord) => void;
};

function MentionPicker({ bots, query, highlightedIndex, onHover, onSelect }: MentionPickerProps) {
  // 过滤 — 与父组件 filteredBots 同口径 (大小写不敏感, 中文 includes 原 query)
  const q = query.toLowerCase();
  const filtered = !q
    ? bots
    : bots.filter((b) => {
        const handle = (b.handle || '').toLowerCase();
        const name = (b.display_name || '').toLowerCase();
        return handle.includes(q) || name.includes(q) || b.display_name.includes(query);
      });

  return (
    <div
      className="absolute left-0 top-full mt-1 z-[70] w-[320px] max-h-[280px] overflow-y-auto bg-white rounded-lg shadow-lg ring-1 ring-inset ring-gray-200"
      // 阻止 mousedown 抢 textarea focus (否则 onClick 之前 textarea blur, cursor 丢)
      onMouseDown={(e) => e.preventDefault()}
    >
      {filtered.length === 0 ? (
        <div className="px-3 py-3 text-[11.5px] text-gray-400 leading-relaxed">
          无匹配的机器人同事 — 你可以手动输 @庆华
        </div>
      ) : (
        filtered.map((b, i) => {
          const highlighted = highlightedIndex === i;
          return (
            <button
              key={b.id}
              type="button"
              onMouseEnter={() => onHover(i)}
              onClick={() => onSelect(b)}
              className={`w-full text-left px-3 py-2 border-b border-gray-100 last:border-b-0 transition-colors ${
                highlighted ? 'bg-[#5B7BFE]/10' : 'hover:bg-gray-50'
              }`}
            >
              <div className={`flex items-center gap-2 text-[12.5px] font-medium ${highlighted ? 'text-gray-900' : 'text-gray-800'}`}>
                <Bot size={11} className="text-[#5B7BFE]" />
                <span>{b.display_name}</span>
                <span className={`text-[10.5px] ${highlighted ? 'text-gray-500' : 'text-gray-400'}`}>@{b.handle}</span>
                <span className="ml-auto text-[9.5px] px-1.5 py-0.5 rounded bg-[#5B7BFE]/10 text-[#3B5BCF]">{b.actor_type}</span>
              </div>
              <div className={`mt-0.5 text-[10.5px] ${highlighted ? 'text-gray-500' : 'text-gray-400'}`}>
                {b.department_name || '未分配部门'}
              </div>
            </button>
          );
        })
      )}
    </div>
  );
}
