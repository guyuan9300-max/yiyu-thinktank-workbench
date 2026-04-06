# 益语智库自用平台（Yiyu ThinkTank Workbench）

## Identity
- **What it is**: 桌面优先的内部工作系统，把咨询判断工作从散装文档搬到有结构、有记忆、有证据链的系统里
- **Who it's for**: 益语智库内部团队（顾源源/CEO、林佳维、乐乐、四个部门负责人）及未来客户
- **Core value**: 前台足够轻（像滴答清单），后台足够深（组织判断机器）

## Tech Stack
- **Frontend**: React/TypeScript + Tailwind CSS, Vite 构建, 主文件 `src/renderer/App.tsx`（约 9000 行）
- **Backend (Local)**: Python FastAPI, `backend/app/main.py`（约 20000 行）, SQLite, 运行在动态端口
- **Backend (Cloud)**: Python, 部署在 101.126.34.232, 服务 yiyu-cloud-backend.service, venv 在 /opt/yiyu/cloud-backend/.venv
- **Desktop Shell**: Electron + Vite (`electron-vite`)
- **Mobile App**: React Native + Expo (Android 优先)
- **打包安装路径**: ~/Applications/益语智库自用平台.app

## Project Path
```
/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench
```
⚠️ 禁止使用旧路径 `~/.openclaw/`，统一用 `~/openclaw/workspace/`

## Build & Deploy（固定流程）
```bash
cd /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench
pkill -f "益语智库自用平台" 2>/dev/null; sleep 2
npm run dist:mac-local
rm -rf ~/Applications/益语智库自用平台.app
cp -R dist/mac-arm64/益语智库自用平台.app ~/Applications/益语智库自用平台.app
nohup ~/Applications/益语智库自用平台.app/Contents/MacOS/益语智库自用平台 > /dev/null 2>&1 &
```
⚠️ `npm run install:mac-local` 有时不完整，直接 rm + cp -R 更可靠
⚠️ 绝对不要做 `codesign --force --deep --sign -`

## Architecture Overview

系统分两条主线。**本地知识与判断线**（backend/）跑在用户本机，负责：客户工作台、资料导入与知识底座、AI 问答与理解构建、事件线记忆与澄清、诊断引擎、客户背景与组织 DNA。数据存储：~/Library/Application Support/YiyuThinkTankWorkbench/

**共享业务与协作线**（cloud_backend/）负责：员工账号安全、审批任务协作、周复盘与层级视野、部门组织架构、智能输入和任务压力种子。数据存储：~/Library/Application Support/YiyuThinkTankCloud/

**前端**是 React + Tailwind 单体 SPA（src/renderer/），**Electron 主进程**（src/main/）管窗口、preload 桥接、Git 协作同步。

## Key Files
| 文件 | 职责 |
|------|------|
| src/renderer/App.tsx | 主应用，含周复盘、事件线列表等 |
| src/renderer/components/tasks/EventLineReportPanel.tsx | 事件线汇报面板（预览+导出）|
| src/shared/types.ts | 全部 TypeScript 类型定义 |
| backend/app/main.py | 本地 FastAPI 后端（API + Word 导出 + 附件缓存代理）|
| backend/app/db.py | SQLite schema + migration |
| backend/app/models.py | Pydantic 模型 |
| cloud_backend/ | 云端后端代码 |
| src/main/main.ts | Electron 主进程，窗口管理 |
| src/main/preload.ts | contextBridge 安全桥接 |
| src/main/collabGit.ts | Git 协作同步 |

## 2026 战略方向
从"流程交付型咨询"转向"战略+应用共建+学习加速"。五个战略锚点：应用交付、OS V1.0、标杆客户、小型作战单元、预测性管理。

## 客户列表（2026 Q1）
| 客户 | 核心场景 | 阶段 |
|------|---------|------|
| 日慈 | 数据清洗→飞书建档→自动化 | 硬交付 + 验证产品化链路 |
| 为爱黔行 | 战略陪伴样板工程 | 共性问题技术试点 + 复诊机制 |
| CFFC | 3月理事会汇报 | 枢纽型组织，向上社交入口 |
| 蓝信封 | 管理权回收 + 飞书迁移 | 创始人回归管理 + 系统迁移 |
| 贝石 | 手册结项 + 社群运营探索 | 视频半自动化 + AI 社群运营 |
| 黄河基金会 | 潜在回归客户 | 能力准备 + 风险边界评估 |
| 愿景资本 | 3月活动 + 技术创新展示 | 活动策划 + 创新点落地 |

## User Preferences
- 不要反复确认，直接执行
- 品牌色 #5B7BFE，设计风格极简克制
- 设计语言统一：角的尺寸、颜色的使用排版一致

## Session History (Last 5)
| Date | Focus | Key Outcomes |
|------|-------|-------------|
| 2026-04-05 | 技能库建设 + 项目记忆 | 安装 engineering 插件 + 创建 5 个自定义技能 + 建立项目记忆系统 |
| 2026-04-05 | 周复盘 UI + 事件线改造 | 周复盘新壳（tab切换、视角胶囊）、事件线活动分类（is_key）、附件展示改造、图片OCR、本地缓存、Word导出封面 |
| 2026-04-04 | 架构设计 | 更新数据架构图（.drawio），三大模块展开版 |
| 2026-04-04 | 桌面端构建 | Electron 构建→安装→截图验证流程跑通 |
| 2026-04-03 | 手机端开发 | React Native 时间轴拖拽交互，经历多次构建失败后成功 |
