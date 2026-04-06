# 益语智库平台 — 系统架构

## 整体架构

```
Electron App (~/Applications/益语智库自用平台.app)
├── Main Process (Node.js)
│   ├── main.ts — 窗口管理、生命周期
│   ├── preload.ts — contextBridge 安全桥接
│   └── collabGit.ts — Git 协作同步
│
├── Renderer Process (Browser)
│   └── React SPA (Vite, src/renderer/)
│       ├── App.tsx (~9000行) — 主应用
│       ├── components/tasks/ — 任务模块
│       │   └── EventLineReportPanel.tsx — 事件线汇报
│       ├── collab/ — 协作同步卡
│       ├── workbench/ — 统一工作台
│       └── strategic_accompaniment/ — 战略陪跑壳
│
├── Local Backend (Python, child process)
│   ├── backend/app/main.py (~20000行) — FastAPI
│   ├── backend/app/db.py — SQLite schema + migration
│   └── backend/app/models.py — Pydantic 模型
│   └── 数据: ~/Library/Application Support/YiyuThinkTankWorkbench/
│       └── Cache/event-line-attachments/ — 本地附件缓存
│
└── Cloud Backend (远程)
    ├── cloud_backend/ — 代码
    ├── 部署: 101.126.34.232
    ├── 服务: yiyu-cloud-backend.service
    └── venv: /opt/yiyu/cloud-backend/.venv
```

## 三层数据主权

| 层级 | 位置 | 存储内容 |
|------|------|---------|
| 本地桌面 | ~/Library/.../YiyuThinkTankWorkbench/ | 客户原始资料、诊断引擎、知识底座、事件线记忆、本地整理稿、附件缓存 |
| 云端协作 | 101.126.34.232 | 员工账号、审批流、任务协作、周复盘、部门聚合、公共事件线 |
| LAN服务器 | 规划中 | 文件对象存储、备份恢复、Admin Console |

## 本地后端 API 结构

FastAPI 运行在动态端口，主要功能：
- 任务 CRUD + 周计划/周总结
- 事件线活动管理（is_key 分类）
- 附件缓存代理（云端→本地缓存→前端）
- Word 导出（含专业封面页）
- 图片 OCR（Ark API）
- AI 问答与理解构建
- 诊断引擎

## 前端模块结构

App.tsx 约 9000 行，主要区域：
- 任务日历视图（TaskCalendarView）
- 周复盘面板（~行8180-8419）— 新壳：固定高度、tab切换、视角胶囊
- 事件线列表与报告
- 各种 Agent Panel
- 协作同步卡（右下角 Git 控件）
- 统一工作台

## 手机端（React Native + Expo）

- Android 优先
- 时间轴拖拽交互
- MobileSyncOp 队列与桌面端同步
- 轻量操作：查看任务、快速记录、时间段调整
