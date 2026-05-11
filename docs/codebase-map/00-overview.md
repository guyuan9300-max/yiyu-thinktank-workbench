# L0 仓库全景

生成时间：2026-05-11 09:18:34

## 一级目录体量

| 目录 | 子目录数 | 文件数 | 代码行数（去注释空行不算特殊处理） |
| --- | ---: | ---: | ---: |
| backend | 13 | 298 | 22 |
| cloud_backend | 5 | 37 | 121 |
| src | 19 | 86 | 61 |
| scripts | 1 | 25 | 26 |
| docs | 5 | 38 | 384 |
| mobile | 2085 | 3886 | 87 |
| build | 3 | 60 | 15 |
| build-resources | 2 | 15 | 23 |
| cloud_backend | 5 | 37 | 121 |
| deploy | 3 | 6 | 196 |
| qa | 2 | 12 | 0 |
| 软件描述 | 2 | 2 | 0 |

## 顶层文件

```
-rw-------       5.7K  CEO_WORKLOG.md
-rw-------       1.4K  README.md
-rw-------          0  app.db
-rw-------       5.5K  index.html
-rw-------       276K  package-lock.json
-rw-------       5.2K  package.json
-rw-------         83  postcss.config.cjs
-rw-------       1.1K  tailwind.config.cjs
-rw-------        594  tsconfig.json
-rw-------        475  tsconfig.node.json
-rw-------        35K  tsconfig.node.tsbuildinfo
-rw-------        409  vite.config.ts
```

## 语言分布（源代码文件数）

| 语言 | 文件数 | 代码行数 |
| --- | ---: | ---: |
| .ts | 132 | 61 |
| .tsx | 88 | 3574 |
| .py | 194 | 121 |
| .mjs | 49 | 440 |
| .cjs | 2 | 40 |
| .js | 30 | 1604 |
| .md | 48 | 23 |
| .sh | 6 | 79 |

## 单文件 Top 20（按行数，含本仓库源码）

```
23465 ./src/renderer/App.tsx
13616 ./cloud_backend/app/main.py
7680 ./backend/tests/test_api_smoke.py
7254 ./backend/app/models.py
6582 ./src/shared/types.ts
5809 ./build/shared/types.d.ts
4582 ./backend/app/services/ai.py
4358 ./backend/app/services/knowledge_base.py
4044 ./backend/app/services/knowledge_v2.py
3932 ./backend/app/services/analysis_center.py
3574 ./src/renderer/legacy_features/topics/LegacyTopicsManagementView.tsx
3513 ./backend/app/services/digital_asset_center.py
3339 ./src/renderer/lib/api.ts
3015 ./backend/app/services/growth_engine.py
2986 ./backend/app/db.py
2976 ./src/main/main.ts
2733 ./src/renderer/components/tasks/EventLineReportPanel.tsx
2724 ./backend/app/services/review_analysis.py
2723 ./build/main/main.js
2507 ./backend/app/services/review_narrative.py
```

## 子模块状态

```
fatal: no submodule mapping found in .gitmodules for path 'mobile'
(no submodules)
```

## .gitignore 摘要

```
node_modules/
.expo/
mobile/.expo/
mobile/dist/
.claude/
.playwright-cli/
dist/
build/
coverage/
.DS_Store
.codex/
__pycache__/
.pytest_cache/
.venv/
backend/*.db
cloud_backend/*.db
data/*.db
data/*.db-shm
data/*.db-wal
.env
.env.local
.env.*.local
*.sqlite
*.sqlite3
*.sqlite-shm
*.sqlite-wal
*.db
*.db-shm
*.db-wal
*.log
```
