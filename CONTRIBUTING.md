# Contributing

感谢你关注益语智库工作台。这个项目仍在快速迭代，欢迎通过 issue、discussion 或 pull request 参与。

## 开发流程

1. Fork 仓库并创建功能分支。
2. 复制 `.env.example` 为 `.env`，按需填入自己的云端、AI、飞书和对象存储配置。
3. 运行本地开发环境：

```bash
npm install
cd backend && uv sync && cd ..
cd cloud_backend && uv sync && cd ..
npm run dev
```

4. 提交前至少运行：

```bash
npm run typecheck:renderer
python3 -m compileall backend/app cloud_backend/app
```

如果改动涉及后端逻辑，请补充或更新对应测试。

## Pull Request 要求

- 描述问题背景、解决方案和验证方式。
- 不提交真实客户资料、数据库、日志、密钥、证书或本地运行时产物。
- 不把 `.env`、`.db`、`.log`、打包产物和个人配置加入仓库。
- UI 改动请附简短说明，必要时附脱敏截图。

## Issue 建议

提交 bug 时请尽量说明：

- 软件版本和操作系统。
- 复现步骤。
- 预期结果和实际结果。
- 是否连接云端、AI、飞书或对象存储。
- 脱敏后的错误提示或日志片段。

