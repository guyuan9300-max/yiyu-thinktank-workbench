# v0.3.4 RC 运行与价值证明手册

本手册只覆盖当前阶段的两件事：

1. 证明主链接管在真实环境里稳定
2. 把这轮修缮的变化证明给团队和业务同事看

当前仍然不扩功能，不接本地 `70B / Derived Sync / Internal Control Plane / Paperclip`。
本轮 `mobile` 完全 out of scope，不进入任何 RC 判断、baseline、Wave 2 或 value-proof 结论。

本轮唯一目标写死为：证明 `installed-runtime` 下的主链接管，可以稳定进入 `Day 0 / Wave 2`，而不是把所有 full smoke 打绿。

本轮 RC 固定定义为 `installed-runtime RC`：

- `47829` 必须由安装版 app 这条真实运行链拉起
- 如果需要手动拉 packaged backend 才能继续，只记为 `blockerClass=packaging`
- 这轮要证明的是 `安装版 + 47829 + 当前 renderer/main 资产` 能稳定承载主链接管，而不是“源码版能跑”
- `packaging pass != A0 pass`：安装链恢复只代表允许回到 `A0`，不代表 RC 已恢复
- `install-receipt.json + install-smoke.json` 是恢复 RC 主流程的前置证据
- `invalidated-artifacts.note.json` 是旧 baseline / Day 0 / Wave 2 / install-step 证据失效的唯一口径

## 当前阶段判断

- `架构修缮`：主体已完成
- `运行证明`：Wave 1 已通过，Wave 2 待完成
- `用户可感知价值`：待补安装版闭环、4 个场景验证与业务反馈

当前执行顺序固定为：

1. 安装版闭环 Step A0
2. 固定 gate 复核
3. full smoke 分层刷新
4. 原子重生单一基线文件
5. 安装版闭环 Step A1
6. Wave 2 Day 0 预热
7. Wave 2 正式观察
8. 安装版闭环 Step B
9. 4 个用户场景价值验证
10. 输出一页对照结论

## 缺口补跑策略

这轮默认按“缺口补跑”执行，不先整链从头重放：

- 先复用 `~/Library/Application Support/YiyuThinkTankWorkbench/runtime/main-chain-rc/v0.3.4/` 里的现有产物作为暂存现场
- 第一轮只补跑 3 件事：
  - `db-isolation-check.json`
  - `full-smoke-classification.json`
  - 现有 `rc-baseline.json / install-step-a.json / wave2-day0.json` 是否满足新增硬门禁
- 只有命中下面任一项，才回退到更早阶段重放：
  - `db-isolation-check.json.readyForBaselineRegeneration=false`
  - `full-smoke-classification.json.canRegenerateBaseline=false`
  - 身份元组变化：`buildVersion / rendererEntry / databasePath / latestJudgmentsShadowOff / backendStartedByInstalledApp`
  - 现有 `Step A` 证据显示曾依赖手动 backend 或额外 workaround

## 冻结纪律

从现在开始到 Wave 2 结束，固定按 RC 冻结期执行：

- 除直接 blocker 外，不再改代码
- 直接 blocker 只指以下 4 类：
  - 阻止 `47829` 恢复
  - 阻止安装版 Step A / Step B 取证
  - 阻止 Day 0 预检
  - 会让 Day 0 / Wave 2 结论失真的问题
- `mobile` 不纳入本轮 RC 判断、baseline、Wave 2、Step A / Step B 或 value-proof

Wave 2 的所有结论都绑定到同一份身份元组：

- `commitSha`
- `backendUrl`
- `buildVersion`
- `databasePath`
- `latestJudgmentsShadowOff`
- `dirtyWorktree / dirtyPaths`
- `installedRuntimeSignature.appBundleMTime`
- `installedRuntimeSignature.rendererEntry`
- `installedRuntimeSignature.backendStartedByInstalledApp`

其中 `installedRuntimeSignature.backendPid` 只作为诊断字段留档，不参与 identity gate。

只要身份元组任一项变化，当前 Wave 2 记录立即作废：

1. 重新生成 `output/main-chain/rc-baseline.json`
2. 重新从 Day 0 开始

## 固定 gate

进入 Day 0 前，先复跑：

