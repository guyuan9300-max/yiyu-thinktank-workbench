// ============================================================
// 批量任务确定性解析器 (batch task import · deterministic parse)
//
// 设计origin: execute+1 收敛 —— 用户粘贴的清单是半结构化的
//   "日期头行 + 标题行 + 描述段", 每条以 M/D 日期开头。
// 关键: 全程确定性 (正则), 不依赖 LLM/组织AI —— 组织AI 502 时也能跑通。
//   日期解析规则已在真实清单上实测 10/10 命中 (含区间取起止、相对词忽略)。
//
// 输出交给 BatchTaskImportPanel 渲染成可编辑预览表, 用户确认后逐条 createTask。
// ============================================================

export interface ParsedBatchTask {
  /** React key 用的临时本地 id (非任务 id)。 */
  localId: string;
  /** 原始日期头行, 供预览表溯源展示。 */
  dateLine: string;
  /** 起始日期 'YYYY-MM-DD'; 解析失败为 null (预览表会标红让用户补)。 */
  startDate: string | null;
  /** 区间结束日期 'YYYY-MM-DD'; 单日任务为 null。 */
  endDate: string | null;
  /** 'HH:MM' 时间提示 (今晚→20:00 / 明天中午→12:00 / 周三早上→09:00); 无则 ''。 */
  dueTime: string;
  /** 任务标题。 */
  title: string;
  /** 任务描述/背景。 */
  desc: string;
  /** 负责人姓名(原文, 未解析成 id); 无则 undefined。 */
  ownerName?: string;
  /** 协作者姓名列表(原文); 无则空数组。 */
  collaboratorNames: string[];
  /** 事件线名称(原文); 无则 undefined。 */
  eventLineName?: string;
  /** 客户/项目名称(原文); 无则 undefined。 */
  clientName?: string;
  /** 优先级; 无则 undefined(落库按 normal)。 */
  priority?: 'low' | 'normal' | 'high';
  /** 用户可在预览表取消勾选以跳过该条; 默认 true。 */
  include: boolean;
}

// M/D (可选 /YYYY) —— 与后端 time_anchor_normalizer 同源正则思路。
const SLASH_RE = /(\d{1,2})\/(\d{1,2})(?:\/(\d{4}))?/g;
// 日期头行: 以 M/D 开头 (允许前导空白)。
const DATE_HEADER_RE = /^\s*\d{1,2}\/\d{1,2}/;
// 从日期头行剥掉日期 token 后剩下的"注解/内联标题"。
const LEADING_DATE_RE = /^\s*\d{1,2}\/\d{1,2}(?:\s*[—\-~～]\s*\d{1,2}\/\d{1,2})?\s*/;

// 相对时间 → 时间提示 (仅作 dueTime 猜测, 不影响日期; 日期永远取显式 M/D)。
const TIME_HINTS: Array<[RegExp, string]> = [
  [/中午/, '12:00'],
  [/早上|早晨|上午/, '09:00'],
  [/下午/, '15:00'],
  [/傍晚|黄昏/, '18:00'],
  [/晚上|今晚|夜里/, '20:00'],
];

/** 日期头行剥掉日期后, 剩余文本是否只是"相对注解"(今天/明天中午/周三早上…) 而非标题。 */
function isAnnotationOnly(leftover: string): boolean {
  const t = leftover.trim();
  if (!t) return true;
  // 真标题通常 > 6 字 (如"整理给汇丰的资源诉求清单"=12);
  // 相对注解都很短 (今天/今晚=2, 明天中午/周三早上/周三会后=4, 周一前=3)。
  return t.length <= 6;
}

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

function toIso(month: number, day: number, year: number): string | null {
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  return `${year}-${pad2(month)}-${pad2(day)}`;
}

function inferDueTime(dateLine: string): string {
  for (const [re, time] of TIME_HINTS) {
    if (re.test(dateLine)) return time;
  }
  return '';
}

