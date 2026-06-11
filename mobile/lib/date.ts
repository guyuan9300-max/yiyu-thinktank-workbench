function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

export function formatLocalDateKey(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

export function parseLocalDateKey(dateKey: string): Date {
  const match = dateKey.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return new Date(dateKey);
  }
  const [, year, month, day] = match;
  return new Date(Number(year), Number(month) - 1, Number(day));
}

export function addDays(date: Date, deltaDays: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + deltaDays);
  return next;
}

export function startOfLocalDay(date: Date): Date {
  const next = new Date(date);
  next.setHours(0, 0, 0, 0);
  return next;
}

export function endOfLocalDay(date: Date): Date {
  const next = new Date(date);
  next.setHours(23, 59, 59, 999);
  return next;
}

export function getLocalWeekRangeKeys(date: Date): { startKey: string; endKey: string } {
  const monday = getLocalWeekAnchorDate(date);
  const sunday = addDays(monday, 6);
  return {
    startKey: formatLocalDateKey(monday),
    endKey: formatLocalDateKey(sunday),
  };
}

export function getLocalWeekAnchorDate(date: Date): Date {
  const start = startOfLocalDay(date);
  const day = start.getDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  return addDays(start, mondayOffset);
}

export function getLocalWeekAnchorDateKey(date: Date): string {
  return formatLocalDateKey(getLocalWeekAnchorDate(date));
}

export function weekLabelForDate(baseDate: Date): string {
  const utcDate = new Date(Date.UTC(baseDate.getFullYear(), baseDate.getMonth(), baseDate.getDate()));
  const day = utcDate.getUTCDay() || 7;
  utcDate.setUTCDate(utcDate.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(utcDate.getUTCFullYear(), 0, 1));
  const week = Math.ceil((((utcDate.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  return `${utcDate.getUTCFullYear()}-W${pad2(week)}`;
}

export function weekLabelForDateKey(dateKey: string): string {
  return weekLabelForDate(parseLocalDateKey(dateKey));
}

export function formatWeekLabelCn(weekLabel: string): string {
  const match = weekLabel.match(/^\d{4}-W(\d{2})$/);
  return match ? `第${parseInt(match[1], 10)}周` : weekLabel;
}

export function buildWeekInfo(date: Date): { weekAnchorDate: string; weekLabel: string } {
  const weekAnchorDate = getLocalWeekAnchorDateKey(date);
  return {
    weekAnchorDate,
    weekLabel: weekLabelForDateKey(weekAnchorDate),
  };
}

export function isDateKeyWithinWeek(dateKey: string | null | undefined, weekAnchorDate: string): boolean {
  if (!dateKey) {
    return false;
  }
  const target = dateKey.slice(0, 10);
  const { startKey, endKey } = getLocalWeekRangeKeys(parseLocalDateKey(weekAnchorDate));
  return target >= startKey && target <= endKey;
}
