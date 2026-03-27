# Codex 协作接入说明

这份文档是写给另一个 Codex 的。目标不是解释背景，而是让对方能够：

1. 从 GitHub 拉下这个项目  
2. 在本机成功打开并运行这个软件  
3. 在自己的分支上安全协作开发  
4. 把结果通过 GitHub PR 回到主线  

请严格按下面步骤执行，不要擅自扩大操作范围。

## 1. 目标项目

- 项目名称：`yiyu-thinktank-workbench`
- 仓库地址（由对接人补充）：
  - SSH：`git@github.com:guyuan9300-max/yiyu-thinktank-workbench.git`
  - HTTPS：`https://github.com/guyuan9300-max/yiyu-thinktank-workbench.git`
- 仓库类型：`private`
- 这是唯一需要操作的项目目录

不要操作更大的工作区根目录。  
你本地应该进入的目录是：

```bash
cd yiyu-thinktank-workbench
```

## 2. 项目结构

这是一个桌面优先项目，包含 4 层：

- `src/`
  - Electron 主进程 + preload + React 前端壳
- `backend/`
  - 本地桥接后端
  - 负责文件系统、客户工作台、知识底座、本地 AI 调用
- `cloud_backend/`
  - 共享业务后端
  - 负责账号、审批、任务协作、层级视野
- `build-resources/`
  - 桌面打包资源

## 3. 本机环境要求

请先确认本机满足以下要求：

- `Node.js >= 20`
- `Python >= 3.11`
- `uv`
- macOS 环境优先

如果任一前置环境缺失，请先补环境，再继续。

## 4. 克隆项目

优先使用 SSH。

### 方式 A：SSH

```bash
git clone git@github.com:guyuan9300-max/yiyu-thinktank-workbench.git
cd yiyu-thinktank-workbench
```

### 方式 B：HTTPS

```bash
git clone https://github.com/guyuan9300-max/yiyu-thinktank-workbench.git
cd yiyu-thinktank-workbench
```

## 5. 安装依赖

### 5.1 安装前端 / Electron 依赖

```bash
npm install
```

### 5.2 安装本地 Python backend 依赖

```bash
cd backend
uv sync
cd ..
```

### 5.3 安装 cloud backend 依赖

```bash
cd cloud_backend
uv sync
cd ..
```

## 6. 启动项目

### 开发态启动

这是默认启动方式：

```bash
npm run dev
```

它会同时启动：

- Vite renderer
- Electron main 编译监听
- Electron 桌面窗口

### 本地安装版启动

如果需要打包并安装本地 app：

```bash
npm run dist:mac-local
npm run install:mac-local
npm run start
```

## 7. 启动后最小验证

启动成功不等于能用。  
你必须至少做一次最小人工验证。

请完成下面检查：

1. Electron 窗口可以正常打开
2. 左侧或顶部导航可以切换主要模块
3. 前端页面没有整页白屏
4. 本地 backend 没有直接异常退出
5. 至少点通一条核心路径，不要只停在首页

如果没有做到这一步，不要回报“已经跑起来了”。

## 7.1 本地开发可用登录账号

当你通过项目自带的 Electron 启动链启动本地 app 时，中心后端会注入固定的开发 seed 账号，方便协作调试。

你可以直接使用下面任一账号登录：

- 管理员账号：
  - 邮箱：`admin@yiyu-system.com`
  - 密码：`Admin123!`
- 管理员账号：
  - 邮箱：`guyuan@klngo.org`
  - 密码：`Guyuan31`

说明：

- 这是本地开发协作口令，用于同事拉代码后快速登录验证
- 如果你单独手工启动 `cloud_backend` 而不是通过项目自带桌面启动链，可能需要自己显式设置同名环境变量
- 不要把这套本地开发口令拿去当线上或公网环境口令

## 8. Git 协作规则

不要直接在 `main` 上开发。

### 8.1 同步主线

```bash
git checkout main
git pull --ff-only
```

### 8.2 创建自己的分支

```bash
git checkout -b feature/<your-feature-name>
```

如果是修 bug，也可以：

```bash
git checkout -b fix/<your-bug-name>
```

### 8.3 开发完成后提交

```bash
git add .
git commit -m "<clear-commit-message>"
git push -u origin <your-branch-name>
```

### 8.4 通过 PR 合并

不要直接 push 到 `main`。  
请创建 Pull Request，把你的分支合并回 `main`。

## 9. 不要提交的内容

仓库里已经有 `.gitignore`，但你仍然需要主动检查。

不要提交：

- `.env`
- 本地数据库
- `node_modules`
- `dist`
- `build`
- 临时文件
- 日志
- 本地 agent / codex 私有配置

如果你看到新的本地产物，请先确认是否应该被忽略。

## 10. 开发约束

请遵守下面约束：

- 不要改仓库边界，把别的工作区内容混进来
- 不要把整个 workspace 根目录当项目仓
- 不要提交密钥、token、密码
- 不要擅自重写 main 分支历史
- 不要跳过人工验证

## 11. 遇到问题时的排查顺序

如果项目打不开，请按这个顺序排查：

1. `npm install` 是否成功
2. `backend/uv sync` 是否成功
3. `cloud_backend/uv sync` 是否成功
4. `npm run dev` 是否有首个报错
5. 是 renderer、Electron 还是 Python backend 报错

不要只说“打不开”。  
请直接贴出第一条有效报错。

## 12. 你需要回报的内容

完成接入后，请按下面格式回报：

```md
## 接入结果

- clone：成功 / 失败
- npm install：成功 / 失败
- backend uv sync：成功 / 失败
- cloud_backend uv sync：成功 / 失败
- npm run dev：成功 / 失败
- Electron 窗口：已打开 / 未打开
- 最小人工验证：已完成 / 未完成

## 当前阻塞

- <如果有报错，贴第一条关键报错>

## 下一步

- <你准备在哪个分支上开始改什么>
```

## 13. 如果你已经开始开发

开始改代码前，请先：

```bash
git status
git branch
```

确认：

- 当前不在 `main`
- 当前工作区没有意外脏文件

## 14. 备注

这个项目是内部协作桌面应用，仓库应长期保持 `private`。  
如果你发现仓库权限、远端地址、分支保护或 push 权限有问题，请先报告，不要自行绕过。
