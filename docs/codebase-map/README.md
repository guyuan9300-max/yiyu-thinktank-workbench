# 代码库索引（codebase-map）

由 Claude 于 2026-05-11 接手时生成。**索引文件本身不包含源码，只包含结构信息**（行号、签名、路由表、文件清单等），用于在不读全部源码的前提下定位需要的代码。

## 索引文件清单

| 文件 | 大小 | 行数 | 覆盖范围 |
| --- | ---: | ---: | --- |
| `00-overview.md` | 2.5KB | 117 | 仓库全景：一级目录、语言分布、单文件 Top20、子模块状态 |
| `10-electron-main.md` | 12.0KB | 231 | Electron 主进程：main.ts / preload.ts 函数、IPC、生命周期 |
| `11-renderer-app-blocks.md` | 32.1KB | 503 | src/renderer/App.tsx 23k+ 行单文件按区块切分 |
| `12-renderer-misc-and-types.md` | 65.8KB | 1103 | src/renderer/ 其他文件 + src/shared/types.ts 类型清单 |
| `20-backend-routes-services.md` | 54.8KB | 849 | 本地后端 FastAPI 路由表 + services 模块清单 + models 类 |
| `21-cloud-backend.md` | 37.8KB | 484 | 云端 FastAPI 路由 + helper + 测试覆盖 |
| `30-scripts.md` | 9.8KB | 379 | scripts/ 打包/诊断脚本逐个用途 |
| `31-docs.md` | 7.5KB | 290 | docs/ 项目文档主题清单 |
| `40-mobile.md` | 12.3KB | 310 | mobile/ 子仓库浅索引（结构与文件清单，未深入代码） |

## 按问题类型查找

| 你的问题 | 去哪查 |
| --- | --- |
| 这个仓库一共多大？哪些目录是大头？ | `00-overview.md` |
| Electron 主进程在哪启动后端？IPC 怎么暴露的？ | `10-electron-main.md` |
| 登录页 / 注册页 / 任务列表 / 月历 在 App.tsx 哪一段？ | `11-renderer-app-blocks.md` |
| 某 API 客户端函数（login/register/...）在哪定义？ | `12-renderer-misc-and-types.md`（lib/api.ts 段） |
| 某共享类型 / interface 在 types.ts 哪一节？ | `12-renderer-misc-and-types.md`（types.ts 段） |
| 本地后端有哪些 API 路由？某个 service 在哪？ | `20-backend-routes-services.md` |
| 云端有哪些路由？测试覆盖哪些场景？ | `21-cloud-backend.md` |
| 打包某一步的脚本是哪个？怎么跑？ | `30-scripts.md` |
| 以前的发布流程 / 决策 / 设计在哪份文档？ | `31-docs.md` |
| 移动端有哪些屏幕 / 接口？ | `40-mobile.md`（浅索引） |

## 使用约定

1. 索引文件**没有源码**，遇到具体实现细节时，按行号回到源文件用 `sed -n 'AAA,BBBp' file` 精读那一段；
2. 索引文件不进上下文：用 `grep -n '关键词' docs/codebase-map/*.md` 反查行号，再针对性地读那一节；
3. 任何模块改动后，对应索引文件可以重生成（每个 L1 索引都由一段独立的 bash 生成，不依赖其他索引）；
4. mobile/ 子仓库只做了**浅索引**，需要改动移动端时再单独读。

## 关联文档

- `docs/project-handoff-2026-05-11.md`：上游交接文档（业务/产品意图）
- `docs/handoff-followup-2026-05-11.md`：Claude 接手评估（dirty 改动分析、§4 验收偏差、§3 高优先级 Bug、命令序列）

## 当前总量

索引文件总计：**237.5 KB** / **4313 行**（10 个文件）