/** 从一段文字里抓 M/D → {起始, 结束}; 起止相同视为单日(结束=null)。 */
function extractDates(text: string, defaultYear: number): { startDate: string | null; endDate: string | null } {
  const matches = [...text.matchAll(SLASH_RE)];
  let startDate: string | null = null;
  let endDate: string | null = null;
  if (matches.length >= 1) {
    const [, mo, d, y] = matches[0];
    startDate = toIso(Number(mo), Number(d), y ? Number(y) : defaultYear);
  }
  if (matches.length >= 2) {
    const [, mo, d, y] = matches[1];
    endDate = toIso(Number(mo), Number(d), y ? Number(y) : defaultYear);
  }
  if (endDate && endDate === startDate) endDate = null;
  return { startDate, endDate };
}

function mapPriority(v?: string): 'low' | 'normal' | 'high' | undefined {
  if (!v) return undefined;
  if (/高/.test(v)) return 'high';
  if (/低/.test(v)) return 'low';
  if (/中|普通|正常/.test(v)) return 'normal';
  return undefined;
}

// ── 标签块格式(负责人/协作者/事件线/客户/优先级/背景) ──
// 标签 → 字段。同义标签都映射到同一字段。
const FIELD_LABELS: Record<string, 'title' | 'date' | 'owner' | 'collaborators' | 'eventLine' | 'client' | 'priority' | 'desc'> = {
  标题: 'title', 名称: 'title',
  日期: 'date', 时间: 'date',
  负责人: 'owner', 主责: 'owner',
  协作者: 'collaborators', 协作: 'collaborators', 参与人: 'collaborators',
  事件线: 'eventLine',
  客户: 'client', '客户/项目': 'client', 项目: 'client',
  优先级: 'priority',
  背景: 'desc', 描述: 'desc', 说明: 'desc',
};
// 行首 "标签：值"(中英文冒号)。标签限中英文/斜杠, 1–8 字, 避免误伤正文里的冒号句。
const LABEL_LINE_RE = /^\s*([一-龥A-Za-z/]{1,8})\s*[:：]\s*(.*)$/;

/** 整段是否为标签块格式(出现"标题："或"日期："即判定)。 */
function isLabeledFormat(raw: string): boolean {
  return /(^|\n)\s*(标题|日期)\s*[:：]/.test(raw);
}

function splitByComma(v?: string): string[] {
  return (v || '').split(/[、,，;；\/]/).map((s) => s.trim()).filter(Boolean);
}

/** 解析单个标签块 → ParsedBatchTask。背景可跨多行(下一标签前的行都并入)。 */
function parseLabeledBlock(block: string, index: number, defaultYear: number): ParsedBatchTask {
  const fields: Partial<Record<string, string>> = {};
  let curKey: string | null = null;
  for (const line of block.split(/\r?\n/)) {
    const m = line.match(LABEL_LINE_RE);
    const key = m ? FIELD_LABELS[m[1].trim()] : undefined;
    if (key) {
      fields[key] = m![2].trim();
      curKey = key;
    } else if (curKey && line.trim()) {
      fields[curKey] = `${fields[curKey] ? `${fields[curKey]} ` : ''}${line.trim()}`;
    }
  }
  const dateStr = fields.date || '';
  const { startDate, endDate } = extractDates(dateStr, defaultYear);
  return {
    localId: `batch-${index}-${startDate || 'nodate'}`,
    dateLine: dateStr,
    startDate,
    endDate,
    dueTime: inferDueTime(dateStr),
    title: (fields.title || '').trim(),
    desc: (fields.desc || '').trim(),
    ownerName: fields.owner?.trim() || undefined,
    collaboratorNames: splitByComma(fields.collaborators),
    eventLineName: fields.eventLine?.trim() || undefined,
    clientName: fields.client?.trim() || undefined,
    priority: mapPriority(fields.priority),
    include: true,
  };
}

interface RawBlock {
  dateLine: string;
  inlineTitle: string; // 日期头行内联标题 (单行格式); 多行格式为 ''
  restLines: string[];
}

