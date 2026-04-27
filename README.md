# 益语智库自用平台

这是一个桌面优先的内部工作台，当前包含两条主线：

- 共享业务主线：账号、审批、协作任务、周复盘、层级视野
- 本地知识主线：客户工作台、资料导入、知识加工、AI 问答、引证、记忆沉淀

## 当前架构

- `src/`
  - Electron 主进程、preload、React 单体前端壳
- `backend/`
  - 本地桥接后端
  - 负责文件系统、知识底座、客户工作台、Qdrant、本地 AI 调用
- `cloud_backend/`
  - 共享业务后端
  - 负责员工账号、审批、任务协作、层级视野

## 知识底座原则

- 原始文件保留为事实源
- AI 代理文档和记忆文档以 `.md` 形式存放在本地数据目录
- 检索链路为：
  - `master index`
  - `surrogate markdown`
  - `raw chunk drillthrough`
- 前端搜索与最终回答分阶段执行，避免重复检索

## 本地启动

```bash
cd /Users/guyuanyuan/Desktop/益语智库自用平台
npm install
npm run dev
```

## 测试

```bash
cd /Users/guyuanyuan/Desktop/益语智库自用平台/backend
uv run pytest tests/test_api_smoke.py

cd /Users/guyuanyuan/Desktop/益语智库自用平台
npm run build
```

## 运行数据

- 本地工作台数据目录：
  - `~/Library/Application Support/YiyuThinkTankWorkbench`
- 共享业务数据目录：
  - `~/Library/Application Support/YiyuThinkTankCloud`
