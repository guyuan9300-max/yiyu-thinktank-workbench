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
  unexpected_matches="$(printf '%s\n' "$lifecycle_matches" | rg -v '^(lib/(android-back|record-note-service|sync-engine|system-health|task-board-store-core)\.ts|components/(RecordNote|SmartInputSheet)\.tsx|components/tasks-screen/SmartInputRecoveryController\.tsx|app/\(tabs\)/(calendar|profile)\.tsx):' || true)"
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
