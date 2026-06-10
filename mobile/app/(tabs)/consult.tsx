import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ExpoSpeechRecognitionModule, useSpeechRecognitionEvent } from "expo-speech-recognition";
import { AudioModule } from "expo-audio";
import * as Clipboard from "expo-clipboard";
import { useAppChromeInsets } from "../../lib/app-chrome";
import { SimpleMarkdown } from "../../lib/simple-markdown";
import {
  colors,
  fontSize,
  spacing,
  borderRadius,
  shadow,
  palette,
  typography,
} from "../../lib/theme";
import { useAndroidBackToTasks } from "../../lib/android-back";
import { ChevronDown, Mic, Send, Copy, Layers, FileText, Clock, CheckCircle2, AlertCircle, ListPlus, BookOpen, AlertTriangle } from "lucide-react-native";
import { useRouter, type ErrorBoundaryProps } from "expo-router";
import { RouteErrorFallback } from "../../components/ErrorBoundary";
import { setPendingConsultDraft } from "../../lib/consult-to-task";
import { enqueueConsultationKnowledgeRequest, fetchConsultationKnowledgeRequests, fetchMobileCapabilities, sendConsultationChat } from "../../lib/api";
import type { ConsultationKnowledgeRequestRecord } from "../../lib/api";
import * as cache from "../../lib/cache";
import { useTaskBoard } from "../../lib/task-board-store";
import { useRenderCount } from "../../lib/use-render-count";
import EventLineDrawer from "../../components/EventLineDrawer";
import WorkspaceLiteSheet from "../../components/WorkspaceLiteSheet";
import { useCurrentFocus } from "../../lib/current-focus-store";
import { useClientIntel } from "../../lib/client-intel-store";
import { buildConsultRequestContext } from "../../lib/consult-context-adapter";
import { normalizeConsultationResponseForMobile } from "../../lib/consult-response-core";
import {
  freezeConsultThreadContext,
  hasConsultThreadContextDrift,
  refreshConsultThreadContext,
} from "../../lib/consult-thread-context";
import { transferEventLineToClient } from "../../lib/event-line-client-transfer";
import {
  buildConsultContextOptions,
  resolveConsultContextFromFocus,
  type ConsultContextOption,
} from "../../lib/consult-context";
import {
  buildSpeechRecognitionErrorMessage,
  getEventTranscript,
  getPermissionGranted,
} from "../../lib/local-speech-recognition-core";
import type { ConsultThreadContextSnapshot, MobileCapabilityRecord, SmartTaskDraft } from "../../lib/types";

// ─── Types ──────────────────────────────────────

interface ChatMessage {
  readonly id: string;
  readonly role: "ai" | "user";
  readonly text: string;
  readonly answerMode?: "grounded" | "limited_context" | "missing_context" | "error" | null;
  readonly contextQuality?: {
    level?: "none" | "thin" | "partial" | "rich" | string;
    availableSources?: string[];
    missingSources?: string[];
    staleSources?: string[];
    contextBundleHash?: string | null;
  } | null;
  readonly evidence?: Array<{
    id: string;
    type: string;
    title: string;
    updatedAt?: string | null;
    snippet?: string | null;
  }>;
  readonly missingContext?: Array<{
    type: string;
    message: string;
  }>;
}

// ─── Constants ──────────────────────────────────

const AI_THINKING_PLACEHOLDER = "正在思考...";

const EVIDENCE_TYPE_LABEL: Record<string, string> = {
  workspace: "客户工作台",
  client_dna: "客户档案",
  event_line: "事件线",
  meeting: "会议纪要",
  task: "任务",
  knowledge_surrogate: "知识库",
  cockpit: "战略驾驶舱",
  thread_snapshot: "上下文快照",
  task_board: "任务板",
  client_name: "客户名",
  understanding: "理解快照",
  entity: "实体",
  relation: "关系",
  atomic_fact: "事实",
  contradiction: "矛盾",
  glossary_term: "术语",
};

const MISSING_CONTEXT_TYPE_LABEL: Record<string, string> = {
  client_dna: "客户档案",
  workspace: "客户工作台",
  event_line: "事件线",
  meeting: "会议纪要",
  person_profile: "人物档案",
  project_background: "项目背景",
  strategic_cockpit: "战略驾驶舱",
  knowledge_surrogate: "知识库",
  task_board: "任务板",
  understanding: "理解快照",
};

const ANSWER_MODE_LABEL: Record<string, { text: string; tone: "info" | "warn" | "ok" }> = {
  grounded: { text: "已结合上下文", tone: "ok" },
  limited_context: { text: "上下文有限", tone: "warn" },
  missing_context: { text: "缺少上下文", tone: "warn" },
};

function formatEvidenceType(type: string): string {
  return EVIDENCE_TYPE_LABEL[type] ?? type;
}

function formatMissingContextType(type: string): string {
  return MISSING_CONTEXT_TYPE_LABEL[type] ?? type;
}

const DEFAULT_QUICK_QUESTIONS: readonly string[] = [
  "今天最该推进什么？",
  "这周有哪些未确认的事项？",
  "帮我看一下最近的风险信号",
  "如何开始今日的第一件任务？",
] as const;

/**
 * P0-5: 上下文驱动的快速问题
 * 优先级：事件线 > 客户 > 最近任务 > default
 */
function buildContextualQuickQuestions(args: {
  clientName: string | null;
  eventLineName: string | null;
  pendingTaskTitle: string | null;
}): readonly string[] {
  const { clientName, eventLineName, pendingTaskTitle } = args;
  if (eventLineName) {
    const q: string[] = [
      `${eventLineName} 推进到哪了？`,
      `${eventLineName} 下一步该怎么走？`,
      `${eventLineName} 有哪些卡点？`,
      `${eventLineName} 上次更新讲了什么？`,
    ];
    return q;
  }
  if (clientName) {
    const q: string[] = [
      `${clientName} 现在最该推进什么？`,
      `${clientName} 最近有什么风险？`,
      `${clientName} 上次会议讲了什么？`,
      `${clientName} 还有哪些事没确认？`,
    ];
    return q;
  }
  if (pendingTaskTitle) {
    return [
      `「${pendingTaskTitle}」该怎么开始？`,
      "今天最该推进什么？",
      "这周有哪些未确认的事项？",
      "帮我看一下最近的风险信号",
    ];
  }
  return DEFAULT_QUICK_QUESTIONS;
}

