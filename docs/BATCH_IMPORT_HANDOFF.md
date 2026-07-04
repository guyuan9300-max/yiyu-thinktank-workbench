# 批量导入任务(AI 自动批量生成任务)· 交接文档

> 2026-07-04 交接给新会话/新同事。本文件是唯一入口, 读它即可接手。

---

## 0. 一句话

在"AI 工作指令"弹窗里新增**「批量导入」**入口: 用户粘贴一份**标签格式**的任务清单 → 确定性解析 → 把客户/事件线/负责人/协作者的**名字自动关联成 id**(对不上的落背景, 事后手动补) → 串行批量建任务。**全部逻辑层已验证通过, 未合并 main, 未进真机软件。**

---

## 1. 代码在哪

- **实验仓(git worktree)**: `~/openclaw/workspace/yiyu-batch-task-import`
- **分支**: `feat/batch-task-import`, 基线 HEAD = `147d72d`(主仓 `~/openclaw/workspace/yiyu-thinktank-workbench` main 的提交)
- **注意**: worktree 无独立 `node_modules`, 已软链主仓的(`ln -s …/yiyu-thinktank-workbench/node_modules node_modules`)。跑 tsc/测试前确认软链在。

### 改动文件(全加法, 1077 行, 0 删除)
| 文件 | 作用 |
|---|---|
| `src/shared/batchTaskParse.ts` | 确定性解析器: 标签块格式 + 旧位置式(向后兼容)。纯函数无网络。 |
| `src/shared/batchTaskParse.test.ts` | 解析器单测 17 条 |
| `src/renderer/lib/batchTaskResolve.ts` | 名字→id 解析(客户/事件线/成员), 精确匹配, 未命中落背景 |
| `src/renderer/lib/batchTaskResolve.test.ts` | 解析单测 7 条(含防误配回归) |
| `src/renderer/components/ai_command/BatchTaskImportPanel.tsx` | 批量面板: 粘贴→预览表(带解析 chips)→串行落库 |
| `src/renderer/components/ai_command/AICommandModal.tsx` | +38 行: 加"批量导入"入口按钮 + `batchMode` 早返回分支(单条 quick_task 路径零改动, 守 §M1) |
| `src/renderer/App.tsx` | +4 行: 挂载点传 taskLists/defaultListId/currentOwnerName/onBatchTasksCreated |

### 跑测试/类型检查
```bash
cd ~/openclaw/workspace/yiyu-batch-task-import
# 解析器/解析单测(用 node strip-types 直跑, 因 test 被 tsconfig 排除)
node --experimental-strip-types --test <(sed "s#'./batchTaskParse'#'$PWD/src/shared/batchTaskParse.ts'#" src/shared/batchTaskParse.test.ts)
# 渲染层类型检查
node_modules/.bin/tsc --noEmit -p tsconfig.json
```

---

## 2. 功能状态(已验证 / 待办)

### 已验证(全绿)
- 解析器 **17/17** 单测; 解析(名字→id) **7/7** 单测; 渲染层 **typecheck 0 错**。
- **副本后端集成实测通过**(对真库副本起 dev 后端 + 真实名册): 标签解析 → 客户"汇丰"命中本地 client_id → 事件线命中或新建(POST /event-lines) → `createTask` 带 clientId/eventLineId/priority → HTTP 200 持久化正确 → 未命中的人落背景。
- 真库零污染(所有测试在 `/tmp` 副本上做)。

### 待办(交接给你)
1. **Electron 界面点击验证**(唯一没跑的一层): 开面板→粘贴→看预览 chips→点建→看任务带负责人/事件线上日历。底下每层逻辑+后端已验证。
2. **协作者落库取回**live 确认(低风险, resolve 单测已证产出正确 id, 但没在副本实跑取回)。
3. **合并 main + 进真机软件**(等顾源源点头; 按 §5 纪律)。

### ★关键依赖(必须先懂)
**负责人/协作者的"自动关联"死死依赖云登录。** `GET /api/v1/employees/mention-candidates` 要登录态; 云会话空时返回 `401 Not authenticated` → 成员名册为空 → **所有人(含顾源源)都匹配不上、全落背景**。客户/事件线是本地表(clients/event_lines), 不受影响。
→ **先修云登录(见 §4), 重登后成员自动关联才生效。**

---

## 3. ★ AI 批量生成任务的填写要求(任务描述 · 贴给 AI 用)

> 把任务清单整理成下面的**标签块**格式。每条任务一块, 块之间空一行。字段用中文冒号, 没有的字段整行省略(不要写"无")。

```
标题：<8–20字的简短任务名>
日期：<M/D；跨天用 M/D—M/D；可加 上午/下午/晚上>
负责人：<1个名字>
协作者：<多个名字，用、或逗号分隔>
事件线：<所属事件线名称，如"715上线">
客户：<关联客户名，如"汇丰">
优先级：<高/普通/低>
背景：<3–5句：①目标(为什么做)②现状/最新变化③关键决策或口径④依赖/卡点⑤交付标准>
```

### 规则(务必告诉 AI)
1. **每条必须有 `标题` 和 `日期`**; 其余可省。
2. **名字要用系统里的准确名称**才能自动关联(如客户写"汇丰"不要写"汇丰银行"; 负责人写全名)。系统做**精确匹配**——不精确就不自动关联, 会把名字并进背景, 你事后手动补(这是刻意的安全设计, 避免指派错人/挂错事件线)。
3. **负责人/协作者只填内部同事**(在组织成员名册里的)。外部人(如 Terry、Maggie、汇丰的人)**写进背景**, 不要放进负责人/协作者。
4. **背景要写厚**——具体、可执行, 别一句话带过(这是之前的痛点)。
5. 日期永远带显式数字(`7/2`); "明天/周一前"这类相对词可写但必须同时有数字日期。

