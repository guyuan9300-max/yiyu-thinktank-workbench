# 益语智库工作台

益语智库工作台是一款面向公益组织、小型团队和顾问型服务团队的 AI 协作桌面软件。它把任务协作、客户/项目资料、事件线、文档知识库、情报与舆情、周复盘和成长记录放在同一个工作台里，帮助团队把分散的信息转化为可执行的判断和行动。

> 当前仓库已公开开源。生产部署、组织云、AI、飞书、对象存储和发布分发相关密钥需要自行配置，仓库不包含任何运行时密钥。

## 功能

- 协作收件箱：接收和处理需要自己确认的协作任务与通知。
- 任务与日程：管理个人任务、协作任务、时间安排和复盘入口。
- 事件线：围绕客户、项目或议题沉淀关键进展、决策与证据。
- 工作台：导入和管理项目资料，支持文件解析、知识检索和 AI 问答。
- 战略陪伴：维护客户/项目档案、判断思考和下一步行动。
- 资讯情报站：围绕工作对象抓取时效情报和舆情信号。
- 周复盘与成长中心：沉淀经验、复盘任务，并形成个人/团队成长记录。
- 集成能力：支持云端协作、飞书消息/文档/日历、对象存储、语音转写和大模型配置。

## 技术架构

- `src/`：Electron 主进程、preload、React/Vite 渲染端和共享类型。
- `backend/`：本地 FastAPI 后端，负责本机文件、知识库、AI 编排和本地运行时能力。
- `cloud_backend/`：云端 FastAPI 后端，负责账号、组织、协作同步、飞书集成和组织级配置。
- `scripts/`：本地开发、打包、发布和运行时检查脚本。
- `docs/`：公开架构、开发、配置、发布和法律合规文档。

更多结构说明见 [docs/architecture.md](docs/architecture.md)。

## 环境要求

- macOS（桌面端主要面向 macOS）
- Node.js 20+
- npm 10+
- Python 3.11+
- uv（Python 依赖和测试）

## 本地开发

```bash
npm install
cd backend && uv sync && cd ..
cd cloud_backend && uv sync && cd ..
cp .env.example .env
npm run build:main
npm run dev
```

默认开发模式不预置任何远端云地址。需要连接自建云端时，在 `.env` 或启动环境中配置 `YIYU_REMOTE_CLOUD_API_URL`。

## 常用命令

```bash
# 渲染端类型检查
npm run typecheck:renderer

# 本地后端测试
npm run backend:test

# 云端后端测试
npm run cloud:test

# 构建本地未签名 macOS 包
npm run dist:mac-local

# 构建并安装到本机测试
npm run install:mac-local
```

## 配置

复制 `.env.example` 为 `.env` 后按需填写。常见配置包括：

- `YIYU_REMOTE_CLOUD_API_URL`：自建云端协作服务地址。
- `YIYU_CLOUD_SECRET_KEY`：云端服务签名密钥。
- `YIYU_LLM_*`：大模型服务配置。
- `FEISHU_*`：飞书应用与机器人配置。
- `OBJECT_STORAGE_*`：对象存储配置。
- `SPEECH_*`：语音转写配置。
- `YIYU_UPDATE_FEED_URL`：桌面端更新源。

真实密钥、证书、数据库、日志和运行时文件不得提交到仓库。

## 安全扫描

仓库包含推送前和 CI 可复用的安全扫描脚本：

```bash
npm run security:scan
```

它会阻止 `.env`、数据库、日志、证书、私钥、发布密钥目录和疑似真实密钥进入源码树。DMG/ZIP 安装包不被视为密钥，但不建议作为普通源码提交；正式安装包应通过 GitHub Release 或火山云 TOS 发布。

## 文档

- [开发指南](docs/development.md)
- [配置说明](docs/configuration.md)
- [架构概览](docs/architecture.md)
- [发布说明](docs/release.md)
- [常见问题](docs/faq.md)
- [安全反馈](SECURITY.md)

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。
