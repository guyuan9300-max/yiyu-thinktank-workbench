import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Alert, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { ExpoSpeechRecognitionModule, useSpeechRecognitionEvent } from "expo-speech-recognition";
import { AudioModule } from "expo-audio";
import { useAppChromeInsets } from "../lib/app-chrome";
import { colors, fontSize, shadow, palette, typography, iconStroke } from "../lib/theme";
import { X, Mic, Sparkles, Briefcase, ListTodo, Calendar, Tag, User, ChevronRight, CheckCircle2, Plus, Check } from "lucide-react-native";
import { createEventLine } from "../lib/create-task-service";
import { useAuth } from "../lib/auth-context";
import {
  buildProjectOptions,
  deriveProjectLabel,
  filterEventLinesForSelection,
  findAutoMatchedClient,
  findAutoMatchedEventLine,
  getProjectKey,
  normalizeSearchText,
  shouldApplyAutoAssociation,
  type AssociationSource,
  type ProjectOption,
} from "../lib/create-task-association";
import {
  invalidateTaskCreationResources,
  loadEmployeeDirectory,
  loadTaskCreationResources,
  type OrgMember,
} from "../lib/create-task-resources";
import {
  createTaskLocalFirst,
  updateTaskLocalFirst,
} from "../lib/task-repository";
import { tagLikeToName, type ClientSummaryRecord, type EventLineRecord, type SmartTaskDraft, type TaskRecord } from "../lib/types";
import DateTimePickerSheet from "./DateTimePickerSheet";
import { buildCreateTaskDueDate } from "../lib/create-task-due-date-core";
import { buildScheduleFromStartEnd } from "../lib/calendar-repository-core";
import { getTaskDeadlineDateKey, getTaskScheduleDateTime, getTaskScheduleEndDateTime } from "../lib/task-time";
import {
  buildSpeechRecognitionErrorMessage,
  getEventTranscript,
  getPermissionGranted,
} from "../lib/local-speech-recognition-core";
import { buildLocalSmartTaskDraftFromTranscript } from "../lib/recording-session-core";
import { parseLocalTaskInput } from "../lib/local-task-parser";

function getTodayDateKey(): string {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
}

interface Props {
  onClose: () => void;
  onCreated: () => void;
  preset?: { dueDate?: string; dueTime?: string };
  task?: TaskRecord | null;
  draft?: SmartTaskDraft | null;
}

