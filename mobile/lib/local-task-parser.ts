/**
 * local-task-parser.ts —— 本地规则式"智能识别日期/时间"(对标滴答清单,零云端、即时、离线)。
 *
 * 输入一句中文(键盘听写或手输),抽取出:
 *  - dueDate:  YYYY-MM-DD | null
 *  - dueTime:  HH:MM | null
 *  - title:    去掉已识别的日期/时间文字后的干净标题
 *
 * 规则源自后端 smart_input.py 的 _parse_date_range/_parse_time_range(已在生产验证),
 * 在此基础上补了星期(周五/下周一)解析。纯函数,不依赖任何网络。
 */

const CN_DIGITS: Record<string, number> = {
  零: 0, 〇: 0, 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9,
};

const WEEKDAY_CN: Record<string, number> = {
  日: 0, 天: 0, 一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6,
};

export interface ParsedTask {
  title: string;
  dueDate: string | null;
  dueTime: string | null;
}

function coerceChineseNumber(raw: string): number | null {
  const value = raw.trim();
  if (!value) return null;
  if (/^\d+$/.test(value)) return parseInt(value, 10);
  if (value === "十") return 10;
  if (value.includes("十")) {
    const [left, right] = value.split("十");
    const tens = left === "" ? 1 : CN_DIGITS[left];
    if (tens === undefined) return null;
    const ones = right === "" ? 0 : CN_DIGITS[right];
    if (ones === undefined) return null;
    return tens * 10 + ones;
  }
  if (value.length === 1) return CN_DIGITS[value] ?? null;
  let total = 0;
  for (const ch of value) {
    const d = CN_DIGITS[ch];
    if (d === undefined) return null;
    total = total * 10 + d;
  }
  return total;
}

