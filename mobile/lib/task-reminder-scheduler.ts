import { Platform } from "react-native";
import { requireOptionalNativeModule } from "expo-modules-core";
import * as localDb from "./local-db";
import { getTaskScheduleDateTime, getTaskDeadlineDate } from "./task-time";
import { devLog } from "./dev-log";
import type { TaskRecord } from "./types";

// 任务提醒本地通知调度。
// 设计：提醒提前量(reminderMinutesBefore)作为任务字段跨端同步；各端按
// "计划时间(scheduledStartAt 优先, 否则 deadlineAt) − 提前量" 在本地排一条系统通知。
// 用确定性 identifier(每任务一个) 免维护 id 映射；重排=先取消同 id 再排。
//
// 关键：expo-notifications 是原生模块。为了让"未重打包"的构建也能正常启动，
// 这里【不在顶层 import】它（顶层 import 在缺原生模块的包里会让整条依赖链崩），
// 改为运行时 guarded require：拿不到就全部静默 no-op，重打包后自动生效。

type NotificationsModule = typeof import("expo-notifications");

const REMINDER_CHANNEL_ID = "task-reminders";
let channelReady = false;
let permissionGranted = false;
let notifModule: NotificationsModule | null = null;
let notifTried = false;

function getNotifications(): NotificationsModule | null {
  if (notifTried) return notifModule;
  notifTried = true;
  // 关键：先用【不抛错】的 requireOptionalNativeModule 探测原生通知模块是否编进了包。
  // 不在(未重打包)就根本不去 require("expo-notifications")——它内部各子模块在缺原生
  // 模块时会 requireNativeModule 抛出并上报 LogBox 红屏(绕过 try/catch)。
  const nativeReady = requireOptionalNativeModule("ExpoNotificationScheduler") != null;
  if (!nativeReady) {
    devLog("reminder", "notifications native module unavailable (rebuild needed)");
    notifModule = null;
    return null;
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    notifModule = require("expo-notifications") as NotificationsModule;
  } catch (error) {
    devLog("reminder", "expo-notifications load failed", { error });
    notifModule = null;
  }
  return notifModule;
}

function reminderIdentifier(taskId: string): string {
  return `task-reminder:${taskId}`;
}

/**
 * 申请通知权限 + 建好带声音/震动的 Android 渠道。幂等。
 * 注意：不在登录/启动时无条件调用——改为"首次真正需要排提醒时"懒申请（见 scheduleTaskReminder），
 * 避免用户一登录就被弹通知权限。
 */
export async function ensureReminderSetup(): Promise<boolean> {
  const Notifications = getNotifications();
  if (!Notifications) return false;
  try {
    const settings = await Notifications.getPermissionsAsync();
    permissionGranted = settings.granted;
    if (!permissionGranted) {
      const requested = await Notifications.requestPermissionsAsync({
        ios: { allowAlert: true, allowSound: true, allowBadge: true },
      });
      permissionGranted = requested.granted;
    }
    if (Platform.OS === "android" && !channelReady) {
      await Notifications.setNotificationChannelAsync(REMINDER_CHANNEL_ID, {
        name: "任务提醒",
        importance: Notifications.AndroidImportance.HIGH, // HIGH 才会响铃+横幅
        sound: "default",
        enableVibrate: true,
        vibrationPattern: [0, 250, 250, 250],
      });
      channelReady = true;
    }
    return permissionGranted;
  } catch (error) {
    devLog("reminder", "setup failed", { error });
    return false;
  }
}

// 纯日期任务（只有"哪天"没有"几点"）的提醒锚点：当天上午 9:00。
// 对标滴答清单 all-day 任务的默认晨间提醒（已与产品确认）。
const ALL_DAY_REMINDER_HOUR = 9;

/**
 * 解析提醒应锚定的基准时刻：
 *  1) 有明确时间的计划时刻（scheduledStartAt 优先，其次带时间的 dueDate）→ 用真实时刻；
 *  2) 否则回退到截止日 deadlineAt。本应用 deadlineAt 按"天"粒度处理，故锚定当天 9:00。
 */
function resolveReminderBaseTime(task: TaskRecord): Date | null {
  const scheduled = getTaskScheduleDateTime(task);
  if (scheduled?.value) return scheduled.value;
  const deadline = getTaskDeadlineDate(task);
  if (!deadline) return null;
  return new Date(
    deadline.getFullYear(),
    deadline.getMonth(),
    deadline.getDate(),
    ALL_DAY_REMINDER_HOUR,
    0,
    0,
    0,
  );
}

/** 计算提醒触发时刻；返回 null 表示不该排程（无提醒/无时间/已完成/已删除/已过期）。 */
function computeReminderTrigger(task: TaskRecord): Date | null {
  if (task.reminderMinutesBefore == null) return null;
  if (task.progressStatus === "done") return null;
  if (task.deletedAt) return null;
  const baseTime = resolveReminderBaseTime(task);
  if (!baseTime) return null;
  const triggerMs = baseTime.getTime() - task.reminderMinutesBefore * 60_000;
  if (triggerMs <= Date.now()) return null; // 已过去的不排
  return new Date(triggerMs);
}

function reminderBody(minutesBefore: number): string {
  if (minutesBefore === 0) return "任务现在开始";
  return `任务将在 ${minutesBefore} 分钟后开始`;
}

/** 为单个任务排（或重排）提醒：先取消旧的，再按当前字段排。无需提醒则只取消。 */
export async function scheduleTaskReminder(task: TaskRecord): Promise<void> {
  const Notifications = getNotifications();
  if (!Notifications) return;
  try {
    const identifier = reminderIdentifier(task.id);
    await Notifications.cancelScheduledNotificationAsync(identifier).catch(() => undefined);
    const trigger = computeReminderTrigger(task);
    if (!trigger) return;
    if (!permissionGranted) {
      const ok = await ensureReminderSetup();
      if (!ok) return;
    }
    await Notifications.scheduleNotificationAsync({
      identifier,
      content: {
        title: task.title?.trim() || "任务提醒",
        body: reminderBody(task.reminderMinutesBefore ?? 0),
        sound: "default",
      },
      trigger: {
        type: Notifications.SchedulableTriggerInputTypes.DATE,
        date: trigger,
        channelId: REMINDER_CHANNEL_ID,
      },
    });
  } catch (error) {
    devLog("reminder", "schedule failed", { error });
  }
}

/** 取消某任务的提醒（删除/完成时调）。 */
export async function cancelTaskReminder(taskId: string): Promise<void> {
  const Notifications = getNotifications();
  if (!Notifications) return;
  try {
    await Notifications.cancelScheduledNotificationAsync(reminderIdentifier(taskId));
  } catch (error) {
    devLog("reminder", "cancel failed", { error });
  }
}

/** 全量重排（登录启动后、以及云端同步回填后调）。 */
export async function rescheduleAllReminders(): Promise<void> {
  const Notifications = getNotifications();
  if (!Notifications) return;
  try {
    // 不在此处无条件 ensureReminderSetup（会在登录/回填时弹权限）。
    // 每个 scheduleTaskReminder 只有在真有提醒要排时才懒申请权限。
    const tasks = localDb.getAllTasks();
    for (const task of tasks) {
      await scheduleTaskReminder(task);
    }
  } catch (error) {
    devLog("reminder", "reschedule-all failed", { error });
  }
}