export default function CreateTask({ onClose, onCreated, preset, task, draft }: Props) {
  const chrome = useAppChromeInsets();
  const { user } = useAuth();
  // 用户所属组织名（设置→搭建中心建组织后，工作台会生成一个同名客户代表该组织）
  const ownOrgName = user?.organizationName?.trim() || null;
  const activeDraft = !task ? draft ?? null : null;
  const taskSchedule = task ? getTaskScheduleDateTime(task) : null;
  const taskScheduleEnd = task ? getTaskScheduleEndDateTime(task) : null;
  const taskDateKey = taskSchedule?.dateKey ?? (task ? getTaskDeadlineDateKey(task) : null);
  const [title, setTitle] = useState(task?.title ?? activeDraft?.title ?? "");
  const [description, setDescription] = useState(task?.description ?? activeDraft?.description ?? "");
  const [actionType, setActionType] = useState<string>(
    tagLikeToName(task?.tags?.[0]) ?? activeDraft?.tags?.[0] ?? "材料/交付",
  );
  const [allEventLines, setAllEventLines] = useState<EventLineRecord[]>([]);
  const [allClients, setAllClients] = useState<ClientSummaryRecord[]>([]);
  const [selectedEventLine, setSelectedEventLine] = useState<EventLineRecord | null>(null);
  const [selectedProjectKey, setSelectedProjectKey] = useState<string | null>(null);
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [selectedClientName, setSelectedClientName] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [customDate, setCustomDate] = useState<string | null>(taskDateKey ?? activeDraft?.dueDate ?? null);
  const [customTime, setCustomTime] = useState<string | null>(taskSchedule?.timeLabel ?? activeDraft?.dueTime ?? null);
  const [customReminder, setCustomReminder] = useState<number | null>(task?.reminderMinutesBefore ?? null);
  const [dateCleared, setDateCleared] = useState(false);
  const [customEndDate, setCustomEndDate] = useState<string | null>(taskScheduleEnd?.dateKey ?? null);
  const [customEndTime, setCustomEndTime] = useState<string | null>(taskScheduleEnd?.timeLabel ?? null);
  const [showClientPicker, setShowClientPicker] = useState(false);
  const [showEventLinePicker, setShowEventLinePicker] = useState(false);
  const [isCreatingEventLine, setIsCreatingEventLine] = useState(false);
  const [newEventLineName, setNewEventLineName] = useState("");
  const [creatingEventLineLoading, setCreatingEventLineLoading] = useState(false);
  const [defaultListId, setDefaultListId] = useState<string | null>(null);
  const [durationMinutes, setDurationMinutes] = useState<number | null>(task?.durationMinutes ?? activeDraft?.durationMinutes ?? null);
  const [associationSource, setAssociationSource] = useState<AssociationSource>("default");
  const [lockedAssociationTitleKey, setLockedAssociationTitleKey] = useState<string | null>(null);
  const [isVoiceInputActive, setIsVoiceInputActive] = useState(false);
  // 本地识别(对标滴答):标题里说/打"明天下午3点…"即时抽出日期时间,不走云端。
  const [detectedSchedule, setDetectedSchedule] = useState<{ dueDate: string | null; dueTime: string | null; title: string } | null>(null);
  const voiceInputOwnerRef = useRef(false);
  const voiceStartInFlightRef = useRef(false);
  // 负责人/协作人(对齐软件端;数据源 = 组织成员目录)
  const [orgMembers, setOrgMembers] = useState<OrgMember[]>([]);
  const [ownerId, setOwnerId] = useState<string | null>(task?.ownerId ?? null);
  const [collaboratorIds, setCollaboratorIds] = useState<string[]>(
    task?.collaborators?.filter((c) => !c.isOwner).map((c) => c.userId) ?? [],
  );
  const [showAssigneePicker, setShowAssigneePicker] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadEmployeeDirectory()
      .then((members) => { if (!cancelled) setOrgMembers(members); })
      .catch(() => { /* 成员拉取失败不阻塞建任务,降级为默认分派给我 */ });
    return () => { cancelled = true; };
  }, []);

  const resolveDefaultListId = useCallback(async () => {
    const { settings, taskLists } = await loadTaskCreationResources();
    if (settings?.defaultListId) {
      return settings.defaultListId;
    }
    return taskLists.find((item) => item.isDefault)?.id ?? taskLists[0]?.id ?? null;
  }, []);

  const titleSearchKey = useMemo(() => normalizeSearchText(title), [title]);
  // 自动识别归属时同时看标题和描述（用户诉求：按标题+描述识别组织/项目/事件线）。
  const associationSearchKey = useMemo(
    () => normalizeSearchText(`${title} ${description}`),
    [title, description],
  );
  const clientById = useMemo(
    () => new Map(allClients.map((client) => [client.id, client])),
    [allClients],
  );

  const projectOptions = useMemo(() => {
    return buildProjectOptions(allClients, allEventLines);
  }, [allClients, allEventLines]);

  const filteredEventLines = useMemo(() => {
    return filterEventLinesForSelection(allEventLines, selectedClientId, selectedProjectKey);
  }, [allEventLines, selectedClientId, selectedProjectKey]);

  const syncSelectionFromEventLine = useCallback((eventLine: EventLineRecord | null, source: "auto" | "manual" | "default") => {
    if (!eventLine) {
      setSelectedEventLine(null);
      setSelectedProjectKey(null);
      setSelectedClientId(null);
      setSelectedClientName(null);
      if (source === "manual") {
        setLockedAssociationTitleKey(titleSearchKey);
      }
      setAssociationSource(source);
      return;
    }

    setSelectedEventLine(eventLine);
    const client = eventLine.primaryClientId ? clientById.get(eventLine.primaryClientId) : null;
    setSelectedProjectKey(eventLine.primaryClientId ? `client:${eventLine.primaryClientId}` : getProjectKey(eventLine));
    setSelectedClientId(eventLine.primaryClientId ?? null);
    setSelectedClientName(client?.name ?? eventLine.primaryClientName ?? deriveProjectLabel(eventLine));

    if (source === "manual") {
      setLockedAssociationTitleKey(titleSearchKey);
    }
    setAssociationSource(source);
  }, [clientById, titleSearchKey]);

  const autoMatchedEventLine = useMemo(() => {
    return findAutoMatchedEventLine(associationSearchKey, allEventLines);
  }, [allEventLines, associationSearchKey]);
  const autoMatchedClient = useMemo(() => {
    return findAutoMatchedClient(associationSearchKey, allClients);
  }, [allClients, associationSearchKey]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resources = await loadTaskCreationResources();
        if (cancelled) {
          return;
        }
        const resolvedListId =
          resources.settings?.defaultListId ??
          resources.taskLists.find((item) => item.isDefault)?.id ??
          resources.taskLists[0]?.id ??
          null;
        const els = resources.eventLines;
        const clients = resources.clients;
        setAllEventLines(els);
        setAllClients(clients);
        setDefaultListId(resolvedListId);
        if (task?.eventLineId) {
          const matchingEventLine = els.find((item) => item.id === task.eventLineId) ?? null;
          if (matchingEventLine) {
            syncSelectionFromEventLine(matchingEventLine, "manual");
            return;
          }
        }
        if (activeDraft?.eventLineId) {
          const matchingEventLine = els.find((item) => item.id === activeDraft.eventLineId) ?? null;
          if (matchingEventLine) {
            syncSelectionFromEventLine(matchingEventLine, "manual");
            return;
          }
        }
        if (task?.clientId) {
          const matchingClient = clients.find((item) => item.id === task.clientId) ?? null;
          if (matchingClient) {
            setSelectedProjectKey(`client:${matchingClient.id}`);
            setSelectedClientId(matchingClient.id);
            setSelectedClientName(matchingClient.name);
            setAssociationSource("manual");
            setLockedAssociationTitleKey(titleSearchKey);
            return;
          }
        }
        if (activeDraft?.clientId) {
          const matchingClient = clients.find((item) => item.id === activeDraft.clientId) ?? null;
          if (matchingClient) {
            setSelectedProjectKey(`client:${matchingClient.id}`);
            setSelectedClientId(matchingClient.id);
            setSelectedClientName(matchingClient.name);
            setAssociationSource("manual");
            setLockedAssociationTitleKey(titleSearchKey);
            return;
          }
        }
        // 默认归属：优先选用户所属组织对应的同名客户；匹配不到就不预选，
        // 绝不盲取列表第一个（那样会默认成"贝石基金会"等外部客户）。
        const ownOrgClient = ownOrgName
          ? clients.find((c) => c.name === ownOrgName || c.alias === ownOrgName)
          : null;
        if (ownOrgClient) {
          setSelectedProjectKey(`client:${ownOrgClient.id}`);
          setSelectedClientId(ownOrgClient.id);
          setSelectedClientName(ownOrgClient.name);
          setAssociationSource("default");
        }
        // 匹配不到本组织 → 留空，让用户主动选（标题命中事件线时仍会自动关联）
      } catch {}
    })();
    return () => {
      cancelled = true;
    };
  }, [activeDraft?.clientId, activeDraft?.eventLineId, ownOrgName, syncSelectionFromEventLine, task?.clientId, task?.eventLineId, titleSearchKey]);

  useEffect(() => {
    if (!task) {
      return;
    }
    setTitle(task.title ?? "");
    setDescription(task.description ?? "");
    setActionType(tagLikeToName(task.tags?.[0]) ?? "材料/交付");
    const nextSchedule = getTaskScheduleDateTime(task);
    setCustomDate(nextSchedule?.dateKey ?? getTaskDeadlineDateKey(task));
    setCustomTime(nextSchedule?.timeLabel ?? null);
    setDateCleared(false);
    setDurationMinutes(task.durationMinutes ?? null);
    setCustomReminder(task.reminderMinutesBefore ?? null);
  }, [task]);

  useEffect(() => {
    if (task || !activeDraft) {
      return;
    }
    setTitle(activeDraft.title ?? "");
    setDescription(activeDraft.description ?? "");
    setActionType(activeDraft.tags?.[0] ?? "材料/交付");
    setCustomDate(activeDraft.dueDate ?? null);
    setCustomTime(activeDraft.dueTime ?? null);
    setDateCleared(false);
    setDurationMinutes(activeDraft.durationMinutes ?? null);
  }, [activeDraft, task]);

  useSpeechRecognitionEvent("start", () => {
    if (!voiceInputOwnerRef.current) {
      return;
    }
    voiceStartInFlightRef.current = false;
    setIsVoiceInputActive(true);
  });

  useSpeechRecognitionEvent("end", () => {
    if (!voiceInputOwnerRef.current) {
      return;
    }
    voiceStartInFlightRef.current = false;
    voiceInputOwnerRef.current = false;
    setIsVoiceInputActive(false);
  });

  useSpeechRecognitionEvent("result", (event) => {
    if (!voiceInputOwnerRef.current) {
      return;
    }
    const transcript = getEventTranscript(event);
    if (!transcript) {
      return;
    }
    const parsedDraft = buildLocalSmartTaskDraftFromTranscript(
      transcript,
      customDate ?? preset?.dueDate ?? getTodayDateKey(),
    ).draft;
    const parsedTitle = parsedDraft.title?.trim() || transcript;
    const parsedDescription = parsedDraft.description?.trim() || transcript;
    if (!title.trim()) {
      setTitle(parsedTitle);
      setDescription(parsedDescription);
      if (parsedDraft.dueDate) {
        setCustomDate(parsedDraft.dueDate);
        setDateCleared(false);
      }
      if (parsedDraft.dueTime) {
        setCustomTime(parsedDraft.dueTime);
        setDateCleared(false);
      }
      if (parsedDraft.durationMinutes) {
        setDurationMinutes(parsedDraft.durationMinutes);
      }
      return;
    }
    setDescription((current) => (current.trim() ? `${current.trim()}\n${parsedDescription}` : parsedDescription));
    if (parsedDraft.dueDate && !customDate) {
      setCustomDate(parsedDraft.dueDate);
      setDateCleared(false);
    }
    if (parsedDraft.dueTime && !customTime) {
      setCustomTime(parsedDraft.dueTime);
      setDateCleared(false);
    }
    if (parsedDraft.durationMinutes && !durationMinutes) {
      setDurationMinutes(parsedDraft.durationMinutes);
    }
  });

  useSpeechRecognitionEvent("error", (event) => {
    if (!voiceInputOwnerRef.current) {
      return;
    }
    voiceStartInFlightRef.current = false;
    voiceInputOwnerRef.current = false;
    setIsVoiceInputActive(false);
    Alert.alert("语音输入失败", buildSpeechRecognitionErrorMessage(event, "请稍后再试。"));
  });

  useEffect(() => {
    return () => {
      if (!voiceInputOwnerRef.current) {
        return;
      }
      voiceStartInFlightRef.current = false;
      voiceInputOwnerRef.current = false;
      try {
        ExpoSpeechRecognitionModule.stop();
      } catch {
        // Best-effort cleanup when the modal is dismissed during native recognition.
      }
    };
  }, []);

  useEffect(() => {
    // 1) 优先按标题+描述自动匹配事件线
    if (shouldApplyAutoAssociation({
      source: associationSource,
      lockedTitleKey: lockedAssociationTitleKey,
      titleSearchKey,
      selectedEventLineId: selectedEventLine?.id ?? null,
      autoMatchedEventLineId: autoMatchedEventLine?.id ?? null,
    })) {
      syncSelectionFromEventLine(autoMatchedEventLine, "auto");
      return;
    }
    // 2) 没命中事件线，但标题/描述命中某客户/组织 → 自动选该客户（不覆盖手动/已锁定）
    if (
      !autoMatchedEventLine &&
      autoMatchedClient &&
      associationSource !== "manual" &&
      lockedAssociationTitleKey !== titleSearchKey &&
      selectedClientId !== autoMatchedClient.id
    ) {
      setSelectedProjectKey(`client:${autoMatchedClient.id}`);
      setSelectedClientId(autoMatchedClient.id);
      setSelectedClientName(autoMatchedClient.name);
      setSelectedEventLine(null);
      setAssociationSource("auto");
    }
  }, [associationSource, autoMatchedClient, autoMatchedEventLine, lockedAssociationTitleKey, selectedClientId, selectedEventLine?.id, syncSelectionFromEventLine, titleSearchKey]);

  const handleSelectClient = (project: ProjectOption) => {
    // Set the project selection directly — do NOT let syncSelectionFromEventLine override it
    setSelectedProjectKey(project.id);
    setSelectedClientId(project.clientId);
    setSelectedClientName(project.name);
    setAssociationSource("manual");
    setLockedAssociationTitleKey(titleSearchKey);

    // Find a matching event line under this project, but only set the event line — not the project
    const firstEventLine =
      allEventLines.find((el) => project.clientId ? el.primaryClientId === project.clientId && el.status === "active" : getProjectKey(el) === project.id && el.status === "active") ||
      allEventLines.find((el) => project.clientId ? el.primaryClientId === project.clientId : getProjectKey(el) === project.id) ||
      null;
    setSelectedEventLine(firstEventLine);
    setShowClientPicker(false);
  };

  const handleCreateEventLine = async () => {
    const name = newEventLineName.trim();
    if (!name) { Alert.alert("提示", "请输入事件线名称"); return; }
    setCreatingEventLineLoading(true);
    try {
      const created = await createEventLine({
        name,
        primaryClientId: selectedClientId ?? undefined,
        primaryClientName: selectedClientName ?? undefined,
        status: "active",
      });
      invalidateTaskCreationResources();
      setAllEventLines((prev) => [created, ...prev]);
      syncSelectionFromEventLine(created, "manual");
      setIsCreatingEventLine(false);
      setNewEventLineName("");
      setShowEventLinePicker(false);
    } catch {
      Alert.alert("创建失败", "事件线创建失败，请重试");
    } finally {
      setCreatingEventLineLoading(false);
    }
  };

  const getDueDate = useCallback(() => (
    buildCreateTaskDueDate({
      customDate,
      customTime,
      preset,
      dateCleared,
    })
  ), [customDate, customTime, dateCleared, preset]);

  // 标题即时本地解析:键盘听写/手输"明天下午3点…"自动识别日期时间(零云端、即时)。
  const handleTitleChange = useCallback((text: string) => {
    setTitle(text);
    if (task) return; // 编辑已有任务时不自动改期
    const parsed = parseLocalTaskInput(text);
    if (parsed.dueDate || parsed.dueTime) {
      setDetectedSchedule(parsed);
      if (!customDate && !dateCleared) {
        if (parsed.dueDate) setCustomDate(parsed.dueDate);
        if (parsed.dueTime) setCustomTime(parsed.dueTime);
      }
    } else {
      setDetectedSchedule(null);
    }
  }, [task, customDate, dateCleared]);

  const dismissDetectedSchedule = useCallback(() => {
    setDetectedSchedule(null);
    setCustomDate(null);
    setCustomTime(null);
    setDateCleared(true);
  }, []);

  const handleSubmit = async () => {
    // 保存时用去掉日期文字后的干净标题(若本地识别到日期)
    const submitTitle = (!task && detectedSchedule?.title?.trim()) || title.trim();
    if (!submitTitle) { Alert.alert("提示", "请输入任务标题"); return; }
    setSubmitting(true);
    try {
      const listId = defaultListId ?? await resolveDefaultListId();
      if (!listId) {
        Alert.alert("创建失败", "默认任务列表未配置，请先在设置中确认列表。");
        return;
      }
      setDefaultListId(listId);
      // 起止用 customDate/customTime + customEndDate/customEndTime（与 picker value 同口径），支持跨天
      const startDate = dateCleared ? customDate : customDate ?? (preset?.dueDate ?? null);
      const startTime = dateCleared ? customTime : customTime ?? (preset?.dueTime ?? null);
      const scheduleUpdates = buildScheduleFromStartEnd({
        startDate: task && dateCleared ? null : startDate,
        startTime: task && dateCleared ? null : startTime,
        endDate: customEndDate,
        endTime: customEndTime,
      });
      const payload = {
        title: submitTitle,
        description: description.trim() || undefined,
        // scheduleUpdates 已含由起止推导的 durationMinutes（跨天可 >1440），不再用旧 state 覆盖
        ...scheduleUpdates,
        reminderMinutesBefore: customReminder,
        priority: task?.priority ?? "normal",
        clientId: selectedEventLine?.primaryClientId ?? selectedClientId ?? undefined,
        eventLineId: selectedEventLine?.id,
        tags: [actionType],
        // 负责人/协作人:不选则不发(云端默认分派给创建者)
        ownerId: ownerId ?? undefined,
        collaboratorIds: collaboratorIds.length > 0 ? collaboratorIds : undefined,
      };
      if (task) {
        updateTaskLocalFirst(task.id, {
          ...payload,
          listId: task.listId ?? listId,
        });
      } else {
        createTaskLocalFirst({
          ...payload,
          listId,
        });
      }
      onCreated();
    } catch (e) {
      Alert.alert(task ? "保存失败" : "创建失败", "请检查网络连接后重试");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleVoiceInput = useCallback(async () => {
    if (isVoiceInputActive) {
      voiceStartInFlightRef.current = false;
      voiceInputOwnerRef.current = false;
      setIsVoiceInputActive(false);
      try {
        ExpoSpeechRecognitionModule.stop();
      } catch {
        // Native recognizer may already have ended.
      }
      return;
    }
    if (voiceStartInFlightRef.current) {
      return;
    }
    voiceStartInFlightRef.current = true;
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
        requiresOnDeviceRecognition: false,
        addsPunctuation: true,
        contextualStrings: [selectedClientName, selectedEventLine?.name, title].filter((item): item is string => Boolean(item)),
      } as any);
      setIsVoiceInputActive(true);
    } catch (error) {
      voiceInputOwnerRef.current = false;
      setIsVoiceInputActive(false);
      Alert.alert("语音输入失败", buildSpeechRecognitionErrorMessage(error, "请稍后再试。"));
    } finally {
      voiceStartInFlightRef.current = false;
    }
  }, [isVoiceInputActive, selectedClientName, selectedEventLine?.name, title]);

  const actionTypes = ["材料/交付", "会议/沟通", "内部分析"];

  const ownerMember = orgMembers.find((m) => m.id === ownerId) ?? null;
  const assigneeInitial = ownerMember?.fullName?.charAt(0) ?? "我";
  const assigneeSummary = ownerId
    ? `负责：${ownerMember?.fullName ?? "已选成员"}${collaboratorIds.length ? ` · 协作 ${collaboratorIds.length} 人` : ""}`
    : collaboratorIds.length
      ? `默认负责我 · 协作 ${collaboratorIds.length} 人`
      : "默认分派给我";

  return (
    <View style={s.overlay}>
      <View style={[s.header, { paddingTop: chrome.headerTopPadding }]}>
        <TouchableOpacity onPress={onClose} style={s.closeBtn}><X size={24} color={colors.textTertiary} /></TouchableOpacity>
        <Text style={s.headerTitle}>{task ? "编辑任务" : "快速新建任务"}</Text>
        <TouchableOpacity
          onPress={() => {
            void handleSubmit();
          }}
          disabled={submitting}
        >
          <Text style={s.draftText}>{task ? "保存" : "创建"}</Text>
        </TouchableOpacity>
      </View>
      <ScrollView style={s.body} contentContainerStyle={[s.bodyContent, { paddingBottom: chrome.overlayBottomPadding + 88 }]}>
        <View style={s.titleArea}>
          <TextInput style={s.titleInput} placeholder="准备做什么？(可使用语音输入)" placeholderTextColor={colors.textTertiary} value={title} onChangeText={handleTitleChange} multiline autoFocus />
          <TouchableOpacity
            style={[s.micBtn, isVoiceInputActive && s.micBtnActive]}
            onPress={() => {
              void handleToggleVoiceInput();
            }}
          >
            <Mic size={20} color={isVoiceInputActive ? colors.textOnBrand : colors.brand} />
          </TouchableOpacity>
        </View>
        {!task && detectedSchedule && (detectedSchedule.dueDate || detectedSchedule.dueTime) ? (
          <View style={s.detectChip}>
            <Calendar size={14} color={colors.brand} />
            <Text style={s.detectChipText}>
              已识别 {[detectedSchedule.dueDate, detectedSchedule.dueTime].filter(Boolean).join(" ")}
            </Text>
            <TouchableOpacity onPress={dismissDetectedSchedule} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <X size={13} color={colors.textTertiary} />
            </TouchableOpacity>
          </View>
        ) : null}
        <View style={s.descriptionCard}>
          <Text style={s.descriptionLabel}>{activeDraft ? "智能输入摘要" : "详细内容"}</Text>
          <TextInput
            style={s.descriptionInput}
            placeholder="补充任务详情、背景和备注"
            placeholderTextColor={colors.textTertiary}
            value={description}
            onChangeText={setDescription}
            multiline
            textAlignVertical="top"
          />
        </View>
        <View style={s.contextCard}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}><Sparkles size={14} color={palette.inkBlue} /><Text style={s.contextLabel}>{activeDraft ? "已根据智能输入自动关联" : "已根据当前场景自动关联"}</Text></View>
          {/* Client selector */}
          <TouchableOpacity style={s.contextRow} onPress={() => setShowClientPicker(true)}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}><Briefcase size={14} color={colors.textSecondary} /><Text style={s.contextKey}>关联项目</Text></View>
            <View style={s.contextVal}>
              <Text style={s.contextValText}>{selectedClientName ?? "选择项目"}</Text>
              <ChevronRight size={14} color={colors.textTertiary} />
            </View>
          </TouchableOpacity>
          {/* Event line selector */}
          <TouchableOpacity style={s.contextRow} onPress={() => setShowEventLinePicker(true)}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}><ListTodo size={14} color={colors.textSecondary} /><Text style={s.contextKey}>所在事件线</Text></View>
            <View style={s.contextVal}>
              <Text style={s.contextValText} numberOfLines={1}>{selectedEventLine?.name ?? "选择事件线"}</Text>
              <ChevronRight size={14} color={colors.textTertiary} />
            </View>
          </TouchableOpacity>
        </View>
        {/* Client picker modal */}
        <Modal visible={showClientPicker} transparent animationType="fade" onRequestClose={() => setShowClientPicker(false)}>
          <Pressable style={s.pickerOverlay} onPress={() => setShowClientPicker(false)}>
            <View style={s.pickerCardWrap} onStartShouldSetResponder={() => true}>
              <ScrollView style={s.pickerCard} keyboardShouldPersistTaps="handled">
                <Text style={s.pickerTitle}>选择关联项目</Text>
                {projectOptions.map((project) => (
                  <TouchableOpacity key={project.id} style={[s.pickerItem, selectedProjectKey === project.id && s.pickerItemActive]} onPress={() => handleSelectClient(project)}>
                    <Text style={[s.pickerItemText, selectedProjectKey === project.id && s.pickerItemTextActive]}>{project.name}</Text>
                  </TouchableOpacity>
                ))}
                {projectOptions.length === 0 && <Text style={s.pickerEmpty}>暂无可选项目，将按事件线自动关联</Text>}
                <TouchableOpacity style={s.pickerItem} onPress={() => { syncSelectionFromEventLine(null, "manual"); setShowClientPicker(false); }}>
                  <Text style={[s.pickerItemText, { color: palette.textTertiary }]}>清除关联</Text>
                </TouchableOpacity>
              </ScrollView>
            </View>
          </Pressable>
        </Modal>
        {/* Event line picker modal */}
        <Modal visible={showEventLinePicker} transparent animationType="fade" onRequestClose={() => { setShowEventLinePicker(false); setIsCreatingEventLine(false); setNewEventLineName(""); }}>
          <Pressable style={s.pickerOverlay} onPress={() => { setShowEventLinePicker(false); setIsCreatingEventLine(false); setNewEventLineName(""); }}>
            <View style={s.pickerCardWrap} onStartShouldSetResponder={() => true}>
              <ScrollView style={s.pickerCard} keyboardShouldPersistTaps="handled">
                <Text style={s.pickerTitle}>选择事件线{selectedClientName ? ` · ${selectedClientName}` : ""}</Text>
                {isCreatingEventLine ? (
                  <View style={s.newEventLineRow}>
                    <TextInput
                      style={s.newEventLineInput}
                      placeholder="输入事件线名称"
                      placeholderTextColor={palette.textTertiary}
                      value={newEventLineName}
                      onChangeText={setNewEventLineName}
                      autoFocus
                    />
                    <View style={{ flexDirection: "row", gap: 8, marginTop: 10 }}>
                      <TouchableOpacity
                        style={[s.newEventLineBtn, creatingEventLineLoading && { opacity: 0.5 }]}
                        onPress={handleCreateEventLine}
                        disabled={creatingEventLineLoading}
                      >
                        <Text style={s.newEventLineBtnText}>{creatingEventLineLoading ? "创建中..." : "确认创建"}</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={s.newEventLineCancelBtn}
                        onPress={() => { setIsCreatingEventLine(false); setNewEventLineName(""); }}
                      >
                        <Text style={s.newEventLineCancelText}>取消</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ) : (
                  <TouchableOpacity style={s.pickerItem} onPress={() => setIsCreatingEventLine(true)}>
                    <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                      <Plus size={14} color={palette.inkBlack} />
                      <Text style={[s.pickerItemText, { color: palette.inkBlack, fontWeight: "700" }]}>新建事件线</Text>
                    </View>
                  </TouchableOpacity>
                )}
                {filteredEventLines.map((el) => (
                  <TouchableOpacity key={el.id} style={[s.pickerItem, selectedEventLine?.id === el.id && s.pickerItemActive]} onPress={() => { syncSelectionFromEventLine(el, "manual"); setShowEventLinePicker(false); setIsCreatingEventLine(false); setNewEventLineName(""); }}>
                    <Text style={[s.pickerItemText, selectedEventLine?.id === el.id && s.pickerItemTextActive]} numberOfLines={1}>{el.name}</Text>
                  </TouchableOpacity>
                ))}
                {filteredEventLines.length === 0 && !isCreatingEventLine && <Text style={s.pickerEmpty}>该项目下暂无事件线</Text>}
                <TouchableOpacity style={s.pickerItem} onPress={() => { syncSelectionFromEventLine(null, "manual"); setShowEventLinePicker(false); setIsCreatingEventLine(false); setNewEventLineName(""); }}>
                  <Text style={[s.pickerItemText, { color: palette.textTertiary }]}>清除关联</Text>
                </TouchableOpacity>
              </ScrollView>
            </View>
          </Pressable>
        </Modal>
        <View style={s.props}>
          <TouchableOpacity style={s.propRow} onPress={() => setShowDatePicker(true)}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}><Calendar size={20} color={colors.accent} /><Text style={s.propLabel}>设置时间</Text></View>
            <Text style={s.propDateHint}>{(() => {
              const dueDate = getDueDate();
              if (!dueDate) return "未排期";
              const [date, time] = dueDate.split("T");
              return `${date.replace(/-/g, "/")}${time ? " " + time.slice(0, 5) : ""}`;
            })()}</Text>
          </TouchableOpacity>
          {showDatePicker && (
            <DateTimePickerSheet
              value={{
                date: dateCleared ? customDate : customDate ?? (preset?.dueDate ?? null),
                time: dateCleared ? customTime : customTime ?? (preset?.dueTime ?? null),
                endDate: customEndDate,
                endTime: customEndTime,
                durationMinutes: null,
                reminderMinutesBefore: customReminder,
              }}
              onChange={(v) => {
                setCustomDate(v.date);
                setCustomTime(v.time);
                setCustomEndDate(v.endDate ?? null);
                setCustomEndTime(v.endTime ?? null);
                setCustomReminder(v.reminderMinutesBefore ?? null);
                setDateCleared(false);
              }}
              onClose={() => setShowDatePicker(false)}
              onClear={() => { setCustomDate(null); setCustomTime(null); setCustomEndDate(null); setCustomEndTime(null); setDateCleared(true); }}
            />
          )}
          <Text style={s.feishuSyncHint}>
            手机版创建的任务会经组织云同步到电脑端；若组织已接通飞书，也会进入飞书任务，带时间时生成日历提醒。
          </Text>
          <View style={s.propRow}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}><Tag size={20} color={colors.accent} /><Text style={s.propLabel}>动作类型</Text></View>
            <View style={s.chips}>{actionTypes.map(t => (
              <TouchableOpacity key={t} style={[s.chip, actionType === t && s.chipBrand]} onPress={() => setActionType(t)}>
                <Text style={[s.chipText, actionType === t && s.chipTextActive]}>{t}</Text>
              </TouchableOpacity>
            ))}</View>
          </View>
          <View style={s.propRow}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}><User size={20} color={colors.accent} /><Text style={s.propLabel}>执行 / 协同</Text></View>
            <TouchableOpacity style={s.assigneeBtn} activeOpacity={0.7} onPress={() => setShowAssigneePicker(true)}>
              <View style={s.assigneeAvatar}><Text style={s.assigneeAvatarText}>{assigneeInitial}</Text></View>
              <Text style={s.assigneeText} numberOfLines={1}>{assigneeSummary}</Text>
              <ChevronRight size={16} color={colors.textTertiary} />
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
      <View style={[s.bottomBar, { paddingBottom: chrome.overlayBottomPadding }]}>
        <TouchableOpacity style={[s.submitBtn, submitting && s.submitBtnDisabled]} onPress={handleSubmit} disabled={submitting}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6 }}>{!submitting && <CheckCircle2 size={20} color={palette.paperRice} />}<Text style={s.submitBtnText}>{submitting ? (task ? "保存中..." : "创建中...") : (task ? "保存修改" : "创建任务")}</Text></View>
        </TouchableOpacity>
      </View>

      <Modal visible={showAssigneePicker} transparent animationType="slide" onRequestClose={() => setShowAssigneePicker(false)}>
        <Pressable style={s.pickerBackdrop} onPress={() => setShowAssigneePicker(false)} />
        <View style={[s.pickerSheet, { paddingBottom: chrome.overlayBottomPadding + 8 }]}>
          <View style={s.pickerHeader}>
            <Text style={s.assigneePickerTitle}>负责人 / 协作人</Text>
            <TouchableOpacity onPress={() => setShowAssigneePicker(false)}><Text style={s.pickerDone}>完成</Text></TouchableOpacity>
          </View>
          <Text style={s.pickerHint}>点左侧圆圈设为负责人,点右侧「协作」加为协作人。都不选则默认分派给自己。</Text>
          <ScrollView style={{ maxHeight: 400 }} keyboardShouldPersistTaps="handled">
            {orgMembers.length === 0 ? (
              <Text style={s.assigneePickerEmpty}>暂未加载到组织成员(可稍后重试),将默认分派给自己。</Text>
            ) : orgMembers.map((m) => {
              const isOwner = ownerId === m.id;
              const isCollab = collaboratorIds.includes(m.id);
              const sub = [m.departmentName, m.jobTitle].filter(Boolean).join(" · ");
              return (
                <View key={m.id} style={s.memberRow}>
                  <TouchableOpacity
                    style={[s.ownerRadio, isOwner && s.ownerRadioOn]}
                    onPress={() => {
                      setOwnerId(isOwner ? null : m.id);
                      if (!isOwner) setCollaboratorIds((prev) => prev.filter((id) => id !== m.id));
                    }}
                  >
                    {isOwner ? <Check size={14} color={palette.paperRice} /> : null}
                  </TouchableOpacity>
                  <View style={{ flex: 1 }}>
                    <Text style={s.memberName} numberOfLines={1}>{m.fullName}{isOwner ? "  · 负责人" : ""}</Text>
                    {sub ? <Text style={s.memberSub} numberOfLines={1}>{sub}</Text> : null}
                  </View>
                  <TouchableOpacity
                    style={[s.collabChip, isCollab && s.collabChipOn, isOwner && s.collabChipDisabled]}
                    disabled={isOwner}
                    onPress={() => setCollaboratorIds((prev) => isCollab ? prev.filter((id) => id !== m.id) : [...prev, m.id])}
                  >
                    <Text style={[s.collabChipText, isCollab && s.collabChipTextOn]}>协作</Text>
                  </TouchableOpacity>
                </View>
              );
            })}
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  overlay: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: colors.surface, zIndex: 50 },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 16, paddingTop: 0, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: colors.borderLight },
  closeBtn: { padding: 8 }, closeText: { fontSize: 20, color: colors.textTertiary },
  headerTitle: { fontSize: 14, fontWeight: "700", color: colors.text },
  draftText: { fontSize: 14, fontWeight: "700", color: colors.accent },
  body: { flex: 1 }, bodyContent: { padding: 20, paddingBottom: 0 },
  titleArea: { position: "relative", marginBottom: 20 },
  titleInput: { fontSize: 22, fontWeight: "700", color: colors.text, minHeight: 80, textAlignVertical: "top", paddingRight: 44 },
  micBtn: { position: "absolute", right: 0, bottom: 4, padding: 8, backgroundColor: colors.surfaceSecondary, borderRadius: 20 },
  detectChip: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: 6,
    marginTop: -8,
    marginBottom: 16,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: colors.brandBg,
    borderWidth: 1,
    borderColor: palette.airyBlueBorder,
  },
  detectChipText: { fontSize: 13, fontWeight: "600", color: colors.brand },
  micBtnActive: { backgroundColor: colors.brand },
  micIcon: { fontSize: 18 },
  descriptionCard: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: colors.borderLight },
  descriptionLabel: { fontSize: 12, fontWeight: "700", color: colors.textSecondary, marginBottom: 10 },
  descriptionInput: { minHeight: 104, fontSize: 14, lineHeight: 22, color: colors.text },
  contextCard: { backgroundColor: palette.paperMoon, borderWidth: 1, borderColor: palette.borderSubtle, borderRadius: 16, padding: 16, marginBottom: 20 },
  contextLabel: { fontSize: 11, fontWeight: "800", color: palette.inkBlue, marginBottom: 12, textTransform: "uppercase" as const },
  contextRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", backgroundColor: "rgba(255,255,255,0.6)", paddingHorizontal: 12, paddingVertical: 8, borderRadius: 12, borderWidth: 1, borderColor: "rgba(255,255,255,0.8)", marginBottom: 8 },
  contextKey: { fontSize: 12, color: colors.textSecondary, fontWeight: "500" },
  contextVal: { flexDirection: "row", alignItems: "center", gap: 8 },
  contextValText: { fontSize: 14, fontWeight: "700", color: colors.text, maxWidth: 140 },
  contextX: { fontSize: 12, color: colors.textTertiary },
  props: { gap: 16, paddingTop: 8 },
  propRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingBottom: 16, borderBottomWidth: 1, borderBottomColor: colors.borderLight },
  propLabel: { fontSize: 14, fontWeight: "500", color: colors.textSecondary },
  propDateHint: { fontSize: 13, color: palette.textTertiary, fontWeight: "400" },
  feishuSyncHint: {
    marginTop: -8,
    marginBottom: 2,
    fontSize: 12,
    lineHeight: 18,
    color: palette.textTertiary,
  },
  chips: { flexDirection: "row", gap: 8 },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: colors.surfaceSecondary },
  chipActive: { backgroundColor: colors.accentBg2, borderWidth: 1, borderColor: colors.accent },
  chipBrand: { backgroundColor: colors.brandBg2, borderWidth: 1, borderColor: colors.brand },
  chipText: { fontSize: 12, fontWeight: "500", color: colors.textSecondary },
  chipTextActive: { color: colors.text, fontWeight: "700" },
  assigneeBtn: { flexDirection: "row", alignItems: "center", backgroundColor: colors.surfaceSecondary, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, gap: 6 },
  assigneeAvatar: { width: 16, height: 16, borderRadius: 8, backgroundColor: colors.brand, alignItems: "center", justifyContent: "center" },
  assigneeAvatarText: { fontSize: 8, fontWeight: "700", color: colors.textOnBrand },
  assigneeText: { fontSize: 14, fontWeight: "700", color: colors.text },
  assigneeChevron: { fontSize: 14, color: colors.textTertiary },
  // 负责人/协作人选择器
  pickerBackdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(0,0,0,0.35)" },
  pickerSheet: { position: "absolute", left: 0, right: 0, bottom: 0, backgroundColor: colors.surface, borderTopLeftRadius: 20, borderTopRightRadius: 20, paddingHorizontal: 16, paddingTop: 14 },
  pickerHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 6 },
  assigneePickerTitle: { fontSize: 16, fontWeight: "800", color: colors.text },
  pickerDone: { fontSize: 15, fontWeight: "800", color: colors.brand },
  pickerHint: { fontSize: 12, color: colors.textSecondary, lineHeight: 18, marginBottom: 10 },
  assigneePickerEmpty: { fontSize: 13, color: colors.textTertiary, paddingVertical: 24, textAlign: "center" },
  memberRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.borderLight },
  ownerRadio: { width: 26, height: 26, borderRadius: 13, borderWidth: 1.5, borderColor: palette.inkBlue, alignItems: "center", justifyContent: "center" },
  ownerRadioOn: { backgroundColor: palette.inkBlue, borderColor: palette.inkBlue },
  memberName: { fontSize: 15, fontWeight: "600", color: colors.text },
  memberSub: { fontSize: 12, color: colors.textTertiary, marginTop: 2 },
  collabChip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 14, borderWidth: 1, borderColor: colors.borderLight, backgroundColor: colors.surfaceSecondary },
  collabChipOn: { backgroundColor: palette.bambooGreen, borderColor: palette.bambooGreen },
  collabChipDisabled: { opacity: 0.35 },
  collabChipText: { fontSize: 13, fontWeight: "700", color: colors.textSecondary },
  collabChipTextOn: { color: palette.paperRice },
  bottomBar: { position: "absolute", bottom: 0, left: 0, right: 0, padding: 16, paddingBottom: 0, borderTopWidth: 1, borderTopColor: colors.borderLight, backgroundColor: colors.surface },
  submitBtn: { backgroundColor: colors.accent, borderRadius: 16, paddingVertical: 14, alignItems: "center", ...shadow.elevated },
  submitBtnDisabled: { opacity: 0.6 },
  submitBtnText: { fontSize: 18, fontWeight: "800", color: colors.textOnBrand },
  // Picker modals
  pickerOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.3)", justifyContent: "center", alignItems: "center", paddingHorizontal: 40 },
  pickerCardWrap: { width: "100%" },
  pickerCard: { backgroundColor: palette.paperRice, borderRadius: 16, paddingVertical: 8, width: "100%", maxHeight: 400, shadowColor: palette.inkBlack, shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.15, shadowRadius: 24, elevation: 8 },
  pickerTitle: { fontSize: 14, fontWeight: "700", color: palette.textSecondary, paddingHorizontal: 20, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: palette.borderSubtle },
  pickerItem: { paddingHorizontal: 20, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: palette.paperMoon },
  pickerItemActive: { backgroundColor: palette.paperMoon },
  pickerItemText: { fontSize: 15, fontWeight: "500", color: palette.inkBlack },
  pickerItemTextActive: { color: palette.inkBlack, fontWeight: "700" },
  pickerEmpty: { fontSize: 13, color: palette.textTertiary, paddingHorizontal: 20, paddingVertical: 14, textAlign: "center" },
  newEventLineRow: { paddingHorizontal: 20, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: palette.borderSubtle },
  newEventLineInput: { fontSize: 15, fontWeight: "500", color: palette.inkBlack, borderWidth: 1, borderColor: palette.borderSubtle, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10, backgroundColor: palette.paperMoon },
  newEventLineBtn: { flex: 1, backgroundColor: palette.inkBlack, borderRadius: 10, paddingVertical: 10, alignItems: "center" },
  newEventLineBtnText: { fontSize: 14, fontWeight: "700", color: palette.paperRice },
  newEventLineCancelBtn: { flex: 1, backgroundColor: palette.borderSubtle, borderRadius: 10, paddingVertical: 10, alignItems: "center" },
  newEventLineCancelText: { fontSize: 14, fontWeight: "500", color: palette.textSecondary },
});
