# 益语软件平台源码导出（第009卷）

- 导出时间: 2026-04-20 18:08:04
- 内容范围: 主仓库源码 + mobile 子仓库源码
- 说明: 每个条目为完整源码文件。

## `mobile/scripts/mobile-blocker-ledger.md`

- 编码: `utf-8`

~~~markdown
# Mobile Stability Blocker Ledger

Use this as a lightweight run log for Android RC scans and PR re-scans.

## Run Metadata

- Date: 2026-04-18
- Branch: main
- Build commit: bb64401746c436ebf5284980ce26882a6ac78d21
- Build type: release (RC)
- APK path: android/app/build/outputs/apk/release/app-release.apk
- APK timestamp: 2026-04-18 16:47:24 +0800
- Device ID: not detected
- Device model: unknown
- Android version: unknown
- Network type: pending device attach
- Battery / low-power mode: pending device attach
- Device state: ADB server up, no `device` in `adb devices -l`
- Tester: Codex + user
- Additional env notes:
  - Local JDK 17 installed at `/Users/guyuanyuan/.local/jdks/temurin17/Contents/Home`
  - Build uses `ANDROID_HOME=/Users/guyuanyuan/Library/Android/sdk`

## Automated Gates

- `npx tsc --noEmit`: PASS (via `verify:rc-android` preflight)
- `npm run test:core`: PASS (60/60)
- `npm run verify:rc-android`: BLOCKED (no Android device attached on 2026-04-18 20:18+0800)
- Hard grep gates: PASS (page-level taskBoard fetch none; UTC date key none; legacy DateTimePicker none)
- Lifecycle ownership grep reviewed: PASS (latest scan baseline)
- Strategy review completed: PASS (follow `scripts/verify-mobile-stability.md`)
- Fresh release build:
  - `./gradlew assembleRelease`: PASS
  - fresh APK timestamp: `2026-04-18 16:47:24 +0800`
  - fresh APK sha256: `f105e8916b188df806aeeb3ef5cc49c787dd62bc8b562ccbfe9a11cdb5be5c44`

## Full RC Pass

- Cold launch:
- Login:
- First sync completed once:
- `tasks -> calendar -> consult -> tasks`:
- Pull to refresh on all 3 pages:
- Background / foreground:
- Calendar drag date:
- Calendar resize duration:
- Tasks drag to calendar:
- Task insight stopgap validation:
- Smart input recovery:
- Logout:
- Relogin:
- Offline restart local-board render:

### Task Insight RC Samples

| sample | expectedState | actualState | repeats task text | preview used as task understanding | says what is missing | concrete next step | pass/fail | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 和元兵吃饭 | `insufficient_context` or `weak_link` |  |  |  |  |  |  |  |
| 晚上约高瑞瑞 | `insufficient_context` |  |  |  |  |  |  |  |
| 跟进日慈基金会继续推进… | `ready` or `weak_link` |  |  |  |  |  |  |  |
| 已完成待复盘任务 | `ready` or `insufficient_context` |  |  |  |  |  |  |  |
| 逾期但无业务上下文任务 | `insufficient_context` |  |  |  |  |  |  |  |

Task insight `NO-GO` triggers:
- repeats `task.title` or `task.description`
- uses `contextPreview.judgment.summary` as task understanding
- gives a business judgment with only task text
- gives a concrete suggestion from only a broad event-line link

## Confirmation Rerun

- `npm run verify:rc-android`:
- Hard grep gates rerun:
- Login starts sync once:
- Shared snapshot across tab switch:
- Task insight samples rerun:
- Logout clears local state:
- Offline restart local render:

## Blockers

### Blocker 1

- Layer: environment
- Severity: P0 / NO-GO
- Trigger step: `npm run verify:rc-android` -> Android device detection
- Expected: `adb devices -l` shows >= 1 row with status `device`
- Actual: `List of devices attached` with zero devices
- Reproducible: yes
- Evidence: `verify:rc-android` output on 2026-04-18 20:18+0800; manual `adb devices -l` empty
- Fix owner layer: environment (USB/ADB)
- Closure rerun steps:
  - restore ADB device visibility
  - rerun `npm run verify:rc-android`
  - run `adb install -r android/app/build/outputs/apk/release/app-release.apk`

### Blocker 2

- Layer: environment
- Severity: P0 / NO-GO
- Trigger step: JDK preflight before Gradle build
- Expected: `/usr/libexec/java_home -V` returns a valid JDK 17+
- Actual: **resolved**
- Reproducible: resolved after local JDK install
- Evidence: `java -version` -> Temurin 17.0.18; `./gradlew -version` PASS
- Fix owner layer: environment (JDK)
- Closure rerun steps: closed (keep `JAVA_HOME` pointing to local Temurin 17)

### Blocker 3

- Layer: environment
- Severity: P0 / NO-GO
- Trigger step: Milestone 2 device install verification
- Expected: `adb install -r ...` succeeds on attached device
- Actual: `adb: no devices/emulators found`
- Reproducible: yes
- Evidence: install attempt on 2026-04-18 16:48+0800
- Fix owner layer: environment (USB/ADB)
- Closure rerun steps: attach authorized device -> rerun install -> check package `lastUpdateTime`

## Final Decision

- Result: `NO-GO` (environment blocked before real-device RC pass)
- Notes: code-side gates green + fresh APK rebuilt; only remaining blocker is physical device visibility in ADB.
~~~

## `mobile/scripts/pr4a-dod.md`

- 编码: `utf-8`

~~~markdown
# PR4A DoD

`Attachment / Voice Skeleton` only closes when all five checks below are green.

| Check | Pass Condition |
| --- | --- |
| 旧上传失败可见 | 旧上传链失败项能在 health advanced diagnostics 中看到 pseudo-op |
| 可重试 | 支持单条重试和全部重试，失败原因可解释 |
| 录音原件可恢复 | 杀进程后录音原件仍能从 app 私有持久目录找回 |
| `local_id` 绑定稳定 | 本地 task 与本地 voice draft 在没有 `remote_id` 时也能稳定绑定 |
| `interactive` 不被堵塞 | 大文件失败或 transfer 堵塞时，任务完成、改期等交互链仍可立即响应 |
~~~

## `mobile/scripts/round1-confirmation-blocker-flow.md`

- 编码: `utf-8`

~~~markdown
# Round 1 -> Confirmation Blocker Flow

Track every Round 1 blocker through fix and confirmation rerun.

| blockerId | layer | severity | rootCause | fixCommit | requiredRerunScope | confirmedClosed |
| --- | --- | --- | --- | --- | --- | --- |
| env-adb-device-missing-20260418 | environment | P0 | Android device not visible in `adb devices -l` |  | `verify:rc-android` + `adb install -r` + Round 1 step 1 | no |
| env-jdk-missing-20260418 | environment | P0 | No local Java runtime for Gradle | local-only (no code commit) | `java -version` + `./gradlew -version` + `assembleRelease` | yes |
| task-insight-sample-* | tasks | P1 | Understanding card repeats task text, misclassifies weak context, or gives unsupported judgment |  | sample rerun + `npm run test:core` + relevant task detail checks | no |
~~~

## `mobile/scripts/run-android-rc-gates.sh`

- 编码: `utf-8`

~~~bash
#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ADB_BIN="${ADB_BIN:-}"
if [[ -z "$ADB_BIN" ]]; then
  if command -v adb >/dev/null 2>&1; then
    ADB_BIN="$(command -v adb)"
  elif [[ -x "$HOME/Library/Android/sdk/platform-tools/adb" ]]; then
    ADB_BIN="$HOME/Library/Android/sdk/platform-tools/adb"
  fi
fi

echo "==> RC gate: TypeScript"
if [[ "${SKIP_TYPESCRIPT_GATE:-0}" != "1" ]]; then
  npx tsc --noEmit
else
  echo "skipped (handled by outer stability scan)"
fi

echo
echo "==> RC gate: core tests"
if [[ "${SKIP_CORE_TEST_GATE:-0}" != "1" ]]; then
  npm run test:core
else
  echo "skipped (handled by outer stability scan)"
fi

echo
echo "==> RC gate: guarded direct task API writes"
npm run check:no-direct-task-api-writes

echo
echo "==> RC gate: grep - taskBoard direct fetch paths"
taskboard_matches="$(rg -n 'fetchTaskBoard|loadWithCache\(.*taskBoard' app components lib -g '!node_modules/**' || true)"
if [[ -n "$taskboard_matches" ]]; then
  echo "$taskboard_matches"
  page_level_matches="$(printf '%s\n' "$taskboard_matches" | rg '^(app|components)/' || true)"
  if [[ -n "$page_level_matches" ]]; then
    echo
    echo "FAIL: page-level taskBoard direct fetch residuals found."
    exit 1
  fi
fi

echo
echo "==> RC gate: grep - UTC date key usage"
utc_matches="$(rg -n 'toISOString\(\)\.slice\(0, 10\)' app components lib -g '!node_modules/**' || true)"
if [[ -n "$utc_matches" ]]; then
  echo "$utc_matches"
  echo
  echo "FAIL: UTC date key residuals found."
  exit 1
fi

echo
echo "==> RC gate: grep - legacy DateTimePicker usage"
picker_matches="$(rg -n 'DateTimePicker([^S]|$)' app components lib -g '!node_modules/**' || true)"
if [[ -n "$picker_matches" ]]; then
  echo "$picker_matches"
  echo
  echo "FAIL: legacy DateTimePicker residuals found."
  exit 1
fi

echo
echo "==> RC gate: Android runtime flags"
rg -n 'newArchEnabled|hermesEnabled' android/gradle.properties

echo
echo "==> RC gate: Android APK presence"
APK_PATH="android/app/build/outputs/apk/release/app-release.apk"
if [[ ! -f "$APK_PATH" ]]; then
  echo "FAIL: release APK not found at $APK_PATH"
  exit 1
fi
echo "$APK_PATH"

echo
echo "==> RC gate: Android device detection"
if [[ -z "$ADB_BIN" ]]; then
  echo "BLOCKED: adb not found. Set ADB_BIN or install Android platform-tools."
  exit 2
fi

"$ADB_BIN" start-server >/dev/null
device_output="$("$ADB_BIN" devices -l)"
echo "$device_output"

device_count="$(printf '%s\n' "$device_output" | awk 'NR>1 && $2=="device" { count += 1 } END { print count + 0 }')"
if [[ "$device_count" -lt 1 ]]; then
  echo
  echo "BLOCKED: no Android device attached. Connect a real device, then rerun:"
  echo "  npm run verify:rc-android"
  exit 2
fi

echo
echo "PASS: automated RC gates succeeded and Android device is attached."
echo "Next: execute scripts/android-rc-blocker-checklist.md on the device."
~~~

## `mobile/scripts/run-mobile-core-tests.mjs`

- 编码: `utf-8`

~~~javascript
import { execFileSync } from "node:child_process";
import { readdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = dirname(__dirname);
const buildRoot = join(repoRoot, ".mobile-core-tests");
const testsDir = join(repoRoot, "lib", "__tests__");

rmSync(buildRoot, { recursive: true, force: true });

execFileSync(
  "npx",
  ["tsc", "-p", "tsconfig.tests.json"],
  {
    cwd: repoRoot,
    stdio: "inherit",
  },
);

const testFiles = readdirSync(testsDir)
  .filter((file) => file.endsWith(".test.mjs"))
  .sort()
  .map((file) => join("lib", "__tests__", file));

if (testFiles.length === 0) {
  throw new Error("No core test files found.");
}

execFileSync(
  process.execPath,
  ["--test", ...testFiles],
  {
    cwd: repoRoot,
    stdio: "inherit",
  },
);
~~~

## `mobile/scripts/run-mobile-stability-scan.sh`

- 编码: `utf-8`

~~~bash
#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> Stability scan: TypeScript"
npx tsc --noEmit

echo
echo "==> Stability scan: core tests"
npm run test:core

echo
echo "==> Stability scan: Android RC gate"
SKIP_TYPESCRIPT_GATE=1 SKIP_CORE_TEST_GATE=1 bash scripts/run-android-rc-gates.sh

echo
echo "==> Stability scan: lifecycle ownership grep"
lifecycle_matches="$(rg -n 'setInterval|useFocusEffect|AppState\.addEventListener|BackgroundFetch\.registerTaskAsync|triggerSync\(' app components lib -g '!node_modules/**' || true)"
if [[ -n "$lifecycle_matches" ]]; then
  echo "$lifecycle_matches"
  unexpected_matches="$(printf '%s\n' "$lifecycle_matches" | rg -v '^(lib/(android-back|sync-engine|task-board-store-core)\.ts|components/(RecordNote|SmartInputSheet)\.tsx|components/tasks-screen/SmartInputRecoveryController\.tsx|app/\(tabs\)/calendar\.tsx):' || true)"
  if [[ -n "$unexpected_matches" ]]; then
    echo
    echo "FAIL: unexpected lifecycle ownership matches found."
    echo "$unexpected_matches"
    exit 1
  fi
else
  echo "No lifecycle ownership matches found."
fi

echo
echo "==> Stability scan: strategy review checkpoints"
cat <<'EOF'
- Review scripts/verify-mobile-stability.md before release or PR split.
- Confirm the 7 release risks are still covered by gates and device checks.
- Confirm blocker layering still routes foundation issues to runtime/sync/store first.
- Confirm release behavior remains the only go/no-go truth; debug/dev is diagnostic only.
- Confirm two clean results are still required for RC release decisions.
EOF

echo
echo "==> Stability scan: evidence template"
echo "Record the run in scripts/mobile-blocker-ledger.md"
~~~

## `mobile/scripts/verify-mobile-stability.md`

- 编码: `utf-8`

~~~markdown
# Mobile Stability Verification

This document is the single source of truth for repeated stability scans on the mobile release candidate and the follow-up PRs.

## Scan Loop

Run this order every round:

1. `npx tsc --noEmit`
2. `npm run test:core`
3. `npm run verify:rc-android`
4. `npm run check:no-direct-task-api-writes`
5. Static grep gates
6. Strategy risk review
7. Android real-device blocker checklist
8. Blocker layer assignment
9. After any fix, restart from step 1

Convenience entrypoint:

- `npm run scan:stability-android`

That command runs:

- TypeScript
- core tests
- Android RC gate
- no-direct-task-api-writes guard
- lifecycle ownership grep
- strategy review reminders

It does not replace the manual real-device checklist.

## Hard Gates

These are release-blocking and should be zero-regression gates:

- page-level `fetchTaskBoard` or `loadWithCache(...taskBoard)` residues
- UTC `toISOString().slice(0, 10)` date-key logic
- legacy `DateTimePicker` usage in the main flow

Commands:

```bash
rg "fetchTaskBoard|loadWithCache\\(.*taskBoard" app components lib
rg "toISOString\\(\\)\\.slice\\(0, 10\\)" app components lib
rg "DateTimePicker([^S]|$)" app components lib
```

Expected release behavior:

- `fetchTaskBoard` hits may exist only in lower-level sync or API code, never in page/component taskBoard reads
- UTC date-key hits should be zero
- legacy `DateTimePicker` hits should be zero

## Risk Surfaces To Re-scan

Every round, review these ownership boundaries:

- runtime lifecycle remains idempotent:
  - `initializeRuntime`
  - `startAuthenticatedRuntime`
  - `stopAuthenticatedRuntime`
  - `startSyncEngine`
  - `stopSyncEngine`
- sync registration stays centralized in `lib/sync-engine.ts`
- taskBoard read path stays centralized in `lib/task-board-store.ts`
- task pages do not fork taskBoard state
- local date helpers remain the only source for “today” logic
- smart-input recovery stays event-driven and never reintroduces background polling in the tasks flow
- CreateTask association precedence remains `manual > auto > default`

Targeted review files:

- `lib/runtime.ts`
- `lib/runtime-controller.ts`
- `lib/sync-engine.ts`
- `lib/task-board-store.ts`
- `app/(tabs)/tasks.tsx`
- `app/(tabs)/calendar.tsx`
- `app/(tabs)/consult.tsx`
- `components/CreateTask.tsx`

Lifecycle ownership grep:

```bash
rg "setInterval|useFocusEffect|AppState\\.addEventListener|BackgroundFetch\\.registerTaskAsync|triggerSync\\(" app components lib
```

This grep is review-required, not auto-fail by itself. Use it to confirm the owner is still intentional:

- `lib/sync-engine.ts`: foreground sync timer, AppState listener, BackgroundFetch registration, `triggerSync()` owner
- `lib/task-board-store-core.ts`: unified `triggerSync()` consumer
- `lib/android-back.ts`: Android back navigation helper via `useFocusEffect`
- `components/RecordNote.tsx`: recording duration timer
- `components/SmartInputSheet.tsx`: queued-recording counter refresh only, not task recovery polling
- `components/tasks-screen/SmartInputRecoveryController.tsx`: tasks-page recovery hooks for `tasks_enter`, `app_active`, and manual recovery only
- `app/(tabs)/calendar.tsx`: minute tick for day-view current-time indicator only

If new hits appear outside those boundaries, treat them as blockers until reviewed. If they reintroduce page-level data fetching, polling, or duplicated lifecycle ownership, they are release-blocking.

## Strategy Risk Review

Each round, confirm the gates still cover these release risks:

1. login starts sync exactly once
2. `tasks / calendar / consult` share one taskBoard snapshot
3. pull-to-refresh still routes through unified `refresh()`
4. smart-input recovery does not interrupt the user
5. logout clears local SQLite and avoids cross-account residue
6. offline restart still renders from the local board after one successful sync
7. `calendar` and `tasks` drag flows still behave the same

Blocker layering must stay stable:

- `runtime / baseUrl / sync / local-db / taskBoard store` issues return to foundation first
- `tasks` issues stay in the tasks layer
- `calendar / consult` issues stay in their screen layers
- `CreateTask / picker` issues stay in the create flow layer

Release decision rules must stay stable:

- release behavior is the only go/no-go truth
- debug/dev builds are diagnostic only
- BackgroundFetch is checked only for correct registration and cleanup, not schedule guarantees
- RC release requires two clean results:
  - one full real-device blocker pass
  - one confirmation re-scan

## Android RC Checklist

Use `scripts/android-rc-blocker-checklist.md` for the real-device order. Do not reorder it.

The confirmation re-scan must repeat at least:

- `npm run verify:rc-android`
- the 3 hard grep gates
- login -> sync starts once
- tab switching shows one snapshot
- logout clears local state
- offline restart renders from the local board

## PR Cadence

`PR1 foundation`

- rerun all automated gates after every change
- rerun the full real-device checklist when runtime, sync, or local-db changes

`PR2 store + tasks`

- rerun all automated gates
- rerun at least: quick tab switch, tasks refresh, smart-input recovery, tasks drag-to-calendar

`PR3 calendar + consult`

- rerun all automated gates
- rerun at least: calendar date drag, duration resize, consult context consistency, background/foreground

`PR4 CreateTask / picker / verify`

- rerun all automated gates
- rerun at least: CreateTask association precedence, picker main flow, logout isolation, offline restart

If any PR reopens a hard gate or alters release decision rules, treat it as a blocker immediately. Do not defer it to a later PR.

## Blocker Closure Standard

A blocker is closed only when all of the following are true:

1. reproduced
2. fixed
3. full automated gates rerun
4. affected real-device steps rerun
5. if foundation/store/sync related, one extra full RC re-scan rerun

Record every RC or PR scan in `scripts/mobile-blocker-ledger.md`.
~~~

## `mobile/scripts/write-checkpoint-snapshot.mjs`

- 编码: `utf-8`

~~~javascript
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = dirname(__dirname);
const localDbSource = readFileSync(join(repoRoot, "lib", "local-db.ts"), "utf8");
const runtimeFlagsSource = readFileSync(join(repoRoot, "lib", "runtime-flags.ts"), "utf8");

function run(command, args) {
  try {
    const output = execFileSync(command, args, {
      cwd: repoRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    }).trim();
    return { ok: true, output };
  } catch (error) {
    const stdout = error?.stdout ? String(error.stdout).trim() : "";
    const stderr = error?.stderr ? String(error.stderr).trim() : "";
    return {
      ok: false,
      output: [stdout, stderr].filter(Boolean).join("\n").trim(),
    };
  }
}

function extractSchemaVersion(source) {
  const match = source.match(/CURRENT_SCHEMA_VERSION\s*=\s*(\d+)/);
  return match?.[1] ?? "unknown";
}

function extractDefaultFlags(source) {
  const match = source.match(/const DEFAULT_FLAGS:[\s\S]+?=\s*\{([\s\S]*?)\n\};/);
  if (!match) {
    return [];
  }
  return match[1]
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.replace(/,$/, ""));
}

const branch = run("git", ["rev-parse", "--abbrev-ref", "HEAD"]);
const commit = run("git", ["rev-parse", "HEAD"]);
const status = run("git", ["status", "--short"]);
const tsc = run("npx", ["tsc", "--noEmit"]);
const coreTests = run("npm", ["run", "test:core"]);
const noDirectWrites = run("npm", ["run", "check:no-direct-task-api-writes"]);
const inventory = run("npm", ["run", "inventory:direct-api-usage"]);

const timestamp = new Date().toISOString();
const outputPath = join(repoRoot, "scripts", "checkpoint-snapshot.md");

const contents = `# Checkpoint Snapshot

Generated at: \`${timestamp}\`

## Baseline

- Branch: \`${branch.output || "unknown"}\`
- Commit: \`${commit.output || "unknown"}\`
- Schema version: \`${extractSchemaVersion(localDbSource)}\`

## Runtime Flags Default

${extractDefaultFlags(runtimeFlagsSource).map((line) => `- \`${line}\``).join("\n")}

## Gate Summary

- \`npx tsc --noEmit\`: ${tsc.ok ? "PASS" : "FAIL"}
- \`npm run test:core\`: ${coreTests.ok ? "PASS" : "FAIL"}
- \`npm run check:no-direct-task-api-writes\`: ${noDirectWrites.ok ? "PASS" : "FAIL"}
- \`npm run inventory:direct-api-usage\`: ${inventory.ok ? "PASS" : "FAIL"}

## Inventory Snapshot

\`\`\`text
${inventory.output || "(no output)"}
\`\`\`

## Git Status

\`\`\`text
${status.output || "(clean)"}
\`\`\`
`;

writeFileSync(outputPath, contents);
console.log(outputPath);
~~~

## `mobile/tsconfig.json`

- 编码: `utf-8`

~~~json
{
  "extends": "expo/tsconfig.base",
  "compilerOptions": {
    "strict": false,
    "skipLibCheck": true
  },
  "include": [
    "app",
    "components",
    "lib"
  ]
}
~~~

## `mobile/tsconfig.tests.json`

- 编码: `utf-8`

~~~json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "CommonJS",
    "moduleResolution": "Node",
    "strict": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "declaration": false,
    "rootDir": ".",
    "outDir": ".mobile-core-tests/dist"
  },
  "include": [
    "lib/base-url.ts",
    "lib/date.ts",
    "lib/runtime-controller.ts",
    "lib/task-board-store-core.ts",
    "lib/smart-input-recovery.ts",
    "lib/create-task-association.ts",
    "lib/consult-context.ts",
    "lib/boundary-cards.ts",
    "lib/current-focus-core.ts",
    "lib/sync-freeze-core.ts",
    "lib/calendar-repository-core.ts",
    "lib/focus-selectors.ts",
    "lib/week-signal.ts",
    "lib/consult-context-adapter.ts",
    "lib/task-understanding.ts",
    "lib/account-scope.ts",
    "lib/types.ts",
    "lib/pending-op-policy.ts",
    "lib/consult-thread-context.ts",
    "lib/task-sync-policy.ts",
    "lib/smart-input-queue-core.ts",
    "lib/legacy-upload-pseudo-op-core.ts",
    "lib/record-note-flow-core.ts",
    "lib/legacy-upload-runner-core.ts",
    "lib/scope-storage-core.ts"
  ]
}
~~~

## `package-lock.json`

- 编码: `utf-8`

~~~json
{
  "name": "yiyu-thinktank-workbench",
  "version": "0.1.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "yiyu-thinktank-workbench",
      "version": "0.1.0",
      "dependencies": {
        "@rollup/rollup-linux-arm64-gnu": "^4.60.1",
        "lucide-react": "^0.511.0",
        "qrcode": "^1.5.4",
        "react": "^18.3.1",
        "react-dom": "^18.3.1"
      },
      "devDependencies": {
        "@tailwindcss/typography": "^0.5.16",
        "@types/node": "^22.13.9",
        "@types/react": "^18.3.18",
        "@types/react-dom": "^18.3.5",
        "@vitejs/plugin-react": "^4.3.4",
        "autoprefixer": "^10.4.21",
        "concurrently": "^9.1.2",
        "cross-env": "^7.0.3",
        "electron": "^37.6.1",
        "electron-builder": "^26.0.12",
        "postcss": "^8.5.6",
        "tailwindcss": "^3.4.17",
        "typescript": "^5.8.2",
        "vite": "^6.2.1",
        "wait-on": "^8.0.3"
      }
    },
    "node_modules/@alloc/quick-lru": {
      "version": "5.2.0",
      "resolved": "https://registry.npmmirror.com/@alloc/quick-lru/-/quick-lru-5.2.0.tgz",
      "integrity": "sha512-UrcABB+4bUrFABwbluTIBErXwvbsU/V7TZWfmbgJfbkwiBuziS9gxdODUyuiecfdGQ85jglMW6juS3+z5TsKLw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/@babel/code-frame": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/code-frame/-/code-frame-7.29.0.tgz",
      "integrity": "sha512-9NhCeYjq9+3uxgdtp20LSiJXJvN0FeCtNGpJxuMFZ1Kv3cWUNb6DOhJwUvcVCzKGR66cw4njwM6hrJLqgOwbcw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-validator-identifier": "^7.28.5",
        "js-tokens": "^4.0.0",
        "picocolors": "^1.1.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/compat-data": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/compat-data/-/compat-data-7.29.0.tgz",
      "integrity": "sha512-T1NCJqT/j9+cn8fvkt7jtwbLBfLC/1y1c7NtCeXFRgzGTsafi68MRv8yzkYSapBnFA6L3U2VSc02ciDzoAJhJg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/core": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/core/-/core-7.29.0.tgz",
      "integrity": "sha512-CGOfOJqWjg2qW/Mb6zNsDm+u5vFQ8DxXfbM09z69p5Z6+mE1ikP2jUXw+j42Pf1XTYED2Rni5f95npYeuwMDQA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.29.0",
        "@babel/generator": "^7.29.0",
        "@babel/helper-compilation-targets": "^7.28.6",
        "@babel/helper-module-transforms": "^7.28.6",
        "@babel/helpers": "^7.28.6",
        "@babel/parser": "^7.29.0",
        "@babel/template": "^7.28.6",
        "@babel/traverse": "^7.29.0",
        "@babel/types": "^7.29.0",
        "@jridgewell/remapping": "^2.3.5",
        "convert-source-map": "^2.0.0",
        "debug": "^4.1.0",
        "gensync": "^1.0.0-beta.2",
        "json5": "^2.2.3",
        "semver": "^6.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "funding": {
        "type": "opencollective",
        "url": "https://opencollective.com/babel"
      }
    },
    "node_modules/@babel/generator": {
      "version": "7.29.1",
      "resolved": "https://registry.npmmirror.com/@babel/generator/-/generator-7.29.1.tgz",
      "integrity": "sha512-qsaF+9Qcm2Qv8SRIMMscAvG4O3lJ0F1GuMo5HR/Bp02LopNgnZBC/EkbevHFeGs4ls/oPz9v+Bsmzbkbe+0dUw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/parser": "^7.29.0",
        "@babel/types": "^7.29.0",
        "@jridgewell/gen-mapping": "^0.3.12",
        "@jridgewell/trace-mapping": "^0.3.28",
        "jsesc": "^3.0.2"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-compilation-targets": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/helper-compilation-targets/-/helper-compilation-targets-7.28.6.tgz",
      "integrity": "sha512-JYtls3hqi15fcx5GaSNL7SCTJ2MNmjrkHXg4FSpOA/grxK8KwyZ5bubHsCq8FXCkua6xhuaaBit+3b7+VZRfcA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/compat-data": "^7.28.6",
        "@babel/helper-validator-option": "^7.27.1",
        "browserslist": "^4.24.0",
        "lru-cache": "^5.1.1",
        "semver": "^6.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-globals": {
      "version": "7.28.0",
      "resolved": "https://registry.npmmirror.com/@babel/helper-globals/-/helper-globals-7.28.0.tgz",
      "integrity": "sha512-+W6cISkXFa1jXsDEdYA8HeevQT/FULhxzR99pxphltZcVaugps53THCeiWA8SguxxpSp3gKPiuYfSWopkLQ4hw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-module-imports": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/helper-module-imports/-/helper-module-imports-7.28.6.tgz",
      "integrity": "sha512-l5XkZK7r7wa9LucGw9LwZyyCUscb4x37JWTPz7swwFE/0FMQAGpiWUZn8u9DzkSBWEcK25jmvubfpw2dnAMdbw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/traverse": "^7.28.6",
        "@babel/types": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-module-transforms": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/helper-module-transforms/-/helper-module-transforms-7.28.6.tgz",
      "integrity": "sha512-67oXFAYr2cDLDVGLXTEABjdBJZ6drElUSI7WKp70NrpyISso3plG9SAGEF6y7zbha/wOzUByWWTJvEDVNIUGcA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-module-imports": "^7.28.6",
        "@babel/helper-validator-identifier": "^7.28.5",
        "@babel/traverse": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0"
      }
    },
    "node_modules/@babel/helper-plugin-utils": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/helper-plugin-utils/-/helper-plugin-utils-7.28.6.tgz",
      "integrity": "sha512-S9gzZ/bz83GRysI7gAD4wPT/AI3uCnY+9xn+Mx/KPs2JwHJIz1W8PZkg2cqyt3RNOBM8ejcXhV6y8Og7ly/Dug==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-string-parser": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/helper-string-parser/-/helper-string-parser-7.27.1.tgz",
      "integrity": "sha512-qMlSxKbpRlAridDExk92nSobyDdpPijUq2DW6oDnUqd0iOGxmQjyqhMIihI9+zv4LPyZdRje2cavWPbCbWm3eA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-validator-identifier": {
      "version": "7.28.5",
      "resolved": "https://registry.npmmirror.com/@babel/helper-validator-identifier/-/helper-validator-identifier-7.28.5.tgz",
      "integrity": "sha512-qSs4ifwzKJSV39ucNjsvc6WVHs6b7S03sOh2OcHF9UHfVPqWWALUsNUVzhSBiItjRZoLHx7nIarVjqKVusUZ1Q==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-validator-option": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/helper-validator-option/-/helper-validator-option-7.27.1.tgz",
      "integrity": "sha512-YvjJow9FxbhFFKDSuFnVCe2WxXk1zWc22fFePVNEaWJEu8IrZVlda6N0uHwzZrUM1il7NC9Mlp4MaJYbYd9JSg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helpers": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/helpers/-/helpers-7.28.6.tgz",
      "integrity": "sha512-xOBvwq86HHdB7WUDTfKfT/Vuxh7gElQ+Sfti2Cy6yIWNW05P8iUslOVcZ4/sKbE+/jQaukQAdz/gf3724kYdqw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/template": "^7.28.6",
        "@babel/types": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/parser": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/parser/-/parser-7.29.0.tgz",
      "integrity": "sha512-IyDgFV5GeDUVX4YdF/3CPULtVGSXXMLh1xVIgdCgxApktqnQV0r7/8Nqthg+8YLGaAtdyIlo2qIdZrbCv4+7ww==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.29.0"
      },
      "bin": {
        "parser": "bin/babel-parser.js"
      },
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@babel/plugin-transform-react-jsx-self": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-react-jsx-self/-/plugin-transform-react-jsx-self-7.27.1.tgz",
      "integrity": "sha512-6UzkCs+ejGdZ5mFFC/OCUrv028ab2fp1znZmCZjAOBKiBK2jXD1O+BPSfX8X2qjJ75fZBMSnQn3Rq2mrBJK2mw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-react-jsx-source": {
      "version": "7.27.1",
      "resolved": "https://registry.npmmirror.com/@babel/plugin-transform-react-jsx-source/-/plugin-transform-react-jsx-source-7.27.1.tgz",
      "integrity": "sha512-zbwoTsBruTeKB9hSq73ha66iFeJHuaFkUbwvqElnygoNbj/jHRsSeokowZFN3CZ64IvEqcmmkVe89OPXc7ldAw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.27.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/template": {
      "version": "7.28.6",
      "resolved": "https://registry.npmmirror.com/@babel/template/-/template-7.28.6.tgz",
      "integrity": "sha512-YA6Ma2KsCdGb+WC6UpBVFJGXL58MDA6oyONbjyF/+5sBgxY/dwkhLogbMT2GXXyU84/IhRw/2D1Os1B/giz+BQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.28.6",
        "@babel/parser": "^7.28.6",
        "@babel/types": "^7.28.6"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/traverse": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/traverse/-/traverse-7.29.0.tgz",
      "integrity": "sha512-4HPiQr0X7+waHfyXPZpWPfWL/J7dcN1mx9gL6WdQVMbPnF3+ZhSMs8tCxN7oHddJE9fhNE7+lxdnlyemKfJRuA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.29.0",
        "@babel/generator": "^7.29.0",
        "@babel/helper-globals": "^7.28.0",
        "@babel/parser": "^7.29.0",
        "@babel/template": "^7.28.6",
        "@babel/types": "^7.29.0",
        "debug": "^4.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/types": {
      "version": "7.29.0",
      "resolved": "https://registry.npmmirror.com/@babel/types/-/types-7.29.0.tgz",
      "integrity": "sha512-LwdZHpScM4Qz8Xw2iKSzS+cfglZzJGvofQICy7W7v4caru4EaAmyUuO6BGrbyQ2mYV11W0U8j5mBhd14dd3B0A==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-string-parser": "^7.27.1",
        "@babel/helper-validator-identifier": "^7.28.5"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@develar/schema-utils": {
      "version": "2.6.5",
      "resolved": "https://registry.npmmirror.com/@develar/schema-utils/-/schema-utils-2.6.5.tgz",
      "integrity": "sha512-0cp4PsWQ/9avqTVMCtZ+GirikIA36ikvjtHweU4/j8yLtgObI0+JUPhYFScgwlteveGB1rt3Cm8UhN04XayDig==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "ajv": "^6.12.0",
        "ajv-keywords": "^3.4.1"
      },
      "engines": {
        "node": ">= 8.9.0"
      },
      "funding": {
        "type": "opencollective",
        "url": "https://opencollective.com/webpack"
      }
    },
    "node_modules/@electron/asar": {
      "version": "3.4.1",
      "resolved": "https://registry.npmmirror.com/@electron/asar/-/asar-3.4.1.tgz",
      "integrity": "sha512-i4/rNPRS84t0vSRa2HorerGRXWyF4vThfHesw0dmcWHp+cspK743UanA0suA5Q5y8kzY2y6YKrvbIUn69BCAiA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "commander": "^5.0.0",
        "glob": "^7.1.6",
        "minimatch": "^3.0.4"
      },
      "bin": {
        "asar": "bin/asar.js"
      },
      "engines": {
        "node": ">=10.12.0"
      }
    },
    "node_modules/@electron/asar/node_modules/balanced-match": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/balanced-match/-/balanced-match-1.0.2.tgz",
      "integrity": "sha512-3oSeUO0TMV67hN1AmbXsK4yaqU7tjiHlbxRDZOpH0KW9+CeX4bRAaX0Anxt0tx2MrpRpWwQaPwIlISEJhYU5Pw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@electron/asar/node_modules/brace-expansion": {
      "version": "1.1.12",
      "resolved": "https://registry.npmmirror.com/brace-expansion/-/brace-expansion-1.1.12.tgz",
      "integrity": "sha512-9T9UjW3r0UW5c1Q7GTwllptXwhvYmEzFhzMfZ9H7FQWt+uZePjZPjBP/W1ZEyZ1twGWom5/56TF4lPcqjnDHcg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "balanced-match": "^1.0.0",
        "concat-map": "0.0.1"
      }
    },
    "node_modules/@electron/asar/node_modules/minimatch": {
      "version": "3.1.5",
      "resolved": "https://registry.npmmirror.com/minimatch/-/minimatch-3.1.5.tgz",
      "integrity": "sha512-VgjWUsnnT6n+NUk6eZq77zeFdpW2LWDzP6zFGrCbHXiYNul5Dzqk2HHQ5uFH2DNW5Xbp8+jVzaeNt94ssEEl4w==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "brace-expansion": "^1.1.7"
      },
      "engines": {
        "node": "*"
      }
    },
    "node_modules/@electron/fuses": {
      "version": "1.8.0",
      "resolved": "https://registry.npmmirror.com/@electron/fuses/-/fuses-1.8.0.tgz",
      "integrity": "sha512-zx0EIq78WlY/lBb1uXlziZmDZI4ubcCXIMJ4uGjXzZW0nS19TjSPeXPAjzzTmKQlJUZm0SbmZhPKP7tuQ1SsEw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "chalk": "^4.1.1",
        "fs-extra": "^9.0.1",
        "minimist": "^1.2.5"
      },
      "bin": {
        "electron-fuses": "dist/bin.js"
      }
    },
    "node_modules/@electron/fuses/node_modules/fs-extra": {
      "version": "9.1.0",
      "resolved": "https://registry.npmmirror.com/fs-extra/-/fs-extra-9.1.0.tgz",
      "integrity": "sha512-hcg3ZmepS30/7BSFqRvoo3DOMQu7IjqxO5nCDt+zM9XWjb33Wg7ziNT+Qvqbuc3+gWpzO02JubVyk2G4Zvo1OQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "at-least-node": "^1.0.0",
        "graceful-fs": "^4.2.0",
        "jsonfile": "^6.0.1",
        "universalify": "^2.0.0"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/@electron/fuses/node_modules/jsonfile": {
      "version": "6.2.0",
      "resolved": "https://registry.npmmirror.com/jsonfile/-/jsonfile-6.2.0.tgz",
      "integrity": "sha512-FGuPw30AdOIUTRMC2OMRtQV+jkVj2cfPqSeWXv1NEAJ1qZ5zb1X6z1mFhbfOB/iy3ssJCD+3KuZ8r8C3uVFlAg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "universalify": "^2.0.0"
      },
      "optionalDependencies": {
        "graceful-fs": "^4.1.6"
      }
    },
    "node_modules/@electron/fuses/node_modules/universalify": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/universalify/-/universalify-2.0.1.tgz",
      "integrity": "sha512-gptHNQghINnc/vTGIk0SOFGFNXw7JVrlRUtConJRlvaw6DuX0wO5Jeko9sWrMBhh+PsYAZ7oXAiOnf/UKogyiw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 10.0.0"
      }
    },
    "node_modules/@electron/get": {
      "version": "2.0.3",
      "resolved": "https://registry.npmmirror.com/@electron/get/-/get-2.0.3.tgz",
      "integrity": "sha512-Qkzpg2s9GnVV2I2BjRksUi43U5e6+zaQMcjoJy0C+C5oxaKl+fmckGDQFtRpZpZV0NQekuZZ+tGz7EA9TVnQtQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "debug": "^4.1.1",
        "env-paths": "^2.2.0",
        "fs-extra": "^8.1.0",
        "got": "^11.8.5",
        "progress": "^2.0.3",
        "semver": "^6.2.0",
        "sumchecker": "^3.0.1"
      },
      "engines": {
        "node": ">=12"
      },
      "optionalDependencies": {
        "global-agent": "^3.0.0"
      }
    },
    "node_modules/@electron/notarize": {
      "version": "2.5.0",
      "resolved": "https://registry.npmmirror.com/@electron/notarize/-/notarize-2.5.0.tgz",
      "integrity": "sha512-jNT8nwH1f9X5GEITXaQ8IF/KdskvIkOFfB2CvwumsveVidzpSc+mvhhTMdAGSYF3O+Nq49lJ7y+ssODRXu06+A==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "debug": "^4.1.1",
        "fs-extra": "^9.0.1",
        "promise-retry": "^2.0.1"
      },
      "engines": {
        "node": ">= 10.0.0"
      }
    },
    "node_modules/@electron/notarize/node_modules/fs-extra": {
      "version": "9.1.0",
      "resolved": "https://registry.npmmirror.com/fs-extra/-/fs-extra-9.1.0.tgz",
      "integrity": "sha512-hcg3ZmepS30/7BSFqRvoo3DOMQu7IjqxO5nCDt+zM9XWjb33Wg7ziNT+Qvqbuc3+gWpzO02JubVyk2G4Zvo1OQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "at-least-node": "^1.0.0",
        "graceful-fs": "^4.2.0",
        "jsonfile": "^6.0.1",
        "universalify": "^2.0.0"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/@electron/notarize/node_modules/jsonfile": {
      "version": "6.2.0",
      "resolved": "https://registry.npmmirror.com/jsonfile/-/jsonfile-6.2.0.tgz",
      "integrity": "sha512-FGuPw30AdOIUTRMC2OMRtQV+jkVj2cfPqSeWXv1NEAJ1qZ5zb1X6z1mFhbfOB/iy3ssJCD+3KuZ8r8C3uVFlAg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "universalify": "^2.0.0"
      },
      "optionalDependencies": {
        "graceful-fs": "^4.1.6"
      }
    },
    "node_modules/@electron/notarize/node_modules/universalify": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/universalify/-/universalify-2.0.1.tgz",
      "integrity": "sha512-gptHNQghINnc/vTGIk0SOFGFNXw7JVrlRUtConJRlvaw6DuX0wO5Jeko9sWrMBhh+PsYAZ7oXAiOnf/UKogyiw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 10.0.0"
      }
    },
    "node_modules/@electron/osx-sign": {
      "version": "1.3.3",
      "resolved": "https://registry.npmmirror.com/@electron/osx-sign/-/osx-sign-1.3.3.tgz",
      "integrity": "sha512-KZ8mhXvWv2rIEgMbWZ4y33bDHyUKMXnx4M0sTyPNK/vcB81ImdeY9Ggdqy0SWbMDgmbqyQ+phgejh6V3R2QuSg==",
      "dev": true,
      "license": "BSD-2-Clause",
      "dependencies": {
        "compare-version": "^0.1.2",
        "debug": "^4.3.4",
        "fs-extra": "^10.0.0",
        "isbinaryfile": "^4.0.8",
        "minimist": "^1.2.6",
        "plist": "^3.0.5"
      },
      "bin": {
        "electron-osx-flat": "bin/electron-osx-flat.js",
        "electron-osx-sign": "bin/electron-osx-sign.js"
      },
      "engines": {
        "node": ">=12.0.0"
      }
    },
    "node_modules/@electron/osx-sign/node_modules/fs-extra": {
      "version": "10.1.0",
      "resolved": "https://registry.npmmirror.com/fs-extra/-/fs-extra-10.1.0.tgz",
      "integrity": "sha512-oRXApq54ETRj4eMiFzGnHWGy+zo5raudjuxN0b8H7s/RU2oW0Wvsx9O0ACRN/kRq9E8Vu/ReskGB5o3ji+FzHQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "graceful-fs": "^4.2.0",
        "jsonfile": "^6.0.1",
        "universalify": "^2.0.0"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/@electron/osx-sign/node_modules/isbinaryfile": {
      "version": "4.0.10",
      "resolved": "https://registry.npmmirror.com/isbinaryfile/-/isbinaryfile-4.0.10.tgz",
      "integrity": "sha512-iHrqe5shvBUcFbmZq9zOQHBoeOhZJu6RQGrDpBgenUm/Am+F3JM2MgQj+rK3Z601fzrL5gLZWtAPH2OBaSVcyw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 8.0.0"
      },
      "funding": {
        "url": "https://github.com/sponsors/gjtorikian/"
      }
    },
    "node_modules/@electron/osx-sign/node_modules/jsonfile": {
      "version": "6.2.0",
      "resolved": "https://registry.npmmirror.com/jsonfile/-/jsonfile-6.2.0.tgz",
      "integrity": "sha512-FGuPw30AdOIUTRMC2OMRtQV+jkVj2cfPqSeWXv1NEAJ1qZ5zb1X6z1mFhbfOB/iy3ssJCD+3KuZ8r8C3uVFlAg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "universalify": "^2.0.0"
      },
      "optionalDependencies": {
        "graceful-fs": "^4.1.6"
      }
    },
    "node_modules/@electron/osx-sign/node_modules/universalify": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/universalify/-/universalify-2.0.1.tgz",
      "integrity": "sha512-gptHNQghINnc/vTGIk0SOFGFNXw7JVrlRUtConJRlvaw6DuX0wO5Jeko9sWrMBhh+PsYAZ7oXAiOnf/UKogyiw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 10.0.0"
      }
    },
    "node_modules/@electron/rebuild": {
      "version": "4.0.3",
      "resolved": "https://registry.npmmirror.com/@electron/rebuild/-/rebuild-4.0.3.tgz",
      "integrity": "sha512-u9vpTHRMkOYCs/1FLiSVAFZ7FbjsXK+bQuzviJZa+lG7BHZl1nz52/IcGvwa3sk80/fc3llutBkbCq10Vh8WQA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@malept/cross-spawn-promise": "^2.0.0",
        "debug": "^4.1.1",
        "detect-libc": "^2.0.1",
        "got": "^11.7.0",
        "graceful-fs": "^4.2.11",
        "node-abi": "^4.2.0",
        "node-api-version": "^0.2.1",
        "node-gyp": "^11.2.0",
        "ora": "^5.1.0",
        "read-binary-file-arch": "^1.0.6",
        "semver": "^7.3.5",
        "tar": "^7.5.6",
        "yargs": "^17.0.1"
      },
      "bin": {
        "electron-rebuild": "lib/cli.js"
      },
      "engines": {
        "node": ">=22.12.0"
      }
    },
    "node_modules/@electron/rebuild/node_modules/semver": {
      "version": "7.7.4",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-7.7.4.tgz",
      "integrity": "sha512-vFKC2IEtQnVhpT78h1Yp8wzwrf8CM+MzKMHGJZfBtzhZNycRFnXsHk6E5TxIkkMsgNS7mdX3AGB7x2QM2di4lA==",
      "dev": true,
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/@electron/universal": {
      "version": "2.0.3",
      "resolved": "https://registry.npmmirror.com/@electron/universal/-/universal-2.0.3.tgz",
      "integrity": "sha512-Wn9sPYIVFRFl5HmwMJkARCCf7rqK/EurkfQ/rJZ14mHP3iYTjZSIOSVonEAnhWeAXwtw7zOekGRlc6yTtZ0t+g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@electron/asar": "^3.3.1",
        "@malept/cross-spawn-promise": "^2.0.0",
        "debug": "^4.3.1",
        "dir-compare": "^4.2.0",
        "fs-extra": "^11.1.1",
        "minimatch": "^9.0.3",
        "plist": "^3.1.0"
      },
      "engines": {
        "node": ">=16.4"
      }
    },
    "node_modules/@electron/universal/node_modules/balanced-match": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/balanced-match/-/balanced-match-1.0.2.tgz",
      "integrity": "sha512-3oSeUO0TMV67hN1AmbXsK4yaqU7tjiHlbxRDZOpH0KW9+CeX4bRAaX0Anxt0tx2MrpRpWwQaPwIlISEJhYU5Pw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@electron/universal/node_modules/brace-expansion": {
      "version": "2.0.2",
      "resolved": "https://registry.npmmirror.com/brace-expansion/-/brace-expansion-2.0.2.tgz",
      "integrity": "sha512-Jt0vHyM+jmUBqojB7E1NIYadt0vI0Qxjxd2TErW94wDz+E2LAm5vKMXXwg6ZZBTHPuUlDgQHKXvjGBdfcF1ZDQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "balanced-match": "^1.0.0"
      }
    },
    "node_modules/@electron/universal/node_modules/fs-extra": {
      "version": "11.3.4",
      "resolved": "https://registry.npmmirror.com/fs-extra/-/fs-extra-11.3.4.tgz",
      "integrity": "sha512-CTXd6rk/M3/ULNQj8FBqBWHYBVYybQ3VPBw0xGKFe3tuH7ytT6ACnvzpIQ3UZtB8yvUKC2cXn1a+x+5EVQLovA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "graceful-fs": "^4.2.0",
        "jsonfile": "^6.0.1",
        "universalify": "^2.0.0"
      },
      "engines": {
        "node": ">=14.14"
      }
    },
    "node_modules/@electron/universal/node_modules/jsonfile": {
      "version": "6.2.0",
      "resolved": "https://registry.npmmirror.com/jsonfile/-/jsonfile-6.2.0.tgz",
      "integrity": "sha512-FGuPw30AdOIUTRMC2OMRtQV+jkVj2cfPqSeWXv1NEAJ1qZ5zb1X6z1mFhbfOB/iy3ssJCD+3KuZ8r8C3uVFlAg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "universalify": "^2.0.0"
      },
      "optionalDependencies": {
        "graceful-fs": "^4.1.6"
      }
    },
    "node_modules/@electron/universal/node_modules/minimatch": {
      "version": "9.0.9",
      "resolved": "https://registry.npmmirror.com/minimatch/-/minimatch-9.0.9.tgz",
      "integrity": "sha512-OBwBN9AL4dqmETlpS2zasx+vTeWclWzkblfZk7KTA5j3jeOONz/tRCnZomUyvNg83wL5Zv9Ss6HMJXAgL8R2Yg==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "brace-expansion": "^2.0.2"
      },
      "engines": {
        "node": ">=16 || 14 >=14.17"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/@electron/universal/node_modules/universalify": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/universalify/-/universalify-2.0.1.tgz",
      "integrity": "sha512-gptHNQghINnc/vTGIk0SOFGFNXw7JVrlRUtConJRlvaw6DuX0wO5Jeko9sWrMBhh+PsYAZ7oXAiOnf/UKogyiw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 10.0.0"
      }
    },
    "node_modules/@electron/windows-sign": {
      "version": "1.2.2",
      "resolved": "https://registry.npmmirror.com/@electron/windows-sign/-/windows-sign-1.2.2.tgz",
      "integrity": "sha512-dfZeox66AvdPtb2lD8OsIIQh12Tp0GNCRUDfBHIKGpbmopZto2/A8nSpYYLoedPIHpqkeblZ/k8OV0Gy7PYuyQ==",
      "dev": true,
      "license": "BSD-2-Clause",
      "optional": true,
      "peer": true,
      "dependencies": {
        "cross-dirname": "^0.1.0",
        "debug": "^4.3.4",
        "fs-extra": "^11.1.1",
        "minimist": "^1.2.8",
        "postject": "^1.0.0-alpha.6"
      },
      "bin": {
        "electron-windows-sign": "bin/electron-windows-sign.js"
      },
      "engines": {
        "node": ">=14.14"
      }
    },
    "node_modules/@electron/windows-sign/node_modules/fs-extra": {
      "version": "11.3.4",
      "resolved": "https://registry.npmmirror.com/fs-extra/-/fs-extra-11.3.4.tgz",
      "integrity": "sha512-CTXd6rk/M3/ULNQj8FBqBWHYBVYybQ3VPBw0xGKFe3tuH7ytT6ACnvzpIQ3UZtB8yvUKC2cXn1a+x+5EVQLovA==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "peer": true,
      "dependencies": {
        "graceful-fs": "^4.2.0",
        "jsonfile": "^6.0.1",
        "universalify": "^2.0.0"
      },
      "engines": {
        "node": ">=14.14"
      }
    },
    "node_modules/@electron/windows-sign/node_modules/jsonfile": {
      "version": "6.2.0",
      "resolved": "https://registry.npmmirror.com/jsonfile/-/jsonfile-6.2.0.tgz",
      "integrity": "sha512-FGuPw30AdOIUTRMC2OMRtQV+jkVj2cfPqSeWXv1NEAJ1qZ5zb1X6z1mFhbfOB/iy3ssJCD+3KuZ8r8C3uVFlAg==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "peer": true,
      "dependencies": {
        "universalify": "^2.0.0"
      },
      "optionalDependencies": {
        "graceful-fs": "^4.1.6"
      }
    },
    "node_modules/@electron/windows-sign/node_modules/universalify": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/universalify/-/universalify-2.0.1.tgz",
      "integrity": "sha512-gptHNQghINnc/vTGIk0SOFGFNXw7JVrlRUtConJRlvaw6DuX0wO5Jeko9sWrMBhh+PsYAZ7oXAiOnf/UKogyiw==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "peer": true,
      "engines": {
        "node": ">= 10.0.0"
      }
    },
    "node_modules/@esbuild/aix-ppc64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/aix-ppc64/-/aix-ppc64-0.25.12.tgz",
      "integrity": "sha512-Hhmwd6CInZ3dwpuGTF8fJG6yoWmsToE+vYgD4nytZVxcu1ulHpUQRAB1UJ8+N1Am3Mz4+xOByoQoSZf4D+CpkA==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "aix"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-arm": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/android-arm/-/android-arm-0.25.12.tgz",
      "integrity": "sha512-VJ+sKvNA/GE7Ccacc9Cha7bpS8nyzVv0jdVgwNDaR4gDMC/2TTRc33Ip8qrNYUcpkOHUT5OZ0bUcNNVZQ9RLlg==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/android-arm64/-/android-arm64-0.25.12.tgz",
      "integrity": "sha512-6AAmLG7zwD1Z159jCKPvAxZd4y/VTO0VkprYy+3N2FtJ8+BQWFXU+OxARIwA46c5tdD9SsKGZ/1ocqBS/gAKHg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/android-x64/-/android-x64-0.25.12.tgz",
      "integrity": "sha512-5jbb+2hhDHx5phYR2By8GTWEzn6I9UqR11Kwf22iKbNpYrsmRB18aX/9ivc5cabcUiAT/wM+YIZ6SG9QO6a8kg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/darwin-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/darwin-arm64/-/darwin-arm64-0.25.12.tgz",
      "integrity": "sha512-N3zl+lxHCifgIlcMUP5016ESkeQjLj/959RxxNYIthIg+CQHInujFuXeWbWMgnTo4cp5XVHqFPmpyu9J65C1Yg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/darwin-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/darwin-x64/-/darwin-x64-0.25.12.tgz",
      "integrity": "sha512-HQ9ka4Kx21qHXwtlTUVbKJOAnmG1ipXhdWTmNXiPzPfWKpXqASVcWdnf2bnL73wgjNrFXAa3yYvBSd9pzfEIpA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/freebsd-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/freebsd-arm64/-/freebsd-arm64-0.25.12.tgz",
      "integrity": "sha512-gA0Bx759+7Jve03K1S0vkOu5Lg/85dou3EseOGUes8flVOGxbhDDh/iZaoek11Y8mtyKPGF3vP8XhnkDEAmzeg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/freebsd-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/freebsd-x64/-/freebsd-x64-0.25.12.tgz",
      "integrity": "sha512-TGbO26Yw2xsHzxtbVFGEXBFH0FRAP7gtcPE7P5yP7wGy7cXK2oO7RyOhL5NLiqTlBh47XhmIUXuGciXEqYFfBQ==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-arm": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/linux-arm/-/linux-arm-0.25.12.tgz",
      "integrity": "sha512-lPDGyC1JPDou8kGcywY0YILzWlhhnRjdof3UlcoqYmS9El818LLfJJc3PXXgZHrHCAKs/Z2SeZtDJr5MrkxtOw==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/linux-arm64/-/linux-arm64-0.25.12.tgz",
      "integrity": "sha512-8bwX7a8FghIgrupcxb4aUmYDLp8pX06rGh5HqDT7bB+8Rdells6mHvrFHHW2JAOPZUbnjUpKTLg6ECyzvas2AQ==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-ia32": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/linux-ia32/-/linux-ia32-0.25.12.tgz",
      "integrity": "sha512-0y9KrdVnbMM2/vG8KfU0byhUN+EFCny9+8g202gYqSSVMonbsCfLjUO+rCci7pM0WBEtz+oK/PIwHkzxkyharA==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-loong64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/linux-loong64/-/linux-loong64-0.25.12.tgz",
      "integrity": "sha512-h///Lr5a9rib/v1GGqXVGzjL4TMvVTv+s1DPoxQdz7l/AYv6LDSxdIwzxkrPW438oUXiDtwM10o9PmwS/6Z0Ng==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-mips64el": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/linux-mips64el/-/linux-mips64el-0.25.12.tgz",
      "integrity": "sha512-iyRrM1Pzy9GFMDLsXn1iHUm18nhKnNMWscjmp4+hpafcZjrr2WbT//d20xaGljXDBYHqRcl8HnxbX6uaA/eGVw==",
      "cpu": [
        "mips64el"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-ppc64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/linux-ppc64/-/linux-ppc64-0.25.12.tgz",
      "integrity": "sha512-9meM/lRXxMi5PSUqEXRCtVjEZBGwB7P/D4yT8UG/mwIdze2aV4Vo6U5gD3+RsoHXKkHCfSxZKzmDssVlRj1QQA==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-riscv64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/linux-riscv64/-/linux-riscv64-0.25.12.tgz",
      "integrity": "sha512-Zr7KR4hgKUpWAwb1f3o5ygT04MzqVrGEGXGLnj15YQDJErYu/BGg+wmFlIDOdJp0PmB0lLvxFIOXZgFRrdjR0w==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-s390x": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/linux-s390x/-/linux-s390x-0.25.12.tgz",
      "integrity": "sha512-MsKncOcgTNvdtiISc/jZs/Zf8d0cl/t3gYWX8J9ubBnVOwlk65UIEEvgBORTiljloIWnBzLs4qhzPkJcitIzIg==",
      "cpu": [
        "s390x"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/linux-x64/-/linux-x64-0.25.12.tgz",
      "integrity": "sha512-uqZMTLr/zR/ed4jIGnwSLkaHmPjOjJvnm6TVVitAa08SLS9Z0VM8wIRx7gWbJB5/J54YuIMInDquWyYvQLZkgw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/netbsd-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/netbsd-arm64/-/netbsd-arm64-0.25.12.tgz",
      "integrity": "sha512-xXwcTq4GhRM7J9A8Gv5boanHhRa/Q9KLVmcyXHCTaM4wKfIpWkdXiMog/KsnxzJ0A1+nD+zoecuzqPmCRyBGjg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "netbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/netbsd-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/netbsd-x64/-/netbsd-x64-0.25.12.tgz",
      "integrity": "sha512-Ld5pTlzPy3YwGec4OuHh1aCVCRvOXdH8DgRjfDy/oumVovmuSzWfnSJg+VtakB9Cm0gxNO9BzWkj6mtO1FMXkQ==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "netbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openbsd-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/openbsd-arm64/-/openbsd-arm64-0.25.12.tgz",
      "integrity": "sha512-fF96T6KsBo/pkQI950FARU9apGNTSlZGsv1jZBAlcLL1MLjLNIWPBkj5NlSz8aAzYKg+eNqknrUJ24QBybeR5A==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openbsd-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/openbsd-x64/-/openbsd-x64-0.25.12.tgz",
      "integrity": "sha512-MZyXUkZHjQxUvzK7rN8DJ3SRmrVrke8ZyRusHlP+kuwqTcfWLyqMOE3sScPPyeIXN/mDJIfGXvcMqCgYKekoQw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openharmony-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/openharmony-arm64/-/openharmony-arm64-0.25.12.tgz",
      "integrity": "sha512-rm0YWsqUSRrjncSXGA7Zv78Nbnw4XL6/dzr20cyrQf7ZmRcsovpcRBdhD43Nuk3y7XIoW2OxMVvwuRvk9XdASg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openharmony"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/sunos-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/sunos-x64/-/sunos-x64-0.25.12.tgz",
      "integrity": "sha512-3wGSCDyuTHQUzt0nV7bocDy72r2lI33QL3gkDNGkod22EsYl04sMf0qLb8luNKTOmgF/eDEDP5BFNwoBKH441w==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "sunos"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-arm64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/win32-arm64/-/win32-arm64-0.25.12.tgz",
      "integrity": "sha512-rMmLrur64A7+DKlnSuwqUdRKyd3UE7oPJZmnljqEptesKM8wx9J8gx5u0+9Pq0fQQW8vqeKebwNXdfOyP+8Bsg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-ia32": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/win32-ia32/-/win32-ia32-0.25.12.tgz",
      "integrity": "sha512-HkqnmmBoCbCwxUKKNPBixiWDGCpQGVsrQfJoVGYLPT41XWF8lHuE5N6WhVia2n4o5QK5M4tYr21827fNhi4byQ==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-x64": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/@esbuild/win32-x64/-/win32-x64-0.25.12.tgz",
      "integrity": "sha512-alJC0uCZpTFrSL0CCDjcgleBXPnCrEAhTBILpeAp7M/OFgoqtAetfBzX0xM00MUsVVPpVjlPuMbREqnZCXaTnA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@hapi/address": {
      "version": "5.1.1",
      "resolved": "https://registry.npmmirror.com/@hapi/address/-/address-5.1.1.tgz",
      "integrity": "sha512-A+po2d/dVoY7cYajycYI43ZbYMXukuopIsqCjh5QzsBCipDtdofHntljDlpccMjIfTy6UOkg+5KPriwYch2bXA==",
      "dev": true,
      "license": "BSD-3-Clause",
      "dependencies": {
        "@hapi/hoek": "^11.0.2"
      },
      "engines": {
        "node": ">=14.0.0"
      }
    },
    "node_modules/@hapi/formula": {
      "version": "3.0.2",
      "resolved": "https://registry.npmmirror.com/@hapi/formula/-/formula-3.0.2.tgz",
      "integrity": "sha512-hY5YPNXzw1He7s0iqkRQi+uMGh383CGdyyIGYtB+W5N3KHPXoqychklvHhKCC9M3Xtv0OCs/IHw+r4dcHtBYWw==",
      "dev": true,
      "license": "BSD-3-Clause"
    },
    "node_modules/@hapi/hoek": {
      "version": "11.0.7",
      "resolved": "https://registry.npmmirror.com/@hapi/hoek/-/hoek-11.0.7.tgz",
      "integrity": "sha512-HV5undWkKzcB4RZUusqOpcgxOaq6VOAH7zhhIr2g3G8NF/MlFO75SjOr2NfuSx0Mh40+1FqCkagKLJRykUWoFQ==",
      "dev": true,
      "license": "BSD-3-Clause"
    },
    "node_modules/@hapi/pinpoint": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/@hapi/pinpoint/-/pinpoint-2.0.1.tgz",
      "integrity": "sha512-EKQmr16tM8s16vTT3cA5L0kZZcTMU5DUOZTuvpnY738m+jyP3JIUj+Mm1xc1rsLkGBQ/gVnfKYPwOmPg1tUR4Q==",
      "dev": true,
      "license": "BSD-3-Clause"
    },
    "node_modules/@hapi/tlds": {
      "version": "1.1.6",
      "resolved": "https://registry.npmmirror.com/@hapi/tlds/-/tlds-1.1.6.tgz",
      "integrity": "sha512-xdi7A/4NZokvV0ewovme3aUO5kQhW9pQ2YD1hRqZGhhSi5rBv4usHYidVocXSi9eihYsznZxLtAiEYYUL6VBGw==",
      "dev": true,
      "license": "BSD-3-Clause",
      "engines": {
        "node": ">=14.0.0"
      }
    },
    "node_modules/@hapi/topo": {
      "version": "6.0.2",
      "resolved": "https://registry.npmmirror.com/@hapi/topo/-/topo-6.0.2.tgz",
      "integrity": "sha512-KR3rD5inZbGMrHmgPxsJ9dbi6zEK+C3ZwUwTa+eMwWLz7oijWUTWD2pMSNNYJAU6Qq+65NkxXjqHr/7LM2Xkqg==",
      "dev": true,
      "license": "BSD-3-Clause",
      "dependencies": {
        "@hapi/hoek": "^11.0.2"
      }
    },
    "node_modules/@isaacs/cliui": {
      "version": "8.0.2",
      "resolved": "https://registry.npmmirror.com/@isaacs/cliui/-/cliui-8.0.2.tgz",
      "integrity": "sha512-O8jcjabXaleOG9DQ0+ARXWZBTfnP4WNAqzuiJK7ll44AmxGKv/J2M4TPjxjY3znBCfvBXFzucm1twdyFybFqEA==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "string-width": "^5.1.2",
        "string-width-cjs": "npm:string-width@^4.2.0",
        "strip-ansi": "^7.0.1",
        "strip-ansi-cjs": "npm:strip-ansi@^6.0.1",
        "wrap-ansi": "^8.1.0",
        "wrap-ansi-cjs": "npm:wrap-ansi@^7.0.0"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/@isaacs/cliui/node_modules/ansi-regex": {
      "version": "6.2.2",
      "resolved": "https://registry.npmmirror.com/ansi-regex/-/ansi-regex-6.2.2.tgz",
      "integrity": "sha512-Bq3SmSpyFHaWjPk8If9yc6svM8c56dB5BAtW4Qbw5jHTwwXXcTLoRMkpDJp6VL0XzlWaCHTXrkFURMYmD0sLqg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=12"
      },
      "funding": {
        "url": "https://github.com/chalk/ansi-regex?sponsor=1"
      }
    },
    "node_modules/@isaacs/cliui/node_modules/ansi-styles": {
      "version": "6.2.3",
      "resolved": "https://registry.npmmirror.com/ansi-styles/-/ansi-styles-6.2.3.tgz",
      "integrity": "sha512-4Dj6M28JB+oAH8kFkTLUo+a2jwOFkuqb3yucU0CANcRRUbxS0cP0nZYCGjcc3BNXwRIsUVmDGgzawme7zvJHvg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=12"
      },
      "funding": {
        "url": "https://github.com/chalk/ansi-styles?sponsor=1"
      }
    },
    "node_modules/@isaacs/cliui/node_modules/emoji-regex": {
      "version": "9.2.2",
      "resolved": "https://registry.npmmirror.com/emoji-regex/-/emoji-regex-9.2.2.tgz",
      "integrity": "sha512-L18DaJsXSUk2+42pv8mLs5jJT2hqFkFE4j21wOmgbUqsZ2hL72NsUU785g9RXgo3s0ZNgVl42TiHp3ZtOv/Vyg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@isaacs/cliui/node_modules/string-width": {
      "version": "5.1.2",
      "resolved": "https://registry.npmmirror.com/string-width/-/string-width-5.1.2.tgz",
      "integrity": "sha512-HnLOCR3vjcY8beoNLtcjZ5/nxn2afmME6lhrDrebokqMap+XbeW8n9TXpPDOqdGK5qcI3oT0GKTW6wC7EMiVqA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "eastasianwidth": "^0.2.0",
        "emoji-regex": "^9.2.2",
        "strip-ansi": "^7.0.1"
      },
      "engines": {
        "node": ">=12"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/@isaacs/cliui/node_modules/strip-ansi": {
      "version": "7.2.0",
      "resolved": "https://registry.npmmirror.com/strip-ansi/-/strip-ansi-7.2.0.tgz",
      "integrity": "sha512-yDPMNjp4WyfYBkHnjIRLfca1i6KMyGCtsVgoKe/z1+6vukgaENdgGBZt+ZmKPc4gavvEZ5OgHfHdrazhgNyG7w==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "ansi-regex": "^6.2.2"
      },
      "engines": {
        "node": ">=12"
      },
      "funding": {
        "url": "https://github.com/chalk/strip-ansi?sponsor=1"
      }
    },
    "node_modules/@isaacs/cliui/node_modules/wrap-ansi": {
      "version": "8.1.0",
      "resolved": "https://registry.npmmirror.com/wrap-ansi/-/wrap-ansi-8.1.0.tgz",
      "integrity": "sha512-si7QWI6zUMq56bESFvagtmzMdGOtoxfR+Sez11Mobfc7tm+VkUckk9bW2UeffTGVUbOksxmSw0AA2gs8g71NCQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "ansi-styles": "^6.1.0",
        "string-width": "^5.0.1",
        "strip-ansi": "^7.0.1"
      },
      "engines": {
        "node": ">=12"
      },
      "funding": {
        "url": "https://github.com/chalk/wrap-ansi?sponsor=1"
      }
    },
    "node_modules/@isaacs/fs-minipass": {
      "version": "4.0.1",
      "resolved": "https://registry.npmmirror.com/@isaacs/fs-minipass/-/fs-minipass-4.0.1.tgz",
      "integrity": "sha512-wgm9Ehl2jpeqP3zw/7mo3kRHFp5MEDhqAdwy1fTGkHAwnkGOVsgpvQhL8B5n1qlb01jV3n/bI0ZfZp5lWA1k4w==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "minipass": "^7.0.4"
      },
      "engines": {
        "node": ">=18.0.0"
      }
    },
    "node_modules/@jridgewell/gen-mapping": {
      "version": "0.3.13",
      "resolved": "https://registry.npmmirror.com/@jridgewell/gen-mapping/-/gen-mapping-0.3.13.tgz",
      "integrity": "sha512-2kkt/7niJ6MgEPxF0bYdQ6etZaA+fQvDcLKckhy1yIQOzaoKjBBjSj63/aLVjYE3qhRt5dvM+uUyfCg6UKCBbA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@jridgewell/sourcemap-codec": "^1.5.0",
        "@jridgewell/trace-mapping": "^0.3.24"
      }
    },
    "node_modules/@jridgewell/remapping": {
      "version": "2.3.5",
      "resolved": "https://registry.npmmirror.com/@jridgewell/remapping/-/remapping-2.3.5.tgz",
      "integrity": "sha512-LI9u/+laYG4Ds1TDKSJW2YPrIlcVYOwi2fUC6xB43lueCjgxV4lffOCZCtYFiH6TNOX+tQKXx97T4IKHbhyHEQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@jridgewell/gen-mapping": "^0.3.5",
        "@jridgewell/trace-mapping": "^0.3.24"
      }
    },
    "node_modules/@jridgewell/resolve-uri": {
      "version": "3.1.2",
      "resolved": "https://registry.npmmirror.com/@jridgewell/resolve-uri/-/resolve-uri-3.1.2.tgz",
      "integrity": "sha512-bRISgCIjP20/tbWSPWMEi54QVPRZExkuD9lJL+UIxUKtwVJA8wW1Trb1jMs1RFXo1CBTNZ/5hpC9QvmKWdopKw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@jridgewell/sourcemap-codec": {
      "version": "1.5.5",
      "resolved": "https://registry.npmmirror.com/@jridgewell/sourcemap-codec/-/sourcemap-codec-1.5.5.tgz",
      "integrity": "sha512-cYQ9310grqxueWbl+WuIUIaiUaDcj7WOq5fVhEljNVgRfOUhY9fy2zTvfoqWsnebh8Sl70VScFbICvJnLKB0Og==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@jridgewell/trace-mapping": {
      "version": "0.3.31",
      "resolved": "https://registry.npmmirror.com/@jridgewell/trace-mapping/-/trace-mapping-0.3.31.tgz",
      "integrity": "sha512-zzNR+SdQSDJzc8joaeP8QQoCQr8NuYx2dIIytl1QeBEZHJ9uW6hebsrYgbz8hJwUQao3TWCMtmfV8Nu1twOLAw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@jridgewell/resolve-uri": "^3.1.0",
        "@jridgewell/sourcemap-codec": "^1.4.14"
      }
    },
    "node_modules/@malept/cross-spawn-promise": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/@malept/cross-spawn-promise/-/cross-spawn-promise-2.0.0.tgz",
      "integrity": "sha512-1DpKU0Z5ThltBwjNySMC14g0CkbyhCaz9FkhxqNsZI6uAPJXFS8cMXlBKo26FJ8ZuW6S9GCMcR9IO5k2X5/9Fg==",
      "dev": true,
      "funding": [
        {
          "type": "individual",
          "url": "https://github.com/sponsors/malept"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/subscription/pkg/npm-.malept-cross-spawn-promise?utm_medium=referral&utm_source=npm_fund"
        }
      ],
      "license": "Apache-2.0",
      "dependencies": {
        "cross-spawn": "^7.0.1"
      },
      "engines": {
        "node": ">= 12.13.0"
      }
    },
    "node_modules/@malept/flatpak-bundler": {
      "version": "0.4.0",
      "resolved": "https://registry.npmmirror.com/@malept/flatpak-bundler/-/flatpak-bundler-0.4.0.tgz",
      "integrity": "sha512-9QOtNffcOF/c1seMCDnjckb3R9WHcG34tky+FHpNKKCW0wc/scYLwMtO+ptyGUfMW0/b/n4qRiALlaFHc9Oj7Q==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "debug": "^4.1.1",
        "fs-extra": "^9.0.0",
        "lodash": "^4.17.15",
        "tmp-promise": "^3.0.2"
      },
      "engines": {
        "node": ">= 10.0.0"
      }
    },
    "node_modules/@malept/flatpak-bundler/node_modules/fs-extra": {
      "version": "9.1.0",
      "resolved": "https://registry.npmmirror.com/fs-extra/-/fs-extra-9.1.0.tgz",
      "integrity": "sha512-hcg3ZmepS30/7BSFqRvoo3DOMQu7IjqxO5nCDt+zM9XWjb33Wg7ziNT+Qvqbuc3+gWpzO02JubVyk2G4Zvo1OQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "at-least-node": "^1.0.0",
        "graceful-fs": "^4.2.0",
        "jsonfile": "^6.0.1",
        "universalify": "^2.0.0"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/@malept/flatpak-bundler/node_modules/jsonfile": {
      "version": "6.2.0",
      "resolved": "https://registry.npmmirror.com/jsonfile/-/jsonfile-6.2.0.tgz",
      "integrity": "sha512-FGuPw30AdOIUTRMC2OMRtQV+jkVj2cfPqSeWXv1NEAJ1qZ5zb1X6z1mFhbfOB/iy3ssJCD+3KuZ8r8C3uVFlAg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "universalify": "^2.0.0"
      },
      "optionalDependencies": {
        "graceful-fs": "^4.1.6"
      }
    },
    "node_modules/@malept/flatpak-bundler/node_modules/universalify": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/universalify/-/universalify-2.0.1.tgz",
      "integrity": "sha512-gptHNQghINnc/vTGIk0SOFGFNXw7JVrlRUtConJRlvaw6DuX0wO5Jeko9sWrMBhh+PsYAZ7oXAiOnf/UKogyiw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 10.0.0"
      }
    },
    "node_modules/@nodelib/fs.scandir": {
      "version": "2.1.5",
      "resolved": "https://registry.npmmirror.com/@nodelib/fs.scandir/-/fs.scandir-2.1.5.tgz",
      "integrity": "sha512-vq24Bq3ym5HEQm2NKCr3yXDwjc7vTsEThRDnkp2DK9p1uqLR+DHurm/NOTo0KG7HYHU7eppKZj3MyqYuMBf62g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@nodelib/fs.stat": "2.0.5",
        "run-parallel": "^1.1.9"
      },
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/@nodelib/fs.stat": {
      "version": "2.0.5",
      "resolved": "https://registry.npmmirror.com/@nodelib/fs.stat/-/fs.stat-2.0.5.tgz",
      "integrity": "sha512-RkhPPp2zrqDAQA/2jNhnztcPAlv64XdhIp7a7454A5ovI7Bukxgt7MX7udwAu3zg1DcpPU0rz3VV1SeaqvY4+A==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/@nodelib/fs.walk": {
      "version": "1.2.8",
      "resolved": "https://registry.npmmirror.com/@nodelib/fs.walk/-/fs.walk-1.2.8.tgz",
      "integrity": "sha512-oGB+UxlgWcgQkgwo8GcEGwemoTFt3FIO9ababBmaGwXIoBKZ+GTy0pP185beGg7Llih/NSHSV2XAs1lnznocSg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@nodelib/fs.scandir": "2.1.5",
        "fastq": "^1.6.0"
      },
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/@npmcli/agent": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/@npmcli/agent/-/agent-3.0.0.tgz",
      "integrity": "sha512-S79NdEgDQd/NGCay6TCoVzXSj74skRZIKJcpJjC5lOq34SZzyI6MqtiiWoiVWoVrTcGjNeC4ipbh1VIHlpfF5Q==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "agent-base": "^7.1.0",
        "http-proxy-agent": "^7.0.0",
        "https-proxy-agent": "^7.0.1",
        "lru-cache": "^10.0.1",
        "socks-proxy-agent": "^8.0.3"
      },
      "engines": {
        "node": "^18.17.0 || >=20.5.0"
      }
    },
    "node_modules/@npmcli/agent/node_modules/lru-cache": {
      "version": "10.4.3",
      "resolved": "https://registry.npmmirror.com/lru-cache/-/lru-cache-10.4.3.tgz",
      "integrity": "sha512-JNAzZcXrCt42VGLuYz0zfAzDfAvJWW6AfYlDBQyDV5DClI2m5sAmK+OIO7s59XfsRsWHp02jAJrRadPRGTt6SQ==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/@npmcli/fs": {
      "version": "4.0.0",
      "resolved": "https://registry.npmmirror.com/@npmcli/fs/-/fs-4.0.0.tgz",
      "integrity": "sha512-/xGlezI6xfGO9NwuJlnwz/K14qD1kCSAGtacBHnGzeAIuJGazcp45KP5NuyARXoKb7cwulAGWVsbeSxdG/cb0Q==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "semver": "^7.3.5"
      },
      "engines": {
        "node": "^18.17.0 || >=20.5.0"
      }
    },
    "node_modules/@npmcli/fs/node_modules/semver": {
      "version": "7.7.4",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-7.7.4.tgz",
      "integrity": "sha512-vFKC2IEtQnVhpT78h1Yp8wzwrf8CM+MzKMHGJZfBtzhZNycRFnXsHk6E5TxIkkMsgNS7mdX3AGB7x2QM2di4lA==",
      "dev": true,
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/@pkgjs/parseargs": {
      "version": "0.11.0",
      "resolved": "https://registry.npmmirror.com/@pkgjs/parseargs/-/parseargs-0.11.0.tgz",
      "integrity": "sha512-+1VkjdD0QBLPodGrJUeqarH8VAIvQODIbwh9XpP5Syisf7YoQgsJKPNFoqqLQlu+VQ/tVSshMR6loPMn8U+dPg==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "engines": {
        "node": ">=14"
      }
    },
    "node_modules/@rolldown/pluginutils": {
      "version": "1.0.0-beta.27",
      "resolved": "https://registry.npmmirror.com/@rolldown/pluginutils/-/pluginutils-1.0.0-beta.27.tgz",
      "integrity": "sha512-+d0F4MKMCbeVUJwG96uQ4SgAznZNSq93I3V+9NHA4OpvqG8mRCpGdKmK8l/dl02h2CCDHwW2FqilnTyDcAnqjA==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@rollup/rollup-android-arm-eabi": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-android-arm-eabi/-/rollup-android-arm-eabi-4.59.0.tgz",
      "integrity": "sha512-upnNBkA6ZH2VKGcBj9Fyl9IGNPULcjXRlg0LLeaioQWueH30p6IXtJEbKAgvyv+mJaMxSm1l6xwDXYjpEMiLMg==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ]
    },
    "node_modules/@rollup/rollup-android-arm64": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-android-arm64/-/rollup-android-arm64-4.59.0.tgz",
      "integrity": "sha512-hZ+Zxj3SySm4A/DylsDKZAeVg0mvi++0PYVceVyX7hemkw7OreKdCvW2oQ3T1FMZvCaQXqOTHb8qmBShoqk69Q==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ]
    },
    "node_modules/@rollup/rollup-darwin-arm64": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-darwin-arm64/-/rollup-darwin-arm64-4.59.0.tgz",
      "integrity": "sha512-W2Psnbh1J8ZJw0xKAd8zdNgF9HRLkdWwwdWqubSVk0pUuQkoHnv7rx4GiF9rT4t5DIZGAsConRE3AxCdJ4m8rg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ]
    },
    "node_modules/@rollup/rollup-darwin-x64": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-darwin-x64/-/rollup-darwin-x64-4.59.0.tgz",
      "integrity": "sha512-ZW2KkwlS4lwTv7ZVsYDiARfFCnSGhzYPdiOU4IM2fDbL+QGlyAbjgSFuqNRbSthybLbIJ915UtZBtmuLrQAT/w==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ]
    },
    "node_modules/@rollup/rollup-freebsd-arm64": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-freebsd-arm64/-/rollup-freebsd-arm64-4.59.0.tgz",
      "integrity": "sha512-EsKaJ5ytAu9jI3lonzn3BgG8iRBjV4LxZexygcQbpiU0wU0ATxhNVEpXKfUa0pS05gTcSDMKpn3Sx+QB9RlTTA==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ]
    },
    "node_modules/@rollup/rollup-freebsd-x64": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-freebsd-x64/-/rollup-freebsd-x64-4.59.0.tgz",
      "integrity": "sha512-d3DuZi2KzTMjImrxoHIAODUZYoUUMsuUiY4SRRcJy6NJoZ6iIqWnJu9IScV9jXysyGMVuW+KNzZvBLOcpdl3Vg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm-gnueabihf": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-arm-gnueabihf/-/rollup-linux-arm-gnueabihf-4.59.0.tgz",
      "integrity": "sha512-t4ONHboXi/3E0rT6OZl1pKbl2Vgxf9vJfWgmUoCEVQVxhW6Cw/c8I6hbbu7DAvgp82RKiH7TpLwxnJeKv2pbsw==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm-musleabihf": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-arm-musleabihf/-/rollup-linux-arm-musleabihf-4.59.0.tgz",
      "integrity": "sha512-CikFT7aYPA2ufMD086cVORBYGHffBo4K8MQ4uPS/ZnY54GKj36i196u8U+aDVT2LX4eSMbyHtyOh7D7Zvk2VvA==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm64-gnu": {
      "version": "4.60.1",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm64-gnu/-/rollup-linux-arm64-gnu-4.60.1.tgz",
      "integrity": "sha512-Nql7sTeAzhTAja3QXeAI48+/+GjBJ+QmAH13snn0AJSNL50JsDqotyudHyMbO2RbJkskbMbFJfIJKWA6R1LCJQ==",
      "cpu": [
        "arm64"
      ],
      "license": "MIT",
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm64-musl": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-arm64-musl/-/rollup-linux-arm64-musl-4.59.0.tgz",
      "integrity": "sha512-peZRVEdnFWZ5Bh2KeumKG9ty7aCXzzEsHShOZEFiCQlDEepP1dpUl/SrUNXNg13UmZl+gzVDPsiCwnV1uI0RUA==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-loong64-gnu": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-loong64-gnu/-/rollup-linux-loong64-gnu-4.59.0.tgz",
      "integrity": "sha512-gbUSW/97f7+r4gHy3Jlup8zDG190AuodsWnNiXErp9mT90iCy9NKKU0Xwx5k8VlRAIV2uU9CsMnEFg/xXaOfXg==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-loong64-musl": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-loong64-musl/-/rollup-linux-loong64-musl-4.59.0.tgz",
      "integrity": "sha512-yTRONe79E+o0FWFijasoTjtzG9EBedFXJMl888NBEDCDV9I2wGbFFfJQQe63OijbFCUZqxpHz1GzpbtSFikJ4Q==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-ppc64-gnu": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-ppc64-gnu/-/rollup-linux-ppc64-gnu-4.59.0.tgz",
      "integrity": "sha512-sw1o3tfyk12k3OEpRddF68a1unZ5VCN7zoTNtSn2KndUE+ea3m3ROOKRCZxEpmT9nsGnogpFP9x6mnLTCaoLkA==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-ppc64-musl": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-ppc64-musl/-/rollup-linux-ppc64-musl-4.59.0.tgz",
      "integrity": "sha512-+2kLtQ4xT3AiIxkzFVFXfsmlZiG5FXYW7ZyIIvGA7Bdeuh9Z0aN4hVyXS/G1E9bTP/vqszNIN/pUKCk/BTHsKA==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-riscv64-gnu": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-riscv64-gnu/-/rollup-linux-riscv64-gnu-4.59.0.tgz",
      "integrity": "sha512-NDYMpsXYJJaj+I7UdwIuHHNxXZ/b/N2hR15NyH3m2qAtb/hHPA4g4SuuvrdxetTdndfj9b1WOmy73kcPRoERUg==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-riscv64-musl": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-riscv64-musl/-/rollup-linux-riscv64-musl-4.59.0.tgz",
      "integrity": "sha512-nLckB8WOqHIf1bhymk+oHxvM9D3tyPndZH8i8+35p/1YiVoVswPid2yLzgX7ZJP0KQvnkhM4H6QZ5m0LzbyIAg==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-s390x-gnu": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-s390x-gnu/-/rollup-linux-s390x-gnu-4.59.0.tgz",
      "integrity": "sha512-oF87Ie3uAIvORFBpwnCvUzdeYUqi2wY6jRFWJAy1qus/udHFYIkplYRW+wo+GRUP4sKzYdmE1Y3+rY5Gc4ZO+w==",
      "cpu": [
        "s390x"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-x64-gnu": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-x64-gnu/-/rollup-linux-x64-gnu-4.59.0.tgz",
      "integrity": "sha512-3AHmtQq/ppNuUspKAlvA8HtLybkDflkMuLK4DPo77DfthRb71V84/c4MlWJXixZz4uruIH4uaa07IqoAkG64fg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-x64-musl": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-x64-musl/-/rollup-linux-x64-musl-4.59.0.tgz",
      "integrity": "sha512-2UdiwS/9cTAx7qIUZB/fWtToJwvt0Vbo0zmnYt7ED35KPg13Q0ym1g442THLC7VyI6JfYTP4PiSOWyoMdV2/xg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-openbsd-x64": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-openbsd-x64/-/rollup-openbsd-x64-4.59.0.tgz",
      "integrity": "sha512-M3bLRAVk6GOwFlPTIxVBSYKUaqfLrn8l0psKinkCFxl4lQvOSz8ZrKDz2gxcBwHFpci0B6rttydI4IpS4IS/jQ==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openbsd"
      ]
    },
    "node_modules/@rollup/rollup-openharmony-arm64": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-openharmony-arm64/-/rollup-openharmony-arm64-4.59.0.tgz",
      "integrity": "sha512-tt9KBJqaqp5i5HUZzoafHZX8b5Q2Fe7UjYERADll83O4fGqJ49O1FsL6LpdzVFQcpwvnyd0i+K/VSwu/o/nWlA==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openharmony"
      ]
    },
    "node_modules/@rollup/rollup-win32-arm64-msvc": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-win32-arm64-msvc/-/rollup-win32-arm64-msvc-4.59.0.tgz",
      "integrity": "sha512-V5B6mG7OrGTwnxaNUzZTDTjDS7F75PO1ae6MJYdiMu60sq0CqN5CVeVsbhPxalupvTX8gXVSU9gq+Rx1/hvu6A==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@rollup/rollup-win32-ia32-msvc": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-win32-ia32-msvc/-/rollup-win32-ia32-msvc-4.59.0.tgz",
      "integrity": "sha512-UKFMHPuM9R0iBegwzKF4y0C4J9u8C6MEJgFuXTBerMk7EJ92GFVFYBfOZaSGLu6COf7FxpQNqhNS4c4icUPqxA==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@rollup/rollup-win32-x64-gnu": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-win32-x64-gnu/-/rollup-win32-x64-gnu-4.59.0.tgz",
      "integrity": "sha512-laBkYlSS1n2L8fSo1thDNGrCTQMmxjYY5G0WFWjFFYZkKPjsMBsgJfGf4TLxXrF6RyhI60L8TMOjBMvXiTcxeA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@rollup/rollup-win32-x64-msvc": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/@rollup/rollup-win32-x64-msvc/-/rollup-win32-x64-msvc-4.59.0.tgz",
      "integrity": "sha512-2HRCml6OztYXyJXAvdDXPKcawukWY2GpR5/nxKp4iBgiO3wcoEGkAaqctIbZcNB6KlUQBIqt8VYkNSj2397EfA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@sindresorhus/is": {
      "version": "4.6.0",
      "resolved": "https://registry.npmmirror.com/@sindresorhus/is/-/is-4.6.0.tgz",
      "integrity": "sha512-t09vSN3MdfsyCHoFcTRCH/iUtG7OJ0CsjzB8cjAmKc/va/kIgeDI/TxsigdncE/4be734m0cvIYwNaV4i2XqAw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sindresorhus/is?sponsor=1"
      }
    },
    "node_modules/@standard-schema/spec": {
      "version": "1.1.0",
      "resolved": "https://registry.npmmirror.com/@standard-schema/spec/-/spec-1.1.0.tgz",
      "integrity": "sha512-l2aFy5jALhniG5HgqrD6jXLi/rUWrKvqN/qJx6yoJsgKhblVd+iqqU4RCXavm/jPityDo5TCvKMnpjKnOriy0w==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@szmarczak/http-timer": {
      "version": "4.0.6",
      "resolved": "https://registry.npmmirror.com/@szmarczak/http-timer/-/http-timer-4.0.6.tgz",
      "integrity": "sha512-4BAffykYOgO+5nzBWYwE3W90sBgLJoUPRWWcL8wlyiM8IB8ipJz3UMJ9KXQd1RKQXpKp8Tutn80HZtWsu2u76w==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "defer-to-connect": "^2.0.0"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/@tailwindcss/typography": {
      "version": "0.5.19",
      "resolved": "https://registry.npmmirror.com/@tailwindcss/typography/-/typography-0.5.19.tgz",
      "integrity": "sha512-w31dd8HOx3k9vPtcQh5QHP9GwKcgbMp87j58qi6xgiBnFFtKEAgCWnDw4qUT8aHwkCp8bKvb/KGKWWHedP0AAg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "postcss-selector-parser": "6.0.10"
      },
      "peerDependencies": {
        "tailwindcss": ">=3.0.0 || insiders || >=4.0.0-alpha.20 || >=4.0.0-beta.1"
      }
    },
    "node_modules/@types/babel__core": {
      "version": "7.20.5",
      "resolved": "https://registry.npmmirror.com/@types/babel__core/-/babel__core-7.20.5.tgz",
      "integrity": "sha512-qoQprZvz5wQFJwMDqeseRXWv3rqMvhgpbXFfVyWhbx9X47POIA6i/+dXefEmZKoAgOaTdaIgNSMqMIU61yRyzA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/parser": "^7.20.7",
        "@babel/types": "^7.20.7",
        "@types/babel__generator": "*",
        "@types/babel__template": "*",
        "@types/babel__traverse": "*"
      }
    },
    "node_modules/@types/babel__generator": {
      "version": "7.27.0",
      "resolved": "https://registry.npmmirror.com/@types/babel__generator/-/babel__generator-7.27.0.tgz",
      "integrity": "sha512-ufFd2Xi92OAVPYsy+P4n7/U7e68fex0+Ee8gSG9KX7eo084CWiQ4sdxktvdl0bOPupXtVJPY19zk6EwWqUQ8lg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.0.0"
      }
    },
    "node_modules/@types/babel__template": {
      "version": "7.4.4",
      "resolved": "https://registry.npmmirror.com/@types/babel__template/-/babel__template-7.4.4.tgz",
      "integrity": "sha512-h/NUaSyG5EyxBIp8YRxo4RMe2/qQgvyowRwVMzhYhBCONbW8PUsg4lkFMrhgZhUe5z3L3MiLDuvyJ/CaPa2A8A==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/parser": "^7.1.0",
        "@babel/types": "^7.0.0"
      }
    },
    "node_modules/@types/babel__traverse": {
      "version": "7.28.0",
      "resolved": "https://registry.npmmirror.com/@types/babel__traverse/-/babel__traverse-7.28.0.tgz",
      "integrity": "sha512-8PvcXf70gTDZBgt9ptxJ8elBeBjcLOAcOtoO/mPJjtji1+CdGbHgm77om1GrsPxsiE+uXIpNSK64UYaIwQXd4Q==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.28.2"
      }
    },
    "node_modules/@types/cacheable-request": {
      "version": "6.0.3",
      "resolved": "https://registry.npmmirror.com/@types/cacheable-request/-/cacheable-request-6.0.3.tgz",
      "integrity": "sha512-IQ3EbTzGxIigb1I3qPZc1rWJnH0BmSKv5QYTalEwweFvyBDLSAe24zP0le/hyi7ecGfZVlIVAg4BZqb8WBwKqw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@types/http-cache-semantics": "*",
        "@types/keyv": "^3.1.4",
        "@types/node": "*",
        "@types/responselike": "^1.0.0"
      }
    },
    "node_modules/@types/debug": {
      "version": "4.1.12",
      "resolved": "https://registry.npmmirror.com/@types/debug/-/debug-4.1.12.tgz",
      "integrity": "sha512-vIChWdVG3LG1SMxEvI/AK+FWJthlrqlTu7fbrlywTkkaONwk/UAGaULXRlf8vkzFBLVm0zkMdCquhL5aOjhXPQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@types/ms": "*"
      }
    },
    "node_modules/@types/estree": {
      "version": "1.0.8",
      "resolved": "https://registry.npmmirror.com/@types/estree/-/estree-1.0.8.tgz",
      "integrity": "sha512-dWHzHa2WqEXI/O1E9OjrocMTKJl2mSrEolh1Iomrv6U+JuNwaHXsXx9bLu5gG7BUWFIN0skIQJQ/L1rIex4X6w==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@types/fs-extra": {
      "version": "9.0.13",
      "resolved": "https://registry.npmmirror.com/@types/fs-extra/-/fs-extra-9.0.13.tgz",
      "integrity": "sha512-nEnwB++1u5lVDM2UI4c1+5R+FYaKfaAzS4OococimjVm3nQw3TuzH5UNsocrcTBbhnerblyHj4A49qXbIiZdpA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@types/node": "*"
      }
    },
    "node_modules/@types/http-cache-semantics": {
      "version": "4.2.0",
      "resolved": "https://registry.npmmirror.com/@types/http-cache-semantics/-/http-cache-semantics-4.2.0.tgz",
      "integrity": "sha512-L3LgimLHXtGkWikKnsPg0/VFx9OGZaC+eN1u4r+OB1XRqH3meBIAVC2zr1WdMH+RHmnRkqliQAOHNJ/E0j/e0Q==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@types/keyv": {
      "version": "3.1.4",
      "resolved": "https://registry.npmmirror.com/@types/keyv/-/keyv-3.1.4.tgz",
      "integrity": "sha512-BQ5aZNSCpj7D6K2ksrRCTmKRLEpnPvWDiLPfoGyhZ++8YtiK9d/3DBKPJgry359X/P1PfruyYwvnvwFjuEiEIg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@types/node": "*"
      }
    },
    "node_modules/@types/ms": {
      "version": "2.1.0",
      "resolved": "https://registry.npmmirror.com/@types/ms/-/ms-2.1.0.tgz",
      "integrity": "sha512-GsCCIZDE/p3i96vtEqx+7dBUGXrc7zeSK3wwPHIaRThS+9OhWIXRqzs4d6k1SVU8g91DrNRWxWUGhp5KXQb2VA==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@types/node": {
      "version": "22.19.15",
      "resolved": "https://registry.npmmirror.com/@types/node/-/node-22.19.15.tgz",
      "integrity": "sha512-F0R/h2+dsy5wJAUe3tAU6oqa2qbWY5TpNfL/RGmo1y38hiyO1w3x2jPtt76wmuaJI4DQnOBu21cNXQ2STIUUWg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "undici-types": "~6.21.0"
      }
    },
    "node_modules/@types/plist": {
      "version": "3.0.5",
      "resolved": "https://registry.npmmirror.com/@types/plist/-/plist-3.0.5.tgz",
      "integrity": "sha512-E6OCaRmAe4WDmWNsL/9RMqdkkzDCY1etutkflWk4c+AcjDU07Pcz1fQwTX0TQz+Pxqn9i4L1TU3UFpjnrcDgxA==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "dependencies": {
        "@types/node": "*",
        "xmlbuilder": ">=11.0.1"
      }
    },
    "node_modules/@types/prop-types": {
      "version": "15.7.15",
      "resolved": "https://registry.npmmirror.com/@types/prop-types/-/prop-types-15.7.15.tgz",
      "integrity": "sha512-F6bEyamV9jKGAFBEmlQnesRPGOQqS2+Uwi0Em15xenOxHaf2hv6L8YCVn3rPdPJOiJfPiCnLIRyvwVaqMY3MIw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@types/react": {
      "version": "18.3.28",
      "resolved": "https://registry.npmmirror.com/@types/react/-/react-18.3.28.tgz",
      "integrity": "sha512-z9VXpC7MWrhfWipitjNdgCauoMLRdIILQsAEV+ZesIzBq/oUlxk0m3ApZuMFCXdnS4U7KrI+l3WRUEGQ8K1QKw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@types/prop-types": "*",
        "csstype": "^3.2.2"
      }
    },
    "node_modules/@types/react-dom": {
      "version": "18.3.7",
      "resolved": "https://registry.npmmirror.com/@types/react-dom/-/react-dom-18.3.7.tgz",
      "integrity": "sha512-MEe3UeoENYVFXzoXEWsvcpg6ZvlrFNlOQ7EOsvhI3CfAXwzPfO8Qwuxd40nepsYKqyyVQnTdEfv68q91yLcKrQ==",
      "dev": true,
      "license": "MIT",
      "peerDependencies": {
        "@types/react": "^18.0.0"
      }
    },
    "node_modules/@types/responselike": {
      "version": "1.0.3",
      "resolved": "https://registry.npmmirror.com/@types/responselike/-/responselike-1.0.3.tgz",
      "integrity": "sha512-H/+L+UkTV33uf49PH5pCAUBVPNj2nDBXTN+qS1dOwyyg24l3CcicicCA7ca+HMvJBZcFgl5r8e+RR6elsb4Lyw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@types/node": "*"
      }
    },
    "node_modules/@types/verror": {
      "version": "1.10.11",
      "resolved": "https://registry.npmmirror.com/@types/verror/-/verror-1.10.11.tgz",
      "integrity": "sha512-RlDm9K7+o5stv0Co8i8ZRGxDbrTxhJtgjqjFyVh/tXQyl/rYtTKlnTvZ88oSTeYREWurwx20Js4kTuKCsFkUtg==",
      "dev": true,
      "license": "MIT",
      "optional": true
    },
    "node_modules/@types/yauzl": {
      "version": "2.10.3",
      "resolved": "https://registry.npmmirror.com/@types/yauzl/-/yauzl-2.10.3.tgz",
      "integrity": "sha512-oJoftv0LSuaDZE3Le4DbKX+KS9G36NzOeSap90UIK0yMA/NhKJhqlSGtNDORNRaIbQfzjXDrQa0ytJ6mNRGz/Q==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "dependencies": {
        "@types/node": "*"
      }
    },
    "node_modules/@vitejs/plugin-react": {
      "version": "4.7.0",
      "resolved": "https://registry.npmmirror.com/@vitejs/plugin-react/-/plugin-react-4.7.0.tgz",
      "integrity": "sha512-gUu9hwfWvvEDBBmgtAowQCojwZmJ5mcLn3aufeCsitijs3+f2NsrPtlAWIR6OPiqljl96GVCUbLe0HyqIpVaoA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/core": "^7.28.0",
        "@babel/plugin-transform-react-jsx-self": "^7.27.1",
        "@babel/plugin-transform-react-jsx-source": "^7.27.1",
        "@rolldown/pluginutils": "1.0.0-beta.27",
        "@types/babel__core": "^7.20.5",
        "react-refresh": "^0.17.0"
      },
      "engines": {
        "node": "^14.18.0 || >=16.0.0"
      },
      "peerDependencies": {
        "vite": "^4.2.0 || ^5.0.0 || ^6.0.0 || ^7.0.0"
      }
    },
    "node_modules/@xmldom/xmldom": {
      "version": "0.8.11",
      "resolved": "https://registry.npmmirror.com/@xmldom/xmldom/-/xmldom-0.8.11.tgz",
      "integrity": "sha512-cQzWCtO6C8TQiYl1ruKNn2U6Ao4o4WBBcbL61yJl84x+j5sOWWFU9X7DpND8XZG3daDppSsigMdfAIl2upQBRw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=10.0.0"
      }
    },
    "node_modules/7zip-bin": {
      "version": "5.2.0",
      "resolved": "https://registry.npmmirror.com/7zip-bin/-/7zip-bin-5.2.0.tgz",
      "integrity": "sha512-ukTPVhqG4jNzMro2qA9HSCSSVJN3aN7tlb+hfqYCt3ER0yWroeA2VR38MNrOHLQ/cVj+DaIMad0kFCtWWowh/A==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/abbrev": {
      "version": "3.0.1",
      "resolved": "https://registry.npmmirror.com/abbrev/-/abbrev-3.0.1.tgz",
      "integrity": "sha512-AO2ac6pjRB3SJmGJo+v5/aK6Omggp6fsLrs6wN9bd35ulu4cCwaAU9+7ZhXjeqHVkaHThLuzH0nZr0YpCDhygg==",
      "dev": true,
      "license": "ISC",
      "engines": {
        "node": "^18.17.0 || >=20.5.0"
      }
    },
    "node_modules/agent-base": {
      "version": "7.1.4",
      "resolved": "https://registry.npmmirror.com/agent-base/-/agent-base-7.1.4.tgz",
      "integrity": "sha512-MnA+YT8fwfJPgBx3m60MNqakm30XOkyIoH1y6huTQvC0PwZG7ki8NacLBcrPbNoo8vEZy7Jpuk7+jMO+CUovTQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 14"
      }
    },
    "node_modules/ajv": {
      "version": "6.14.0",
      "resolved": "https://registry.npmmirror.com/ajv/-/ajv-6.14.0.tgz",
      "integrity": "sha512-IWrosm/yrn43eiKqkfkHis7QioDleaXQHdDVPKg0FSwwd/DuvyX79TZnFOnYpB7dcsFAMmtFztZuXPDvSePkFw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "fast-deep-equal": "^3.1.1",
        "fast-json-stable-stringify": "^2.0.0",
        "json-schema-traverse": "^0.4.1",
        "uri-js": "^4.2.2"
      },
      "funding": {
        "type": "github",
        "url": "https://github.com/sponsors/epoberezkin"
      }
    },
    "node_modules/ajv-keywords": {
      "version": "3.5.2",
      "resolved": "https://registry.npmmirror.com/ajv-keywords/-/ajv-keywords-3.5.2.tgz",
      "integrity": "sha512-5p6WTN0DdTGVQk6VjcEju19IgaHudalcfabD7yhDGeA6bcQnmL+CpveLJq/3hvfwd1aof6L386Ougkx6RfyMIQ==",
      "dev": true,
      "license": "MIT",
      "peerDependencies": {
        "ajv": "^6.9.1"
      }
    },
    "node_modules/ansi-regex": {
      "version": "5.0.1",
      "resolved": "https://registry.npmmirror.com/ansi-regex/-/ansi-regex-5.0.1.tgz",
      "integrity": "sha512-quJQXlTSUGL2LH9SUXo8VwsY4soanhgo6LNSm84E1LBcE8s3O0wpdiRzyR9z/ZZJMlMWv37qOOb9pdJlMUEKFQ==",
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/ansi-styles": {
      "version": "4.3.0",
      "resolved": "https://registry.npmmirror.com/ansi-styles/-/ansi-styles-4.3.0.tgz",
      "integrity": "sha512-zbB9rCJAT1rbjiVDb2hqKFHNYLxgtk8NURxZ3IZwD3F6NtxbXZQCnnSi1Lkx+IDohdPlFp222wVALIheZJQSEg==",
      "license": "MIT",
      "dependencies": {
        "color-convert": "^2.0.1"
      },
      "engines": {
        "node": ">=8"
      },
      "funding": {
        "url": "https://github.com/chalk/ansi-styles?sponsor=1"
      }
    },
    "node_modules/any-promise": {
      "version": "1.3.0",
      "resolved": "https://registry.npmmirror.com/any-promise/-/any-promise-1.3.0.tgz",
      "integrity": "sha512-7UvmKalWRt1wgjL1RrGxoSJW/0QZFIegpeGvZG9kjp8vrRu55XTHbwnqq2GpXm9uLbcuhxm3IqX9OB4MZR1b2A==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/anymatch": {
      "version": "3.1.3",
      "resolved": "https://registry.npmmirror.com/anymatch/-/anymatch-3.1.3.tgz",
      "integrity": "sha512-KMReFUr0B4t+D+OBkjR3KYqvocp2XaSzO55UcB6mgQMd3KbcE+mWTyvVV7D/zsdEbNnV6acZUutkiHQXvTr1Rw==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "normalize-path": "^3.0.0",
        "picomatch": "^2.0.4"
      },
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/anymatch/node_modules/picomatch": {
      "version": "2.3.1",
      "resolved": "https://registry.npmmirror.com/picomatch/-/picomatch-2.3.1.tgz",
      "integrity": "sha512-JU3teHTNjmE2VCGFzuY8EXzCDVwEqB2a8fsIvwaStHhAWJEeVd1o1QD80CU6+ZdEXXSLbSsuLwJjkCBWqRQUVA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=8.6"
      },
      "funding": {
        "url": "https://github.com/sponsors/jonschlinkert"
      }
    },
    "node_modules/app-builder-bin": {
      "version": "5.0.0-alpha.12",
      "resolved": "https://registry.npmmirror.com/app-builder-bin/-/app-builder-bin-5.0.0-alpha.12.tgz",
      "integrity": "sha512-j87o0j6LqPL3QRr8yid6c+Tt5gC7xNfYo6uQIQkorAC6MpeayVMZrEDzKmJJ/Hlv7EnOQpaRm53k6ktDYZyB6w==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/app-builder-lib": {
      "version": "26.8.1",
      "resolved": "https://registry.npmmirror.com/app-builder-lib/-/app-builder-lib-26.8.1.tgz",
      "integrity": "sha512-p0Im/Dx5C4tmz8QEE1Yn4MkuPC8PrnlRneMhWJj7BBXQfNTJUshM/bp3lusdEsDbvvfJZpXWnYesgSLvwtM2Zw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@develar/schema-utils": "~2.6.5",
        "@electron/asar": "3.4.1",
        "@electron/fuses": "^1.8.0",
        "@electron/get": "^3.0.0",
        "@electron/notarize": "2.5.0",
        "@electron/osx-sign": "1.3.3",
        "@electron/rebuild": "^4.0.3",
        "@electron/universal": "2.0.3",
        "@malept/flatpak-bundler": "^0.4.0",
        "@types/fs-extra": "9.0.13",
        "async-exit-hook": "^2.0.1",
        "builder-util": "26.8.1",
        "builder-util-runtime": "9.5.1",
        "chromium-pickle-js": "^0.2.0",
        "ci-info": "4.3.1",
        "debug": "^4.3.4",
        "dotenv": "^16.4.5",
        "dotenv-expand": "^11.0.6",
        "ejs": "^3.1.8",
        "electron-publish": "26.8.1",
        "fs-extra": "^10.1.0",
        "hosted-git-info": "^4.1.0",
        "isbinaryfile": "^5.0.0",
        "jiti": "^2.4.2",
        "js-yaml": "^4.1.0",
        "json5": "^2.2.3",
        "lazy-val": "^1.0.5",
        "minimatch": "^10.0.3",
        "plist": "3.1.0",
        "proper-lockfile": "^4.1.2",
        "resedit": "^1.7.0",
        "semver": "~7.7.3",
        "tar": "^7.5.7",
        "temp-file": "^3.4.0",
        "tiny-async-pool": "1.3.0",
        "which": "^5.0.0"
      },
      "engines": {
        "node": ">=14.0.0"
      },
      "peerDependencies": {
        "dmg-builder": "26.8.1",
        "electron-builder-squirrel-windows": "26.8.1"
      }
    },
    "node_modules/app-builder-lib/node_modules/@electron/get": {
      "version": "3.1.0",
      "resolved": "https://registry.npmmirror.com/@electron/get/-/get-3.1.0.tgz",
      "integrity": "sha512-F+nKc0xW+kVbBRhFzaMgPy3KwmuNTYX1fx6+FxxoSnNgwYX6LD7AKBTWkU0MQ6IBoe7dz069CNkR673sPAgkCQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "debug": "^4.1.1",
        "env-paths": "^2.2.0",
        "fs-extra": "^8.1.0",
        "got": "^11.8.5",
        "progress": "^2.0.3",
        "semver": "^6.2.0",
        "sumchecker": "^3.0.1"
      },
      "engines": {
        "node": ">=14"
      },
      "optionalDependencies": {
        "global-agent": "^3.0.0"
      }
    },
    "node_modules/app-builder-lib/node_modules/@electron/get/node_modules/fs-extra": {
      "version": "8.1.0",
      "resolved": "https://registry.npmmirror.com/fs-extra/-/fs-extra-8.1.0.tgz",
      "integrity": "sha512-yhlQgA6mnOJUKOsRUFsgJdQCvkKhcz8tlZG5HBQfReYZy46OwLcY+Zia0mtdHsOo9y/hP+CxMN0TU9QxoOtG4g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "graceful-fs": "^4.2.0",
        "jsonfile": "^4.0.0",
        "universalify": "^0.1.0"
      },
      "engines": {
        "node": ">=6 <7 || >=8"
      }
    },
    "node_modules/app-builder-lib/node_modules/@electron/get/node_modules/semver": {
      "version": "6.3.1",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-6.3.1.tgz",
      "integrity": "sha512-BR7VvDCVHO+q2xBEWskxS6DJE1qRnb7DxzUrogb71CWoSficBxYsiAGd+Kl0mmq/MprG9yArRkyrQxTO6XjMzA==",
      "dev": true,
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      }
    },
    "node_modules/app-builder-lib/node_modules/ci-info": {
      "version": "4.3.1",
      "resolved": "https://registry.npmmirror.com/ci-info/-/ci-info-4.3.1.tgz",
      "integrity": "sha512-Wdy2Igu8OcBpI2pZePZ5oWjPC38tmDVx5WKUXKwlLYkA0ozo85sLsLvkBbBn/sZaSCMFOGZJ14fvW9t5/d7kdA==",
      "dev": true,
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/sibiraj-s"
        }
      ],
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/app-builder-lib/node_modules/fs-extra": {
      "version": "10.1.0",
      "resolved": "https://registry.npmmirror.com/fs-extra/-/fs-extra-10.1.0.tgz",
      "integrity": "sha512-oRXApq54ETRj4eMiFzGnHWGy+zo5raudjuxN0b8H7s/RU2oW0Wvsx9O0ACRN/kRq9E8Vu/ReskGB5o3ji+FzHQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "graceful-fs": "^4.2.0",
        "jsonfile": "^6.0.1",
        "universalify": "^2.0.0"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/app-builder-lib/node_modules/fs-extra/node_modules/jsonfile": {
      "version": "6.2.0",
      "resolved": "https://registry.npmmirror.com/jsonfile/-/jsonfile-6.2.0.tgz",
      "integrity": "sha512-FGuPw30AdOIUTRMC2OMRtQV+jkVj2cfPqSeWXv1NEAJ1qZ5zb1X6z1mFhbfOB/iy3ssJCD+3KuZ8r8C3uVFlAg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "universalify": "^2.0.0"
      },
      "optionalDependencies": {
        "graceful-fs": "^4.1.6"
      }
    },
    "node_modules/app-builder-lib/node_modules/fs-extra/node_modules/universalify": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/universalify/-/universalify-2.0.1.tgz",
      "integrity": "sha512-gptHNQghINnc/vTGIk0SOFGFNXw7JVrlRUtConJRlvaw6DuX0wO5Jeko9sWrMBhh+PsYAZ7oXAiOnf/UKogyiw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 10.0.0"
      }
    },
    "node_modules/app-builder-lib/node_modules/isexe": {
      "version": "3.1.5",
      "resolved": "https://registry.npmmirror.com/isexe/-/isexe-3.1.5.tgz",
      "integrity": "sha512-6B3tLtFqtQS4ekarvLVMZ+X+VlvQekbe4taUkf/rhVO3d/h0M2rfARm/pXLcPEsjjMsFgrFgSrhQIxcSVrBz8w==",
      "dev": true,
      "license": "BlueOak-1.0.0",
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/app-builder-lib/node_modules/semver": {
      "version": "7.7.4",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-7.7.4.tgz",
      "integrity": "sha512-vFKC2IEtQnVhpT78h1Yp8wzwrf8CM+MzKMHGJZfBtzhZNycRFnXsHk6E5TxIkkMsgNS7mdX3AGB7x2QM2di4lA==",
      "dev": true,
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/app-builder-lib/node_modules/which": {
      "version": "5.0.0",
      "resolved": "https://registry.npmmirror.com/which/-/which-5.0.0.tgz",
      "integrity": "sha512-JEdGzHwwkrbWoGOlIHqQ5gtprKGOenpDHpxE9zVR1bWbOtYRyPPHMe9FaP6x61CmNaTThSkb0DAJte5jD+DmzQ==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "isexe": "^3.1.1"
      },
      "bin": {
        "node-which": "bin/which.js"
      },
      "engines": {
        "node": "^18.17.0 || >=20.5.0"
      }
    },
    "node_modules/arg": {
      "version": "5.0.2",
      "resolved": "https://registry.npmmirror.com/arg/-/arg-5.0.2.tgz",
      "integrity": "sha512-PYjyFOLKQ9y57JvQ6QLo8dAgNqswh8M1RMJYdQduT6xbWSgK36P/Z/v+p888pM69jMMfS8Xd8F6I1kQ/I9HUGg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/argparse": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/argparse/-/argparse-2.0.1.tgz",
      "integrity": "sha512-8+9WqebbFzpX9OR+Wa6O29asIogeRMzcGtAINdpMHHyAg10f05aSFVBbcEqGf/PXw1EjAZ+q2/bEBg3DvurK3Q==",
      "dev": true,
      "license": "Python-2.0"
    },
    "node_modules/assert-plus": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/assert-plus/-/assert-plus-1.0.0.tgz",
      "integrity": "sha512-NfJ4UzBCcQGLDlQq7nHxH+tv3kyZ0hHQqF5BO6J7tNJeP5do1llPr8dZ8zHonfhAu0PHAdMkSo+8o0wxg9lZWw==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "engines": {
        "node": ">=0.8"
      }
    },
    "node_modules/astral-regex": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/astral-regex/-/astral-regex-2.0.0.tgz",
      "integrity": "sha512-Z7tMw1ytTXt5jqMcOP+OQteU1VuNK9Y02uuJtKQ1Sv69jXQKKg5cibLwGJow8yzZP+eAc18EmLGPal0bp36rvQ==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/async": {
      "version": "3.2.6",
      "resolved": "https://registry.npmmirror.com/async/-/async-3.2.6.tgz",
      "integrity": "sha512-htCUDlxyyCLMgaM3xXg0C0LW2xqfuQ6p05pCEIsXuyQ+a1koYKTuBMzRNwmybfLgvJDMd0r1LTn4+E0Ti6C2AA==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/async-exit-hook": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/async-exit-hook/-/async-exit-hook-2.0.1.tgz",
      "integrity": "sha512-NW2cX8m1Q7KPA7a5M2ULQeZ2wR5qI5PAbw5L0UOMxdioVk9PMZ0h1TmyZEkPYrCvYjDlFICusOu1dlEKAAeXBw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.12.0"
      }
    },
    "node_modules/asynckit": {
      "version": "0.4.0",
      "resolved": "https://registry.npmmirror.com/asynckit/-/asynckit-0.4.0.tgz",
      "integrity": "sha512-Oei9OH4tRh0YqU3GxhX79dM/mwVgvbZJaSNaRk+bshkj0S5cfHcgYakreBjrHwatXKbz+IoIdYLxrKim2MjW0Q==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/at-least-node": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/at-least-node/-/at-least-node-1.0.0.tgz",
      "integrity": "sha512-+q/t7Ekv1EDY2l6Gda6LLiX14rU9TV20Wa3ofeQmwPFZbOMo9DXrLbOjFaaclkXKWidIaopwAObQDqwWtGUjqg==",
      "dev": true,
      "license": "ISC",
      "engines": {
        "node": ">= 4.0.0"
      }
    },
    "node_modules/autoprefixer": {
      "version": "10.4.27",
      "resolved": "https://registry.npmmirror.com/autoprefixer/-/autoprefixer-10.4.27.tgz",
      "integrity": "sha512-NP9APE+tO+LuJGn7/9+cohklunJsXWiaWEfV3si4Gi/XHDwVNgkwr1J3RQYFIvPy76GmJ9/bW8vyoU1LcxwKHA==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/postcss/"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/autoprefixer"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "browserslist": "^4.28.1",
        "caniuse-lite": "^1.0.30001774",
        "fraction.js": "^5.3.4",
        "picocolors": "^1.1.1",
        "postcss-value-parser": "^4.2.0"
      },
      "bin": {
        "autoprefixer": "bin/autoprefixer"
      },
      "engines": {
        "node": "^10 || ^12 || >=14"
      },
      "peerDependencies": {
        "postcss": "^8.1.0"
      }
    },
    "node_modules/axios": {
      "version": "1.13.6",
      "resolved": "https://registry.npmmirror.com/axios/-/axios-1.13.6.tgz",
      "integrity": "sha512-ChTCHMouEe2kn713WHbQGcuYrr6fXTBiu460OTwWrWob16g1bXn4vtz07Ope7ewMozJAnEquLk5lWQWtBig9DQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "follow-redirects": "^1.15.11",
        "form-data": "^4.0.5",
        "proxy-from-env": "^1.1.0"
      }
    },
    "node_modules/balanced-match": {
      "version": "4.0.4",
      "resolved": "https://registry.npmmirror.com/balanced-match/-/balanced-match-4.0.4.tgz",
      "integrity": "sha512-BLrgEcRTwX2o6gGxGOCNyMvGSp35YofuYzw9h1IMTRmKqttAZZVU67bdb9Pr2vUHA8+j3i2tJfjO6C6+4myGTA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": "18 || 20 || >=22"
      }
    },
    "node_modules/base64-js": {
      "version": "1.5.1",
      "resolved": "https://registry.npmmirror.com/base64-js/-/base64-js-1.5.1.tgz",
      "integrity": "sha512-AKpaYlHn8t4SVbOHCy+b5+KKgvR4vrsD8vbvrbiQJps7fKDTkjkDry6ji0rUJjC0kzbNePLwzxq8iypo41qeWA==",
      "dev": true,
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/feross"
        },
        {
          "type": "patreon",
          "url": "https://www.patreon.com/feross"
        },
        {
          "type": "consulting",
          "url": "https://feross.org/support"
        }
      ],
      "license": "MIT"
    },
    "node_modules/baseline-browser-mapping": {
      "version": "2.10.0",
      "resolved": "https://registry.npmmirror.com/baseline-browser-mapping/-/baseline-browser-mapping-2.10.0.tgz",
      "integrity": "sha512-lIyg0szRfYbiy67j9KN8IyeD7q7hcmqnJ1ddWmNt19ItGpNN64mnllmxUNFIOdOm6by97jlL6wfpTTJrmnjWAA==",
      "dev": true,
      "license": "Apache-2.0",
      "bin": {
        "baseline-browser-mapping": "dist/cli.cjs"
      },
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/binary-extensions": {
      "version": "2.3.0",
      "resolved": "https://registry.npmmirror.com/binary-extensions/-/binary-extensions-2.3.0.tgz",
      "integrity": "sha512-Ceh+7ox5qe7LJuLHoY0feh3pHuUDHAcRUeyL2VYghZwfpkNIy/+8Ocg0a3UuSoYzavmylwuLWQOf3hl0jjMMIw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=8"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/bl": {
      "version": "4.1.0",
      "resolved": "https://registry.npmmirror.com/bl/-/bl-4.1.0.tgz",
      "integrity": "sha512-1W07cM9gS6DcLperZfFSj+bWLtaPGSOHWhPiGzXmvVJbRLdG82sH/Kn8EtW1VqWVA54AKf2h5k5BbnIbwF3h6w==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "buffer": "^5.5.0",
        "inherits": "^2.0.4",
        "readable-stream": "^3.4.0"
      }
    },
    "node_modules/boolean": {
      "version": "3.2.0",
      "resolved": "https://registry.npmmirror.com/boolean/-/boolean-3.2.0.tgz",
      "integrity": "sha512-d0II/GO9uf9lfUHH2BQsjxzRJZBdsjgsBiW4BvhWk/3qoKwQFjIDVN19PfX8F2D/r9PCMTtLWjYVCFrpeYUzsw==",
      "deprecated": "Package no longer supported. Contact Support at https://www.npmjs.com/support for more info.",
      "dev": true,
      "license": "MIT",
      "optional": true
    },
    "node_modules/brace-expansion": {
      "version": "5.0.4",
      "resolved": "https://registry.npmmirror.com/brace-expansion/-/brace-expansion-5.0.4.tgz",
      "integrity": "sha512-h+DEnpVvxmfVefa4jFbCf5HdH5YMDXRsmKflpf1pILZWRFlTbJpxeU55nJl4Smt5HQaGzg1o6RHFPJaOqnmBDg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "balanced-match": "^4.0.2"
      },
      "engines": {
        "node": "18 || 20 || >=22"
      }
    },
    "node_modules/braces": {
      "version": "3.0.3",
      "resolved": "https://registry.npmmirror.com/braces/-/braces-3.0.3.tgz",
      "integrity": "sha512-yQbXgO/OSZVD2IsiLlro+7Hf6Q18EJrKSEsdoMzKePKXct3gvD8oLcOQdIzGupr5Fj+EDe8gO/lxc1BzfMpxvA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "fill-range": "^7.1.1"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/browserslist": {
      "version": "4.28.1",
      "resolved": "https://registry.npmmirror.com/browserslist/-/browserslist-4.28.1.tgz",
      "integrity": "sha512-ZC5Bd0LgJXgwGqUknZY/vkUQ04r8NXnJZ3yYi4vDmSiZmC/pdSN0NbNRPxZpbtO4uAfDUAFffO8IZoM3Gj8IkA==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/browserslist"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/browserslist"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "baseline-browser-mapping": "^2.9.0",
        "caniuse-lite": "^1.0.30001759",
        "electron-to-chromium": "^1.5.263",
        "node-releases": "^2.0.27",
        "update-browserslist-db": "^1.2.0"
      },
      "bin": {
        "browserslist": "cli.js"
      },
      "engines": {
        "node": "^6 || ^7 || ^8 || ^9 || ^10 || ^11 || ^12 || >=13.7"
      }
    },
    "node_modules/buffer": {
      "version": "5.7.1",
      "resolved": "https://registry.npmmirror.com/buffer/-/buffer-5.7.1.tgz",
      "integrity": "sha512-EHcyIPBQ4BSGlvjB16k5KgAJ27CIsHY/2JBmCRReo48y9rQ3MaUzWX3KVlBa4U7MyX02HdVj0K7C3WaB3ju7FQ==",
      "dev": true,
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/feross"
        },
        {
          "type": "patreon",
          "url": "https://www.patreon.com/feross"
        },
        {
          "type": "consulting",
          "url": "https://feross.org/support"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "base64-js": "^1.3.1",
        "ieee754": "^1.1.13"
      }
    },
    "node_modules/buffer-crc32": {
      "version": "0.2.13",
      "resolved": "https://registry.npmmirror.com/buffer-crc32/-/buffer-crc32-0.2.13.tgz",
      "integrity": "sha512-VO9Ht/+p3SN7SKWqcrgEzjGbRSJYTx+Q1pTQC0wrWqHx0vpJraQ6GtHx8tvcg1rlK1byhU5gccxgOgj7B0TDkQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": "*"
      }
    },
    "node_modules/buffer-from": {
      "version": "1.1.2",
      "resolved": "https://registry.npmmirror.com/buffer-from/-/buffer-from-1.1.2.tgz",
      "integrity": "sha512-E+XQCRwSbaaiChtv6k6Dwgc+bx+Bs6vuKJHHl5kox/BaKbhiXzqQOwK4cO22yElGp2OCmjwVhT3HmxgyPGnJfQ==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/builder-util": {
      "version": "26.8.1",
      "resolved": "https://registry.npmmirror.com/builder-util/-/builder-util-26.8.1.tgz",
      "integrity": "sha512-pm1lTYbGyc90DHgCDO7eo8Rl4EqKLciayNbZqGziqnH9jrlKe8ZANGdityLZU+pJh16dfzjAx2xQq9McuIPEtw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@types/debug": "^4.1.6",
        "7zip-bin": "~5.2.0",
        "app-builder-bin": "5.0.0-alpha.12",
        "builder-util-runtime": "9.5.1",
        "chalk": "^4.1.2",
        "cross-spawn": "^7.0.6",
        "debug": "^4.3.4",
        "fs-extra": "^10.1.0",
        "http-proxy-agent": "^7.0.0",
        "https-proxy-agent": "^7.0.0",
        "js-yaml": "^4.1.0",
        "sanitize-filename": "^1.6.3",
        "source-map-support": "^0.5.19",
        "stat-mode": "^1.0.0",
        "temp-file": "^3.4.0",
        "tiny-async-pool": "1.3.0"
      }
    },
    "node_modules/builder-util-runtime": {
      "version": "9.5.1",
      "resolved": "https://registry.npmmirror.com/builder-util-runtime/-/builder-util-runtime-9.5.1.tgz",
      "integrity": "sha512-qt41tMfgHTllhResqM5DcnHyDIWNgzHvuY2jDcYP9iaGpkWxTUzV6GQjDeLnlR1/DtdlcsWQbA7sByMpmJFTLQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "debug": "^4.3.4",
        "sax": "^1.2.4"
      },
      "engines": {
        "node": ">=12.0.0"
      }
    },
    "node_modules/builder-util/node_modules/fs-extra": {
      "version": "10.1.0",
      "resolved": "https://registry.npmmirror.com/fs-extra/-/fs-extra-10.1.0.tgz",
      "integrity": "sha512-oRXApq54ETRj4eMiFzGnHWGy+zo5raudjuxN0b8H7s/RU2oW0Wvsx9O0ACRN/kRq9E8Vu/ReskGB5o3ji+FzHQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "graceful-fs": "^4.2.0",
        "jsonfile": "^6.0.1",
        "universalify": "^2.0.0"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/builder-util/node_modules/jsonfile": {
      "version": "6.2.0",
      "resolved": "https://registry.npmmirror.com/jsonfile/-/jsonfile-6.2.0.tgz",
      "integrity": "sha512-FGuPw30AdOIUTRMC2OMRtQV+jkVj2cfPqSeWXv1NEAJ1qZ5zb1X6z1mFhbfOB/iy3ssJCD+3KuZ8r8C3uVFlAg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "universalify": "^2.0.0"
      },
      "optionalDependencies": {
        "graceful-fs": "^4.1.6"
      }
    },
    "node_modules/builder-util/node_modules/universalify": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/universalify/-/universalify-2.0.1.tgz",
      "integrity": "sha512-gptHNQghINnc/vTGIk0SOFGFNXw7JVrlRUtConJRlvaw6DuX0wO5Jeko9sWrMBhh+PsYAZ7oXAiOnf/UKogyiw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 10.0.0"
      }
    },
    "node_modules/cacache": {
      "version": "19.0.1",
      "resolved": "https://registry.npmmirror.com/cacache/-/cacache-19.0.1.tgz",
      "integrity": "sha512-hdsUxulXCi5STId78vRVYEtDAjq99ICAUktLTeTYsLoTE6Z8dS0c8pWNCxwdrk9YfJeobDZc2Y186hD/5ZQgFQ==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "@npmcli/fs": "^4.0.0",
        "fs-minipass": "^3.0.0",
        "glob": "^10.2.2",
        "lru-cache": "^10.0.1",
        "minipass": "^7.0.3",
        "minipass-collect": "^2.0.1",
        "minipass-flush": "^1.0.5",
        "minipass-pipeline": "^1.2.4",
        "p-map": "^7.0.2",
        "ssri": "^12.0.0",
        "tar": "^7.4.3",
        "unique-filename": "^4.0.0"
      },
      "engines": {
        "node": "^18.17.0 || >=20.5.0"
      }
    },
    "node_modules/cacache/node_modules/balanced-match": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/balanced-match/-/balanced-match-1.0.2.tgz",
      "integrity": "sha512-3oSeUO0TMV67hN1AmbXsK4yaqU7tjiHlbxRDZOpH0KW9+CeX4bRAaX0Anxt0tx2MrpRpWwQaPwIlISEJhYU5Pw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/cacache/node_modules/brace-expansion": {
      "version": "2.0.2",
      "resolved": "https://registry.npmmirror.com/brace-expansion/-/brace-expansion-2.0.2.tgz",
      "integrity": "sha512-Jt0vHyM+jmUBqojB7E1NIYadt0vI0Qxjxd2TErW94wDz+E2LAm5vKMXXwg6ZZBTHPuUlDgQHKXvjGBdfcF1ZDQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "balanced-match": "^1.0.0"
      }
    },
    "node_modules/cacache/node_modules/glob": {
      "version": "10.4.5",
      "resolved": "https://registry.npmmirror.com/glob/-/glob-10.4.5.tgz",
      "integrity": "sha512-7Bv8RF0k6xjo7d4A/PxYLbUCfb6c+Vpd2/mB2yRDlew7Jb5hEXiCD9ibfO7wpk8i4sevK6DFny9h7EYbM3/sHg==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "foreground-child": "^3.1.0",
        "jackspeak": "^3.1.2",
        "minimatch": "^9.0.4",
        "minipass": "^7.1.2",
        "package-json-from-dist": "^1.0.0",
        "path-scurry": "^1.11.1"
      },
      "bin": {
        "glob": "dist/esm/bin.mjs"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/cacache/node_modules/lru-cache": {
      "version": "10.4.3",
      "resolved": "https://registry.npmmirror.com/lru-cache/-/lru-cache-10.4.3.tgz",
      "integrity": "sha512-JNAzZcXrCt42VGLuYz0zfAzDfAvJWW6AfYlDBQyDV5DClI2m5sAmK+OIO7s59XfsRsWHp02jAJrRadPRGTt6SQ==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/cacache/node_modules/minimatch": {
      "version": "9.0.9",
      "resolved": "https://registry.npmmirror.com/minimatch/-/minimatch-9.0.9.tgz",
      "integrity": "sha512-OBwBN9AL4dqmETlpS2zasx+vTeWclWzkblfZk7KTA5j3jeOONz/tRCnZomUyvNg83wL5Zv9Ss6HMJXAgL8R2Yg==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "brace-expansion": "^2.0.2"
      },
      "engines": {
        "node": ">=16 || 14 >=14.17"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/cacheable-lookup": {
      "version": "5.0.4",
      "resolved": "https://registry.npmmirror.com/cacheable-lookup/-/cacheable-lookup-5.0.4.tgz",
      "integrity": "sha512-2/kNscPhpcxrOigMZzbiWF7dz8ilhb/nIHU3EyZiXWXpeq/au8qJ8VhdftMkty3n7Gj6HIGalQG8oiBNB3AJgA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=10.6.0"
      }
    },
    "node_modules/cacheable-request": {
      "version": "7.0.4",
      "resolved": "https://registry.npmmirror.com/cacheable-request/-/cacheable-request-7.0.4.tgz",
      "integrity": "sha512-v+p6ongsrp0yTGbJXjgxPow2+DL93DASP4kXCDKb8/bwRtt9OEF3whggkkDkGNzgcWy2XaF4a8nZglC7uElscg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "clone-response": "^1.0.2",
        "get-stream": "^5.1.0",
        "http-cache-semantics": "^4.0.0",
        "keyv": "^4.0.0",
        "lowercase-keys": "^2.0.0",
        "normalize-url": "^6.0.1",
        "responselike": "^2.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/call-bind-apply-helpers": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/call-bind-apply-helpers/-/call-bind-apply-helpers-1.0.2.tgz",
      "integrity": "sha512-Sp1ablJ0ivDkSzjcaJdxEunN5/XvksFJ2sMBFfq6x0ryhQV/2b/KwFe21cMpmHtPOSij8K99/wSfoEuTObmuMQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "es-errors": "^1.3.0",
        "function-bind": "^1.1.2"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/camelcase": {
      "version": "5.3.1",
      "resolved": "https://registry.npmmirror.com/camelcase/-/camelcase-5.3.1.tgz",
      "integrity": "sha512-L28STB170nwWS63UjtlEOE3dldQApaJXZkOI1uMFfzf3rRuPegHaHesyee+YxQ+W6SvRDQV6UrdOdRiR153wJg==",
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/camelcase-css": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/camelcase-css/-/camelcase-css-2.0.1.tgz",
      "integrity": "sha512-QOSvevhslijgYwRx6Rv7zKdMF8lbRmx+uQGx2+vDc+KI/eBnsy9kit5aj23AgGu3pa4t9AgwbnXWqS+iOY+2aA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/caniuse-lite": {
      "version": "1.0.30001777",
      "resolved": "https://registry.npmmirror.com/caniuse-lite/-/caniuse-lite-1.0.30001777.tgz",
      "integrity": "sha512-tmN+fJxroPndC74efCdp12j+0rk0RHwV5Jwa1zWaFVyw2ZxAuPeG8ZgWC3Wz7uSjT3qMRQ5XHZ4COgQmsCMJAQ==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/browserslist"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/caniuse-lite"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "CC-BY-4.0"
    },
    "node_modules/chalk": {
      "version": "4.1.2",
      "resolved": "https://registry.npmmirror.com/chalk/-/chalk-4.1.2.tgz",
      "integrity": "sha512-oKnbhFyRIXpUuez8iBMmyEa4nbj4IOQyuhc/wy9kY7/WVPcwIO9VA668Pu8RkO7+0G76SLROeyw9CpQ061i4mA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "ansi-styles": "^4.1.0",
        "supports-color": "^7.1.0"
      },
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/chalk/chalk?sponsor=1"
      }
    },
    "node_modules/chalk/node_modules/supports-color": {
      "version": "7.2.0",
      "resolved": "https://registry.npmmirror.com/supports-color/-/supports-color-7.2.0.tgz",
      "integrity": "sha512-qpCAvRl9stuOHveKsn7HncJRvv501qIacKzQlO/+Lwxc9+0q2wLyv4Dfvt80/DPn2pqOBsJdDiogXGR9+OvwRw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "has-flag": "^4.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/chokidar": {
      "version": "3.6.0",
      "resolved": "https://registry.npmmirror.com/chokidar/-/chokidar-3.6.0.tgz",
      "integrity": "sha512-7VT13fmjotKpGipCW9JEQAusEPE+Ei8nl6/g4FBAmIm0GOOLMua9NDDo/DWp0ZAxCr3cPq5ZpBqmPAQgDda2Pw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "anymatch": "~3.1.2",
        "braces": "~3.0.2",
        "glob-parent": "~5.1.2",
        "is-binary-path": "~2.1.0",
        "is-glob": "~4.0.1",
        "normalize-path": "~3.0.0",
        "readdirp": "~3.6.0"
      },
      "engines": {
        "node": ">= 8.10.0"
      },
      "funding": {
        "url": "https://paulmillr.com/funding/"
      },
      "optionalDependencies": {
        "fsevents": "~2.3.2"
      }
    },
    "node_modules/chokidar/node_modules/glob-parent": {
      "version": "5.1.2",
      "resolved": "https://registry.npmmirror.com/glob-parent/-/glob-parent-5.1.2.tgz",
      "integrity": "sha512-AOIgSQCepiJYwP3ARnGx+5VnTu2HBYdzbGP45eLw1vr3zB3vZLeyed1sC9hnbcOc9/SrMyM5RPQrkGz4aS9Zow==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "is-glob": "^4.0.1"
      },
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/chownr": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/chownr/-/chownr-3.0.0.tgz",
      "integrity": "sha512-+IxzY9BZOQd/XuYPRmrvEVjF/nqj5kgT4kEq7VofrDoM1MxoRjEWkrCC3EtLi59TVawxTAn+orJwFQcrqEN1+g==",
      "dev": true,
      "license": "BlueOak-1.0.0",
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/chromium-pickle-js": {
      "version": "0.2.0",
      "resolved": "https://registry.npmmirror.com/chromium-pickle-js/-/chromium-pickle-js-0.2.0.tgz",
      "integrity": "sha512-1R5Fho+jBq0DDydt+/vHWj5KJNJCKdARKOCwZUen84I5BreWoLqRLANH1U87eJy1tiASPtMnGqJJq0ZsLoRPOw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/ci-info": {
      "version": "4.4.0",
      "resolved": "https://registry.npmmirror.com/ci-info/-/ci-info-4.4.0.tgz",
      "integrity": "sha512-77PSwercCZU2Fc4sX94eF8k8Pxte6JAwL4/ICZLFjJLqegs7kCuAsqqj/70NQF6TvDpgFjkubQB2FW2ZZddvQg==",
      "dev": true,
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/sibiraj-s"
        }
      ],
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/cli-cursor": {
      "version": "3.1.0",
      "resolved": "https://registry.npmmirror.com/cli-cursor/-/cli-cursor-3.1.0.tgz",
      "integrity": "sha512-I/zHAwsKf9FqGoXM4WWRACob9+SNukZTd94DWF57E4toouRulbCxcUh6RKUEOQlYTHJnzkPMySvPNaaSLNfLZw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "restore-cursor": "^3.1.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/cli-spinners": {
      "version": "2.9.2",
      "resolved": "https://registry.npmmirror.com/cli-spinners/-/cli-spinners-2.9.2.tgz",
      "integrity": "sha512-ywqV+5MmyL4E7ybXgKys4DugZbX0FC6LnwrhjuykIjnK9k8OQacQ7axGKnjDXWNhns0xot3bZI5h55H8yo9cJg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/cli-truncate": {
      "version": "2.1.0",
      "resolved": "https://registry.npmmirror.com/cli-truncate/-/cli-truncate-2.1.0.tgz",
      "integrity": "sha512-n8fOixwDD6b/ObinzTrp1ZKFzbgvKZvuz/TvejnLn1aQfC6r52XEx85FmuC+3HI+JM7coBRXUvNqEU2PHVrHpg==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "dependencies": {
        "slice-ansi": "^3.0.0",
        "string-width": "^4.2.0"
      },
      "engines": {
        "node": ">=8"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/cliui": {
      "version": "8.0.1",
      "resolved": "https://registry.npmmirror.com/cliui/-/cliui-8.0.1.tgz",
      "integrity": "sha512-BSeNnyus75C4//NQ9gQt1/csTXyo/8Sb+afLAkzAptFuMsod9HFokGNudZpi/oQV73hnVK+sR+5PVRMd+Dr7YQ==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "string-width": "^4.2.0",
        "strip-ansi": "^6.0.1",
        "wrap-ansi": "^7.0.0"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/clone": {
      "version": "1.0.4",
      "resolved": "https://registry.npmmirror.com/clone/-/clone-1.0.4.tgz",
      "integrity": "sha512-JQHZ2QMW6l3aH/j6xCqQThY/9OH4D/9ls34cgkUBiEeocRTU04tHfKPBsUK1PqZCUQM7GiA0IIXJSuXHI64Kbg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.8"
      }
    },
    "node_modules/clone-response": {
      "version": "1.0.3",
      "resolved": "https://registry.npmmirror.com/clone-response/-/clone-response-1.0.3.tgz",
      "integrity": "sha512-ROoL94jJH2dUVML2Y/5PEDNaSHgeOdSDicUyS7izcF63G6sTc/FTjLub4b8Il9S8S0beOfYt0TaA5qvFK+w0wA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "mimic-response": "^1.0.0"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/color-convert": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/color-convert/-/color-convert-2.0.1.tgz",
      "integrity": "sha512-RRECPsj7iu/xb5oKYcsFHSppFNnsj/52OVTRKb4zP5onXwVF3zVmmToNcOfGC+CRDpfK/U584fMg38ZHCaElKQ==",
      "license": "MIT",
      "dependencies": {
        "color-name": "~1.1.4"
      },
      "engines": {
        "node": ">=7.0.0"
      }
    },
    "node_modules/color-name": {
      "version": "1.1.4",
      "resolved": "https://registry.npmmirror.com/color-name/-/color-name-1.1.4.tgz",
      "integrity": "sha512-dOy+3AuW3a2wNbZHIuMZpTcgjGuLU/uBL/ubcZF9OXbDo8ff4O8yVp5Bf0efS8uEoYo5q4Fx7dY9OgQGXgAsQA==",
      "license": "MIT"
    },
    "node_modules/combined-stream": {
      "version": "1.0.8",
      "resolved": "https://registry.npmmirror.com/combined-stream/-/combined-stream-1.0.8.tgz",
      "integrity": "sha512-FQN4MRfuJeHf7cBbBMJFXhKSDq+2kAArBlmRBvcvFE5BB1HZKXtSFASDhdlz9zOYwxh8lDdnvmMOe/+5cdoEdg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "delayed-stream": "~1.0.0"
      },
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/commander": {
      "version": "5.1.0",
      "resolved": "https://registry.npmmirror.com/commander/-/commander-5.1.0.tgz",
      "integrity": "sha512-P0CysNDQ7rtVw4QIQtm+MRxV66vKFSvlsQvGYXZWR3qFU0jlMKHZZZgw8e+8DSah4UDKMqnknRDQz+xuQXQ/Zg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/compare-version": {
      "version": "0.1.2",
      "resolved": "https://registry.npmmirror.com/compare-version/-/compare-version-0.1.2.tgz",
      "integrity": "sha512-pJDh5/4wrEnXX/VWRZvruAGHkzKdr46z11OlTPN+VrATlWWhSKewNCJ1futCO5C7eJB3nPMFZA1LeYtcFboZ2A==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/concat-map": {
      "version": "0.0.1",
      "resolved": "https://registry.npmmirror.com/concat-map/-/concat-map-0.0.1.tgz",
      "integrity": "sha512-/Srv4dswyQNBfohGpz9o6Yb3Gz3SrUDqBH5rTuhGR7ahtlbYKnVxw2bCFMRljaA7EXHaXZ8wsHdodFvbkhKmqg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/concurrently": {
      "version": "9.2.1",
      "resolved": "https://registry.npmmirror.com/concurrently/-/concurrently-9.2.1.tgz",
      "integrity": "sha512-fsfrO0MxV64Znoy8/l1vVIjjHa29SZyyqPgQBwhiDcaW8wJc2W3XWVOGx4M3oJBnv/zdUZIIp1gDeS98GzP8Ng==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "chalk": "4.1.2",
        "rxjs": "7.8.2",
        "shell-quote": "1.8.3",
        "supports-color": "8.1.1",
        "tree-kill": "1.2.2",
        "yargs": "17.7.2"
      },
      "bin": {
        "conc": "dist/bin/concurrently.js",
        "concurrently": "dist/bin/concurrently.js"
      },
      "engines": {
        "node": ">=18"
      },
      "funding": {
        "url": "https://github.com/open-cli-tools/concurrently?sponsor=1"
      }
    },
    "node_modules/convert-source-map": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/convert-source-map/-/convert-source-map-2.0.0.tgz",
      "integrity": "sha512-Kvp459HrV2FEJ1CAsi1Ku+MY3kasH19TFykTz2xWmMeq6bk2NU3XXvfJ+Q61m0xktWwt+1HSYf3JZsTms3aRJg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/core-util-is": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/core-util-is/-/core-util-is-1.0.2.tgz",
      "integrity": "sha512-3lqz5YjWTYnW6dlDa5TLaTCcShfar1e40rmcJVwCBJC6mWlFuj0eCHIElmG1g5kyuJ/GD+8Wn4FFCcz4gJPfaQ==",
      "dev": true,
      "license": "MIT",
      "optional": true
    },
    "node_modules/crc": {
      "version": "3.8.0",
      "resolved": "https://registry.npmmirror.com/crc/-/crc-3.8.0.tgz",
      "integrity": "sha512-iX3mfgcTMIq3ZKLIsVFAbv7+Mc10kxabAGQb8HvjA1o3T1PIYprbakQ65d3I+2HGHt6nSKkM9PYjgoJO2KcFBQ==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "dependencies": {
        "buffer": "^5.1.0"
      }
    },
    "node_modules/cross-dirname": {
      "version": "0.1.0",
      "resolved": "https://registry.npmmirror.com/cross-dirname/-/cross-dirname-0.1.0.tgz",
      "integrity": "sha512-+R08/oI0nl3vfPcqftZRpytksBXDzOUveBq/NBVx0sUp1axwzPQrKinNx5yd5sxPu8j1wIy8AfnVQ+5eFdha6Q==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "peer": true
    },
    "node_modules/cross-env": {
      "version": "7.0.3",
      "resolved": "https://registry.npmmirror.com/cross-env/-/cross-env-7.0.3.tgz",
      "integrity": "sha512-+/HKd6EgcQCJGh2PSjZuUitQBQynKor4wrFbRg4DtAgS1aWO+gU52xpH7M9ScGgXSYmAVS9bIJ8EzuaGw0oNAw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "cross-spawn": "^7.0.1"
      },
      "bin": {
        "cross-env": "src/bin/cross-env.js",
        "cross-env-shell": "src/bin/cross-env-shell.js"
      },
      "engines": {
        "node": ">=10.14",
        "npm": ">=6",
        "yarn": ">=1"
      }
    },
    "node_modules/cross-spawn": {
      "version": "7.0.6",
      "resolved": "https://registry.npmmirror.com/cross-spawn/-/cross-spawn-7.0.6.tgz",
      "integrity": "sha512-uV2QOWP2nWzsy2aMp8aRibhi9dlzF5Hgh5SHaB9OiTGEyDTiJJyx0uy51QXdyWbtAHNua4XJzUKca3OzKUd3vA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "path-key": "^3.1.0",
        "shebang-command": "^2.0.0",
        "which": "^2.0.1"
      },
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/cssesc": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/cssesc/-/cssesc-3.0.0.tgz",
      "integrity": "sha512-/Tb/JcjK111nNScGob5MNtsntNM1aCNUDipB/TkwZFhyDrrE47SOx/18wF2bbjgc3ZzCSKW1T5nt5EbFoAz/Vg==",
      "dev": true,
      "license": "MIT",
      "bin": {
        "cssesc": "bin/cssesc"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/csstype": {
      "version": "3.2.3",
      "resolved": "https://registry.npmmirror.com/csstype/-/csstype-3.2.3.tgz",
      "integrity": "sha512-z1HGKcYy2xA8AGQfwrn0PAy+PB7X/GSj3UVJW9qKyn43xWa+gl5nXmU4qqLMRzWVLFC8KusUX8T/0kCiOYpAIQ==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/debug": {
      "version": "4.4.3",
      "resolved": "https://registry.npmmirror.com/debug/-/debug-4.4.3.tgz",
      "integrity": "sha512-RGwwWnwQvkVfavKVt22FGLw+xYSdzARwm0ru6DhTVA3umU5hZc28V3kO4stgYryrTlLpuvgI9GiijltAjNbcqA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "ms": "^2.1.3"
      },
      "engines": {
        "node": ">=6.0"
      },
      "peerDependenciesMeta": {
        "supports-color": {
          "optional": true
        }
      }
    },
    "node_modules/decamelize": {
      "version": "1.2.0",
      "resolved": "https://registry.npmmirror.com/decamelize/-/decamelize-1.2.0.tgz",
      "integrity": "sha512-z2S+W9X73hAUUki+N+9Za2lBlun89zigOyGrsax+KUQ6wKW4ZoWpEYBkGhQjwAjjDCkWxhY0VKEhk8wzY7F5cA==",
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/decompress-response": {
      "version": "6.0.0",
      "resolved": "https://registry.npmmirror.com/decompress-response/-/decompress-response-6.0.0.tgz",
      "integrity": "sha512-aW35yZM6Bb/4oJlZncMH2LCoZtJXTRxES17vE3hoRiowU2kWHaJKFkSBDnDR+cm9J+9QhXmREyIfv0pji9ejCQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "mimic-response": "^3.1.0"
      },
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/decompress-response/node_modules/mimic-response": {
      "version": "3.1.0",
      "resolved": "https://registry.npmmirror.com/mimic-response/-/mimic-response-3.1.0.tgz",
      "integrity": "sha512-z0yWI+4FDrrweS8Zmt4Ej5HdJmky15+L2e6Wgn3+iK5fWzb6T3fhNFq2+MeTRb064c6Wr4N/wv0DzQTjNzHNGQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/defaults": {
      "version": "1.0.4",
      "resolved": "https://registry.npmmirror.com/defaults/-/defaults-1.0.4.tgz",
      "integrity": "sha512-eFuaLoy/Rxalv2kr+lqMlUnrDWV+3j4pljOIJgLIhI058IQfWJ7vXhyEIHu+HtC738klGALYxOKDO0bQP3tg8A==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "clone": "^1.0.2"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/defer-to-connect": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/defer-to-connect/-/defer-to-connect-2.0.1.tgz",
      "integrity": "sha512-4tvttepXG1VaYGrRibk5EwJd1t4udunSOVMdLSAL6mId1ix438oPwPZMALY41FCijukO1L0twNcGsdzS7dHgDg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/define-data-property": {
      "version": "1.1.4",
      "resolved": "https://registry.npmmirror.com/define-data-property/-/define-data-property-1.1.4.tgz",
      "integrity": "sha512-rBMvIzlpA8v6E+SJZoo++HAYqsLrkg7MSfIinMPFhmkorw7X+dOXVJQs+QT69zGkzMyfDnIMN2Wid1+NbL3T+A==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "dependencies": {
        "es-define-property": "^1.0.0",
        "es-errors": "^1.3.0",
        "gopd": "^1.0.1"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/define-properties": {
      "version": "1.2.1",
      "resolved": "https://registry.npmmirror.com/define-properties/-/define-properties-1.2.1.tgz",
      "integrity": "sha512-8QmQKqEASLd5nx0U1B1okLElbUuuttJ/AnYmRXbbbGDWh6uS208EjD4Xqq/I9wK7u0v6O08XhTWnt5XtEbR6Dg==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "dependencies": {
        "define-data-property": "^1.0.1",
        "has-property-descriptors": "^1.0.0",
        "object-keys": "^1.1.1"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/delayed-stream": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/delayed-stream/-/delayed-stream-1.0.0.tgz",
      "integrity": "sha512-ZySD7Nf91aLB0RxL4KGrKHBXl7Eds1DAmEdcoVawXnLD7SDhpNgtuII2aAkg7a7QS41jxPSZ17p4VdGnMHk3MQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.4.0"
      }
    },
    "node_modules/detect-libc": {
      "version": "2.1.2",
      "resolved": "https://registry.npmmirror.com/detect-libc/-/detect-libc-2.1.2.tgz",
      "integrity": "sha512-Btj2BOOO83o3WyH59e8MgXsxEQVcarkUOpEYrubB0urwnN10yQ364rsiByU11nZlqWYZm05i/of7io4mzihBtQ==",
      "dev": true,
      "license": "Apache-2.0",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/detect-node": {
      "version": "2.1.0",
      "resolved": "https://registry.npmmirror.com/detect-node/-/detect-node-2.1.0.tgz",
      "integrity": "sha512-T0NIuQpnTvFDATNuHN5roPwSBG83rFsuO+MXXH9/3N1eFbn4wcPjttvjMLEPWJ0RGUYgQE7cGgS3tNxbqCGM7g==",
      "dev": true,
      "license": "MIT",
      "optional": true
    },
    "node_modules/didyoumean": {
      "version": "1.2.2",
      "resolved": "https://registry.npmmirror.com/didyoumean/-/didyoumean-1.2.2.tgz",
      "integrity": "sha512-gxtyfqMg7GKyhQmb056K7M3xszy/myH8w+B4RT+QXBQsvAOdc3XymqDDPHx1BgPgsdAA5SIifona89YtRATDzw==",
      "dev": true,
      "license": "Apache-2.0"
    },
    "node_modules/dijkstrajs": {
      "version": "1.0.3",
      "resolved": "https://registry.npmmirror.com/dijkstrajs/-/dijkstrajs-1.0.3.tgz",
      "integrity": "sha512-qiSlmBq9+BCdCA/L46dw8Uy93mloxsPSbwnm5yrKn2vMPiy8KyAskTF6zuV/j5BMsmOGZDPs7KjU+mjb670kfA==",
      "license": "MIT"
    },
    "node_modules/dir-compare": {
      "version": "4.2.0",
      "resolved": "https://registry.npmmirror.com/dir-compare/-/dir-compare-4.2.0.tgz",
      "integrity": "sha512-2xMCmOoMrdQIPHdsTawECdNPwlVFB9zGcz3kuhmBO6U3oU+UQjsue0i8ayLKpgBcm+hcXPMVSGUN9d+pvJ6+VQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "minimatch": "^3.0.5",
        "p-limit": "^3.1.0 "
      }
    },
    "node_modules/dir-compare/node_modules/balanced-match": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/balanced-match/-/balanced-match-1.0.2.tgz",
      "integrity": "sha512-3oSeUO0TMV67hN1AmbXsK4yaqU7tjiHlbxRDZOpH0KW9+CeX4bRAaX0Anxt0tx2MrpRpWwQaPwIlISEJhYU5Pw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/dir-compare/node_modules/brace-expansion": {
      "version": "1.1.12",
      "resolved": "https://registry.npmmirror.com/brace-expansion/-/brace-expansion-1.1.12.tgz",
      "integrity": "sha512-9T9UjW3r0UW5c1Q7GTwllptXwhvYmEzFhzMfZ9H7FQWt+uZePjZPjBP/W1ZEyZ1twGWom5/56TF4lPcqjnDHcg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "balanced-match": "^1.0.0",
        "concat-map": "0.0.1"
      }
    },
    "node_modules/dir-compare/node_modules/minimatch": {
      "version": "3.1.5",
      "resolved": "https://registry.npmmirror.com/minimatch/-/minimatch-3.1.5.tgz",
      "integrity": "sha512-VgjWUsnnT6n+NUk6eZq77zeFdpW2LWDzP6zFGrCbHXiYNul5Dzqk2HHQ5uFH2DNW5Xbp8+jVzaeNt94ssEEl4w==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "brace-expansion": "^1.1.7"
      },
      "engines": {
        "node": "*"
      }
    },
    "node_modules/dlv": {
      "version": "1.1.3",
      "resolved": "https://registry.npmmirror.com/dlv/-/dlv-1.1.3.tgz",
      "integrity": "sha512-+HlytyjlPKnIG8XuRG8WvmBP8xs8P71y+SKKS6ZXWoEgLuePxtDoUEiH7WkdePWrQ5JBpE6aoVqfZfJUQkjXwA==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/dmg-builder": {
      "version": "26.8.1",
      "resolved": "https://registry.npmmirror.com/dmg-builder/-/dmg-builder-26.8.1.tgz",
      "integrity": "sha512-glMJgnTreo8CFINujtAhCgN96QAqApDMZ8Vl1r8f0QT8QprvC1UCltV4CcWj20YoIyLZx6IUskaJZ0NV8fokcg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "app-builder-lib": "26.8.1",
        "builder-util": "26.8.1",
        "fs-extra": "^10.1.0",
        "iconv-lite": "^0.6.2",
        "js-yaml": "^4.1.0"
      },
      "optionalDependencies": {
        "dmg-license": "^1.0.11"
      }
    },
    "node_modules/dmg-builder/node_modules/fs-extra": {
      "version": "10.1.0",
      "resolved": "https://registry.npmmirror.com/fs-extra/-/fs-extra-10.1.0.tgz",
      "integrity": "sha512-oRXApq54ETRj4eMiFzGnHWGy+zo5raudjuxN0b8H7s/RU2oW0Wvsx9O0ACRN/kRq9E8Vu/ReskGB5o3ji+FzHQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "graceful-fs": "^4.2.0",
        "jsonfile": "^6.0.1",
        "universalify": "^2.0.0"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/dmg-builder/node_modules/jsonfile": {
      "version": "6.2.0",
      "resolved": "https://registry.npmmirror.com/jsonfile/-/jsonfile-6.2.0.tgz",
      "integrity": "sha512-FGuPw30AdOIUTRMC2OMRtQV+jkVj2cfPqSeWXv1NEAJ1qZ5zb1X6z1mFhbfOB/iy3ssJCD+3KuZ8r8C3uVFlAg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "universalify": "^2.0.0"
      },
      "optionalDependencies": {
        "graceful-fs": "^4.1.6"
      }
    },
    "node_modules/dmg-builder/node_modules/universalify": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/universalify/-/universalify-2.0.1.tgz",
      "integrity": "sha512-gptHNQghINnc/vTGIk0SOFGFNXw7JVrlRUtConJRlvaw6DuX0wO5Jeko9sWrMBhh+PsYAZ7oXAiOnf/UKogyiw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 10.0.0"
      }
    },
    "node_modules/dmg-license": {
      "version": "1.0.11",
      "resolved": "https://registry.npmmirror.com/dmg-license/-/dmg-license-1.0.11.tgz",
      "integrity": "sha512-ZdzmqwKmECOWJpqefloC5OJy1+WZBBse5+MR88z9g9Zn4VY+WYUkAyojmhzJckH5YbbZGcYIuGAkY5/Ys5OM2Q==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "dependencies": {
        "@types/plist": "^3.0.1",
        "@types/verror": "^1.10.3",
        "ajv": "^6.10.0",
        "crc": "^3.8.0",
        "iconv-corefoundation": "^1.1.7",
        "plist": "^3.0.4",
        "smart-buffer": "^4.0.2",
        "verror": "^1.10.0"
      },
      "bin": {
        "dmg-license": "bin/dmg-license.js"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/dotenv": {
      "version": "16.6.1",
      "resolved": "https://registry.npmmirror.com/dotenv/-/dotenv-16.6.1.tgz",
      "integrity": "sha512-uBq4egWHTcTt33a72vpSG0z3HnPuIl6NqYcTrKEg2azoEyl2hpW0zqlxysq2pK9HlDIHyHyakeYaYnSAwd8bow==",
      "dev": true,
      "license": "BSD-2-Clause",
      "engines": {
        "node": ">=12"
      },
      "funding": {
        "url": "https://dotenvx.com"
      }
    },
    "node_modules/dotenv-expand": {
      "version": "11.0.7",
      "resolved": "https://registry.npmmirror.com/dotenv-expand/-/dotenv-expand-11.0.7.tgz",
      "integrity": "sha512-zIHwmZPRshsCdpMDyVsqGmgyP0yT8GAgXUnkdAoJisxvf33k7yO6OuoKmcTGuXPWSsm8Oh88nZicRLA9Y0rUeA==",
      "dev": true,
      "license": "BSD-2-Clause",
      "dependencies": {
        "dotenv": "^16.4.5"
      },
      "engines": {
        "node": ">=12"
      },
      "funding": {
        "url": "https://dotenvx.com"
      }
    },
    "node_modules/dunder-proto": {
      "version": "1.0.1",
      "resolved": "https://registry.npmmirror.com/dunder-proto/-/dunder-proto-1.0.1.tgz",
      "integrity": "sha512-KIN/nDJBQRcXw0MLVhZE9iQHmG68qAVIBg9CqmUYjmQIhgij9U5MFvrqkUL5FbtyyzZuOeOt0zdeRe4UY7ct+A==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "call-bind-apply-helpers": "^1.0.1",
        "es-errors": "^1.3.0",
        "gopd": "^1.2.0"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/eastasianwidth": {
      "version": "0.2.0",
      "resolved": "https://registry.npmmirror.com/eastasianwidth/-/eastasianwidth-0.2.0.tgz",
      "integrity": "sha512-I88TYZWc9XiYHRQ4/3c5rjjfgkjhLyW2luGIheGERbNQ6OY7yTybanSpDXZa8y7VUP9YmDcYa+eyq4ca7iLqWA==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/ejs": {
      "version": "3.1.10",
      "resolved": "https://registry.npmmirror.com/ejs/-/ejs-3.1.10.tgz",
      "integrity": "sha512-UeJmFfOrAQS8OJWPZ4qtgHyWExa088/MtK5UEyoJGFH67cDEXkZSviOiKRCZ4Xij0zxI3JECgYs3oKx+AizQBA==",
      "dev": true,
      "license": "Apache-2.0",
      "dependencies": {
        "jake": "^10.8.5"
      },
      "bin": {
        "ejs": "bin/cli.js"
      },
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/electron": {
      "version": "37.6.1",
      "resolved": "https://registry.npmmirror.com/electron/-/electron-37.6.1.tgz",
      "integrity": "sha512-aHtJVNjqf0lk7dlPoc1X+fMBpZtLn+XGvP6IYc3gooTwsD1D/Ic2SBRC9SnIk6LkWTsDaSF9jgH1d9Q7eABy/Q==",
      "dev": true,
      "hasInstallScript": true,
      "license": "MIT",
      "dependencies": {
        "@electron/get": "^2.0.0",
        "@types/node": "^22.7.7",
        "extract-zip": "^2.0.1"
      },
      "bin": {
        "electron": "cli.js"
      },
      "engines": {
        "node": ">= 12.20.55"
      }
    },
    "node_modules/electron-builder": {
      "version": "26.8.1",
      "resolved": "https://registry.npmmirror.com/electron-builder/-/electron-builder-26.8.1.tgz",
      "integrity": "sha512-uWhx1r74NGpCagG0ULs/P9Nqv2nsoo+7eo4fLUOB8L8MdWltq9odW/uuLXMFCDGnPafknYLZgjNX0ZIFRzOQAw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "app-builder-lib": "26.8.1",
        "builder-util": "26.8.1",
        "builder-util-runtime": "9.5.1",
        "chalk": "^4.1.2",
        "ci-info": "^4.2.0",
        "dmg-builder": "26.8.1",
        "fs-extra": "^10.1.0",
        "lazy-val": "^1.0.5",
        "simple-update-notifier": "2.0.0",
        "yargs": "^17.6.2"
      },
      "bin": {
        "electron-builder": "cli.js",
        "install-app-deps": "install-app-deps.js"
      },
      "engines": {
        "node": ">=14.0.0"
      }
    },
    "node_modules/electron-builder-squirrel-windows": {
      "version": "26.8.1",
      "resolved": "https://registry.npmmirror.com/electron-builder-squirrel-windows/-/electron-builder-squirrel-windows-26.8.1.tgz",
      "integrity": "sha512-o288fIdgPLHA76eDrFADHPoo7VyGkDCYbLV1GzndaMSAVBoZrGvM9m2IehdcVMzdAZJ2eV9bgyissQXHv5tGzA==",
      "dev": true,
      "license": "MIT",
      "peer": true,
      "dependencies": {
        "app-builder-lib": "26.8.1",
        "builder-util": "26.8.1",
        "electron-winstaller": "5.4.0"
      }
    },
    "node_modules/electron-builder/node_modules/fs-extra": {
      "version": "10.1.0",
      "resolved": "https://registry.npmmirror.com/fs-extra/-/fs-extra-10.1.0.tgz",
      "integrity": "sha512-oRXApq54ETRj4eMiFzGnHWGy+zo5raudjuxN0b8H7s/RU2oW0Wvsx9O0ACRN/kRq9E8Vu/ReskGB5o3ji+FzHQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "graceful-fs": "^4.2.0",
        "jsonfile": "^6.0.1",
        "universalify": "^2.0.0"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/electron-builder/node_modules/jsonfile": {
      "version": "6.2.0",
      "resolved": "https://registry.npmmirror.com/jsonfile/-/jsonfile-6.2.0.tgz",
      "integrity": "sha512-FGuPw30AdOIUTRMC2OMRtQV+jkVj2cfPqSeWXv1NEAJ1qZ5zb1X6z1mFhbfOB/iy3ssJCD+3KuZ8r8C3uVFlAg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "universalify": "^2.0.0"
      },
      "optionalDependencies": {
        "graceful-fs": "^4.1.6"
      }
    },
    "node_modules/electron-builder/node_modules/universalify": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/universalify/-/universalify-2.0.1.tgz",
      "integrity": "sha512-gptHNQghINnc/vTGIk0SOFGFNXw7JVrlRUtConJRlvaw6DuX0wO5Jeko9sWrMBhh+PsYAZ7oXAiOnf/UKogyiw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 10.0.0"
      }
    },
    "node_modules/electron-publish": {
      "version": "26.8.1",
      "resolved": "https://registry.npmmirror.com/electron-publish/-/electron-publish-26.8.1.tgz",
      "integrity": "sha512-q+jrSTIh/Cv4eGZa7oVR+grEJo/FoLMYBAnSL5GCtqwUpr1T+VgKB/dn1pnzxIxqD8S/jP1yilT9VrwCqINR4w==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@types/fs-extra": "^9.0.11",
        "builder-util": "26.8.1",
        "builder-util-runtime": "9.5.1",
        "chalk": "^4.1.2",
        "form-data": "^4.0.5",
        "fs-extra": "^10.1.0",
        "lazy-val": "^1.0.5",
        "mime": "^2.5.2"
      }
    },
    "node_modules/electron-publish/node_modules/fs-extra": {
      "version": "10.1.0",
      "resolved": "https://registry.npmmirror.com/fs-extra/-/fs-extra-10.1.0.tgz",
      "integrity": "sha512-oRXApq54ETRj4eMiFzGnHWGy+zo5raudjuxN0b8H7s/RU2oW0Wvsx9O0ACRN/kRq9E8Vu/ReskGB5o3ji+FzHQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "graceful-fs": "^4.2.0",
        "jsonfile": "^6.0.1",
        "universalify": "^2.0.0"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/electron-publish/node_modules/jsonfile": {
      "version": "6.2.0",
      "resolved": "https://registry.npmmirror.com/jsonfile/-/jsonfile-6.2.0.tgz",
      "integrity": "sha512-FGuPw30AdOIUTRMC2OMRtQV+jkVj2cfPqSeWXv1NEAJ1qZ5zb1X6z1mFhbfOB/iy3ssJCD+3KuZ8r8C3uVFlAg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "universalify": "^2.0.0"
      },
      "optionalDependencies": {
        "graceful-fs": "^4.1.6"
      }
    },
    "node_modules/electron-publish/node_modules/universalify": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/universalify/-/universalify-2.0.1.tgz",
      "integrity": "sha512-gptHNQghINnc/vTGIk0SOFGFNXw7JVrlRUtConJRlvaw6DuX0wO5Jeko9sWrMBhh+PsYAZ7oXAiOnf/UKogyiw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 10.0.0"
      }
    },
    "node_modules/electron-to-chromium": {
      "version": "1.5.307",
      "resolved": "https://registry.npmmirror.com/electron-to-chromium/-/electron-to-chromium-1.5.307.tgz",
      "integrity": "sha512-5z3uFKBWjiNR44nFcYdkcXjKMbg5KXNdciu7mhTPo9tB7NbqSNP2sSnGR+fqknZSCwKkBN+oxiiajWs4dT6ORg==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/electron-winstaller": {
      "version": "5.4.0",
      "resolved": "https://registry.npmmirror.com/electron-winstaller/-/electron-winstaller-5.4.0.tgz",
      "integrity": "sha512-bO3y10YikuUwUuDUQRM4KfwNkKhnpVO7IPdbsrejwN9/AABJzzTQ4GeHwyzNSrVO+tEH3/Np255a3sVZpZDjvg==",
      "dev": true,
      "hasInstallScript": true,
      "license": "MIT",
      "peer": true,
      "dependencies": {
        "@electron/asar": "^3.2.1",
        "debug": "^4.1.1",
        "fs-extra": "^7.0.1",
        "lodash": "^4.17.21",
        "temp": "^0.9.0"
      },
      "engines": {
        "node": ">=8.0.0"
      },
      "optionalDependencies": {
        "@electron/windows-sign": "^1.1.2"
      }
    },
    "node_modules/electron-winstaller/node_modules/fs-extra": {
      "version": "7.0.1",
      "resolved": "https://registry.npmmirror.com/fs-extra/-/fs-extra-7.0.1.tgz",
      "integrity": "sha512-YJDaCJZEnBmcbw13fvdAM9AwNOJwOzrE4pqMqBq5nFiEqXUqHwlK4B+3pUw6JNvfSPtX05xFHtYy/1ni01eGCw==",
      "dev": true,
      "license": "MIT",
      "peer": true,
      "dependencies": {
        "graceful-fs": "^4.1.2",
        "jsonfile": "^4.0.0",
        "universalify": "^0.1.0"
      },
      "engines": {
        "node": ">=6 <7 || >=8"
      }
    },
    "node_modules/emoji-regex": {
      "version": "8.0.0",
      "resolved": "https://registry.npmmirror.com/emoji-regex/-/emoji-regex-8.0.0.tgz",
      "integrity": "sha512-MSjYzcWNOA0ewAHpz0MxpYFvwg6yjy1NG3xteoqz644VCo/RPgnr1/GGt+ic3iJTzQ8Eu3TdM14SawnVUmGE6A==",
      "license": "MIT"
    },
    "node_modules/encoding": {
      "version": "0.1.13",
      "resolved": "https://registry.npmmirror.com/encoding/-/encoding-0.1.13.tgz",
      "integrity": "sha512-ETBauow1T35Y/WZMkio9jiM0Z5xjHHmJ4XmjZOq1l/dXz3lr2sRn87nJy20RupqSh1F2m3HHPSp8ShIPQJrJ3A==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "dependencies": {
        "iconv-lite": "^0.6.2"
      }
    },
    "node_modules/end-of-stream": {
      "version": "1.4.5",
      "resolved": "https://registry.npmmirror.com/end-of-stream/-/end-of-stream-1.4.5.tgz",
      "integrity": "sha512-ooEGc6HP26xXq/N+GCGOT0JKCLDGrq2bQUZrQ7gyrJiZANJ/8YDTxTpQBXGMn+WbIQXNVpyWymm7KYVICQnyOg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "once": "^1.4.0"
      }
    },
    "node_modules/env-paths": {
      "version": "2.2.1",
      "resolved": "https://registry.npmmirror.com/env-paths/-/env-paths-2.2.1.tgz",
      "integrity": "sha512-+h1lkLKhZMTYjog1VEpJNG7NZJWcuc2DDk/qsqSTRRCOXiLjeQ1d1/udrUGhqMxUgAlwKNZ0cf2uqan5GLuS2A==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/err-code": {
      "version": "2.0.3",
      "resolved": "https://registry.npmmirror.com/err-code/-/err-code-2.0.3.tgz",
      "integrity": "sha512-2bmlRpNKBxT/CRmPOlyISQpNj+qSeYvcym/uT0Jx2bMOlKLtSy1ZmLuVxSEKKyor/N5yhvp/ZiG1oE3DEYMSFA==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/es-define-property": {
      "version": "1.0.1",
      "resolved": "https://registry.npmmirror.com/es-define-property/-/es-define-property-1.0.1.tgz",
      "integrity": "sha512-e3nRfgfUZ4rNGL232gUgX06QNyyez04KdjFrF+LTRoOXmrOgFKDg4BCdsjW8EnT69eqdYGmRpJwiPVYNrCaW3g==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/es-errors": {
      "version": "1.3.0",
      "resolved": "https://registry.npmmirror.com/es-errors/-/es-errors-1.3.0.tgz",
      "integrity": "sha512-Zf5H2Kxt2xjTvbJvP2ZWLEICxA6j+hAmMzIlypy4xcBg1vKVnx89Wy0GbS+kf5cwCVFFzdCFh2XSCFNULS6csw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/es-object-atoms": {
      "version": "1.1.1",
      "resolved": "https://registry.npmmirror.com/es-object-atoms/-/es-object-atoms-1.1.1.tgz",
      "integrity": "sha512-FGgH2h8zKNim9ljj7dankFPcICIK9Cp5bm+c2gQSYePhpaG5+esrLODihIorn+Pe6FGJzWhXQotPv73jTaldXA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "es-errors": "^1.3.0"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/es-set-tostringtag": {
      "version": "2.1.0",
      "resolved": "https://registry.npmmirror.com/es-set-tostringtag/-/es-set-tostringtag-2.1.0.tgz",
      "integrity": "sha512-j6vWzfrGVfyXxge+O0x5sh6cvxAog0a/4Rdd2K36zCMV5eJ+/+tOAngRO8cODMNWbVRdVlmGZQL2YS3yR8bIUA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "es-errors": "^1.3.0",
        "get-intrinsic": "^1.2.6",
        "has-tostringtag": "^1.0.2",
        "hasown": "^2.0.2"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/es6-error": {
      "version": "4.1.1",
      "resolved": "https://registry.npmmirror.com/es6-error/-/es6-error-4.1.1.tgz",
      "integrity": "sha512-Um/+FxMr9CISWh0bi5Zv0iOD+4cFh5qLeks1qhAopKVAJw3drgKbKySikp7wGhDL0HPeaja0P5ULZrxLkniUVg==",
      "dev": true,
      "license": "MIT",
      "optional": true
    },
    "node_modules/esbuild": {
      "version": "0.25.12",
      "resolved": "https://registry.npmmirror.com/esbuild/-/esbuild-0.25.12.tgz",
      "integrity": "sha512-bbPBYYrtZbkt6Os6FiTLCTFxvq4tt3JKall1vRwshA3fdVztsLAatFaZobhkBC8/BrPetoa0oksYoKXoG4ryJg==",
      "dev": true,
      "hasInstallScript": true,
      "license": "MIT",
      "bin": {
        "esbuild": "bin/esbuild"
      },
      "engines": {
        "node": ">=18"
      },
      "optionalDependencies": {
        "@esbuild/aix-ppc64": "0.25.12",
        "@esbuild/android-arm": "0.25.12",
        "@esbuild/android-arm64": "0.25.12",
        "@esbuild/android-x64": "0.25.12",
        "@esbuild/darwin-arm64": "0.25.12",
        "@esbuild/darwin-x64": "0.25.12",
        "@esbuild/freebsd-arm64": "0.25.12",
        "@esbuild/freebsd-x64": "0.25.12",
        "@esbuild/linux-arm": "0.25.12",
        "@esbuild/linux-arm64": "0.25.12",
        "@esbuild/linux-ia32": "0.25.12",
        "@esbuild/linux-loong64": "0.25.12",
        "@esbuild/linux-mips64el": "0.25.12",
        "@esbuild/linux-ppc64": "0.25.12",
        "@esbuild/linux-riscv64": "0.25.12",
        "@esbuild/linux-s390x": "0.25.12",
        "@esbuild/linux-x64": "0.25.12",
        "@esbuild/netbsd-arm64": "0.25.12",
        "@esbuild/netbsd-x64": "0.25.12",
        "@esbuild/openbsd-arm64": "0.25.12",
        "@esbuild/openbsd-x64": "0.25.12",
        "@esbuild/openharmony-arm64": "0.25.12",
        "@esbuild/sunos-x64": "0.25.12",
        "@esbuild/win32-arm64": "0.25.12",
        "@esbuild/win32-ia32": "0.25.12",
        "@esbuild/win32-x64": "0.25.12"
      }
    },
    "node_modules/escalade": {
      "version": "3.2.0",
      "resolved": "https://registry.npmmirror.com/escalade/-/escalade-3.2.0.tgz",
      "integrity": "sha512-WUj2qlxaQtO4g6Pq5c29GTcWGDyd8itL8zTlipgECz3JesAiiOKotd8JU6otB3PACgG6xkJUyVhboMS+bje/jA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/escape-string-regexp": {
      "version": "4.0.0",
      "resolved": "https://registry.npmmirror.com/escape-string-regexp/-/escape-string-regexp-4.0.0.tgz",
      "integrity": "sha512-TtpcNJ3XAzx3Gq8sWRzJaVajRs0uVxA2YAkdb1jm2YkPz4G6egUFAyA3n5vtEIZefPk5Wa4UXbKuS5fKkJWdgA==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/exponential-backoff": {
      "version": "3.1.3",
      "resolved": "https://registry.npmmirror.com/exponential-backoff/-/exponential-backoff-3.1.3.tgz",
      "integrity": "sha512-ZgEeZXj30q+I0EN+CbSSpIyPaJ5HVQD18Z1m+u1FXbAeT94mr1zw50q4q6jiiC447Nl/YTcIYSAftiGqetwXCA==",
      "dev": true,
      "license": "Apache-2.0"
    },
    "node_modules/extract-zip": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/extract-zip/-/extract-zip-2.0.1.tgz",
      "integrity": "sha512-GDhU9ntwuKyGXdZBUgTIe+vXnWj0fppUEtMDL0+idd5Sta8TGpHssn/eusA9mrPr9qNDym6SxAYZjNvCn/9RBg==",
      "dev": true,
      "license": "BSD-2-Clause",
      "dependencies": {
        "debug": "^4.1.1",
        "get-stream": "^5.1.0",
        "yauzl": "^2.10.0"
      },
      "bin": {
        "extract-zip": "cli.js"
      },
      "engines": {
        "node": ">= 10.17.0"
      },
      "optionalDependencies": {
        "@types/yauzl": "^2.9.1"
      }
    },
    "node_modules/extsprintf": {
      "version": "1.4.1",
      "resolved": "https://registry.npmmirror.com/extsprintf/-/extsprintf-1.4.1.tgz",
      "integrity": "sha512-Wrk35e8ydCKDj/ArClo1VrPVmN8zph5V4AtHwIuHhvMXsKf73UT3BOD+azBIW+3wOJ4FhEH7zyaJCFvChjYvMA==",
      "dev": true,
      "engines": [
        "node >=0.6.0"
      ],
      "license": "MIT",
      "optional": true
    },
    "node_modules/fast-deep-equal": {
      "version": "3.1.3",
      "resolved": "https://registry.npmmirror.com/fast-deep-equal/-/fast-deep-equal-3.1.3.tgz",
      "integrity": "sha512-f3qQ9oQy9j2AhBe/H9VC91wLmKBCCU/gDOnKNAYG5hswO7BLKj09Hc5HYNz9cGI++xlpDCIgDaitVs03ATR84Q==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/fast-glob": {
      "version": "3.3.3",
      "resolved": "https://registry.npmmirror.com/fast-glob/-/fast-glob-3.3.3.tgz",
      "integrity": "sha512-7MptL8U0cqcFdzIzwOTHoilX9x5BrNqye7Z/LuC7kCMRio1EMSyqRK3BEAUD7sXRq4iT4AzTVuZdhgQ2TCvYLg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@nodelib/fs.stat": "^2.0.2",
        "@nodelib/fs.walk": "^1.2.3",
        "glob-parent": "^5.1.2",
        "merge2": "^1.3.0",
        "micromatch": "^4.0.8"
      },
      "engines": {
        "node": ">=8.6.0"
      }
    },
    "node_modules/fast-glob/node_modules/glob-parent": {
      "version": "5.1.2",
      "resolved": "https://registry.npmmirror.com/glob-parent/-/glob-parent-5.1.2.tgz",
      "integrity": "sha512-AOIgSQCepiJYwP3ARnGx+5VnTu2HBYdzbGP45eLw1vr3zB3vZLeyed1sC9hnbcOc9/SrMyM5RPQrkGz4aS9Zow==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "is-glob": "^4.0.1"
      },
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/fast-json-stable-stringify": {
      "version": "2.1.0",
      "resolved": "https://registry.npmmirror.com/fast-json-stable-stringify/-/fast-json-stable-stringify-2.1.0.tgz",
      "integrity": "sha512-lhd/wF+Lk98HZoTCtlVraHtfh5XYijIjalXck7saUtuanSDyLMxnHhSXEDJqHxD7msR8D0uCmqlkwjCV8xvwHw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/fastq": {
      "version": "1.20.1",
      "resolved": "https://registry.npmmirror.com/fastq/-/fastq-1.20.1.tgz",
      "integrity": "sha512-GGToxJ/w1x32s/D2EKND7kTil4n8OVk/9mycTc4VDza13lOvpUZTGX3mFSCtV9ksdGBVzvsyAVLM6mHFThxXxw==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "reusify": "^1.0.4"
      }
    },
    "node_modules/fd-slicer": {
      "version": "1.1.0",
      "resolved": "https://registry.npmmirror.com/fd-slicer/-/fd-slicer-1.1.0.tgz",
      "integrity": "sha512-cE1qsB/VwyQozZ+q1dGxR8LBYNZeofhEdUNGSMbQD3Gw2lAzX9Zb3uIU6Ebc/Fmyjo9AWWfnn0AUCHqtevs/8g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "pend": "~1.2.0"
      }
    },
    "node_modules/fdir": {
      "version": "6.5.0",
      "resolved": "https://registry.npmmirror.com/fdir/-/fdir-6.5.0.tgz",
      "integrity": "sha512-tIbYtZbucOs0BRGqPJkshJUYdL+SDH7dVM8gjy+ERp3WAUjLEFJE+02kanyHtwjWOnwrKYBiwAmM0p4kLJAnXg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=12.0.0"
      },
      "peerDependencies": {
        "picomatch": "^3 || ^4"
      },
      "peerDependenciesMeta": {
        "picomatch": {
          "optional": true
        }
      }
    },
    "node_modules/filelist": {
      "version": "1.0.6",
      "resolved": "https://registry.npmmirror.com/filelist/-/filelist-1.0.6.tgz",
      "integrity": "sha512-5giy2PkLYY1cP39p17Ech+2xlpTRL9HLspOfEgm0L6CwBXBTgsK5ou0JtzYuepxkaQ/tvhCFIJ5uXo0OrM2DxA==",
      "dev": true,
      "license": "Apache-2.0",
      "dependencies": {
        "minimatch": "^5.0.1"
      }
    },
    "node_modules/filelist/node_modules/balanced-match": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/balanced-match/-/balanced-match-1.0.2.tgz",
      "integrity": "sha512-3oSeUO0TMV67hN1AmbXsK4yaqU7tjiHlbxRDZOpH0KW9+CeX4bRAaX0Anxt0tx2MrpRpWwQaPwIlISEJhYU5Pw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/filelist/node_modules/brace-expansion": {
      "version": "2.0.2",
      "resolved": "https://registry.npmmirror.com/brace-expansion/-/brace-expansion-2.0.2.tgz",
      "integrity": "sha512-Jt0vHyM+jmUBqojB7E1NIYadt0vI0Qxjxd2TErW94wDz+E2LAm5vKMXXwg6ZZBTHPuUlDgQHKXvjGBdfcF1ZDQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "balanced-match": "^1.0.0"
      }
    },
    "node_modules/filelist/node_modules/minimatch": {
      "version": "5.1.9",
      "resolved": "https://registry.npmmirror.com/minimatch/-/minimatch-5.1.9.tgz",
      "integrity": "sha512-7o1wEA2RyMP7Iu7GNba9vc0RWWGACJOCZBJX2GJWip0ikV+wcOsgVuY9uE8CPiyQhkGFSlhuSkZPavN7u1c2Fw==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "brace-expansion": "^2.0.1"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/fill-range": {
      "version": "7.1.1",
      "resolved": "https://registry.npmmirror.com/fill-range/-/fill-range-7.1.1.tgz",
      "integrity": "sha512-YsGpe3WHLK8ZYi4tWDg2Jy3ebRz2rXowDxnld4bkQB00cc/1Zw9AWnC0i9ztDJitivtQvaI9KaLyKrc+hBW0yg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "to-regex-range": "^5.0.1"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/find-up": {
      "version": "4.1.0",
      "resolved": "https://registry.npmmirror.com/find-up/-/find-up-4.1.0.tgz",
      "integrity": "sha512-PpOwAdQ/YlXQ2vj8a3h8IipDuYRi3wceVQQGYWxNINccq40Anw7BlsEXCMbt1Zt+OLA6Fq9suIpIWD0OsnISlw==",
      "license": "MIT",
      "dependencies": {
        "locate-path": "^5.0.0",
        "path-exists": "^4.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/follow-redirects": {
      "version": "1.15.11",
      "resolved": "https://registry.npmmirror.com/follow-redirects/-/follow-redirects-1.15.11.tgz",
      "integrity": "sha512-deG2P0JfjrTxl50XGCDyfI97ZGVCxIpfKYmfyrQ54n5FO/0gfIES8C/Psl6kWVDolizcaaxZJnTS0QSMxvnsBQ==",
      "dev": true,
      "funding": [
        {
          "type": "individual",
          "url": "https://github.com/sponsors/RubenVerborgh"
        }
      ],
      "license": "MIT",
      "engines": {
        "node": ">=4.0"
      },
      "peerDependenciesMeta": {
        "debug": {
          "optional": true
        }
      }
    },
    "node_modules/foreground-child": {
      "version": "3.3.1",
      "resolved": "https://registry.npmmirror.com/foreground-child/-/foreground-child-3.3.1.tgz",
      "integrity": "sha512-gIXjKqtFuWEgzFRJA9WCQeSJLZDjgJUOMCMzxtvFq/37KojM1BFGufqsCy0r4qSQmYLsZYMeyRqzIWOMup03sw==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "cross-spawn": "^7.0.6",
        "signal-exit": "^4.0.1"
      },
      "engines": {
        "node": ">=14"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/foreground-child/node_modules/signal-exit": {
      "version": "4.1.0",
      "resolved": "https://registry.npmmirror.com/signal-exit/-/signal-exit-4.1.0.tgz",
      "integrity": "sha512-bzyZ1e88w9O1iNJbKnOlvYTrWPDl46O1bG0D3XInv+9tkPrxrN8jUUTiFlDkkmKWgn1M6CfIA13SuGqOa9Korw==",
      "dev": true,
      "license": "ISC",
      "engines": {
        "node": ">=14"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/form-data": {
      "version": "4.0.5",
      "resolved": "https://registry.npmmirror.com/form-data/-/form-data-4.0.5.tgz",
      "integrity": "sha512-8RipRLol37bNs2bhoV67fiTEvdTrbMUYcFTiy3+wuuOnUog2QBHCZWXDRijWQfAkhBj2Uf5UnVaiWwA5vdd82w==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "asynckit": "^0.4.0",
        "combined-stream": "^1.0.8",
        "es-set-tostringtag": "^2.1.0",
        "hasown": "^2.0.2",
        "mime-types": "^2.1.12"
      },
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/fraction.js": {
      "version": "5.3.4",
      "resolved": "https://registry.npmmirror.com/fraction.js/-/fraction.js-5.3.4.tgz",
      "integrity": "sha512-1X1NTtiJphryn/uLQz3whtY6jK3fTqoE3ohKs0tT+Ujr1W59oopxmoEh7Lu5p6vBaPbgoM0bzveAW4Qi5RyWDQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": "*"
      },
      "funding": {
        "type": "github",
        "url": "https://github.com/sponsors/rawify"
      }
    },
    "node_modules/fs-extra": {
      "version": "8.1.0",
      "resolved": "https://registry.npmmirror.com/fs-extra/-/fs-extra-8.1.0.tgz",
      "integrity": "sha512-yhlQgA6mnOJUKOsRUFsgJdQCvkKhcz8tlZG5HBQfReYZy46OwLcY+Zia0mtdHsOo9y/hP+CxMN0TU9QxoOtG4g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "graceful-fs": "^4.2.0",
        "jsonfile": "^4.0.0",
        "universalify": "^0.1.0"
      },
      "engines": {
        "node": ">=6 <7 || >=8"
      }
    },
    "node_modules/fs-minipass": {
      "version": "3.0.3",
      "resolved": "https://registry.npmmirror.com/fs-minipass/-/fs-minipass-3.0.3.tgz",
      "integrity": "sha512-XUBA9XClHbnJWSfBzjkm6RvPsyg3sryZt06BEQoXcF7EK/xpGaQYJgQKDJSUH5SGZ76Y7pFx1QBnXz09rU5Fbw==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "minipass": "^7.0.3"
      },
      "engines": {
        "node": "^14.17.0 || ^16.13.0 || >=18.0.0"
      }
    },
    "node_modules/fs.realpath": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/fs.realpath/-/fs.realpath-1.0.0.tgz",
      "integrity": "sha512-OO0pH2lK6a0hZnAdau5ItzHPI6pUlvI7jMVnxUQRtw4owF2wk8lOSabtGDCTP4Ggrg2MbGnWO9X8K1t4+fGMDw==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/fsevents": {
      "version": "2.3.3",
      "resolved": "https://registry.npmmirror.com/fsevents/-/fsevents-2.3.3.tgz",
      "integrity": "sha512-5xoDfX+fL7faATnagmWPpbFtwh/R77WmMMqqHGS65C3vvB0YHrgF+B1YmZ3441tMj5n63k0212XNoJwzlhffQw==",
      "dev": true,
      "hasInstallScript": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": "^8.16.0 || ^10.6.0 || >=11.0.0"
      }
    },
    "node_modules/function-bind": {
      "version": "1.1.2",
      "resolved": "https://registry.npmmirror.com/function-bind/-/function-bind-1.1.2.tgz",
      "integrity": "sha512-7XHNxH7qX9xG5mIwxkhumTox/MIRNcOgDrxWsMt2pAr23WHp6MrRlN7FBSFpCpr+oVO0F744iUgR82nJMfG2SA==",
      "dev": true,
      "license": "MIT",
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/gensync": {
      "version": "1.0.0-beta.2",
      "resolved": "https://registry.npmmirror.com/gensync/-/gensync-1.0.0-beta.2.tgz",
      "integrity": "sha512-3hN7NaskYvMDLQY55gnW3NQ+mesEAepTqlg+VEbj7zzqEMBVNhzcGYYeqFo/TlYz6eQiFcp1HcsCZO+nGgS8zg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/get-caller-file": {
      "version": "2.0.5",
      "resolved": "https://registry.npmmirror.com/get-caller-file/-/get-caller-file-2.0.5.tgz",
      "integrity": "sha512-DyFP3BM/3YHTQOCUL/w0OZHR0lpKeGrxotcHWcqNEdnltqFwXVfhEBQ94eIo34AfQpo0rGki4cyIiftY06h2Fg==",
      "license": "ISC",
      "engines": {
        "node": "6.* || 8.* || >= 10.*"
      }
    },
    "node_modules/get-intrinsic": {
      "version": "1.3.0",
      "resolved": "https://registry.npmmirror.com/get-intrinsic/-/get-intrinsic-1.3.0.tgz",
      "integrity": "sha512-9fSjSaos/fRIVIp+xSJlE6lfwhES7LNtKaCBIamHsjr2na1BiABJPo0mOjjz8GJDURarmCPGqaiVg5mfjb98CQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "call-bind-apply-helpers": "^1.0.2",
        "es-define-property": "^1.0.1",
        "es-errors": "^1.3.0",
        "es-object-atoms": "^1.1.1",
        "function-bind": "^1.1.2",
        "get-proto": "^1.0.1",
        "gopd": "^1.2.0",
        "has-symbols": "^1.1.0",
        "hasown": "^2.0.2",
        "math-intrinsics": "^1.1.0"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/get-proto": {
      "version": "1.0.1",
      "resolved": "https://registry.npmmirror.com/get-proto/-/get-proto-1.0.1.tgz",
      "integrity": "sha512-sTSfBjoXBp89JvIKIefqw7U2CCebsc74kiY6awiGogKtoSGbgjYE/G/+l9sF3MWFPNc9IcoOC4ODfKHfxFmp0g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "dunder-proto": "^1.0.1",
        "es-object-atoms": "^1.0.0"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/get-stream": {
      "version": "5.2.0",
      "resolved": "https://registry.npmmirror.com/get-stream/-/get-stream-5.2.0.tgz",
      "integrity": "sha512-nBF+F1rAZVCu/p7rjzgA+Yb4lfYXrpl7a6VmJrU8wF9I1CKvP/QwPNZHnOlwbTkY6dvtFIzFMSyQXbLoTQPRpA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "pump": "^3.0.0"
      },
      "engines": {
        "node": ">=8"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/glob": {
      "version": "7.2.3",
      "resolved": "https://registry.npmmirror.com/glob/-/glob-7.2.3.tgz",
      "integrity": "sha512-nFR0zLpU2YCaRxwoCJvL6UvCH2JFyFVIvwTLsIf21AuHlMskA1hhTdk+LlYJtOlYt9v6dvszD2BGRqBL+iQK9Q==",
      "deprecated": "Glob versions prior to v9 are no longer supported",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "fs.realpath": "^1.0.0",
        "inflight": "^1.0.4",
        "inherits": "2",
        "minimatch": "^3.1.1",
        "once": "^1.3.0",
        "path-is-absolute": "^1.0.0"
      },
      "engines": {
        "node": "*"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/glob-parent": {
      "version": "6.0.2",
      "resolved": "https://registry.npmmirror.com/glob-parent/-/glob-parent-6.0.2.tgz",
      "integrity": "sha512-XxwI8EOhVQgWp6iDL+3b0r86f4d6AX6zSU55HfB4ydCEuXLXc5FcYeOu+nnGftS4TEju/11rt4KJPTMgbfmv4A==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "is-glob": "^4.0.3"
      },
      "engines": {
        "node": ">=10.13.0"
      }
    },
    "node_modules/glob/node_modules/balanced-match": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/balanced-match/-/balanced-match-1.0.2.tgz",
      "integrity": "sha512-3oSeUO0TMV67hN1AmbXsK4yaqU7tjiHlbxRDZOpH0KW9+CeX4bRAaX0Anxt0tx2MrpRpWwQaPwIlISEJhYU5Pw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/glob/node_modules/brace-expansion": {
      "version": "1.1.12",
      "resolved": "https://registry.npmmirror.com/brace-expansion/-/brace-expansion-1.1.12.tgz",
      "integrity": "sha512-9T9UjW3r0UW5c1Q7GTwllptXwhvYmEzFhzMfZ9H7FQWt+uZePjZPjBP/W1ZEyZ1twGWom5/56TF4lPcqjnDHcg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "balanced-match": "^1.0.0",
        "concat-map": "0.0.1"
      }
    },
    "node_modules/glob/node_modules/minimatch": {
      "version": "3.1.5",
      "resolved": "https://registry.npmmirror.com/minimatch/-/minimatch-3.1.5.tgz",
      "integrity": "sha512-VgjWUsnnT6n+NUk6eZq77zeFdpW2LWDzP6zFGrCbHXiYNul5Dzqk2HHQ5uFH2DNW5Xbp8+jVzaeNt94ssEEl4w==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "brace-expansion": "^1.1.7"
      },
      "engines": {
        "node": "*"
      }
    },
    "node_modules/global-agent": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/global-agent/-/global-agent-3.0.0.tgz",
      "integrity": "sha512-PT6XReJ+D07JvGoxQMkT6qji/jVNfX/h364XHZOWeRzy64sSFr+xJ5OX7LI3b4MPQzdL4H8Y8M0xzPpsVMwA8Q==",
      "dev": true,
      "license": "BSD-3-Clause",
      "optional": true,
      "dependencies": {
        "boolean": "^3.0.1",
        "es6-error": "^4.1.1",
        "matcher": "^3.0.0",
        "roarr": "^2.15.3",
        "semver": "^7.3.2",
        "serialize-error": "^7.0.1"
      },
      "engines": {
        "node": ">=10.0"
      }
    },
    "node_modules/global-agent/node_modules/semver": {
      "version": "7.7.4",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-7.7.4.tgz",
      "integrity": "sha512-vFKC2IEtQnVhpT78h1Yp8wzwrf8CM+MzKMHGJZfBtzhZNycRFnXsHk6E5TxIkkMsgNS7mdX3AGB7x2QM2di4lA==",
      "dev": true,
      "license": "ISC",
      "optional": true,
      "bin": {
        "semver": "bin/semver.js"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/globalthis": {
      "version": "1.0.4",
      "resolved": "https://registry.npmmirror.com/globalthis/-/globalthis-1.0.4.tgz",
      "integrity": "sha512-DpLKbNU4WylpxJykQujfCcwYWiV/Jhm50Goo0wrVILAv5jOr9d+H+UR3PhSCD2rCCEIg0uc+G+muBTwD54JhDQ==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "dependencies": {
        "define-properties": "^1.2.1",
        "gopd": "^1.0.1"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/gopd": {
      "version": "1.2.0",
      "resolved": "https://registry.npmmirror.com/gopd/-/gopd-1.2.0.tgz",
      "integrity": "sha512-ZUKRh6/kUFoAiTAtTYPZJ3hw9wNxx+BIBOijnlG9PnrJsCcSjs1wyyD6vJpaYtgnzDrKYRSqf3OO6Rfa93xsRg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/got": {
      "version": "11.8.6",
      "resolved": "https://registry.npmmirror.com/got/-/got-11.8.6.tgz",
      "integrity": "sha512-6tfZ91bOr7bOXnK7PRDCGBLa1H4U080YHNaAQ2KsMGlLEzRbk44nsZF2E1IeRc3vtJHPVbKCYgdFbaGO2ljd8g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@sindresorhus/is": "^4.0.0",
        "@szmarczak/http-timer": "^4.0.5",
        "@types/cacheable-request": "^6.0.1",
        "@types/responselike": "^1.0.0",
        "cacheable-lookup": "^5.0.3",
        "cacheable-request": "^7.0.2",
        "decompress-response": "^6.0.0",
        "http2-wrapper": "^1.0.0-beta.5.2",
        "lowercase-keys": "^2.0.0",
        "p-cancelable": "^2.0.0",
        "responselike": "^2.0.0"
      },
      "engines": {
        "node": ">=10.19.0"
      },
      "funding": {
        "url": "https://github.com/sindresorhus/got?sponsor=1"
      }
    },
    "node_modules/graceful-fs": {
      "version": "4.2.11",
      "resolved": "https://registry.npmmirror.com/graceful-fs/-/graceful-fs-4.2.11.tgz",
      "integrity": "sha512-RbJ5/jmFcNNCcDV5o9eTnBLJ/HszWV0P73bc+Ff4nS/rJj+YaS6IGyiOL0VoBYX+l1Wrl3k63h/KrH+nhJ0XvQ==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/has-flag": {
      "version": "4.0.0",
      "resolved": "https://registry.npmmirror.com/has-flag/-/has-flag-4.0.0.tgz",
      "integrity": "sha512-EykJT/Q1KjTWctppgIAgfSO0tKVuZUjhgMr17kqTumMl6Afv3EISleU7qZUzoXDFTAHTDC4NOoG/ZxU3EvlMPQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/has-property-descriptors": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/has-property-descriptors/-/has-property-descriptors-1.0.2.tgz",
      "integrity": "sha512-55JNKuIW+vq4Ke1BjOTjM2YctQIvCT7GFzHwmfZPGo5wnrgkid0YQtnAleFSqumZm4az3n2BS+erby5ipJdgrg==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "dependencies": {
        "es-define-property": "^1.0.0"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/has-symbols": {
      "version": "1.1.0",
      "resolved": "https://registry.npmmirror.com/has-symbols/-/has-symbols-1.1.0.tgz",
      "integrity": "sha512-1cDNdwJ2Jaohmb3sg4OmKaMBwuC48sYni5HUw2DvsC8LjGTLK9h+eb1X6RyuOHe4hT0ULCW68iomhjUoKUqlPQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/has-tostringtag": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/has-tostringtag/-/has-tostringtag-1.0.2.tgz",
      "integrity": "sha512-NqADB8VjPFLM2V0VvHUewwwsw0ZWBaIdgo+ieHtK3hasLz4qeCRjYcqfB6AQrBggRKppKF8L52/VqdVsO47Dlw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "has-symbols": "^1.0.3"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/hasown": {
      "version": "2.0.2",
      "resolved": "https://registry.npmmirror.com/hasown/-/hasown-2.0.2.tgz",
      "integrity": "sha512-0hJU9SCPvmMzIBdZFqNPXWa6dqh7WdH0cII9y+CyS8rG3nL48Bclra9HmKhVVUHyPWNH5Y7xDwAB7bfgSjkUMQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "function-bind": "^1.1.2"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/hosted-git-info": {
      "version": "4.1.0",
      "resolved": "https://registry.npmmirror.com/hosted-git-info/-/hosted-git-info-4.1.0.tgz",
      "integrity": "sha512-kyCuEOWjJqZuDbRHzL8V93NzQhwIB71oFWSyzVo+KPZI+pnQPPxucdkrOZvkLRnrf5URsQM+IJ09Dw29cRALIA==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "lru-cache": "^6.0.0"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/hosted-git-info/node_modules/lru-cache": {
      "version": "6.0.0",
      "resolved": "https://registry.npmmirror.com/lru-cache/-/lru-cache-6.0.0.tgz",
      "integrity": "sha512-Jo6dJ04CmSjuznwJSS3pUeWmd/H0ffTlkXXgwZi+eq1UCmqQwCh+eLsYOYCwY991i2Fah4h1BEMCx4qThGbsiA==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "yallist": "^4.0.0"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/hosted-git-info/node_modules/yallist": {
      "version": "4.0.0",
      "resolved": "https://registry.npmmirror.com/yallist/-/yallist-4.0.0.tgz",
      "integrity": "sha512-3wdGidZyq5PB084XLES5TpOSRA3wjXAlIWMhum2kRcv/41Sn2emQ0dycQW4uZXLejwKvg6EsvbdlVL+FYEct7A==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/http-cache-semantics": {
      "version": "4.2.0",
      "resolved": "https://registry.npmmirror.com/http-cache-semantics/-/http-cache-semantics-4.2.0.tgz",
      "integrity": "sha512-dTxcvPXqPvXBQpq5dUr6mEMJX4oIEFv6bwom3FDwKRDsuIjjJGANqhBuoAn9c1RQJIdAKav33ED65E2ys+87QQ==",
      "dev": true,
      "license": "BSD-2-Clause"
    },
    "node_modules/http-proxy-agent": {
      "version": "7.0.2",
      "resolved": "https://registry.npmmirror.com/http-proxy-agent/-/http-proxy-agent-7.0.2.tgz",
      "integrity": "sha512-T1gkAiYYDWYx3V5Bmyu7HcfcvL7mUrTWiM6yOfa3PIphViJ/gFPbvidQ+veqSOHci/PxBcDabeUNCzpOODJZig==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "agent-base": "^7.1.0",
        "debug": "^4.3.4"
      },
      "engines": {
        "node": ">= 14"
      }
    },
    "node_modules/http2-wrapper": {
      "version": "1.0.3",
      "resolved": "https://registry.npmmirror.com/http2-wrapper/-/http2-wrapper-1.0.3.tgz",
      "integrity": "sha512-V+23sDMr12Wnz7iTcDeJr3O6AIxlnvT/bmaAAAP/Xda35C90p9599p0F1eHR/N1KILWSoWVAiOMFjBBXaXSMxg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "quick-lru": "^5.1.1",
        "resolve-alpn": "^1.0.0"
      },
      "engines": {
        "node": ">=10.19.0"
      }
    },
    "node_modules/https-proxy-agent": {
      "version": "7.0.6",
      "resolved": "https://registry.npmmirror.com/https-proxy-agent/-/https-proxy-agent-7.0.6.tgz",
      "integrity": "sha512-vK9P5/iUfdl95AI+JVyUuIcVtd4ofvtrOr3HNtM2yxC9bnMbEdp3x01OhQNnjb8IJYi38VlTE3mBXwcfvywuSw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "agent-base": "^7.1.2",
        "debug": "4"
      },
      "engines": {
        "node": ">= 14"
      }
    },
    "node_modules/iconv-corefoundation": {
      "version": "1.1.7",
      "resolved": "https://registry.npmmirror.com/iconv-corefoundation/-/iconv-corefoundation-1.1.7.tgz",
      "integrity": "sha512-T10qvkw0zz4wnm560lOEg0PovVqUXuOFhhHAkixw8/sycy7TJt7v/RrkEKEQnAw2viPSJu6iAkErxnzR0g8PpQ==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "dependencies": {
        "cli-truncate": "^2.1.0",
        "node-addon-api": "^1.6.3"
      },
      "engines": {
        "node": "^8.11.2 || >=10"
      }
    },
    "node_modules/iconv-lite": {
      "version": "0.6.3",
      "resolved": "https://registry.npmmirror.com/iconv-lite/-/iconv-lite-0.6.3.tgz",
      "integrity": "sha512-4fCk79wshMdzMp2rH06qWrJE4iolqLhCUH+OiuIgU++RB0+94NlDL81atO7GX55uUKueo0txHNtvEyI6D7WdMw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "safer-buffer": ">= 2.1.2 < 3.0.0"
      },
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/ieee754": {
      "version": "1.2.1",
      "resolved": "https://registry.npmmirror.com/ieee754/-/ieee754-1.2.1.tgz",
      "integrity": "sha512-dcyqhDvX1C46lXZcVqCpK+FtMRQVdIMN6/Df5js2zouUsqG7I6sFxitIC+7KYK29KdXOLHdu9zL4sFnoVQnqaA==",
      "dev": true,
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/feross"
        },
        {
          "type": "patreon",
          "url": "https://www.patreon.com/feross"
        },
        {
          "type": "consulting",
          "url": "https://feross.org/support"
        }
      ],
      "license": "BSD-3-Clause"
    },
    "node_modules/imurmurhash": {
      "version": "0.1.4",
      "resolved": "https://registry.npmmirror.com/imurmurhash/-/imurmurhash-0.1.4.tgz",
      "integrity": "sha512-JmXMZ6wuvDmLiHEml9ykzqO6lwFbof0GG4IkcGaENdCRDDmMVnny7s5HsIgHCbaq0w2MyPhDqkhTUgS2LU2PHA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.8.19"
      }
    },
    "node_modules/inflight": {
      "version": "1.0.6",
      "resolved": "https://registry.npmmirror.com/inflight/-/inflight-1.0.6.tgz",
      "integrity": "sha512-k92I/b08q4wvFscXCLvqfsHCrjrF7yiXsQuIVvVE7N82W3+aqpzuUdBbfhWcy/FZR3/4IgflMgKLOsvPDrGCJA==",
      "deprecated": "This module is not supported, and leaks memory. Do not use it. Check out lru-cache if you want a good and tested way to coalesce async requests by a key value, which is much more comprehensive and powerful.",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "once": "^1.3.0",
        "wrappy": "1"
      }
    },
    "node_modules/inherits": {
      "version": "2.0.4",
      "resolved": "https://registry.npmmirror.com/inherits/-/inherits-2.0.4.tgz",
      "integrity": "sha512-k/vGaX4/Yla3WzyMCvTQOXYeIHvqOKtnqBduzTHpzpQZzAskKMhZ2K+EnBiSM9zGSoIFeMpXKxa4dYeZIQqewQ==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/ip-address": {
      "version": "10.1.0",
      "resolved": "https://registry.npmmirror.com/ip-address/-/ip-address-10.1.0.tgz",
      "integrity": "sha512-XXADHxXmvT9+CRxhXg56LJovE+bmWnEWB78LB83VZTprKTmaC5QfruXocxzTZ2Kl0DNwKuBdlIhjL8LeY8Sf8Q==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 12"
      }
    },
    "node_modules/is-binary-path": {
      "version": "2.1.0",
      "resolved": "https://registry.npmmirror.com/is-binary-path/-/is-binary-path-2.1.0.tgz",
      "integrity": "sha512-ZMERYes6pDydyuGidse7OsHxtbI7WVeUEozgR/g7rd0xUimYNlvZRE/K2MgZTjWy725IfelLeVcEM97mmtRGXw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "binary-extensions": "^2.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/is-core-module": {
      "version": "2.16.1",
      "resolved": "https://registry.npmmirror.com/is-core-module/-/is-core-module-2.16.1.tgz",
      "integrity": "sha512-UfoeMA6fIJ8wTYFEUjelnaGI67v6+N7qXJEvQuIGa99l4xsCruSYOVSQ0uPANn4dAzm8lkYPaKLrrijLq7x23w==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "hasown": "^2.0.2"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/is-extglob": {
      "version": "2.1.1",
      "resolved": "https://registry.npmmirror.com/is-extglob/-/is-extglob-2.1.1.tgz",
      "integrity": "sha512-SbKbANkN603Vi4jEZv49LeVJMn4yGwsbzZworEoyEiutsN3nJYdbO36zfhGJ6QEDpOZIFkDtnq5JRxmvl3jsoQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/is-fullwidth-code-point": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/is-fullwidth-code-point/-/is-fullwidth-code-point-3.0.0.tgz",
      "integrity": "sha512-zymm5+u+sCsSWyD9qNaejV3DFvhCKclKdizYaJUuHA83RLjb7nSuGnddCHGv0hk+KY7BMAlsWeK4Ueg6EV6XQg==",
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/is-glob": {
      "version": "4.0.3",
      "resolved": "https://registry.npmmirror.com/is-glob/-/is-glob-4.0.3.tgz",
      "integrity": "sha512-xelSayHH36ZgE7ZWhli7pW34hNbNl8Ojv5KVmkJD4hBdD3th8Tfk9vYasLM+mXWOZhFkgZfxhLSnrwRr4elSSg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "is-extglob": "^2.1.1"
      },
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/is-interactive": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/is-interactive/-/is-interactive-1.0.0.tgz",
      "integrity": "sha512-2HvIEKRoqS62guEC+qBjpvRubdX910WCMuJTZ+I9yvqKU2/12eSL549HMwtabb4oupdj2sMP50k+XJfB/8JE6w==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/is-number": {
      "version": "7.0.0",
      "resolved": "https://registry.npmmirror.com/is-number/-/is-number-7.0.0.tgz",
      "integrity": "sha512-41Cifkg6e8TylSpdtTpeLVMqvSBEVzTttHvERD741+pnZ8ANv0004MRL43QKPDlK9cGvNp6NZWZUBlbGXYxxng==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.12.0"
      }
    },
    "node_modules/is-unicode-supported": {
      "version": "0.1.0",
      "resolved": "https://registry.npmmirror.com/is-unicode-supported/-/is-unicode-supported-0.1.0.tgz",
      "integrity": "sha512-knxG2q4UC3u8stRGyAVJCOdxFmv5DZiRcdlIaAQXAbSfJya+OhopNotLQrstBhququ4ZpuKbDc/8S6mgXgPFPw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/isbinaryfile": {
      "version": "5.0.7",
      "resolved": "https://registry.npmmirror.com/isbinaryfile/-/isbinaryfile-5.0.7.tgz",
      "integrity": "sha512-gnWD14Jh3FzS3CPhF0AxNOJ8CxqeblPTADzI38r0wt8ZyQl5edpy75myt08EG2oKvpyiqSqsx+Wkz9vtkbTqYQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 18.0.0"
      },
      "funding": {
        "url": "https://github.com/sponsors/gjtorikian/"
      }
    },
    "node_modules/isexe": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/isexe/-/isexe-2.0.0.tgz",
      "integrity": "sha512-RHxMLp9lnKHGHRng9QFhRCMbYAcVpn69smSGcq3f36xjgVVWThj4qqLbTLlq7Ssj8B+fIQ1EuCEGI2lKsyQeIw==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/jackspeak": {
      "version": "3.4.3",
      "resolved": "https://registry.npmmirror.com/jackspeak/-/jackspeak-3.4.3.tgz",
      "integrity": "sha512-OGlZQpz2yfahA/Rd1Y8Cd9SIEsqvXkLVoSw/cgwhnhFMDbsQFeZYoJJ7bIZBS9BcamUW96asq/npPWugM+RQBw==",
      "dev": true,
      "license": "BlueOak-1.0.0",
      "dependencies": {
        "@isaacs/cliui": "^8.0.2"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      },
      "optionalDependencies": {
        "@pkgjs/parseargs": "^0.11.0"
      }
    },
    "node_modules/jake": {
      "version": "10.9.4",
      "resolved": "https://registry.npmmirror.com/jake/-/jake-10.9.4.tgz",
      "integrity": "sha512-wpHYzhxiVQL+IV05BLE2Xn34zW1S223hvjtqk0+gsPrwd/8JNLXJgZZM/iPFsYc1xyphF+6M6EvdE5E9MBGkDA==",
      "dev": true,
      "license": "Apache-2.0",
      "dependencies": {
        "async": "^3.2.6",
        "filelist": "^1.0.4",
        "picocolors": "^1.1.1"
      },
      "bin": {
        "jake": "bin/cli.js"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/jiti": {
      "version": "2.6.1",
      "resolved": "https://registry.npmmirror.com/jiti/-/jiti-2.6.1.tgz",
      "integrity": "sha512-ekilCSN1jwRvIbgeg/57YFh8qQDNbwDb9xT/qu2DAHbFFZUicIl4ygVaAvzveMhMVr3LnpSKTNnwt8PoOfmKhQ==",
      "dev": true,
      "license": "MIT",
      "bin": {
        "jiti": "lib/jiti-cli.mjs"
      }
    },
    "node_modules/joi": {
      "version": "18.0.2",
      "resolved": "https://registry.npmmirror.com/joi/-/joi-18.0.2.tgz",
      "integrity": "sha512-RuCOQMIt78LWnktPoeBL0GErkNaJPTBGcYuyaBvUOQSpcpcLfWrHPPihYdOGbV5pam9VTWbeoF7TsGiHugcjGA==",
      "dev": true,
      "license": "BSD-3-Clause",
      "dependencies": {
        "@hapi/address": "^5.1.1",
        "@hapi/formula": "^3.0.2",
        "@hapi/hoek": "^11.0.7",
        "@hapi/pinpoint": "^2.0.1",
        "@hapi/tlds": "^1.1.1",
        "@hapi/topo": "^6.0.2",
        "@standard-schema/spec": "^1.0.0"
      },
      "engines": {
        "node": ">= 20"
      }
    },
    "node_modules/js-tokens": {
      "version": "4.0.0",
      "resolved": "https://registry.npmmirror.com/js-tokens/-/js-tokens-4.0.0.tgz",
      "integrity": "sha512-RdJUflcE3cUzKiMqQgsCu06FPu9UdIJO0beYbPhHN4k6apgJtifcoCtT9bcxOpYBtpD2kCM6Sbzg4CausW/PKQ==",
      "license": "MIT"
    },
    "node_modules/js-yaml": {
      "version": "4.1.1",
      "resolved": "https://registry.npmmirror.com/js-yaml/-/js-yaml-4.1.1.tgz",
      "integrity": "sha512-qQKT4zQxXl8lLwBtHMWwaTcGfFOZviOJet3Oy/xmGk2gZH677CJM9EvtfdSkgWcATZhj/55JZ0rmy3myCT5lsA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "argparse": "^2.0.1"
      },
      "bin": {
        "js-yaml": "bin/js-yaml.js"
      }
    },
    "node_modules/jsesc": {
      "version": "3.1.0",
      "resolved": "https://registry.npmmirror.com/jsesc/-/jsesc-3.1.0.tgz",
      "integrity": "sha512-/sM3dO2FOzXjKQhJuo0Q173wf2KOo8t4I8vHy6lF9poUp7bKT0/NHE8fPX23PwfhnykfqnC2xRxOnVw5XuGIaA==",
      "dev": true,
      "license": "MIT",
      "bin": {
        "jsesc": "bin/jsesc"
      },
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/json-buffer": {
      "version": "3.0.1",
      "resolved": "https://registry.npmmirror.com/json-buffer/-/json-buffer-3.0.1.tgz",
      "integrity": "sha512-4bV5BfR2mqfQTJm+V5tPPdf+ZpuhiIvTuAB5g8kcrXOZpTT/QwwVRWBywX1ozr6lEuPdbHxwaJlm9G6mI2sfSQ==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/json-schema-traverse": {
      "version": "0.4.1",
      "resolved": "https://registry.npmmirror.com/json-schema-traverse/-/json-schema-traverse-0.4.1.tgz",
      "integrity": "sha512-xbbCH5dCYU5T8LcEhhuh7HJ88HXuW3qsI3Y0zOZFKfZEHcpWiHU/Jxzk629Brsab/mMiHQti9wMP+845RPe3Vg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/json-stringify-safe": {
      "version": "5.0.1",
      "resolved": "https://registry.npmmirror.com/json-stringify-safe/-/json-stringify-safe-5.0.1.tgz",
      "integrity": "sha512-ZClg6AaYvamvYEE82d3Iyd3vSSIjQ+odgjaTzRuO3s7toCdFKczob2i0zCh7JE8kWn17yvAWhUVxvqGwUalsRA==",
      "dev": true,
      "license": "ISC",
      "optional": true
    },
    "node_modules/json5": {
      "version": "2.2.3",
      "resolved": "https://registry.npmmirror.com/json5/-/json5-2.2.3.tgz",
      "integrity": "sha512-XmOWe7eyHYH14cLdVPoyg+GOH3rYX++KpzrylJwSW98t3Nk+U8XOl8FWKOgwtzdb8lXGf6zYwDUzeHMWfxasyg==",
      "dev": true,
      "license": "MIT",
      "bin": {
        "json5": "lib/cli.js"
      },
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/jsonfile": {
      "version": "4.0.0",
      "resolved": "https://registry.npmmirror.com/jsonfile/-/jsonfile-4.0.0.tgz",
      "integrity": "sha512-m6F1R3z8jjlf2imQHS2Qez5sjKWQzbuuhuJ/FKYFRZvPE3PuHcSMVZzfsLhGVOkfd20obL5SWEBew5ShlquNxg==",
      "dev": true,
      "license": "MIT",
      "optionalDependencies": {
        "graceful-fs": "^4.1.6"
      }
    },
    "node_modules/keyv": {
      "version": "4.5.4",
      "resolved": "https://registry.npmmirror.com/keyv/-/keyv-4.5.4.tgz",
      "integrity": "sha512-oxVHkHR/EJf2CNXnWxRLW6mg7JyCCUcG0DtEGmL2ctUo1PNTin1PUil+r/+4r5MpVgC/fn1kjsx7mjSujKqIpw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "json-buffer": "3.0.1"
      }
    },
    "node_modules/lazy-val": {
      "version": "1.0.5",
      "resolved": "https://registry.npmmirror.com/lazy-val/-/lazy-val-1.0.5.tgz",
      "integrity": "sha512-0/BnGCCfyUMkBpeDgWihanIAF9JmZhHBgUhEqzvf+adhNGLoP6TaiI5oF8oyb3I45P+PcnrqihSf01M0l0G5+Q==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/lilconfig": {
      "version": "3.1.3",
      "resolved": "https://registry.npmmirror.com/lilconfig/-/lilconfig-3.1.3.tgz",
      "integrity": "sha512-/vlFKAoH5Cgt3Ie+JLhRbwOsCQePABiU3tJ1egGvyQ+33R/vcwM2Zl2QR/LzjsBeItPt3oSVXapn+m4nQDvpzw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=14"
      },
      "funding": {
        "url": "https://github.com/sponsors/antonk52"
      }
    },
    "node_modules/lines-and-columns": {
      "version": "1.2.4",
      "resolved": "https://registry.npmmirror.com/lines-and-columns/-/lines-and-columns-1.2.4.tgz",
      "integrity": "sha512-7ylylesZQ/PV29jhEDl3Ufjo6ZX7gCqJr5F7PKrqc93v7fzSymt1BpwEU8nAUXs8qzzvqhbjhK5QZg6Mt/HkBg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/locate-path": {
      "version": "5.0.0",
      "resolved": "https://registry.npmmirror.com/locate-path/-/locate-path-5.0.0.tgz",
      "integrity": "sha512-t7hw9pI+WvuwNJXwk5zVHpyhIqzg2qTlklJOf0mVxGSbe3Fp2VieZcduNYjaLDoy6p9uGpQEGWG87WpMKlNq8g==",
      "license": "MIT",
      "dependencies": {
        "p-locate": "^4.1.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/lodash": {
      "version": "4.17.23",
      "resolved": "https://registry.npmmirror.com/lodash/-/lodash-4.17.23.tgz",
      "integrity": "sha512-LgVTMpQtIopCi79SJeDiP0TfWi5CNEc/L/aRdTh3yIvmZXTnheWpKjSZhnvMl8iXbC1tFg9gdHHDMLoV7CnG+w==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/log-symbols": {
      "version": "4.1.0",
      "resolved": "https://registry.npmmirror.com/log-symbols/-/log-symbols-4.1.0.tgz",
      "integrity": "sha512-8XPvpAA8uyhfteu8pIvQxpJZ7SYYdpUivZpGy6sFsBuKRY/7rQGavedeB8aK+Zkyq6upMFVL/9AW6vOYzfRyLg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "chalk": "^4.1.0",
        "is-unicode-supported": "^0.1.0"
      },
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/loose-envify": {
      "version": "1.4.0",
      "resolved": "https://registry.npmmirror.com/loose-envify/-/loose-envify-1.4.0.tgz",
      "integrity": "sha512-lyuxPGr/Wfhrlem2CL/UcnUc1zcqKAImBDzukY7Y5F/yQiNdko6+fRLevlw1HgMySw7f611UIY408EtxRSoK3Q==",
      "license": "MIT",
      "dependencies": {
        "js-tokens": "^3.0.0 || ^4.0.0"
      },
      "bin": {
        "loose-envify": "cli.js"
      }
    },
    "node_modules/lowercase-keys": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/lowercase-keys/-/lowercase-keys-2.0.0.tgz",
      "integrity": "sha512-tqNXrS78oMOE73NMxK4EMLQsQowWf8jKooH9g7xPavRT706R6bkQJ6DY2Te7QukaZsulxa30wQ7bk0pm4XiHmA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/lru-cache": {
      "version": "5.1.1",
      "resolved": "https://registry.npmmirror.com/lru-cache/-/lru-cache-5.1.1.tgz",
      "integrity": "sha512-KpNARQA3Iwv+jTA0utUVVbrh+Jlrr1Fv0e56GGzAFOXN7dk/FviaDW8LHmK52DlcH4WP2n6gI8vN1aesBFgo9w==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "yallist": "^3.0.2"
      }
    },
    "node_modules/lucide-react": {
      "version": "0.511.0",
      "resolved": "https://registry.npmmirror.com/lucide-react/-/lucide-react-0.511.0.tgz",
      "integrity": "sha512-VK5a2ydJ7xm8GvBeKLS9mu1pVK6ucef9780JVUjw6bAjJL/QXnd4Y0p7SPeOUMC27YhzNCZvm5d/QX0Tp3rc0w==",
      "license": "ISC",
      "peerDependencies": {
        "react": "^16.5.1 || ^17.0.0 || ^18.0.0 || ^19.0.0"
      }
    },
    "node_modules/make-fetch-happen": {
      "version": "14.0.3",
      "resolved": "https://registry.npmmirror.com/make-fetch-happen/-/make-fetch-happen-14.0.3.tgz",
      "integrity": "sha512-QMjGbFTP0blj97EeidG5hk/QhKQ3T4ICckQGLgz38QF7Vgbk6e6FTARN8KhKxyBbWn8R0HU+bnw8aSoFPD4qtQ==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "@npmcli/agent": "^3.0.0",
        "cacache": "^19.0.1",
        "http-cache-semantics": "^4.1.1",
        "minipass": "^7.0.2",
        "minipass-fetch": "^4.0.0",
        "minipass-flush": "^1.0.5",
        "minipass-pipeline": "^1.2.4",
        "negotiator": "^1.0.0",
        "proc-log": "^5.0.0",
        "promise-retry": "^2.0.1",
        "ssri": "^12.0.0"
      },
      "engines": {
        "node": "^18.17.0 || >=20.5.0"
      }
    },
    "node_modules/matcher": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/matcher/-/matcher-3.0.0.tgz",
      "integrity": "sha512-OkeDaAZ/bQCxeFAozM55PKcKU0yJMPGifLwV4Qgjitu+5MoAfSQN4lsLJeXZ1b8w0x+/Emda6MZgXS1jvsapng==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "dependencies": {
        "escape-string-regexp": "^4.0.0"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/math-intrinsics": {
      "version": "1.1.0",
      "resolved": "https://registry.npmmirror.com/math-intrinsics/-/math-intrinsics-1.1.0.tgz",
      "integrity": "sha512-/IXtbwEk5HTPyEwyKX6hGkYXxM9nbj64B+ilVJnC/R6B0pH5G4V3b0pVbL7DBj4tkhBAppbQUlf6F6Xl9LHu1g==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/merge2": {
      "version": "1.4.1",
      "resolved": "https://registry.npmmirror.com/merge2/-/merge2-1.4.1.tgz",
      "integrity": "sha512-8q7VEgMJW4J8tcfVPy8g09NcQwZdbwFEqhe/WZkoIzjn/3TGDwtOCYtXGxA3O8tPzpczCCDgv+P2P5y00ZJOOg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/micromatch": {
      "version": "4.0.8",
      "resolved": "https://registry.npmmirror.com/micromatch/-/micromatch-4.0.8.tgz",
      "integrity": "sha512-PXwfBhYu0hBCPw8Dn0E+WDYb7af3dSLVWKi3HGv84IdF4TyFoC0ysxFd0Goxw7nSv4T/PzEJQxsYsEiFCKo2BA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "braces": "^3.0.3",
        "picomatch": "^2.3.1"
      },
      "engines": {
        "node": ">=8.6"
      }
    },
    "node_modules/micromatch/node_modules/picomatch": {
      "version": "2.3.1",
      "resolved": "https://registry.npmmirror.com/picomatch/-/picomatch-2.3.1.tgz",
      "integrity": "sha512-JU3teHTNjmE2VCGFzuY8EXzCDVwEqB2a8fsIvwaStHhAWJEeVd1o1QD80CU6+ZdEXXSLbSsuLwJjkCBWqRQUVA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=8.6"
      },
      "funding": {
        "url": "https://github.com/sponsors/jonschlinkert"
      }
    },
    "node_modules/mime": {
      "version": "2.6.0",
      "resolved": "https://registry.npmmirror.com/mime/-/mime-2.6.0.tgz",
      "integrity": "sha512-USPkMeET31rOMiarsBNIHZKLGgvKc/LrjofAnBlOttf5ajRvqiRA8QsenbcooctK6d6Ts6aqZXBA+XbkKthiQg==",
      "dev": true,
      "license": "MIT",
      "bin": {
        "mime": "cli.js"
      },
      "engines": {
        "node": ">=4.0.0"
      }
    },
    "node_modules/mime-db": {
      "version": "1.52.0",
      "resolved": "https://registry.npmmirror.com/mime-db/-/mime-db-1.52.0.tgz",
      "integrity": "sha512-sPU4uV7dYlvtWJxwwxHD0PuihVNiE7TyAbQ5SWxDCB9mUYvOgroQOwYQQOKPJ8CIbE+1ETVlOoK1UC2nU3gYvg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/mime-types": {
      "version": "2.1.35",
      "resolved": "https://registry.npmmirror.com/mime-types/-/mime-types-2.1.35.tgz",
      "integrity": "sha512-ZDY+bPm5zTTF+YpCrAU9nK0UgICYPT0QtT1NZWFv4s++TNkcgVaT0g6+4R2uI4MjQjzysHB1zxuWL50hzaeXiw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "mime-db": "1.52.0"
      },
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/mimic-fn": {
      "version": "2.1.0",
      "resolved": "https://registry.npmmirror.com/mimic-fn/-/mimic-fn-2.1.0.tgz",
      "integrity": "sha512-OqbOk5oEQeAZ8WXWydlu9HJjz9WVdEIvamMCcXmuqUYjTknH/sqsWvhQ3vgwKFRR1HpjvNBKQ37nbJgYzGqGcg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/mimic-response": {
      "version": "1.0.1",
      "resolved": "https://registry.npmmirror.com/mimic-response/-/mimic-response-1.0.1.tgz",
      "integrity": "sha512-j5EctnkH7amfV/q5Hgmoal1g2QHFJRraOtmx0JpIqkxhBhI/lJSl1nMpQ45hVarwNETOoWEimndZ4QK0RHxuxQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/minimatch": {
      "version": "10.2.4",
      "resolved": "https://registry.npmmirror.com/minimatch/-/minimatch-10.2.4.tgz",
      "integrity": "sha512-oRjTw/97aTBN0RHbYCdtF1MQfvusSIBQM0IZEgzl6426+8jSC0nF1a/GmnVLpfB9yyr6g6FTqWqiZVbxrtaCIg==",
      "dev": true,
      "license": "BlueOak-1.0.0",
      "dependencies": {
        "brace-expansion": "^5.0.2"
      },
      "engines": {
        "node": "18 || 20 || >=22"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/minimist": {
      "version": "1.2.8",
      "resolved": "https://registry.npmmirror.com/minimist/-/minimist-1.2.8.tgz",
      "integrity": "sha512-2yyAR8qBkN3YuheJanUpWC5U3bb5osDywNB8RzDVlDwDHbocAJveqqj1u8+SVD7jkWT4yvsHCpWqqWqAxb0zCA==",
      "dev": true,
      "license": "MIT",
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/minipass": {
      "version": "7.1.3",
      "resolved": "https://registry.npmmirror.com/minipass/-/minipass-7.1.3.tgz",
      "integrity": "sha512-tEBHqDnIoM/1rXME1zgka9g6Q2lcoCkxHLuc7ODJ5BxbP5d4c2Z5cGgtXAku59200Cx7diuHTOYfSBD8n6mm8A==",
      "dev": true,
      "license": "BlueOak-1.0.0",
      "engines": {
        "node": ">=16 || 14 >=14.17"
      }
    },
    "node_modules/minipass-collect": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/minipass-collect/-/minipass-collect-2.0.1.tgz",
      "integrity": "sha512-D7V8PO9oaz7PWGLbCACuI1qEOsq7UKfLotx/C0Aet43fCUB/wfQ7DYeq2oR/svFJGYDHPr38SHATeaj/ZoKHKw==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "minipass": "^7.0.3"
      },
      "engines": {
        "node": ">=16 || 14 >=14.17"
      }
    },
    "node_modules/minipass-fetch": {
      "version": "4.0.1",
      "resolved": "https://registry.npmmirror.com/minipass-fetch/-/minipass-fetch-4.0.1.tgz",
      "integrity": "sha512-j7U11C5HXigVuutxebFadoYBbd7VSdZWggSe64NVdvWNBqGAiXPL2QVCehjmw7lY1oF9gOllYbORh+hiNgfPgQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "minipass": "^7.0.3",
        "minipass-sized": "^1.0.3",
        "minizlib": "^3.0.1"
      },
      "engines": {
        "node": "^18.17.0 || >=20.5.0"
      },
      "optionalDependencies": {
        "encoding": "^0.1.13"
      }
    },
    "node_modules/minipass-flush": {
      "version": "1.0.5",
      "resolved": "https://registry.npmmirror.com/minipass-flush/-/minipass-flush-1.0.5.tgz",
      "integrity": "sha512-JmQSYYpPUqX5Jyn1mXaRwOda1uQ8HP5KAT/oDSLCzt1BYRhQU0/hDtsB1ufZfEEzMZ9aAVmsBw8+FWsIXlClWw==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "minipass": "^3.0.0"
      },
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/minipass-flush/node_modules/minipass": {
      "version": "3.3.6",
      "resolved": "https://registry.npmmirror.com/minipass/-/minipass-3.3.6.tgz",
      "integrity": "sha512-DxiNidxSEK+tHG6zOIklvNOwm3hvCrbUrdtzY74U6HKTJxvIDfOUL5W5P2Ghd3DTkhhKPYGqeNUIh5qcM4YBfw==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "yallist": "^4.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/minipass-flush/node_modules/yallist": {
      "version": "4.0.0",
      "resolved": "https://registry.npmmirror.com/yallist/-/yallist-4.0.0.tgz",
      "integrity": "sha512-3wdGidZyq5PB084XLES5TpOSRA3wjXAlIWMhum2kRcv/41Sn2emQ0dycQW4uZXLejwKvg6EsvbdlVL+FYEct7A==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/minipass-pipeline": {
      "version": "1.2.4",
      "resolved": "https://registry.npmmirror.com/minipass-pipeline/-/minipass-pipeline-1.2.4.tgz",
      "integrity": "sha512-xuIq7cIOt09RPRJ19gdi4b+RiNvDFYe5JH+ggNvBqGqpQXcru3PcRmOZuHBKWK1Txf9+cQ+HMVN4d6z46LZP7A==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "minipass": "^3.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/minipass-pipeline/node_modules/minipass": {
      "version": "3.3.6",
      "resolved": "https://registry.npmmirror.com/minipass/-/minipass-3.3.6.tgz",
      "integrity": "sha512-DxiNidxSEK+tHG6zOIklvNOwm3hvCrbUrdtzY74U6HKTJxvIDfOUL5W5P2Ghd3DTkhhKPYGqeNUIh5qcM4YBfw==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "yallist": "^4.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/minipass-pipeline/node_modules/yallist": {
      "version": "4.0.0",
      "resolved": "https://registry.npmmirror.com/yallist/-/yallist-4.0.0.tgz",
      "integrity": "sha512-3wdGidZyq5PB084XLES5TpOSRA3wjXAlIWMhum2kRcv/41Sn2emQ0dycQW4uZXLejwKvg6EsvbdlVL+FYEct7A==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/minipass-sized": {
      "version": "1.0.3",
      "resolved": "https://registry.npmmirror.com/minipass-sized/-/minipass-sized-1.0.3.tgz",
      "integrity": "sha512-MbkQQ2CTiBMlA2Dm/5cY+9SWFEN8pzzOXi6rlM5Xxq0Yqbda5ZQy9sU75a673FE9ZK0Zsbr6Y5iP6u9nktfg2g==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "minipass": "^3.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/minipass-sized/node_modules/minipass": {
      "version": "3.3.6",
      "resolved": "https://registry.npmmirror.com/minipass/-/minipass-3.3.6.tgz",
      "integrity": "sha512-DxiNidxSEK+tHG6zOIklvNOwm3hvCrbUrdtzY74U6HKTJxvIDfOUL5W5P2Ghd3DTkhhKPYGqeNUIh5qcM4YBfw==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "yallist": "^4.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/minipass-sized/node_modules/yallist": {
      "version": "4.0.0",
      "resolved": "https://registry.npmmirror.com/yallist/-/yallist-4.0.0.tgz",
      "integrity": "sha512-3wdGidZyq5PB084XLES5TpOSRA3wjXAlIWMhum2kRcv/41Sn2emQ0dycQW4uZXLejwKvg6EsvbdlVL+FYEct7A==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/minizlib": {
      "version": "3.1.0",
      "resolved": "https://registry.npmmirror.com/minizlib/-/minizlib-3.1.0.tgz",
      "integrity": "sha512-KZxYo1BUkWD2TVFLr0MQoM8vUUigWD3LlD83a/75BqC+4qE0Hb1Vo5v1FgcfaNXvfXzr+5EhQ6ing/CaBijTlw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "minipass": "^7.1.2"
      },
      "engines": {
        "node": ">= 18"
      }
    },
    "node_modules/mkdirp": {
      "version": "0.5.6",
      "resolved": "https://registry.npmmirror.com/mkdirp/-/mkdirp-0.5.6.tgz",
      "integrity": "sha512-FP+p8RB8OWpF3YZBCrP5gtADmtXApB5AMLn+vdyA+PyxCjrCs00mjyUozssO33cwDeT3wNGdLxJ5M//YqtHAJw==",
      "dev": true,
      "license": "MIT",
      "peer": true,
      "dependencies": {
        "minimist": "^1.2.6"
      },
      "bin": {
        "mkdirp": "bin/cmd.js"
      }
    },
    "node_modules/ms": {
      "version": "2.1.3",
      "resolved": "https://registry.npmmirror.com/ms/-/ms-2.1.3.tgz",
      "integrity": "sha512-6FlzubTLZG3J2a/NVCAleEhjzq5oxgHyaCU9yYXvcLsvoVaHJq/s5xXI6/XXP6tz7R9xAOtHnSO/tXtF3WRTlA==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/mz": {
      "version": "2.7.0",
      "resolved": "https://registry.npmmirror.com/mz/-/mz-2.7.0.tgz",
      "integrity": "sha512-z81GNO7nnYMEhrGh9LeymoE4+Yr0Wn5McHIZMK5cfQCl+NDX08sCZgUc9/6MHni9IWuFLm1Z3HTCXu2z9fN62Q==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "any-promise": "^1.0.0",
        "object-assign": "^4.0.1",
        "thenify-all": "^1.0.0"
      }
    },
    "node_modules/nanoid": {
      "version": "3.3.11",
      "resolved": "https://registry.npmmirror.com/nanoid/-/nanoid-3.3.11.tgz",
      "integrity": "sha512-N8SpfPUnUp1bK+PMYW8qSWdl9U+wwNWI4QKxOYDy9JAro3WMX7p2OeVRF9v+347pnakNevPmiHhNmZ2HbFA76w==",
      "dev": true,
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "bin": {
        "nanoid": "bin/nanoid.cjs"
      },
      "engines": {
        "node": "^10 || ^12 || ^13.7 || ^14 || >=15.0.1"
      }
    },
    "node_modules/negotiator": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/negotiator/-/negotiator-1.0.0.tgz",
      "integrity": "sha512-8Ofs/AUQh8MaEcrlq5xOX0CQ9ypTF5dl78mjlMNfOK08fzpgTHQRQPBxcPlEtIw0yRpws+Zo/3r+5WRby7u3Gg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/node-abi": {
      "version": "4.26.0",
      "resolved": "https://registry.npmmirror.com/node-abi/-/node-abi-4.26.0.tgz",
      "integrity": "sha512-8QwIZqikRvDIkXS2S93LjzhsSPJuIbfaMETWH+Bx8oOT9Sa9UsUtBFQlc3gBNd1+QINjaTloitXr1W3dQLi9Iw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "semver": "^7.6.3"
      },
      "engines": {
        "node": ">=22.12.0"
      }
    },
    "node_modules/node-abi/node_modules/semver": {
      "version": "7.7.4",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-7.7.4.tgz",
      "integrity": "sha512-vFKC2IEtQnVhpT78h1Yp8wzwrf8CM+MzKMHGJZfBtzhZNycRFnXsHk6E5TxIkkMsgNS7mdX3AGB7x2QM2di4lA==",
      "dev": true,
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/node-addon-api": {
      "version": "1.7.2",
      "resolved": "https://registry.npmmirror.com/node-addon-api/-/node-addon-api-1.7.2.tgz",
      "integrity": "sha512-ibPK3iA+vaY1eEjESkQkM0BbCqFOaZMiXRTtdB0u7b4djtY6JnsjvPdUHVMg6xQt3B8fpTTWHI9A+ADjM9frzg==",
      "dev": true,
      "license": "MIT",
      "optional": true
    },
    "node_modules/node-api-version": {
      "version": "0.2.1",
      "resolved": "https://registry.npmmirror.com/node-api-version/-/node-api-version-0.2.1.tgz",
      "integrity": "sha512-2xP/IGGMmmSQpI1+O/k72jF/ykvZ89JeuKX3TLJAYPDVLUalrshrLHkeVcCCZqG/eEa635cr8IBYzgnDvM2O8Q==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "semver": "^7.3.5"
      }
    },
    "node_modules/node-api-version/node_modules/semver": {
      "version": "7.7.4",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-7.7.4.tgz",
      "integrity": "sha512-vFKC2IEtQnVhpT78h1Yp8wzwrf8CM+MzKMHGJZfBtzhZNycRFnXsHk6E5TxIkkMsgNS7mdX3AGB7x2QM2di4lA==",
      "dev": true,
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/node-gyp": {
      "version": "11.5.0",
      "resolved": "https://registry.npmmirror.com/node-gyp/-/node-gyp-11.5.0.tgz",
      "integrity": "sha512-ra7Kvlhxn5V9Slyus0ygMa2h+UqExPqUIkfk7Pc8QTLT956JLSy51uWFwHtIYy0vI8cB4BDhc/S03+880My/LQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "env-paths": "^2.2.0",
        "exponential-backoff": "^3.1.1",
        "graceful-fs": "^4.2.6",
        "make-fetch-happen": "^14.0.3",
        "nopt": "^8.0.0",
        "proc-log": "^5.0.0",
        "semver": "^7.3.5",
        "tar": "^7.4.3",
        "tinyglobby": "^0.2.12",
        "which": "^5.0.0"
      },
      "bin": {
        "node-gyp": "bin/node-gyp.js"
      },
      "engines": {
        "node": "^18.17.0 || >=20.5.0"
      }
    },
    "node_modules/node-gyp/node_modules/isexe": {
      "version": "3.1.5",
      "resolved": "https://registry.npmmirror.com/isexe/-/isexe-3.1.5.tgz",
      "integrity": "sha512-6B3tLtFqtQS4ekarvLVMZ+X+VlvQekbe4taUkf/rhVO3d/h0M2rfARm/pXLcPEsjjMsFgrFgSrhQIxcSVrBz8w==",
      "dev": true,
      "license": "BlueOak-1.0.0",
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/node-gyp/node_modules/semver": {
      "version": "7.7.4",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-7.7.4.tgz",
      "integrity": "sha512-vFKC2IEtQnVhpT78h1Yp8wzwrf8CM+MzKMHGJZfBtzhZNycRFnXsHk6E5TxIkkMsgNS7mdX3AGB7x2QM2di4lA==",
      "dev": true,
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/node-gyp/node_modules/which": {
      "version": "5.0.0",
      "resolved": "https://registry.npmmirror.com/which/-/which-5.0.0.tgz",
      "integrity": "sha512-JEdGzHwwkrbWoGOlIHqQ5gtprKGOenpDHpxE9zVR1bWbOtYRyPPHMe9FaP6x61CmNaTThSkb0DAJte5jD+DmzQ==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "isexe": "^3.1.1"
      },
      "bin": {
        "node-which": "bin/which.js"
      },
      "engines": {
        "node": "^18.17.0 || >=20.5.0"
      }
    },
    "node_modules/node-releases": {
      "version": "2.0.36",
      "resolved": "https://registry.npmmirror.com/node-releases/-/node-releases-2.0.36.tgz",
      "integrity": "sha512-TdC8FSgHz8Mwtw9g5L4gR/Sh9XhSP/0DEkQxfEFXOpiul5IiHgHan2VhYYb6agDSfp4KuvltmGApc8HMgUrIkA==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/nopt": {
      "version": "8.1.0",
      "resolved": "https://registry.npmmirror.com/nopt/-/nopt-8.1.0.tgz",
      "integrity": "sha512-ieGu42u/Qsa4TFktmaKEwM6MQH0pOWnaB3htzh0JRtx84+Mebc0cbZYN5bC+6WTZ4+77xrL9Pn5m7CV6VIkV7A==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "abbrev": "^3.0.0"
      },
      "bin": {
        "nopt": "bin/nopt.js"
      },
      "engines": {
        "node": "^18.17.0 || >=20.5.0"
      }
    },
    "node_modules/normalize-path": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/normalize-path/-/normalize-path-3.0.0.tgz",
      "integrity": "sha512-6eZs5Ls3WtCisHWp9S2GUy8dqkpGi4BVSz3GaqiE6ezub0512ESztXUwUB6C6IKbQkY2Pnb/mD4WYojCRwcwLA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/normalize-url": {
      "version": "6.1.0",
      "resolved": "https://registry.npmmirror.com/normalize-url/-/normalize-url-6.1.0.tgz",
      "integrity": "sha512-DlL+XwOy3NxAQ8xuC0okPgK46iuVNAK01YN7RueYBqqFeGsBjV9XmCAzAdgt+667bCl5kPh9EqKKDwnaPG1I7A==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/object-assign": {
      "version": "4.1.1",
      "resolved": "https://registry.npmmirror.com/object-assign/-/object-assign-4.1.1.tgz",
      "integrity": "sha512-rJgTQnkUnH1sFw8yT6VSU3zD3sWmu6sZhIseY8VX+GRu3P6F7Fu+JNDoXfklElbLJSnc3FUQHVe4cU5hj+BcUg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/object-hash": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/object-hash/-/object-hash-3.0.0.tgz",
      "integrity": "sha512-RSn9F68PjH9HqtltsSnqYC1XXoWe9Bju5+213R98cNGttag9q9yAOTzdbsqvIa7aNm5WffBZFpWYr2aWrklWAw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/object-keys": {
      "version": "1.1.1",
      "resolved": "https://registry.npmmirror.com/object-keys/-/object-keys-1.1.1.tgz",
      "integrity": "sha512-NuAESUOUMrlIXOfHKzD6bpPu3tYt3xvjNdRIQ+FeT0lNb4K8WR70CaDxhuNguS2XG+GjkyMwOzsN5ZktImfhLA==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/once": {
      "version": "1.4.0",
      "resolved": "https://registry.npmmirror.com/once/-/once-1.4.0.tgz",
      "integrity": "sha512-lNaJgI+2Q5URQBkccEKHTQOPaXdUxnZZElQTZY0MFUAuaEqe1E+Nyvgdz/aIyNi6Z9MzO5dv1H8n58/GELp3+w==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "wrappy": "1"
      }
    },
    "node_modules/onetime": {
      "version": "5.1.2",
      "resolved": "https://registry.npmmirror.com/onetime/-/onetime-5.1.2.tgz",
      "integrity": "sha512-kbpaSSGJTWdAY5KPVeMOKXSrPtr8C8C7wodJbcsd51jRnmD+GZu8Y0VoU6Dm5Z4vWr0Ig/1NKuWRKf7j5aaYSg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "mimic-fn": "^2.1.0"
      },
      "engines": {
        "node": ">=6"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/ora": {
      "version": "5.4.1",
      "resolved": "https://registry.npmmirror.com/ora/-/ora-5.4.1.tgz",
      "integrity": "sha512-5b6Y85tPxZZ7QytO+BQzysW31HJku27cRIlkbAXaNx+BdcVi+LlRFmVXzeF6a7JCwJpyw5c4b+YSVImQIrBpuQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "bl": "^4.1.0",
        "chalk": "^4.1.0",
        "cli-cursor": "^3.1.0",
        "cli-spinners": "^2.5.0",
        "is-interactive": "^1.0.0",
        "is-unicode-supported": "^0.1.0",
        "log-symbols": "^4.1.0",
        "strip-ansi": "^6.0.0",
        "wcwidth": "^1.0.1"
      },
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/p-cancelable": {
      "version": "2.1.1",
      "resolved": "https://registry.npmmirror.com/p-cancelable/-/p-cancelable-2.1.1.tgz",
      "integrity": "sha512-BZOr3nRQHOntUjTrH8+Lh54smKHoHyur8We1V8DSMVrl5A2malOOwuJRnKRDjSnkoeBh4at6BwEnb5I7Jl31wg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/p-limit": {
      "version": "3.1.0",
      "resolved": "https://registry.npmmirror.com/p-limit/-/p-limit-3.1.0.tgz",
      "integrity": "sha512-TYOanM3wGwNGsZN2cVTYPArw454xnXj5qmWF1bEoAc4+cU/ol7GVh7odevjp1FNHduHc3KZMcFduxU5Xc6uJRQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "yocto-queue": "^0.1.0"
      },
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/p-locate": {
      "version": "4.1.0",
      "resolved": "https://registry.npmmirror.com/p-locate/-/p-locate-4.1.0.tgz",
      "integrity": "sha512-R79ZZ/0wAxKGu3oYMlz8jy/kbhsNrS7SKZ7PxEHBgJ5+F2mtFW2fK2cOtBh1cHYkQsbzFV7I+EoRKe6Yt0oK7A==",
      "license": "MIT",
      "dependencies": {
        "p-limit": "^2.2.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/p-locate/node_modules/p-limit": {
      "version": "2.3.0",
      "resolved": "https://registry.npmmirror.com/p-limit/-/p-limit-2.3.0.tgz",
      "integrity": "sha512-//88mFWSJx8lxCzwdAABTJL2MyWB12+eIY7MDL2SqLmAkeKU9qxRvWuSyTjm3FUmpBEMuFfckAIqEaVGUDxb6w==",
      "license": "MIT",
      "dependencies": {
        "p-try": "^2.0.0"
      },
      "engines": {
        "node": ">=6"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/p-map": {
      "version": "7.0.4",
      "resolved": "https://registry.npmmirror.com/p-map/-/p-map-7.0.4.tgz",
      "integrity": "sha512-tkAQEw8ysMzmkhgw8k+1U/iPhWNhykKnSk4Rd5zLoPJCuJaGRPo6YposrZgaxHKzDHdDWWZvE/Sk7hsL2X/CpQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=18"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/p-try": {
      "version": "2.2.0",
      "resolved": "https://registry.npmmirror.com/p-try/-/p-try-2.2.0.tgz",
      "integrity": "sha512-R4nPAVTAU0B9D35/Gk3uJf/7XYbQcyohSKdvAxIRSNghFl4e71hVoGnBNQz9cWaXxO2I10KTC+3jMdvvoKw6dQ==",
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/package-json-from-dist": {
      "version": "1.0.1",
      "resolved": "https://registry.npmmirror.com/package-json-from-dist/-/package-json-from-dist-1.0.1.tgz",
      "integrity": "sha512-UEZIS3/by4OC8vL3P2dTXRETpebLI2NiI5vIrjaD/5UtrkFX/tNbwjTSRAGC/+7CAo2pIcBaRgWmcBBHcsaCIw==",
      "dev": true,
      "license": "BlueOak-1.0.0"
    },
    "node_modules/path-exists": {
      "version": "4.0.0",
      "resolved": "https://registry.npmmirror.com/path-exists/-/path-exists-4.0.0.tgz",
      "integrity": "sha512-ak9Qy5Q7jYb2Wwcey5Fpvg2KoAc/ZIhLSLOSBmRmygPsGwkVVt0fZa0qrtMz+m6tJTAHfZQ8FnmB4MG4LWy7/w==",
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/path-is-absolute": {
      "version": "1.0.1",
      "resolved": "https://registry.npmmirror.com/path-is-absolute/-/path-is-absolute-1.0.1.tgz",
      "integrity": "sha512-AVbw3UJ2e9bq64vSaS9Am0fje1Pa8pbGqTTsmXfaIiMpnr5DlDhfJOuLj9Sf95ZPVDAUerDfEk88MPmPe7UCQg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/path-key": {
      "version": "3.1.1",
      "resolved": "https://registry.npmmirror.com/path-key/-/path-key-3.1.1.tgz",
      "integrity": "sha512-ojmeN0qd+y0jszEtoY48r0Peq5dwMEkIlCOu6Q5f41lfkswXuKtYrhgoTpLnyIcHm24Uhqx+5Tqm2InSwLhE6Q==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/path-parse": {
      "version": "1.0.7",
      "resolved": "https://registry.npmmirror.com/path-parse/-/path-parse-1.0.7.tgz",
      "integrity": "sha512-LDJzPVEEEPR+y48z93A0Ed0yXb8pAByGWo/k5YYdYgpY2/2EsOsksJrq7lOHxryrVOn1ejG6oAp8ahvOIQD8sw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/path-scurry": {
      "version": "1.11.1",
      "resolved": "https://registry.npmmirror.com/path-scurry/-/path-scurry-1.11.1.tgz",
      "integrity": "sha512-Xa4Nw17FS9ApQFJ9umLiJS4orGjm7ZzwUrwamcGQuHSzDyth9boKDaycYdDcZDuqYATXw4HFXgaqWTctW/v1HA==",
      "dev": true,
      "license": "BlueOak-1.0.0",
      "dependencies": {
        "lru-cache": "^10.2.0",
        "minipass": "^5.0.0 || ^6.0.2 || ^7.0.0"
      },
      "engines": {
        "node": ">=16 || 14 >=14.18"
      },
      "funding": {
        "url": "https://github.com/sponsors/isaacs"
      }
    },
    "node_modules/path-scurry/node_modules/lru-cache": {
      "version": "10.4.3",
      "resolved": "https://registry.npmmirror.com/lru-cache/-/lru-cache-10.4.3.tgz",
      "integrity": "sha512-JNAzZcXrCt42VGLuYz0zfAzDfAvJWW6AfYlDBQyDV5DClI2m5sAmK+OIO7s59XfsRsWHp02jAJrRadPRGTt6SQ==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/pe-library": {
      "version": "0.4.1",
      "resolved": "https://registry.npmmirror.com/pe-library/-/pe-library-0.4.1.tgz",
      "integrity": "sha512-eRWB5LBz7PpDu4PUlwT0PhnQfTQJlDDdPa35urV4Osrm0t0AqQFGn+UIkU3klZvwJ8KPO3VbBFsXquA6p6kqZw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=12",
        "npm": ">=6"
      },
      "funding": {
        "type": "github",
        "url": "https://github.com/sponsors/jet2jet"
      }
    },
    "node_modules/pend": {
      "version": "1.2.0",
      "resolved": "https://registry.npmmirror.com/pend/-/pend-1.2.0.tgz",
      "integrity": "sha512-F3asv42UuXchdzt+xXqfW1OGlVBe+mxa2mqI0pg5yAHZPvFmY3Y6drSf/GQ1A86WgWEN9Kzh/WrgKa6iGcHXLg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/picocolors": {
      "version": "1.1.1",
      "resolved": "https://registry.npmmirror.com/picocolors/-/picocolors-1.1.1.tgz",
      "integrity": "sha512-xceH2snhtb5M9liqDsmEw56le376mTZkEX/jEb/RxNFyegNul7eNslCXP9FDj/Lcu0X8KEyMceP2ntpaHrDEVA==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/picomatch": {
      "version": "4.0.3",
      "resolved": "https://registry.npmmirror.com/picomatch/-/picomatch-4.0.3.tgz",
      "integrity": "sha512-5gTmgEY/sqK6gFXLIsQNH19lWb4ebPDLA4SdLP7dsWkIXHWlG66oPuVvXSGFPppYZz8ZDZq0dYYrbHfBCVUb1Q==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=12"
      },
      "funding": {
        "url": "https://github.com/sponsors/jonschlinkert"
      }
    },
    "node_modules/pify": {
      "version": "2.3.0",
      "resolved": "https://registry.npmmirror.com/pify/-/pify-2.3.0.tgz",
      "integrity": "sha512-udgsAY+fTnvv7kI7aaxbqwWNb0AHiB0qBO89PZKPkoTmGOgdbrHDKD+0B2X4uTfJ/FT1R09r9gTsjUjNJotuog==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/pirates": {
      "version": "4.0.7",
      "resolved": "https://registry.npmmirror.com/pirates/-/pirates-4.0.7.tgz",
      "integrity": "sha512-TfySrs/5nm8fQJDcBDuUng3VOUKsd7S+zqvbOTiGXHfxX4wK31ard+hoNuvkicM/2YFzlpDgABOevKSsB4G/FA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/plist": {
      "version": "3.1.0",
      "resolved": "https://registry.npmmirror.com/plist/-/plist-3.1.0.tgz",
      "integrity": "sha512-uysumyrvkUX0rX/dEVqt8gC3sTBzd4zoWfLeS29nb53imdaXVvLINYXTI2GNqzaMuvacNx4uJQ8+b3zXR0pkgQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@xmldom/xmldom": "^0.8.8",
        "base64-js": "^1.5.1",
        "xmlbuilder": "^15.1.1"
      },
      "engines": {
        "node": ">=10.4.0"
      }
    },
    "node_modules/pngjs": {
      "version": "5.0.0",
      "resolved": "https://registry.npmmirror.com/pngjs/-/pngjs-5.0.0.tgz",
      "integrity": "sha512-40QW5YalBNfQo5yRYmiw7Yz6TKKVr3h6970B2YE+3fQpsWcrbj1PzJgxeJ19DRQjhMbKPIuMY8rFaXc8moolVw==",
      "license": "MIT",
      "engines": {
        "node": ">=10.13.0"
      }
    },
    "node_modules/postcss": {
      "version": "8.5.8",
      "resolved": "https://registry.npmmirror.com/postcss/-/postcss-8.5.8.tgz",
      "integrity": "sha512-OW/rX8O/jXnm82Ey1k44pObPtdblfiuWnrd8X7GJ7emImCOstunGbXUpp7HdBrFQX6rJzn3sPT397Wp5aCwCHg==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/postcss/"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/postcss"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "nanoid": "^3.3.11",
        "picocolors": "^1.1.1",
        "source-map-js": "^1.2.1"
      },
      "engines": {
        "node": "^10 || ^12 || >=14"
      }
    },
    "node_modules/postcss-import": {
      "version": "15.1.0",
      "resolved": "https://registry.npmmirror.com/postcss-import/-/postcss-import-15.1.0.tgz",
      "integrity": "sha512-hpr+J05B2FVYUAXHeK1YyI267J/dDDhMU6B6civm8hSY1jYJnBXxzKDKDswzJmtLHryrjhnDjqqp/49t8FALew==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "postcss-value-parser": "^4.0.0",
        "read-cache": "^1.0.0",
        "resolve": "^1.1.7"
      },
      "engines": {
        "node": ">=14.0.0"
      },
      "peerDependencies": {
        "postcss": "^8.0.0"
      }
    },
    "node_modules/postcss-js": {
      "version": "4.1.0",
      "resolved": "https://registry.npmmirror.com/postcss-js/-/postcss-js-4.1.0.tgz",
      "integrity": "sha512-oIAOTqgIo7q2EOwbhb8UalYePMvYoIeRY2YKntdpFQXNosSu3vLrniGgmH9OKs/qAkfoj5oB3le/7mINW1LCfw==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/postcss/"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "camelcase-css": "^2.0.1"
      },
      "engines": {
        "node": "^12 || ^14 || >= 16"
      },
      "peerDependencies": {
        "postcss": "^8.4.21"
      }
    },
    "node_modules/postcss-load-config": {
      "version": "6.0.1",
      "resolved": "https://registry.npmmirror.com/postcss-load-config/-/postcss-load-config-6.0.1.tgz",
      "integrity": "sha512-oPtTM4oerL+UXmx+93ytZVN82RrlY/wPUV8IeDxFrzIjXOLF1pN+EmKPLbubvKHT2HC20xXsCAH2Z+CKV6Oz/g==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/postcss/"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "lilconfig": "^3.1.1"
      },
      "engines": {
        "node": ">= 18"
      },
      "peerDependencies": {
        "jiti": ">=1.21.0",
        "postcss": ">=8.0.9",
        "tsx": "^4.8.1",
        "yaml": "^2.4.2"
      },
      "peerDependenciesMeta": {
        "jiti": {
          "optional": true
        },
        "postcss": {
          "optional": true
        },
        "tsx": {
          "optional": true
        },
        "yaml": {
          "optional": true
        }
      }
    },
    "node_modules/postcss-nested": {
      "version": "6.2.0",
      "resolved": "https://registry.npmmirror.com/postcss-nested/-/postcss-nested-6.2.0.tgz",
      "integrity": "sha512-HQbt28KulC5AJzG+cZtj9kvKB93CFCdLvog1WFLf1D+xmMvPGlBstkpTEZfK5+AN9hfJocyBFCNiqyS48bpgzQ==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/postcss/"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "postcss-selector-parser": "^6.1.1"
      },
      "engines": {
        "node": ">=12.0"
      },
      "peerDependencies": {
        "postcss": "^8.2.14"
      }
    },
    "node_modules/postcss-nested/node_modules/postcss-selector-parser": {
      "version": "6.1.2",
      "resolved": "https://registry.npmmirror.com/postcss-selector-parser/-/postcss-selector-parser-6.1.2.tgz",
      "integrity": "sha512-Q8qQfPiZ+THO/3ZrOrO0cJJKfpYCagtMUkXbnEfmgUjwXg6z/WBeOyS9APBBPCTSiDV+s4SwQGu8yFsiMRIudg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "cssesc": "^3.0.0",
        "util-deprecate": "^1.0.2"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/postcss-selector-parser": {
      "version": "6.0.10",
      "resolved": "https://registry.npmmirror.com/postcss-selector-parser/-/postcss-selector-parser-6.0.10.tgz",
      "integrity": "sha512-IQ7TZdoaqbT+LCpShg46jnZVlhWD2w6iQYAcYXfHARZ7X1t/UGhhceQDs5X0cGqKvYlHNOuv7Oa1xmb0oQuA3w==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "cssesc": "^3.0.0",
        "util-deprecate": "^1.0.2"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/postcss-value-parser": {
      "version": "4.2.0",
      "resolved": "https://registry.npmmirror.com/postcss-value-parser/-/postcss-value-parser-4.2.0.tgz",
      "integrity": "sha512-1NNCs6uurfkVbeXG4S8JFT9t19m45ICnif8zWLd5oPSZ50QnwMfK+H3jv408d4jw/7Bttv5axS5IiHoLaVNHeQ==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/postject": {
      "version": "1.0.0-alpha.6",
      "resolved": "https://registry.npmmirror.com/postject/-/postject-1.0.0-alpha.6.tgz",
      "integrity": "sha512-b9Eb8h2eVqNE8edvKdwqkrY6O7kAwmI8kcnBv1NScolYJbo59XUF0noFq+lxbC1yN20bmC0WBEbDC5H/7ASb0A==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "peer": true,
      "dependencies": {
        "commander": "^9.4.0"
      },
      "bin": {
        "postject": "dist/cli.js"
      },
      "engines": {
        "node": ">=14.0.0"
      }
    },
    "node_modules/postject/node_modules/commander": {
      "version": "9.5.0",
      "resolved": "https://registry.npmmirror.com/commander/-/commander-9.5.0.tgz",
      "integrity": "sha512-KRs7WVDKg86PWiuAqhDrAQnTXZKraVcCc6vFdL14qrZ/DcWwuRo7VoiYXalXO7S5GKpqYiVEwCbgFDfxNHKJBQ==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "peer": true,
      "engines": {
        "node": "^12.20.0 || >=14"
      }
    },
    "node_modules/proc-log": {
      "version": "5.0.0",
      "resolved": "https://registry.npmmirror.com/proc-log/-/proc-log-5.0.0.tgz",
      "integrity": "sha512-Azwzvl90HaF0aCz1JrDdXQykFakSSNPaPoiZ9fm5qJIMHioDZEi7OAdRwSm6rSoPtY3Qutnm3L7ogmg3dc+wbQ==",
      "dev": true,
      "license": "ISC",
      "engines": {
        "node": "^18.17.0 || >=20.5.0"
      }
    },
    "node_modules/progress": {
      "version": "2.0.3",
      "resolved": "https://registry.npmmirror.com/progress/-/progress-2.0.3.tgz",
      "integrity": "sha512-7PiHtLll5LdnKIMw100I+8xJXR5gW2QwWYkT6iJva0bXitZKa/XMrSbdmg3r2Xnaidz9Qumd0VPaMrZlF9V9sA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.4.0"
      }
    },
    "node_modules/promise-retry": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/promise-retry/-/promise-retry-2.0.1.tgz",
      "integrity": "sha512-y+WKFlBR8BGXnsNlIHFGPZmyDf3DFMoLhaflAnyZgV6rG6xu+JwesTo2Q9R6XwYmtmwAFCkAk3e35jEdoeh/3g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "err-code": "^2.0.2",
        "retry": "^0.12.0"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/proper-lockfile": {
      "version": "4.1.2",
      "resolved": "https://registry.npmmirror.com/proper-lockfile/-/proper-lockfile-4.1.2.tgz",
      "integrity": "sha512-TjNPblN4BwAWMXU8s9AEz4JmQxnD1NNL7bNOY/AKUzyamc379FWASUhc/K1pL2noVb+XmZKLL68cjzLsiOAMaA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "graceful-fs": "^4.2.4",
        "retry": "^0.12.0",
        "signal-exit": "^3.0.2"
      }
    },
    "node_modules/proxy-from-env": {
      "version": "1.1.0",
      "resolved": "https://registry.npmmirror.com/proxy-from-env/-/proxy-from-env-1.1.0.tgz",
      "integrity": "sha512-D+zkORCbA9f1tdWRK0RaCR3GPv50cMxcrz4X8k5LTSUD1Dkw47mKJEZQNunItRTkWwgtaUSo1RVFRIG9ZXiFYg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/pump": {
      "version": "3.0.4",
      "resolved": "https://registry.npmmirror.com/pump/-/pump-3.0.4.tgz",
      "integrity": "sha512-VS7sjc6KR7e1ukRFhQSY5LM2uBWAUPiOPa/A3mkKmiMwSmRFUITt0xuj+/lesgnCv+dPIEYlkzrcyXgquIHMcA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "end-of-stream": "^1.1.0",
        "once": "^1.3.1"
      }
    },
    "node_modules/punycode": {
      "version": "2.3.1",
      "resolved": "https://registry.npmmirror.com/punycode/-/punycode-2.3.1.tgz",
      "integrity": "sha512-vYt7UD1U9Wg6138shLtLOvdAu+8DsC/ilFtEVHcH+wydcSpNE20AfSOduf6MkRFahL5FY7X1oU7nKVZFtfq8Fg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/qrcode": {
      "version": "1.5.4",
      "resolved": "https://registry.npmmirror.com/qrcode/-/qrcode-1.5.4.tgz",
      "integrity": "sha512-1ca71Zgiu6ORjHqFBDpnSMTR2ReToX4l1Au1VFLyVeBTFavzQnv5JxMFr3ukHVKpSrSA2MCk0lNJSykjUfz7Zg==",
      "license": "MIT",
      "dependencies": {
        "dijkstrajs": "^1.0.1",
        "pngjs": "^5.0.0",
        "yargs": "^15.3.1"
      },
      "bin": {
        "qrcode": "bin/qrcode"
      },
      "engines": {
        "node": ">=10.13.0"
      }
    },
    "node_modules/qrcode/node_modules/cliui": {
      "version": "6.0.0",
      "resolved": "https://registry.npmmirror.com/cliui/-/cliui-6.0.0.tgz",
      "integrity": "sha512-t6wbgtoCXvAzst7QgXxJYqPt0usEfbgQdftEPbLL/cvv6HPE5VgvqCuAIDR0NgU52ds6rFwqrgakNLrHEjCbrQ==",
      "license": "ISC",
      "dependencies": {
        "string-width": "^4.2.0",
        "strip-ansi": "^6.0.0",
        "wrap-ansi": "^6.2.0"
      }
    },
    "node_modules/qrcode/node_modules/wrap-ansi": {
      "version": "6.2.0",
      "resolved": "https://registry.npmmirror.com/wrap-ansi/-/wrap-ansi-6.2.0.tgz",
      "integrity": "sha512-r6lPcBGxZXlIcymEu7InxDMhdW0KDxpLgoFLcguasxCaJ/SOIZwINatK9KY/tf+ZrlywOKU0UDj3ATXUBfxJXA==",
      "license": "MIT",
      "dependencies": {
        "ansi-styles": "^4.0.0",
        "string-width": "^4.1.0",
        "strip-ansi": "^6.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/qrcode/node_modules/y18n": {
      "version": "4.0.3",
      "resolved": "https://registry.npmmirror.com/y18n/-/y18n-4.0.3.tgz",
      "integrity": "sha512-JKhqTOwSrqNA1NY5lSztJ1GrBiUodLMmIZuLiDaMRJ+itFd+ABVE8XBjOvIWL+rSqNDC74LCSFmlb/U4UZ4hJQ==",
      "license": "ISC"
    },
    "node_modules/qrcode/node_modules/yargs": {
      "version": "15.4.1",
      "resolved": "https://registry.npmmirror.com/yargs/-/yargs-15.4.1.tgz",
      "integrity": "sha512-aePbxDmcYW++PaqBsJ+HYUFwCdv4LVvdnhBy78E57PIor8/OVvhMrADFFEDh8DHDFRv/O9i3lPhsENjO7QX0+A==",
      "license": "MIT",
      "dependencies": {
        "cliui": "^6.0.0",
        "decamelize": "^1.2.0",
        "find-up": "^4.1.0",
        "get-caller-file": "^2.0.1",
        "require-directory": "^2.1.1",
        "require-main-filename": "^2.0.0",
        "set-blocking": "^2.0.0",
        "string-width": "^4.2.0",
        "which-module": "^2.0.0",
        "y18n": "^4.0.0",
        "yargs-parser": "^18.1.2"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/qrcode/node_modules/yargs-parser": {
      "version": "18.1.3",
      "resolved": "https://registry.npmmirror.com/yargs-parser/-/yargs-parser-18.1.3.tgz",
      "integrity": "sha512-o50j0JeToy/4K6OZcaQmW6lyXXKhq7csREXcDwk2omFPJEwUNOVtJKvmDr9EI1fAJZUyZcRF7kxGBWmRXudrCQ==",
      "license": "ISC",
      "dependencies": {
        "camelcase": "^5.0.0",
        "decamelize": "^1.2.0"
      },
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/queue-microtask": {
      "version": "1.2.3",
      "resolved": "https://registry.npmmirror.com/queue-microtask/-/queue-microtask-1.2.3.tgz",
      "integrity": "sha512-NuaNSa6flKT5JaSYQzJok04JzTL1CA6aGhv5rfLW3PgqA+M2ChpZQnAC8h8i4ZFkBS8X5RqkDBHA7r4hej3K9A==",
      "dev": true,
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/feross"
        },
        {
          "type": "patreon",
          "url": "https://www.patreon.com/feross"
        },
        {
          "type": "consulting",
          "url": "https://feross.org/support"
        }
      ],
      "license": "MIT"
    },
    "node_modules/quick-lru": {
      "version": "5.1.1",
      "resolved": "https://registry.npmmirror.com/quick-lru/-/quick-lru-5.1.1.tgz",
      "integrity": "sha512-WuyALRjWPDGtt/wzJiadO5AXY+8hZ80hVpe6MyivgraREW751X3SbhRvG3eLKOYN+8VEvqLcf3wdnt44Z4S4SA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/react": {
      "version": "18.3.1",
      "resolved": "https://registry.npmmirror.com/react/-/react-18.3.1.tgz",
      "integrity": "sha512-wS+hAgJShR0KhEvPJArfuPVN1+Hz1t0Y6n5jLrGQbkb4urgPE/0Rve+1kMB1v/oWgHgm4WIcV+i7F2pTVj+2iQ==",
      "license": "MIT",
      "dependencies": {
        "loose-envify": "^1.1.0"
      },
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/react-dom": {
      "version": "18.3.1",
      "resolved": "https://registry.npmmirror.com/react-dom/-/react-dom-18.3.1.tgz",
      "integrity": "sha512-5m4nQKp+rZRb09LNH59GM4BxTh9251/ylbKIbpe7TpGxfJ+9kv6BLkLBXIjjspbgbnIBNqlI23tRnTWT0snUIw==",
      "license": "MIT",
      "dependencies": {
        "loose-envify": "^1.1.0",
        "scheduler": "^0.23.2"
      },
      "peerDependencies": {
        "react": "^18.3.1"
      }
    },
    "node_modules/react-refresh": {
      "version": "0.17.0",
      "resolved": "https://registry.npmmirror.com/react-refresh/-/react-refresh-0.17.0.tgz",
      "integrity": "sha512-z6F7K9bV85EfseRCp2bzrpyQ0Gkw1uLoCel9XBVWPg/TjRj94SkJzUTGfOa4bs7iJvBWtQG0Wq7wnI0syw3EBQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/read-binary-file-arch": {
      "version": "1.0.6",
      "resolved": "https://registry.npmmirror.com/read-binary-file-arch/-/read-binary-file-arch-1.0.6.tgz",
      "integrity": "sha512-BNg9EN3DD3GsDXX7Aa8O4p92sryjkmzYYgmgTAc6CA4uGLEDzFfxOxugu21akOxpcXHiEgsYkC6nPsQvLLLmEg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "debug": "^4.3.4"
      },
      "bin": {
        "read-binary-file-arch": "cli.js"
      }
    },
    "node_modules/read-cache": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/read-cache/-/read-cache-1.0.0.tgz",
      "integrity": "sha512-Owdv/Ft7IjOgm/i0xvNDZ1LrRANRfew4b2prF3OWMQLxLfu3bS8FVhCsrSCMK4lR56Y9ya+AThoTpDCTxCmpRA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "pify": "^2.3.0"
      }
    },
    "node_modules/readable-stream": {
      "version": "3.6.2",
      "resolved": "https://registry.npmmirror.com/readable-stream/-/readable-stream-3.6.2.tgz",
      "integrity": "sha512-9u/sniCrY3D5WdsERHzHE4G2YCXqoG5FTHUiCC4SIbr6XcLZBY05ya9EKjYek9O5xOAwjGq+1JdGBAS7Q9ScoA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "inherits": "^2.0.3",
        "string_decoder": "^1.1.1",
        "util-deprecate": "^1.0.1"
      },
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/readdirp": {
      "version": "3.6.0",
      "resolved": "https://registry.npmmirror.com/readdirp/-/readdirp-3.6.0.tgz",
      "integrity": "sha512-hOS089on8RduqdbhvQ5Z37A0ESjsqz6qnRcffsMU3495FuTdqSm+7bhJ29JvIOsBDEEnan5DPu9t3To9VRlMzA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "picomatch": "^2.2.1"
      },
      "engines": {
        "node": ">=8.10.0"
      }
    },
    "node_modules/readdirp/node_modules/picomatch": {
      "version": "2.3.1",
      "resolved": "https://registry.npmmirror.com/picomatch/-/picomatch-2.3.1.tgz",
      "integrity": "sha512-JU3teHTNjmE2VCGFzuY8EXzCDVwEqB2a8fsIvwaStHhAWJEeVd1o1QD80CU6+ZdEXXSLbSsuLwJjkCBWqRQUVA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=8.6"
      },
      "funding": {
        "url": "https://github.com/sponsors/jonschlinkert"
      }
    },
    "node_modules/require-directory": {
      "version": "2.1.1",
      "resolved": "https://registry.npmmirror.com/require-directory/-/require-directory-2.1.1.tgz",
      "integrity": "sha512-fGxEI7+wsG9xrvdjsrlmL22OMTTiHRwAMroiEeMgq8gzoLC/PQr7RsRDSTLUg/bZAZtF+TVIkHc6/4RIKrui+Q==",
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/require-main-filename": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/require-main-filename/-/require-main-filename-2.0.0.tgz",
      "integrity": "sha512-NKN5kMDylKuldxYLSUfrbo5Tuzh4hd+2E8NPPX02mZtn1VuREQToYe/ZdlJy+J3uCpfaiGF05e7B8W0iXbQHmg==",
      "license": "ISC"
    },
    "node_modules/resedit": {
      "version": "1.7.2",
      "resolved": "https://registry.npmmirror.com/resedit/-/resedit-1.7.2.tgz",
      "integrity": "sha512-vHjcY2MlAITJhC0eRD/Vv8Vlgmu9Sd3LX9zZvtGzU5ZImdTN3+d6e/4mnTyV8vEbyf1sgNIrWxhWlrys52OkEA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "pe-library": "^0.4.1"
      },
      "engines": {
        "node": ">=12",
        "npm": ">=6"
      },
      "funding": {
        "type": "github",
        "url": "https://github.com/sponsors/jet2jet"
      }
    },
    "node_modules/resolve": {
      "version": "1.22.11",
      "resolved": "https://registry.npmmirror.com/resolve/-/resolve-1.22.11.tgz",
      "integrity": "sha512-RfqAvLnMl313r7c9oclB1HhUEAezcpLjz95wFH4LVuhk9JF/r22qmVP9AMmOU4vMX7Q8pN8jwNg/CSpdFnMjTQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "is-core-module": "^2.16.1",
        "path-parse": "^1.0.7",
        "supports-preserve-symlinks-flag": "^1.0.0"
      },
      "bin": {
        "resolve": "bin/resolve"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/resolve-alpn": {
      "version": "1.2.1",
      "resolved": "https://registry.npmmirror.com/resolve-alpn/-/resolve-alpn-1.2.1.tgz",
      "integrity": "sha512-0a1F4l73/ZFZOakJnQ3FvkJ2+gSTQWz/r2KE5OdDY0TxPm5h4GkqkWWfM47T7HsbnOtcJVEF4epCVy6u7Q3K+g==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/responselike": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/responselike/-/responselike-2.0.1.tgz",
      "integrity": "sha512-4gl03wn3hj1HP3yzgdI7d3lCkF95F21Pz4BPGvKHinyQzALR5CapwC8yIi0Rh58DEMQ/SguC03wFj2k0M/mHhw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "lowercase-keys": "^2.0.0"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/restore-cursor": {
      "version": "3.1.0",
      "resolved": "https://registry.npmmirror.com/restore-cursor/-/restore-cursor-3.1.0.tgz",
      "integrity": "sha512-l+sSefzHpj5qimhFSE5a8nufZYAM3sBSVMAPtYkmC+4EH2anSGaEMXSD0izRQbu9nfyQ9y5JrVmp7E8oZrUjvA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "onetime": "^5.1.0",
        "signal-exit": "^3.0.2"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/retry": {
      "version": "0.12.0",
      "resolved": "https://registry.npmmirror.com/retry/-/retry-0.12.0.tgz",
      "integrity": "sha512-9LkiTwjUh6rT555DtE9rTX+BKByPfrMzEAtnlEtdEwr3Nkffwiihqe2bWADg+OQRjt9gl6ICdmB/ZFDCGAtSow==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 4"
      }
    },
    "node_modules/reusify": {
      "version": "1.1.0",
      "resolved": "https://registry.npmmirror.com/reusify/-/reusify-1.1.0.tgz",
      "integrity": "sha512-g6QUff04oZpHs0eG5p83rFLhHeV00ug/Yf9nZM6fLeUrPguBTkTQOdpAWWspMh55TZfVQDPaN3NQJfbVRAxdIw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "iojs": ">=1.0.0",
        "node": ">=0.10.0"
      }
    },
    "node_modules/rimraf": {
      "version": "2.6.3",
      "resolved": "https://registry.npmmirror.com/rimraf/-/rimraf-2.6.3.tgz",
      "integrity": "sha512-mwqeW5XsA2qAejG46gYdENaxXjx9onRNCfn7L0duuP4hCuTIi/QO7PDK07KJfp1d+izWPrzEJDcSqBa0OZQriA==",
      "deprecated": "Rimraf versions prior to v4 are no longer supported",
      "dev": true,
      "license": "ISC",
      "peer": true,
      "dependencies": {
        "glob": "^7.1.3"
      },
      "bin": {
        "rimraf": "bin.js"
      }
    },
    "node_modules/roarr": {
      "version": "2.15.4",
      "resolved": "https://registry.npmmirror.com/roarr/-/roarr-2.15.4.tgz",
      "integrity": "sha512-CHhPh+UNHD2GTXNYhPWLnU8ONHdI+5DI+4EYIAOaiD63rHeYlZvyh8P+in5999TTSFgUYuKUAjzRI4mdh/p+2A==",
      "dev": true,
      "license": "BSD-3-Clause",
      "optional": true,
      "dependencies": {
        "boolean": "^3.0.1",
        "detect-node": "^2.0.4",
        "globalthis": "^1.0.1",
        "json-stringify-safe": "^5.0.1",
        "semver-compare": "^1.0.0",
        "sprintf-js": "^1.1.2"
      },
      "engines": {
        "node": ">=8.0"
      }
    },
    "node_modules/rollup": {
      "version": "4.59.0",
      "resolved": "https://registry.npmmirror.com/rollup/-/rollup-4.59.0.tgz",
      "integrity": "sha512-2oMpl67a3zCH9H79LeMcbDhXW/UmWG/y2zuqnF2jQq5uq9TbM9TVyXvA4+t+ne2IIkBdrLpAaRQAvo7YI/Yyeg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@types/estree": "1.0.8"
      },
      "bin": {
        "rollup": "dist/bin/rollup"
      },
      "engines": {
        "node": ">=18.0.0",
        "npm": ">=8.0.0"
      },
      "optionalDependencies": {
        "@rollup/rollup-android-arm-eabi": "4.59.0",
        "@rollup/rollup-android-arm64": "4.59.0",
        "@rollup/rollup-darwin-arm64": "4.59.0",
        "@rollup/rollup-darwin-x64": "4.59.0",
        "@rollup/rollup-freebsd-arm64": "4.59.0",
        "@rollup/rollup-freebsd-x64": "4.59.0",
        "@rollup/rollup-linux-arm-gnueabihf": "4.59.0",
        "@rollup/rollup-linux-arm-musleabihf": "4.59.0",
        "@rollup/rollup-linux-arm64-gnu": "4.59.0",
        "@rollup/rollup-linux-arm64-musl": "4.59.0",
        "@rollup/rollup-linux-loong64-gnu": "4.59.0",
        "@rollup/rollup-linux-loong64-musl": "4.59.0",
        "@rollup/rollup-linux-ppc64-gnu": "4.59.0",
        "@rollup/rollup-linux-ppc64-musl": "4.59.0",
        "@rollup/rollup-linux-riscv64-gnu": "4.59.0",
        "@rollup/rollup-linux-riscv64-musl": "4.59.0",
        "@rollup/rollup-linux-s390x-gnu": "4.59.0",
        "@rollup/rollup-linux-x64-gnu": "4.59.0",
        "@rollup/rollup-linux-x64-musl": "4.59.0",
        "@rollup/rollup-openbsd-x64": "4.59.0",
        "@rollup/rollup-openharmony-arm64": "4.59.0",
        "@rollup/rollup-win32-arm64-msvc": "4.59.0",
        "@rollup/rollup-win32-ia32-msvc": "4.59.0",
        "@rollup/rollup-win32-x64-gnu": "4.59.0",
        "@rollup/rollup-win32-x64-msvc": "4.59.0",
        "fsevents": "~2.3.2"
      }
    },
    "node_modules/rollup/node_modules/@rollup/rollup-linux-arm64-gnu": {
      "version": "4.59.0",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm64-gnu/-/rollup-linux-arm64-gnu-4.59.0.tgz",
      "integrity": "sha512-jYgUGk5aLd1nUb1CtQ8E+t5JhLc9x5WdBKew9ZgAXg7DBk0ZHErLHdXM24rfX+bKrFe+Xp5YuJo54I5HFjGDAA==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/run-parallel": {
      "version": "1.2.0",
      "resolved": "https://registry.npmmirror.com/run-parallel/-/run-parallel-1.2.0.tgz",
      "integrity": "sha512-5l4VyZR86LZ/lDxZTR6jqL8AFE2S0IFLMP26AbjsLVADxHdhB/c0GUsH+y39UfCi3dzz8OlQuPmnaJOMoDHQBA==",
      "dev": true,
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/feross"
        },
        {
          "type": "patreon",
          "url": "https://www.patreon.com/feross"
        },
        {
          "type": "consulting",
          "url": "https://feross.org/support"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "queue-microtask": "^1.2.2"
      }
    },
    "node_modules/rxjs": {
      "version": "7.8.2",
      "resolved": "https://registry.npmmirror.com/rxjs/-/rxjs-7.8.2.tgz",
      "integrity": "sha512-dhKf903U/PQZY6boNNtAGdWbG85WAbjT/1xYoZIC7FAY0yWapOBQVsVrDl58W86//e1VpMNBtRV4MaXfdMySFA==",
      "dev": true,
      "license": "Apache-2.0",
      "dependencies": {
        "tslib": "^2.1.0"
      }
    },
    "node_modules/safe-buffer": {
      "version": "5.2.1",
      "resolved": "https://registry.npmmirror.com/safe-buffer/-/safe-buffer-5.2.1.tgz",
      "integrity": "sha512-rp3So07KcdmmKbGvgaNxQSJr7bGVSVk5S9Eq1F+ppbRo70+YeaDxkw5Dd8NPN+GD6bjnYm2VuPuCXmpuYvmCXQ==",
      "dev": true,
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/feross"
        },
        {
          "type": "patreon",
          "url": "https://www.patreon.com/feross"
        },
        {
          "type": "consulting",
          "url": "https://feross.org/support"
        }
      ],
      "license": "MIT"
    },
    "node_modules/safer-buffer": {
      "version": "2.1.2",
      "resolved": "https://registry.npmmirror.com/safer-buffer/-/safer-buffer-2.1.2.tgz",
      "integrity": "sha512-YZo3K82SD7Riyi0E1EQPojLz7kpepnSQI9IyPbHHg1XXXevb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/sanitize-filename": {
      "version": "1.6.3",
      "resolved": "https://registry.npmmirror.com/sanitize-filename/-/sanitize-filename-1.6.3.tgz",
      "integrity": "sha512-y/52Mcy7aw3gRm7IrcGDFx/bCk4AhRh2eI9luHOQM86nZsqwiRkkq2GekHXBBD+SmPidc8i2PqtYZl+pWJ8Oeg==",
      "dev": true,
      "license": "WTFPL OR ISC",
      "dependencies": {
        "truncate-utf8-bytes": "^1.0.0"
      }
    },
    "node_modules/sax": {
      "version": "1.5.0",
      "resolved": "https://registry.npmmirror.com/sax/-/sax-1.5.0.tgz",
      "integrity": "sha512-21IYA3Q5cQf089Z6tgaUTr7lDAyzoTPx5HRtbhsME8Udispad8dC/+sziTNugOEx54ilvatQ9YCzl4KQLPcRHA==",
      "dev": true,
      "license": "BlueOak-1.0.0",
      "engines": {
        "node": ">=11.0.0"
      }
    },
    "node_modules/scheduler": {
      "version": "0.23.2",
      "resolved": "https://registry.npmmirror.com/scheduler/-/scheduler-0.23.2.tgz",
      "integrity": "sha512-UOShsPwz7NrMUqhR6t0hWjFduvOzbtv7toDH1/hIrfRNIDBnnBWd0CwJTGvTpngVlmwGCdP9/Zl/tVrDqcuYzQ==",
      "license": "MIT",
      "dependencies": {
        "loose-envify": "^1.1.0"
      }
    },
    "node_modules/semver": {
      "version": "6.3.1",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-6.3.1.tgz",
      "integrity": "sha512-BR7VvDCVHO+q2xBEWskxS6DJE1qRnb7DxzUrogb71CWoSficBxYsiAGd+Kl0mmq/MprG9yArRkyrQxTO6XjMzA==",
      "dev": true,
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      }
    },
    "node_modules/semver-compare": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/semver-compare/-/semver-compare-1.0.0.tgz",
      "integrity": "sha512-YM3/ITh2MJ5MtzaM429anh+x2jiLVjqILF4m4oyQB18W7Ggea7BfqdH/wGMK7dDiMghv/6WG7znWMwUDzJiXow==",
      "dev": true,
      "license": "MIT",
      "optional": true
    },
    "node_modules/serialize-error": {
      "version": "7.0.1",
      "resolved": "https://registry.npmmirror.com/serialize-error/-/serialize-error-7.0.1.tgz",
      "integrity": "sha512-8I8TjW5KMOKsZQTvoxjuSIa7foAwPWGOts+6o7sgjz41/qMD9VQHEDxi6PBvK2l0MXUmqZyNpUK+T2tQaaElvw==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "dependencies": {
        "type-fest": "^0.13.1"
      },
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/set-blocking": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/set-blocking/-/set-blocking-2.0.0.tgz",
      "integrity": "sha512-KiKBS8AnWGEyLzofFfmvKwpdPzqiy16LvQfK3yv/fVH7Bj13/wl3JSR1J+rfgRE9q7xUJK4qvgS8raSOeLUehw==",
      "license": "ISC"
    },
    "node_modules/shebang-command": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/shebang-command/-/shebang-command-2.0.0.tgz",
      "integrity": "sha512-kHxr2zZpYtdmrN1qDjrrX/Z1rR1kG8Dx+gkpK1G4eXmvXswmcE1hTWBWYUzlraYw1/yZp6YuDY77YtvbN0dmDA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "shebang-regex": "^3.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/shebang-regex": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/shebang-regex/-/shebang-regex-3.0.0.tgz",
      "integrity": "sha512-7++dFhtcx3353uBaq8DDR4NuxBetBzC7ZQOhmTQInHEd6bSrXdiEyzCvG07Z44UYdLShWUyXt5M/yhz8ekcb1A==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/shell-quote": {
      "version": "1.8.3",
      "resolved": "https://registry.npmmirror.com/shell-quote/-/shell-quote-1.8.3.tgz",
      "integrity": "sha512-ObmnIF4hXNg1BqhnHmgbDETF8dLPCggZWBjkQfhZpbszZnYur5DUljTcCHii5LC3J5E0yeO/1LIMyH+UvHQgyw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/signal-exit": {
      "version": "3.0.7",
      "resolved": "https://registry.npmmirror.com/signal-exit/-/signal-exit-3.0.7.tgz",
      "integrity": "sha512-wnD2ZE+l+SPC/uoS0vXeE9L1+0wuaMqKlfz9AMUo38JsyLSBWSFcHR1Rri62LZc12vLr1gb3jl7iwQhgwpAbGQ==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/simple-update-notifier": {
      "version": "2.0.0",
      "resolved": "https://registry.npmmirror.com/simple-update-notifier/-/simple-update-notifier-2.0.0.tgz",
      "integrity": "sha512-a2B9Y0KlNXl9u/vsW6sTIu9vGEpfKu2wRV6l1H3XEas/0gUIzGzBoP/IouTcUQbm9JWZLH3COxyn03TYlFax6w==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "semver": "^7.5.3"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/simple-update-notifier/node_modules/semver": {
      "version": "7.7.4",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-7.7.4.tgz",
      "integrity": "sha512-vFKC2IEtQnVhpT78h1Yp8wzwrf8CM+MzKMHGJZfBtzhZNycRFnXsHk6E5TxIkkMsgNS7mdX3AGB7x2QM2di4lA==",
      "dev": true,
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/slice-ansi": {
      "version": "3.0.0",
      "resolved": "https://registry.npmmirror.com/slice-ansi/-/slice-ansi-3.0.0.tgz",
      "integrity": "sha512-pSyv7bSTC7ig9Dcgbw9AuRNUb5k5V6oDudjZoMBSr13qpLBG7tB+zgCkARjq7xIUgdz5P1Qe8u+rSGdouOOIyQ==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "dependencies": {
        "ansi-styles": "^4.0.0",
        "astral-regex": "^2.0.0",
        "is-fullwidth-code-point": "^3.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/smart-buffer": {
      "version": "4.2.0",
      "resolved": "https://registry.npmmirror.com/smart-buffer/-/smart-buffer-4.2.0.tgz",
      "integrity": "sha512-94hK0Hh8rPqQl2xXc3HsaBoOXKV20MToPkcXvwbISWLEs+64sBq5kFgn2kJDHb1Pry9yrP0dxrCI9RRci7RXKg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 6.0.0",
        "npm": ">= 3.0.0"
      }
    },
    "node_modules/socks": {
      "version": "2.8.7",
      "resolved": "https://registry.npmmirror.com/socks/-/socks-2.8.7.tgz",
      "integrity": "sha512-HLpt+uLy/pxB+bum/9DzAgiKS8CX1EvbWxI4zlmgGCExImLdiad2iCwXT5Z4c9c3Eq8rP2318mPW2c+QbtjK8A==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "ip-address": "^10.0.1",
        "smart-buffer": "^4.2.0"
      },
      "engines": {
        "node": ">= 10.0.0",
        "npm": ">= 3.0.0"
      }
    },
    "node_modules/socks-proxy-agent": {
      "version": "8.0.5",
      "resolved": "https://registry.npmmirror.com/socks-proxy-agent/-/socks-proxy-agent-8.0.5.tgz",
      "integrity": "sha512-HehCEsotFqbPW9sJ8WVYB6UbmIMv7kUUORIF2Nncq4VQvBfNBLibW9YZR5dlYCSUhwcD628pRllm7n+E+YTzJw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "agent-base": "^7.1.2",
        "debug": "^4.3.4",
        "socks": "^2.8.3"
      },
      "engines": {
        "node": ">= 14"
      }
    },
    "node_modules/source-map": {
      "version": "0.6.1",
      "resolved": "https://registry.npmmirror.com/source-map/-/source-map-0.6.1.tgz",
      "integrity": "sha512-UjgapumWlbMhkBgzT7Ykc5YXUT46F0iKu8SGXq0bcwP5dz/h0Plj6enJqjz1Zbq2l5WaqYnrVbwWOWMyF3F47g==",
      "dev": true,
      "license": "BSD-3-Clause",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/source-map-js": {
      "version": "1.2.1",
      "resolved": "https://registry.npmmirror.com/source-map-js/-/source-map-js-1.2.1.tgz",
      "integrity": "sha512-UXWMKhLOwVKb728IUtQPXxfYU+usdybtUrK/8uGE8CQMvrhOpwvzDBwj0QhSL7MQc7vIsISBG8VQ8+IDQxpfQA==",
      "dev": true,
      "license": "BSD-3-Clause",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/source-map-support": {
      "version": "0.5.21",
      "resolved": "https://registry.npmmirror.com/source-map-support/-/source-map-support-0.5.21.tgz",
      "integrity": "sha512-uBHU3L3czsIyYXKX88fdrGovxdSCoTGDRZ6SYXtSRxLZUzHg5P/66Ht6uoUlHu9EZod+inXhKo3qQgwXUT/y1w==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "buffer-from": "^1.0.0",
        "source-map": "^0.6.0"
      }
    },
    "node_modules/sprintf-js": {
      "version": "1.1.3",
      "resolved": "https://registry.npmmirror.com/sprintf-js/-/sprintf-js-1.1.3.tgz",
      "integrity": "sha512-Oo+0REFV59/rz3gfJNKQiBlwfHaSESl1pcGyABQsnnIfWOFt6JNj5gCog2U6MLZ//IGYD+nA8nI+mTShREReaA==",
      "dev": true,
      "license": "BSD-3-Clause",
      "optional": true
    },
    "node_modules/ssri": {
      "version": "12.0.0",
      "resolved": "https://registry.npmmirror.com/ssri/-/ssri-12.0.0.tgz",
      "integrity": "sha512-S7iGNosepx9RadX82oimUkvr0Ct7IjJbEbs4mJcTxst8um95J3sDYU1RBEOvdu6oL1Wek2ODI5i4MAw+dZ6cAQ==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "minipass": "^7.0.3"
      },
      "engines": {
        "node": "^18.17.0 || >=20.5.0"
      }
    },
    "node_modules/stat-mode": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/stat-mode/-/stat-mode-1.0.0.tgz",
      "integrity": "sha512-jH9EhtKIjuXZ2cWxmXS8ZP80XyC3iasQxMDV8jzhNJpfDb7VbQLVW4Wvsxz9QZvzV+G4YoSfBUVKDOyxLzi/sg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/string_decoder": {
      "version": "1.3.0",
      "resolved": "https://registry.npmmirror.com/string_decoder/-/string_decoder-1.3.0.tgz",
      "integrity": "sha512-hkRX8U1WjJFd8LsDJ2yQ/wWWxaopEsABU1XfkM8A+j0+85JAGppt16cr1Whg6KIbb4okU6Mql6BOj+uup/wKeA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "safe-buffer": "~5.2.0"
      }
    },
    "node_modules/string-width": {
      "version": "4.2.3",
      "resolved": "https://registry.npmmirror.com/string-width/-/string-width-4.2.3.tgz",
      "integrity": "sha512-wKyQRQpjJ0sIp62ErSZdGsjMJWsap5oRNihHhu6G7JVO/9jIB6UyevL+tXuOqrng8j/cxKTWyWUwvSTriiZz/g==",
      "license": "MIT",
      "dependencies": {
        "emoji-regex": "^8.0.0",
        "is-fullwidth-code-point": "^3.0.0",
        "strip-ansi": "^6.0.1"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/string-width-cjs": {
      "name": "string-width",
      "version": "4.2.3",
      "resolved": "https://registry.npmmirror.com/string-width/-/string-width-4.2.3.tgz",
      "integrity": "sha512-wKyQRQpjJ0sIp62ErSZdGsjMJWsap5oRNihHhu6G7JVO/9jIB6UyevL+tXuOqrng8j/cxKTWyWUwvSTriiZz/g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "emoji-regex": "^8.0.0",
        "is-fullwidth-code-point": "^3.0.0",
        "strip-ansi": "^6.0.1"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/strip-ansi": {
      "version": "6.0.1",
      "resolved": "https://registry.npmmirror.com/strip-ansi/-/strip-ansi-6.0.1.tgz",
      "integrity": "sha512-Y38VPSHcqkFrCpFnQ9vuSXmquuv5oXOKpGeT6aGrr3o3Gc9AlVa6JBfUSOCnbxGGZF+/0ooI7KrPuUSztUdU5A==",
      "license": "MIT",
      "dependencies": {
        "ansi-regex": "^5.0.1"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/strip-ansi-cjs": {
      "name": "strip-ansi",
      "version": "6.0.1",
      "resolved": "https://registry.npmmirror.com/strip-ansi/-/strip-ansi-6.0.1.tgz",
      "integrity": "sha512-Y38VPSHcqkFrCpFnQ9vuSXmquuv5oXOKpGeT6aGrr3o3Gc9AlVa6JBfUSOCnbxGGZF+/0ooI7KrPuUSztUdU5A==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "ansi-regex": "^5.0.1"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/sucrase": {
      "version": "3.35.1",
      "resolved": "https://registry.npmmirror.com/sucrase/-/sucrase-3.35.1.tgz",
      "integrity": "sha512-DhuTmvZWux4H1UOnWMB3sk0sbaCVOoQZjv8u1rDoTV0HTdGem9hkAZtl4JZy8P2z4Bg0nT+YMeOFyVr4zcG5Tw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@jridgewell/gen-mapping": "^0.3.2",
        "commander": "^4.0.0",
        "lines-and-columns": "^1.1.6",
        "mz": "^2.7.0",
        "pirates": "^4.0.1",
        "tinyglobby": "^0.2.11",
        "ts-interface-checker": "^0.1.9"
      },
      "bin": {
        "sucrase": "bin/sucrase",
        "sucrase-node": "bin/sucrase-node"
      },
      "engines": {
        "node": ">=16 || 14 >=14.17"
      }
    },
    "node_modules/sucrase/node_modules/commander": {
      "version": "4.1.1",
      "resolved": "https://registry.npmmirror.com/commander/-/commander-4.1.1.tgz",
      "integrity": "sha512-NOKm8xhkzAjzFx8B2v5OAHT+u5pRQc2UCa2Vq9jYL/31o2wi9mxBA7LIFs3sV5VSC49z6pEhfbMULvShKj26WA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/sumchecker": {
      "version": "3.0.1",
      "resolved": "https://registry.npmmirror.com/sumchecker/-/sumchecker-3.0.1.tgz",
      "integrity": "sha512-MvjXzkz/BOfyVDkG0oFOtBxHX2u3gKbMHIF/dXblZsgD3BWOFLmHovIpZY7BykJdAjcqRCBi1WYBNdEC9yI7vg==",
      "dev": true,
      "license": "Apache-2.0",
      "dependencies": {
        "debug": "^4.1.0"
      },
      "engines": {
        "node": ">= 8.0"
      }
    },
    "node_modules/supports-color": {
      "version": "8.1.1",
      "resolved": "https://registry.npmmirror.com/supports-color/-/supports-color-8.1.1.tgz",
      "integrity": "sha512-MpUEN2OodtUzxvKQl72cUF7RQ5EiHsGvSsVG0ia9c5RbWGL2CI4C7EpPS8UTBIplnlzZiNuV56w+FuNxy3ty2Q==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "has-flag": "^4.0.0"
      },
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/chalk/supports-color?sponsor=1"
      }
    },
    "node_modules/supports-preserve-symlinks-flag": {
      "version": "1.0.0",
      "resolved": "https://registry.npmmirror.com/supports-preserve-symlinks-flag/-/supports-preserve-symlinks-flag-1.0.0.tgz",
      "integrity": "sha512-ot0WnXS9fgdkgIcePe6RHNk1WA8+muPa6cSjeR3V8K27q9BB1rTE3R1p7Hv0z1ZyAc8s6Vvv8DIyWf681MAt0w==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/tailwindcss": {
      "version": "3.4.19",
      "resolved": "https://registry.npmmirror.com/tailwindcss/-/tailwindcss-3.4.19.tgz",
      "integrity": "sha512-3ofp+LL8E+pK/JuPLPggVAIaEuhvIz4qNcf3nA1Xn2o/7fb7s/TYpHhwGDv1ZU3PkBluUVaF8PyCHcm48cKLWQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@alloc/quick-lru": "^5.2.0",
        "arg": "^5.0.2",
        "chokidar": "^3.6.0",
        "didyoumean": "^1.2.2",
        "dlv": "^1.1.3",
        "fast-glob": "^3.3.2",
        "glob-parent": "^6.0.2",
        "is-glob": "^4.0.3",
        "jiti": "^1.21.7",
        "lilconfig": "^3.1.3",
        "micromatch": "^4.0.8",
        "normalize-path": "^3.0.0",
        "object-hash": "^3.0.0",
        "picocolors": "^1.1.1",
        "postcss": "^8.4.47",
        "postcss-import": "^15.1.0",
        "postcss-js": "^4.0.1",
        "postcss-load-config": "^4.0.2 || ^5.0 || ^6.0",
        "postcss-nested": "^6.2.0",
        "postcss-selector-parser": "^6.1.2",
        "resolve": "^1.22.8",
        "sucrase": "^3.35.0"
      },
      "bin": {
        "tailwind": "lib/cli.js",
        "tailwindcss": "lib/cli.js"
      },
      "engines": {
        "node": ">=14.0.0"
      }
    },
    "node_modules/tailwindcss/node_modules/jiti": {
      "version": "1.21.7",
      "resolved": "https://registry.npmmirror.com/jiti/-/jiti-1.21.7.tgz",
      "integrity": "sha512-/imKNG4EbWNrVjoNC/1H5/9GFy+tqjGBHCaSsN+P2RnPqjsLmv6UD3Ej+Kj8nBWaRAwyk7kK5ZUc+OEatnTR3A==",
      "dev": true,
      "license": "MIT",
      "bin": {
        "jiti": "bin/jiti.js"
      }
    },
    "node_modules/tailwindcss/node_modules/postcss-selector-parser": {
      "version": "6.1.2",
      "resolved": "https://registry.npmmirror.com/postcss-selector-parser/-/postcss-selector-parser-6.1.2.tgz",
      "integrity": "sha512-Q8qQfPiZ+THO/3ZrOrO0cJJKfpYCagtMUkXbnEfmgUjwXg6z/WBeOyS9APBBPCTSiDV+s4SwQGu8yFsiMRIudg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "cssesc": "^3.0.0",
        "util-deprecate": "^1.0.2"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/tar": {
      "version": "7.5.11",
      "resolved": "https://registry.npmmirror.com/tar/-/tar-7.5.11.tgz",
      "integrity": "sha512-ChjMH33/KetonMTAtpYdgUFr0tbz69Fp2v7zWxQfYZX4g5ZN2nOBXm1R2xyA+lMIKrLKIoKAwFj93jE/avX9cQ==",
      "dev": true,
      "license": "BlueOak-1.0.0",
      "dependencies": {
        "@isaacs/fs-minipass": "^4.0.0",
        "chownr": "^3.0.0",
        "minipass": "^7.1.2",
        "minizlib": "^3.1.0",
        "yallist": "^5.0.0"
      },
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/tar/node_modules/yallist": {
      "version": "5.0.0",
      "resolved": "https://registry.npmmirror.com/yallist/-/yallist-5.0.0.tgz",
      "integrity": "sha512-YgvUTfwqyc7UXVMrB+SImsVYSmTS8X/tSrtdNZMImM+n7+QTriRXyXim0mBrTXNeqzVF0KWGgHPeiyViFFrNDw==",
      "dev": true,
      "license": "BlueOak-1.0.0",
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/temp": {
      "version": "0.9.4",
      "resolved": "https://registry.npmmirror.com/temp/-/temp-0.9.4.tgz",
      "integrity": "sha512-yYrrsWnrXMcdsnu/7YMYAofM1ktpL5By7vZhf15CrXijWWrEYZks5AXBudalfSWJLlnen/QUJUB5aoB0kqZUGA==",
      "dev": true,
      "license": "MIT",
      "peer": true,
      "dependencies": {
        "mkdirp": "^0.5.1",
        "rimraf": "~2.6.2"
      },
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/temp-file": {
      "version": "3.4.0",
      "resolved": "https://registry.npmmirror.com/temp-file/-/temp-file-3.4.0.tgz",
      "integrity": "sha512-C5tjlC/HCtVUOi3KWVokd4vHVViOmGjtLwIh4MuzPo/nMYTV/p1urt3RnMz2IWXDdKEGJH3k5+KPxtqRsUYGtg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "async-exit-hook": "^2.0.1",
        "fs-extra": "^10.0.0"
      }
    },
    "node_modules/temp-file/node_modules/fs-extra": {
      "version": "10.1.0",
      "resolved": "https://registry.npmmirror.com/fs-extra/-/fs-extra-10.1.0.tgz",
      "integrity": "sha512-oRXApq54ETRj4eMiFzGnHWGy+zo5raudjuxN0b8H7s/RU2oW0Wvsx9O0ACRN/kRq9E8Vu/ReskGB5o3ji+FzHQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "graceful-fs": "^4.2.0",
        "jsonfile": "^6.0.1",
        "universalify": "^2.0.0"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/temp-file/node_modules/jsonfile": {
      "version": "6.2.0",
      "resolved": "https://registry.npmmirror.com/jsonfile/-/jsonfile-6.2.0.tgz",
      "integrity": "sha512-FGuPw30AdOIUTRMC2OMRtQV+jkVj2cfPqSeWXv1NEAJ1qZ5zb1X6z1mFhbfOB/iy3ssJCD+3KuZ8r8C3uVFlAg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "universalify": "^2.0.0"
      },
      "optionalDependencies": {
        "graceful-fs": "^4.1.6"
      }
    },
    "node_modules/temp-file/node_modules/universalify": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/universalify/-/universalify-2.0.1.tgz",
      "integrity": "sha512-gptHNQghINnc/vTGIk0SOFGFNXw7JVrlRUtConJRlvaw6DuX0wO5Jeko9sWrMBhh+PsYAZ7oXAiOnf/UKogyiw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 10.0.0"
      }
    },
    "node_modules/thenify": {
      "version": "3.3.1",
      "resolved": "https://registry.npmmirror.com/thenify/-/thenify-3.3.1.tgz",
      "integrity": "sha512-RVZSIV5IG10Hk3enotrhvz0T9em6cyHBLkH/YAZuKqd8hRkKhSfCGIcP2KUY0EPxndzANBmNllzWPwak+bheSw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "any-promise": "^1.0.0"
      }
    },
    "node_modules/thenify-all": {
      "version": "1.6.0",
      "resolved": "https://registry.npmmirror.com/thenify-all/-/thenify-all-1.6.0.tgz",
      "integrity": "sha512-RNxQH/qI8/t3thXJDwcstUO4zeqo64+Uy/+sNVRBx4Xn2OX+OZ9oP+iJnNFqplFra2ZUVeKCSa2oVWi3T4uVmA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "thenify": ">= 3.1.0 < 4"
      },
      "engines": {
        "node": ">=0.8"
      }
    },
    "node_modules/tiny-async-pool": {
      "version": "1.3.0",
      "resolved": "https://registry.npmmirror.com/tiny-async-pool/-/tiny-async-pool-1.3.0.tgz",
      "integrity": "sha512-01EAw5EDrcVrdgyCLgoSPvqznC0sVxDSVeiOz09FUpjh71G79VCqneOr+xvt7T1r76CF6ZZfPjHorN2+d+3mqA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "semver": "^5.5.0"
      }
    },
    "node_modules/tiny-async-pool/node_modules/semver": {
      "version": "5.7.2",
      "resolved": "https://registry.npmmirror.com/semver/-/semver-5.7.2.tgz",
      "integrity": "sha512-cBznnQ9KjJqU67B52RMC65CMarK2600WFnbkcaiwWq3xy/5haFJlshgnpjovMVJ+Hff49d8GEn0b87C5pDQ10g==",
      "dev": true,
      "license": "ISC",
      "bin": {
        "semver": "bin/semver"
      }
    },
    "node_modules/tinyglobby": {
      "version": "0.2.15",
      "resolved": "https://registry.npmmirror.com/tinyglobby/-/tinyglobby-0.2.15.tgz",
      "integrity": "sha512-j2Zq4NyQYG5XMST4cbs02Ak8iJUdxRM0XI5QyxXuZOzKOINmWurp3smXu3y5wDcJrptwpSjgXHzIQxR0omXljQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "fdir": "^6.5.0",
        "picomatch": "^4.0.3"
      },
      "engines": {
        "node": ">=12.0.0"
      },
      "funding": {
        "url": "https://github.com/sponsors/SuperchupuDev"
      }
    },
    "node_modules/tmp": {
      "version": "0.2.5",
      "resolved": "https://registry.npmmirror.com/tmp/-/tmp-0.2.5.tgz",
      "integrity": "sha512-voyz6MApa1rQGUxT3E+BK7/ROe8itEx7vD8/HEvt4xwXucvQ5G5oeEiHkmHZJuBO21RpOf+YYm9MOivj709jow==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=14.14"
      }
    },
    "node_modules/tmp-promise": {
      "version": "3.0.3",
      "resolved": "https://registry.npmmirror.com/tmp-promise/-/tmp-promise-3.0.3.tgz",
      "integrity": "sha512-RwM7MoPojPxsOBYnyd2hy0bxtIlVrihNs9pj5SUvY8Zz1sQcQG2tG1hSr8PDxfgEB8RNKDhqbIlroIarSNDNsQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "tmp": "^0.2.0"
      }
    },
    "node_modules/to-regex-range": {
      "version": "5.0.1",
      "resolved": "https://registry.npmmirror.com/to-regex-range/-/to-regex-range-5.0.1.tgz",
      "integrity": "sha512-65P7iz6X5yEr1cwcgvQxbbIw7Uk3gOy5dIdtZ4rDveLqhrdJP+Li/Hx6tyK0NEb+2GCyneCMJiGqrADCSNk8sQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "is-number": "^7.0.0"
      },
      "engines": {
        "node": ">=8.0"
      }
    },
    "node_modules/tree-kill": {
      "version": "1.2.2",
      "resolved": "https://registry.npmmirror.com/tree-kill/-/tree-kill-1.2.2.tgz",
      "integrity": "sha512-L0Orpi8qGpRG//Nd+H90vFB+3iHnue1zSSGmNOOCh1GLJ7rUKVwV2HvijphGQS2UmhUZewS9VgvxYIdgr+fG1A==",
      "dev": true,
      "license": "MIT",
      "bin": {
        "tree-kill": "cli.js"
      }
    },
    "node_modules/truncate-utf8-bytes": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/truncate-utf8-bytes/-/truncate-utf8-bytes-1.0.2.tgz",
      "integrity": "sha512-95Pu1QXQvruGEhv62XCMO3Mm90GscOCClvrIUwCM0PYOXK3kaF3l3sIHxx71ThJfcbM2O5Au6SO3AWCSEfW4mQ==",
      "dev": true,
      "license": "WTFPL",
      "dependencies": {
        "utf8-byte-length": "^1.0.1"
      }
    },
    "node_modules/ts-interface-checker": {
      "version": "0.1.13",
      "resolved": "https://registry.npmmirror.com/ts-interface-checker/-/ts-interface-checker-0.1.13.tgz",
      "integrity": "sha512-Y/arvbn+rrz3JCKl9C4kVNfTfSm2/mEp5FSz5EsZSANGPSlQrpRI5M4PKF+mJnE52jOO90PnPSc3Ur3bTQw0gA==",
      "dev": true,
      "license": "Apache-2.0"
    },
    "node_modules/tslib": {
      "version": "2.8.1",
      "resolved": "https://registry.npmmirror.com/tslib/-/tslib-2.8.1.tgz",
      "integrity": "sha512-oJFu94HQb+KVduSUQL7wnpmqnfmLsOA/nAh6b6EH0wCEoK0/mPeXU6c3wKDV83MkOuHPRHtSXKKU99IBazS/2w==",
      "dev": true,
      "license": "0BSD"
    },
    "node_modules/type-fest": {
      "version": "0.13.1",
      "resolved": "https://registry.npmmirror.com/type-fest/-/type-fest-0.13.1.tgz",
      "integrity": "sha512-34R7HTnG0XIJcBSn5XhDd7nNFPRcXYRZrBB2O2jdKqYODldSzBAqzsWoZYYvduky73toYS/ESqxPvkDf/F0XMg==",
      "dev": true,
      "license": "(MIT OR CC0-1.0)",
      "optional": true,
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/typescript": {
      "version": "5.9.3",
      "resolved": "https://registry.npmmirror.com/typescript/-/typescript-5.9.3.tgz",
      "integrity": "sha512-jl1vZzPDinLr9eUt3J/t7V6FgNEw9QjvBPdysz9KfQDD41fQrC2Y4vKQdiaUpFT4bXlb1RHhLpp8wtm6M5TgSw==",
      "dev": true,
      "license": "Apache-2.0",
      "bin": {
        "tsc": "bin/tsc",
        "tsserver": "bin/tsserver"
      },
      "engines": {
        "node": ">=14.17"
      }
    },
    "node_modules/undici-types": {
      "version": "6.21.0",
      "resolved": "https://registry.npmmirror.com/undici-types/-/undici-types-6.21.0.tgz",
      "integrity": "sha512-iwDZqg0QAGrg9Rav5H4n0M64c3mkR59cJ6wQp+7C4nI0gsmExaedaYLNO44eT4AtBBwjbTiGPMlt2Md0T9H9JQ==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/unique-filename": {
      "version": "4.0.0",
      "resolved": "https://registry.npmmirror.com/unique-filename/-/unique-filename-4.0.0.tgz",
      "integrity": "sha512-XSnEewXmQ+veP7xX2dS5Q4yZAvO40cBN2MWkJ7D/6sW4Dg6wYBNwM1Vrnz1FhH5AdeLIlUXRI9e28z1YZi71NQ==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "unique-slug": "^5.0.0"
      },
      "engines": {
        "node": "^18.17.0 || >=20.5.0"
      }
    },
    "node_modules/unique-slug": {
      "version": "5.0.0",
      "resolved": "https://registry.npmmirror.com/unique-slug/-/unique-slug-5.0.0.tgz",
      "integrity": "sha512-9OdaqO5kwqR+1kVgHAhsp5vPNU0hnxRa26rBFNfNgM7M6pNtgzeBn3s/xbyCQL3dcjzOatcef6UUHpB/6MaETg==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "imurmurhash": "^0.1.4"
      },
      "engines": {
        "node": "^18.17.0 || >=20.5.0"
      }
    },
    "node_modules/universalify": {
      "version": "0.1.2",
      "resolved": "https://registry.npmmirror.com/universalify/-/universalify-0.1.2.tgz",
      "integrity": "sha512-rBJeI5CXAlmy1pV+617WB9J63U6XcazHHF2f2dbJix4XzpUF0RS3Zbj0FGIOCAva5P/d/GBOYaACQ1w+0azUkg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">= 4.0.0"
      }
    },
    "node_modules/update-browserslist-db": {
      "version": "1.2.3",
      "resolved": "https://registry.npmmirror.com/update-browserslist-db/-/update-browserslist-db-1.2.3.tgz",
      "integrity": "sha512-Js0m9cx+qOgDxo0eMiFGEueWztz+d4+M3rGlmKPT+T4IS/jP4ylw3Nwpu6cpTTP8R1MAC1kF4VbdLt3ARf209w==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/browserslist"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/browserslist"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "escalade": "^3.2.0",
        "picocolors": "^1.1.1"
      },
      "bin": {
        "update-browserslist-db": "cli.js"
      },
      "peerDependencies": {
        "browserslist": ">= 4.21.0"
      }
    },
    "node_modules/uri-js": {
      "version": "4.4.1",
      "resolved": "https://registry.npmmirror.com/uri-js/-/uri-js-4.4.1.tgz",
      "integrity": "sha512-7rKUyy33Q1yc98pQ1DAmLtwX109F7TIfWlW1Ydo8Wl1ii1SeHieeh0HHfPeL2fMXK6z0s8ecKs9frCuLJvndBg==",
      "dev": true,
      "license": "BSD-2-Clause",
      "dependencies": {
        "punycode": "^2.1.0"
      }
    },
    "node_modules/utf8-byte-length": {
      "version": "1.0.5",
      "resolved": "https://registry.npmmirror.com/utf8-byte-length/-/utf8-byte-length-1.0.5.tgz",
      "integrity": "sha512-Xn0w3MtiQ6zoz2vFyUVruaCL53O/DwUvkEeOvj+uulMm0BkUGYWmBYVyElqZaSLhY6ZD0ulfU3aBra2aVT4xfA==",
      "dev": true,
      "license": "(WTFPL OR MIT)"
    },
    "node_modules/util-deprecate": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/util-deprecate/-/util-deprecate-1.0.2.tgz",
      "integrity": "sha512-EPD5q1uXyFxJpCrLnCc1nHnq3gOa6DZBocAIiI2TaSCA7VCJ1UJDMagCzIkXNsUYfD1daK//LTEQ8xiIbrHtcw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/verror": {
      "version": "1.10.1",
      "resolved": "https://registry.npmmirror.com/verror/-/verror-1.10.1.tgz",
      "integrity": "sha512-veufcmxri4e3XSrT0xwfUR7kguIkaxBeosDg00yDWhk49wdwkSUrvvsm7nc75e1PUyvIeZj6nS8VQRYz2/S4Xg==",
      "dev": true,
      "license": "MIT",
      "optional": true,
      "dependencies": {
        "assert-plus": "^1.0.0",
        "core-util-is": "1.0.2",
        "extsprintf": "^1.2.0"
      },
      "engines": {
        "node": ">=0.6.0"
      }
    },
    "node_modules/vite": {
      "version": "6.4.1",
      "resolved": "https://registry.npmmirror.com/vite/-/vite-6.4.1.tgz",
      "integrity": "sha512-+Oxm7q9hDoLMyJOYfUYBuHQo+dkAloi33apOPP56pzj+vsdJDzr+j1NISE5pyaAuKL4A3UD34qd0lx5+kfKp2g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "esbuild": "^0.25.0",
        "fdir": "^6.4.4",
        "picomatch": "^4.0.2",
        "postcss": "^8.5.3",
        "rollup": "^4.34.9",
        "tinyglobby": "^0.2.13"
      },
      "bin": {
        "vite": "bin/vite.js"
      },
      "engines": {
        "node": "^18.0.0 || ^20.0.0 || >=22.0.0"
      },
      "funding": {
        "url": "https://github.com/vitejs/vite?sponsor=1"
      },
      "optionalDependencies": {
        "fsevents": "~2.3.3"
      },
      "peerDependencies": {
        "@types/node": "^18.0.0 || ^20.0.0 || >=22.0.0",
        "jiti": ">=1.21.0",
        "less": "*",
        "lightningcss": "^1.21.0",
        "sass": "*",
        "sass-embedded": "*",
        "stylus": "*",
        "sugarss": "*",
        "terser": "^5.16.0",
        "tsx": "^4.8.1",
        "yaml": "^2.4.2"
      },
      "peerDependenciesMeta": {
        "@types/node": {
          "optional": true
        },
        "jiti": {
          "optional": true
        },
        "less": {
          "optional": true
        },
        "lightningcss": {
          "optional": true
        },
        "sass": {
          "optional": true
        },
        "sass-embedded": {
          "optional": true
        },
        "stylus": {
          "optional": true
        },
        "sugarss": {
          "optional": true
        },
        "terser": {
          "optional": true
        },
        "tsx": {
          "optional": true
        },
        "yaml": {
          "optional": true
        }
      }
    },
    "node_modules/wait-on": {
      "version": "8.0.5",
      "resolved": "https://registry.npmmirror.com/wait-on/-/wait-on-8.0.5.tgz",
      "integrity": "sha512-J3WlS0txVHkhLRb2FsmRg3dkMTCV1+M6Xra3Ho7HzZDHpE7DCOnoSoCJsZotrmW3uRMhvIJGSKUKrh/MeF4iag==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "axios": "^1.12.1",
        "joi": "^18.0.1",
        "lodash": "^4.17.21",
        "minimist": "^1.2.8",
        "rxjs": "^7.8.2"
      },
      "bin": {
        "wait-on": "bin/wait-on"
      },
      "engines": {
        "node": ">=12.0.0"
      }
    },
    "node_modules/wcwidth": {
      "version": "1.0.1",
      "resolved": "https://registry.npmmirror.com/wcwidth/-/wcwidth-1.0.1.tgz",
      "integrity": "sha512-XHPEwS0q6TaxcvG85+8EYkbiCux2XtWG2mkc47Ng2A77BQu9+DqIOJldST4HgPkuea7dvKSj5VgX3P1d4rW8Tg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "defaults": "^1.0.3"
      }
    },
    "node_modules/which": {
      "version": "2.0.2",
      "resolved": "https://registry.npmmirror.com/which/-/which-2.0.2.tgz",
      "integrity": "sha512-BLI3Tl1TW3Pvl70l3yq3Y64i+awpwXqsGBYWkkqMtnbXgrMD+yj7rhW0kuEDxzJaYXGjEW5ogapKNMEKNMjibA==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "isexe": "^2.0.0"
      },
      "bin": {
        "node-which": "bin/node-which"
      },
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/which-module": {
      "version": "2.0.1",
      "resolved": "https://registry.npmmirror.com/which-module/-/which-module-2.0.1.tgz",
      "integrity": "sha512-iBdZ57RDvnOR9AGBhML2vFZf7h8vmBjhoaZqODJBFWHVtKkDmKuHai3cx5PgVMrX5YDNp27AofYbAwctSS+vhQ==",
      "license": "ISC"
    },
    "node_modules/wrap-ansi": {
      "version": "7.0.0",
      "resolved": "https://registry.npmmirror.com/wrap-ansi/-/wrap-ansi-7.0.0.tgz",
      "integrity": "sha512-YVGIj2kamLSTxw6NsZjoBxfSwsn0ycdesmc4p+Q21c5zPuZ1pl+NfxVdxPtdHvmNVOQ6XSYG4AUtyt/Fi7D16Q==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "ansi-styles": "^4.0.0",
        "string-width": "^4.1.0",
        "strip-ansi": "^6.0.0"
      },
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/chalk/wrap-ansi?sponsor=1"
      }
    },
    "node_modules/wrap-ansi-cjs": {
      "name": "wrap-ansi",
      "version": "7.0.0",
      "resolved": "https://registry.npmmirror.com/wrap-ansi/-/wrap-ansi-7.0.0.tgz",
      "integrity": "sha512-YVGIj2kamLSTxw6NsZjoBxfSwsn0ycdesmc4p+Q21c5zPuZ1pl+NfxVdxPtdHvmNVOQ6XSYG4AUtyt/Fi7D16Q==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "ansi-styles": "^4.0.0",
        "string-width": "^4.1.0",
        "strip-ansi": "^6.0.0"
      },
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/chalk/wrap-ansi?sponsor=1"
      }
    },
    "node_modules/wrappy": {
      "version": "1.0.2",
      "resolved": "https://registry.npmmirror.com/wrappy/-/wrappy-1.0.2.tgz",
      "integrity": "sha512-l4Sp/DRseor9wL6EvV2+TuQn63dMkPjZ/sp9XkghTEbV9KlPS1xUsZ3u7/IQO4wxtcFB4bgpQPRcR3QCvezPcQ==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/xmlbuilder": {
      "version": "15.1.1",
      "resolved": "https://registry.npmmirror.com/xmlbuilder/-/xmlbuilder-15.1.1.tgz",
      "integrity": "sha512-yMqGBqtXyeN1e3TGYvgNgDVZ3j84W4cwkOXQswghol6APgZWaff9lnbvN7MHYJOiXsvGPXtjTYJEiC9J2wv9Eg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=8.0"
      }
    },
    "node_modules/y18n": {
      "version": "5.0.8",
      "resolved": "https://registry.npmmirror.com/y18n/-/y18n-5.0.8.tgz",
      "integrity": "sha512-0pfFzegeDWJHJIAmTLRP2DwHjdF5s7jo9tuztdQxAhINCdvS+3nGINqPd00AphqJR/0LhANUS6/+7SCb98YOfA==",
      "dev": true,
      "license": "ISC",
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/yallist": {
      "version": "3.1.1",
      "resolved": "https://registry.npmmirror.com/yallist/-/yallist-3.1.1.tgz",
      "integrity": "sha512-a4UGQaWPH59mOXUYnAG2ewncQS4i4F43Tv3JoAM+s2VDAmS9NsK8GpDMLrCHPksFT7h3K6TOoUNn2pb7RoXx4g==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/yargs": {
      "version": "17.7.2",
      "resolved": "https://registry.npmmirror.com/yargs/-/yargs-17.7.2.tgz",
      "integrity": "sha512-7dSzzRQ++CKnNI/krKnYRV7JKKPUXMEh61soaHKg9mrWEhzFWhFnxPxGl+69cD1Ou63C13NUPCnmIcrvqCuM6w==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "cliui": "^8.0.1",
        "escalade": "^3.1.1",
        "get-caller-file": "^2.0.5",
        "require-directory": "^2.1.1",
        "string-width": "^4.2.3",
        "y18n": "^5.0.5",
        "yargs-parser": "^21.1.1"
      },
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/yargs-parser": {
      "version": "21.1.1",
      "resolved": "https://registry.npmmirror.com/yargs-parser/-/yargs-parser-21.1.1.tgz",
      "integrity": "sha512-tVpsJW7DdjecAiFpbIB1e3qxIQsE6NoPc5/eTdrbbIC4h0LVsWhnoa3g+m2HclBIujHzsxZ4VJVA+GUuc2/LBw==",
      "dev": true,
      "license": "ISC",
      "engines": {
        "node": ">=12"
      }
    },
    "node_modules/yauzl": {
      "version": "2.10.0",
      "resolved": "https://registry.npmmirror.com/yauzl/-/yauzl-2.10.0.tgz",
      "integrity": "sha512-p4a9I6X6nu6IhoGmBqAcbJy1mlC4j27vEPZX9F4L4/vZT3Lyq1VkFHw/V/PUcB9Buo+DG3iHkT0x3Qya58zc3g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "buffer-crc32": "~0.2.3",
        "fd-slicer": "~1.1.0"
      }
    },
    "node_modules/yocto-queue": {
      "version": "0.1.0",
      "resolved": "https://registry.npmmirror.com/yocto-queue/-/yocto-queue-0.1.0.tgz",
      "integrity": "sha512-rVksvsnNCdJ/ohGc6xgPwyN8eheCxsiLM8mxuE/t/mOVqJewPuO1miLpTHQiRgTKCLexL4MeAFVagts7HmNZ2Q==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    }
  }
}
~~~

## `package.json`

- 编码: `utf-8`

~~~json
{
  "name": "yiyu-thinktank-workbench",
  "version": "0.1.0",
  "private": true,
  "description": "益语智库自用平台桌面版",
  "type": "module",
  "main": "build/main/main.js",
  "scripts": {
    "dev:renderer": "vite --host 127.0.0.1 --port 4173 --strictPort",
    "dev:main": "tsc -p tsconfig.node.json --watch",
    "dev:electron": "wait-on tcp:4173 build/main/main.js && cross-env VITE_DEV_SERVER_URL=http://127.0.0.1:4173 node scripts/run-local-electron.mjs .",
    "dev": "concurrently -k \"npm:dev:renderer\" \"npm:dev:main\" \"npm:dev:electron\"",
    "build:renderer": "vite build",
    "build:main": "tsc -p tsconfig.node.json",
    "build:backend-check": "cd backend && python3 -m compileall app",
    "build:mac-icon": "python3 scripts/generate-mac-icon.py",
    "build": "npm run build:main && npm run build:renderer && npm run build:backend-check",
    "test:calendar": "npm run build:main && node --test build/shared/calendar.test.js",
    "backend:test": "cd backend && uv run pytest",
    "cloud:test": "cd cloud_backend && uv run pytest",
    "start": "node scripts/open-installed-app.mjs",
    "start:raw": "node scripts/run-local-electron.mjs .",
    "install:mac-local": "npm run dist:mac-local && node scripts/install-mac-app.mjs",
    "dist:mac": "node scripts/ensure-mac-release-prereqs.mjs && npm run build && electron-builder --mac dmg zip",
    "dist:mac-local": "npm run build && electron-builder --dir -c.electronDist=node_modules/electron/dist -c.mac.identity=null -c.mac.hardenedRuntime=false -c.mac.gatekeeperAssess=false -c.mac.forceCodeSigning=false && node scripts/stabilize-mac-app.mjs \"dist/mac-arm64/益语智库自用平台.app\""
  },
  "build": {
    "appId": "com.yiyu.selfworkbench",
    "productName": "益语智库自用平台",
    "asar": false,
    "directories": {
      "buildResources": "build-resources"
    },
    "files": [
      "build/**/*",
      "dist/renderer/**/*",
      "backend/**/*",
      "!backend/.venv{,/**}",
      "!backend/tests{,/**}",
      "!backend/.pytest_cache{,/**}",
      "!backend/**/__pycache__{,/**}",
      "!backend/**/*.pyc",
      "cloud_backend/**/*",
      "!cloud_backend/.venv{,/**}",
      "!cloud_backend/tests{,/**}",
      "!cloud_backend/.pytest_cache{,/**}",
      "!cloud_backend/**/__pycache__{,/**}",
      "!cloud_backend/**/*.pyc",
      "package.json"
    ],
    "mac": {
      "category": "public.app-category.productivity",
      "forceCodeSigning": true,
      "target": [
        "dmg",
        "zip"
      ]
    }
  },
  "dependencies": {
    "@rollup/rollup-linux-arm64-gnu": "^4.60.1",
    "lucide-react": "^0.511.0",
    "qrcode": "^1.5.4",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@tailwindcss/typography": "^0.5.16",
    "@types/node": "^22.13.9",
    "@types/react": "^18.3.18",
    "@types/react-dom": "^18.3.5",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.21",
    "concurrently": "^9.1.2",
    "cross-env": "^7.0.3",
    "electron": "^37.6.1",
    "electron-builder": "^26.0.12",
    "postcss": "^8.5.6",
    "tailwindcss": "^3.4.17",
    "typescript": "^5.8.2",
    "vite": "^6.2.1",
    "wait-on": "^8.0.3"
  }
}
~~~

## `postcss.config.cjs`

- 编码: `utf-8`

~~~javascript
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
~~~

## `scripts/check-installed-runtime.mjs`

- 编码: `utf-8`

~~~javascript
#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const APP_NAME = '益语智库自用平台.app';
const APP_DISPLAY_NAME = '益语智库自用平台';
const projectRoot = path.resolve(new URL('..', import.meta.url).pathname);
const defaultSourceApp = path.join(projectRoot, 'dist', 'mac-arm64', APP_NAME);
const targetApp = path.join(os.homedir(), 'Applications', APP_NAME);
const targetBinary = path.join(targetApp, 'Contents', 'MacOS', APP_DISPLAY_NAME);
const runtimeBackendPython = path.join(
  os.homedir(),
  'Library',
  'Application Support',
  'YiyuThinkTankWorkbench',
  'runtime',
  'backend-venv',
  'bin',
  'python',
);
const defaultBaseUrl = process.env.YIYU_BACKEND_URL || 'http://127.0.0.1:47829';
const defaultOutput = path.join(
  os.homedir(),
  'Library',
  'Application Support',
  'YiyuThinkTankWorkbench',
  'runtime',
  'main-chain-rc',
  'v0.3.4',
  'install-smoke.json',
);
const defaultLaunchTimeoutSeconds = 90;

function parseArgs(argv) {
  const options = {
    sourceApp: defaultSourceApp,
    baseUrl: defaultBaseUrl,
    output: defaultOutput,
    launchTimeoutSeconds: defaultLaunchTimeoutSeconds,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    const next = argv[index + 1];
    if (current === '--source-app') {
      if (!next) {
        throw new Error('missing value for --source-app');
      }
      options.sourceApp = path.resolve(next);
      index += 1;
      continue;
    }
    if (current.startsWith('--source-app=')) {
      options.sourceApp = path.resolve(current.slice('--source-app='.length));
      continue;
    }
    if (current === '--base-url') {
      if (!next) {
        throw new Error('missing value for --base-url');
      }
      options.baseUrl = next;
      index += 1;
      continue;
    }
    if (current.startsWith('--base-url=')) {
      options.baseUrl = current.slice('--base-url='.length);
      continue;
    }
    if (current === '--output') {
      if (!next) {
        throw new Error('missing value for --output');
      }
      options.output = path.resolve(next);
      index += 1;
      continue;
    }
    if (current.startsWith('--output=')) {
      options.output = path.resolve(current.slice('--output='.length));
      continue;
    }
    if (current === '--launch-timeout-seconds') {
      if (!next) {
        throw new Error('missing value for --launch-timeout-seconds');
      }
      options.launchTimeoutSeconds = Number(next);
      index += 1;
      continue;
    }
    if (current.startsWith('--launch-timeout-seconds=')) {
      options.launchTimeoutSeconds = Number(current.slice('--launch-timeout-seconds='.length));
      continue;
    }
    throw new Error(`unknown option: ${current}`);
  }
  if (!Number.isFinite(options.launchTimeoutSeconds) || options.launchTimeoutSeconds <= 0) {
    throw new Error(`invalid --launch-timeout-seconds value: ${options.launchTimeoutSeconds}`);
  }
  return options;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function run(command, args, options = {}) {
  return spawnSync(command, args, {
    encoding: 'utf8',
    stdio: options.stdio ?? 'pipe',
    env: options.env ?? process.env,
    ...options,
  });
}

function runText(command, args, options = {}) {
  const result = run(command, args, options);
  return {
    status: result.status ?? 0,
    stdout: result.stdout || '',
    stderr: result.stderr || '',
    error: result.error || null,
  };
}

function writeJson(outputPath, payload) {
  const target = path.resolve(outputPath);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

function pickRendererEntry(assetDir) {
  if (!fs.existsSync(assetDir)) {
    return null;
  }
  const entries = fs.readdirSync(assetDir)
    .filter((name) => /^(main|index)-.*\.js$/.test(name))
    .sort();
  return entries.find((name) => name.startsWith('main-')) || entries[0] || null;
}

function inspectAppBundle(appPath) {
  const resolved = path.resolve(appPath);
  const exists = fs.existsSync(resolved);
  const assetDir = path.join(resolved, 'Contents', 'Resources', 'app', 'dist', 'renderer', 'assets');
  return {
    exists,
    rendererEntry: pickRendererEntry(assetDir),
  };
}

function findAppPids() {
  const result = runText('pgrep', ['-f', targetBinary]);
  return result.stdout.trim().split('\n').filter(Boolean).map((value) => Number(value)).filter(Number.isInteger);
}

function getListenerInfo(port) {
  const output = runText('lsof', ['-nP', `-iTCP:${port}`, '-sTCP:LISTEN', '-Fp']);
  const pid = output.stdout.split('\n')
    .find((line) => line.startsWith('p') && line.slice(1).trim())
    ?.slice(1);
  if (!pid) {
    return { pid: null, command: null };
  }
  const command = runText('ps', ['-p', pid, '-o', 'command=']).stdout.trim() || null;
  return {
    pid: Number(pid),
    command,
  };
}

function listenerMatchesInstalledRuntime(command) {
  return Boolean(command && command.includes(runtimeBackendPython));
}

function stopInstalledApp() {
  run('osascript', ['-e', `tell application "${APP_DISPLAY_NAME}" to quit`], { stdio: 'ignore' });
  run('pkill', ['-x', APP_DISPLAY_NAME], { stdio: 'ignore' });
  run('pkill', ['-f', targetBinary], { stdio: 'ignore' });
  const waitResult = run('bash', ['-lc', `for _ in {1..40}; do pgrep -f '${targetBinary.replace(/'/g, `'\\''`)}' >/dev/null || exit 0; sleep 0.25; done; exit 1`], { stdio: 'ignore' });
  return waitResult.status === 0;
}

function stopExpectedBackendListener(port) {
  const listener = getListenerInfo(port);
  if (!listener.pid) {
    return { cleared: true, reason: null };
  }
  if (!listenerMatchesInstalledRuntime(listener.command)) {
    return {
      cleared: false,
      reason: `47829 已被非安装版 runtime 进程占用：${listener.command || listener.pid}`,
    };
  }
  run('kill', ['-TERM', String(listener.pid)], { stdio: 'ignore' });
  const waitResult = run('bash', ['-lc', `for _ in {1..40}; do lsof -nP -iTCP:${port} -sTCP:LISTEN >/dev/null || exit 0; sleep 0.25; done; exit 1`], { stdio: 'ignore' });
  if (waitResult.status !== 0) {
    return {
      cleared: false,
      reason: `无法清理旧的 47829 listener pid=${listener.pid}`,
    };
  }
  return { cleared: true, reason: null };
}

async function request200(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch(url, { method: 'GET', signal: controller.signal });
    return response.status === 200;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

function payloadFromState(state) {
  return {
    recordedAt: new Date().toISOString(),
    targetAppExists: state.targetAppExists,
    sourceRendererEntry: state.sourceRendererEntry,
    targetRendererEntry: state.targetRendererEntry,
    rendererEntryMatch: state.rendererEntryMatch,
    launchAttempted: state.launchAttempted,
    appProcessRunning: state.appProcessRunning,
    backendStartedByInstalledApp: state.backendStartedByInstalledApp,
    backendPid: state.backendPid,
    backendCommand: state.backendCommand,
    settingsMainChainStability200: state.settingsMainChainStability200,
    analysisMigrationMetrics200: state.analysisMigrationMetrics200,
    readyToResumeA0: state.readyToResumeA0,
    blockerClass: state.blockerClass,
    reason: state.reason,
  };
}

async function main() {
  let options = {
    sourceApp: defaultSourceApp,
    baseUrl: defaultBaseUrl,
    output: defaultOutput,
    launchTimeoutSeconds: defaultLaunchTimeoutSeconds,
  };
  const state = {
    targetAppExists: false,
    sourceRendererEntry: null,
    targetRendererEntry: null,
    rendererEntryMatch: false,
    launchAttempted: false,
    appProcessRunning: false,
    backendStartedByInstalledApp: false,
    backendPid: null,
    backendCommand: null,
    settingsMainChainStability200: false,
    analysisMigrationMetrics200: false,
    readyToResumeA0: false,
    blockerClass: 'packaging',
    reason: '',
  };

  try {
    options = parseArgs(process.argv.slice(2));
    const baseUrl = options.baseUrl.replace(/\/+$/, '');
    const port = Number(new URL(baseUrl).port || '80');
    const sourceInfo = inspectAppBundle(options.sourceApp);
    const targetInfo = inspectAppBundle(targetApp);
    state.targetAppExists = targetInfo.exists;
    state.sourceRendererEntry = sourceInfo.rendererEntry;
    state.targetRendererEntry = targetInfo.rendererEntry;
    state.rendererEntryMatch = Boolean(
      sourceInfo.rendererEntry
        && targetInfo.rendererEntry
        && sourceInfo.rendererEntry === targetInfo.rendererEntry
    );

    if (!state.targetAppExists) {
      state.reason = `正式安装 target app 缺失：${targetApp}`;
      return state;
    }
    if (!state.rendererEntryMatch) {
      state.reason = `renderer 入口不一致：source=${state.sourceRendererEntry || 'null'} target=${state.targetRendererEntry || 'null'}`;
      return state;
    }

    stopInstalledApp();
    const cleanup = stopExpectedBackendListener(port);
    if (!cleanup.cleared) {
      state.reason = cleanup.reason;
      return state;
    }

    state.launchAttempted = true;
    const openScript = path.join(projectRoot, 'scripts', 'open-installed-app.mjs');
    const launch = run(process.execPath, [openScript, '--tab', 'settings', '--settings-section', 'overview'], { stdio: 'inherit' });
    if (launch.error) {
      state.reason = `open-installed-app.mjs 执行失败：${launch.error.message}`;
      return state;
    }
    if (launch.status !== 0) {
      state.reason = `open-installed-app.mjs 退出码 ${launch.status}`;
      return state;
    }

    const deadline = Date.now() + options.launchTimeoutSeconds * 1000;
    while (Date.now() < deadline) {
      const pids = findAppPids();
      const listener = getListenerInfo(port);
      const appProcessRunning = pids.length > 0;
      const backendStartedByInstalledApp = appProcessRunning && listenerMatchesInstalledRuntime(listener.command);
      let settingsMainChainStability200 = false;
      let analysisMigrationMetrics200 = false;
      if (backendStartedByInstalledApp) {
        settingsMainChainStability200 = await request200(`${baseUrl}/api/v1/settings/main-chain-stability`);
        analysisMigrationMetrics200 = await request200(`${baseUrl}/api/v1/runtime/analysis-migration-metrics`);
      }

      state.appProcessRunning = appProcessRunning;
      state.backendStartedByInstalledApp = backendStartedByInstalledApp;
      state.backendPid = listener.pid;
      state.backendCommand = listener.command;
      state.settingsMainChainStability200 = settingsMainChainStability200;
      state.analysisMigrationMetrics200 = analysisMigrationMetrics200;

      if (appProcessRunning && backendStartedByInstalledApp && settingsMainChainStability200 && analysisMigrationMetrics200) {
        state.readyToResumeA0 = true;
        state.blockerClass = 'none';
        state.reason = 'installed-runtime packaging 已恢复，可回到 A0。';
        return state;
      }

      await sleep(2_000);
    }

    if (!state.appProcessRunning) {
      state.reason = '安装版启动后未保持运行。';
      return state;
    }
    if (!state.backendStartedByInstalledApp) {
      state.reason = '47829 未由安装版 runtime backend 拉起。';
      return state;
    }
    if (!state.settingsMainChainStability200) {
      state.reason = '/api/v1/settings/main-chain-stability 未返回 200。';
      return state;
    }
    if (!state.analysisMigrationMetrics200) {
      state.reason = '/api/v1/runtime/analysis-migration-metrics 未返回 200。';
      return state;
    }
    state.reason = '安装后最小冒烟未达到恢复 A0 的条件。';
    return state;
  } catch (error) {
    state.reason = error instanceof Error ? error.message : String(error);
    return state;
  } finally {
    const payload = payloadFromState(state);
    writeJson(options.output, payload);
    console.log(JSON.stringify(payload, null, 2));
  }
}

const state = await main();
if (!state.readyToResumeA0) {
  process.exit(1);
}
~~~

## `scripts/cleanup_audit_data.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


AUDIT_PREFIX = "【审计】%"
AUDIT_CONTAINS = "%【审计】%"
AUDIT_FIXTURE_PATH = "/tmp/yiyu-audit-fixtures%"
AUDIT_FIXTURE_CONTAINS = "%/tmp/yiyu-audit-fixtures%"


def resolve_db_path() -> Path:
    data_dir = os.environ.get("YIYU_WORKBENCH_DATA_DIR")
    if data_dir:
        return Path(data_dir).expanduser() / "app.db"
    return Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench" / "app.db"


def delete_like(cursor: sqlite3.Cursor, table: str, column: str, pattern: str) -> int:
    cursor.execute(f"DELETE FROM {table} WHERE {column} LIKE ?", (pattern,))
    return cursor.rowcount


def main() -> None:
    db_path = resolve_db_path()
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        deleted: dict[str, int] = {}
        audit_client_ids = [row[0] for row in cursor.execute("SELECT id FROM clients WHERE name LIKE ?", (AUDIT_PREFIX,)).fetchall()]
        audit_meeting_ids: list[str] = []
        if audit_client_ids:
            placeholders = ",".join("?" for _ in audit_client_ids)
            audit_meeting_ids = [
                row[0]
                for row in cursor.execute(
                    f"SELECT id FROM meetings WHERE client_id IN ({placeholders})",
                    tuple(audit_client_ids),
                ).fetchall()
            ]

        deleted["task_notes.audit"] = delete_like(cursor, "task_notes", "note", AUDIT_CONTAINS)
        deleted["weekly_reviews.audit"] = delete_like(cursor, "weekly_reviews", "summary", AUDIT_CONTAINS)
        deleted["chat_messages.audit"] = delete_like(cursor, "chat_messages", "content", AUDIT_CONTAINS)
        deleted["activity_logs.audit"] = delete_like(cursor, "activity_logs", "detail_json", AUDIT_CONTAINS)
        deleted["activity_logs.fixture"] = delete_like(cursor, "activity_logs", "detail_json", AUDIT_FIXTURE_CONTAINS)
        deleted["documents.fixture"] = delete_like(cursor, "documents", "path", AUDIT_FIXTURE_PATH)
        deleted["imports.fixture"] = delete_like(cursor, "imports", "source_path", AUDIT_FIXTURE_PATH)
        deleted["client_folders.fixture"] = delete_like(cursor, "client_folders", "path", AUDIT_FIXTURE_PATH)
        deleted["analysis_runs.audit"] = delete_like(cursor, "analysis_runs", "input_text", AUDIT_CONTAINS)
        deleted["topic_candidates.audit"] = delete_like(cursor, "topic_candidates", "title", AUDIT_PREFIX)
        deleted["handbook_entries.audit"] = delete_like(cursor, "handbook_entries", "title", AUDIT_PREFIX)
        if audit_meeting_ids:
            placeholders = ",".join("?" for _ in audit_meeting_ids)
            cursor.execute(
                f"DELETE FROM tasks WHERE source_type = 'meeting' AND source_id IN ({placeholders})",
                tuple(audit_meeting_ids),
            )
            deleted["tasks.audit_meeting_source"] = cursor.rowcount
        else:
            deleted["tasks.audit_meeting_source"] = 0
        deleted["tasks.audit"] = delete_like(cursor, "tasks", "title", AUDIT_PREFIX)
        deleted["topic_radars.audit"] = delete_like(cursor, "topic_radars", "title", AUDIT_PREFIX)
        deleted["clients.audit"] = delete_like(cursor, "clients", "name", AUDIT_PREFIX)
        conn.commit()
    finally:
        conn.close()

    print(f"Audit cleanup completed for {db_path}")
    for key, count in deleted.items():
        print(f"{key}: {count}")


if __name__ == "__main__":
    main()
~~~

## `scripts/deploy-cloud-backend-volcengine.sh`

- 编码: `utf-8`

~~~bash
#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-root@101.126.34.232}"
REMOTE_DIR="${2:-/opt/yiyu/cloud-backend}"
SERVICE_NAME="${3:-yiyu-cloud-backend.service}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH_OPTS=(-o StrictHostKeyChecking=no)

if [[ -n "${YIYU_VOLCENGINE_SSH_KEY:-}" ]]; then
  SSH_OPTS+=(-i "${YIYU_VOLCENGINE_SSH_KEY}")
fi

echo "==> Syncing cloud backend code to ${TARGET}:${REMOTE_DIR}"
ssh "${SSH_OPTS[@]}" "${TARGET}" "install -d -m 0755 ${REMOTE_DIR} ${REMOTE_DIR}/app"
rsync -az --delete \
  -e "ssh ${SSH_OPTS[*]}" \
  "${REPO_ROOT}/cloud_backend/app/" \
  "${TARGET}:${REMOTE_DIR}/app/"
rsync -az \
  -e "ssh ${SSH_OPTS[*]}" \
  "${REPO_ROOT}/cloud_backend/pyproject.toml" \
  "${REPO_ROOT}/cloud_backend/uv.lock" \
  "${REPO_ROOT}/cloud_backend/requirements.deploy.txt" \
  "${TARGET}:${REMOTE_DIR}/"

echo "==> Refreshing venv and restarting ${SERVICE_NAME}"
ssh "${SSH_OPTS[@]}" "${TARGET}" bash -s -- "${REMOTE_DIR}" "${SERVICE_NAME}" <<'REMOTE'
set -euo pipefail

REMOTE_DIR="$1"
SERVICE_NAME="$2"

if ! id -u yiyu >/dev/null 2>&1; then
  echo "Missing system user yiyu" >&2
  exit 1
fi
if [[ ! -f "${REMOTE_DIR}/.env" ]]; then
  echo "Missing ${REMOTE_DIR}/.env" >&2
  exit 1
fi
for key in YIYU_CLOUD_PUBLIC_BASE_URL DOUBAO_FILE_ASR_APP_ID DOUBAO_FILE_ASR_ACCESS_TOKEN DOUBAO_STREAM_ASR_APP_ID DOUBAO_STREAM_ASR_ACCESS_TOKEN; do
  if ! grep -q "^${key}=" "${REMOTE_DIR}/.env"; then
    echo "WARN missing ${key} in ${REMOTE_DIR}/.env" >&2
  fi
done
if [[ ! -x "${REMOTE_DIR}/.venv/bin/python" ]]; then
  python3 -m venv "${REMOTE_DIR}/.venv"
fi
"${REMOTE_DIR}/.venv/bin/python" -m pip install --upgrade pip >/dev/null
"${REMOTE_DIR}/.venv/bin/python" -m pip install -r "${REMOTE_DIR}/requirements.deploy.txt" >/dev/null
chown -R yiyu:yiyu "${REMOTE_DIR}"
systemctl restart "${SERVICE_NAME}"
systemctl --no-pager --full status "${SERVICE_NAME}" | sed -n '1,20p'
REMOTE

echo "==> Smoke check"
"${REPO_ROOT}/scripts/smoke-cloud-backend-volcengine.sh"
~~~

## `scripts/ensure-mac-release-prereqs.mjs`

- 编码: `utf-8`

~~~javascript
import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import process from 'node:process';

const projectRoot = path.resolve(import.meta.dirname, '..');
const iconPath = path.join(projectRoot, 'build-resources', 'icon.icns');

function parseDeveloperIdIdentities(output) {
  return output
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.includes('Developer ID Application:'));
}

function readCodeSigningIdentities() {
  const result = spawnSync('security', ['find-identity', '-v', '-p', 'codesigning'], {
    encoding: 'utf-8',
  });

  if (result.error) {
    return {
      identities: [],
      error: result.error.message,
    };
  }

  return {
    identities: parseDeveloperIdIdentities(result.stdout),
    error: result.status === 0 ? null : (result.stderr || result.stdout || `security exited with code ${result.status ?? 'unknown'}`),
  };
}

function hasNotarizationCredentials(env) {
  const hasAppleIdFlow = Boolean(env.APPLE_ID && env.APPLE_APP_SPECIFIC_PASSWORD && env.APPLE_TEAM_ID);
  const hasApiKeyFlow = Boolean(env.APPLE_API_KEY && env.APPLE_API_KEY_ID && env.APPLE_API_ISSUER);
  return hasAppleIdFlow || hasApiKeyFlow;
}

const failures = [];
const warnings = [];

if (!existsSync(iconPath)) {
  failures.push(`缺少发布图标：${iconPath}`);
}

const signing = readCodeSigningIdentities();
if (signing.error && signing.identities.length === 0) {
  failures.push(`无法读取代码签名身份：${signing.error}`);
} else if (signing.identities.length === 0) {
  failures.push('当前钥匙串中没有可用的 Developer ID Application 证书。');
}

if (!hasNotarizationCredentials(process.env)) {
  failures.push('当前环境没有 notarization 凭据。请配置 APPLE_ID/APPLE_APP_SPECIFIC_PASSWORD/APPLE_TEAM_ID，或 APPLE_API_KEY/APPLE_API_KEY_ID/APPLE_API_ISSUER。');
}

if (process.env.CSC_IDENTITY_AUTO_DISCOVERY === 'false') {
  warnings.push('检测到 CSC_IDENTITY_AUTO_DISCOVERY=false，这会阻止正式签名发现身份。');
}

if (failures.length > 0) {
  console.error('Mac 官网发布包前置检查失败：');
  for (const item of failures) {
    console.error(`- ${item}`);
  }
  if (warnings.length > 0) {
    console.error('');
    console.error('附加提醒：');
    for (const item of warnings) {
      console.error(`- ${item}`);
    }
  }
  console.error('');
  console.error('当前环境不满足官网分发版打包要求。');
  console.error('如果你只是需要本机自测包，请改用：npm run dist:mac-local');
  process.exit(1);
}

console.log('Mac 官网发布包前置检查通过。');
console.log(`- Developer ID Application 身份数量：${signing.identities.length}`);
console.log(`- 发布图标：${iconPath}`);
console.log('- notarization 凭据：已检测到');
~~~

## `scripts/generate-mac-icon.py`

- 编码: `utf-8`

~~~python
#!/usr/bin/env python3

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_RESOURCES = PROJECT_ROOT / "build-resources"
ICONSET_DIR = BUILD_RESOURCES / "icon.iconset"
ICON_PATH = BUILD_RESOURCES / "icon.icns"
BASE_SIZE = 1024


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode MS.ttf",
    ]
    for candidate in candidates:
        font_path = Path(candidate)
        if font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def build_base_icon() -> Image.Image:
    image = Image.new("RGBA", (BASE_SIZE, BASE_SIZE), "#F4F7FF")
    draw = ImageDraw.Draw(image)

    shadow = Image.new("RGBA", (BASE_SIZE, BASE_SIZE), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((132, 132, 892, 892), radius=210, fill=(31, 64, 173, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(36))
    image.alpha_composite(shadow)

    draw.rounded_rectangle((112, 112, 912, 912), radius=210, fill="#5B7BFE")
    draw.rounded_rectangle((170, 170, 854, 854), radius=170, outline=(255, 255, 255, 48), width=6)
    draw.ellipse((744, 178, 848, 282), fill="#F9FBFF")
    draw.rounded_rectangle((214, 724, 358, 772), radius=24, fill=(255, 255, 255, 64))

    font = load_font(420)
    text = "益"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_x = (BASE_SIZE - text_width) / 2 - bbox[0]
    text_y = (BASE_SIZE - text_height) / 2 - bbox[1] - 10
    draw.text((text_x, text_y), text, font=font, fill="#FFFFFF")
    return image


def write_iconset(image: Image.Image) -> None:
    if ICONSET_DIR.exists():
        shutil.rmtree(ICONSET_DIR)
    ICONSET_DIR.mkdir(parents=True, exist_ok=True)

    variants = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]

    for file_name, size in variants:
        resized = image.resize((size, size), Image.LANCZOS)
        resized.save(ICONSET_DIR / file_name)


def build_icns() -> None:
    subprocess.run(
        ["/usr/bin/iconutil", "-c", "icns", str(ICONSET_DIR), "-o", str(ICON_PATH)],
        check=True,
    )


def main() -> None:
    BUILD_RESOURCES.mkdir(parents=True, exist_ok=True)
    base_icon = build_base_icon()
    write_iconset(base_icon)
    build_icns()
    print(f"generated {ICON_PATH}")


if __name__ == "__main__":
    main()
~~~

## `scripts/install-mac-app.mjs`

- 编码: `utf-8`

~~~javascript
#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const APP_NAME = '益语智库自用平台.app';
const APP_BASENAME = APP_NAME.replace(/\.app$/, '');
const projectRoot = path.resolve(new URL('..', import.meta.url).pathname);
const userApplicationsDir = path.join(os.homedir(), 'Applications');
const targetApp = path.join(userApplicationsDir, APP_NAME);
const timestamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..+/, '').replace('T', '-');
const stagingApp = path.join(userApplicationsDir, `.${APP_BASENAME}.installing-${timestamp}.app`);
const backupRoot = path.join(os.homedir(), 'Library', 'Application Support', 'yiyu-thinktank-workbench', 'runtime', 'install-backups');
const backupApp = path.join(backupRoot, `益语智库自用平台.old-${timestamp}.app`);
const defaultReceiptPath = path.join(
  os.homedir(),
  'Library',
  'Application Support',
  'YiyuThinkTankWorkbench',
  'runtime',
  'main-chain-rc',
  'v0.3.4',
  'install-receipt.json',
);
const legacyCandidates = [
  '/Applications/益语智库.app',
  path.join(os.homedir(), 'Library', 'Application Support', 'yiyu-thinktank-workbench', 'runtime', 'local-electron', '益语智库工作台.app'),
  path.join(os.homedir(), 'Library', 'Application Support', 'yiyu-thinktank-workbench', 'runtime', 'local-electron-dist', '益语智库工作台.app'),
];

function parseArgs(argv) {
  let source = null;
  let receipt = defaultReceiptPath;
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    if (current === '--receipt') {
      const value = argv[index + 1];
      if (!value) {
        throw new Error('missing value for --receipt');
      }
      receipt = path.resolve(value);
      index += 1;
      continue;
    }
    if (current.startsWith('--receipt=')) {
      receipt = path.resolve(current.slice('--receipt='.length));
      continue;
    }
    if (current.startsWith('--')) {
      throw new Error(`unknown option: ${current}`);
    }
    if (source) {
      throw new Error(`unexpected extra argument: ${current}`);
    }
    source = path.resolve(current);
  }
  return {
    sourceApp: source || path.join(projectRoot, 'dist', 'mac-arm64', APP_NAME),
    receiptPath: receipt,
  };
}

function info(message) {
  console.log(`[install-mac-app] ${message}`);
}

function runOrFail(command, args) {
  const result = spawnSync(command, args, { stdio: 'inherit' });
  if (result.error) {
    throw new Error(`${command} failed: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`${command} exited with status ${result.status}`);
  }
}

function runQuiet(command, args) {
  return spawnSync(command, args, { stdio: 'ignore' });
}

function stabilizeInstalledApp(targetPath) {
  const scriptPath = path.join(projectRoot, 'scripts', 'stabilize-mac-app.mjs');
  const result = spawnSync(process.execPath, [scriptPath, targetPath], { stdio: 'inherit' });
  if (result.error) {
    throw new Error(`stabilize script failed: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`stabilize script exited with status ${result.status}`);
  }
}

function stopRunningApp() {
  info('stopping running app instances before install');
  runQuiet('osascript', ['-e', 'tell application "益语智库自用平台" to quit']);
  runQuiet('pkill', ['-x', '益语智库自用平台']);
  runQuiet('pkill', ['-f', `${targetApp}/Contents/MacOS/${APP_BASENAME}`]);
  const waitResult = spawnSync(
    'bash',
    ['-lc', 'for _ in {1..30}; do pgrep -x "益语智库自用平台" >/dev/null || exit 0; sleep 0.2; done; exit 0'],
    { stdio: 'ignore' },
  );
  if (waitResult.status !== 0) {
    throw new Error('timed out waiting for running app instance to stop');
  }
}

function pickRendererEntry(assetDir) {
  const files = fs.readdirSync(assetDir).filter((name) => /^(main|index)-.*\.js$/.test(name)).sort();
  const preferred = files.find((name) => /^main-.*\.js$/.test(name));
  return preferred || files[0] || null;
}

function snapshotSourceBundle(sourcePath) {
  const sourceFrameworksDir = path.join(sourcePath, 'Contents', 'Frameworks');
  const sourceRendererAssetDir = path.join(sourcePath, 'Contents', 'Resources', 'app', 'dist', 'renderer', 'assets');
  return {
    frameworkEntries: fs.existsSync(sourceFrameworksDir) ? fs.readdirSync(sourceFrameworksDir).sort() : null,
    rendererEntry: fs.existsSync(sourceRendererAssetDir) ? pickRendererEntry(sourceRendererAssetDir) : null,
  };
}

function inspectAppBundle(targetPath) {
  const resolvedPath = path.resolve(targetPath);
  const exists = fs.existsSync(resolvedPath);
  const assetDir = path.join(resolvedPath, 'Contents', 'Resources', 'app', 'dist', 'renderer', 'assets');
  return {
    path: resolvedPath,
    exists,
    modifiedAt: exists ? new Date(fs.statSync(resolvedPath).mtimeMs).toISOString() : null,
    rendererEntry: fs.existsSync(assetDir) ? pickRendererEntry(assetDir) : null,
  };
}

function scanStagingBundles(sourceRendererEntry) {
  if (!fs.existsSync(userApplicationsDir)) {
    return [];
  }
  return fs.readdirSync(userApplicationsDir)
    .filter((name) => name.startsWith(`.${APP_BASENAME}.installing-`) && name.endsWith('.app'))
    .map((name) => {
      const appPath = path.join(userApplicationsDir, name);
      const metadata = inspectAppBundle(appPath);
      return {
        path: appPath,
        modifiedAt: metadata.modifiedAt,
        rendererEntry: metadata.rendererEntry,
        staleForCurrentInstall: Boolean(
          sourceRendererEntry
            ? metadata.rendererEntry !== sourceRendererEntry
            : true
        ),
      };
    })
    .sort((left, right) => left.path.localeCompare(right.path, 'zh-Hans-CN'));
}

function writeReceipt(receiptPath, payload) {
  const target = path.resolve(receiptPath);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  info(`wrote install receipt: ${target}`);
}

function verifyInstalledBundle(targetPath, sourceSnapshot) {
  const requiredPaths = [
    path.join(targetPath, 'Contents', 'Info.plist'),
    path.join(targetPath, 'Contents', 'PkgInfo'),
    path.join(targetPath, 'Contents', 'Frameworks'),
    path.join(targetPath, 'Contents', 'Frameworks', 'Electron Framework.framework'),
    path.join(targetPath, 'Contents', 'Frameworks', 'Electron Framework.framework', 'Electron Framework'),
    path.join(targetPath, 'Contents', 'Frameworks', `${APP_BASENAME} Helper.app`),
  ];

  for (const requiredPath of requiredPaths) {
    if (!fs.existsSync(requiredPath)) {
      throw new Error(`installed app bundle is incomplete, missing: ${requiredPath}`);
    }
  }

  const targetFrameworksDir = path.join(targetPath, 'Contents', 'Frameworks');
  const targetFrameworkEntries = fs.readdirSync(targetFrameworksDir).sort();
  if (sourceSnapshot.frameworkEntries && sourceSnapshot.frameworkEntries.length !== targetFrameworkEntries.length) {
    throw new Error(
      `installed app framework count mismatch: source=${sourceSnapshot.frameworkEntries.length} target=${targetFrameworkEntries.length}`,
    );
  }
}

function safeRemove(targetPath) {
  if (!fs.existsSync(targetPath)) {
    return;
  }
  fs.rmSync(targetPath, { recursive: true, force: true });
}

let sourceApp = path.join(projectRoot, 'dist', 'mac-arm64', APP_NAME);
let receiptPath = defaultReceiptPath;
let currentStep = 'validate-source';
let promoted = false;

function buildReceipt({ failureStep = null, errorMessage = null } = {}) {
  const sourceInfo = inspectAppBundle(sourceApp);
  const targetInfo = inspectAppBundle(targetApp);
  return {
    recordedAt: new Date().toISOString(),
    sourceApp,
    sourceAppMTime: sourceInfo.modifiedAt,
    sourceRendererEntry: sourceInfo.rendererEntry,
    stagingApp,
    targetApp,
    targetAppMTime: targetInfo.modifiedAt,
    targetRendererEntry: targetInfo.rendererEntry,
    rendererEntryMatch: Boolean(
      sourceInfo.rendererEntry
        && targetInfo.rendererEntry
        && sourceInfo.rendererEntry === targetInfo.rendererEntry
    ),
    promoted,
    failureStep,
    errorMessage,
    staleCandidates: scanStagingBundles(sourceInfo.rendererEntry),
  };
}

try {
  ({ sourceApp, receiptPath } = parseArgs(process.argv.slice(2)));
  if (!fs.existsSync(sourceApp)) {
    throw new Error(`source app not found: ${sourceApp}`);
  }

  const sourceSnapshot = snapshotSourceBundle(sourceApp);

  fs.mkdirSync(userApplicationsDir, { recursive: true });
  fs.mkdirSync(backupRoot, { recursive: true });

  currentStep = 'stop-running-app';
  stopRunningApp();

  currentStep = 'clear-staging';
  safeRemove(stagingApp);

  currentStep = 'copy-to-staging';
  info(`installing ${sourceApp} -> ${stagingApp}`);
  runOrFail('ditto', [sourceApp, stagingApp]);

  currentStep = 'stabilize-staging';
  stabilizeInstalledApp(stagingApp);

  currentStep = 'verify-staging-bundle';
  verifyInstalledBundle(stagingApp, sourceSnapshot);

  currentStep = 'verify-renderer-entry';
  const targetRendererAssetDir = path.join(stagingApp, 'Contents', 'Resources', 'app', 'dist', 'renderer', 'assets');
  const sourceEntry = sourceSnapshot.rendererEntry;
  const targetEntry = pickRendererEntry(targetRendererAssetDir);
  if (!sourceEntry || !targetEntry) {
    throw new Error('unable to verify installed renderer assets');
  }
  if (sourceEntry !== targetEntry) {
    throw new Error(`installed app renderer asset mismatch: source=${sourceEntry} target=${targetEntry}`);
  }
  info(`verified installed renderer asset: ${targetEntry}`);

  if (fs.existsSync(targetApp)) {
    currentStep = 'backup-existing-target';
    info(`existing app detected, backing up to: ${backupApp}`);
    fs.renameSync(targetApp, backupApp);
  }

  currentStep = 'promote-target-app';
  info(`promoting verified app into place: ${stagingApp} -> ${targetApp}`);
  fs.renameSync(stagingApp, targetApp);
  promoted = true;

  writeReceipt(receiptPath, buildReceipt());

  const legacyHits = legacyCandidates.filter((targetPath) => fs.existsSync(targetPath));
  if (legacyHits.length > 0) {
    info('legacy/duplicate app entries still exist. clean these manually if they are no longer needed:');
    for (const targetPath of legacyHits) {
      console.log(` - ${targetPath}`);
    }
  }

  info(`recommended launch entry: ${targetApp}`);
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  writeReceipt(receiptPath, buildReceipt({ failureStep: currentStep, errorMessage: message }));
  console.error(`[install-mac-app] ${message}`);
  process.exit(1);
}
~~~

## `scripts/open-installed-app.mjs`

- 编码: `utf-8`

~~~javascript
#!/usr/bin/env node

import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';

const APP_NAME = '益语智库自用平台.app';
const projectRoot = path.resolve(new URL('..', import.meta.url).pathname);
const installedApp = path.join(os.homedir(), 'Applications', APP_NAME);
const binaryPath = path.join(installedApp, 'Contents', 'MacOS', '益语智库自用平台');
const rawElectronPattern = `${projectRoot}/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron \\.`;
const DEFAULT_PACKAGED_REMOTE_CLOUD_API_URL = 'http://101.126.34.232';
const RENDERER_QUERY_ARG = '--yiyu-renderer-query';

function sanitizedLaunchEnv() {
  const env = { ...process.env };
  delete env.YIYU_REMOTE_CLOUD_API_URL;
  env.YIYU_PACKAGED_REMOTE_CLOUD_API_URL = DEFAULT_PACKAGED_REMOTE_CLOUD_API_URL;
  return env;
}

function run(command, args, options = {}) {
  return spawnSync(command, args, {
    stdio: options.stdio ?? 'pipe',
    encoding: 'utf8',
    env: options.env ?? sanitizedLaunchEnv(),
    ...options,
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function countAppProcesses() {
  const result = run('pgrep', ['-f', '益语智库自用平台']);
  return (result.stdout || '').trim().split('\n').filter(Boolean).length;
}

function parseLaunchArgs(argv) {
  const queryParams = new URLSearchParams();
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    if (current === '--tab') {
      const value = argv[index + 1];
      if (value) {
        queryParams.set('tab', value);
        index += 1;
      }
      continue;
    }
    if (current === '--settings-section') {
      const value = argv[index + 1];
      if (value) {
        queryParams.set('settingsSection', value);
        index += 1;
      }
      continue;
    }
    if (current === '--query') {
      const value = argv[index + 1];
      if (value) {
        for (const [key, paramValue] of new URLSearchParams(value.replace(/^\?+/, ''))) {
          queryParams.set(key, paramValue);
        }
        index += 1;
      }
    }
  }
  const serialized = queryParams.toString();
  return serialized ? [`${RENDERER_QUERY_ARG}=${serialized}`] : [];
}

const launchArgs = parseLaunchArgs(process.argv.slice(2));

const exists = run('test', ['-d', installedApp]);
if (exists.status !== 0) {
  console.error(`[open-installed-app] installed app not found: ${installedApp}`);
  console.error('[open-installed-app] run `npm run dist:mac-local && npm run install:mac-local` first.');
  process.exit(1);
}

// 杀掉旧的 dev electron 进程
run('pkill', ['-f', rawElectronPattern], { stdio: 'ignore' });

// 方式 1: open -a
console.log('[open-installed-app] trying open -a ...');
const openArgs = ['-na', installedApp, ...(launchArgs.length > 0 ? ['--args', ...launchArgs] : [])];
run('open', openArgs, { stdio: 'inherit' });
await sleep(4000);

if (countAppProcesses() >= 2) {
  console.log('[open-installed-app] launched via open -a');
  run('osascript', ['-e', 'tell application "益语智库自用平台" to activate'], { stdio: 'ignore' });
  process.exit(0);
}

// 方式 2: 直接执行二进制（Sequoia 需要 tty）
console.log('[open-installed-app] open -a failed, falling back to direct binary with tty ...');
if (!fs.existsSync(binaryPath)) {
  console.error(`[open-installed-app] binary not found: ${binaryPath}`);
  process.exit(1);
}

// 用 script -q /dev/null 模拟 tty — Electron 在 macOS Sequoia 上需要 tty 才能正常启动
const child = spawn('script', ['-q', '/dev/null', binaryPath, ...launchArgs], {
  detached: true,
  stdio: 'ignore',
  env: sanitizedLaunchEnv(),
});
child.unref();
console.log(`[open-installed-app] launched via script+binary (pid: ${child.pid})`);
~~~

## `scripts/publish-desktop-client-knowledge-to-cloud.py`

- 编码: `utf-8`

~~~python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable


DEFAULT_DB_PATH = Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench" / "app.db"
DEFAULT_CLOUD_BASE_URL = os.environ.get("YIYU_CLOUD_API_URL", "http://101.126.34.232").rstrip("/")
SUPPORTED_SOURCE_TYPES = (
    "workspace_snapshot",
    "client_dna",
    "event_line_snapshot",
    "meeting_summary",
    "knowledge_surrogate",
    "strategic_cockpit",
)


def table_exists(db: sqlite3.Connection, table_name: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def table_columns(db: sqlite3.Connection, table_name: str) -> set[str]:
    if not table_exists(db, table_name):
        return set()
    rows = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def load_cloud_access_token(db: sqlite3.Connection) -> str:
    row = db.execute("SELECT value FROM settings WHERE key = 'cloud_access_token'").fetchone()
    token = str(row[0]).strip() if row and row[0] else ""
    if not token:
        raise SystemExit("未找到 cloud_access_token，请先在桌面版里登录云端账号。")
    return token


def fetch_json(url: str, token: str, *, method: str = "GET", payload: dict | None = None) -> object:
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"{method} {url} 失败：HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"{method} {url} 失败：{exc}") from exc
    return json.loads(body)


def stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def normalize_text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def load_clients(db: sqlite3.Connection, selected_client_ids: Iterable[str] | None) -> list[sqlite3.Row]:
    selected = [item.strip() for item in (selected_client_ids or []) if item.strip()]
    db.row_factory = sqlite3.Row
    if selected:
        placeholders = ",".join("?" for _ in selected)
        rows = db.execute(
            f"SELECT id, name, alias, updated_at FROM clients WHERE id IN ({placeholders}) ORDER BY updated_at DESC",
            tuple(selected),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, name, alias, updated_at FROM clients ORDER BY updated_at DESC",
        ).fetchall()
    return list(rows)


def build_workspace_snapshot(db: sqlite3.Connection, client_row: sqlite3.Row) -> dict[str, object]:
    client_id = str(client_row["id"])
    event_line_rows = db.execute(
        """
        SELECT id, name, stage, summary, current_blocker, next_step, recent_decision, updated_at
        FROM event_lines
        WHERE primary_client_id = ?
        ORDER BY updated_at DESC
        LIMIT 6
        """,
        (client_id,),
    ).fetchall() if table_exists(db, "event_lines") else []
    task_rows = db.execute(
        """
        SELECT id, title, progress_status, current_blocker, next_action, event_line_id, updated_at
        FROM tasks
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 8
        """,
        (client_id,),
    ).fetchall() if table_exists(db, "tasks") else []
    event_line_name_by_id = {str(row["id"]): normalize_text(row["name"]) for row in event_line_rows}
    surrogate_rows = db.execute(
        """
        SELECT id, title, overview_summary, source_type, updated_at
        FROM knowledge_surrogates
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 4
        """,
        (client_id,),
    ).fetchall() if table_exists(db, "knowledge_surrogates") else []

    goals = [
        {
            "id": str(row["id"]),
            "title": normalize_text(row["name"]) or "事件线",
            "summary": normalize_text(row["summary"]) or normalize_text(row["next_step"]),
            "subtitle": normalize_text(row["stage"]),
            "updatedAt": normalize_text(row["updated_at"]) or None,
        }
        for row in event_line_rows[:4]
    ]
    related_tasks = [
        {
            "id": str(row["id"]),
            "title": normalize_text(row["title"]) or "未命名任务",
            "status": normalize_text(row["progress_status"]),
            "eventLineName": event_line_name_by_id.get(normalize_text(row["event_line_id"])) or None,
            "nextAction": normalize_text(row["next_action"]) or normalize_text(row["current_blocker"]) or None,
        }
        for row in task_rows[:6]
    ]
    open_questions = [
        {
            "id": f"question-{row['id']}",
            "title": normalize_text(row["title"]) or "开放问题",
            "summary": normalize_text(row["current_blocker"]) or normalize_text(row["next_action"]),
            "subtitle": normalize_text(row["progress_status"]),
            "updatedAt": normalize_text(row["updated_at"]) or None,
        }
        for row in task_rows[:4]
        if normalize_text(row["current_blocker"]) or normalize_text(row["next_action"])
    ]
    recent_documents = [
        {
            "id": str(row["id"]),
            "title": normalize_text(row["title"]) or "知识代理",
            "summary": normalize_text(row["overview_summary"]),
            "subtitle": normalize_text(row["source_type"]),
            "updatedAt": normalize_text(row["updated_at"]) or None,
        }
        for row in surrogate_rows[:4]
    ]
    available_sources = ["workspace_snapshot"]
    missing_sources = []
    if recent_documents:
        available_sources.append("knowledge_surrogate")
    else:
        missing_sources.append("knowledge_surrogate")
    if not open_questions:
        missing_sources.append("recent_meetings")
    if not goals and not related_tasks:
        missing_sources.append("workspace_snapshot")

    status = "rich" if recent_documents and goals and related_tasks else ("partial" if goals or related_tasks else "missing")
    return {
        "status": status,
        "client": {
            "id": client_id,
            "name": normalize_text(client_row["name"]) or "客户",
            "updatedAt": normalize_text(client_row["updated_at"]) or None,
        },
        "goals": goals,
        "meetings": [],
        "documentCards": recent_documents,
        "latestOpenQuestions": open_questions,
        "latestConflicts": [
            {
                "id": f"conflict-{row['id']}",
                "title": normalize_text(row["name"]) or "事件线冲突",
                "summary": normalize_text(row["recent_decision"]) or normalize_text(row["current_blocker"]),
                "subtitle": normalize_text(row["stage"]),
                "updatedAt": normalize_text(row["updated_at"]) or None,
            }
            for row in event_line_rows[:3]
            if normalize_text(row["recent_decision"]) or normalize_text(row["current_blocker"])
        ],
        "relatedTasks": related_tasks,
        "availableSources": available_sources,
        "missingSources": missing_sources,
    }


def build_client_dna_summary(db: sqlite3.Connection, client_row: sqlite3.Row) -> dict[str, object] | None:
    if not table_exists(db, "client_dna_documents"):
        return None
    rows = db.execute(
        """
        SELECT module_key, title, summary, normalized_text, updated_at
        FROM client_dna_documents
        WHERE client_id = ?
        ORDER BY updated_at DESC
        """,
        (str(client_row["id"]),),
    ).fetchall()
    if not rows:
        return None
    modules = []
    summaries = []
    latest_updated_at = normalize_text(client_row["updated_at"])
    for row in rows:
        text = normalize_text(row["summary"]) or normalize_text(row["normalized_text"])
        if not text or text.startswith('{"prompt'):
            continue
        latest_updated_at = normalize_text(row["updated_at"]) or latest_updated_at
        title = normalize_text(row["title"]) or normalize_text(row["module_key"]) or "客户资料"
        modules.append(
            {
                "moduleKey": normalize_text(row["module_key"]),
                "title": title,
                "summary": text[:2000],
                "updatedAt": normalize_text(row["updated_at"]) or None,
            }
        )
        summaries.append(f"{title}：{text[:220]}")
    if not modules:
        return None
    return {
        "summary": "；".join(summaries[:6]),
        "modules": modules,
        "updatedAt": latest_updated_at or None,
    }


def build_event_line_snapshots(db: sqlite3.Connection, client_row: sqlite3.Row) -> list[dict[str, object]]:
    if not table_exists(db, "event_lines"):
        return []
    rows = db.execute(
        """
        SELECT id, name, status, stage, summary, current_blocker, next_step, recent_decision, updated_at
        FROM event_lines
        WHERE primary_client_id = ?
        ORDER BY updated_at DESC
        """,
        (str(client_row["id"]),),
    ).fetchall()
    return [
        {
            "sourceId": str(row["id"]),
            "payload": {
                "id": str(row["id"]),
                "name": normalize_text(row["name"]),
                "status": normalize_text(row["status"]),
                "stage": normalize_text(row["stage"]),
                "summary": normalize_text(row["summary"]),
                "currentBlocker": normalize_text(row["current_blocker"]),
                "nextStep": normalize_text(row["next_step"]),
                "recentDecision": normalize_text(row["recent_decision"]),
            },
            "updatedAt": normalize_text(row["updated_at"]) or normalize_text(client_row["updated_at"]),
        }
        for row in rows
    ]


def build_meeting_summaries(db: sqlite3.Connection, client_row: sqlite3.Row) -> list[dict[str, object]]:
    if not table_exists(db, "meetings"):
        return []
    columns = table_columns(db, "meetings")
    required = {"id", "client_id"}
    if not required.issubset(columns):
        return []
    title_column = "title" if "title" in columns else None
    summary_column = "summary" if "summary" in columns else ("overview" if "overview" in columns else None)
    date_column = "meeting_date" if "meeting_date" in columns else ("held_at" if "held_at" in columns else "updated_at")
    rows = db.execute(
        f"""
        SELECT id, {title_column or 'id'} AS meeting_title,
               {summary_column or 'id'} AS meeting_summary,
               {date_column} AS meeting_date,
               updated_at
        FROM meetings
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 8
        """,
        (str(client_row["id"]),),
    ).fetchall()
    result = []
    for row in rows:
        title = normalize_text(row["meeting_title"]) or "会议"
        summary = normalize_text(row["meeting_summary"])
        result.append(
            {
                "sourceId": str(row["id"]),
                "payload": {
                    "title": title,
                    "summary": summary,
                    "meetingDate": normalize_text(row["meeting_date"]) or None,
                },
                "updatedAt": normalize_text(row["updated_at"]) or normalize_text(client_row["updated_at"]),
            }
        )
    return result


def build_surrogates(db: sqlite3.Connection, client_row: sqlite3.Row) -> list[dict[str, object]]:
    if not table_exists(db, "knowledge_surrogates"):
        return []
    rows = db.execute(
        """
        SELECT id, title, overview_summary, retrieval_summary, source_type, updated_at
        FROM knowledge_surrogates
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 12
        """,
        (str(client_row["id"]),),
    ).fetchall()
    return [
        {
            "sourceId": str(row["id"]),
            "payload": {
                "title": normalize_text(row["title"]) or "知识代理",
                "summary": normalize_text(row["overview_summary"]) or normalize_text(row["retrieval_summary"]),
                "overviewSummary": normalize_text(row["overview_summary"]),
                "sourceType": normalize_text(row["source_type"]),
            },
            "updatedAt": normalize_text(row["updated_at"]) or normalize_text(client_row["updated_at"]),
        }
        for row in rows
        if normalize_text(row["overview_summary"]) or normalize_text(row["retrieval_summary"])
    ]


def build_cockpit_snapshot(workspace_snapshot: dict[str, object], client_row: sqlite3.Row) -> dict[str, object]:
    goals = workspace_snapshot.get("goals") if isinstance(workspace_snapshot.get("goals"), list) else []
    open_questions = workspace_snapshot.get("latestOpenQuestions") if isinstance(workspace_snapshot.get("latestOpenQuestions"), list) else []
    documents = workspace_snapshot.get("documentCards") if isinstance(workspace_snapshot.get("documentCards"), list) else []
    headline = (
        "已从桌面端发布轻量战略 cockpit，可作为手机端咨询的止损上下文。"
        if goals or documents
        else "当前桌面端没有足够资料生成正式战略 cockpit。"
    )
    return {
        "status": "partial" if goals or documents or open_questions else "missing",
        "headline": {"summary": headline},
        "health": [{"summary": item.get("summary") or item.get("title") or "暂无健康线索"} for item in goals[:3] if isinstance(item, dict)],
        "twoWeekChanges": [{"summary": item.get("summary") or item.get("title") or "暂无变化线索"} for item in goals[:3] if isinstance(item, dict)],
        "pendingDecisions": [{"summary": item.get("summary") or item.get("title") or "暂无待决策"} for item in open_questions[:3] if isinstance(item, dict)],
        "pendingMaterials": [{"summary": item.get("summary") or item.get("title") or "暂无待补材料"} for item in documents[:3] if isinstance(item, dict)],
        "updatedAt": normalize_text(client_row["updated_at"]) or None,
    }


def build_publish_items(
    db: sqlite3.Connection,
    client_row: sqlite3.Row,
    include: set[str],
) -> list[dict[str, object]]:
    client_id = str(client_row["id"])
    client_name = normalize_text(client_row["name"]) or "客户"
    items: list[dict[str, object]] = []

    workspace_snapshot = build_workspace_snapshot(db, client_row)
    workspace_updated_at = normalize_text(workspace_snapshot.get("client", {}).get("updatedAt") if isinstance(workspace_snapshot.get("client"), dict) else client_row["updated_at"]) or normalize_text(client_row["updated_at"])

    def append_item(source_type: str, source_id: str, payload: dict[str, object], updated_at: str, evidence_refs: list[str] | None = None) -> None:
        items.append(
            {
                "clientId": client_id,
                "sourceType": source_type,
                "sourceId": source_id,
                "snapshotVersion": 1,
                "snapshotHash": stable_hash(payload),
                "updatedAt": updated_at,
                "payload": payload,
                "evidenceRefs": evidence_refs or [],
            }
        )

    if "workspace_snapshot" in include:
        append_item(
            "workspace_snapshot",
            f"workspace:{client_id}",
            workspace_snapshot,
            workspace_updated_at,
            [f"client:{client_name}"],
        )

    if "client_dna" in include:
        dna_summary = build_client_dna_summary(db, client_row)
        if dna_summary:
            append_item(
                "client_dna",
                f"dna:{client_id}",
                dna_summary,
                normalize_text(dna_summary.get("updatedAt")) or workspace_updated_at,
                [f"client:{client_name}", "client_dna_documents"],
            )

    if "event_line_snapshot" in include:
        for snapshot in build_event_line_snapshots(db, client_row):
            append_item(
                "event_line_snapshot",
                str(snapshot["sourceId"]),
                dict(snapshot["payload"]),
                str(snapshot["updatedAt"]),
                [f"client:{client_name}", f"event_line:{snapshot['sourceId']}"],
            )

    if "meeting_summary" in include:
        for summary in build_meeting_summaries(db, client_row):
            append_item(
                "meeting_summary",
                str(summary["sourceId"]),
                dict(summary["payload"]),
                str(summary["updatedAt"]),
                [f"client:{client_name}", f"meeting:{summary['sourceId']}"],
            )

    if "knowledge_surrogate" in include:
        for surrogate in build_surrogates(db, client_row):
            append_item(
                "knowledge_surrogate",
                str(surrogate["sourceId"]),
                dict(surrogate["payload"]),
                str(surrogate["updatedAt"]),
                [f"client:{client_name}", f"knowledge:{surrogate['sourceId']}"],
            )

    if "strategic_cockpit" in include:
        cockpit_snapshot = build_cockpit_snapshot(workspace_snapshot, client_row)
        append_item(
            "strategic_cockpit",
            f"cockpit:{client_id}",
            cockpit_snapshot,
            normalize_text(cockpit_snapshot.get("updatedAt")) or workspace_updated_at,
            [f"client:{client_name}", "workspace_snapshot"],
        )

    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="把桌面端客户知识快照手动发布到云端 mirror。")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="桌面端本地 app.db 路径")
    parser.add_argument("--base-url", default=DEFAULT_CLOUD_BASE_URL, help="云端 API Base URL")
    parser.add_argument("--client-id", action="append", dest="client_ids", help="只发布指定 client_id，可重复传入")
    parser.add_argument(
        "--include",
        default="workspace_snapshot,client_dna,event_line_snapshot,meeting_summary,knowledge_surrogate,strategic_cockpit",
        help="逗号分隔的 sourceType 白名单",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印将要发布的条目，不真正调用云端")
    args = parser.parse_args()

    include = {item.strip() for item in args.include.split(",") if item.strip()}
    unsupported = sorted(include - set(SUPPORTED_SOURCE_TYPES))
    if unsupported:
        raise SystemExit(f"不支持的 sourceType：{', '.join(unsupported)}")

    db_path = Path(args.db_path).expanduser()
    if not db_path.exists():
        raise SystemExit(f"本地数据库不存在：{db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    token = load_cloud_access_token(conn)
    clients = load_clients(conn, args.client_ids)
    if not clients:
        raise SystemExit("没有找到需要发布的客户。")

    all_items: list[dict[str, object]] = []
    for client_row in clients:
        all_items.extend(build_publish_items(conn, client_row, include))

    print(f"客户数量：{len(clients)}")
    print(f"待发布快照：{len(all_items)} 条")
    for item in all_items[:20]:
        print(f"- {item['clientId']} | {item['sourceType']} | {item['sourceId']}")
    if len(all_items) > 20:
        print(f"... 其余 {len(all_items) - 20} 条未展开")

    if args.dry_run or not all_items:
        return 0

    result = fetch_json(
        f"{args.base_url}/api/v1/mobile/knowledge-mirror/publish",
        token,
        method="POST",
        payload={"items": all_items},
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
~~~

## `scripts/run-local-electron.mjs`

- 编码: `utf-8`

~~~javascript
#!/usr/bin/env node

import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '..');
const sourceDistRoot = path.join(projectRoot, 'node_modules', 'electron', 'dist');
const sourceElectronApp = path.join(sourceDistRoot, 'Electron.app');
const sourceElectronBinary = path.join(sourceElectronApp, 'Contents', 'MacOS', 'Electron');
const sourceBundleId = 'com.yiyu.selfworkbench.dev';
const sourceBundleName = '益语智库自用平台（开发版）';
const appArgs = process.argv.slice(2);

function fail(message) {
  console.error(`[run-local-electron] ${message}`);
  process.exit(1);
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: options.stdio ?? 'pipe',
    encoding: 'utf8',
    ...options,
  });
  if (result.status !== 0) {
    const detail = (result.stderr || result.stdout || '').trim();
    fail(`${command} ${args.join(' ')} failed${detail ? `: ${detail}` : ''}`);
  }
  return result;
}

function plistRead(plistPath, keyPath) {
  const result = spawnSync('/usr/libexec/PlistBuddy', ['-c', `Print :${keyPath}`, plistPath], {
    stdio: 'pipe',
    encoding: 'utf8',
  });
  if (result.status !== 0) return '';
  return (result.stdout || '').trim();
}

function plistSet(plistPath, keyPath, value) {
  const setResult = spawnSync('/usr/libexec/PlistBuddy', ['-c', `Set :${keyPath} ${value}`, plistPath], {
    stdio: 'ignore',
  });
  if (setResult.status === 0) return;
  run('/usr/libexec/PlistBuddy', ['-c', `Add :${keyPath} string ${value}`, plistPath], { stdio: 'ignore' });
}

function ensurePlistStringValue(plistPath, keyPath, value) {
  if (plistRead(plistPath, keyPath) === value) return false;
  plistSet(plistPath, keyPath, value);
  return true;
}

function restoreSourceElectronBundleIdentity() {
  if (!fs.existsSync(sourceElectronBinary)) {
    fail(`Electron runtime not found at ${sourceElectronBinary}`);
  }

  let changed = false;
  const topInfo = path.join(sourceElectronApp, 'Contents', 'Info.plist');
  changed = ensurePlistStringValue(topInfo, 'CFBundleIdentifier', sourceBundleId) || changed;
  changed = ensurePlistStringValue(topInfo, 'CFBundleName', sourceBundleName) || changed;
  changed = ensurePlistStringValue(topInfo, 'CFBundleDisplayName', sourceBundleName) || changed;

  const helpers = [
    {
      relative: path.join('Contents', 'Frameworks', 'Electron Helper.app', 'Contents', 'Info.plist'),
      id: `${sourceBundleId}.helper`,
      name: `${sourceBundleName} Helper`,
    },
    {
      relative: path.join('Contents', 'Frameworks', 'Electron Helper (Renderer).app', 'Contents', 'Info.plist'),
      id: `${sourceBundleId}.helper.renderer`,
      name: `${sourceBundleName} Helper (Renderer)`,
    },
    {
      relative: path.join('Contents', 'Frameworks', 'Electron Helper (GPU).app', 'Contents', 'Info.plist'),
      id: `${sourceBundleId}.helper.gpu`,
      name: `${sourceBundleName} Helper (GPU)`,
    },
    {
      relative: path.join('Contents', 'Frameworks', 'Electron Helper (Plugin).app', 'Contents', 'Info.plist'),
      id: `${sourceBundleId}.helper.plugin`,
      name: `${sourceBundleName} Helper (Plugin)`,
    },
  ];

  for (const helper of helpers) {
    const helperInfo = path.join(sourceElectronApp, helper.relative);
    if (!fs.existsSync(helperInfo)) continue;
    changed = ensurePlistStringValue(helperInfo, 'CFBundleIdentifier', helper.id) || changed;
    changed = ensurePlistStringValue(helperInfo, 'CFBundleName', helper.name) || changed;
    changed = ensurePlistStringValue(helperInfo, 'CFBundleDisplayName', helper.name) || changed;
  }

  const frameworkInfo = path.join(
    sourceElectronApp,
    'Contents',
    'Frameworks',
    'Electron Framework.framework',
    'Versions',
    'A',
    'Resources',
    'Info.plist',
  );
  if (fs.existsSync(frameworkInfo)) {
    changed = ensurePlistStringValue(frameworkInfo, 'CFBundleIdentifier', `${sourceBundleId}.framework`) || changed;
    changed = ensurePlistStringValue(frameworkInfo, 'CFBundleName', `${sourceBundleName} Framework`) || changed;
  }

  if (changed) {
    spawnSync('codesign', ['--force', '--deep', '--sign', '-', sourceElectronApp], {
      stdio: 'ignore',
    });
  }
}

if (process.platform !== 'darwin') {
  const child = spawn(sourceElectronBinary, appArgs.length ? appArgs : ['.'], {
    cwd: projectRoot,
    stdio: 'inherit',
    env: process.env,
  });
  child.on('exit', (code, signal) => {
    if (signal) process.kill(process.pid, signal);
    process.exit(code ?? 0);
  });
} else {
  restoreSourceElectronBundleIdentity();
  const child = spawn(sourceElectronBinary, appArgs.length ? appArgs : ['.'], {
    cwd: projectRoot,
    stdio: 'inherit',
    env: process.env,
  });
  child.on('exit', (code, signal) => {
    if (signal) process.kill(process.pid, signal);
    process.exit(code ?? 0);
  });
}
~~~

## `scripts/smoke-cloud-backend-volcengine.sh`

- 编码: `utf-8`

~~~bash
#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://101.126.34.232}"

retry_curl() {
  local path="$1"
  local attempts="${2:-8}"
  local delay="${3:-2}"
  local i
  for ((i=1; i<=attempts; i++)); do
    if curl -fsS "${BASE_URL%/}${path}" >/tmp/yiyu-cloud-smoke.out 2>/tmp/yiyu-cloud-smoke.err; then
      cat /tmp/yiyu-cloud-smoke.out
      return 0
    fi
    if [[ $i -lt $attempts ]]; then
      sleep "${delay}"
    fi
  done
  cat /tmp/yiyu-cloud-smoke.err >&2 || true
  return 1
}

echo "=== health ==="
retry_curl "/health"
echo

echo "=== smart-input route ==="
OPENAPI_JSON="$(retry_curl "/openapi.json")"
if grep -q '"/api/v1/mobile/smart-input/task-draft"' <<<"${OPENAPI_JSON}"; then
  echo "smart-input route present"
else
  echo "smart-input route missing" >&2
  exit 1
fi

echo "=== required env hints ==="
cat <<'EOF'
Ensure remote .env contains:
- YIYU_CLOUD_PUBLIC_BASE_URL
- DOUBAO_FILE_ASR_APP_ID
- DOUBAO_FILE_ASR_ACCESS_TOKEN
- DOUBAO_STREAM_ASR_APP_ID
- DOUBAO_STREAM_ASR_ACCESS_TOKEN
Optional:
- DASHSCOPE_API_KEY
- YIYU_SMART_INPUT_MODEL
EOF
~~~

## `scripts/stabilize-mac-app.mjs`

- 编码: `utf-8`

~~~javascript
#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const inputAppPath = process.argv[2];
const appPath = inputAppPath ? path.resolve(inputAppPath) : '';

function fail(message) {
  console.error(`[stabilize-mac-app] ${message}`);
  process.exit(1);
}

function info(message) {
  console.log(`[stabilize-mac-app] ${message}`);
}

function run(command, args, { allowFailure = false, stdio = 'inherit' } = {}) {
  const result = spawnSync(command, args, { stdio, encoding: 'utf8' });
  if (result.error) {
    if (allowFailure) return result;
    fail(`${command} failed: ${result.error.message}`);
  }
  if (result.status !== 0 && !allowFailure) {
    const detail = (result.stderr || result.stdout || '').trim();
    fail(`${command} ${args.join(' ')} exited with status ${result.status}${detail ? `: ${detail}` : ''}`);
  }
  return result;
}

function clearAllAttributesRecursive(targetPath) {
  run('xattr', ['-cr', targetPath], { allowFailure: true, stdio: 'ignore' });
}

function removeTransientRuntimeFiles(rootPath) {
  const visit = (entryPath) => {
    const stat = fs.lstatSync(entryPath);
    if (stat.isSymbolicLink()) return;
    if (stat.isDirectory()) {
      if (path.basename(entryPath) === '__pycache__') {
        fs.rmSync(entryPath, { recursive: true, force: true });
        return;
      }
      for (const child of fs.readdirSync(entryPath)) {
        visit(path.join(entryPath, child));
      }
      return;
    }
    if (entryPath.endsWith('.cstemp') || entryPath.endsWith('.pyc') || entryPath.endsWith('.pyo')) {
      fs.rmSync(entryPath, { force: true });
    }
  };

  visit(rootPath);
}

if (process.platform !== 'darwin') {
  fail('This script only supports macOS.');
}

if (!appPath || !fs.existsSync(appPath) || !appPath.endsWith('.app')) {
  fail(`App bundle not found: ${appPath || '(missing path)'}`);
}

info(`stabilizing ${appPath}`);
removeTransientRuntimeFiles(appPath);
clearAllAttributesRecursive(appPath);

info('re-signing app bundle');
run('codesign', ['--force', '--deep', '--sign', '-', '--timestamp=none', appPath]);

removeTransientRuntimeFiles(appPath);
clearAllAttributesRecursive(appPath);

info('verifying code signature');
run('codesign', ['--verify', '--deep', '--strict', '--verbose=2', appPath]);

const assessment = run('spctl', ['--assess', '--type', 'open', '-vv', appPath], {
  allowFailure: true,
  stdio: 'pipe',
});
const assessmentOutput = `${assessment.stdout || ''}${assessment.stderr || ''}`.trim();
if (assessment.status === 0) {
  info(`gatekeeper assessment passed: ${assessmentOutput || 'ok'}`);
} else if (assessmentOutput) {
  info(`gatekeeper assessment note: ${assessmentOutput}`);
}

info('stabilization complete');
~~~

## `scripts/sync-local-event-lines-to-cloud.py`

- 编码: `utf-8`

~~~python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_DB_PATH = Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench" / "app.db"
DEFAULT_CLOUD_BASE_URL = os.environ.get("YIYU_CLOUD_API_URL", "http://101.126.34.232").rstrip("/")


def load_cloud_access_token(db: sqlite3.Connection) -> str:
    row = db.execute("SELECT value FROM settings WHERE key = 'cloud_access_token'").fetchone()
    token = str(row[0]).strip() if row and row[0] else ""
    if not token:
        raise SystemExit("未找到 cloud_access_token，请先在桌面版里登录云端账号。")
    return token


def fetch_json(url: str, token: str, *, method: str = "GET", payload: dict | None = None) -> object:
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"{method} {url} 失败：HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"{method} {url} 失败：{exc}") from exc
    return json.loads(body)


def local_event_lines_payload(db: sqlite3.Connection) -> list[dict[str, object]]:
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """
        SELECT id, name, kind, status, visibility_scope, business_category, stage, summary, intent,
               current_blocker, recent_decision, next_step, evidence_count, owner_id, owner_name,
               primary_client_id, primary_client_name, primary_department_id, primary_department_name,
               participant_ids_json, closed_at, closed_by_user_id, created_at, updated_at
        FROM event_lines
        ORDER BY updated_at DESC, created_at DESC
        """
    ).fetchall()
    result: list[dict[str, object]] = []
    for row in rows:
        activities = db.execute(
            """
            SELECT id, source_type, source_id, happened_at, actor_id, title, summary, metadata_json
            FROM event_line_activities
            WHERE event_line_id = ?
            ORDER BY happened_at ASC, id ASC
            """,
            (str(row["id"]),),
        ).fetchall()
        result.append(
            {
                "id": str(row["id"]),
                "name": str(row["name"]),
                "kind": str(row["kind"] or "custom"),
                "status": str(row["status"] or "active"),
                "visibilityScope": str(row["visibility_scope"] or "project_public"),
                "businessCategory": str(row["business_category"]) if row["business_category"] else None,
                "stage": str(row["stage"]) if row["stage"] else None,
                "summary": str(row["summary"]) if row["summary"] else None,
                "intent": str(row["intent"]) if row["intent"] else None,
                "currentBlocker": str(row["current_blocker"]) if row["current_blocker"] else None,
                "recentDecision": str(row["recent_decision"]) if row["recent_decision"] else None,
                "nextStep": str(row["next_step"]) if row["next_step"] else None,
                "evidenceCount": int(row["evidence_count"] or 0),
                "ownerId": str(row["owner_id"]) if row["owner_id"] else None,
                "primaryClientId": str(row["primary_client_id"]) if row["primary_client_id"] else None,
                "primaryClientName": str(row["primary_client_name"]) if row["primary_client_name"] else None,
                "primaryDepartmentId": str(row["primary_department_id"]) if row["primary_department_id"] else None,
                "participantIds": [
                    str(item)
                    for item in json.loads(row["participant_ids_json"] or "[]")
                    if str(item).strip()
                ],
                "closedAt": str(row["closed_at"]) if row["closed_at"] else None,
                "closedByUserId": str(row["closed_by_user_id"]) if row["closed_by_user_id"] else None,
                "createdAt": str(row["created_at"]),
                "updatedAt": str(row["updated_at"]),
                "activities": [
                    {
                        "id": str(activity["id"]),
                        "sourceType": str(activity["source_type"]),
                        "sourceId": str(activity["source_id"]),
                        "happenedAt": str(activity["happened_at"]),
                        "actorId": str(activity["actor_id"]) if activity["actor_id"] else None,
                        "title": str(activity["title"]),
                        "summary": str(activity["summary"]),
                        "metadata": (
                            json.loads(activity["metadata_json"] or "{}")
                            if activity["metadata_json"]
                            else {}
                        ),
                    }
                    for activity in activities
                ],
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="把桌面本地事件线增量补到当前云端。")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="本地桌面 app.db 路径")
    parser.add_argument("--base-url", default=DEFAULT_CLOUD_BASE_URL, help="云端 API Base URL")
    parser.add_argument("--dry-run", action="store_true", help="只显示待迁移条目，不真正写入云端")
    args = parser.parse_args()

    db_path = Path(args.db_path).expanduser()
    if not db_path.exists():
        raise SystemExit(f"本地数据库不存在：{db_path}")

    conn = sqlite3.connect(str(db_path))
    token = load_cloud_access_token(conn)
    local_event_lines = local_event_lines_payload(conn)
    remote_event_lines = fetch_json(f"{args.base_url}/api/v1/event-lines", token)
    if not isinstance(remote_event_lines, list):
        raise SystemExit("云端事件线返回格式异常。")
    remote_ids = {
        str(item.get("id"))
        for item in remote_event_lines
        if isinstance(item, dict) and item.get("id")
    }
    missing = [item for item in local_event_lines if str(item["id"]) not in remote_ids]

    print(f"本地事件线：{len(local_event_lines)} 条")
    print(f"云端事件线：{len(remote_ids)} 条")
    print(f"待补迁移：{len(missing)} 条")
    for item in missing:
        print(f"- {item['id']} | {item['name']}")

    if args.dry_run or not missing:
        return 0

    result = fetch_json(
        f"{args.base_url}/api/v1/event-lines/import-desktop",
        token,
        method="POST",
        payload={"eventLines": missing},
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
~~~

## `scripts/test-template-save.sh`

- 编码: `utf-8`

~~~bash
#!/bin/bash
# End-to-end test: create template under 益语智库, then verify it appears in project structure
set -e

BASE="http://127.0.0.1:47829"
CLIENT_ID="client_53d82aa249"

echo "=== Step 1: Create template module ==="
RESULT=$(curl -s -w "\n%{http_code}" -X POST "$BASE/api/v1/clients/$CLIENT_ID/project-modules" \
  -H "Content-Type: application/json" \
  -d '{"name":"烟测模板","goal":"自动测试","templateTasksJson":"{\"tasks\":[{\"id\":\"t1\",\"title\":\"第一步\",\"description\":\"测试\",\"relativeDays\":0,\"durationMinutes\":60,\"priority\":\"normal\"}],\"options\":{\"autoCreateEventLine\":true,\"aiFillEmpty\":false}}"}')
HTTP_CODE=$(echo "$RESULT" | tail -1)
BODY=$(echo "$RESULT" | head -1)
echo "HTTP: $HTTP_CODE"
echo "Body: $BODY"
if [ "$HTTP_CODE" != "200" ]; then
  echo "FAIL: create returned $HTTP_CODE"
  exit 1
fi
MODULE_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Created module: $MODULE_ID"

echo ""
echo "=== Step 2: Verify in project structure ==="
STRUCTURE=$(curl -s "$BASE/api/v1/clients/$CLIENT_ID/project-structure")
FOUND=$(echo "$STRUCTURE" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for m in d.get('modules', []):
    if m['id'] == '$MODULE_ID':
        has_template = bool(m.get('templateTasksJson'))
        print(f'FOUND: {m[\"name\"]}  hasTemplate={has_template}')
        sys.exit(0)
print('NOT_FOUND')
sys.exit(1)
" 2>&1)
echo "$FOUND"

echo ""
echo "=== Step 3: Clean up ==="
sqlite3 "/Users/guyuanyuan/Library/Application Support/YiyuThinkTankWorkbench/app.db" "DELETE FROM project_modules WHERE id = '$MODULE_ID'"
echo "Cleaned up $MODULE_ID"

echo ""
echo "=== ALL TESTS PASSED ==="
~~~

## `src/main/collabGit.ts`

- 编码: `utf-8`

~~~typescript
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import type {
  CollabActionResult,
  CollabChangeGroup,
  CollabChangeGroupKey,
  CollabConflictRisk,
  CollabEffectPreview,
  CollabFileChange,
  CollabFileChangeType,
  CollabRepoStatus,
  CommitAndPushToMainPayload,
  PullPreview,
  PullSelectedFromMainPayload,
  PushPreview,
} from '../shared/types.js';

type RunCommandOptions = {
  cwd?: string;
  allowNonZero?: boolean;
};

type RunCommandResult = {
  stdout: string;
  stderr: string;
  exitCode: number;
};

type ParsedStatusEntry = {
  path: string;
  previousPath?: string | null;
  type: CollabFileChangeType;
  x: string;
  y: string;
  isUnmerged: boolean;
};

type ParsedDiffEntry = {
  path: string;
  previousPath?: string | null;
  type: Exclude<CollabFileChangeType, 'untracked'>;
};

type RepoSnapshot = {
  repoPath: string | null;
  repoName: string | null;
  suggestedRepoPath: string | null;
  gitRepoPath: string | null;
  scopeRelativePath: string | null;
  isConfigured: boolean;
  isValid: boolean;
  branch: string | null;
  isMainBranch: boolean;
  aheadCount: number;
  behindCount: number;
  hasUnmergedPaths: boolean;
  localEntries: ParsedStatusEntry[];
  remoteEntries: ParsedDiffEntry[];
  localBranchEntries: ParsedDiffEntry[];
  localChangeCount: number;
  remoteChangeCount: number;
  statusText: string;
};

type RepoOptions = {
  repoPath?: string | null;
  suggestedCandidates: string[];
  fetchRemote?: boolean;
  appDbPath?: string | null;
};

type RepoWorkContext = {
  repoPath: string;
  gitRepoPath: string;
  scopeRelativePath: string | null;
};

type SharedSettingsTarget = {
  settingKey: 'settings.system_admin';
  repoRelativePath: '.yiyu-sync/settings.system_admin.json';
  groupKey: CollabChangeGroupKey;
  defaultValue: () => Record<string, unknown>;
};

type SharedSettingsRecord = Record<string, unknown>;

type EffectDraft = {
  id: string;
  title: string;
  summary: string;
  visibility: CollabEffectPreview['visibility'];
  scopeLabel: string;
  details: string[];
  relatedPaths: Set<string>;
  beforeLabel?: string | null;
  afterLabel?: string | null;
  beforeImageDataUrl?: string | null;
  afterImageDataUrl?: string | null;
};

const GROUP_LABELS: Record<CollabChangeGroupKey, string> = {
  shared_settings: '共享设置',
  renderer: '界面',
  desktop_shell: '桌面壳',
  local_backend: '本地 backend',
  cloud_backend: '共享 backend',
  scripts_docs: '脚本/文档/配置',
  other: '其他',
};

const GROUP_ORDER: CollabChangeGroupKey[] = [
  'shared_settings',
  'renderer',
  'desktop_shell',
  'local_backend',
  'cloud_backend',
  'scripts_docs',
  'other',
];

const SHARED_SETTINGS_TARGETS: SharedSettingsTarget[] = [
  {
    settingKey: 'settings.system_admin',
    repoRelativePath: '.yiyu-sync/settings.system_admin.json',
    groupKey: 'shared_settings',
    defaultValue: () => ({
      allowBusinessSettingsForEmployees: true,
      allowOrgDnaForEmployees: true,
      protectEmployeeAdmin: true,
      protectAiAndCloud: true,
      protectCloudSecurity: true,
      brandLogoDataUrl: null,
      updatedAt: new Date().toISOString(),
    }),
  },
];

const SHARED_SETTING_LABELS: Record<string, string> = {
  brandLogoDataUrl: '左上角品牌头像',
  allowBusinessSettingsForEmployees: '员工业务设置权限',
  allowOrgDnaForEmployees: '员工组织 DNA 权限',
  protectEmployeeAdmin: '员工管理保护',
  protectAiAndCloud: 'AI 与云端保护',
  protectCloudSecurity: '云端安全保护',
  updatedAt: '更新时间',
};

const BINARY_EXTENSIONS = new Set([
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.webp',
  '.ico',
  '.icns',
  '.pdf',
  '.zip',
  '.gz',
  '.mp4',
  '.mov',
  '.mp3',
  '.wav',
  '.ttf',
  '.otf',
  '.woff',
  '.woff2',
  '.dmg',
]);

const IGNORABLE_LOCAL_STATUS_PATHS = new Set([
  '.yiyu-sync/settings.system_admin.json',
]);

const IGNORABLE_LOCAL_STATUS_PREFIXES = [
  'mobile/',
];

const COLLAB_PRIMARY_REPO_NAME = 'yiyu-thinktank-workbench';
const COLLAB_LEGACY_REPO_NAME = 'yiyu-thinktank-workbench-main-sync';
const COLLAB_VISIBLE_WORKSPACE_SEGMENT = `${path.sep}openclaw${path.sep}workspace`;
const COLLAB_HIDDEN_WORKSPACE_SEGMENT = `${path.sep}.openclaw${path.sep}workspace`;

function normalizeCollabRepoBindingPath(targetPath: string) {
  let normalized = path.resolve(targetPath).replace(/[\\/]+$/, '');
  if (normalized.includes(COLLAB_HIDDEN_WORKSPACE_SEGMENT)) {
    normalized = normalized.replace(COLLAB_HIDDEN_WORKSPACE_SEGMENT, COLLAB_VISIBLE_WORKSPACE_SEGMENT);
  }
  const legacySuffix = `${path.sep}${COLLAB_LEGACY_REPO_NAME}`;
  if (normalized.endsWith(legacySuffix)) {
    return normalized.slice(0, -COLLAB_LEGACY_REPO_NAME.length) + COLLAB_PRIMARY_REPO_NAME;
  }
  if (path.basename(normalized) === 'workspace') {
    return path.join(normalized, COLLAB_PRIMARY_REPO_NAME);
  }
  return normalized;
}

function formatSyncedJson(value: Record<string, unknown>) {
  return `${JSON.stringify(value, null, 2)}\n`;
}

function readSharedSettingRecord(appDbPath: string, settingKey: string, defaultValue: () => Record<string, unknown>) {
  const db = new DatabaseSync(appDbPath);
  try {
    const row = db.prepare('SELECT value FROM settings WHERE key = ?').get(settingKey) as { value?: string } | undefined;
    if (row?.value) {
      const parsed = JSON.parse(row.value);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>;
      }
    }
  } catch {
    // Fall back to a stable default snapshot when local settings are missing or malformed.
  } finally {
    db.close();
  }
  return defaultValue();
}

function writeSharedSettingRecord(appDbPath: string, settingKey: string, value: Record<string, unknown>) {
  const db = new DatabaseSync(appDbPath);
  try {
    db.prepare('INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)').run(settingKey, JSON.stringify(value));
  } finally {
    db.close();
  }
}

async function exportSharedSettingsToRepo(repoPath: string, appDbPath?: string | null) {
  if (!appDbPath) return;
  const stat = await fs.promises.stat(appDbPath).catch(() => null);
  if (!stat?.isFile()) return;
  for (const target of SHARED_SETTINGS_TARGETS) {
    const nextRecord = readSharedSettingRecord(appDbPath, target.settingKey, target.defaultValue);
    const targetPath = path.join(repoPath, target.repoRelativePath);
    const nextContent = formatSyncedJson(nextRecord);
    const currentContent = await fs.promises.readFile(targetPath, 'utf8').catch(() => null);
    if (currentContent === nextContent) continue;
    await fs.promises.mkdir(path.dirname(targetPath), { recursive: true });
    await fs.promises.writeFile(targetPath, nextContent, 'utf8');
  }
}

async function importSelectedSharedSettingsFromRepo(repoPath: string, appDbPath: string | null | undefined, selectedPaths: string[]) {
  if (!appDbPath) return;
  const stat = await fs.promises.stat(appDbPath).catch(() => null);
  if (!stat?.isFile()) return;
  const selectedSet = new Set(selectedPaths);
  for (const target of SHARED_SETTINGS_TARGETS) {
    if (!selectedSet.has(target.repoRelativePath)) continue;
    const targetPath = path.join(repoPath, target.repoRelativePath);
    const rawContent = await fs.promises.readFile(targetPath, 'utf8').catch(() => null);
    if (!rawContent) {
      writeSharedSettingRecord(appDbPath, target.settingKey, target.defaultValue());
      continue;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(rawContent);
    } catch (error) {
      throw new Error(`${target.repoRelativePath} 不是有效 JSON，无法同步到本机设置。`);
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error(`${target.repoRelativePath} 内容格式不正确，无法同步到本机设置。`);
    }
    writeSharedSettingRecord(appDbPath, target.settingKey, parsed as Record<string, unknown>);
  }
}

function isPlainRecord(value: unknown): value is SharedSettingsRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function parseSharedSettingsContent(rawContent: string | null | undefined) {
  if (!rawContent) return null;
  try {
    const parsed = JSON.parse(rawContent);
    return isPlainRecord(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function areJsonValuesEqual(left: unknown, right: unknown) {
  return JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
}

function createEffectDraft(
  id: string,
  title: string,
  summary: string,
  visibility: CollabEffectPreview['visibility'],
  scopeLabel: string,
  relatedPaths: string[],
  details: string[] = [],
): EffectDraft {
  return {
    id,
    title,
    summary,
    visibility,
    scopeLabel,
    details,
    relatedPaths: new Set(relatedPaths),
  };
}

function finalizeEffectDrafts(drafts: EffectDraft[]): CollabEffectPreview[] {
  return drafts
    .map((draft) => ({
      id: draft.id,
      title: draft.title,
      summary: draft.summary,
      visibility: draft.visibility,
      scopeLabel: draft.scopeLabel,
      details: Array.from(new Set(draft.details.filter(Boolean))),
      relatedPaths: Array.from(draft.relatedPaths),
      beforeLabel: draft.beforeLabel ?? null,
      afterLabel: draft.afterLabel ?? null,
      beforeImageDataUrl: draft.beforeImageDataUrl ?? null,
      afterImageDataUrl: draft.afterImageDataUrl ?? null,
    }))
    .filter((draft) => draft.relatedPaths.length > 0);
}

function labelSharedSettingKey(settingKey: string) {
  return SHARED_SETTING_LABELS[settingKey] || settingKey;
}

async function readGitObject(context: RepoWorkContext, revision: string, targetPath: string) {
  const gitTargetPath = toScopedGitPath(context.scopeRelativePath, targetPath);
  const result = await runGit(context.gitRepoPath, ['show', `${revision}:${gitTargetPath}`], { allowNonZero: true });
  if (result.exitCode !== 0) return null;
  return result.stdout;
}

async function readWorkingTreeText(context: RepoWorkContext, targetPath: string) {
  return fs.promises.readFile(path.join(context.repoPath, targetPath), 'utf8').catch(() => null);
}

function normalizeRepoPath(targetPath: string) {
  return normalizeCollabRepoBindingPath(targetPath);
}

function normalizeRelativePath(targetPath: string) {
  return targetPath.replace(/\\/g, '/').replace(/^\.\//, '').replace(/^\/+/, '');
}

function computeScopeRelativePath(gitRepoPath: string, repoPath: string) {
  const relativePath = normalizeRelativePath(path.relative(gitRepoPath, repoPath));
  return relativePath && relativePath !== '.' ? relativePath : null;
}

function toScopedGitPath(scopeRelativePath: string | null, targetPath: string) {
  const normalizedTargetPath = normalizeRelativePath(targetPath);
  if (!scopeRelativePath) return normalizedTargetPath;
  return normalizedTargetPath ? `${scopeRelativePath}/${normalizedTargetPath}` : scopeRelativePath;
}

function stripScopePrefix(targetPath: string, scopeRelativePath: string | null) {
  const normalizedTargetPath = normalizeRelativePath(targetPath);
  if (!scopeRelativePath) return normalizedTargetPath;
  if (normalizedTargetPath === scopeRelativePath) return '';
  const prefix = `${scopeRelativePath}/`;
  if (!normalizedTargetPath.startsWith(prefix)) return null;
  return normalizedTargetPath.slice(prefix.length);
}

function mapStatusEntryToScope(entry: ParsedStatusEntry, scopeRelativePath: string | null): ParsedStatusEntry | null {
  const scopedPath = stripScopePrefix(entry.path, scopeRelativePath);
  const scopedPreviousPath = entry.previousPath ? stripScopePrefix(entry.previousPath, scopeRelativePath) : null;
  if (scopedPath === null) {
    if (entry.type === 'renamed' && scopedPreviousPath) {
      return {
        ...entry,
        path: scopedPreviousPath,
        previousPath: scopedPreviousPath,
      };
    }
    return null;
  }
  return {
    ...entry,
    path: scopedPath,
    previousPath: scopedPreviousPath,
  };
}

function mapDiffEntryToScope(entry: ParsedDiffEntry, scopeRelativePath: string | null): ParsedDiffEntry | null {
  const scopedPath = stripScopePrefix(entry.path, scopeRelativePath);
  const scopedPreviousPath = entry.previousPath ? stripScopePrefix(entry.previousPath, scopeRelativePath) : null;
  if (scopedPath === null) {
    if (entry.type === 'renamed' && scopedPreviousPath) {
      return {
        ...entry,
        path: scopedPreviousPath,
        previousPath: scopedPreviousPath,
      };
    }
    return null;
  }
  return {
    ...entry,
    path: scopedPath,
    previousPath: scopedPreviousPath,
  };
}

function createRepoWorkContext(repoPath: string, gitRepoPath: string, scopeRelativePath: string | null): RepoWorkContext {
  return { repoPath, gitRepoPath, scopeRelativePath };
}

function parseFileChangeTypeFromStatus(x: string, y: string, remainder: string): CollabFileChangeType {
  if (x === '?' && y === '?') return 'untracked';
  if (remainder.includes(' -> ') || x === 'R' || y === 'R') return 'renamed';
  if (x === 'D' || y === 'D') return 'deleted';
  if (x === 'A' || y === 'A') return 'added';
  return 'modified';
}

function isUnmergedStatus(x: string, y: string) {
  const pair = `${x}${y}`;
  return x === 'U' || y === 'U' || ['DD', 'AU', 'UD', 'UA', 'DU', 'AA', 'UU'].includes(pair);
}

function parseBranchHeader(rawLine: string) {
  const header = rawLine.replace(/^##\s*/, '').trim();
  if (!header) {
    return { branch: null, aheadCount: 0, behindCount: 0 };
  }
  if (header.startsWith('HEAD ')) {
    return { branch: 'HEAD', aheadCount: 0, behindCount: 0 };
  }
  const statusMatch = header.match(/^([^\s.]+)(?:\.\.\.[^\s]+)?(?: \[(.+)\])?$/);
  const branch = statusMatch?.[1] || header.split('...')[0] || header;
  const trailer = statusMatch?.[2] || '';
  const aheadCount = Number(trailer.match(/ahead (\d+)/)?.[1] || 0);
  const behindCount = Number(trailer.match(/behind (\d+)/)?.[1] || 0);
  return { branch, aheadCount, behindCount };
}

function parseStatusEntries(rawOutput: string) {
  const lines = rawOutput
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter(Boolean);
  const branchHeader = lines[0]?.startsWith('##') ? lines.shift() || '' : '';
  const parsedEntries: ParsedStatusEntry[] = [];
  for (const line of lines) {
    const x = line[0] || ' ';
    const y = line[1] || ' ';
    const remainder = line.slice(3);
    const type = parseFileChangeTypeFromStatus(x, y, remainder);
    if (type === 'renamed') {
      const [previousPath, nextPath] = remainder.split(' -> ');
      parsedEntries.push({
        path: (nextPath || previousPath || '').trim(),
        previousPath: previousPath?.trim() || null,
        type,
        x,
        y,
        isUnmerged: isUnmergedStatus(x, y),
      });
      continue;
    }
    parsedEntries.push({
      path: remainder.trim(),
      type,
      x,
      y,
      isUnmerged: isUnmergedStatus(x, y),
    });
  }
  return { branchHeader, parsedEntries };
}

function parseDiffEntries(rawOutput: string) {
  return rawOutput
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .flatMap((line) => {
      const parts = line.split('\t');
      const code = parts[0] || '';
      if (code.startsWith('R')) {
        const previousPath = parts[1]?.trim();
        const nextPath = parts[2]?.trim();
        if (!nextPath) return [];
        return [{
          path: nextPath,
          previousPath: previousPath || null,
          type: 'renamed' as const,
        }];
      }
      const targetPath = parts[1]?.trim();
      if (!targetPath) return [];
      const typeMap: Record<string, ParsedDiffEntry['type']> = {
        A: 'added',
        D: 'deleted',
        M: 'modified',
        T: 'modified',
      };
      return [{
        path: targetPath,
        type: typeMap[code[0] || 'M'] || 'modified',
      }];
    });
}

function classifyChangeGroup(targetPath: string) {
  const normalized = targetPath.replace(/\\/g, '/');
  if (normalized.startsWith('.yiyu-sync/')) {
    return { key: 'shared_settings' as const, label: GROUP_LABELS.shared_settings };
  }
  if (normalized.startsWith('src/renderer/')) return { key: 'renderer' as const, label: GROUP_LABELS.renderer };
  if (normalized.startsWith('src/main/') || normalized.startsWith('build-resources/')) {
    return { key: 'desktop_shell' as const, label: GROUP_LABELS.desktop_shell };
  }
  if (normalized.startsWith('backend/')) return { key: 'local_backend' as const, label: GROUP_LABELS.local_backend };
  if (normalized.startsWith('cloud_backend/')) return { key: 'cloud_backend' as const, label: GROUP_LABELS.cloud_backend };
  if (
    normalized.startsWith('scripts/') ||
    normalized.startsWith('docs/') ||
    normalized === 'README.md' ||
    normalized.endsWith('.md') ||
    normalized.endsWith('.docx') ||
    normalized.endsWith('.json') ||
    normalized.endsWith('.yaml') ||
    normalized.endsWith('.yml') ||
    normalized.endsWith('.toml') ||
    normalized.endsWith('.config.ts') ||
    normalized.endsWith('.config.js') ||
    normalized.startsWith('.')
  ) {
    return { key: 'scripts_docs' as const, label: GROUP_LABELS.scripts_docs };
  }
  return { key: 'other' as const, label: GROUP_LABELS.other };
}

function formatChangeSummary(type: CollabFileChangeType, previousPath?: string | null) {
  switch (type) {
    case 'added':
      return '新增';
    case 'deleted':
      return '删除';
    case 'renamed':
      return previousPath ? `重命名自 ${previousPath}` : '重命名';
    case 'untracked':
      return '未跟踪';
    default:
      return '修改';
  }
}

function hasBinaryExtension(targetPath: string) {
  return BINARY_EXTENSIONS.has(path.extname(targetPath).toLowerCase());
}

function isIgnorableLocalStatusPath(targetPath: string) {
  const normalizedPath = targetPath.replace(/\\/g, '/');
  return IGNORABLE_LOCAL_STATUS_PATHS.has(normalizedPath)
    || IGNORABLE_LOCAL_STATUS_PREFIXES.some((prefix) => normalizedPath === prefix.slice(0, -1) || normalizedPath.startsWith(prefix));
}

function addPathsToSet(targetSet: Set<string>, targetPath: string, previousPath?: string | null) {
  targetSet.add(targetPath);
  if (previousPath) targetSet.add(previousPath);
}

function countGroups(files: CollabFileChange[]): CollabChangeGroup[] {
  const counts = new Map<CollabChangeGroupKey, number>();
  for (const file of files) {
    counts.set(file.groupKey, (counts.get(file.groupKey) || 0) + 1);
  }
  return GROUP_ORDER
    .filter((groupKey) => counts.has(groupKey))
    .map((groupKey) => ({
      key: groupKey,
      label: GROUP_LABELS[groupKey],
      fileCount: counts.get(groupKey) || 0,
    }));
}

function buildSuggestedMessage(prefix: 'push' | 'pull', groups: CollabChangeGroup[]) {
  const labels = groups.slice(0, 3).map((group) => group.label).join('、') || '代码';
  return prefix === 'push' ? `sync: 更新${labels}` : `sync: 从 main 同步${labels}`;
}

function summarizeRendererEffect(targetPath: string) {
  const normalized = targetPath.replace(/\\/g, '/');
  if (normalized === 'src/renderer/App.tsx' || normalized.startsWith('src/renderer/components/collab/')) {
    return {
      id: 'renderer-collab-shell',
      title: '左侧协作入口和同步弹窗会变化',
      summary: '你会先看到“软件会怎么变”，再决定是否执行同步，不会再一上来只看文件清单。',
      visibility: 'visible' as const,
      scopeLabel: '界面可见',
      detail: '协作同步入口、确认弹窗和主要提示文案会更新。',
    };
  }
  if (normalized.startsWith('src/renderer/components/settings/')) {
    return {
      id: 'renderer-settings',
      title: '系统设置页的结构或文案会变化',
      summary: '你会在系统设置里直接看到布局、卡片或说明文字的调整。',
      visibility: 'visible' as const,
      scopeLabel: '界面可见',
      detail: '系统设置相关组件有改动，进入设置页时能直接看到变化。',
    };
  }
  if (normalized.startsWith('src/renderer/components/tasks/')) {
    return {
      id: 'renderer-tasks',
      title: '任务与日程模块会变化',
      summary: '任务与日程页面的结构、流程或操作入口会调整。',
      visibility: 'visible' as const,
      scopeLabel: '界面可见',
      detail: '任务相关组件有改动，建议同步后直接进入“任务与日程”确认。',
    };
  }
  if (normalized.startsWith('src/renderer/components/client_workspace/')) {
    return {
      id: 'renderer-client-workspace',
      title: '客户工作台的页面表现会变化',
      summary: '客户工作台里的区域结构、入口或交互可能会更新。',
      visibility: 'visible' as const,
      scopeLabel: '界面可见',
      detail: '客户工作台相关组件有改动，同步后建议优先打开该模块确认。',
    };
  }
  if (normalized.startsWith('src/renderer/components/strategic_accompaniment/')) {
    return {
      id: 'renderer-strategic',
      title: '战略陪伴模块会变化',
      summary: '战略陪伴页面的结构或操作流程可能会更新。',
      visibility: 'visible' as const,
      scopeLabel: '界面可见',
      detail: '战略陪伴相关组件有改动。',
    };
  }
  return {
    id: 'renderer-general',
    title: '软件界面会变化',
    summary: '同步后，至少会有一处你能直接看到的界面变化。',
    visibility: 'visible' as const,
    scopeLabel: '界面可见',
    detail: '前端界面文件有改动，建议同步后打开对应模块核对前后差别。',
  };
}

function summarizeDesktopEffect(targetPath: string) {
  const normalized = targetPath.replace(/\\/g, '/');
  if (normalized.startsWith('src/main/') || normalized === 'src/renderer/lib/api.ts' || normalized === 'src/shared/types.ts') {
    return {
      id: 'desktop-collab-runtime',
      title: '桌面端同步行为会变化',
      summary: '按钮背后的 Git 同步、确认逻辑或安装版更新流程会变化。',
      visibility: 'mixed' as const,
      scopeLabel: '桌面行为',
      detail: '这类变化不一定马上体现在单个页面上，但会直接影响按钮怎么工作。',
    };
  }
  return {
    id: 'desktop-general',
    title: '桌面端行为会变化',
    summary: '安装版的本地行为、桥接能力或启动逻辑会更新。',
    visibility: 'mixed' as const,
    scopeLabel: '桌面行为',
    detail: '这类变化更多影响软件怎么运行，而不是单个界面长什么样。',
  };
}

function summarizeBackendEffect(groupKey: CollabChangeGroupKey) {
  if (groupKey === 'local_backend') {
    return {
      id: 'backend-local',
      title: '本地 backend 逻辑会变化',
      summary: '界面未必马上不同，但本地数据链路、处理规则或接口行为会变化。',
      visibility: 'background' as const,
      scopeLabel: '后台逻辑',
      detail: '这类改动通常体现在任务结果、数据状态或接口响应上。',
    };
  }
  if (groupKey === 'cloud_backend') {
    return {
      id: 'backend-cloud',
      title: '共享 backend 逻辑会变化',
      summary: '界面未必立刻变，但共享账号、审批、组织或云端流程会受影响。',
      visibility: 'background' as const,
      scopeLabel: '后台逻辑',
      detail: '这类变化更偏业务规则和共享数据处理。',
    };
  }
  return {
    id: 'docs-config',
    title: '脚本、文档或配置会变化',
    summary: '你未必马上在界面看到差别，但后续构建、安装或说明文档会更新。',
    visibility: 'background' as const,
    scopeLabel: '配置与文档',
    detail: '这类变化通常影响协作方式、构建流程或说明文档。',
  };
}

function addEffectDetail(effectMap: Map<string, EffectDraft>, nextDraft: ReturnType<typeof createEffectDraft>, detail?: string | null) {
  const existing = effectMap.get(nextDraft.id);
  if (existing) {
    nextDraft.relatedPaths.forEach((targetPath) => existing.relatedPaths.add(targetPath));
    if (detail) existing.details.push(detail);
    return;
  }
  if (detail) nextDraft.details.push(detail);
  effectMap.set(nextDraft.id, nextDraft);
}

async function buildSharedSettingsEffect(
  mode: 'push' | 'pull',
  context: RepoWorkContext,
  files: CollabFileChange[],
) {
  const target = SHARED_SETTINGS_TARGETS[0];
  const matchedFiles = files.filter((file) => file.path === target.repoRelativePath);
  if (!matchedFiles.length) return null;
  const beforeRevision = mode === 'push' ? 'origin/main' : 'HEAD';
  const beforeRecord = parseSharedSettingsContent(await readGitObject(context, beforeRevision, target.repoRelativePath)) || target.defaultValue();
  const afterRecord = mode === 'push'
    ? (parseSharedSettingsContent(await readWorkingTreeText(context, target.repoRelativePath)) || target.defaultValue())
    : (parseSharedSettingsContent(await readGitObject(context, 'origin/main', target.repoRelativePath)) || target.defaultValue());
  const changedKeys = Array.from(new Set([
    ...Object.keys(beforeRecord),
    ...Object.keys(afterRecord),
  ])).filter((settingKey) => !areJsonValuesEqual(beforeRecord[settingKey], afterRecord[settingKey]));
  if (!changedKeys.length) return null;
  const changedLabels = changedKeys.slice(0, 4).map(labelSharedSettingKey);
  const brandChanged = !areJsonValuesEqual(beforeRecord.brandLogoDataUrl, afterRecord.brandLogoDataUrl);
  const summary = brandChanged
    ? '同步后，左上角品牌头像会跟着变化，团队两边看到的品牌展示会更一致。'
    : '同步后，系统级共享设置会变化，并影响这台机器对品牌或保护规则的理解。';
  const draft = createEffectDraft(
    'shared-settings-system-admin',
    brandChanged ? '系统品牌头像和共享设置会变化' : '系统级共享设置会变化',
    summary,
    brandChanged ? 'visible' : 'mixed',
    brandChanged ? '界面可见' : '共享设置',
    matchedFiles.map((file) => file.path),
    changedLabels.map((label) => `${label} 会更新`),
  );
  draft.beforeLabel = mode === 'push' ? 'main 当前效果' : '你本地当前效果';
  draft.afterLabel = mode === 'push' ? '推送到 main 后' : '从 main 同步后';
  draft.beforeImageDataUrl = typeof beforeRecord.brandLogoDataUrl === 'string' ? beforeRecord.brandLogoDataUrl : null;
  draft.afterImageDataUrl = typeof afterRecord.brandLogoDataUrl === 'string' ? afterRecord.brandLogoDataUrl : null;
  return draft;
}

async function buildEffectPreviews(
  mode: 'push' | 'pull',
  snapshot: RepoSnapshot,
  files: CollabFileChange[],
) {
  if (!snapshot.repoPath || !snapshot.gitRepoPath) return [];
  const context = createRepoWorkContext(snapshot.repoPath, snapshot.gitRepoPath, snapshot.scopeRelativePath);
  const effectMap = new Map<string, EffectDraft>();
  const sharedEffect = await buildSharedSettingsEffect(mode, context, files);
  if (sharedEffect) effectMap.set(sharedEffect.id, sharedEffect);
  for (const file of files) {
    const normalized = file.path.replace(/\\/g, '/');
    if (normalized === '.yiyu-sync/settings.system_admin.json') continue;
    if (file.groupKey === 'renderer') {
      const effect = summarizeRendererEffect(normalized);
      addEffectDetail(
        effectMap,
        createEffectDraft(effect.id, effect.title, effect.summary, effect.visibility, effect.scopeLabel, [file.path]),
        effect.detail,
      );
      continue;
    }
    if (file.groupKey === 'desktop_shell' || normalized === 'src/renderer/lib/api.ts' || normalized === 'src/shared/types.ts') {
      const effect = summarizeDesktopEffect(normalized);
      addEffectDetail(
        effectMap,
        createEffectDraft(effect.id, effect.title, effect.summary, effect.visibility, effect.scopeLabel, [file.path]),
        effect.detail,
      );
      continue;
    }
    if (file.groupKey === 'local_backend' || file.groupKey === 'cloud_backend' || file.groupKey === 'scripts_docs' || file.groupKey === 'other') {
      const effect = summarizeBackendEffect(file.groupKey === 'other' ? 'scripts_docs' : file.groupKey);
      addEffectDetail(
        effectMap,
        createEffectDraft(effect.id, effect.title, effect.summary, effect.visibility, effect.scopeLabel, [file.path]),
        effect.detail,
      );
    }
  }
  return finalizeEffectDrafts(Array.from(effectMap.values()));
}

async function runCommand(command: string, args: string[], options: RunCommandOptions = {}): Promise<RunCommandResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: process.env,
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });
    child.on('error', reject);
    child.on('close', (exitCode) => {
      const normalizedExitCode = exitCode ?? 0;
      if (!options.allowNonZero && normalizedExitCode !== 0) {
        reject(new Error((stderr || stdout || `${command} exited with status ${normalizedExitCode}`).trim()));
        return;
      }
      resolve({
        stdout,
        stderr,
        exitCode: normalizedExitCode,
      });
    });
  });
}

async function runGit(repoPath: string, args: string[], options: RunCommandOptions = {}) {
  return runCommand('git', args, {
    cwd: repoPath,
    allowNonZero: options.allowNonZero,
  });
}

async function resolveGitRepoTopLevel(targetPath: string) {
  const stat = await fs.promises.stat(targetPath).catch(() => null);
  if (!stat?.isDirectory()) return null;
  const result = await runCommand('git', ['rev-parse', '--show-toplevel'], {
    cwd: targetPath,
    allowNonZero: true,
  });
  if (result.exitCode !== 0) return null;
  const repoRoot = result.stdout.trim();
  return repoRoot ? normalizeRepoPath(repoRoot) : null;
}

async function listFilesRecursively(targetPath: string): Promise<string[]> {
  const stat = await fs.promises.stat(targetPath).catch(() => null);
  if (!stat) return [];
  if (stat.isFile()) return [targetPath];
  if (!stat.isDirectory()) return [];
  const entries = await fs.promises.readdir(targetPath, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async (entry) => {
    const nextPath = path.join(targetPath, entry.name);
    if (entry.isDirectory()) return listFilesRecursively(nextPath);
    if (entry.isFile()) return [nextPath];
    return [];
  }));
  return nested.flat();
}

async function expandUntrackedDirectoryEntries(repoRoot: string, entries: ParsedStatusEntry[]) {
  const expandedEntries: ParsedStatusEntry[] = [];
  for (const entry of entries) {
    if (entry.type !== 'untracked') {
      expandedEntries.push(entry);
      continue;
    }
    const normalizedPath = entry.path.replace(/\\/g, '/');
    const looksLikeDirectory = normalizedPath.endsWith('/');
    const absolutePath = path.join(repoRoot, normalizedPath.replace(/\/$/, ''));
    const stat = await fs.promises.stat(absolutePath).catch(() => null);
    if (!looksLikeDirectory && !stat?.isDirectory()) {
      expandedEntries.push(entry);
      continue;
    }
    const files = await listFilesRecursively(absolutePath);
    if (!files.length) {
      expandedEntries.push({ ...entry, path: normalizedPath.replace(/\/$/, '') });
      continue;
    }
    for (const filePath of files) {
      expandedEntries.push({
        ...entry,
        path: path.relative(repoRoot, filePath).replace(/\\/g, '/'),
      });
    }
  }
  return expandedEntries;
}

export async function findSuggestedCollabRepoPath(candidates: string[]) {
  const seen = new Set<string>();
  for (const candidate of candidates) {
    if (!candidate) continue;
    const normalized = normalizeRepoPath(candidate);
    if (seen.has(normalized)) continue;
    seen.add(normalized);
    const repoRoot = await resolveGitRepoTopLevel(normalized);
    if (repoRoot) return normalized;
  }
  return null;
}

function createStatusText(
  snapshot: Pick<RepoSnapshot, 'isConfigured' | 'isValid' | 'branch' | 'isMainBranch' | 'hasUnmergedPaths' | 'behindCount' | 'aheadCount' | 'localChangeCount'>,
  suggestedRepoPath?: string | null,
) {
  if (!snapshot.isConfigured) return '先绑定源码目录，按钮才会生效。';
  if (!snapshot.isValid) return '当前目录不是有效 Git 仓库。';
  if (snapshot.hasUnmergedPaths) return '检测到 Git 冲突，请先手工收口。';
  if (!snapshot.isMainBranch) {
    if (suggestedRepoPath) {
      return `当前工作目录在 ${snapshot.branch || '未知'} 分支，系统会改用 main 基线仓库继续。`;
    }
    return `当前分支是 ${snapshot.branch || '未知'}，请先切回 main。`;
  }
  if (snapshot.behindCount > 0 && snapshot.localChangeCount > 0) {
    return `main 落后 ${snapshot.behindCount} 个提交，且本地还有 ${snapshot.localChangeCount} 项改动。`;
  }
  if (snapshot.behindCount > 0) return `main 落后 ${snapshot.behindCount} 个提交，请先同步。`;
  if (snapshot.localChangeCount > 0) return `本地有 ${snapshot.localChangeCount} 项待处理改动。`;
  if (snapshot.aheadCount > 0) return `本地有 ${snapshot.aheadCount} 个已提交未推送变更。`;
  return '当前已与 origin/main 对齐。';
}

async function collectRepoSnapshot(options: RepoOptions): Promise<RepoSnapshot> {
  const repoPath = options.repoPath ? normalizeRepoPath(options.repoPath) : null;
  const suggestedRepoPath = await findSuggestedCollabRepoPath(options.suggestedCandidates);
  if (!repoPath) {
    return {
      repoPath: null,
      repoName: null,
      suggestedRepoPath,
      gitRepoPath: null,
      scopeRelativePath: null,
      isConfigured: false,
      isValid: false,
      branch: null,
      isMainBranch: false,
      aheadCount: 0,
      behindCount: 0,
      hasUnmergedPaths: false,
      localEntries: [],
      remoteEntries: [],
      localBranchEntries: [],
      localChangeCount: 0,
      remoteChangeCount: 0,
      statusText: '先绑定源码目录，按钮才会生效。',
    };
  }
  const repoRoot = await resolveGitRepoTopLevel(repoPath);
  if (!repoRoot) {
    return {
      repoPath,
      repoName: path.basename(repoPath),
      suggestedRepoPath,
      gitRepoPath: null,
      scopeRelativePath: null,
      isConfigured: true,
      isValid: false,
      branch: null,
      isMainBranch: false,
      aheadCount: 0,
      behindCount: 0,
      hasUnmergedPaths: false,
      localEntries: [],
      remoteEntries: [],
      localBranchEntries: [],
      localChangeCount: 0,
      remoteChangeCount: 0,
      statusText: '当前目录不是有效 Git 仓库。',
    };
  }
  const scopeRelativePath = computeScopeRelativePath(repoRoot, repoPath);
  const gitContext = createRepoWorkContext(repoPath, repoRoot, scopeRelativePath);

  await exportSharedSettingsToRepo(repoPath, options.appDbPath);

  if (options.fetchRemote) {
    await runGit(gitContext.gitRepoPath, ['fetch', 'origin'], { allowNonZero: true });
  }

  const scopedGitArgs = scopeRelativePath ? ['--', scopeRelativePath] : [];
  const statusResult = await runGit(gitContext.gitRepoPath, ['status', '--porcelain=v1', '--branch', ...scopedGitArgs]);
  const { branchHeader, parsedEntries } = parseStatusEntries(statusResult.stdout);
  const expandedLocalEntries = await expandUntrackedDirectoryEntries(gitContext.gitRepoPath, parsedEntries);
  const scopedLocalEntries = expandedLocalEntries
    .map((entry) => mapStatusEntryToScope(entry, gitContext.scopeRelativePath))
    .filter((entry): entry is ParsedStatusEntry => Boolean(entry));
  const collabVisibleLocalEntries = scopedLocalEntries.filter((entry) => !isIgnorableLocalStatusPath(entry.path));
  const { branch, aheadCount, behindCount } = parseBranchHeader(branchHeader);
  const remoteDiffResult = await runGit(gitContext.gitRepoPath, ['diff', '--name-status', '--find-renames=50%', 'HEAD..origin/main', ...scopedGitArgs], {
    allowNonZero: true,
  });
  const localBranchDiffResult = await runGit(gitContext.gitRepoPath, ['diff', '--name-status', '--find-renames=50%', 'origin/main...HEAD', ...scopedGitArgs], {
    allowNonZero: true,
  });
  const remoteEntries = parseDiffEntries(remoteDiffResult.stdout)
    .map((entry) => mapDiffEntryToScope(entry, gitContext.scopeRelativePath))
    .filter((entry): entry is ParsedDiffEntry => Boolean(entry));
  const localBranchEntries = parseDiffEntries(localBranchDiffResult.stdout)
    .map((entry) => mapDiffEntryToScope(entry, gitContext.scopeRelativePath))
    .filter((entry): entry is ParsedDiffEntry => Boolean(entry));
  const hasUnmergedPaths = scopedLocalEntries.some((entry) => entry.isUnmerged);
  const snapshotBase = {
    isConfigured: true,
    isValid: true,
    branch,
    isMainBranch: branch === 'main',
    hasUnmergedPaths,
    behindCount,
    aheadCount,
    localChangeCount: collabVisibleLocalEntries.length,
  };
  return {
    repoPath,
    repoName: path.basename(repoPath),
    suggestedRepoPath,
    gitRepoPath: gitContext.gitRepoPath,
    scopeRelativePath: gitContext.scopeRelativePath,
    ...snapshotBase,
    localEntries: collabVisibleLocalEntries,
    remoteEntries,
    localBranchEntries,
    remoteChangeCount: remoteEntries.length,
    statusText: createStatusText(snapshotBase, suggestedRepoPath && suggestedRepoPath !== repoRoot ? suggestedRepoPath : null),
  };
}

function snapshotToStatus(snapshot: RepoSnapshot): CollabRepoStatus {
  return {
    repoPath: snapshot.repoPath,
    repoName: snapshot.repoName,
    suggestedRepoPath: snapshot.suggestedRepoPath,
    workingRepoPath: snapshot.gitRepoPath,
    workingBranch: snapshot.branch,
    workingChangeCount: snapshot.localChangeCount,
    isConfigured: snapshot.isConfigured,
    isValid: snapshot.isValid,
    branch: snapshot.branch,
    isMainBranch: snapshot.isMainBranch,
    hasLocalChanges: snapshot.localChangeCount > 0,
    hasUnmergedPaths: snapshot.hasUnmergedPaths,
    aheadCount: snapshot.aheadCount,
    behindCount: snapshot.behindCount,
    localChangeCount: snapshot.localChangeCount,
    remoteChangeCount: snapshot.remoteChangeCount,
    statusText: snapshot.statusText,
  };
}

function createConflictRisk(kind: CollabConflictRisk['kind'], message: string): CollabConflictRisk {
  return { kind, message };
}

function createLocalFileChanges(snapshot: RepoSnapshot) {
  const remotePaths = new Set<string>();
  const remoteTypeByPath = new Map<string, ParsedDiffEntry['type']>();
  for (const entry of snapshot.remoteEntries) {
    addPathsToSet(remotePaths, entry.path, entry.previousPath);
    remoteTypeByPath.set(entry.path, entry.type);
    if (entry.previousPath) remoteTypeByPath.set(entry.previousPath, entry.type);
  }
  return snapshot.localEntries.map((entry) => {
    const group = classifyChangeGroup(entry.path);
    let risk: CollabConflictRisk | null = null;
    if (entry.isUnmerged) {
      risk = createConflictRisk('unmerged', '这个文件当前已处于 Git 冲突态，需先手工确认。');
    } else if (remotePaths.has(entry.path) || (entry.previousPath && remotePaths.has(entry.previousPath))) {
      const remoteType = remoteTypeByPath.get(entry.path) || (entry.previousPath ? remoteTypeByPath.get(entry.previousPath) : null);
      risk = entry.type === 'deleted' || remoteType === 'deleted'
        ? createConflictRisk('delete_replace', '这个文件在远端 main 也有删除/替换动作，直接推送时很可能互相覆盖。')
        : createConflictRisk('overlap', '这个文件在远端 main 也发生了变化，推送时很可能覆盖对方版本。');
    } else if (entry.type === 'renamed') {
      risk = createConflictRisk('rename', '这个文件涉及重命名，覆盖 main 时要特别留意路径变化。');
    } else if (hasBinaryExtension(entry.path)) {
      risk = createConflictRisk('binary', '这个文件看起来是二进制资源，无法做细粒度合并。');
    }
    return {
      path: entry.path,
      previousPath: entry.previousPath || null,
      type: entry.type,
      groupKey: group.key,
      groupLabel: group.label,
      summary: formatChangeSummary(entry.type, entry.previousPath),
      risk,
    } satisfies CollabFileChange;
  });
}

function createRemoteFileChanges(snapshot: RepoSnapshot) {
  const localChangedPaths = new Set<string>();
  for (const entry of snapshot.localEntries) {
    addPathsToSet(localChangedPaths, entry.path, entry.previousPath);
  }
  for (const entry of snapshot.localBranchEntries) {
    addPathsToSet(localChangedPaths, entry.path, entry.previousPath);
  }
  return snapshot.remoteEntries.map((entry) => {
    const group = classifyChangeGroup(entry.path);
    let risk: CollabConflictRisk | null = null;
    if (entry.type === 'renamed') {
      risk = createConflictRisk('rename', '这个文件在 main 中发生了重命名，覆盖本地时要注意新旧路径。');
    } else if (hasBinaryExtension(entry.path)) {
      risk = createConflictRisk('binary', '这个文件看起来是二进制资源，只能整体覆盖本地版本。');
    } else if (localChangedPaths.has(entry.path) || (entry.previousPath && localChangedPaths.has(entry.previousPath))) {
      risk = entry.type === 'deleted'
        ? createConflictRisk('delete_replace', 'main 准备删除这个文件，但本地也改过它，覆盖时要特别确认。')
        : createConflictRisk('overlap', '这个文件在本地和 main 都发生了变化，同步时很可能互相覆盖。');
    }
    return {
      path: entry.path,
      previousPath: entry.previousPath || null,
      type: entry.type,
      groupKey: group.key,
      groupLabel: group.label,
      summary: formatChangeSummary(entry.type, entry.previousPath),
      risk,
    } satisfies CollabFileChange;
  });
}

async function getCommitSummaries(context: RepoWorkContext) {
  const scopedGitArgs = context.scopeRelativePath ? ['--', context.scopeRelativePath] : [];
  const logResult = await runGit(context.gitRepoPath, ['log', '--format=%h %s', 'HEAD..origin/main', ...scopedGitArgs], { allowNonZero: true });
  return logResult.stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function normalizeSelectedPaths(selectedPaths: string[], allFiles: CollabFileChange[]) {
  const allowedPaths = new Set(allFiles.map((file) => file.path));
  const normalizedSelectedPaths = Array.from(new Set(selectedPaths.map((item) => item.trim()).filter(Boolean)));
  for (const targetPath of normalizedSelectedPaths) {
    if (!allowedPaths.has(targetPath)) {
      throw new Error(`已勾选的文件不在当前预览列表中：${targetPath}`);
    }
  }
  return normalizedSelectedPaths;
}

function collectStatusEntryPaths(entry: ParsedStatusEntry) {
  const paths = [entry.path];
  if (entry.previousPath && entry.previousPath !== entry.path) {
    paths.push(entry.previousPath);
  }
  return paths;
}

async function discardLocalPath(context: RepoWorkContext, file: CollabFileChange) {
  const targetPath = path.join(context.repoPath, file.path);
  if (file.type === 'untracked' || file.type === 'added') {
    await removePathsFromIndex(context, [file.path]);
    await fs.promises.rm(targetPath, { force: true, recursive: true }).catch(() => {
      // Untracked files may already be gone; ignore.
    });
    return;
  }
  if (file.type === 'renamed') {
    await removePathsFromIndex(context, [file.path]);
    await fs.promises.rm(targetPath, { force: true, recursive: true }).catch(() => {
      // Renamed targets may already be gone; ignore.
    });
    if (file.previousPath) {
      await checkoutPathFromRevision(context, 'HEAD', file.previousPath);
    }
    return;
  }
  await checkoutPathFromRevision(context, 'HEAD', file.path);
}

async function discardParsedStatusEntry(context: RepoWorkContext, entry: ParsedStatusEntry) {
  await discardLocalPath(context, {
    path: entry.path,
    previousPath: entry.previousPath || null,
    type: entry.type,
    groupKey: classifyChangeGroup(entry.path).key,
    groupLabel: classifyChangeGroup(entry.path).label,
    summary: formatChangeSummary(entry.type, entry.previousPath),
    risk: null,
  });
}

async function pushPartialStash(context: RepoWorkContext, targetPaths: string[], label: string) {
  if (!targetPaths.length) return false;
  const gitTargetPaths = targetPaths.map((targetPath) => toScopedGitPath(context.scopeRelativePath, targetPath));
  const before = await runGit(context.gitRepoPath, ['stash', 'list'], { allowNonZero: true });
  await runGit(context.gitRepoPath, ['stash', 'push', '-u', '-m', label, '--', ...gitTargetPaths], { allowNonZero: true });
  const after = await runGit(context.gitRepoPath, ['stash', 'list'], { allowNonZero: true });
  return before.stdout !== after.stdout;
}

async function popLatestStash(context: RepoWorkContext) {
  await runGit(context.gitRepoPath, ['stash', 'pop'], { allowNonZero: true });
}

async function addPathsToIndex(context: RepoWorkContext, targetPaths: string[]) {
  const gitTargetPaths = targetPaths.map((targetPath) => toScopedGitPath(context.scopeRelativePath, targetPath));
  await runGit(context.gitRepoPath, ['add', '--sparse', '-A', '--', ...gitTargetPaths]);
}

async function removePathsFromIndex(context: RepoWorkContext, targetPaths: string[]) {
  const gitTargetPaths = targetPaths.map((targetPath) => toScopedGitPath(context.scopeRelativePath, targetPath));
  await runGit(context.gitRepoPath, ['rm', '--sparse', '-f', '--ignore-unmatch', '--', ...gitTargetPaths], { allowNonZero: true });
}

async function checkoutPathFromRevision(context: RepoWorkContext, revision: 'HEAD' | 'origin/main', targetPath: string) {
  await runGit(context.gitRepoPath, ['checkout', '--ignore-skip-worktree-bits', revision, '--', toScopedGitPath(context.scopeRelativePath, targetPath)], { allowNonZero: true });
}

async function checkoutOursPath(context: RepoWorkContext, targetPath: string) {
  await runGit(context.gitRepoPath, ['checkout', '--ignore-skip-worktree-bits', '--ours', '--', toScopedGitPath(context.scopeRelativePath, targetPath)], { allowNonZero: true });
}

async function mergeOriginMainForPush(context: RepoWorkContext, selectedPaths: string[], preview: PushPreview) {
  const selectedSet = new Set(selectedPaths);
  await runGit(context.gitRepoPath, ['merge', '--no-commit', '--no-ff', 'origin/main'], { allowNonZero: true });
  try {
    for (const file of preview.files) {
      if (!selectedSet.has(file.path) || !file.risk) continue;
      if (file.type === 'deleted') {
        await removePathsFromIndex(context, [file.path]);
        continue;
      }
      await checkoutOursPath(context, file.path);
      await addPathsToIndex(context, [file.path]);
      if (file.type === 'renamed' && file.previousPath && file.previousPath !== file.path) {
        await removePathsFromIndex(context, [file.previousPath]);
      }
    }
    const unresolved = await runGit(context.gitRepoPath, ['diff', '--name-only', '--diff-filter=U'], { allowNonZero: true });
    const unresolvedPaths = unresolved.stdout
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (unresolvedPaths.length > 0) {
      throw new Error(`仍有未解决的冲突：${unresolvedPaths.join('、')}`);
    }
    const mergeMessage = 'sync: 合并 origin/main 后继续推送选中的本地修改';
    await runGit(context.gitRepoPath, ['commit', '-m', mergeMessage]);
  } catch (error) {
    await runGit(context.gitRepoPath, ['merge', '--abort'], { allowNonZero: true });
    throw error;
  }
}

export async function getCollabRepoStatus(options: RepoOptions): Promise<CollabRepoStatus> {
  const snapshot = await collectRepoSnapshot(options);
  return snapshotToStatus(snapshot);
}

export async function previewPushToMain(options: RepoOptions): Promise<PushPreview> {
  const snapshot = await collectRepoSnapshot({
    ...options,
    fetchRemote: true,
  });
  const status = snapshotToStatus(snapshot);
  const files = createLocalFileChanges(snapshot);
  const groups = countGroups(files);
  const effects = await buildEffectPreviews('push', snapshot, files);
  let executionBlockReason: string | null = null;
  const notices: string[] = [];
  if (!snapshot.isConfigured) executionBlockReason = '还没有绑定源码目录，先选一个 Git 仓库后再继续。';
  else if (!snapshot.isValid) executionBlockReason = '当前目录不是有效 Git 仓库，请重新绑定源码目录。';
  else if (!snapshot.isMainBranch) executionBlockReason = '当前不在 main 分支，先切回 main 再继续。';
  else if (snapshot.hasUnmergedPaths) executionBlockReason = '检测到 Git 冲突，先手工收口后再执行。';
  else if (!files.length && snapshot.aheadCount === 0) executionBlockReason = '当前没有可提交的本地文件改动。';
  if (!executionBlockReason && snapshot.aheadCount > 0) {
    notices.push(`你本地还有 ${snapshot.aheadCount} 个已提交但未推送的 commit。确认后会和这次勾选的改动一起推到 main。`);
  }
  if (!executionBlockReason && snapshot.behindCount > 0) {
    notices.push(`main 最新版本比你本地多 ${snapshot.behindCount} 个提交。确认后会先把远端 main 合进来，再继续把你勾选的本地修改推上去。`);
  }
  return {
    status,
    suggestedMessage: buildSuggestedMessage('push', groups),
    effects,
    groups,
    files,
    notice: notices.join(' '),
    executionBlockReason,
  };
}

export async function commitAndPushToMain(
  payload: CommitAndPushToMainPayload,
  suggestedCandidates: string[],
  appDbPath?: string | null,
): Promise<CollabActionResult> {
  const preview = await previewPushToMain({
    repoPath: payload.repoPath,
    suggestedCandidates,
    appDbPath,
  });
  if (!preview.status.repoPath) {
    throw new Error('请先绑定源码目录。');
  }
  if (preview.executionBlockReason) {
    throw new Error(preview.executionBlockReason);
  }
  const selectedPaths = normalizeSelectedPaths(payload.selectedPaths, preview.files);
  const message = payload.message.trim();
  if (!message && selectedPaths.length > 0) {
    throw new Error('请填写本次提交说明。');
  }
  const repoPath = preview.status.repoPath;
  const gitRepoPath = preview.status.workingRepoPath || repoPath;
  const scopeRelativePath = computeScopeRelativePath(gitRepoPath, repoPath);
  const context = createRepoWorkContext(repoPath, gitRepoPath, scopeRelativePath);
  const selectedPathSet = new Set(selectedPaths);
  const droppedConflictFiles = preview.files.filter((file) => (
    !selectedPathSet.has(file.path)
    && preview.status.behindCount > 0
    && ['overlap', 'delete_replace'].includes(file.risk?.kind ?? '')
  ));
  const droppedConflictPaths = droppedConflictFiles.map((file) => file.path);
  for (const file of droppedConflictFiles) {
    await discardLocalPath(context, file);
  }
  const unselectedPaths = preview.files
    .map((file) => file.path)
    .filter((targetPath) => !selectedPathSet.has(targetPath) && !droppedConflictPaths.includes(targetPath));
  let hasStashedUnselected = false;
  if (unselectedPaths.length > 0) {
    hasStashedUnselected = await pushPartialStash(context, unselectedPaths, 'codex-collab-unselected-before-push');
  }
  try {
    if (selectedPaths.length === 0) {
      if (preview.status.behindCount > 0) {
        await mergeOriginMainForPush(context, [], preview);
      }
      if (droppedConflictPaths.length > 0) {
        await importSelectedSharedSettingsFromRepo(context.repoPath, appDbPath, droppedConflictPaths);
      }
      if (preview.status.aheadCount > 0) {
        await runGit(context.gitRepoPath, ['push', 'origin', 'main']);
      }
    } else {
      await addPathsToIndex(context, selectedPaths);
      await runGit(context.gitRepoPath, ['commit', '-m', message]);
      if (preview.status.behindCount > 0) {
        await mergeOriginMainForPush(context, selectedPaths, preview);
      }
      if (droppedConflictPaths.length > 0) {
        await importSelectedSharedSettingsFromRepo(context.repoPath, appDbPath, droppedConflictPaths);
      }
      await runGit(context.gitRepoPath, ['push', 'origin', 'main']);
    }
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(selectedPaths.length > 0 ? `提交已生成，但 push 到 main 失败：${detail}` : `同步 main 状态失败：${detail}`);
  } finally {
    if (hasStashedUnselected) {
      await popLatestStash(context).catch(() => {
        // Keep the push result even if local leftover changes fail to pop back cleanly.
      });
    }
  }
  const status = await getCollabRepoStatus({
    repoPath,
    suggestedCandidates,
    appDbPath,
  });
  return {
    status,
    changedPaths: selectedPaths,
    createdCommit: selectedPaths.length > 0,
    commitMessage: selectedPaths.length > 0 ? message : undefined,
  };
}

export async function previewPullFromMain(options: RepoOptions): Promise<PullPreview> {
  const snapshot = await collectRepoSnapshot({
    ...options,
    fetchRemote: true,
  });
  const status = snapshotToStatus(snapshot);
  const files = createRemoteFileChanges(snapshot);
  const groups = countGroups(files);
  const effects = await buildEffectPreviews('pull', snapshot, files);
  let executionBlockReason: string | null = null;
  let notice: string | null = null;
  if (!snapshot.isConfigured) executionBlockReason = '还没有绑定源码目录，先选一个 Git 仓库后再继续。';
  else if (!snapshot.isValid) executionBlockReason = '当前目录不是有效 Git 仓库，请重新绑定源码目录。';
  else if (!snapshot.isMainBranch) executionBlockReason = '当前不在 main 分支，先切回 main 再继续。';
  else if (snapshot.hasUnmergedPaths) executionBlockReason = '检测到 Git 冲突，先手工收口后再执行。';
  else if (!files.length) executionBlockReason = 'main 当前已经是最新。';
  if (!executionBlockReason && snapshot.remoteChangeCount > 0) {
    notice = snapshot.localChangeCount > 0
      ? `main 最新版本里有 ${snapshot.remoteChangeCount} 项可同步变化。你本地还有 ${snapshot.localChangeCount} 项未提交改动，可能覆盖这些改动的文件默认不会勾选。`
      : `main 最新版本里有 ${snapshot.remoteChangeCount} 项可同步变化。你可以先看下面的软件效果，再决定要不要带到本地。`;
  }
  const commitSummaries = snapshot.repoPath && snapshot.gitRepoPath
    ? await getCommitSummaries(createRepoWorkContext(snapshot.repoPath, snapshot.gitRepoPath, snapshot.scopeRelativePath))
    : [];
  return {
    status,
    suggestedMessage: buildSuggestedMessage('pull', groups),
    commitSummaries,
    effects,
    groups,
    files,
    notice,
    executionBlockReason,
  };
}

async function resolvePullChoice(context: RepoWorkContext, file: CollabFileChange, takeRemote: boolean) {
  if (takeRemote) {
    if (file.type === 'deleted') {
      await removePathsFromIndex(context, [file.path]);
      return;
    }
    await checkoutPathFromRevision(context, 'origin/main', file.path);
    if (file.type === 'renamed' && file.previousPath && file.previousPath !== file.path) {
      await removePathsFromIndex(context, [file.previousPath]);
    }
    return;
  }

  if (file.type === 'added') {
    await removePathsFromIndex(context, [file.path]);
    return;
  }
  if (file.type === 'renamed') {
    await removePathsFromIndex(context, [file.path]);
    if (file.previousPath) {
      await checkoutPathFromRevision(context, 'HEAD', file.previousPath);
    }
    return;
  }
  await checkoutPathFromRevision(context, 'HEAD', file.path);
}

export async function pullSelectedFromMain(
  payload: PullSelectedFromMainPayload,
  suggestedCandidates: string[],
  appDbPath?: string | null,
): Promise<CollabActionResult> {
  const preview = await previewPullFromMain({
    repoPath: payload.repoPath,
    suggestedCandidates,
    appDbPath,
  });
  if (!preview.status.repoPath) {
    throw new Error('请先绑定源码目录。');
  }
  if (preview.executionBlockReason) {
    throw new Error(preview.executionBlockReason);
  }
  const selectedPaths = normalizeSelectedPaths(payload.selectedPaths, preview.files);
  const message = payload.message.trim();
  if (!message && selectedPaths.length > 0) {
    throw new Error('请填写本次同步说明。');
  }
  const repoPath = preview.status.repoPath;
  const gitRepoPath = preview.status.workingRepoPath || repoPath;
  const scopeRelativePath = computeScopeRelativePath(gitRepoPath, repoPath);
  const context = createRepoWorkContext(repoPath, gitRepoPath, scopeRelativePath);
  if (selectedPaths.length === 0) {
    const status = await getCollabRepoStatus({
      repoPath,
      suggestedCandidates,
      appDbPath,
    });
    return {
      status,
      changedPaths: [],
      createdCommit: false,
    };
  }
  const snapshot = await collectRepoSnapshot({
    repoPath,
    suggestedCandidates,
    appDbPath,
    fetchRemote: true,
  });
  const selectedSet = new Set(selectedPaths);
  const overwriteLocalEntryPaths = new Set<string>();
  for (const file of preview.files) {
    if (!selectedSet.has(file.path)) continue;
    if (!file.risk || !['overlap', 'delete_replace'].includes(file.risk.kind)) continue;
    for (const entry of snapshot.localEntries) {
      const entryPaths = collectStatusEntryPaths(entry);
      if (entryPaths.includes(file.path) || (file.previousPath && entryPaths.includes(file.previousPath))) {
        collectStatusEntryPaths(entry).forEach((targetPath) => overwriteLocalEntryPaths.add(targetPath));
      }
    }
  }
  const preservedLocalPaths = new Set<string>();
  for (const entry of snapshot.localEntries) {
    for (const targetPath of collectStatusEntryPaths(entry)) {
      if (!overwriteLocalEntryPaths.has(targetPath)) {
        preservedLocalPaths.add(targetPath);
      }
    }
  }
  for (const entry of snapshot.localEntries) {
    const entryPaths = collectStatusEntryPaths(entry);
    if (entryPaths.some((targetPath) => overwriteLocalEntryPaths.has(targetPath))) {
      await discardParsedStatusEntry(context, entry);
    }
  }
  let hasStashedPreservedLocalChanges = false;
  if (preservedLocalPaths.size > 0) {
    hasStashedPreservedLocalChanges = await pushPartialStash(
      context,
      Array.from(preservedLocalPaths),
      'codex-collab-preserved-local-before-pull',
    );
  }
  await runGit(context.gitRepoPath, ['merge', '--no-commit', '--no-ff', 'origin/main'], { allowNonZero: true });
  try {
    for (const file of preview.files) {
      await resolvePullChoice(context, file, selectedPaths.includes(file.path));
    }
    const unresolved = await runGit(context.gitRepoPath, ['diff', '--name-only', '--diff-filter=U'], { allowNonZero: true });
    const unresolvedPaths = unresolved.stdout
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (unresolvedPaths.length > 0) {
      throw new Error(`仍有未解决的冲突：${unresolvedPaths.join('、')}`);
    }
    await importSelectedSharedSettingsFromRepo(context.repoPath, appDbPath, selectedPaths);
    await runGit(context.gitRepoPath, ['commit', '-m', message]);
  } catch (error) {
    await runGit(context.gitRepoPath, ['merge', '--abort'], { allowNonZero: true });
    throw error;
  } finally {
    if (hasStashedPreservedLocalChanges) {
      await popLatestStash(context).catch(() => {
        // Keep the synced result even if preserved local changes need manual attention.
      });
    }
  }

  const status = await getCollabRepoStatus({
    repoPath,
    suggestedCandidates,
    appDbPath,
  });
  return {
    status,
    changedPaths: selectedPaths,
    createdCommit: true,
    commitMessage: message,
  };
}
~~~

## `src/main/main.ts`

- 编码: `utf-8`

~~~typescript
import { writeFileSync, appendFileSync, mkdirSync } from 'node:fs';
try { appendFileSync('/tmp/yiyu-thinktank-electron-bootstrap.log', `[${new Date().toISOString()}] [PROBE] main.ts top-of-file reached\n`); } catch {}
import { app, BrowserWindow, dialog, ipcMain, protocol, shell } from 'electron';
try { appendFileSync('/tmp/yiyu-thinktank-electron-bootstrap.log', `[${new Date().toISOString()}] [PROBE] electron imported OK\n`); } catch {}
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import http from 'node:http';
import net from 'node:net';
import type {
  CommitAndPushToMainPayload,
  PullSelectedFromMainPayload,
} from '../shared/types.js';
import {
  commitAndPushToMain,
  findSuggestedCollabRepoPath,
  getCollabRepoStatus,
  previewPullFromMain,
  previewPushToMain,
  pullSelectedFromMain,
} from './collabGit.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_BACKEND_PORT = 47829;
const DEFAULT_CLOUD_BACKEND_PORT = 47830;
const projectRoot = path.resolve(__dirname, '../..');
const isDev = !app.isPackaged && Boolean(process.env.VITE_DEV_SERVER_URL);
const REQUIRED_BACKEND_FEATURES = ['knowledge.vectorize-answer', 'knowledge.reclass-events', 'chat.general-answer', 'chat.async-status'];
const REQUIRED_BACKEND_SCHEMA_VERSION = 20260420;
const APP_DISPLAY_NAME = '益语智库自用平台';
const APP_BUNDLE_ID = 'com.yiyu.selfworkbench';
const releasePlanPath = path.join(projectRoot, 'docs', 'mac-release-update-plan.md');
const releaseArtifactsPath = path.join(projectRoot, 'dist');
const fixedUserDataPath = path.join(app.getPath('appData'), 'YiyuThinkTankWorkbench');
const runtimeLogsDir = path.join(fixedUserDataPath, 'runtime', 'logs');
const runtimeUiDir = path.join(fixedUserDataPath, 'runtime', 'ui');
const electronLaunchLogPath = path.join(runtimeLogsDir, 'electron-launch.log');
const collabRebuildLogPath = path.join(runtimeLogsDir, 'collab-rebuild.log');
const emergencyBootstrapLogPath = '/tmp/yiyu-thinktank-electron-bootstrap.log';
const savedApplicationStatePath = path.join(app.getPath('home'), 'Library', 'Saved Application State', `${APP_BUNDLE_ID}.savedState`);
app.setName(APP_DISPLAY_NAME);
app.setPath('userData', fixedUserDataPath);
app.setAboutPanelOptions({
  applicationName: APP_DISPLAY_NAME,
  applicationVersion: app.getVersion(),
  version: app.getVersion(),
});

type RuntimeSyncMetadata = {
  fingerprint: string;
  syncedAt: string;
  project: 'backend' | 'cloud_backend';
};

type BackendHealthPayload = {
  featureFlags?: string[];
  backendBuildHash?: string;
  backendSchemaVersion?: number;
  runtimeMode?: 'packaged' | 'dev';
};

let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcessWithoutNullStreams | null = null;
let cloudBackendProcess: ChildProcessWithoutNullStreams | null = null;
let rendererStaticServer: http.Server | null = null;
let rendererProtocolRegistered = false;
let backendPort = DEFAULT_BACKEND_PORT;
let cloudBackendPort = DEFAULT_CLOUD_BACKEND_PORT;
let rendererPort = 4173;
let uvBinaryPath: string | null = null;
let backendRuntimeVenv = '';
let cloudBackendRuntimeVenv = '';
let ownsBackendProcess = false;
let ownsCloudBackendProcess = false;
let backendExitDetail: string | null = null;
let backendRuntimeWarningShown = false;
const backendRecentLogLines: string[] = [];
const LOCAL_DEV_CLOUD_SEED_ENV = {
  YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD: process.env.YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD || 'Admin123!',
  YIYU_CLOUD_GUYUAN_PASSWORD: process.env.YIYU_CLOUD_GUYUAN_PASSWORD || 'Guyuan31',
  YIYU_CLOUD_QINGHUA_PASSWORD: process.env.YIYU_CLOUD_QINGHUA_PASSWORD || 'Qinghua123!',
  YIYU_CLOUD_JIANING_PASSWORD: process.env.YIYU_CLOUD_JIANING_PASSWORD || 'Jianing123!',
  YIYU_CLOUD_YISHUO_PASSWORD: process.env.YIYU_CLOUD_YISHUO_PASSWORD || 'Yishuo123!',
} satisfies NodeJS.ProcessEnv;
const platformDnaExtractorScriptPath = path.join(projectRoot, 'backend', 'scripts', 'extract_platform_dna_text.py');
const legacyAppBasenames = new Set(['益语智库.app', '益语智库工作台.app']);
const DEFAULT_PACKAGED_REMOTE_CLOUD_API_URL = 'http://101.126.34.232';
const DEPRECATED_PACKAGED_REMOTE_CLOUD_API_URLS = new Set(['https://api.yiyu.love', 'http://api.yiyu.love']);
const RENDERER_QUERY_ARG = '--yiyu-renderer-query';

function normalizeHttpUrl(rawUrl?: string | null) {
  const trimmed = rawUrl?.trim();
  if (!trimmed) return null;
  return trimmed.replace(/\/+$/, '');
}

function remoteCloudBackendUrl() {
  const explicitUrl = (
    normalizeHttpUrl(process.env.YIYU_REMOTE_CLOUD_API_URL)
    || normalizeHttpUrl(process.env.YIYU_PACKAGED_REMOTE_CLOUD_API_URL)
  );
  if (!app.isPackaged) {
    return explicitUrl;
  }
  if (explicitUrl && !DEPRECATED_PACKAGED_REMOTE_CLOUD_API_URLS.has(explicitUrl)) {
    return explicitUrl;
  }
  return DEFAULT_PACKAGED_REMOTE_CLOUD_API_URL;
}

function shouldUseRemoteCloudBackend() {
  return Boolean(remoteCloudBackendUrl());
}

function rendererLaunchQuery() {
  const inlineArg = process.argv.find((value) => value.startsWith(`${RENDERER_QUERY_ARG}=`));
  const rawValue = (
    inlineArg?.slice(`${RENDERER_QUERY_ARG}=`.length)
    || (() => {
      const argIndex = process.argv.indexOf(RENDERER_QUERY_ARG);
      return argIndex >= 0 ? process.argv[argIndex + 1] : '';
    })()
    || process.env.YIYU_RENDERER_QUERY
    || ''
  ).trim();
  if (!rawValue) return '';
  const query = rawValue.replace(/^\?+/, '');
  const serialized = new URLSearchParams(query).toString();
  return serialized ? `?${serialized}` : '';
}

function appendElectronLaunchLog(level: 'INFO' | 'ERROR', message: string) {
  try {
    fs.mkdirSync(runtimeLogsDir, { recursive: true });
    const timestamp = new Date().toISOString();
    fs.appendFileSync(electronLaunchLogPath, `[${timestamp}] [${level}] ${message}\n`, 'utf8');
    fs.appendFileSync(emergencyBootstrapLogPath, `[${timestamp}] [${level}] ${message}\n`, 'utf8');
  } catch {
    // Logging should never crash app startup.
  }
}

function writeProcessStreamSafely(stream: NodeJS.WriteStream | undefined, text: string) {
  if (!stream) return;
  if ('destroyed' in stream && stream.destroyed) return;
  if (typeof stream.writable === 'boolean' && !stream.writable) return;
  try {
    stream.write(text);
  } catch {
    // Packaged macOS launches may not have a live stdio sink. Logging must stay non-fatal.
  }
}

function logElectronInfo(message: string) {
  appendElectronLaunchLog('INFO', message);
  writeProcessStreamSafely(process.stdout, `${message}\n`);
}

function logElectronError(message: string) {
  appendElectronLaunchLog('ERROR', message);
  writeProcessStreamSafely(process.stderr, `${message}\n`);
}

function rememberBackendLogLine(line: string) {
  const trimmed = line.trim();
  if (!trimmed) return;
  backendRecentLogLines.push(trimmed);
  if (backendRecentLogLines.length > 40) {
    backendRecentLogLines.splice(0, backendRecentLogLines.length - 40);
  }
}

function getCollabSuggestedCandidates() {
  const visibleWorkspaceRepo = path.join(app.getPath('home'), 'openclaw', 'workspace', 'yiyu-thinktank-workbench');
  const hiddenWorkspaceRepo = path.join(app.getPath('home'), '.openclaw', 'workspace', 'yiyu-thinktank-workbench');
  return [
    visibleWorkspaceRepo,
    hiddenWorkspaceRepo,
    path.join(path.dirname(projectRoot), 'yiyu-thinktank-workbench'),
    path.join(app.getPath('documents'), 'yiyu-thinktank-workbench'),
    path.join(app.getPath('desktop'), 'yiyu-thinktank-workbench'),
  ];
}

function resolveBundlePath(executablePath: string) {
  let current = path.resolve(executablePath);
  while (current !== path.dirname(current)) {
    if (current.endsWith('.app')) return current;
    current = path.dirname(current);
  }
  return executablePath;
}

async function readBundleId(appBundlePath: string) {
  const plistPath = path.join(appBundlePath, 'Contents', 'Info.plist');
  const raw = await fs.promises.readFile(plistPath, 'utf8').catch(() => '');
  const bundleIdMatch = raw.match(/<key>CFBundleIdentifier<\/key>\s*<string>([^<]+)<\/string>/);
  return bundleIdMatch?.[1]?.trim() || '';
}

async function scanApplicationDirectory(baseDir: string) {
  const entries = await fs.promises.readdir(baseDir, { withFileTypes: true }).catch(() => []);
  return entries
    .filter((entry) => entry.isDirectory() && entry.name.endsWith('.app'))
    .map((entry) => path.join(baseDir, entry.name));
}

async function collectInstalledAppPaths(currentAppBundlePath: string) {
  const candidates = new Set<string>();
  const userApplications = path.join(app.getPath('home'), 'Applications');
  const scanDirs = [
    '/Applications',
    userApplications,
    path.join(fixedUserDataPath, 'runtime', 'local-electron'),
    path.join(fixedUserDataPath, 'runtime', 'local-electron-dist'),
  ];
  for (const baseDir of scanDirs) {
    const found = await scanApplicationDirectory(baseDir);
    for (const targetPath of found) {
      const baseName = path.basename(targetPath);
      if (!baseName.includes('益语智库')) continue;
      candidates.add(targetPath);
    }
  }
  candidates.add(currentAppBundlePath);
  return Array.from(candidates).sort((left, right) => left.localeCompare(right, 'zh-Hans-CN'));
}

protocol.registerSchemesAsPrivileged([
  {
    scheme: 'app',
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
      stream: true,
    },
  },
]);

async function runTaskWindowDiagnostics(window: BrowserWindow) {
  if (!parseBooleanEnv(process.env.YIYU_ELECTRON_TASK_DIAGNOSTICS, false)) return;

  const inspectEvidenceQuery = async () => window.webContents.executeJavaScript(`
    (() => {
      const params = new URLSearchParams(window.location.search);
      const evidenceMode = params.get('evidenceMode');
      if (!evidenceMode) return null;
      const bodyText = document.body?.innerText || '';
      return {
        tab: params.get('tab') || params.get('activeTab') || '',
        evidenceMode,
        taskId: params.get('taskId') || '',
        clientId: params.get('clientId') || '',
        hasRcEvidenceLabel: bodyText.includes('RC Evidence'),
        bodySnippet: bodyText.slice(0, 600),
      };
    })()
  `, true);

  const inspectTargets = async () => window.webContents.executeJavaScript(`
    (() => {
      const findButton = (label) => Array.from(document.querySelectorAll('button'))
        .find((button) => (button.textContent || '').replace(/\\s+/g, '').includes(label.replace(/\\s+/g, '')));
      const findNavButton = (label) => Array.from(document.querySelectorAll('button'))
        .find((button) => (button.textContent || '').replace(/\\s+/g, '').includes(label.replace(/\\s+/g, '')));
      const summarize = (label) => {
        const button = findButton(label);
        if (!button) return { label, found: false };
        const rect = button.getBoundingClientRect();
        const style = window.getComputedStyle(button);
        const centerX = Math.round(rect.left + rect.width / 2);
        const centerY = Math.round(rect.top + rect.height / 2);
        const hitTarget = document.elementFromPoint(centerX, centerY);
        return {
          label,
          found: true,
          centerX,
          centerY,
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          pointerEvents: style.pointerEvents,
          text: (button.textContent || '').trim(),
          hitTargetTag: hitTarget?.tagName || null,
          hitTargetText: (hitTarget?.textContent || '').trim().slice(0, 40),
          hitTargetClass: typeof hitTarget?.className === 'string' ? hitTarget.className.slice(0, 120) : null,
        };
      };

      return {
        heading: document.querySelector('h1')?.textContent || '',
        bodyIncludesToday: document.body.innerText.includes('今天'),
        navTaskButton: (() => {
          const button = findNavButton('任务与日程');
          if (!button) return { found: false };
          const rect = button.getBoundingClientRect();
          return {
            found: true,
            centerX: Math.round(rect.left + rect.width / 2),
            centerY: Math.round(rect.top + rect.height / 2),
            text: (button.textContent || '').trim(),
          };
        })(),
        targets: [
          summarize('我的月历'),
          summarize('任务列表'),
          summarize('新建任务'),
        ],
      };
    })()
  `, true);

  const clickAt = async (x: number, y: number) => {
    window.webContents.sendInputEvent({ type: 'mouseMove', x, y });
    window.webContents.sendInputEvent({ type: 'mouseDown', x, y, button: 'left', clickCount: 1 });
    window.webContents.sendInputEvent({ type: 'mouseUp', x, y, button: 'left', clickCount: 1 });
    await new Promise((resolve) => setTimeout(resolve, 250));
  };

  try {
    const evidenceQuery = await inspectEvidenceQuery() as null | {
      tab: string;
      evidenceMode: string;
      taskId: string;
      clientId: string;
      hasRcEvidenceLabel: boolean;
      bodySnippet: string;
    };
    if (evidenceQuery) {
      logElectronInfo(`[renderer:task-diagnostics] evidence=${JSON.stringify(evidenceQuery)}`);
      return;
    }

    const before = await inspectTargets() as {
      heading: string;
      bodyIncludesToday: boolean;
      navTaskButton: { found: boolean; centerX?: number; centerY?: number; text?: string };
      targets: Array<{ label: string; found: boolean; centerX?: number; centerY?: number; pointerEvents?: string }>;
    };
    logElectronInfo(`[renderer:task-diagnostics] before=${JSON.stringify(before)}`);

    const navTaskButton = before.navTaskButton && before.navTaskButton.found && before.navTaskButton.centerX !== undefined && before.navTaskButton.centerY !== undefined
      ? before.navTaskButton
      : null;
    if (navTaskButton && navTaskButton.centerX !== undefined && navTaskButton.centerY !== undefined) {
      await clickAt(navTaskButton.centerX, navTaskButton.centerY);
    }

    const onTasksPage = await inspectTargets() as {
      heading: string;
      bodyIncludesToday: boolean;
      targets: Array<{ label: string; found: boolean; centerX?: number; centerY?: number; pointerEvents?: string }>;
    };
    logElectronInfo(`[renderer:task-diagnostics] onTasksPage=${JSON.stringify(onTasksPage)}`);

    const calendarTarget = onTasksPage.targets.find((item) => item.label === '我的月历' && item.found && item.centerX !== undefined && item.centerY !== undefined);
    if (calendarTarget && calendarTarget.centerX !== undefined && calendarTarget.centerY !== undefined) {
      await clickAt(calendarTarget.centerX, calendarTarget.centerY);
    }

    const afterCalendar = await window.webContents.executeJavaScript(`
      (() => ({
        bodyIncludesToday: document.body.innerText.includes('今天'),
        bodyIncludesMonthTitle: document.body.innerText.includes('我的月历'),
      }))()
    `, true);
    logElectronInfo(`[renderer:task-diagnostics] afterCalendar=${JSON.stringify(afterCalendar)}`);

    const listTargetPayload = await inspectTargets() as {
      targets: Array<{ label: string; found: boolean; centerX?: number; centerY?: number }>;
    };
    const listTarget = listTargetPayload.targets.find((item) => item.label === '任务列表' && item.found && item.centerX !== undefined && item.centerY !== undefined);
    if (listTarget && listTarget.centerX !== undefined && listTarget.centerY !== undefined) {
      await clickAt(listTarget.centerX, listTarget.centerY);
    }

    const createTargetPayload = await inspectTargets() as {
      targets: Array<{ label: string; found: boolean; centerX?: number; centerY?: number }>;
    };
    const createTarget = createTargetPayload.targets.find((item) => item.label === '新建任务' && item.found && item.centerX !== undefined && item.centerY !== undefined);
    if (createTarget && createTarget.centerX !== undefined && createTarget.centerY !== undefined) {
      await clickAt(createTarget.centerX, createTarget.centerY);
    }

    const afterCreate = await window.webContents.executeJavaScript(`
      (() => {
        const titleInput = Array.from(document.querySelectorAll('input'))
          .find((node) => (node.getAttribute('placeholder') || '').includes('任务标题'));
        const saveButton = Array.from(document.querySelectorAll('button'))
          .find((button) => (button.textContent || '').trim() === '保存任务');
        const cancelButton = Array.from(document.querySelectorAll('button'))
          .find((button) => (button.textContent || '').trim() === '取消');
        if (cancelButton) cancelButton.click();
        return {
          modalTitleInputFound: Boolean(titleInput),
          saveButtonFound: Boolean(saveButton),
          bodyIncludesTaskTitle: document.body.innerText.includes('任务标题'),
        };
      })()
    `, true);
    logElectronInfo(`[renderer:task-diagnostics] afterCreate=${JSON.stringify(afterCreate)}`);
  } catch (error) {
    logElectronError(`[renderer:task-diagnostics] failed=${error instanceof Error ? error.message : String(error)}`);
  }
}

async function runEventLineCreateDiagnostics(window: BrowserWindow) {
  if (!parseBooleanEnv(process.env.YIYU_ELECTRON_EVENT_LINE_DIAGNOSTICS, false)) return;

  const sleep = async (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
  const clickText = async (selector: string, label: string) =>
    window.webContents.executeJavaScript(
      `
        (() => {
          const nodes = Array.from(document.querySelectorAll(${JSON.stringify(selector)}));
          const target = nodes.find((node) => ((node.textContent || '').replace(/\\s+/g, '')).includes(${JSON.stringify(label.replace(/\s+/g, ''))}));
          if (!target) return { found: false };
          target.scrollIntoView({ block: 'center', inline: 'center' });
          target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
          return { found: true, text: (target.textContent || '').trim().slice(0, 80) };
        })()
      `,
      true,
    );
  const inspectState = async (tag: string) =>
    window.webContents.executeJavaScript(
      `
        (() => {
          const bodyText = document.body?.innerText || '';
          const heading = document.querySelector('h1')?.textContent || '';
          const modalHeading = Array.from(document.querySelectorAll('h3')).map((node) => (node.textContent || '').trim()).find(Boolean) || '';
          const eventLineButton = Array.from(document.querySelectorAll('button')).find((node) => ((node.textContent || '').replace(/\\s+/g, '')).includes('从当前任务新建'));
          const boundaryFlag = bodyText.includes('桌面界面启动失败') || bodyText.includes('Renderer Startup Failed');
          const bootEvents = Array.isArray(window.__YIYU_BOOT_EVENTS__) ? window.__YIYU_BOOT_EVENTS__ : [];
          return {
            tag: ${JSON.stringify(tag)},
            heading,
            modalHeading,
            hasEventLineCreateButton: Boolean(eventLineButton),
            eventLineCreateText: (eventLineButton?.textContent || '').trim(),
            bodySnippet: bodyText.slice(0, 800),
            boundaryFlag,
            bootEvents,
          };
        })()
      `,
      true,
    );

  try {
    await sleep(1200);
    logElectronInfo(`[renderer:event-line-diagnostics] start=${JSON.stringify(await inspectState('start'))}`);
    logElectronInfo(`[renderer:event-line-diagnostics] nav-task=${JSON.stringify(await clickText('button', '任务与日程'))}`);
    await sleep(500);
    logElectronInfo(`[renderer:event-line-diagnostics] list-mode=${JSON.stringify(await clickText('button', '任务列表'))}`);
    await sleep(500);
    const openTaskResult = await window.webContents.executeJavaScript(
      `
        (() => {
          const editButtons = Array.from(document.querySelectorAll('button')).filter((node) => ((node.textContent || '').replace(/\\s+/g, '')).includes('编辑'));
          const editButton = editButtons.find((node) => {
            const rect = node.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
          }) || editButtons[0];
          if (!editButton) return { found: false, reason: 'no-edit-button' };
          editButton.scrollIntoView({ block: 'center', inline: 'center' });
          editButton.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
          const cardText = editButton.closest('div')?.textContent || '';
          return { found: true, taskSnippet: cardText.slice(0, 160), actionText: (editButton.textContent || '').trim(), buttonCount: editButtons.length };
        })()
      `,
      true,
    );
    logElectronInfo(`[renderer:event-line-diagnostics] open-task=${JSON.stringify(openTaskResult)}`);
    await sleep(700);
    logElectronInfo(`[renderer:event-line-diagnostics] before-click=${JSON.stringify(await inspectState('before-click'))}`);
    logElectronInfo(`[renderer:event-line-diagnostics] click-create=${JSON.stringify(await clickText('button', '从当前任务新建'))}`);
    await sleep(1400);
    logElectronInfo(`[renderer:event-line-diagnostics] after-click=${JSON.stringify(await inspectState('after-click'))}`);
  } catch (error) {
    logElectronError(`[renderer:event-line-diagnostics] failed=${error instanceof Error ? error.message : String(error)}`);
  }
}

function parseBooleanEnv(value: string | undefined, fallback = false) {
  if (!value) return fallback;
  return ['1', 'true', 'yes', 'on'].includes(value.toLowerCase());
}

function quoteShellArg(value: string) {
  return `"${value.replace(/(["\\$`])/g, '\\$1')}"`;
}


function isExecutable(filePath: string) {
  try {
    fs.accessSync(filePath, fs.constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

function resolveUvBinary() {
  const searchDirs = new Set<string>();
  for (const item of (process.env.PATH ?? '').split(path.delimiter)) {
    if (item) {
      searchDirs.add(item);
    }
  }
  const homeDir = process.env.HOME;
  if (homeDir) {
    searchDirs.add(path.join(homeDir, '.local/bin'));
    searchDirs.add(path.join(homeDir, '.cargo/bin'));
  }
  searchDirs.add('/opt/homebrew/bin');
  searchDirs.add('/usr/local/bin');

  for (const directory of searchDirs) {
    const candidate = path.join(directory, 'uv');
    if (isExecutable(candidate)) {
      return candidate;
    }
  }
  return null;
}

function backendEnv(extraEnv: NodeJS.ProcessEnv = {}) {
  const env = { ...process.env, ...extraEnv };
  const pathEntries = new Set<string>((env.PATH ?? '').split(path.delimiter).filter(Boolean));
  if (uvBinaryPath) {
    pathEntries.add(path.dirname(uvBinaryPath));
  }
  if (env.VIRTUAL_ENV) {
    pathEntries.add(path.join(env.VIRTUAL_ENV, 'bin'));
  }
  env.PATH = Array.from(pathEntries).join(path.delimiter);
  env.YIYU_CLOUD_API_URL = cloudBackendUrl();
  env.YIYU_WORKBENCH_DATA_DIR = fixedUserDataPath;
  env.PYTHONDONTWRITEBYTECODE = '1';
  env.PYTHONPYCACHEPREFIX = path.join(fixedUserDataPath, 'runtime', 'pycache');
  return env;
}

function runtimePythonPath(venvPath: string) {
  return path.join(venvPath, 'bin', 'python');
}

async function runCommand(command: string, args: string[], env: NodeJS.ProcessEnv, label: string) {
  await new Promise<void>((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: projectRoot,
      env,
    });

    logBackend(child.stdout, `${label}:stdout`);
    logBackend(child.stderr, `${label}:stderr`);

    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`${label} exited with code ${code ?? 'unknown'}`));
    });
  });
}

async function runJsonCommand(command: string, args: string[], env: NodeJS.ProcessEnv, label: string) {
  return new Promise<Record<string, unknown>>((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: projectRoot,
      env,
    });

    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });
    child.on('error', reject);
    child.on('exit', (code) => {
      const trimmed = stdout.trim();
      if (code !== 0) {
        reject(new Error(stderr.trim() || trimmed || `${label} exited with code ${code ?? 'unknown'}`));
        return;
      }
      try {
        resolve((trimmed ? JSON.parse(trimmed) : {}) as Record<string, unknown>);
      } catch {
        reject(new Error(`${label} returned invalid json`));
      }
    });
  });
}

function getBackendPythonPath() {
  if (backendRuntimeVenv && isExecutable(path.join(backendRuntimeVenv, 'bin', 'python'))) {
    return path.join(backendRuntimeVenv, 'bin', 'python');
  }
  const fallback = path.join(projectRoot, 'backend', '.venv', 'bin', 'python');
  return fallback;
}

function projectRuntimeMetadataPath(projectDirName: 'backend' | 'cloud_backend', venvPath: string) {
  return path.join(venvPath, `.yiyu-${projectDirName}-runtime.json`);
}

function readRuntimeSyncMetadata(metadataPath: string): RuntimeSyncMetadata | null {
  try {
    const raw = fs.readFileSync(metadataPath, 'utf-8');
    const parsed = JSON.parse(raw) as Partial<RuntimeSyncMetadata>;
    if (
      typeof parsed.fingerprint === 'string' &&
      typeof parsed.syncedAt === 'string' &&
      (parsed.project === 'backend' || parsed.project === 'cloud_backend')
    ) {
      return parsed as RuntimeSyncMetadata;
    }
  } catch {
    // Ignore malformed or missing metadata and force a fresh sync.
  }
  return null;
}

function writeRuntimeSyncMetadata(metadataPath: string, metadata: RuntimeSyncMetadata) {
  fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2), 'utf-8');
}

function buildRuntimeFingerprint(projectDirName: 'backend' | 'cloud_backend') {
  const targetFiles = ['pyproject.toml', 'uv.lock'];
  return targetFiles.map((fileName) => {
    const targetPath = path.join(projectRoot, projectDirName, fileName);
    const stat = fs.statSync(targetPath);
    return `${fileName}:${stat.size}:${Math.trunc(stat.mtimeMs)}`;
  }).join('|');
}

function evaluateBackendRuntimeWarning(payload: BackendHealthPayload): string | null {
  const schemaVersion = Number(payload.backendSchemaVersion || 0);
  if (schemaVersion > 0 && schemaVersion < REQUIRED_BACKEND_SCHEMA_VERSION) {
    return `后端 schema 版本过低：${schemaVersion} < ${REQUIRED_BACKEND_SCHEMA_VERSION}`;
  }
  const expectedBuildHash = buildRuntimeFingerprint('backend');
  const runtimeBuildHash = typeof payload.backendBuildHash === 'string' ? payload.backendBuildHash : '';
  if (runtimeBuildHash && runtimeBuildHash !== expectedBuildHash) {
    return `后端 build hash 与当前包不一致。\nexpected=${expectedBuildHash}\nactual=${runtimeBuildHash}`;
  }
  if (app.isPackaged && payload.runtimeMode && payload.runtimeMode !== 'packaged') {
    return `后端运行模式异常：当前为打包环境，但 runtimeMode=${payload.runtimeMode}`;
  }
  if (!app.isPackaged && payload.runtimeMode && payload.runtimeMode !== 'dev') {
    return `后端运行模式异常：当前为开发环境，但 runtimeMode=${payload.runtimeMode}`;
  }
  return null;
}

async function extractPlatformDnaText(targetPath: string) {
  const pythonPath = getBackendPythonPath();
  if (!isExecutable(pythonPath)) {
    throw new Error('后端 Python 环境不可用，暂时无法读取 docx/pdf。');
  }
  if (!fs.existsSync(platformDnaExtractorScriptPath)) {
    throw new Error('平台 DNA 抽取脚本不存在。');
  }
  const payload = await runJsonCommand(
    pythonPath,
    [platformDnaExtractorScriptPath, targetPath],
    backendEnv({ VIRTUAL_ENV: path.dirname(path.dirname(pythonPath)) }),
    'platform-dna:extract',
  );
  if (!payload.success) {
    throw new Error(typeof payload.error === 'string' ? payload.error : '平台 DNA 文档解析失败');
  }
  return typeof payload.text === 'string' ? payload.text : '';
}

async function ensureProjectRuntime(projectDirName: 'backend' | 'cloud_backend', venvPath: string) {
  if (!uvBinaryPath) {
    throw new Error('missing_uv_binary');
  }
  fs.mkdirSync(path.dirname(venvPath), { recursive: true });
  const pythonPath = path.join(venvPath, 'bin', 'python');
  const uvicornPath = path.join(venvPath, 'bin', 'uvicorn');
  const metadataPath = projectRuntimeMetadataPath(projectDirName, venvPath);
  const fingerprint = buildRuntimeFingerprint(projectDirName);
  const forceSync = parseBooleanEnv(process.env.YIYU_FORCE_RUNTIME_SYNC, false);
  if (!isExecutable(pythonPath)) {
    await runCommand(uvBinaryPath, ['venv', venvPath, '--python', '3.11'], backendEnv(), `${projectDirName}:venv`);
  }
  const existingMetadata = readRuntimeSyncMetadata(metadataPath);
  const shouldSync = forceSync || !isExecutable(uvicornPath) || existingMetadata?.fingerprint !== fingerprint;
  if (!shouldSync) {
    return;
  }
  await runCommand(
    uvBinaryPath,
    ['sync', '--project', path.join(projectRoot, projectDirName), '--active', '--locked'],
    backendEnv({ VIRTUAL_ENV: venvPath }),
    `${projectDirName}:sync`,
  );
  writeRuntimeSyncMetadata(metadataPath, {
    fingerprint,
    syncedAt: new Date().toISOString(),
    project: projectDirName,
  });
}

function backendUrl() {
  return `http://127.0.0.1:${backendPort}`;
}

function cloudBackendUrl() {
  return remoteCloudBackendUrl() || `http://127.0.0.1:${cloudBackendPort}`;
}

function rendererUrl() {
  return `http://127.0.0.1:${rendererPort}${rendererLaunchQuery()}`;
}

function rendererProtocolUrl() {
  return `app://renderer/index.html${rendererLaunchQuery()}`;
}

function writeRendererDiagnosticPage(fileName: string, html: string) {
  fs.mkdirSync(runtimeUiDir, { recursive: true });
  const filePath = path.join(runtimeUiDir, fileName);
  fs.writeFileSync(filePath, html, 'utf8');
  return pathToFileURL(filePath).href;
}

function rendererBootstrapPageUrl(detail = '正在连接本地界面与后台服务，请稍候…') {
  return writeRendererDiagnosticPage('__bootstrap__.html', buildRendererBootstrapPage(detail));
}

function rendererFailurePageUrl(detail: string) {
  return writeRendererDiagnosticPage('__renderer_failure__.html', buildRendererFailurePage(detail));
}

async function registerRendererProtocol() {
  if (rendererProtocolRegistered) return;
  const rendererRoot = path.join(projectRoot, 'dist/renderer');
  protocol.handle('app', async (request) => {
    const requestUrl = new URL(request.url);
    if (requestUrl.pathname === '/__bootstrap__.html') {
      const detail = requestUrl.searchParams.get('detail') || '正在连接本地界面与后台服务，请稍候…';
      return new Response(Buffer.from(buildRendererBootstrapPage(detail)), {
        headers: {
          'Content-Type': 'text/html; charset=utf-8',
          'Cache-Control': 'no-store',
        },
      });
    }
    if (requestUrl.pathname === '/__renderer_failure__.html') {
      const detail = requestUrl.searchParams.get('detail') || '渲染界面启动失败。';
      return new Response(Buffer.from(buildRendererFailurePage(detail)), {
        headers: {
          'Content-Type': 'text/html; charset=utf-8',
          'Cache-Control': 'no-store',
        },
      });
    }
    const normalizedPath = requestUrl.pathname === '/' ? '/index.html' : requestUrl.pathname;
    const candidatePath = path.resolve(rendererRoot, `.${normalizedPath}`);
    const safePath = candidatePath.startsWith(rendererRoot) && fs.existsSync(candidatePath) && fs.statSync(candidatePath).isFile()
      ? candidatePath
      : path.join(rendererRoot, 'index.html');
    const buffer = await fs.promises.readFile(safePath);
    return new Response(buffer, {
      headers: {
        'Content-Type': rendererContentType(safePath),
        'Cache-Control': 'no-store',
      },
    });
  });
  rendererProtocolRegistered = true;
}

async function checkBackendHealthAt(port: number, requiredFeatures: string[]): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${port}/api/v1/system/health`, (res) => {
      if ((res.statusCode ?? 500) >= 500) {
        res.resume();
        resolve(false);
        return;
      }
      const chunks: Buffer[] = [];
      res.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
      res.on('end', () => {
        try {
          const payload = JSON.parse(Buffer.concat(chunks).toString('utf-8')) as BackendHealthPayload;
          const featureFlags = Array.isArray(payload.featureFlags) ? payload.featureFlags : [];
          const missing = requiredFeatures.filter((feature) => !featureFlags.includes(feature));
          resolve(missing.length === 0);
        } catch {
          resolve(false);
        }
      });
    });
    req.on('error', () => resolve(false));
    req.setTimeout(800, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function checkCloudBackendHealthAt(port: number): Promise<boolean> {
  return checkCloudBackendHealth(`http://127.0.0.1:${port}`);
}

async function checkCloudBackendHealth(targetUrl: string): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(`${targetUrl.replace(/\/+$/, '')}/health`, (res) => {
      res.resume();
      resolve((res.statusCode ?? 500) < 500);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(800, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function isPortAvailable(port: number): Promise<boolean> {
  await new Promise((resolve) => setTimeout(resolve, 10));
  return new Promise((resolve) => {
    const server = net.createServer();
    server.unref();
    server.on('error', () => resolve(false));
    server.listen(port, '127.0.0.1', () => {
      server.close(() => resolve(true));
    });
  });
}

async function reservePort(preferredPort: number, reservedPorts = new Set<number>()): Promise<number> {
  if (!reservedPorts.has(preferredPort) && await isPortAvailable(preferredPort)) {
    return preferredPort;
  }
  for (let offset = 1; offset <= 30; offset += 1) {
    const candidate = preferredPort + offset;
    if (!reservedPorts.has(candidate) && await isPortAvailable(candidate)) {
      return candidate;
    }
  }
  throw new Error(`无法为本地服务找到可用端口，起始端口=${preferredPort}`);
}

async function terminateManagedRuntimeProcess(venvPath: string) {
  const runtimePython = runtimePythonPath(venvPath);
  if (!fs.existsSync(runtimePython)) return;
  await new Promise<void>((resolve) => {
    const child = spawn('pkill', ['-f', `${runtimePython} -m uvicorn app.main:app`], {
      env: backendEnv({ VIRTUAL_ENV: venvPath }),
    });
    child.on('error', () => resolve());
    child.on('exit', () => resolve());
  });
}

async function recyclePackagedRuntimeProcesses() {
  if (!app.isPackaged) return;
  await terminateManagedRuntimeProcess(backendRuntimeVenv);
  await terminateManagedRuntimeProcess(cloudBackendRuntimeVenv);
}

function purgeSavedApplicationState() {
  try {
    fs.rmSync(savedApplicationStatePath, { recursive: true, force: true });
  } catch {
    // Ignore saved-state cleanup errors; they should not block startup.
  }
}

function logBackend(pipe: NodeJS.ReadableStream, label: string, onLine?: (line: string) => void) {
  pipe.on('data', (chunk) => {
    const text = chunk.toString();
    writeProcessStreamSafely(process.stdout, `[backend:${label}] ${text}`);
    for (const line of text.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      appendElectronLaunchLog('INFO', `[backend:${label}] ${trimmed}`);
      if (onLine) {
        onLine(trimmed);
      }
    }
  });
}

function startBackend() {
  if (backendProcess) return;
  const entrypoint = runtimePythonPath(backendRuntimeVenv);
  if (!isExecutable(entrypoint)) {
    throw new Error('missing_backend_runtime');
  }
  const args = ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(backendPort)];
  backendProcess = spawn(
    entrypoint,
    args,
    {
      cwd: path.join(projectRoot, 'backend'),
      env: backendEnv({ VIRTUAL_ENV: backendRuntimeVenv }),
    },
  );
  ownsBackendProcess = true;
  backendExitDetail = null;
  backendRecentLogLines.length = 0;

  logBackend(backendProcess.stdout, 'stdout', rememberBackendLogLine);
  logBackend(backendProcess.stderr, 'stderr', rememberBackendLogLine);
  backendProcess.on('error', (error) => {
    backendExitDetail = `后端子进程启动失败：${error.message}`;
    logElectronError(`后端服务启动失败: ${error.message}`);
  });

  backendProcess.on('exit', (code) => {
    backendExitDetail = `后端服务已退出，退出码=${code ?? 'unknown'}`;
    backendProcess = null;
    ownsBackendProcess = false;
    logElectronError(`后端服务已退出，退出码=${code ?? 'unknown'}`);
  });
}

function startCloudBackend() {
  if (cloudBackendProcess) return;
  const entrypoint = runtimePythonPath(cloudBackendRuntimeVenv);
  if (!isExecutable(entrypoint)) {
    throw new Error('missing_cloud_backend_runtime');
  }
  const args = ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(cloudBackendPort)];
  cloudBackendProcess = spawn(
    entrypoint,
    args,
    {
      cwd: path.join(projectRoot, 'cloud_backend'),
      env: backendEnv({
        VIRTUAL_ENV: cloudBackendRuntimeVenv,
        ...LOCAL_DEV_CLOUD_SEED_ENV,
      }),
    },
  );
  ownsCloudBackendProcess = true;

  logBackend(cloudBackendProcess.stdout, 'cloud:stdout');
  logBackend(cloudBackendProcess.stderr, 'cloud:stderr');
  cloudBackendProcess.on('error', (error) => {
    logElectronError(`中心后端启动失败: ${error.message}`);
  });

  cloudBackendProcess.on('exit', (code) => {
    cloudBackendProcess = null;
    ownsCloudBackendProcess = false;
    logElectronError(`中心后端已退出，退出码=${code ?? 'unknown'}`);
  });
}

function stopBackend() {
  if (!backendProcess || !ownsBackendProcess) return;
  backendProcess.kill('SIGTERM');
  backendProcess = null;
  ownsBackendProcess = false;
}

function stopCloudBackend() {
  if (!cloudBackendProcess || !ownsCloudBackendProcess) return;
  cloudBackendProcess.kill('SIGTERM');
  cloudBackendProcess = null;
  ownsCloudBackendProcess = false;
}

function rendererContentType(filePath: string) {
  const ext = path.extname(filePath).toLowerCase();
  switch (ext) {
    case '.html':
      return 'text/html; charset=utf-8';
    case '.js':
      return 'text/javascript; charset=utf-8';
    case '.css':
      return 'text/css; charset=utf-8';
    case '.json':
      return 'application/json; charset=utf-8';
    case '.svg':
      return 'image/svg+xml';
    case '.png':
      return 'image/png';
    case '.jpg':
    case '.jpeg':
      return 'image/jpeg';
    case '.ico':
      return 'image/x-icon';
    default:
      return 'application/octet-stream';
  }
}

async function startRendererStaticServer() {
  if (rendererStaticServer) return;
  const rendererRoot = path.join(projectRoot, 'dist/renderer');
  logElectronInfo(`[renderer:http] preparing static server root=${rendererRoot}`);
  rendererPort = await reservePort(4173, new Set([backendPort, cloudBackendPort]));
  logElectronInfo(`[renderer:http] reserved port=${rendererPort}`);
  rendererStaticServer = http.createServer((req, res) => {
    const requestUrl = req.url || '/';
    const pathname = decodeURIComponent(requestUrl.split('?')[0] || '/');
    const normalizedPath = pathname === '/' ? '/index.html' : pathname;
    const candidatePath = path.resolve(rendererRoot, `.${normalizedPath}`);
    const safePath = candidatePath.startsWith(rendererRoot) ? candidatePath : path.join(rendererRoot, 'index.html');
    const filePath = fs.existsSync(safePath) && fs.statSync(safePath).isFile() ? safePath : path.join(rendererRoot, 'index.html');

    fs.readFile(filePath, (error, buffer) => {
      if (error) {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Not found');
        return;
      }
      res.writeHead(200, {
        'Content-Type': rendererContentType(filePath),
        'Cache-Control': 'no-store',
      });
      res.end(buffer);
    });
  });

  await new Promise<void>((resolve, reject) => {
    if (!rendererStaticServer) {
      reject(new Error('renderer_static_server_missing'));
      return;
    }
    rendererStaticServer.once('error', reject);
    rendererStaticServer.listen(rendererPort, '127.0.0.1', () => resolve());
  });
  logElectronInfo(`[renderer:http] listening on http://127.0.0.1:${rendererPort}`);
}

function stopRendererStaticServer() {
  if (!rendererStaticServer) return;
  rendererStaticServer.close();
  rendererStaticServer = null;
}

function buildRendererFailurePage(detail: string) {
  const message = detail.replace(/[&<>"]/g, (char) => {
    switch (char) {
      case '&':
        return '&amp;';
      case '<':
        return '&lt;';
      case '>':
        return '&gt;';
      case '"':
        return '&quot;';
      default:
        return char;
    }
  });
  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${APP_DISPLAY_NAME}</title>
    <style>
      :root { color-scheme: light; }
      body {
        margin: 0;
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #eef3ff;
        font-family: "PingFang SC", "SF Pro Display", "Helvetica Neue", sans-serif;
        color: #1f2937;
      }
      .panel {
        width: min(560px, calc(100vw - 48px));
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid #dbe5ff;
        border-radius: 24px;
        box-shadow: 0 16px 48px rgba(91, 123, 254, 0.12);
        padding: 28px;
      }
      h1 {
        margin: 0 0 10px;
        font-size: 20px;
        line-height: 1.3;
      }
      p {
        margin: 0;
        font-size: 13px;
        line-height: 1.8;
        color: #4b5563;
        white-space: pre-wrap;
      }
    </style>
  </head>
  <body>
    <main class="panel">
      <h1>桌面界面加载失败</h1>
      <p>${message}</p>
    </main>
  </body>
</html>`;
}

function buildRendererBootstrapPage(detail = '正在连接本地界面与后台服务，请稍候…') {
  const message = detail
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/\n/g, '<br />');

  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${APP_DISPLAY_NAME}</title>
    <style>
      html, body {
        margin: 0;
        min-height: 100%;
        background: linear-gradient(180deg, #f6f8ff 0%, #f9fafb 100%);
        font-family: "PingFang SC", "SF Pro Display", "Helvetica Neue", sans-serif;
      }
      body {
        display: flex;
        align-items: center;
        justify-content: center;
        color: #111827;
      }
      .panel {
        width: min(560px, calc(100vw - 64px));
        border-radius: 28px;
        border: 1px solid #dbe5ff;
        background: rgba(255, 255, 255, 0.96);
        box-shadow: 0 24px 72px rgba(15, 23, 42, 0.12);
        padding: 28px;
      }
      .eyebrow {
        margin: 0;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.22em;
        text-transform: uppercase;
        color: #4f46e5;
      }
      h1 {
        margin: 12px 0 0;
        font-size: 28px;
        line-height: 1.3;
      }
      p {
        margin: 14px 0 0;
        font-size: 14px;
        line-height: 1.9;
        color: #4b5563;
      }
      .meta {
        margin-top: 18px;
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 13px;
        color: #374151;
      }
      .spinner {
        width: 18px;
        height: 18px;
        border-radius: 999px;
        border: 2px solid #c7d2fe;
        border-top-color: #5b7bfe;
        animation: spin 1s linear infinite;
      }
      @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
      }
    </style>
  </head>
  <body>
    <main class="panel">
      <p class="eyebrow">Startup</p>
      <h1>${APP_DISPLAY_NAME}</h1>
      <p>${message}</p>
      <div class="meta">
        <span class="spinner" aria-hidden="true"></span>
        <span>如果停留过久，应用会自动切到启动诊断页。</span>
      </div>
    </main>
  </body>
</html>`;
}

async function loadRendererWithFallback(window: BrowserWindow) {
  const devServerUrl = !app.isPackaged ? process.env.VITE_DEV_SERVER_URL : undefined;
  if (devServerUrl) {
    logElectronInfo(`[renderer:load] using dev server ${devServerUrl}`);
    await window.loadURL(devServerUrl);
    return 'dev';
  }

  const loadErrors: string[] = [];
  await registerRendererProtocol();
  logElectronInfo('[renderer:load] protocol registered');

  try {
    await startRendererStaticServer();
    logElectronInfo(`[renderer:load] loading http renderer ${rendererUrl()}`);
    await window.loadURL(rendererUrl());
    logElectronInfo('[renderer:load] http renderer loaded');
    return 'http';
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    loadErrors.push(`http:${detail}`);
    logElectronError(`[renderer:load] http_failed=${detail}`);
  }

  try {
    logElectronInfo(`[renderer:load] loading protocol renderer ${rendererProtocolUrl()}`);
    await window.loadURL(rendererProtocolUrl());
    logElectronInfo('[renderer:load] protocol renderer loaded');
    return 'app';
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    loadErrors.push(`app:${detail}`);
    logElectronError(`[renderer:load] app_failed=${detail}`);
  }

  const failureMessage = loadErrors.length > 0
    ? `渲染界面启动失败。\n${loadErrors.join('\n')}`
    : '渲染界面启动失败。';
  await window.loadURL(rendererFailurePageUrl(failureMessage));
  return 'error';
}

function buildBackendStartupError(prefix: string) {
  const tail = backendRecentLogLines.slice(-10).join('\n');
  if (tail) {
    return `${prefix}\n\n最近日志：\n${tail}`;
  }
  return prefix;
}

async function waitForBackend(timeoutMs = 45000): Promise<void> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (backendExitDetail) {
      throw new Error(buildBackendStartupError(backendExitDetail));
    }
    try {
      await new Promise<void>((resolve, reject) => {
        const req = http.get(`${backendUrl()}/api/v1/system/health`, (res) => {
          if ((res.statusCode ?? 500) >= 500) {
            reject(new Error(`status=${res.statusCode}`));
            return;
          }
          const chunks: Buffer[] = [];
          res.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
          res.on('end', () => {
            try {
              const payload = JSON.parse(Buffer.concat(chunks).toString('utf-8')) as BackendHealthPayload;
              const featureFlags = Array.isArray(payload.featureFlags) ? payload.featureFlags : [];
              const missing = REQUIRED_BACKEND_FEATURES.filter((feature) => !featureFlags.includes(feature));
              if (missing.length > 0) {
                reject(new Error(`backend_missing_features:${missing.join(',')}`));
                return;
              }
              const runtimeWarning = evaluateBackendRuntimeWarning(payload);
              if (runtimeWarning && !backendRuntimeWarningShown) {
                backendRuntimeWarningShown = true;
                logElectronError(`[backend:runtime-warning] ${runtimeWarning}`);
                dialog.showErrorBox('后端版本告警', `${runtimeWarning}\n\n建议重新安装或更新到同一版本的桌面安装包。`);
              }
              resolve();
            } catch (error) {
              reject(error);
            }
          });
        });
        req.on('error', reject);
      });
      return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 400));
    }
  }
  throw new Error(buildBackendStartupError(`后端服务启动超时（>${Math.round(timeoutMs / 1000)} 秒）`));
}

async function waitForCloudBackend(timeoutMs = 20000): Promise<void> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    try {
      await new Promise<void>((resolve, reject) => {
        const req = http.get(`${cloudBackendUrl()}/health`, (res) => {
          if ((res.statusCode ?? 500) < 500) {
            res.resume();
            resolve();
            return;
          }
          reject(new Error(`status=${res.statusCode}`));
        });
        req.on('error', reject);
      });
      return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 400));
    }
  }
  throw new Error('中心后端启动超时');
}

async function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1600,
    height: 980,
    minWidth: 1280,
    minHeight: 820,
    title: APP_DISPLAY_NAME,
    backgroundColor: '#eef3ff',
    titleBarStyle: 'hiddenInset',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    logElectronInfo(`[renderer:console:${level}] ${sourceId}:${line} ${message}`);
  });
  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    logElectronError(`[renderer:did-fail-load] code=${errorCode} description=${errorDescription} url=${validatedURL}`);
  });
  mainWindow.webContents.on('did-finish-load', () => {
    logElectronInfo(`[renderer:did-finish-load] url=${mainWindow?.webContents.getURL() ?? 'unknown'}`);
    const targetWindow = mainWindow;
    setTimeout(() => {
      if (!targetWindow || targetWindow.isDestroyed()) return;
      void targetWindow.webContents.executeJavaScript(`
        (() => {
          const root = document.getElementById('root');
          const style = root ? window.getComputedStyle(root) : null;
          return {
            href: location.href,
            readyState: document.readyState,
            title: document.title,
            rootChildCount: root?.childElementCount ?? 0,
            rootHtmlLength: root?.innerHTML?.length ?? 0,
            rootTextLength: (root?.textContent || '').trim().length,
            rootSnippet: (root?.textContent || '').trim().slice(0, 240),
            bodyTextLength: (document.body?.innerText || '').trim().length,
            bodySnippet: (document.body?.innerText || '').trim().slice(0, 240),
            rootDisplay: style?.display || null,
            rootVisibility: style?.visibility || null,
            rootOpacity: style?.opacity || null,
            bootEvents: Array.isArray(window.__YIYU_BOOT_EVENTS__) ? window.__YIYU_BOOT_EVENTS__ : [],
            appRendered: Boolean(window.__YIYU_APP_RENDERED__),
          };
        })()
      `, true)
        .then((snapshot) => {
          logElectronInfo(`[renderer:dom-snapshot] ${JSON.stringify(snapshot)}`);
        })
        .catch((error) => {
          const detail = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
          logElectronError(`[renderer:dom-snapshot-failed] ${detail}`);
        });
    }, 1800);
  });
  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    logElectronError(`[renderer:process-gone] reason=${details.reason} exitCode=${details.exitCode}`);
  });
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  await mainWindow.loadURL(rendererBootstrapPageUrl());
  if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.isVisible()) {
    logElectronInfo('[window] showing startup bootstrap page');
    mainWindow.show();
    mainWindow.focus();
  }

  const loadMode = await loadRendererWithFallback(mainWindow);
  if (loadMode === 'dev') {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }
  if (loadMode !== 'error' && mainWindow && !mainWindow.isDestroyed()) {
    if (!mainWindow.isVisible()) {
      logElectronInfo('[window] showing renderer after fallback load');
      mainWindow.show();
    }
    mainWindow.focus();
    app.focus({ steal: true });
  }
  await new Promise((resolve) => setTimeout(resolve, 1200));
  if (loadMode !== 'error' && mainWindow && !mainWindow.isDestroyed()) {
    await runTaskWindowDiagnostics(mainWindow);
    await runEventLineCreateDiagnostics(mainWindow);
  }
}

const gotSingleInstanceLock = app.requestSingleInstanceLock();
appendElectronLaunchLog('INFO', `[app] singleInstanceLock=${gotSingleInstanceLock}`);

if (!gotSingleInstanceLock) {
  appendElectronLaunchLog('ERROR', '[app] failed to acquire single-instance lock, quitting');
  app.quit();
}

app.on('second-instance', () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    if (mainWindow.isMinimized()) {
      mainWindow.restore();
    }
    mainWindow.focus();
    return;
  }
  const existingWindow = BrowserWindow.getAllWindows()[0];
  if (existingWindow) {
    if (existingWindow.isMinimized()) {
      existingWindow.restore();
    }
    existingWindow.focus();
    return;
  }
  void createMainWindow();
});

app.whenReady().then(async () => {
  appendElectronLaunchLog('INFO', '[app] whenReady entered');
  const reservedPorts = new Set<number>();
  const reuseExistingBackend = await checkBackendHealthAt(DEFAULT_BACKEND_PORT, REQUIRED_BACKEND_FEATURES);
  backendPort = reuseExistingBackend ? DEFAULT_BACKEND_PORT : await reservePort(DEFAULT_BACKEND_PORT, reservedPorts);
  reservedPorts.add(backendPort);
  const usingRemoteCloudBackend = shouldUseRemoteCloudBackend();
  const configuredRemoteCloudBackendUrl = remoteCloudBackendUrl();
  let reuseExistingCloudBackend = false;
  if (usingRemoteCloudBackend) {
    logElectronInfo(`[cloud] using remote collaboration backend ${configuredRemoteCloudBackendUrl}`);
  } else {
    reuseExistingCloudBackend = await checkCloudBackendHealthAt(DEFAULT_CLOUD_BACKEND_PORT);
    cloudBackendPort = reuseExistingCloudBackend ? DEFAULT_CLOUD_BACKEND_PORT : await reservePort(DEFAULT_CLOUD_BACKEND_PORT, reservedPorts);
    reservedPorts.add(cloudBackendPort);
  }
  process.env.YIYU_BACKEND_URL = backendUrl();
  process.env.YIYU_CLOUD_API_URL = cloudBackendUrl();
  uvBinaryPath = resolveUvBinary();
  if (!uvBinaryPath) {
    dialog.showErrorBox(
      '缺少 uv 运行时',
      '启动桌面应用前需要先安装 uv。请先执行 `curl -LsSf https://astral.sh/uv/install.sh | sh`，然后重新打开应用。',
    );
    app.quit();
    return;
  }
  const runtimeRoot = path.join(app.getPath('userData'), 'runtime');
  backendRuntimeVenv = path.join(runtimeRoot, 'backend-venv');
  cloudBackendRuntimeVenv = path.join(runtimeRoot, 'cloud-backend-venv');
  try {
    await ensureProjectRuntime('backend', backendRuntimeVenv);
    if (!usingRemoteCloudBackend) {
      await ensureProjectRuntime('cloud_backend', cloudBackendRuntimeVenv);
    }
    await registerRendererProtocol();
    await recyclePackagedRuntimeProcesses();
    purgeSavedApplicationState();
  } catch (error) {
    dialog.showErrorBox('后端运行时准备失败', error instanceof Error ? error.message : String(error));
    app.quit();
    return;
  }
  if (!usingRemoteCloudBackend && !reuseExistingCloudBackend) {
    startCloudBackend();
  }
  if (!reuseExistingBackend) {
    startBackend();
  }
  try {
    await waitForBackend();
  } catch (firstError) {
    logElectronError(`[backend:start] first attempt failed: ${firstError instanceof Error ? firstError.message : String(firstError)}`);
    if (!reuseExistingBackend) {
      try {
        await terminateManagedRuntimeProcess(backendRuntimeVenv);
      } catch {
        // Ignore cleanup failure and still retry once.
      }
      stopBackend();
      startBackend();
      try {
        await waitForBackend(30000);
      } catch (secondError) {
        dialog.showErrorBox('本地后端启动失败', secondError instanceof Error ? secondError.message : String(secondError));
        app.quit();
        return;
      }
    } else {
      dialog.showErrorBox('本地后端启动失败', firstError instanceof Error ? firstError.message : String(firstError));
      app.quit();
      return;
    }
  }
  appendElectronLaunchLog('INFO', '[app] creating main window');
  try {
    await createMainWindow();
  } catch (error) {
    dialog.showErrorBox('桌面界面启动失败', error instanceof Error ? error.message : String(error));
    app.quit();
    return;
  }
  appendElectronLaunchLog('INFO', '[app] main window created successfully');
  void waitForCloudBackend().catch((error) => {
    logElectronError(error instanceof Error ? (error.stack || error.message) : String(error));
  });
  appendElectronLaunchLog('INFO', '[app] startup sequence complete, app should stay alive');

  // Periodic backend health watchdog — restart if crashed silently
  setInterval(async () => {
    if (!ownsBackendProcess) return;
    if (backendProcess) return; // still running
    // Backend was ours but process handle is gone — it crashed
    appendElectronLaunchLog('ERROR', '[backend:watchdog] backend process gone, attempting restart');
    try {
      startBackend();
      await waitForBackend(20000);
      appendElectronLaunchLog('INFO', '[backend:watchdog] backend restarted successfully');
    } catch {
      appendElectronLaunchLog('ERROR', '[backend:watchdog] backend restart failed');
    }
  }, 15000); // Check every 15 seconds

  app.on('activate', async () => {
    // Re-activate: ensure backend is alive before showing window
    if (ownsBackendProcess && !backendProcess) {
      // Backend was owned but has exited — restart it
      appendElectronLaunchLog('INFO', '[app:activate] backend exited, restarting');
      try {
        startBackend();
        await waitForBackend(20000);
      } catch {
        appendElectronLaunchLog('ERROR', '[app:activate] backend restart failed');
      }
    } else if (!ownsBackendProcess && !backendProcess) {
      // No backend at all — check if it's reachable
      const alive = await checkBackendHealthAt(backendPort, []);
      if (!alive) {
        appendElectronLaunchLog('INFO', '[app:activate] backend unreachable, starting fresh');
        try {
          startBackend();
          await waitForBackend(20000);
        } catch {
          appendElectronLaunchLog('ERROR', '[app:activate] backend start failed');
        }
      }
    }
    if (!mainWindow || mainWindow.isDestroyed() || BrowserWindow.getAllWindows().length === 0) {
      try {
        await createMainWindow();
      } catch (error) {
        dialog.showErrorBox('桌面界面启动失败', error instanceof Error ? error.message : String(error));
      }
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });
});

app.on('before-quit', (event) => {
  appendElectronLaunchLog('INFO', `[app] before-quit fired`);
  stopBackend();
  stopCloudBackend();
});
app.on('will-quit', () => {
  appendElectronLaunchLog('INFO', '[app] will-quit fired');
});
app.on('window-all-closed', () => {
  appendElectronLaunchLog('INFO', '[app] window-all-closed fired');
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

ipcMain.handle('yiyu-workbench:selectFiles', async () => {
  const result = await dialog.showOpenDialog({
    title: '选择客户资料文件',
    properties: ['openFile', 'multiSelections'],
  });
  return result.canceled ? [] : result.filePaths;
});

ipcMain.handle('yiyu-workbench:getDesktopAppInfo', async () => {
  const executablePath = process.execPath;
  const appBundlePath = resolveBundlePath(executablePath);
  const recommendedInstallPath = path.join(app.getPath('home'), 'Applications', `${APP_DISPLAY_NAME}.app`);
  const detectedAppPaths = await collectInstalledAppPaths(appBundlePath);
  const legacyAppPaths: string[] = [];
  const duplicateAppPaths: string[] = [];

  for (const targetPath of detectedAppPaths) {
    if (targetPath === appBundlePath) continue;
    const baseName = path.basename(targetPath);
    const bundleId = await readBundleId(targetPath);
    if (legacyAppBasenames.has(baseName) || (bundleId && bundleId !== APP_BUNDLE_ID)) {
      legacyAppPaths.push(targetPath);
    } else {
      duplicateAppPaths.push(targetPath);
    }
  }

  let installWarning: string | null = null;
  if (legacyAppPaths.length > 0) {
    installWarning = `检测到 ${legacyAppPaths.length} 个旧入口，容易误开历史包。`;
  } else if (duplicateAppPaths.length > 0) {
    installWarning = `检测到 ${duplicateAppPaths.length} 个重复安装包，请保留单一入口。`;
  } else if (app.isPackaged && appBundlePath !== recommendedInstallPath) {
    installWarning = '当前运行包不在建议安装位置，后续升级时容易装错包。';
  }

  return {
    appVersion: app.getVersion(),
    isPackaged: app.isPackaged,
    platform: process.platform,
    arch: process.arch,
    appBundlePath,
    executablePath,
    releasePlanPath,
    releaseArtifactsPath,
    updateChannel: 'stable',
    updaterPhase: 'planning',
    recommendedInstallPath,
    installStatus: installWarning ? 'warning' : 'ok',
    installWarning,
    detectedAppPaths,
    legacyAppPaths,
  };
});

ipcMain.handle('yiyu-workbench:selectFolder', async () => {
  const result = await dialog.showOpenDialog({
    title: '选择客户资料目录',
    properties: ['openDirectory'],
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('yiyu-workbench:selectCollabRepo', async () => {
  const result = await dialog.showOpenDialog({
    title: '选择源码仓库目录',
    properties: ['openDirectory'],
  });
  if (result.canceled || !result.filePaths[0]) return null;
  const repoPath = await findSuggestedCollabRepoPath([result.filePaths[0]]);
  if (!repoPath) {
    throw new Error('你选中的目录不是 Git 源码仓库，请重新选择。');
  }
  return repoPath;
});

ipcMain.handle('yiyu-workbench:getCollabRepoStatus', async (_event, repoPath?: string | null) => {
  return getCollabRepoStatus({
    repoPath,
    suggestedCandidates: getCollabSuggestedCandidates(),
    appDbPath: path.join(app.getPath('userData'), 'app.db'),
  });
});

ipcMain.handle('yiyu-workbench:previewPushToMain', async (_event, repoPath: string) => {
  return previewPushToMain({
    repoPath,
    suggestedCandidates: getCollabSuggestedCandidates(),
    appDbPath: path.join(app.getPath('userData'), 'app.db'),
  });
});

ipcMain.handle('yiyu-workbench:commitAndPushToMain', async (_event, payload: CommitAndPushToMainPayload) => {
  return commitAndPushToMain(payload, getCollabSuggestedCandidates(), path.join(app.getPath('userData'), 'app.db'));
});

ipcMain.handle('yiyu-workbench:previewPullFromMain', async (_event, repoPath: string) => {
  return previewPullFromMain({
    repoPath,
    suggestedCandidates: getCollabSuggestedCandidates(),
    appDbPath: path.join(app.getPath('userData'), 'app.db'),
  });
});

ipcMain.handle('yiyu-workbench:pullSelectedFromMain', async (_event, payload: PullSelectedFromMainPayload) => {
  return pullSelectedFromMain(payload, getCollabSuggestedCandidates(), path.join(app.getPath('userData'), 'app.db'));
});

ipcMain.handle('yiyu-workbench:rebuildAndInstallFromRepo', async (_event, repoPath: string) => {
  const normalizedRepoPath = path.resolve(repoPath);
  const rebuildCommand = [
    `cd ${JSON.stringify(normalizedRepoPath)}`,
    `mkdir -p ${JSON.stringify(runtimeLogsDir)}`,
    `npm run dist:mac-local >> ${JSON.stringify(collabRebuildLogPath)} 2>&1`,
    `npm run install:mac-local >> ${JSON.stringify(collabRebuildLogPath)} 2>&1`,
    `node scripts/open-installed-app.mjs >> ${JSON.stringify(collabRebuildLogPath)} 2>&1`,
  ].join(' && ');
  fs.mkdirSync(runtimeLogsDir, { recursive: true });
  fs.appendFileSync(collabRebuildLogPath, `\n[${new Date().toISOString()}] start rebuild from ${normalizedRepoPath}\n`, 'utf8');
  const child = spawn('zsh', ['-lc', rebuildCommand], {
    cwd: normalizedRepoPath,
    detached: true,
    stdio: 'ignore',
  });
  child.unref();
  setTimeout(() => {
    app.quit();
  }, 300);
  return true;
});

ipcMain.handle('yiyu-workbench:readTextFile', async (_event, targetPath: string) => {
  const resolvedPath = path.resolve(targetPath);
  const stat = await fs.promises.stat(resolvedPath).catch(() => null);
  if (!stat || !stat.isFile()) {
    throw new Error('文件不存在，无法读取。');
  }
  const extension = path.extname(resolvedPath).toLowerCase();
  if (['.docx', '.pdf'].includes(extension)) {
    if (stat.size > 15 * 1024 * 1024) {
      throw new Error('当前只支持 15MB 以内的 docx/pdf DNA 文档。');
    }
    return extractPlatformDnaText(resolvedPath);
  }
  if (stat.size > 1024 * 1024) {
    throw new Error('当前只支持 1MB 以内的文本 DNA 文档。');
  }
  return fs.promises.readFile(resolvedPath, 'utf-8');
});

ipcMain.handle('yiyu-workbench:openPath', async (_event, targetPath: string) => {
  const message = await shell.openPath(targetPath);
  return message === '';
});

// --- File watcher for document edit detection ---
const activeFileWatchers = new Map<string, { watcher: fs.FSWatcher; debounceTimer: ReturnType<typeof setTimeout> | null }>();

ipcMain.handle('yiyu-workbench:watchFile', async (_event, targetPath: string) => {
  if (activeFileWatchers.has(targetPath)) return true;
  try {
    const resolvedPath = path.resolve(targetPath);
    const stat = await fs.promises.stat(resolvedPath).catch(() => null);
    if (!stat?.isFile()) return false;
    const initialMtime = stat.mtimeMs;
    const watcher = fs.watch(resolvedPath, () => {
      const entry = activeFileWatchers.get(targetPath);
      if (!entry) return;
      if (entry.debounceTimer) clearTimeout(entry.debounceTimer);
      entry.debounceTimer = setTimeout(async () => {
        const currentStat = await fs.promises.stat(resolvedPath).catch(() => null);
        if (currentStat && currentStat.mtimeMs !== initialMtime) {
          const win = BrowserWindow.getAllWindows()[0];
          if (win) {
            win.webContents.send('yiyu-workbench:fileChanged', targetPath);
          }
        }
      }, 1500);
    });
    activeFileWatchers.set(targetPath, { watcher, debounceTimer: null });
    return true;
  } catch {
    return false;
  }
});

ipcMain.handle('yiyu-workbench:unwatchFile', async (_event, targetPath: string) => {
  const entry = activeFileWatchers.get(targetPath);
  if (entry) {
    if (entry.debounceTimer) clearTimeout(entry.debounceTimer);
    entry.watcher.close();
    activeFileWatchers.delete(targetPath);
  }
  return true;
});

ipcMain.handle('yiyu-workbench:openExternalUrl', async (_event, targetUrl: string) => {
  await shell.openExternal(targetUrl);
  return true;
});

ipcMain.handle('yiyu-workbench:revealInFinder', async (_event, targetPath: string) => {
  shell.showItemInFolder(targetPath);
  return true;
});

ipcMain.handle('yiyu-workbench:saveFileAs', async (_event, sourcePath: string, suggestedName?: string) => {
  const resolvedSourcePath = path.resolve(sourcePath);
  const sourceStat = await fs.promises.stat(resolvedSourcePath).catch(() => null);
  if (!sourceStat?.isFile()) return null;

  const { canceled, filePath } = await dialog.showSaveDialog({
    title: '另存为',
    defaultPath: path.join(app.getPath('documents'), suggestedName || path.basename(resolvedSourcePath)),
    buttonLabel: '保存',
  });
  if (canceled || !filePath) return null;

  await fs.promises.copyFile(resolvedSourcePath, filePath);
  return filePath;
});
~~~

## `src/main/preload.ts`

- 编码: `utf-8`

~~~typescript
import { contextBridge, ipcRenderer, webUtils } from 'electron';
import type {
  CollabActionResult,
  CollabRepoStatus,
  CommitAndPushToMainPayload,
  DesktopAppInfo,
  PullPreview,
  PullSelectedFromMainPayload,
  PushPreview,
} from '../shared/types.js';

const backendBaseUrl = process.env.YIYU_BACKEND_URL ?? 'http://127.0.0.1:47829';

contextBridge.exposeInMainWorld('yiyuWorkbench', {
  backendBaseUrl,
  getDesktopAppInfo: (): Promise<DesktopAppInfo> => ipcRenderer.invoke('yiyu-workbench:getDesktopAppInfo'),
  selectFiles: (): Promise<string[]> => ipcRenderer.invoke('yiyu-workbench:selectFiles'),
  selectFolder: (): Promise<string | null> => ipcRenderer.invoke('yiyu-workbench:selectFolder'),
  selectCollabRepo: (): Promise<string | null> => ipcRenderer.invoke('yiyu-workbench:selectCollabRepo'),
  getCollabRepoStatus: (repoPath?: string | null): Promise<CollabRepoStatus> =>
    ipcRenderer.invoke('yiyu-workbench:getCollabRepoStatus', repoPath),
  previewPushToMain: (repoPath: string): Promise<PushPreview> =>
    ipcRenderer.invoke('yiyu-workbench:previewPushToMain', repoPath),
  commitAndPushToMain: (payload: CommitAndPushToMainPayload): Promise<CollabActionResult> =>
    ipcRenderer.invoke('yiyu-workbench:commitAndPushToMain', payload),
  previewPullFromMain: (repoPath: string): Promise<PullPreview> =>
    ipcRenderer.invoke('yiyu-workbench:previewPullFromMain', repoPath),
  pullSelectedFromMain: (payload: PullSelectedFromMainPayload): Promise<CollabActionResult> =>
    ipcRenderer.invoke('yiyu-workbench:pullSelectedFromMain', payload),
  rebuildAndInstallFromRepo: (repoPath: string): Promise<boolean> =>
    ipcRenderer.invoke('yiyu-workbench:rebuildAndInstallFromRepo', repoPath),
  getDroppedFilePath: (file: File): string | null => {
    try {
      return webUtils.getPathForFile(file) || null;
    } catch {
      return null;
    }
  },
  readTextFile: (targetPath: string): Promise<string> => ipcRenderer.invoke('yiyu-workbench:readTextFile', targetPath),
  openPath: (targetPath: string): Promise<boolean> => ipcRenderer.invoke('yiyu-workbench:openPath', targetPath),
  openExternalUrl: (targetUrl: string): Promise<boolean> => ipcRenderer.invoke('yiyu-workbench:openExternalUrl', targetUrl),
  revealInFinder: (targetPath: string): Promise<boolean> => ipcRenderer.invoke('yiyu-workbench:revealInFinder', targetPath),
  saveFileAs: (sourcePath: string, suggestedName?: string): Promise<string | null> =>
    ipcRenderer.invoke('yiyu-workbench:saveFileAs', sourcePath, suggestedName),
  watchFile: (targetPath: string): Promise<boolean> => ipcRenderer.invoke('yiyu-workbench:watchFile', targetPath),
  unwatchFile: (targetPath: string): Promise<boolean> => ipcRenderer.invoke('yiyu-workbench:unwatchFile', targetPath),
  onFileChanged: (callback: (filePath: string) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, filePath: string) => callback(filePath);
    ipcRenderer.on('yiyu-workbench:fileChanged', handler);
    return () => { ipcRenderer.removeListener('yiyu-workbench:fileChanged', handler); };
  },
});
~~~