let messageIdCounter = 0;
function nextMessageId(): string {
  messageIdCounter += 1;
  return `msg-${messageIdCounter}`;
}

// ─── Component ──────────────────────────────────

export default function ConsultScreen() {
  useRenderCount("ConsultScreen");
  const chrome = useAppChromeInsets();
  const { board, isHydrated } = useTaskBoard();
  const {
    focus,
    clients,
    eventLines,
    setManualClientFocus,
    setManualClientEventLineFocus,
    setCurrentFocusBrowseFromTask,
    clearStoredCurrentFocus,
    setCurrentFocusBoundaryState,
  } = useCurrentFocus();
  const clientIntel = useClientIntel(focus.clientId);
  const router = useRouter();
  const tasks = board.tasks;
  const contextOptions = useMemo(() => buildConsultContextOptions(tasks), [tasks]);

  // P0-5: 上下文驱动的快速问题（替代 hardcoded DEFAULT_QUICK_QUESTIONS）
  const quickQuestions = useMemo(() => {
    const pendingTask = tasks.find((t) => t.progressStatus !== "done");
    return buildContextualQuickQuestions({
      clientName: focus.clientName || null,
      eventLineName: focus.eventLineName || null,
      pendingTaskTitle: pendingTask?.title || null,
    });
  }, [focus.clientName, focus.eventLineName, tasks]);
  const [showContextPicker, setShowContextPicker] = useState(false);
  const [workspaceClientId, setWorkspaceClientId] = useState<string | null>(null);
  const [showEventLineDrawer, setShowEventLineDrawer] = useState(false);
  const [transferringEventLineId, setTransferringEventLineId] = useState<string | null>(null);

  const [messages, setMessages] = useState<readonly ChatMessage[]>([]);
  const [threadContextSnapshot, setThreadContextSnapshot] = useState<ConsultThreadContextSnapshot | null>(null);
  const [inputText, setInputText] = useState("");
  const [headerHeight, setHeaderHeight] = useState(0);
  const [pendingKnowledgeActionKey, setPendingKnowledgeActionKey] = useState<string | null>(null);
  const [knowledgeRequests, setKnowledgeRequests] = useState<readonly ConsultationKnowledgeRequestRecord[]>([]);
  const [showKnowledgePanel, setShowKnowledgePanel] = useState(false);
  const [isVoiceInputActive, setIsVoiceInputActive] = useState(false);
  const [backendCapabilities, setBackendCapabilities] = useState<MobileCapabilityRecord | null>(null);
  const [backendCapabilityError, setBackendCapabilityError] = useState<string | null>(null);

  const [keyboardVisible, setKeyboardVisible] = useState(false);
  const flatListRef = useRef<FlatList<ChatMessage>>(null);
  const voiceInputOwnerRef = useRef(false);

  const selectedContext = useMemo(
    () => resolveConsultContextFromFocus(contextOptions, focus),
    [contextOptions, focus],
  );
  const selectedEventLine = useMemo(
    () => eventLines.find((item) => item.id === selectedContext.eventLineId) ?? null,
    [eventLines, selectedContext.eventLineId],
  );
  const currentClientIntelSnapshot = useMemo(() => {
    if (clientIntel.error || clientIntel.snapshot?.status === "missing") {
      return null;
    }
    return clientIntel.snapshot;
  }, [clientIntel.error, clientIntel.snapshot]);
  const consultRequestContext = useMemo(
    () => buildConsultRequestContext({
      currentFocus: focus,
      selectedContext,
      tasks,
      workspaceLite: currentClientIntelSnapshot,
      eventLine: selectedEventLine,
    }),
    [currentClientIntelSnapshot, focus, selectedContext, selectedEventLine, tasks],
  );
  const activeConsultContext = threadContextSnapshot ?? consultRequestContext;
  const activeEventLine = useMemo(
    () => eventLines.find((item) => item.id === activeConsultContext.eventLineId) ?? null,
    [activeConsultContext.eventLineId, eventLines],
  );
  const threadContextDrifted = useMemo(
    () =>
      threadContextSnapshot
        ? hasConsultThreadContextDrift(threadContextSnapshot, consultRequestContext)
        : false,
    [consultRequestContext, threadContextSnapshot],
  );
  const activeContextLabel = useMemo(() => {
    const parts = [
      activeConsultContext.clientName,
      activeConsultContext.eventLineName,
      activeConsultContext.taskTitle,
    ].filter(Boolean);
    if (parts.length > 0) {
      return parts.join(" / ");
    }
    return selectedContext?.label ?? "当前对话";
  }, [
    activeConsultContext.clientName,
    activeConsultContext.eventLineName,
    activeConsultContext.taskTitle,
    selectedContext?.label,
  ]);
  const displayContextLabel = useMemo(() => {
    if (activeContextLabel === "全部") {
      return "当前对话";
    }
    if (activeContextLabel === "全部上下文") {
      return "当前锁定上下文";
    }
    return activeContextLabel;
  }, [activeContextLabel]);
  const backendContextLimitationReason = useMemo(() => {
    if (backendCapabilityError) {
      return `服务状态检查未完成：${backendCapabilityError}`;
    }
    if (!backendCapabilities) {
      return "服务状态检查未完成，当前按普通问答继续。";
    }
    if (!backendCapabilities.consultationChat) {
      return "当前服务暂不支持咨询会话。";
    }
    if (backendCapabilities.consultationPayloadVersion !== "v2") {
      return "当前服务使用旧接口，手机端按普通问答继续。";
    }
    if (!backendCapabilities.clientWorkspace) {
      return "当前服务暂未提供客户工作台接口。";
    }
    return null;
  }, [backendCapabilities, backendCapabilityError]);
  const handleTransferSelectedEventLine = useCallback(async (clientId: string) => {
    if (!activeEventLine) {
      return;
    }
    const targetClient = clients.find((item) => item.id === clientId);
    if (!targetClient) {
      Alert.alert("迁移失败", "目标客户不存在，请刷新后重试。");
      return;
    }
    setTransferringEventLineId(activeEventLine.id);
    try {
      await transferEventLineToClient(activeEventLine.id, clientId);
      Alert.alert("已更新归属", `已把「${activeEventLine.name}」转到客户「${targetClient.name}」下。`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "请检查网络连接后重试。";
      Alert.alert("迁移失败", message);
    } finally {
      setTransferringEventLineId(null);
    }
  }, [activeEventLine, clients]);

  useSpeechRecognitionEvent("start", () => {
    if (!voiceInputOwnerRef.current) {
      return;
    }
    setIsVoiceInputActive(true);
  });

  useSpeechRecognitionEvent("end", () => {
    if (!voiceInputOwnerRef.current) {
      return;
    }
    voiceInputOwnerRef.current = false;
    setIsVoiceInputActive(false);
  });

  useSpeechRecognitionEvent("result", (event) => {
    if (!voiceInputOwnerRef.current) {
      return;
    }
    const transcript = getEventTranscript(event);
    if (transcript) {
      setInputText(transcript);
    }
  });

  useSpeechRecognitionEvent("error", (event) => {
    if (!voiceInputOwnerRef.current) {
      return;
    }
    voiceInputOwnerRef.current = false;
    setIsVoiceInputActive(false);
    Alert.alert("语音输入失败", buildSpeechRecognitionErrorMessage(event, "请稍后再试。"));
  });

  useEffect(() => {
    return () => {
      if (!voiceInputOwnerRef.current) {
        return;
      }
      voiceInputOwnerRef.current = false;
      try {
        ExpoSpeechRecognitionModule.stop();
      } catch {
        // Best-effort cleanup when the screen unmounts during native recognition.
      }
    };
  }, []);

  // Track keyboard visibility to adjust input bar padding
  useEffect(() => {
    const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide";
    const showSub = Keyboard.addListener(showEvent, () => setKeyboardVisible(true));
    const hideSub = Keyboard.addListener(hideEvent, () => setKeyboardVisible(false));
    return () => { showSub.remove(); hideSub.remove(); };
  }, []);

  useAndroidBackToTasks(
    useCallback(() => {
      if (showContextPicker) {
        setShowContextPicker(false);
        return true;
      }
      if (showEventLineDrawer) {
        setShowEventLineDrawer(false);
        return true;
      }
      if (workspaceClientId) {
        setWorkspaceClientId(null);
        return true;
      }
      return false;
    }, [showContextPicker, showEventLineDrawer, workspaceClientId]),
  );

  useEffect(() => {
    if (!selectedContext && contextOptions.length === 0) {
      return;
    }
    if (messages.length > 0) {
      return;
    }
    // 问候语按需移除：初始对话留空，用户发问后再产生消息。
    setMessages([]);
  }, [contextOptions, messages.length, selectedContext]);

  useEffect(() => {
    setCurrentFocusBoundaryState(clientIntel.snapshot?.boundaryState ?? "none");
  }, [clientIntel.snapshot?.boundaryState, setCurrentFocusBoundaryState]);

  useEffect(() => {
    let cancelled = false;
    cache.loadWithCache(
      cache.KEYS.consultKnowledgeRequests,
      fetchConsultationKnowledgeRequests,
      (requests) => { if (!cancelled) setKnowledgeRequests(requests); },
    ).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchMobileCapabilities()
      .then((capabilities) => {
        if (cancelled) {
          return;
        }
        setBackendCapabilities(capabilities);
        setBackendCapabilityError(null);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setBackendCapabilities(null);
        setBackendCapabilityError(error instanceof Error ? error.message : "能力探测失败");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshKnowledgeRequests = useCallback(() => {
    fetchConsultationKnowledgeRequests()
      .then((requests) => setKnowledgeRequests(requests))
      .catch(() => {});
  }, []);

  // Handle context change
  const handleContextChange = useCallback((option: ConsultContextOption) => {
    if (option.scope === "all") {
      clearStoredCurrentFocus();
    } else if (option.scope === "client" && option.clientId) {
      setManualClientFocus(option.clientId);
    } else if (option.scope === "event_line" && option.clientId && option.eventLineId) {
      setManualClientEventLineFocus(option.clientId, option.eventLineId);
    }
    setShowContextPicker(false);
    setThreadContextSnapshot(null);
    // 切换客户/上下文时清空对话，不再注入问候语。
    setMessages([]);
  }, [clearStoredCurrentFocus, setManualClientEventLineFocus, setManualClientFocus]);

  const [aiLoading, setAiLoading] = useState(false);

  // Send message with real AI
  const handleSend = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || aiLoading) return;

      const userMsg: ChatMessage = {
        id: nextMessageId(),
        role: "user",
        text: trimmed,
      };
      const placeholderId = nextMessageId();
      const placeholderMsg: ChatMessage = {
        id: placeholderId,
        role: "ai",
        text: AI_THINKING_PLACEHOLDER,
      };

      setMessages((prev) => [...prev, userMsg, placeholderMsg]);
      setInputText("");
      setAiLoading(true);

      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);

      const prepareThreadContext = async () => {
        if (threadContextSnapshot) {
          return threadContextSnapshot;
        }
        let nextRequestContext = consultRequestContext;
        if (selectedContext.clientId && !consultRequestContext.workspaceContext) {
          const refreshedSnapshot = await clientIntel.refresh();
          if (refreshedSnapshot) {
            nextRequestContext = buildConsultRequestContext({
              currentFocus: focus,
              selectedContext,
              tasks,
              workspaceLite: refreshedSnapshot,
              eventLine: selectedEventLine,
            });
          }
        }
        const nextFrozenContext = freezeConsultThreadContext(nextRequestContext);
        setThreadContextSnapshot(nextFrozenContext);
        return nextFrozenContext;
      };

      void prepareThreadContext()
        .then(async (resolvedContext) => {
          const response = await sendConsultationChat({
            message: trimmed,
            clientId: resolvedContext.clientId,
            clientName: resolvedContext.clientName,
            eventLineId: resolvedContext.eventLineId,
            eventLineName: resolvedContext.eventLineName,
            taskId: resolvedContext.taskId,
            taskTitle: resolvedContext.taskTitle,
            taskContext: resolvedContext.taskContext ?? null,
            workspaceContext: resolvedContext.workspaceContext ?? null,
            eventLineContext: resolvedContext.eventLineContext ?? null,
            taskBoardContext: resolvedContext.taskBoardContext ?? null,
            understandingContext: resolvedContext.understandingContext ?? null,
            sourceLabels: resolvedContext.sourceLabels,
            missingEventLineHint: resolvedContext.missingEventLineHint ?? null,
          });
          return { response, resolvedContext };
        })
        .then(({ response, resolvedContext }) => {
          const forcedLimitedReason =
            backendContextLimitationReason ??
            (resolvedContext.clientId && !resolvedContext.workspaceContext
              ? "客户工作台未成功加载，本次回答只按客户名 / 任务板等薄上下文处理。"
              : null);
          const normalizedResponse = normalizeConsultationResponseForMobile(response, {
            hasClientName: Boolean(resolvedContext.clientName),
            hasTaskBoardContext: Boolean(resolvedContext.taskBoardContext || resolvedContext.taskContext),
            hasThreadSnapshot: Boolean(resolvedContext.snapshotHash),
            hasWorkspaceContext: Boolean(resolvedContext.workspaceContext),
            forceLimitedContext: Boolean(forcedLimitedReason),
            reason: forcedLimitedReason,
          });
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === placeholderId
                ? {
                    ...msg,
                    text: normalizedResponse.reply,
                    answerMode: normalizedResponse.answerMode ?? null,
                    contextQuality: normalizedResponse.contextQuality ?? null,
                    evidence: normalizedResponse.evidence ?? [],
                    missingContext: normalizedResponse.missingContext ?? [],
                  }
                : msg,
            ),
          );
        })
        .catch((err: unknown) => {
          const errorText =
            err instanceof Error ? err.message : "AI 回复失败，请稍后重试";
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === placeholderId
                ? { ...msg, text: `[错误] ${errorText}` }
                : msg,
            ),
          );
        })
        .finally(() => {
          setAiLoading(false);
          setTimeout(() => {
            flatListRef.current?.scrollToEnd({ animated: true });
          }, 100);
        });
    },
    [
      aiLoading,
      backendContextLimitationReason,
      clientIntel,
      consultRequestContext,
      focus,
      selectedContext,
      selectedEventLine,
      tasks,
      threadContextSnapshot,
    ],
  );

  const handleQuickQuestion = useCallback(
    (question: string) => {
      handleSend(question);
    },
    [handleSend],
  );

  const handleSubmit = useCallback(() => {
    handleSend(inputText);
  }, [handleSend, inputText]);

  const handleRefreshThreadContext = useCallback(() => {
    const nextSnapshot = refreshConsultThreadContext(
      threadContextSnapshot,
      consultRequestContext,
    );
    setThreadContextSnapshot(nextSnapshot);
    Alert.alert(
      "已刷新上下文",
      nextSnapshot.taskTitle
        ? `当前线程已切到任务「${nextSnapshot.taskTitle}」。`
        : nextSnapshot.eventLineName
          ? `当前线程已切到「${nextSnapshot.clientName ?? "当前客户"} / ${nextSnapshot.eventLineName}」。`
          : nextSnapshot.clientName
            ? `当前线程已切到客户「${nextSnapshot.clientName}」。`
            : "当前线程已切回全部上下文。",
    );
  }, [consultRequestContext, threadContextSnapshot]);

  const findPromptForAnswer = useCallback(
    (messageId: string) => {
      const targetIndex = messages.findIndex((item) => item.id === messageId);
      if (targetIndex <= 0) return "";
      for (let index = targetIndex - 1; index >= 0; index -= 1) {
        const candidate = messages[index];
        if (candidate?.role === "user") {
          return candidate.text.trim();
        }
      }
      return "";
    },
    [messages],
  );

  const handleKnowledgeAction = useCallback(
    async (message: ChatMessage, target: "vector_memory" | "document_archive") => {
      if (message.role !== "ai") return;
      const actionKey = `${message.id}:${target}`;
      setPendingKnowledgeActionKey(actionKey);
      try {
        await enqueueConsultationKnowledgeRequest({
          target,
          question: findPromptForAnswer(message.id),
          answer: message.text,
          clientId: activeConsultContext.clientId,
          clientName: activeConsultContext.clientName,
          eventLineId: activeConsultContext.eventLineId,
        });
        Alert.alert(
          "已发送到云端",
          target === "vector_memory"
            ? "这条答案已登记到向量沉淀队列，桌面端会继续做本地知识入库。"
            : "这条答案已登记到文档沉淀队列，桌面端会继续生成正式文档。",
        );
        refreshKnowledgeRequests();
      } catch (error) {
        const messageText = error instanceof Error ? error.message : "沉淀请求发送失败";
        Alert.alert("发送失败", messageText);
      } finally {
        setPendingKnowledgeActionKey((current) => (current === actionKey ? null : current));
      }
    },
    [
      activeConsultContext.clientId,
      activeConsultContext.clientName,
      activeConsultContext.eventLineId,
      findPromptForAnswer,
      refreshKnowledgeRequests,
    ],
  );

  const handleRetryKnowledgeRequest = useCallback(async (request: ConsultationKnowledgeRequestRecord) => {
    if (!request.target || !request.answer) {
      Alert.alert("无法重试", "这条沉淀请求缺少必要内容。");
      return;
    }
    const actionKey = `retry:${request.id}`;
    setPendingKnowledgeActionKey(actionKey);
    try {
      await enqueueConsultationKnowledgeRequest({
        target: request.target,
        question: request.question ?? "",
        answer: request.answer,
        clientId: request.clientId,
        clientName: request.clientName,
        eventLineId: request.eventLineId,
      });
      Alert.alert("已重新加入队列", "失败项已重新提交，桌面端会继续处理。");
      refreshKnowledgeRequests();
    } catch (error) {
      Alert.alert("重试失败", error instanceof Error ? error.message : "请稍后再试。");
    } finally {
      setPendingKnowledgeActionKey((current) => (current === actionKey ? null : current));
    }
  }, [refreshKnowledgeRequests]);

  const handleCopyAnswer = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) {
      return;
    }
    try {
      await Clipboard.setStringAsync(trimmed);
      Alert.alert("已复制", "内容已复制到剪贴板。");
      return;
    } catch {}
    setInputText((current) => (current.trim() ? `${current.trim()}\n${trimmed}` : trimmed));
    Alert.alert("已放入输入框", "当前环境未提供系统剪贴板，已把内容放到输入框中。");
  }, []);

  // P1-A: AI 答案 → 任务 一键转化
  // 把 AI 回答拆成 SmartTaskDraft，跨 tab 暂存到 module-level pending draft，
  // 跳到 tasks tab 自动唤起 CreateTask sheet。CreateTask 已支持 draft.title/description/clientId 预填。
  const handleAddAsTask = useCallback((text: string) => {
    const trimmed = (text || "").trim();
    if (!trimmed) return;
    // 标题用首句（句号/换行/问号 截断），最多 30 字
    const firstSentenceMatch = trimmed.match(/^[^。\n！？!?]{1,80}/);
    const rawTitle = (firstSentenceMatch ? firstSentenceMatch[0] : trimmed).trim();
    const title = rawTitle.length > 30 ? `${rawTitle.slice(0, 30)}…` : rawTitle;
    const draft: SmartTaskDraft = {
      title,
      description: trimmed,
      clientId: focus.clientId || null,
      clientName: focus.clientName || null,
      eventLineId: focus.eventLineId || null,
      eventLineName: focus.eventLineName || null,
    };
    setPendingConsultDraft(draft);
    router.push(`/(tabs)/tasks?modal=create&trigger=${Date.now()}&from=consult`);
  }, [focus.clientId, focus.clientName, focus.eventLineId, focus.eventLineName, router]);

  const handleToggleVoiceInput = useCallback(async () => {
    if (isVoiceInputActive) {
      voiceInputOwnerRef.current = false;
      setIsVoiceInputActive(false);
      try {
        ExpoSpeechRecognitionModule.stop();
      } catch {
        // Native recognizer may already have ended.
      }
      return;
    }
    try {
      const audioPermission = await AudioModule.requestRecordingPermissionsAsync();
      if (!getPermissionGranted(audioPermission)) {
        Alert.alert("语音输入不可用", "请先允许麦克风权限。");
        return;
      }
      const permission = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
      if (!getPermissionGranted(permission)) {
        Alert.alert("语音输入不可用", "请先允许语音识别权限。");
        return;
      }
      voiceInputOwnerRef.current = true;
      ExpoSpeechRecognitionModule.start({
        lang: "zh-CN",
        interimResults: true,
        continuous: false,
        addsPunctuation: true,
        contextualStrings: [
          activeConsultContext.clientName,
          activeConsultContext.eventLineName,
          activeConsultContext.taskTitle,
        ].filter((item): item is string => Boolean(item)),
      });
      setIsVoiceInputActive(true);
    } catch (error) {
      voiceInputOwnerRef.current = false;
      setIsVoiceInputActive(false);
      Alert.alert("语音输入失败", buildSpeechRecognitionErrorMessage(error, "请稍后再试。"));
    }
  }, [
    activeConsultContext.clientName,
    activeConsultContext.eventLineName,
    activeConsultContext.taskTitle,
    isVoiceInputActive,
  ]);

  const handleOpenTaskContext = useCallback((taskId: string) => {
    const matchedTask = tasks.find((item) => item.id === taskId);
    if (!matchedTask) {
      Alert.alert("任务不存在", "当前列表里没有找到这条任务，可能已经被删除或尚未同步。");
      return;
    }
    setCurrentFocusBrowseFromTask(matchedTask);
    setShowEventLineDrawer(false);
    setWorkspaceClientId(null);
    if (!threadContextSnapshot) {
      setMessages([]);
    }
  }, [setCurrentFocusBrowseFromTask, tasks, threadContextSnapshot]);

  // ─── Render ─────────────────────────────────────

  if (!isHydrated) {
    return (
      <SafeAreaView style={[styles.centered, { paddingTop: chrome.screenTopPadding, paddingBottom: chrome.screenBottomPadding }]} edges={["left", "right"]}>
        <ActivityIndicator size="large" color={colors.brand} />
        <Text style={styles.loadingText}>加载中...</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={["left", "right"]}>
      <KeyboardAvoidingView
        style={styles.flex1}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        keyboardVerticalOffset={Platform.OS === "ios" ? 0 : 0}
      >
        {/* Header */}
        <View
          style={[styles.header, { paddingTop: chrome.headerTopPadding }]}
          onLayout={(event) => setHeaderHeight(event.nativeEvent.layout.height)}
        >
          {/* 标题 + 客户选择器同一行；其余上下文状态/问候已按需精简 */}
          <View style={styles.headerTopRow}>
            <Text style={styles.headerTitle}>咨询助手</Text>
            <View style={styles.contextRow}>
              <Text style={styles.contextLabel}>当前上下文：</Text>
              <TouchableOpacity
                style={styles.contextChip}
                onPress={() => setShowContextPicker((current) => !current)}
                activeOpacity={0.7}
              >
                <Text style={styles.contextChipText} numberOfLines={1}>
                  {displayContextLabel}
                </Text>
                <ChevronDown size={12} color={colors.brand} />
              </TouchableOpacity>
            </View>
          </View>
        </View>

        {/* Chat area */}
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(item) => item.id}
          style={styles.chatList}
          contentContainerStyle={styles.chatContent}
          renderItem={({ item }) => (
            <View
              style={[
                styles.messageBubble,
                item.role === "ai" ? styles.aiBubble : styles.userBubble,
              ]}
            >
              {item.text === AI_THINKING_PLACEHOLDER ? (
                <View style={styles.thinkingRow}>
                  <ActivityIndicator size="small" color={colors.brand} />
                  <Text style={[styles.messageText, { marginLeft: 8, color: colors.textSecondary }]}>
                    {AI_THINKING_PLACEHOLDER}
                  </Text>
                </View>
              ) : item.role === "user" ? (
                <Text style={[styles.messageText, styles.userMessageText]}>
                  {item.text}
                </Text>
              ) : (
                <SimpleMarkdown text={item.text} baseStyle={styles.messageText} />
              )}
              {/* 已按需精简：移除 answerMode「已结合上下文」徽章 / 「出处·N」证据块 / 「缺失的上下文」块，只留回答正文与操作图标 */}
              {item.role === "ai" && item.text !== AI_THINKING_PLACEHOLDER && !item.text.startsWith("[错误]") && (
                <View style={styles.actionIcons}>
                  <TouchableOpacity
                    style={styles.actionIcon}
                    onPress={() => {
                      void handleCopyAnswer(item.text);
                    }}
                  >
                    <Copy size={14} color={colors.textSecondary} />
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.actionIcon}
                    onPress={() => {
                      void handleKnowledgeAction(item, "vector_memory");
                    }}
                    disabled={pendingKnowledgeActionKey === `${item.id}:vector_memory`}
                  >
                    {pendingKnowledgeActionKey === `${item.id}:vector_memory` ? (
                      <ActivityIndicator size="small" color={colors.brand} />
                    ) : (
                      <Layers size={14} color={colors.textSecondary} />
                    )}
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.actionIcon}
                    onPress={() => {
                      void handleKnowledgeAction(item, "document_archive");
                    }}
                    disabled={pendingKnowledgeActionKey === `${item.id}:document_archive`}
                  >
                    {pendingKnowledgeActionKey === `${item.id}:document_archive` ? (
                      <ActivityIndicator size="small" color={colors.brand} />
                    ) : (
                      <FileText size={14} color={colors.textSecondary} />
                    )}
                  </TouchableOpacity>
                  {/* P1-A: AI 答案 → 新建任务 */}
                  <TouchableOpacity
                    style={styles.actionIcon}
                    onPress={() => handleAddAsTask(item.text)}
                  >
                    <ListPlus size={14} color={colors.textSecondary} />
                  </TouchableOpacity>
                </View>
              )}
            </View>
          )}
          ListFooterComponent={
            messages.length <= 1 ? (
              <View style={styles.quickQuestions}>
                {quickQuestions.map((q) => (
                  <TouchableOpacity
                    key={q}
                    style={styles.quickChip}
                    onPress={() => handleQuickQuestion(q)}
                    activeOpacity={0.7}
                  >
                    <Text style={styles.quickChipText}>{q}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            ) : null
          }
          onContentSizeChange={() => {
            flatListRef.current?.scrollToEnd({ animated: true });
          }}
        />

        {/* Knowledge request status panel */}
        {knowledgeRequests.length > 0 && (
          <TouchableOpacity
            style={styles.knowledgeStatusBar}
            onPress={() => setShowKnowledgePanel((v) => !v)}
            activeOpacity={0.7}
          >
            <Layers size={14} color={colors.brand} />
            <Text style={styles.knowledgeStatusText}>
              知识沉淀 {knowledgeRequests.filter((r) => r.status === "pending" || r.status === "processing").length} 处理中
              {" / "}
              {knowledgeRequests.filter((r) => r.status === "completed").length} 已完成
            </Text>
            <ChevronDown size={12} color={colors.textSecondary} style={showKnowledgePanel ? { transform: [{ rotate: "180deg" }] } : undefined} />
          </TouchableOpacity>
        )}
        {showKnowledgePanel && knowledgeRequests.length > 0 && (
          <View style={styles.knowledgePanel}>
            {knowledgeRequests.slice(0, 8).map((req) => (
              <View key={req.id} style={styles.knowledgeRow}>
                {req.status === "completed" ? (
                  <CheckCircle2 size={12} color="#10B981" />
                ) : req.status === "failed" ? (
                  <AlertCircle size={12} color={colors.error} />
                ) : (
                  <Clock size={12} color={colors.brand} />
                )}
                <Text style={styles.knowledgeTarget}>
                  {req.target === "vector_memory" ? "向量" : "文档"}
                </Text>
                <Text style={styles.knowledgeQuestion} numberOfLines={1}>
                  {req.question || req.answer?.slice(0, 30) || "—"}
                </Text>
                <Text style={styles.knowledgeStatusLabel}>
                  {req.status === "pending" ? "待处理" : req.status === "processing" ? "处理中" : req.status === "completed" ? "已完成" : "失败"}
                </Text>
                {req.status === "failed" ? (
                  <TouchableOpacity
                    style={styles.knowledgeRetryButton}
                    onPress={() => {
                      void handleRetryKnowledgeRequest(req);
                    }}
                    disabled={pendingKnowledgeActionKey === `retry:${req.id}`}
                  >
                    {pendingKnowledgeActionKey === `retry:${req.id}` ? (
                      <ActivityIndicator size="small" color={colors.brand} />
                    ) : (
                      <Text style={styles.knowledgeRetryText}>重试</Text>
                    )}
                  </TouchableOpacity>
                ) : null}
              </View>
            ))}
          </View>
        )}

        {/* Input bar */}
        <View style={[styles.inputBar, { paddingBottom: keyboardVisible ? spacing.sm : chrome.tabBarHeight + spacing.xs }]}>
          <TouchableOpacity
            style={[styles.micButton, isVoiceInputActive && styles.micButtonActive]}
            onPress={() => {
              void handleToggleVoiceInput();
            }}
          >
            <Mic size={18} color={isVoiceInputActive ? colors.textOnBrand : colors.textSecondary} />
          </TouchableOpacity>
          <TextInput
            style={styles.textInput}
            placeholder={isVoiceInputActive ? "正在听写..." : "输入问题，或点麦克风转成文字"}
            placeholderTextColor={colors.textTertiary}
            value={inputText}
            onChangeText={setInputText}
            onSubmitEditing={handleSubmit}
            returnKeyType="send"
            multiline={false}
          />
          <TouchableOpacity
            style={[
              styles.sendButton,
              (!inputText.trim() || aiLoading) && styles.sendButtonDisabled,
            ]}
            onPress={handleSubmit}
            disabled={!inputText.trim() || aiLoading}
            activeOpacity={0.7}
          >
            {aiLoading ? (
              <ActivityIndicator size="small" color={colors.textOnBrand} />
            ) : (
              <Send size={20} color={colors.textOnBrand} />
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>

      {showContextPicker ? (
        <View style={styles.contextPickerOverlay}>
          <TouchableOpacity
            style={styles.contextPickerBackdrop}
            activeOpacity={1}
            onPress={() => setShowContextPicker(false)}
          />
          <View
            style={[
              styles.contextPickerCard,
              { top: Math.max(headerHeight - spacing.xs, spacing.xxxl) },
            ]}
          >
            <Text style={styles.contextPickerTitle}>选择上下文</Text>
            <ScrollView
              style={styles.contextPickerScroll}
              contentContainerStyle={styles.contextPickerList}
              showsVerticalScrollIndicator
              keyboardShouldPersistTaps="handled"
            >
              {contextOptions.map((item) => (
                <TouchableOpacity
                  key={item.id}
                  style={[
                    styles.contextOptionRow,
                    selectedContext?.id === item.id &&
                      styles.contextOptionSelected,
                  ]}
                  onPress={() => handleContextChange(item)}
                  activeOpacity={0.7}
                >
                  <View style={styles.contextOptionCopy}>
                    <Text
                      style={[
                        styles.contextOptionText,
                        selectedContext?.id === item.id &&
                          styles.contextOptionTextSelected,
                      ]}
                    >
                      {item.scope === "all" ? "自由提问" : item.label}
                    </Text>
                    <Text style={styles.contextOptionMeta}>
                      {item.scope === "event_line"
                        ? `${item.clientName || "客户"} · ${item.eventLineName || "事件线"}`
                        : item.clientName || "当前锁定上下文"}
                    </Text>
                  </View>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>
        </View>
      ) : null}
      <EventLineDrawer
        visible={showEventLineDrawer}
        eventLine={activeEventLine}
        tasks={tasks}
        clients={clients}
        meetingHighlights={clientIntel.snapshot?.latestMeetings ?? []}
        onClose={() => setShowEventLineDrawer(false)}
        onOpenWorkspace={() => {
          if (activeConsultContext.clientId) {
            setWorkspaceClientId(activeConsultContext.clientId);
          }
        }}
        onTransferToClient={handleTransferSelectedEventLine}
        isTransferringClient={transferringEventLineId === activeEventLine?.id}
        onTaskPress={(task) => handleOpenTaskContext(task.id)}
      />
      <WorkspaceLiteSheet
        visible={Boolean(workspaceClientId)}
        clientId={workspaceClientId}
        clientName={activeConsultContext.clientName}
        onClose={() => setWorkspaceClientId(null)}
        onTaskPress={handleOpenTaskContext}
      />
    </SafeAreaView>
  );
}

// ─── Styles ─────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  flex1: {
    flex: 1,
  },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
  },
  loadingText: {
    marginTop: spacing.md,
    color: colors.textSecondary,
    fontSize: fontSize.md,
  },
  errorText: {
    color: colors.error,
    fontSize: fontSize.md,
  },

  // Header —— 与页面背景一致，无白底
  header: {
    backgroundColor: palette.paperRice,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
  },
  headerTopRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  headerTitle: {
    ...typography.titleCard, // 17/600/24，统一跨屏字号
    color: palette.inkBlack,
  },
  contextRow: {
    flexDirection: "row",
    alignItems: "center",
    flexShrink: 1,
  },
  contextLabel: {
    ...typography.caption,
    color: palette.textTertiary,
  },
  contextChip: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(31,42,55,0.06)",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    maxWidth: 240,
  },
  contextChipText: {
    ...typography.caption,
    color: palette.inkBlack,
    fontWeight: "500",
    flexShrink: 1,
  },
  contextHint: {
    marginTop: spacing.xs,
    ...typography.label,
    color: palette.textTertiary,
  },
  contextActionRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  // 跳转按钮 —— 描边 + 浓墨字，不再 surfaceSecondary 实心
  contextActionButton: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  contextActionButtonText: {
    ...typography.label,
    color: palette.inkBlack,
    fontWeight: "600",
  },
  threadSnapshotRow: {
    marginTop: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  threadSnapshotText: {
    flex: 1,
    ...typography.label,
    color: palette.textSecondary,
    fontWeight: "500",
  },
  // drift 警示用朱砂（"上下文失同步" 语义）
  threadSnapshotTextWarning: {
    color: palette.cinnabar,
  },
  threadSnapshotAction: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    borderColor: palette.cinnabarBorder,
  },
  threadSnapshotActionText: {
    ...typography.label,
    color: palette.cinnabar,
    fontWeight: "600",
  },
  chevron: {
    fontSize: 8,
    color: palette.textTertiary,
    marginLeft: spacing.xs,
  },

  // Chat
  chatList: { flex: 1 },
  chatContent: {
    padding: spacing.lg,
    paddingBottom: spacing.xl,
  },
  // 豆包 / GPT 风：对话直接平铺，不做卡片气泡
  messageBubble: {
    marginBottom: spacing.lg,
  },
  // AI 回答：全宽平铺，无背景 / 无描边 / 无左色条
  aiBubble: {
    alignSelf: "stretch",
  },
  // 用户提问：右侧浅灰气泡（与 AI 区分，但不抢眼）
  userBubble: {
    alignSelf: "flex-end",
    maxWidth: "82%",
    backgroundColor: "rgba(31,42,55,0.06)",
    borderRadius: 16,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  messageText: {
    ...typography.body, // 15/400/22
    color: palette.inkBlack,
  },
  userMessageText: {
    color: palette.inkBlack,
  },
  thinkingRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  // Answer mode / evidence / missing context blocks
  answerModeRow: {
    flexDirection: "row",
    marginTop: spacing.md,
  },
  answerModeBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: borderRadius.full,
    borderWidth: 1,
  },
  answerModeBadgeOk: {
    backgroundColor: "rgba(92,122,92,0.10)",
    borderColor: palette.bambooGreen,
  },
  answerModeBadgeWarn: {
    backgroundColor: "rgba(214,148,0,0.12)",
    borderColor: palette.reedYellow,
  },
  answerModeBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: palette.textSecondary,
  },
  answerModeBadgeTextOk: {
    color: palette.bambooGreen,
  },
  answerModeBadgeTextWarn: {
    color: palette.reedYellow,
  },
  evidenceBlock: {
    marginTop: spacing.md,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: palette.borderSubtle,
    gap: 6,
  },
  evidenceBlockHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    marginBottom: 4,
  },
  evidenceBlockTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: palette.textSecondary,
  },
  evidenceRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 6,
  },
  evidenceTypeText: {
    fontSize: 11,
    fontWeight: "600",
    color: palette.inkBronze,
    minWidth: 60,
  },
  evidenceTitleText: {
    flex: 1,
    fontSize: 12,
    color: palette.inkBlack,
    lineHeight: 18,
  },
  evidenceMoreText: {
    fontSize: 11,
    color: palette.textTertiary,
    fontStyle: "italic",
  },
  missingBlock: {
    marginTop: spacing.sm,
    padding: spacing.sm,
    backgroundColor: "rgba(214,148,0,0.06)",
    borderRadius: borderRadius.sm,
    gap: 4,
  },
  missingBlockTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: palette.reedYellow,
  },
  missingRow: {
    fontSize: 11,
    color: palette.inkBlack,
    lineHeight: 17,
  },

  // Action icons —— 去掉背景方框，仅留单色 icon
  actionIcons: {
    flexDirection: "row",
    marginTop: spacing.md,
    gap: spacing.lg,
  },
  actionIcon: {
    width: 22,
    height: 22,
    alignItems: "center",
    justifyContent: "center",
  },
  actionIconText: {
    fontSize: 14,
  },

  // Quick questions
  quickQuestions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  quickChip: {
    backgroundColor: palette.paperSmoke,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.lg,
    paddingVertical: 10,
  },
  quickChipText: {
    ...typography.body, // 15/400/22
    color: palette.inkBlack,
    fontWeight: "500",
  },

  // Knowledge status bar
  knowledgeStatusBar: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    backgroundColor: palette.paperMoon,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: palette.borderSubtle,
    gap: spacing.sm,
  },
  knowledgeStatusText: {
    flex: 1,
    ...typography.label,
    color: palette.textSecondary,
  },
  knowledgePanel: {
    backgroundColor: palette.paperSmoke,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: palette.borderSubtle,
    maxHeight: 200,
  },
  knowledgeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 4,
  },
  knowledgeTarget: {
    ...typography.label,
    color: palette.textTertiary,
    width: 28,
  },
  knowledgeQuestion: {
    flex: 1,
    ...typography.caption,
    color: palette.inkBlack,
  },
  knowledgeStatusLabel: {
    ...typography.label,
    color: palette.textTertiary,
  },
  // 重试按钮 —— 失败语义用朱砂描边
  knowledgeRetryButton: {
    marginLeft: "auto",
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    borderColor: palette.cinnabarBorder,
  },
  knowledgeRetryText: {
    ...typography.label,
    color: palette.cinnabar,
    fontWeight: "600",
  },

  // Input bar —— 烟灰白 + hairline
  inputBar: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: palette.paperSmoke,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: palette.borderSubtle,
    gap: spacing.sm,
  },
  micButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: palette.paperMoon,
    alignItems: "center",
    justifyContent: "center",
  },
  // 录音激活 —— 朱砂（活跃/危险语义）
  micButtonActive: {
    backgroundColor: palette.cinnabar,
  },
  micIcon: {
    fontSize: 18,
  },
  textInput: {
    flex: 1,
    height: 44,
    backgroundColor: palette.paperMoon,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.md, // 12
    paddingHorizontal: spacing.lg,
    ...typography.body, // 15/400/22
    color: palette.inkBlack,
  },
  sendButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: palette.inkBlack,
    alignItems: "center",
    justifyContent: "center",
  },
  sendButtonDisabled: {
    backgroundColor: palette.inkBlack,
    opacity: 0.3, // 用透明度区别 disabled，避免和 micButton 同色
  },
  sendIcon: {
    fontSize: 20,
    color: palette.paperRice,
    fontWeight: "600",
  },

  // Context picker
  contextPickerOverlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 20,
  },
  contextPickerBackdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(31,42,55,0.24)", // 统一 backdrop
  },
  contextPickerCard: {
    position: "absolute",
    right: spacing.lg,
    width: 272,
    maxHeight: "70%", // 组织/上下文多时卡片不超过 70% 屏高，内部列表可滚动
    backgroundColor: palette.paperSmoke,
    borderRadius: borderRadius.lg, // 14
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
  },
  contextPickerScroll: {
    flexGrow: 0,
    flexShrink: 1, // RN 默认 flexShrink=0；不设的话 ScrollView 会撑破卡片 maxHeight 而非滚动
  },
  contextPickerTitle: {
    ...typography.label,
    color: palette.textTertiary,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  contextPickerList: {
    gap: spacing.xs,
  },
  contextOptionRow: {
    borderRadius: borderRadius.sm, // 8
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  contextOptionSelected: {
    backgroundColor: "rgba(31,42,55,0.06)",
  },
  contextOptionCopy: {
    gap: 2,
  },
  contextOptionText: {
    ...typography.body,
    color: palette.inkBlack,
    fontWeight: "500",
  },
  contextOptionTextSelected: {
    color: palette.inkBlack,
    fontWeight: "600",
  },
  contextOptionMeta: {
    ...typography.label,
    color: palette.textTertiary,
  },
});

export function ErrorBoundary(props: ErrorBoundaryProps) {
  return (
    <RouteErrorFallback
      {...props}
      label="consult"
      title="咨询页暂时打不开"
      hint="刚才这个页面遇到了异常，你的对话记录没有丢失。点下方按钮重试即可。"
    />
  );
}