### 示例(一条)
```
标题：统一715新定位方案
日期：7/3
负责人：顾源源
事件线：715上线
客户：汇丰
优先级：高
背景：把715从"对外大促"重新定位为"汇丰内部福利内测+全链路拉通+内部共识激活"。核心口径：先让R+和汇丰员工真实体验会选，用数据反馈推动更大范围资源，不追求GMV。交付：形成统一对内对外口径一页纸，供向菲总/Maggie汇报复用。
```

### 解析行为(你要知道)
- `日期`: 单日 `7/3`→当天; 区间 `7/2—7/3`→日历上跨天条(自动补 09:00–18:00 工作时段)。
- `优先级`: 高→high / 中·普通→normal / 低→low。
- `事件线`: 系统里有同名→关联; 没有→**自动新建**该事件线。
- `客户`: 系统里有同名→关联; 没有→留空(不新建客户)。
- `负责人/协作者`: 名册里精确命中→关联(负责人写 ownerId, 其余写 collaboratorIds); 命中不了→名字并进背景("相关人员（未关联，可事后手动指派）：…")。

---

## 4. 关联问题: 云登录卡死 bug(0.25.0)+ 热补丁

批量导入的成员关联依赖云登录, 而**当前云登录是坏的**——已定位为一个发版回归 bug, 详见记忆 `project_yiyu_cloud_login_stuck_0_25_0_unauthenticated_bug`。

- **根因**: 安装的 `益语智库AI 0.25.0` 的 `backend/app/main.py` 里 `auth_me` 会话过期(401)兜底分支调用了**未定义的 `_unauthenticated`** → NameError→500(先 clear_cloud_session 清空 token)→ 两公司云卡死未登录。主仓源码 HEAD 本来有这个函数(main.py:31023)。
- **已做的热补丁**(2026-07-03): 已把内嵌 `def _unauthenticated`(返回 `AuthStateResponse(authenticated=False,…)`)补进安装包 `/Applications/益语智库AI.app/Contents/Resources/app/backend/app/main.py`, py_compile 通过。备份在同目录 `main.py.bak-unauth-fix-20260703`。
- **顾源源需做**: **Cmd+Q 完全退出软件重开**(加载补丁)→ **益语智库、星丛各重登一次云**。重登后 mention-candidates 通了, 成员自动关联才生效。

---

## 5. 关键设计约束 / 教训(排查+1 定案, 别推翻)

1. **成员 id 必须用 mirror_users / mention-candidates 源(emp_/user_)**, 不能用本地 `operators` 表(op_)——同一人有多套 id(顾源源=op_guyuan=user_guyuan=emp_55ab67ebf7), 对错源=坏链接。见 [[project_yiyu_growth_identity_namespace_2026_06_21]] 的"身份命名空间裂缝"。
2. **精确匹配, 不做模糊**——排查+1 实测: 双向包含会误配("715上线"→误挂已有"上线" / 负责人"李伟"→误指派"李伟明")。宁可落背景兜底, 绝不静默误关联。已用 7 条回归单测焊死。
3. **本地优先解析**: 客户/事件线/成员全读本地表, 离线可用(成员那条受云登录门禁限制)。零新后端接口、零 schema 改动。
4. **串行落库**(非并发): 避开 30 路并发的 `database is locked` + 建任务副作用尖峰(每建 1 条 fan-out 数据中心摄入/AI预计算/云同步后台线程)。副本压测 30/30 无锁。
5. **加法式不破坏单条 quick_task**(§M1: 顾源源"原智能建任务必须保留、可回滚")。`batchMode` 默认 false, 早返回分支, AICommandModal 0 删除。
6. **建任务 payload 契约**(副本实测过接受): `{title, desc, priority, listId(空则后端兜底"收集箱"), scopeMode:'COLLAB_SHARED', deadlineAt/scheduledStartAt/scheduledEndAt/dueDate/startDate, durationMinutes, ddl, clientId, eventLineId, ownerId, ownerName, collaboratorIds, tagIds, sourceType:'batch_import'}`。全天区间补 09:00–18:00 让日历画跨天条(软件不支持"多天全天")。

---

## 6. 怎么继续(建议顺序)
1. 顾源源先按 §4 重启+重登云(解锁成员关联)。
2. 你做 §2 待办的真机 UI 点击验证(可对真库副本起 dev 界面, 参照 §7 的副本起后端法)。
3. 无误后, 按主仓纪律合并到 main(见 `~/openclaw/workspace/yiyu-thinktank-workbench/CLAUDE.md`: main 是唯一真相源, 改完 fast-forward 合回, 从 main 构建部署)。
4. 顾源源填写要求已在 §3, 他可以先让 AI 把 715 清单按标签格式重列。

## 7. 副本起后端法(真机/集成测试用, 不碰真库)
```bash
DST=/tmp/yiyu-batch-verify; rm -rf $DST; mkdir -p $DST
cp ~/Library/Application\ Support/YiyuThinkTankWorkbench2/app.db* $DST/
cd ~/openclaw/workspace/yiyu-batch-task-import/backend
YIYU_WORKBENCH_DATA_DIR=$DST \
  ~/Library/Application\ Support/YiyuThinkTankWorkbench2/runtime/backend-venv/bin/python \
  -m uvicorn app.main:app --host 127.0.0.1 --port 47899 &
# 完事: kill 掉 47899 的进程 + rm -rf $DST。真库后端在 47829, 别动。
```