/** 把"数字上下文"里的中文数字转成阿拉伯数字(三点→3点、十五日→15日、二十三号→23号)。 */
function normalizeSpokenText(text: string): string {
  return text.replace(/([零〇一二两三四五六七八九十]{1,3})(月|日|号|点|时|分)/g, (_m, cn: string, unit: string) => {
    const n = coerceChineseNumber(cn);
    return n === null ? `${cn}${unit}` : `${n}${unit}`;
  });
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function toKey(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function safeDate(year: number, month1: number, day: number): Date | null {
  const d = new Date(year, month1 - 1, day);
  if (d.getFullYear() !== year || d.getMonth() !== month1 - 1 || d.getDate() !== day) return null;
  return d;
}

interface Hit {
  dateKey?: string | null;
  time?: string | null;
  span: string; // 命中的原文片段,用于从标题里抹掉
}

/** 解析日期。返回命中(含原文片段用于抹除)。 */
function parseDate(text: string, ref: Date): Hit | null {
  const norm = normalizeSpokenText(text);

  // 绝对日期:M月D日 / M月D号
  const abs = norm.match(/(?:(\d{4})年)?\s*(\d{1,2})月(\d{1,2})(?:日|号)?/);
  if (abs) {
    const year = abs[1] ? parseInt(abs[1], 10) : ref.getFullYear();
    const d = safeDate(year, parseInt(abs[2], 10), parseInt(abs[3], 10));
    if (d) return { dateKey: toKey(d), span: abs[0] }; // 无年份默认今年(不擅自顺延明年)
  }

  // 相对:今天/明天/后天/大后天/昨天
  const rel: [RegExp, number][] = [
    [/大后天/, 3], [/后天/, 2], [/明天|明日/, 1], [/今天|今日|今晚|今早/, 0], [/昨天/, -1],
  ];
  for (const [re, offset] of rel) {
    const m = norm.match(re);
    if (m) {
      const d = new Date(ref);
      d.setDate(d.getDate() + offset);
      return { dateKey: toKey(d), span: m[0] };
    }
  }

  // 星期:下周X / 下星期X / 本周X / 周X / 星期X / 礼拜X
  const wk = norm.match(/(下{1,2}|本|这)?\s*(?:周|星期|礼拜)([一二三四五六日天])/);
  if (wk) {
    const target = WEEKDAY_CN[wk[2]];
    if (target !== undefined) {
      // 以周一为一周起点计算偏移(中文习惯):本周X / 下周X / 不带前缀=下一个X。
      const targetMon = (target + 6) % 7; // 周一=0 … 周日=6
      const curMon = (ref.getDay() + 6) % 7;
      let offset = targetMon - curMon;
      const prefix = wk[1] || "";
      const downCount = (prefix.match(/下/g) || []).length;
      if (downCount > 0) offset += 7 * downCount;
      else if (!prefix && offset <= 0) offset += 7; // 不带前缀且已过/今天 → 取下一个
      const d = new Date(ref);
      d.setDate(d.getDate() + offset);
      return { dateKey: toKey(d), span: wk[0] };
    }
  }

  // N 天后 / N 天内
  const days = norm.match(/(\d{1,2})\s*天(?:后|之后)/);
  if (days) {
    const d = new Date(ref);
    d.setDate(d.getDate() + parseInt(days[1], 10));
    return { dateKey: toKey(d), span: days[0] };
  }

  return null;
}

function convertClock(hour: number, minute: number, meridiem: string | undefined): [number, number] {
  const label = (meridiem || "").trim();
  if ((label === "下午" || label === "晚上" || label === "傍晚") && hour < 12) hour += 12;
  if (label === "中午" && hour < 11) hour += 12;
  return [hour % 24, minute];
}

/** 解析时间 → HH:MM(+命中片段)。 */
function parseTime(text: string): Hit | null {
  const norm = normalizeSpokenText(text);
  const m = norm.match(/(上午|早上|中午|下午|晚上|傍晚)?\s*(\d{1,2})(?:[:：点时](\d{1,2})?)?\s*(半)?/);
  if (!m) return null;
  // 必须真出现"点/时/:/半"或带时段,才认为是时间,否则可能是普通数字
  const hasClockMark = /[:：点时]|半/.test(m[0]) || Boolean(m[1]);
  if (!hasClockMark) return null;
  let hour = parseInt(m[2], 10);
  let minute = m[3] ? parseInt(m[3], 10) : 0;
  if (m[4] === "半") minute = 30;
  if (hour > 23 || minute > 59) return null;
  [hour, minute] = convertClock(hour, minute, m[1]);
  return { time: `${pad(hour)}:${pad(minute)}`, span: m[0] };
}

const LEADING_FILLER = /^(?:帮我|请|麻烦|记一下|记一笔|提醒我|提醒一下|安排一下|安排|建一个|创建一个|新增一个|新建一个|加一个|加个)(?:任务|日程|提醒|事项)?[,，:：\s]*/;

/** 主入口:把一句话拆成 {title, dueDate, dueTime},并从标题里抹掉日期/时间文字。 */
export function parseLocalTaskInput(raw: string, referenceDate: Date = new Date()): ParsedTask {
  const original = (raw || "").trim();
  if (!original) return { title: "", dueDate: null, dueTime: null };

  const dateHit = parseDate(original, referenceDate);
  const timeHit = parseTime(original);

  // 在归一化后的文本上抹除命中片段(命中片段来自归一化文本,中文数字已转阿拉伯)。
  let title = normalizeSpokenText(original);
  for (const span of [dateHit?.span, timeHit?.span]) {
    if (span && span.trim()) title = title.replace(span.trim(), " ");
  }
  // 清理:去前缀填充词、压空白、修剪标点
  title = title.replace(LEADING_FILLER, "");
  title = title.replace(/\s+/g, " ").trim();
  title = title.replace(/^[,，。、:：;；·•\-—~\s]+|[,，。、:：;；·•\-—~\s]+$/g, "").trim();
  // 常见连接词残留(如"明天 和 X 开会"去掉日期后剩"和 X 开会")
  title = title.replace(/^(?:和|与|跟|在|于|去|到)[\s,，]*/, "").trim();

  return {
    title: title || original,
    dueDate: dateHit?.dateKey ?? null,
    dueTime: timeHit?.time ?? null,
  };
}