- `.venv/bin/python -m pytest -q tests/test_analysis_main_chain.py`
- `.venv/bin/python -m pytest -q tests/test_knowledge_v2.py`
- `.venv/bin/python -m pytest -q tests/test_api_smoke.py -k "strategic_cockpit or workspace_import_builds_document_cards_and_knowledge_status or workspace_import_auto_generates_client_dna_candidates or main_chain_canary_closes_import_analysis_approval_and_cockpit"`
- `npm run build:main`
- `npm run build:renderer`

如果固定 gate 任一失败，先停在这里，只允许修直接 blocker。

## 基线重生原子纪律

`rc-baseline.json` 只能在同一轮连续动作里重生：

1. `capture-git-artifacts`
2. fixed gate 全绿
3. `db-isolation-check.json.readyForBaselineRegeneration=true`
4. live full smoke 跑完，并产出 `full-smoke-classification.json`
5. 立刻生成新的 `output/main-chain/rc-baseline.json`

中间不允许切环境、重启 app、改配置，也不允许把其他动作插在第 2 步和第 5 步之间。
若无法证明 pytest / smoke 与 installed-runtime 当前数据库隔离，则不得执行 `freeze-baseline`。

## 统一工具与目录

阶段 A / Day 0 / Wave 2 统一使用：

- [backend/scripts/main_chain_canary.py](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend/scripts/main_chain_canary.py)
- [backend/scripts/main_chain_rc_ops.py](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend/scripts/main_chain_rc_ops.py)
- [docs/main-chain-value-proof-manual-template.json](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/docs/main-chain-value-proof-manual-template.json)

单一基线文件固定写到：

- `output/main-chain/rc-baseline.json`

运行期外部证据目录固定为：

- `~/Library/Application Support/YiyuThinkTankWorkbench/runtime/main-chain-rc/v0.3.4/`

本轮唯一 backend：

- `http://127.0.0.1:47829`

固定环境变量：

- `YIYU_BACKEND_URL=http://127.0.0.1:47829`

本轮阶段 A / Day 0 / Wave 2 / 安装版闭环 / value-proof 只接受 `47829` 上产生的结果。
来自其他 backend 的结果，不纳入本轮 RC 结论。

## 常用命令

先准备外部目录：

```bash
export YIYU_BACKEND_URL=http://127.0.0.1:47829
export RC_DIR="$HOME/Library/Application Support/YiyuThinkTankWorkbench/runtime/main-chain-rc/v0.3.4"
mkdir -p "$RC_DIR"
cp docs/main-chain-value-proof-manual-template.json "$RC_DIR/value-proof-manual.json"
```

固化本轮代码差异：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_rc_ops.py capture-git-artifacts --runtime-dir "$RC_DIR"
```

记录旧证据作废说明：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_rc_ops.py write-invalidated-artifacts-note \
  --runtime-dir "$RC_DIR" \
  --baseline ../output/main-chain/rc-baseline.json \
  --output "$RC_DIR/invalidated-artifacts.note.json"
```

执行正式安装并生成安装收据：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench
npm run dist:mac-local
node scripts/install-mac-app.mjs dist/mac-arm64/益语智库自用平台.app --receipt "$RC_DIR/install-receipt.json"
```

执行安装后最小冒烟：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench
node scripts/check-installed-runtime.mjs \
  --source-app dist/mac-arm64/益语智库自用平台.app \
  --base-url http://127.0.0.1:47829 \
  --output "$RC_DIR/install-smoke.json"
```

验证 pytest / smoke 与 installed-runtime 数据隔离：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_rc_ops.py verify-db-isolation \
  --output "$RC_DIR/db-isolation-check.json"
```

`db-isolation-check.json` 固定回答：

- live backend 当前 `databasePath` 是什么
- 它是否仍指向 installed-runtime 的 `~/Library/Application Support/YiyuThinkTankWorkbench/app.db`
- `backend/tests/test_api_smoke.py` 与 `test_analysis_main_chain.py` 是否静态证明走 `create_app(tmp_path / "data")`
- 当前测试集中是否存在 `Database(tmp_path / "app.db")` 的临时库证据
- `readyForBaselineRegeneration`

把 full smoke 归类结果收敛成正式 artifact：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_rc_ops.py write-full-smoke-classification \
  --source "$RC_DIR/full-smoke-classification.json" \
  --log "$RC_DIR/full-smoke.log" \
  --output "$RC_DIR/full-smoke-classification.json"
```

