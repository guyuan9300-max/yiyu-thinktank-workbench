# macOS 更新源规范

## 目标

- 为官网版桌面应用提供稳定的更新读取目录。
- 同时支持：
  - 官网首次手动下载安装
  - 客户端应用内更新

## 渠道目录

建议固定两套目录：

- `stable/`
- `beta/`

示意：

```text
https://download.example.com/yiyu/
  stable/
  beta/
```

## 每个渠道必须包含的文件

### 手动下载安装

- `YiyuThinkTankWorkbench-<version>-mac-arm64.dmg`

### 应用内更新

- `YiyuThinkTankWorkbench-<version>-mac-arm64.zip`
- `latest-mac.yml`
- `YiyuThinkTankWorkbench-<version>-mac-arm64.zip.blockmap`

如果后续支持 Intel 或 universal 包，再增加对应命名，但首版先不要混发。

## `latest-mac.yml` 的职责

- 描述当前渠道最新版本
- 指向可下载的 `ZIP`
- 提供校验与尺寸信息
- 供 `electron-updater` 读取

要求：

- `stable/latest-mac.yml` 只指向稳定版
- `beta/latest-mac.yml` 只指向测试版

## 官网下载入口要求

官网至少有两个入口：

- 默认下载入口：指向 `stable` 的 `DMG`
- 内部测试入口：指向 `beta` 的 `DMG`

说明：

- 官网下载页服务的是首次安装。
- 客户端应用内更新读取的是 `latest-mac.yml` 与 `ZIP`。
- 这两条链路不能混淆。

## 命名规范

建议统一使用英文文件名，避免下载链路中的中文路径兼容问题。

推荐格式：

```text
YiyuThinkTankWorkbench-0.1.0-mac-arm64.dmg
YiyuThinkTankWorkbench-0.1.0-mac-arm64.zip
YiyuThinkTankWorkbench-0.1.0-mac-arm64.zip.blockmap
```

## 客户端读取约定

客户端至少需要知道：

- 当前渠道：`stable` 或 `beta`
- 当前版本号
- 更新源基地址

后续实现里应保持：

- `stable` 客户端默认只查 `stable/latest-mac.yml`
- `beta` 客户端默认只查 `beta/latest-mac.yml`

## 发布规则

### 发布到 beta

- 上传新 `DMG`
- 上传新 `ZIP`
- 上传新 `blockmap`
- 更新 `beta/latest-mac.yml`

### 发布到 stable

- 先确认该版本已在 `beta` 验证通过
- 上传新 `DMG`
- 上传新 `ZIP`
- 上传新 `blockmap`
- 更新 `stable/latest-mac.yml`
- 同步官网默认下载入口

## 回滚规则

回滚时不要删除整个目录，优先做：

- 重新上传上一版 `ZIP`
- 重新上传上一版 `blockmap`
- 让 `latest-mac.yml` 指回上一版
- 如需手动下载安装回滚，再把官网默认 `DMG` 链接切回上一版

## 安全与稳定性要求

- 更新源必须使用 HTTPS。
- 同一渠道目录内不要同时保留多个“当前版本”元数据文件。
- 不要让 `stable/latest-mac.yml` 指向 `beta` 产物。
- 不要在未签名或未 notarize 的状态下上传正式包。

## 当前阶段说明

- 当前文档先固定目录与产物规范。
- 真正的上传脚本与 CI 发布流程后续再接。
