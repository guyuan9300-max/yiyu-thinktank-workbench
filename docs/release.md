# 发布说明

## 本地测试包

```bash
npm run dist:mac-local
```

该命令生成未签名 macOS 包，只用于本机测试。

## 正式 macOS 包

正式发布需要：

- Apple Developer ID Application 证书。
- Apple 公证配置。
- 更新源存储写入权限。
- 不包含真实 `.env`、数据库、日志和证书的干净工作树。

推荐先运行：

```bash
npm run release:mac:doctor:strict
npm run release:mac
npm run release:mac:verify-dmg
```

## 更新源

项目内置的是 generic provider 机制。你可以把 `latest-mac.yml`、DMG、ZIP 和 blockmap 上传到自己的静态文件服务或对象存储。

发布时必须先上传安装包和 blockmap，最后上传 `latest-mac.yml`，避免用户读到半完成版本。

## GitHub Release

开源仓库的 GitHub Release 可以用于发布源码说明和变更记录。正式安装包是否放在 GitHub Release 中，由维护者根据签名、公证和分发策略决定。