`full-smoke-classification.json` 固定字段：

- `fullSmokeSummary`
- `failures`
- `rcBlockingFailures`
- `inheritedFailures`
- `classificationReason`
- `canRegenerateBaseline`

冻结 RC 基线文件：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_canary.py freeze-baseline \
  --fixed-gate-status <pass_or_fail> \
  --full-smoke-summary "<latest_full_smoke_summary>" \
  --a-class-count <current_a_class_count> \
  --b-class-summary "<b_class_cluster_1>" \
  --b-class-summary "<b_class_cluster_2>" \
  --c-class-summary "<c_class_cluster_1>" \
  --output ../output/main-chain/rc-baseline.json
```

执行 Day 0 前预检：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_rc_ops.py preflight \
  --baseline ../output/main-chain/rc-baseline.json \
  --output "$RC_DIR/day0-preflight.json"
```

评估 Day 0 客户与 control client：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_rc_ops.py select-day0 \
  --baseline ../output/main-chain/rc-baseline.json \
  --output "$RC_DIR/day0-selection.json"
```

给 Day 0 候选写入选 / 淘汰理由：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_rc_ops.py write-selection-note \
  --baseline ../output/main-chain/rc-baseline.json \
  --selection "$RC_DIR/day0-selection.json" \
  --output "$RC_DIR/day0-selection.note.json"
```

`day0-selection.note.json` 固定记录：

- 每个候选客户 `selected: true|false`
- 对应的入选 / 淘汰理由
- `healthReason`
- `representationReason`
- `controlClientId`
- `controlClientReason`

记录当前基线快照：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_canary.py snapshot --output "$RC_DIR/wave2-before.json"
```

执行 Wave 2 Day 0 预热：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_canary.py wave2-day0 \
  --client-id <client_id_1> \
  --client-id <client_id_2> \
  --client-id <client_id_3> \
  --batch-size 1 \
  --max-jobs 1 \
  --output "$RC_DIR/wave2-day0.json"
```

给 Day 0 / 每日 observation 写 sidecar note：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_rc_ops.py write-note \
  --baseline ../output/main-chain/rc-baseline.json \
  --observation "$RC_DIR/wave2-day0.json" \
  --control-client-id <control_client_id> \
  --operator-note "填写一句最关键的人类判断。"
```

记录 Wave 2 每日 observation：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_canary.py record-observation \
  --before "$RC_DIR/wave2-day1-before.json" \
  --time-range "Wave 2 / Day 1" \
  --client-count 3 \
  --enqueued-jobs 3 \
  --completed-jobs 3 \
  --failed-jobs 0 \
  --verdict watch \
  --conclusion "指标稳定，继续观察" \
  --output "$RC_DIR/wave2-day1.json"
```

记录安装版 Step A / Step B 证据：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_rc_ops.py write-install-evidence \
  --baseline ../output/main-chain/rc-baseline.json \
  --phase step-a \
  --status pass \
  --app-starts \
  --backend-started-by-installed-app \
  --overview-panel-visible \
  --shadow-off-parity \
  --workspace-boundary-correct \
  --cockpit-official-layer-tone-correct \
  --overview-metrics-populated \
  --overview-screenshot "$RC_DIR/screens/overview.png" \
  --workspace-screenshot "$RC_DIR/screens/workspace.png" \
  --cockpit-screenshot "$RC_DIR/screens/cockpit.png" \
  --summary "填写安装版验证结论。" \
  --output "$RC_DIR/install-step-a.json"
```

记录安装版 Step A / Step B blocker 归因：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_rc_ops.py write-install-note \
  --baseline ../output/main-chain/rc-baseline.json \
  --phase step-a \
  --blocker-class none \
  --decision pass \
  --reason "安装版已通过 Step A。" \
  --evidence "$RC_DIR/install-step-a.json" \
  --output "$RC_DIR/install-step-a.note.json"
```

