# scripts/ 脚本索引

## 脚本清单 + 第一段注释（用途）

### app-manifest.mjs（533 行）

```
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
export const APP_NAME = '益语智库自用平台 V2.0.app';
export const APP_DISPLAY_NAME = '益语智库自用平台 V2.0';
export const DEFAULT_PACKAGED_REMOTE_CLOUD_API_URL = 'http://101.126.34.232';
export const VERSION_MANIFEST_RELATIVE_PATH = path.join('dist', 'version-manifest.json');
export const BANNED_RENDERER_COPY = [
```

### build-packaged-runtime.mjs（175 行）

```
#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  RUNTIME_BACKEND_REQUIREMENTS_FILE,
  RUNTIME_PYTHON_SEED_DIR,
  RUNTIME_SEED_MANIFEST_FILE,
```

### check-installed-runtime.mjs（440 行）

```
#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  APP_DISPLAY_NAME,
  APP_NAME,
  DEFAULT_INSTALL_SMOKE_PATH,
```

### ensure-mac-release-prereqs.mjs（108 行）

```
import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import process from 'node:process';
const projectRoot = path.resolve(import.meta.dirname, '..');
const iconPath = path.join(projectRoot, 'build-resources', 'icon.icns');
const entitlementsPath = path.join(projectRoot, 'build-resources', 'entitlements.mac.plist');
const inheritedEntitlementsPath = path.join(projectRoot, 'build-resources', 'entitlements.mac.inherit.plist');
function parseDeveloperIdIdentities(output) {
  return output
```

### install-and-smoke-mac-dmg.mjs（214 行）

```
#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  APP_DISPLAY_NAME,
  APP_NAME,
  DEFAULT_INSTALL_SMOKE_PATH,
```

### install-mac-app.mjs（318 行）

```
#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  APP_DISPLAY_NAME,
  APP_NAME,
  DEFAULT_INSTALL_RECEIPT_PATH,
```

### open-installed-app.mjs（197 行）

```
#!/usr/bin/env node
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  APP_DISPLAY_NAME,
  APP_NAME,
  DEFAULT_INSTALL_SMOKE_PATH,
```

### package-local-mac-dmg.mjs（91 行）

```
#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { APP_DISPLAY_NAME, APP_NAME, sha256File } from './app-manifest.mjs';
const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const packageJsonPath = path.join(projectRoot, 'package.json');
const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
```

### run-local-electron.mjs（143 行）

```
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
```

### stabilize-mac-app.mjs（90 行）

```
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
```

### verify-mac-dmg.mjs（73 行）

```
#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { APP_DISPLAY_NAME, APP_NAME, sha256File } from './app-manifest.mjs';
const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const packageJson = JSON.parse(fs.readFileSync(path.join(projectRoot, 'package.json'), 'utf8'));
const targetDmg = process.argv[2]
```

### verify-packaged-app.mjs（334 行）

```
#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  APP_NAME,
  computeManifestId,
  findBannedRendererCopyViolations,
```

### write-version-manifest.mjs（29 行）

```
#!/usr/bin/env node
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  buildVersionManifest,
  computeManifestId,
  resolveProjectManifestPath,
  writeJsonFile,
} from './app-manifest.mjs';
const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
```

### collect-mac-startup-diagnostics.command（101 行）

```
#!/bin/bash
set -u
TS="$(date +%Y%m%d-%H%M%S)"
OUT="$HOME/Desktop/yiyu-startup-diagnostics-$TS.txt"
APP_NAME="益语智库自用平台 V2.0.app"
EXE_NAME="益语智库自用平台 V2.0"
exec > >(tee -a "$OUT") 2>&1
echo "Yiyu startup diagnostics"
echo "timestamp=$TS"
echo "output=$OUT"
```

### deploy-cloud-backend-volcengine.sh（64 行）

```
#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-${YIYU_CLOUD_DEPLOY_TARGET:-}}"
REMOTE_DIR="${2:-/opt/yiyu/cloud-backend}"
SERVICE_NAME="${3:-yiyu-cloud-backend.service}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH_OPTS=(-o StrictHostKeyChecking=no)
if [[ -z "${TARGET}" ]]; then
  echo "Usage: $0 <ssh-target> [remote-dir] [service-name]" >&2
  echo "Or set YIYU_CLOUD_DEPLOY_TARGET." >&2
```

### smoke-cloud-backend-volcengine.sh（79 行）

```
#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${1:-${YIYU_CLOUD_API_URL:-}}"
if [[ -z "${BASE_URL}" ]]; then
  echo "Usage: $0 <cloud-api-base-url>" >&2
  echo "Or set YIYU_CLOUD_API_URL." >&2
  exit 2
fi
retry_curl() {
  local path="$1"
```

### test-template-save.sh（45 行）

```
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
```

### audit_growth_badge_scope.py（270 行）

```
from __future__ import annotations
import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any
TASK_PREFIXES = (
    "task_created_",
    "task_deadline_",
    "task_ddl_set_",
```

### cleanup_audit_data.py（82 行）

```
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
```

### generate-mac-icon.py（71 行）

```
#!/usr/bin/env python3
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_RESOURCES = PROJECT_ROOT / "build-resources"
ICONSET_DIR = BUILD_RESOURCES / "icon.iconset"
ICON_PATH = BUILD_RESOURCES / "icon.icns"
```

### rebucket_workspace_folders.py（480 行）

```
#!/usr/bin/env python3
from __future__ import annotations
import argparse
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
SYSTEM_FOLDERS = ("收件箱", "线上转写", "待处理", "归档")
ONLINE_TRANSCRIPT_FOLDER = "线上转写"
```

### repair_orphan_data_center_ingest.py（136 行）

```
#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import sqlite3
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
```

### smoke_workspace_chat_async.py（26 行）

```
#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path
import runpy
def main() -> int:
    script_path = Path(__file__).resolve().parent / "smoke_workspace_chat_generation.py"
    argv = [str(script_path), "--mode", "async", *sys.argv[1:]]
    old_argv = sys.argv
    try:
```

### smoke_workspace_chat_generation.py（413 行）

```
#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
```

### sync-local-event-lines-to-cloud.py（304 行）

```
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
```