/**
 * 把粘贴的整段文字按"日期头行"切成块。
 * 支持两种格式:
 *   多行:  "7/1 今天" \n "标题" \n "描述..."
 *   单行:  "7/2—7/3 赛夫提交第一轮选品建议：让赛夫..." (日期后直接跟长标题)
 */
function splitIntoBlocks(raw: string): RawBlock[] {
  const blocks: RawBlock[] = [];
  let cur: RawBlock | null = null;
  for (const line of raw.split(/\r?\n/)) {
    const s = line.trim();
    if (!s) continue;
    if (DATE_HEADER_RE.test(s)) {
      if (cur) blocks.push(cur);
      const leftover = s.replace(LEADING_DATE_RE, '').trim();
      cur = {
        dateLine: s,
        inlineTitle: isAnnotationOnly(leftover) ? '' : leftover,
        restLines: [],
      };
    } else if (cur) {
      cur.restLines.push(s);
    }
    // 若还没遇到任何日期头行就出现正文, 直接丢弃 (无法归属)。
  }
  if (cur) blocks.push(cur);
  return blocks;
}

/**
 * 确定性解析批量任务清单。纯函数, 无副作用、无网络。
 * @param raw 用户粘贴的整段文字
 * @param defaultYear 无显式年份时默认年 (默认取当前年)
 */
export function parseBatchTasks(
  raw: string,
  defaultYear: number = new Date().getFullYear(),
): ParsedBatchTask[] {
  if (!raw || typeof raw !== 'string') return [];
  // 标签块格式(标题：/日期：/负责人：…): 按空行切块, 逐块解析。
  if (isLabeledFormat(raw)) {
    return raw
      .split(/\r?\n\s*\r?\n+/)
      .map((b) => b.trim())
      .filter((b) => b && LABEL_LINE_RE.test(b.split(/\r?\n/)[0] || ''))
      .map((b, i) => parseLabeledBlock(b, i, defaultYear));
  }

  // 旧位置式格式(日期头行 + 标题 + 描述): 保留, 向后兼容。
  const blocks = splitIntoBlocks(raw);
  const tasks: ParsedBatchTask[] = [];

  blocks.forEach((block, index) => {
    // 从日期头行抓所有 M/D → 第一个=起, 第二个=止 (区间)。
    const matches = [...block.dateLine.matchAll(SLASH_RE)];
    let startDate: string | null = null;
    let endDate: string | null = null;
    if (matches.length >= 1) {
      const [, mo, d, y] = matches[0];
      startDate = toIso(Number(mo), Number(d), y ? Number(y) : defaultYear);
    }
    if (matches.length >= 2) {
      const [, mo, d, y] = matches[1];
      endDate = toIso(Number(mo), Number(d), y ? Number(y) : defaultYear);
    }
    // 起止相同视为单日。
    if (endDate && endDate === startDate) endDate = null;

    // 标题: 单行格式用内联标题; 否则取第一条正文行。
    const rawTitle = block.inlineTitle || block.restLines[0] || '';
    // 描述: 内联标题格式 → 全部正文行; 多行格式 → 第一条以外的正文行。
    const rawDesc = block.inlineTitle
      ? block.restLines.join(' ')
      : block.restLines.slice(1).join(' ');

    let title = rawTitle.trim();
    let desc = rawDesc.trim();
    // 单行 "标题：描述": 无独立描述且标题含全角/半角冒号 → 按首个冒号切开。
    if (!desc && /[：:]/.test(title)) {
      const idx = title.search(/[：:]/);
      desc = title.slice(idx + 1).trim();
      title = title.slice(0, idx).trim();
    }

    tasks.push({
      localId: `batch-${index}-${startDate || 'nodate'}`,
      dateLine: block.dateLine,
      startDate,
      endDate,
      dueTime: inferDueTime(block.dateLine),
      title,
      desc,
      collaboratorNames: [],
      include: true,
    });
  });

  return tasks;
}