生成一页价值证明结论：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_canary.py render-value-proof \
  --observation "$RC_DIR/wave2-day3.json" \
  --manual "$RC_DIR/value-proof-manual.json" \
  --output "$RC_DIR/value-proof.md"
```

写阶段 B 决策文件：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend
uv run python scripts/main_chain_rc_ops.py write-phase-b-decision \
  --observation "$RC_DIR/wave2-day3.json" \
  --manual "$RC_DIR/value-proof-manual.json" \
  --blocker-class none \
  --output "$RC_DIR/phase-b-decision.json"
```

`phase-b-decision.json` 固定字段：

- `runCompletionStatus`
- `mainChainJudgmentStability`
- `allowEnterPhaseB`
- `conditionsMet`
- `blockingReasons`
- `blockerClass`

## 基线纪律

- runbook 不记录任何当前 smoke 数字或分类摘要
- 当前结果一律只看 `output/main-chain/rc-baseline.json`
- `full-smoke-classification.json` 是 baseline 前置硬门禁，不再只靠口头归类
- `fullSmoke.summary` 必须来自本轮现跑结果；除非明确写入 `fullSmokeSource = inherited_from_previous_baseline`，否则不允许沿用旧数字
- 需要确认的字段固定为：
  - `generatedAt`
  - `commitSha`
  - `backendUrl`
  - `buildVersion`
  - `databasePath`
  - `latestJudgmentsShadowOff`
  - `dirtyWorktree / dirtyPaths`
  - `installedRuntimeSignature`
  - `classification`
  - `mainChainStability`
  - `metrics`
- 任何身份元组变化，都先重新执行 `freeze-baseline` 刷新基线文件，再从 Day 0 重启

## 安装版闭环

安装版闭环必须分两步执行，不只看源码版。

### Step A：Day 0 前先过基础可用性

没有安装版证据，就不进入 Day 0。

Step A 固定拆成 `A0 + A1` 两段，但都只认安装版真实运行链。

`A0` 只回答一件事：

- 安装版启动时，`47829` 是否由 app 自己拉起，并且窗口内容能真正切到 `Settings -> Overview`

只有 `install-receipt.json` 显示 `rendererEntryMatch=true` 且 `install-smoke.json.readyToResumeA0=true`，才允许开始重新验证 `A0`。

如果 `A0` 需要手动拉 packaged backend 才能继续，则 `A0` 直接失败，并固定归因为 `blockerClass=packaging`。

Step A 总通过条件固定为以下 4 项全部成立：

1. 安装版能正常启动，不再白屏或卡初始化
2. `47829` 由安装版 app 这条链自行拉起，不依赖手动救活 runtime backend
3. `Settings -> Overview` 能看到稳定化面板
4. `latestJudgmentsShadowOff=true` 时，安装版的 `workspace / cockpit / Overview` 行为与源码版一致，并留档 3 张截图：`Overview`、`workspace`、`cockpit`

`Step A1` 的“一致”固定按 3 条判断，不凭肉眼印象：

- `workspaceBoundaryCorrect=true`：正式判断区不能由 candidate / fallback 冒充
- `cockpitOfficialLayerToneCorrect=true`：official layer 为空时，不输出正式结论语气
- `overviewMetricsPopulated=true`：稳定化面板关键指标都已正常显示，不是空壳

只要出现下面任一项，`Step A1` 都不能记 pass：

- 需要手动救活 backend
- 需要额外 workaround 才能继续
- `47829` 不是安装版自拉起

以上情况固定记为：

- `decision=fail`
- `blockerClass=packaging`

任一项不成立，即 Step A 未通过。

Step A 失败后，固定在 `install-step-a.note.json` 里归因：

- `packaging`：安装版白屏、入口失配、打包 / 分发链问题
- `main-chain`：shadow-off 后安装版与源码版主链行为不一致
- `none`：通过，无 blocker

### Step B：固定在 Day 1 或 Day 2 做 shadow-off 对照

固定对同一 control client 做：

- 源码版对照
- 安装版对照
- `latestJudgmentsShadowOff=true`

只要安装版和源码版行为不一致，本轮运行证明就不算通过。

## Day 0 前检查单

进入 `wave2-day0` 前，固定检查：

