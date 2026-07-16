// ============================================================
// 批量任务 名字→id 解析 (graceful)
//
// 设计origin: 排查+1 定案 —— 能对上的自动关联, 对不上的落背景文本, 事后手动补。
// 关键约束(排查+1 一手证据):
//   · 成员必须用 mirror_users/mention-candidates 源的 id(emp_/user_), 不能用 operators(op_)——
//     同一人有多套 id, 对错源=坏链接。这里只匹配调用方传入的 members(来自 getMentionCandidates)。
//   · 客户/事件线用本地 clients/event_lines, id 命名空间一致。
//   · 全部本地匹配, 不依赖云(离线可用)。
// ============================================================

import type { ParsedBatchTask } from '../../shared/batchTaskParse';

export interface NamedRef {
  id: string;
  name: string;
}

export interface BatchDirectories {
  clients: Array<{ id: string; name: string }>;
  eventLines: Array<{ id: string; name: string; status?: string }>;
  /** 来自 getMentionCandidates: { id(emp_/user_), fullName }。 */
  members: Array<{ id: string; fullName: string }>;
}

export interface ResolvedBatchTask {
  parsed: ParsedBatchTask;
  clientId: string | null;
  clientMatched: string | null;
  /** 命中的已有事件线 id。 */
  eventLineId: string | null;
  /** 未命中但用户写了名字；默认不新建，交由预览页明确确认。 */
  eventLineUnmatchedName: string | null;
  ownerId: string | null;
  ownerMatched: string | null;
  collaborators: NamedRef[];
  /** 匹配不到的人名(负责人/协作者), 落库时并进背景。 */
  unmatchedPeople: string[];
}

function normalizePersonName(s: string): string {
  // 归一化: 去空白、小写、去掉常见括注(如"庆华（AI）"→"庆华")。
  return s
    .trim()
    .toLowerCase()
    .replace(/[（(【\[].*?[)）】\]]/g, '')
    .replace(/\s+/g, '');
}

function normalizeStrictReferenceName(s: string): string {
  // 客户/事件线括注可能代表期次或版本，必须保留，避免“一期”误配“二期”。
  return s.trim().toLowerCase().replace(/\s+/g, '');
}

/** 批量导入只允许复用仍在进行中的事件线。 */
export function isBatchReusableEventLineStatus(status?: string): boolean {
  return status !== 'archived' && status !== 'done';
}

/**
 * 只做精确匹配(归一化后相等)。
 * 排查+1 定案: 双向包含会误配(负责人"李伟"→"李伟明"指派错人 / 事件线"715上线"→"上线"挂错线)。
 * 宁可匹配不到走 graceful 降级(人/事件线名称落背景), 也绝不静默误关联。
 */
function matchByName<T>(
  name: string,
  list: T[],
  getName: (t: T) => string,
  normalize: (value: string) => string,
): T | null {
  const n = normalize(name);
  if (!n) return null;
  return list.find((x) => normalize(getName(x)) === n) || null;
}

/** 把一条解析后的任务, 依据本地名册解析成 id(纯函数)。 */
export function resolveBatchTask(task: ParsedBatchTask, dirs: BatchDirectories): ResolvedBatchTask {
  // 客户
  const client = task.clientName
    ? matchByName(task.clientName, dirs.clients, (c) => c.name, normalizeStrictReferenceName)
    : null;

  // 事件线: 命中已有 → id; 有名字但没命中 → 记为未匹配，绝不在这里自动新建。
  const reusableEventLines = dirs.eventLines.filter((eventLine) => isBatchReusableEventLineStatus(eventLine.status));
  const el = task.eventLineName
    ? matchByName(task.eventLineName, reusableEventLines, (e) => e.name, normalizeStrictReferenceName)
    : null;
  const eventLineUnmatchedName = task.eventLineName && !el ? task.eventLineName : null;

  // 负责人
  const unmatchedPeople: string[] = [];
  let ownerId: string | null = null;
  let ownerMatched: string | null = null;
  if (task.ownerName) {
    const m = matchByName(task.ownerName, dirs.members, (u) => u.fullName, normalizePersonName);
    if (m) {
      ownerId = m.id;
      ownerMatched = m.fullName;
    } else {
      unmatchedPeople.push(task.ownerName);
    }
  }

  // 协作者
  const collaborators: NamedRef[] = [];
  for (const name of task.collaboratorNames) {
    const m = matchByName(name, dirs.members, (u) => u.fullName, normalizePersonName);
    if (m && m.id !== ownerId) {
      collaborators.push({ id: m.id, name: m.fullName });
    } else if (!m) {
      unmatchedPeople.push(name);
    }
  }

  return {
    parsed: task,
    clientId: client?.id ?? null,
    clientMatched: client?.name ?? null,
    eventLineId: el?.id ?? null,
    eventLineUnmatchedName,
    ownerId,
    ownerMatched,
    collaborators,
    unmatchedPeople,
  };
}

/** 把匹配不到的人名并进背景文本(graceful fallback)。 */
export function appendUnmatchedToDesc(desc: string, unmatched: string[]): string {
  if (!unmatched.length) return desc;
  const note = `相关人员（未关联，可事后手动指派）：${unmatched.join('、')}`;
  return desc ? `${desc}\n\n${note}` : note;
}
