# 输入广度（input-breadth）线程进度

**起草日期：** 2026-05-12
**主分支：** `feature/input-breadth`（起点 `main` = 793bf44）
**Worktree：** `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench-input-breadth`
**计划文档：** `docs/剩余7维度-Claude-Code完整执行计划-2026-05-12.md` Part 1

---

## 全局进度

| 迭代 | 名称 | 状态 |
|---|---|---|
| I0 | 准备工作 | 🟡 进行中 |
| I1a | 语音模型配置 UI + 后端接入 | ⏳ 待启动 |
| I1b | 录音文件上传 → 异步转写 → 入库 | ⏳ 待启动 |
| I2 | 邮件接入（Gmail / Outlook） | ⏳ 待启动 |
| I3 | IM 历史拉取（飞书群 + 企微 + 钉钉） | ⏳ 待启动 |
| I4 | 文档结构化（Excel/PPT 结构保留） | ⏳ 待启动 |
| I5 | 视频通用化（YouTube/抖音/本地 mp4） | ⏳ 待启动 |

---

## 迭代 I0 · 准备工作

### 验收清单
- [x] 新分支 `feature/input-breadth`（起点 main，与 Cowork 的 understanding-depth 独立）
- [x] 独立 worktree 建立
- [x] 跑 `uv sync` 装 Python 环境
- [x] 静态审计：现状 ASR / 录音上传 / 火山 / 邮件
- [x] 跑 pytest 测试基线（312 passed / 121 failed / 23min）
- [x] 新建 progress 文档（本文）
- [ ] checkpoint 等用户进 I1

### 静态审计结果

#### 1. 现有 ASR 链路（in `link_material_import.py`）

**已有的：**
- `LocalTranscriptEngine` 类（line 60）：纯本地 CLI 调用模式
  - `name: Literal["local_sensevoice", "local_whisper"]`
  - 通过 `subprocess.run` 调本地命令（用户机器要装 sensevoice / whisper CLI）
  - 走 `_transcribe_temp_audio()`（line 788）
- `extract_audio_from_media(media_path, temp_dir, *, ffmpeg: str)`（line 757）：用 ffmpeg 二进制切音轨
- 音频扩展名白名单：`.aac/.aiff/.alac/.flac/.m4a/.mp3/.oga/.ogg/.opus/.wav/.weba/.wma`
- 视频扩展名白名单：`.avi/.flv/.m4v/.mkv/.mov/.mp4/.mpeg/.mpg/.webm/.wmv`
- 集成在 `link_material_import.py` 流程内（line 191-217）：仅 B 站/小红书 yt-dlp 下载后转写

**缺失的：**
- 云 ASR provider（火山 / OpenAI Whisper / 阿里通义 / 讯飞）—— 0 命中
- 用户上传录音文件的入口（前端 + 后端 endpoint）—— 0 命中
- `audio_transcription_jobs` 表 —— 0 命中
- ASR provider 抽象层（现在只有"本地 CLI"一种实现）

#### 2. 现有"上传文件"入口

`backend/app/main.py` 里只有两处 `UploadFile`：
- line 27800：`POST /api/v1/event-lines/{event_line_id}/attachments`（事件线附件）
- line 40457：`POST /api/v1/tasks/{task_id}/attachments`（任务附件）

两处 pattern 相似：`UploadFile = File(...)` + form-multipart。**I1b 可以参考这两个 pattern**。

#### 3. 前端"上传"UI

- 前端 grep `<input type="file" accept="audio"` → **0 命中**
- 客户工作台目前没有任何音频/录音上传入口
- 现有的"导入资料"流程走 `link_material_import`（粘贴链接）或 `import_documents`（拖拽文件，但文件类型审计未含音频）

#### 4. 现有"模型配置"UI（I1a 复用 pattern）

`src/renderer/components/settings/` 下相关组件：
- `OrganizationModelSettingsPanel.tsx` —— LLM（豆包等）配置主面板
- `OrganizationSetupCenter.tsx` —— 设置中心容器

**I1a 设计：** 在 OrganizationModelSettingsPanel 旁边新增一个"语音识别模型"section，复用 ak/sk 加密存储 + 测试连接 pattern。

#### 5. 火山 / 豆包接入现状

`backend/app/services/ai.py` 等 8 个文件含火山/豆包关键词，但都走 `openai_compatible` LLM 通道（不是 ASR）。火山 ASR API 鉴权字段（`app_id + access_key + access_token`）和 LLM 不同，**不能复用现有 ak/sk**，要新建配置。

#### 6. pyproject.toml 现有依赖

```
fastapi, uvicorn, httpx, pydantic, pytest, pypdf, pymupdf, pillow,
python-docx, qdrant-client, fastembed, python-multipart, yt-dlp, curl-cffi
```