1. `GET /api/v1/settings/main-chain-stability` 正常返回
2. `GET /api/v1/runtime/analysis-migration-metrics` 正常返回
3. `latestJudgmentsShadowOff=true`
4. `backfillPaused=false`
5. 当前环境的 `commitSha / backendUrl / buildVersion / databasePath / latestJudgmentsShadowOff / dirtyWorktree / dirtyPaths` 与最新 `rc-baseline.json` 一致
6. 安装版 Step A 已通过

任一项不一致，即不进入 Day 0，只允许修直接 blocker。

## Day 0 客户选择

Day 0 客户选择必须同时满足“健康”与“代表性”。

健康固定为：

- `workspace=200`
- `strategic-cockpit=200`
- `knowledgeReady=true`
- 上下文非空

代表性固定为：最终 `3` 个客户至少覆盖以下 `3` 类中的 `2` 类：

- 文档导入链较完整
- 会议 / 事件线推进痕迹明显
- cockpit 有可读历史或正式 / 候选层内容

固定优先顺序：

- `client_cffc`
- `client_a4d1db29a7`
- `client_53d82aa249`
- `client_284afd836e`
- `client_cb720fc373`

额外规则：

- `client_cffc` 只有在恢复 `47829` 后不再报错时才可入选
- 若不足 `3` 个健康且有代表性的客户，停止，不硬跑 Day 0

## Control Client

从最终入选的 `3` 个客户里固定一个 control client，贯穿 Day 0 到 Day 3 / Day 7。

control client 的用途固定为：

- workspace 对照客户
- cockpit 对照客户
- 安装版 / 源码版对照客户

默认优先级：

- `client_cffc`
- `client_a4d1db29a7`
- `client_284afd836e`
- `client_53d82aa249`

一旦选定，整个 Wave 2 不更换。

## Wave 2 Day 0 预热

Day 0 不是正式观察第 1 天，而是“预热与资格判定日”。

Day 0 只回答这 4 件事：

1. 关闭旧结果通道后，没有隐藏依赖
2. 同一 snapshot 重跑不会让主链对象膨胀或漂移
3. 极小真实 backfill 能完成
4. backfill 不会抢占 `interactive / system`

固定范围：

- `3` 个客户
- 先 dry-run
- 再跑 `1` 轮真实 `client` 级 `strategy_pack + client_overview`
- 全程 `latestJudgmentsShadowOff=true`
- 每个客户至少 `1` 次同 snapshot 重跑
- 额外插入 `1` 次极小真实 backfill：只跑 `1` 个客户、`1` 次、用于验证 worker/backfill 真正被跑过
- 固定参数：`batch-size=1`、`max-jobs=1`
- Day 0 里的这次极小真实 backfill 是本轮唯一真实 backfill 验证；Day 1–Day 3 不再加码

Day 0 通过条件：

- `latestJudgmentsShadowOff=true` 无 hidden dependency
- `evidence_cards / theme_clusters / conflict_groups / open_questions` 不膨胀
- `baselineJudgment` 或 `selectedCandidate` 不无故换 id
- 极小真实 backfill 完成，且未观察到 backfill 明显抢占实时任务

Day 0 任一失败，即不进入 Wave 2 正式观察。

## Wave 2 正式观察

只有 Day 0 通过后才允许启动。

固定参数：

- 客户数：`3`
- 全程 `latestJudgmentsShadowOff=true`
- 首轮连续观察 `3` 天；只有 `Day 3` 仍是 `watch` 才延长到 `7` 天
- 每天至少 `1` 条 observation
- 每条 observation 都必须追加一个 `*.note.json` sidecar
- Day 1–Day 3 的趋势判断不回溯混入 Day 0 指标
- Day 1 / Day 2 / Day 3 同一天只允许一个“额外控制变量”变化

`*.note.json` 固定必填字段：

- `baselineGeneratedAt`
- `commitSha`
- `backendUrl`
- `buildVersion`
- `databasePath`
- `latestJudgmentsShadowOff`
- `dirtyWorktree`
- `dirtyPaths`
- `controlClientId`
- `operatorNote`

`operatorNote` 固定写一句话，记录当天最关键的人类判断。

正式观察要回答三类问题：

