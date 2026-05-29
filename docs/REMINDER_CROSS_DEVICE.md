# 跨设备任务提醒 · 桌面端 v1 规格(定稿 2026-05-29)

> 目标:桌面端任务到点提醒(右上角红时间 + 闪一下消除);与手机端共享同一提醒字段,云同步后自动联动。手机端已实现,可对照参考。

## 0. 决策锁定(顾源源 5/29)

| 项 | 决定 |
|---|---|
| 提醒次数 | **二选一**:每任务一个提醒(单整数字段) |
| 提醒值 | `null`=不提醒 / `0`=准时 / `5`=提前5分钟 |
| 基准时间 | `scheduledStartAt`(计划开始)优先,无则 `deadlineAt`(截止) |
| 时序模型 | **Model B**:准备窗口持续显示 + 到任务点闪一下消除(见 §3) |
| 提醒方式 | **仅右上角红数字闪一下消除**(无 dock 弹跳、无声音;窗口可见时有效) |
| 触发条件 | **只有专门设了提醒的任务**(`reminder_minutes_before != null`),不是所有带时间的任务 |
| 设置勾选作用 | 设置→任务与日程的"准时/提前5分"= **新任务默认值**;每任务在任务编辑器单独开关 |
| 范围 | 桌面本机先做 → 紧接补云端字段让手机联动 |

## 1. 字段契约(两端 + 云端完全一致)

- DB / 后端:`reminder_minutes_before INTEGER`(0=准时,5=提前5分,NULL=不提醒)
- 前端 / camelCase:`reminderMinutesBefore`
- 相对时间:`scheduledStartAt`,无则 `deadlineAt`
- 时间格式:本地裸时间 `YYYY-MM-DDTHH:mm`,禁止混入带 Z 的 UTC(否则提醒偏一个时区)

## 2. 改动清单

### A. 字段地基(本地 + 共享 + 云端)
- `backend/app/db.py` tasks 表(1251)加 `reminder_minutes_before` 列(走 `_ensure_column` migration)+ 版本号 +1
- `backend/app/main.py`:任务上行 POST 带该字段、下行 GET/序列化回写本地、cloud payload 透传
- `src/shared/types.ts` Task(2581 附近)+ create/update payload 类型加 `reminderMinutesBefore`
- `src/shared/taskTime.ts` TaskTimeInput 加 `reminderMinutesBefore`
- `cloud_backend/app/db.py` tasks 加列(`_ensure_column`);`models.py` TaskCreate/UpdatePayload 加 `reminderMinutesBefore`;`main.py` `_task_record` 序列化回传(云端只存+回传,不推送)

### B. 设置项
- 设置→「任务与日程」(App.tsx settingsSection,保存流程在 ~27400)加「闹钟提醒」:准时提醒 / 提前5分钟 勾选 → 作为新任务默认 `reminderMinutesBefore`

### C. 任务编辑器(日历/日程)
- 任务编辑器(App.tsx ~13198,有 scheduledStartAt/dueTime)加每任务"提醒:关 / 准时 / 提前5分"控件

### D. 触发(核心)
- **右上角红时间指示器 = 渲染端**:渲染端有任务数据 + 计时器,自算"准备窗口",窗口可见时显示
- **到点闪一下 = 渲染端**(本 v1 仅视觉闪,无 dock/声音)
- 调度唯一真相源建议放渲染端定时器(本 v1 纯视觉、无跨进程通知需求);未来加 dock/系统通知兜底时再上主进程调度
- **dedup 持久化**:记录已闪过的(任务+触发时刻),app 重启不重闪;启动时跳过超过宽限期的陈旧提醒

## 3. 时序模型 B(定稿)

任务 5:00 开始:
- **提前5分(=5)**:`4:55` 起 → 右上角持续显示红色「4:55」+ 任务名(这 5 分钟准备窗口);到 `5:00` 整点 → 闪一下 → 清除
- **准时(=0)**:到 `5:00` → 直接闪一下 → 清除(无准备窗口)
- 准备窗口 = `[计划时间 − 提前量, 计划时间]`;提前量 0 时窗口为 0,只在到点闪

## 4. 联动验证(补云端字段后)
桌面设"提前5分" → 云端 tasks 表有值 → 手机 pull 拿到 → 手机本地到点响(手机端已实现,声音+震动);反之亦然。手机端不重打包,等"同步手机"再一起打。

## 5. 未来层(本 v1 不做)
- **always-on 兜底**:复用云端已有飞书到点推送引擎(`org_feishu_notifications` due 队列 + 3 后台线程),任务有提醒时云端算 `due_at` enqueue → 全端关闭也能推飞书。本 v1 只做窗口可见的视觉提醒。

## 参考:手机端实现
- 调度:`mobile/lib/task-reminder-scheduler.ts`
- 提前量 UI:`mobile/components/DateTimePickerSheet.tsx`(REMINDER_PRESETS)
- 字段:`mobile/lib/local-db.ts`(reminder_minutes_before 列 + migration)、`mobile/lib/sync-engine.ts`(push/pull)
