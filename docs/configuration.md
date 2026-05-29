# 配置说明

本项目不在仓库中保存真实配置。请复制根目录 `.env.example` 为 `.env`，再按需填写。

## 云端

- `YIYU_REMOTE_CLOUD_API_URL`：桌面端连接的云端协作服务。
- `YIYU_CLOUD_SECRET_KEY`：云端后端服务密钥。
- `YIYU_CLOUD_PUBLIC_BASE_URL`：云端服务对外可访问地址。

## 大模型

可通过组织级配置或环境变量接入不同模型供应商。示例变量：

- `YIYU_LLM_PROVIDER`
- `YIYU_LLM_BASE_URL`
- `YIYU_LLM_API_KEY`
- `YIYU_LLM_MODEL`

如果没有配置模型，依赖 AI 的能力会降级或提示需要配置，不应把真实 API Key 写入代码。

## 飞书

飞书同步需要自建飞书应用或机器人：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_BOT_WEBHOOK`

组织内成员应读取组织级配置，避免每个成员重复保存密钥。

## 对象存储

对象存储用于文件中转、云端附件、语音等文件存储。支持 S3/TOS 兼容服务：

- `OBJECT_STORAGE_ENDPOINT`
- `OBJECT_STORAGE_BUCKET`
- `OBJECT_STORAGE_ACCESS_KEY_ID`
- `OBJECT_STORAGE_SECRET_ACCESS_KEY`

## 语音转写

可以使用本地模型或云端模型。云端模型配置应通过组织级配置下发，成员端只读使用。

## 更新源

正式分发时，`YIYU_UPDATE_FEED_URL` 应指向你自己的更新清单目录。开源仓库不会内置任何私有发布密钥。

