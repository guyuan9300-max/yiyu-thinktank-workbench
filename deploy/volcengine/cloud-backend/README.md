# 火山云部署：cloud_backend

这个目录只负责把在线协作后端 `cloud_backend` 部署到公网，供手机端和后续云协作调用。

## 为什么只部署它

- 手机端当前直接对接的是共享协作后端，而不是桌面本地后端。
- 桌面本地后端继续留在本机，负责本地知识、文件和桥接。
- `cloud_backend` 上云后，手机只需要把服务器地址改成公网 HTTPS 地址即可联动。

## 目录说明

- `Dockerfile`：构建 `cloud_backend` 镜像
- `docker-compose.yml`：启动 API + Caddy HTTPS 代理
- `Caddyfile`：公网反代与证书
- `.env.example`：云端必要环境变量样例
- `bootstrap-server.sh`：第一次登录服务器后执行，自动安装 Docker 并拉起服务

## 最小依赖

- 一台 Ubuntu 云服务器
- 安全组放通 `80 / 443`
- 公网 IP

## HTTPS 策略

默认不依赖你手动配置 DNS。

`bootstrap-server.sh` 会在未提供 `PUBLIC_HOST` 时，自动把公网 IP 变成：

- `x.x.x.x.sslip.io`

然后由 Caddy 申请证书并反向代理到 `cloud_backend`。

如果你后面要切正式域名，例如 `api.example.com`，只需要重新运行：

```bash
PUBLIC_HOST=api.example.com ./bootstrap-server.sh
```

## 手机端接法

部署成功后，手机端服务器地址填：

- `https://<PUBLIC_HOST>`

例如：

- `https://123.123.123.123.sslip.io`

## 注意

- 这套部署当前使用 SQLite，适合作为 V1 协作后端，不适合高并发多副本。
- `.env` 会在首次部署时自动生成随机 secret 和初始口令，后续要妥善保管。
- 如果要长期上线，建议把 `sslip.io` 切到自己的正式域名。

## 自定义云端部署示例

下面是火山云 ECS 的非容器部署示例，地址均为占位示例，正式环境请替换为自己的主机、域名和数据库：