**没有：** ffmpeg-python（项目用系统 ffmpeg 二进制）/ openai / volcengine-python-sdk / openpyxl / python-pptx / reportlab

**I1 实现路线：** 用 `httpx` 直接调火山 ASR HTTP API，**不引入** `volcengine-python-sdk`（计划已确认）。

#### 7. 邮件相关（I2 用，I1 不动）

- IMAP / SMTP / Gmail API / Outlook API / Graph API → **0 命中**
- I2 实现时要新增依赖：`google-auth + google-api-python-client`（Gmail）或 `msal`（Outlook）

#### 8. 三个 worktree 状态

```
/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench       [feature/understanding-depth]  Cowork 在用
/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench-chat  [feature/chat-quality-of-life] 我的 chat 改动（已 commit 987c5ec）
/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench-input-breadth  [feature/input-breadth]  本线程
```

---

## I1 设计草案（待用户拍板后进 ① 目标锁定）

### I1a · 语音模型配置 UI + 后端接入

**一句话目标：** 用户能在系统设置里配置火山 ASR ak/sk，能测试连接，配置加密落库。

**关键改动：**
- 新建 `speech_model_settings` 表（不扩 `ai_model_profiles`）
- 新建 `backend/app/services/speech_recognition/`：
  - `__init__.py`：`TranscriptionProvider` 协议
  - `volcano_provider.py`：火山实现（httpx）
- 加密存储复用现有 LLM ak/sk 加密 helper（I0 完成后查具体位置）
- 系统设置 UI 加"语音识别模型"section（在 `OrganizationModelSettingsPanel.tsx` 内或单建）
- "测试连接"按钮：上传内置 1s 静音 .wav → 调火山 → 拿到任务 ID → 轮询 → 验证

**预算：** 30-40 工具调用

### I1b · 录音文件上传 → 异步转写 → 入库

**一句话目标：** 用户在客户工作台拖拽上传 .m4a/.mp3/.wav 文件，后端切片并行送 ASR，转写完落地为 `.transcript.md` 走 ingest。

**关键改动：**
- 前端：客户工作台加"录音上传"入口（接受 `_AUDIO_EXTENSIONS` 全部 12 种格式）
- 后端：`POST /api/v1/clients/{client_id}/audio-transcriptions`（form-multipart，复用 task attachment pattern）
- 新建 `audio_transcription_jobs` 表（status：queued/running/done/failed/partial）
- 新建 `backend/app/services/speech_recognition/transcription_orchestrator.py`：
  - 上限检查（暂不设硬上限，靠切片解决）
  - 切片：单片 15min + 10s 重叠
  - 并行送 ASR（最多 4 个）
  - 合并 segments + 去除边缘重复
  - 合并失败时单片重试
- 转写完成 → 落地为 `{client_dir}/raw_audio/{job_id}.m4a` + `{job_id}.transcript.md`
- `.transcript.md` 走 `ingest_document_knowledge` 正常入库
- 至少 5 个测试（mock 火山 API）

**预算：** 50-65 工具调用

---

## 测试基线（main = 793bf44）

- **312 passed / 121 failed / 737 warnings**，耗时 23min 32s（1412.52s）
- 121 failed 是 main 分支既有红，**不是 I1 引入的**。按计划 R-G-5 接受 baseline，只关心 delta（I1 不能引入新红）
- 已红测试集中在几个模块（待 I1 实现时确认我的改动不会再增红）：
  - `test_organization_dna_v2` 类（组织 DNA）
  - `test_review_visibility` 类（审阅可见性）
  - `test_task_cloud_shadow_sync` 类（任务云同步）
  - `test_understanding_basic` / `test_understanding_enhanced` 类（理解能力）
  - `test_workspace_chat_primary_fallback_guard` 类（聊天兜底）
- 跑测试命令：`cd backend && uv run pytest tests/ --tb=no -q`

---

## 已知缺口 / 风险登记

| ID | 项 | 处理 |
|---|---|---|
| R-I-1 | 火山 ASR ak/sk 待用户提供 | 阻塞 I1a 测试连接，但不阻塞 I1a 实现 |
| R-I-2 | Task #28（dev app 自主重启）未完成，I1 UI 验证靠 `--reload` | 用户决定是否插队做 #28 |
| R-I-3 | 从 main 起，没拿到 Cowork 实体/矛盾 UI；I1 UI 验证里看到的客户工作台是"老版本" | 不影响 I1（录音上传与实体无关） |
| R-I-4 | 切片实现复杂度高于计划文档估计 | I1b 预算从 50-65 升到 65-80 |

---

## checkpoint 节点

- ⏳ I0 末 checkpoint（即将）：等用户确认进 I1
