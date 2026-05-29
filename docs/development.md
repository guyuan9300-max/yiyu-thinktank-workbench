# 开发指南

## 安装依赖

```bash
npm install
cd backend && uv sync && cd ..
cd cloud_backend && uv sync && cd ..
```

## 启动桌面端

```bash
cp .env.example .env
npm run build:main
npm run dev
```

默认不会连接任何远端云地址。需要连接自建云端时设置：

```bash
YIYU_REMOTE_CLOUD_API_URL=http://localhost:47830 npm run dev
```

## 启动后端

本地后端和云端后端也可以单独运行，便于调试：

```bash
cd backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 47829

cd ../cloud_backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 47830
```

## 常用检查

```bash
npm run typecheck:renderer
python3 -m compileall backend/app cloud_backend/app
npm run backend:test
npm run cloud:test
```

## 打包

本地未签名包：

```bash
npm run dist:mac-local
```

正式签名、公证和更新源发布请参考 [发布说明](release.md)。