### 稳不稳

- `newObjectHitRate`
- `fallbackRate`
- `resolverMismatchRate`
- `approvalBacklog`
- `approvalLagHoursMedian`
- `interactive / system` 是否被 backfill 拖慢

注意：

- `approvalBacklog / approvalLagHoursMedian / candidateReviewWarningCount / candidateReviewOverdueCount / newCandidateUnreviewed24h`
- 均已排除 `main-chain-canary=true` 样本
- 本轮试跑产生的 canary 样本不计入日常审批积压指标

### 靠不靠谱

- `latestJudgmentsShadowOff=true` 后是否仍正常
- `knowledge/status` 是否继续独立于辅助 job
- `workspace / cockpit` 是否继续守住正式 / 待确认 / 提醒边界
- 同 snapshot 重跑后是否保持幂等

### 好不好用

- 业务同事能不能一眼看懂状态边界
- 不同事件线的任务输出是否明显更有差异
- 会议增强是否更能接住未决问题和变化点
- cockpit 是否不再把提醒冒充结论

## 4 个用户场景验证

固定只验证下面 4 个场景：

1. `客户工作台`
   - 能否一眼区分：正式结论、待确认判断、提醒和风险信号、当前运行状态
2. `任务 AI`
   - 同一客户下，不同事件线任务输出是否明显不同
3. `会议增强`
   - 是否稳定出现：决议、行动项、风险、未决问题、变化点
4. `战略 cockpit`
   - 无正式结论时，是否明确写“当前暂无已批准判断”，提醒区是否没有冒充结论

每个场景固定至少保留：

- `1` 张当前截图
- `1` 条“以前 vs 现在”的短对照文案
- `1` 条“仍不够好”的保留判断

建议让 `1–2` 位业务同事直接体验这 4 个场景，并填写模板中的反馈部分。

## 停机规则

以下任一命中即停机：

- `fallbackRate > 20%`
- `resolverMismatchRate > 10%`
- `latestJudgmentsShadowOff` 暴露隐藏消费者
- backfill 明显影响 `interactive / system`
- 任一 `A 类` 失败回潮

停机动作固定为：

1. 立刻把 `backfillPaused=true`
2. 停止 claim 新 backfill
3. 已 claim job 跑完
4. 中止 Wave 2
5. 只允许修直接对应的共享根因

## 一页对照结论

Wave 2 结束后，只输出一页结论，不再继续扩文档体系。

进入阶段 B 的判断优先级固定为：

1. `主链判断口径 = 稳定`
2. 安装版闭环通过
3. 4 个场景与业务反馈齐全
4. 再看指标是否足够好看

如果业务同事仍觉得 `cockpit / workspace / 任务 AI` 不是同一个系统在说话，即使指标漂亮，也不进入阶段 B。

职责边界固定为：

- `value-proof.md` 只回答“值不值得往下走”，不承载阶段门禁
- `phase-b-decision.json` 只回答“能不能往下走”，不承载价值叙事

固定要包含：

- `代码完成态：pass / fail`
- `运行完成态：pass / watch / fail`
- `主链判断口径：稳定 / 基本稳定 / 仍有漂移`
- 安装版闭环是否通过
- 是否允许继续合并后观察
- 是否允许进入 `v0.4`
- 进入阶段 B 的判断依据：满足了哪些条件，或仍卡在哪个 blocker / stop rule

同时固定对照 4 个场景：

- 客户工作台：以前 vs 现在
- 任务 AI：以前 vs 现在
- 会议增强：以前 vs 现在
- cockpit：以前 vs 现在

并附上 5 个人人看得懂的指标：

- 导入后多久可用
- 同 snapshot 重跑会不会越跑越乱
- 页面说法打架率
- 退回旧逻辑比例
- 待确认判断是否堆积

## 阶段切换

只有下面 4 件事同时满足，才允许进入 `v0.4 共享根因清扫`：

1. `运行完成态 = pass`
2. 安装版闭环通过
3. 4 个用户场景的价值变化已经被业务同事确认
4. 主链判断口径为 `稳定`

在此之前，不进入：

- `70B`
- `Derived Sync`
- `Internal Control Plane`
- `Paperclip`