- 实例：`yiyu-cloud-collab-01`
- 当前可用公网地址：[http://203.0.113.10](http://203.0.113.10)
- 证书地址（已签发但当前被火山云 webblock 拦截）：`https://203.0.113.10.sslip.io`
- 运行方式：
  - `systemd`：`yiyu-cloud-backend.service`
  - `nginx`：80/443 反向代理到 `127.0.0.1:47831`
  - `uvicorn`：`app.main:create_app --factory`
- 证书续期：
  - `systemd timer`：`yiyu-certbot-renew.timer`

这次没有沿用 Docker/Caddy 路线，原因是目标机器到 Docker Hub 的出网拉镜像超时；因此切换为：

- `python3 -m venv`
- `systemd`
- `nginx`
- `Let's Encrypt`

同时已经把本机现有的 `YiyuThinkTankCloud/cloud.db` 做一致性快照并导入云端，确保手机端连上后不是空协作库。

### 入口说明

- 桌面端打包版不再预置任何云端地址；首次使用需要在系统设置中填写云端服务地址。
- 移动端不再预置任何云端地址；首次使用需要在登录页或账号设置中填写服务地址。
- 如果你有自定义云端，可以配置为：
  - **HTTPS**：`https://api.example.com`
  - **HTTP 兜底**：`http://203.0.113.10`
- 根域名 `example.com` 的现有站点未改动；只新增子域名 `api.example.com -> 203.0.113.10`。

## 智能输入 / 语音转写配置

2026-03-30 起，手机端后端链路已经拆成两类：

- 智能输入：文字自然语言 -> 结构化任务草稿
- 长录音/补充录音：录音文件 -> 豆包文件 ASR 转写 -> 文档沉淀请求

对应云端接口：

- `POST /api/v1/mobile/smart-input/task-draft`
- `POST /api/v1/tasks/{task_id}/attachments/{attachment_id}/transcribe-to-document`

如果要让长录音文件转写真正可用，线上 `.env` 至少要补这几项：

```bash
YIYU_CLOUD_PUBLIC_BASE_URL=http://203.0.113.10
DOUBAO_FILE_ASR_APP_ID=your-file-asr-app-id
DOUBAO_FILE_ASR_ACCESS_TOKEN=your-file-asr-access-token
```

如果后续要把“智能输入”改成真正的流式短语音识别，再补：

```bash
DOUBAO_STREAM_ASR_APP_ID=your-stream-asr-app-id
DOUBAO_STREAM_ASR_ACCESS_TOKEN=your-stream-asr-access-token
```

可选增强：

```bash
YIYU_SMART_INPUT_MODEL=qwen3.5-plus
DASHSCOPE_API_KEY=your-dashscope-key
```

说明：

- `YIYU_CLOUD_PUBLIC_BASE_URL`
  - 用于给豆包标准版 ASR 提供可回拉的临时音频 URL
  - 如果实例对外域名已经可用，推荐填正式公网域名，例如 `https://api.example.com`
- `DOUBAO_FILE_ASR_*`
  - 负责长录音/补充录音这类文件上传后的中文语音转写
- `DOUBAO_STREAM_ASR_*`
  - 预留给智能输入的短语音/流式识别
- `DASHSCOPE_API_KEY`
  - 可选；存在时会优先走 Qwen 结构化提取
  - 没有时仍可用规则兜底生成草稿

格式注意：

- Expo 真机常见录音格式是 `m4a`
- `m4a/aac` 会优先走豆包标准版识别，因此更依赖 `YIYU_CLOUD_PUBLIC_BASE_URL`
- `wav/mp3/ogg` 这类格式可以直接走极速版 data-base64 接口

## 2026-03-30 可重复发布方式

当前线上协作后端已经不建议继续手工 SSH 拼命令更新。

仓库里现在有两条本地脚本：

- `scripts/deploy-cloud-backend-volcengine.sh`
  - 把 `cloud_backend/app`、`pyproject.toml`、`uv.lock`、`requirements.deploy.txt` 同步到服务器
  - 刷新远端 `venv`
  - 重启 `yiyu-cloud-backend.service`
  - 最后自动做 smoke check
- `scripts/smoke-cloud-backend-volcengine.sh`
  - 检查 `/health`
  - 检查 `/openapi.json` 里是否已经包含智能输入路由
  - 提醒是否已配置智能输入所需环境变量

默认目标：

- 主机：`root@203.0.113.10`
- 目录：`/opt/yiyu/cloud-backend`
- 服务：`yiyu-cloud-backend.service`

如果本机 SSH 不是默认钥匙，可设置：

```bash
export YIYU_VOLCENGINE_SSH_KEY=/absolute/path/to/private_key
```

然后直接执行：

```bash
./scripts/deploy-cloud-backend-volcengine.sh
```

如果只想先检查线上接口，不发布代码：

```bash
./scripts/smoke-cloud-backend-volcengine.sh https://api.example.com
```

## 当前 HTTPS 真实状态

截至 2026-03-30：

- `sslip.io` 域名虽然签出过证书，但公网访问会被火山云 `webblock` 拦截
- `nip.io` 的 HTTP 访问是通的，但无论 `HTTP-01` 还是 `TLS-ALPN-01`，Let's Encrypt 校验都在 CA 侧出现 `Connection reset by peer`
- 已改用自有域名子域名 `api.example.com`
- 解析方式：阿里云 DNS 新增 `api -> 203.0.113.10`
- 证书方式：`acme.sh + Let's Encrypt + nginx`

当前对外口径：

- **主入口**：`https://api.example.com`
- **HTTP 兜底**：`http://203.0.113.10`
- **根站保持不变**：`example.com` 现有网站未迁移、未替换
