# 官网版 Mac 发版流程

## 目标

- 首次安装通过官网下载安装包完成。
- 后续版本通过软件内更新提示完成下载与安装。
- 发版动作由受控构建机或 CI 完成，不在普通用户机器上执行。

## 适用范围

- 渠道：`stable`、`beta`
- 平台：macOS 官网分发版
- 当前不包含：Mac App Store

## 角色分工

- 产品/主线程：
  - 决定版本号
  - 决定发布渠道
  - 确认版本说明
- 构建负责人：
  - 触发构建
  - 处理签名与公证
  - 上传产物与更新元数据
- 验收负责人：
  - 在干净机器验证安装
  - 验证更新发现、下载、安装链路

## 发布前检查

### 代码与构建

- 主分支已合入本次版本需要的改动。
- `npm run build:main` 通过。
- `npm run build:renderer` 通过。
- 如本次涉及后端协议或数据结构，相关测试已通过。

### 打包与凭据

- `Developer ID Application` 证书可用。
- notarization 凭据可用。
- `build-resources/icon.icns` 已准备。
- `build-resources/entitlements.mac.plist` 与 `build-resources/entitlements.mac.inherit.plist` 已准备。
- 下载域名与对象存储可访问。
- 本机若只是做功能自测，请改用 `npm run dist:mac-local`，不要拿它替代正式官网发布包。

签名、公证和申请材料详见：

- `docs/developer-id-signing-notarization.md`

### 版本信息

- 版本号已写入 `package.json`。
- 已确定发布渠道：
  - `stable`
  - `beta`
- 已写好更新说明。

## 构建产物要求

每次发布至少要生成：

- `DMG`
- `ZIP`
- `latest-mac.yml`
- 对应 `blockmap`

说明：

- `DMG` 给官网首次下载安装使用。
- `ZIP + latest-mac.yml + blockmap` 给应用内更新使用。

## 发布步骤

1. 确认本次版本号与发布渠道。
2. 在受控构建机或 CI 执行 macOS 构建。
3. 对 `.app` 与产物完成签名。
4. 完成 notarization 并确认通过。
5. 将产物上传到对应渠道目录。
6. 更新官网手动下载入口：
   - `stable` 发布时更新官网主下载入口
   - `beta` 仅更新测试版入口
7. 在干净机器完成安装与启动验证。
8. 用旧版本客户端验证：
   - 可发现新版本
   - 可完成下载
   - 可完成重启安装
9. 记录发版日志。

## 发布后验证

### 手动安装验证

- 从官网下载安装 `DMG`
- 拖入 `~/Applications/益语智库自用平台.app`
- 首次启动成功
- 本地数据目录正常创建

### 唯一安装入口规则

- 日常运行与验证只认一个入口：
  - `~/Applications/益语智库自用平台.app`
- 不要直接从这些位置长期启动：
  - `dist/mac-arm64/*.app`
  - `~/Library/Application Support/yiyu-thinktank-workbench/runtime/local-electron/*.app`
  - `/Applications/益语智库.app`
- 如果本机做本地封装验证，先执行：
  - `npm run dist:mac-local`
  - `npm run install:mac-local`
- `npm run install:mac-local` 会把旧版本自动归档到：
  - `~/Library/Application Support/yiyu-thinktank-workbench/runtime/install-backups/`
- 如发现多个同名或旧名字应用并存，以设置页“版本与更新”中的“安装入口自检”为准，定位并清理旧入口。

### 应用内更新验证

- 使用上一版本客户端启动
- 能看到新版本提示
- 能开始下载
- 下载后能触发“重启并安装”
- 升级后版本号正确
- 升级后本地数据不丢失

## 渠道规则

### beta

- 用于内部测试与小范围试装。
- 允许更快发布。
- 问题可接受，但必须可回滚。

### stable

- 只在 `beta` 验证通过后发布。
- 官网默认下载入口始终指向 `stable`。

## 版本说明最小模板

- 版本号
- 发布日期
- 本次重点改动
- 已知限制
- 回滚说明（如有）

## 禁止事项

- 不要在普通用户电脑上执行签名、公证和上传。
- 不要发布未完成签名或未完成 notarization 的安装包。
- 不要只上传 `DMG` 而遗漏更新元数据。
- 不要把 `beta` 包误放进 `stable` 目录。
- 不要在 `npm run dist:mac` 前置检查失败时绕过脚本继续发布；那样产出的包会继续出现“闪一下就退出”。
- 不要把 `dist/mac-arm64/*.app` 直接当作长期使用入口；那样很容易继续出现“装错包/开错包”。

## 当前阶段说明

- 当前文档先固化发布纪律。
- 真正的自动更新引擎与发布流水线仍在后续阶段接入。
