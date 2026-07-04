import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseBatchTasks } from './batchTaskParse';

const Y = 2026;

test('多行块: 日期头行 + 标题行 + 描述段', () => {
  const [t] = parseBatchTasks(
    '7/1 今天\n整理给汇丰的资源诉求清单\n明确要向汇丰争取什么：短信、邮件等。',
    Y,
  );
  assert.equal(t.startDate, '2026-07-01');
  assert.equal(t.endDate, null);
  assert.equal(t.title, '整理给汇丰的资源诉求清单');
  assert.ok(t.desc.startsWith('明确要向汇丰'));
});

test('区间日期 7/2—7/3 → start + end', () => {
  const [t] = parseBatchTasks('7/2—7/3\n赛夫提交选品建议\n描述', Y);
  assert.equal(t.startDate, '2026-07-02');
  assert.equal(t.endDate, '2026-07-03');
});

test('连字符区间 7/10-7/11 也识别', () => {
  const [t] = parseBatchTasks('7/10-7/11\n真实链路测试\nx', Y);
  assert.equal(t.startDate, '2026-07-10');
  assert.equal(t.endDate, '2026-07-11');
});

test('相对时间提示: 今晚→20:00 / 明天中午→12:00 / 周三早上→09:00', () => {
  assert.equal(parseBatchTasks('7/1 今晚\n标题\nx', Y)[0].dueTime, '20:00');
  assert.equal(parseBatchTasks('7/2 明天中午\n标题\nx', Y)[0].dueTime, '12:00');
  assert.equal(parseBatchTasks('7/8 周三早上\n标题\nx', Y)[0].dueTime, '09:00');
});

test('相对词不污染日期: 7/6 周一前 仍取 7/6, 无区间', () => {
  const [t] = parseBatchTasks('7/6 周一前\n现金补充支付进入P0\nx', Y);
  assert.equal(t.startDate, '2026-07-06');
  assert.equal(t.endDate, null);
});

test('单行 "日期 标题：描述" → 按冒号切标题/描述', () => {
  const [t] = parseBatchTasks('7/2—7/3 赛夫提交第一轮选品建议：让赛夫基于SKU筛选爆品。', Y);
  assert.equal(t.startDate, '2026-07-02');
  assert.equal(t.endDate, '2026-07-03');
  assert.equal(t.title, '赛夫提交第一轮选品建议');
  assert.equal(t.desc, '让赛夫基于SKU筛选爆品。');
});

test('起止相同视为单日 (endDate=null)', () => {
  const [t] = parseBatchTasks('7/5—7/5\n标题\nx', Y);
  assert.equal(t.startDate, '2026-07-05');
  assert.equal(t.endDate, null);
});

test('多条清单: 按日期头行正确切成多块', () => {
  const tasks = parseBatchTasks(
    '7/1 今天\nA\na描述\n7/2\nB\nb描述\n7/3—7/4\nC\nc描述',
    Y,
  );
  assert.equal(tasks.length, 3);
  assert.deepEqual(tasks.map((t) => t.title), ['A', 'B', 'C']);
  assert.equal(tasks[2].endDate, '2026-07-04');
});

test('日期头行前的游离正文被丢弃, 不误当任务', () => {
  const tasks = parseBatchTasks('随便一句没有日期的话\n7/1\n真任务\nx', Y);
  assert.equal(tasks.length, 1);
  assert.equal(tasks[0].title, '真任务');
});

test('空输入 → 空数组', () => {
  assert.equal(parseBatchTasks('', Y).length, 0);
  assert.equal(parseBatchTasks('   \n  \n', Y).length, 0);
});

test('描述里的 715 (无斜杠) 不被误当日期', () => {
  const [t] = parseBatchTasks('7/15\n新网站上线\n715是基础上线节点。', Y);
  assert.equal(t.startDate, '2026-07-15');
  assert.equal(t.desc, '715是基础上线节点。');
});

test('默认年份可覆盖', () => {
  assert.equal(parseBatchTasks('3/9\n标题\nx', 2027)[0].startDate, '2027-03-09');
});

// ── 标签块格式 ──
test('标签块: 全字段解析', () => {
  const raw = `标题：统一715新定位方案
日期：7/3
负责人：顾源源
协作者：保罗、Jack
事件线：715上线
客户：汇丰
优先级：高
背景：把715重新定位为内部福利内测。
核心口径是先跑通链路。`;
  const [t] = parseBatchTasks(raw, 2026);
  assert.equal(t.title, '统一715新定位方案');
  assert.equal(t.startDate, '2026-07-03');
  assert.equal(t.ownerName, '顾源源');
  assert.deepEqual(t.collaboratorNames, ['保罗', 'Jack']);
  assert.equal(t.eventLineName, '715上线');
  assert.equal(t.clientName, '汇丰');
  assert.equal(t.priority, 'high');
  assert.ok(t.desc.includes('内部福利内测') && t.desc.includes('跑通链路'), '背景应跨多行合并');
});

test('标签块: 多条按空行切块', () => {
  const raw = `标题：A\n日期：7/3\n负责人：顾源源\n背景：一\n\n标题：B\n日期：7/4—7/5\n优先级：低\n背景：二`;
  const tasks = parseBatchTasks(raw, 2026);
  assert.equal(tasks.length, 2);
  assert.equal(tasks[0].title, 'A');
  assert.equal(tasks[1].title, 'B');
  assert.equal(tasks[1].endDate, '2026-07-05');
  assert.equal(tasks[1].priority, 'low');
});

test('标签块: 缺省字段 → undefined/空数组', () => {
  const [t] = parseBatchTasks('标题：X\n日期：7/6\n背景：y', 2026);
  assert.equal(t.ownerName, undefined);
  assert.deepEqual(t.collaboratorNames, []);
  assert.equal(t.eventLineName, undefined);
  assert.equal(t.priority, undefined);
});

test('标签块: 相对时间提示仍生效', () => {
  const [t] = parseBatchTasks('标题：X\n日期：7/8 周三早上\n背景：y', 2026);
  assert.equal(t.dueTime, '09:00');
});

test('位置式旧格式仍向后兼容(有collaboratorNames空数组)', () => {
  const [t] = parseBatchTasks('7/3\n老格式任务\n描述', 2026);
  assert.equal(t.title, '老格式任务');
  assert.deepEqual(t.collaboratorNames, []);
});
