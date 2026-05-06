# 组织与权限 — 新壳设计文档

> 给 Jeana 的完整壳搭建说明。搭完壳后我们再接通后端数据。

---

## 一、背景

当前"系统设置 → 组织与权限"模块太重（4 个 tab、十几个表单字段、汇报线、任务控制规则等），用户看到就想关掉。

新版目标：**2 分钟完成组织搭建，10 秒完成成员加入**。

---

## 二、整体架构

新模块替换现有的 `OrganizationSetupCenter` 组件，放在同样的设置入口下。

### 文件位置

```
src/renderer/components/settings/OrgPermissionShell.tsx   ← 新组件（主文件）
```

### 在 App.tsx 中的挂载位置

替换现有的 `settingsSection === 'system_admin'` 渲染区域（约 App.tsx:14577 行）。

### Props 接口

```typescript
type OrgPermissionShellProps = {
  canEdit: boolean;           // 是否有编辑权限（管理员）
  currentUserId: string;      // 当前登录用户 ID
};
```

> 先不传后端数据，壳里面用 mock 数据。

---

## 三、页面结构（两个视图）

整个模块只有两个视图，用一个 state 切换：

```typescript
type ShellView = 'tree' | 'codes';
const [activeView, setActiveView] = useState<ShellView>('tree');
```

---

## 四、视图 1：组织架构树（默认视图）

### 4.1 顶部标题栏

```
┌─────────────────────────────────────────────────────────────┐
│  组织架构                                     [查看邀请码]   │
│  在这里搭建组织结构，最多支持三层。                            │
└─────────────────────────────────────────────────────────────┘
```

- 标题：`组织架构`
- 副标题：`在这里搭建组织结构，最多支持三层。`
- 右上角按钮：`查看邀请码` → 切换到视图 2

### 4.2 横向树主体

**核心交互：横向展开的组织架构树，最多 3 层。**

布局方向：**从左到右**（不是从上到下）。

```
                    ┌──────────┐
                ┌───┤ 项目经理  │
                │   └──────────┘
 ┌────────┐     │   ┌──────────┐
 │ 咨询部  ├─────┼───┤ 分析师   │
 │ 👤 张三 │     │   └──────────┘
 └────┬───┘     │   ┌──────────┐
      │         └───┤ + 添加岗位│
      │             └──────────┘
 ┌────┴────────┐
 │             │
 │  益语智库    ├────
 │             │    ┌────────┐     ┌──────────┐
 └─────────────┘    │ 运营部  ├─────┤ 内容编辑  │
                    │        │     └──────────┘
                    └────┬───┘     ┌──────────┐
                         │        ┤ + 添加岗位 │
                         │         └──────────┘
                    ┌────┴───┐
                    │+ 添加部门│
                    └────────┘
```

### 4.3 节点样式

#### 第 1 层 — 组织节点（根节点，只有 1 个）

```
容器：rounded-2xl border-2 border-[#5B7BFE]/30 bg-gradient-to-br from-[#eef3ff] to-white
      px-5 py-4 min-w-[160px] shadow-sm
文字：text-[15px] font-bold text-gray-900（组织名称）
图标：Building2（lucide-react），放在名称左侧
交互：点击名称 → inline 编辑（input 替换 span）
      按 Enter 或 blur 保存
```

#### 第 2 层 — 部门节点

```
容器：rounded-2xl border border-gray-200 bg-white px-4 py-3 min-w-[140px] shadow-sm
文字：text-[13px] font-bold text-gray-800（部门名称）
副文字：text-[11px] text-gray-400 mt-0.5（负责人名称，如 "👤 张三"）
图标：Users（lucide-react）
交互：点击名称 → inline 编辑
      hover → 右上角出现 ✕ 删除按钮（text-gray-300 hover:text-rose-500）
      点击负责人区域 → 出现简单的文本输入（输入负责人名称）
```

#### 第 3 层 — 岗位节点

```
容器：rounded-xl border border-gray-100 bg-gray-50/80 px-3 py-2 min-w-[100px]
文字：text-[12px] font-medium text-gray-600
交互：点击名称 → inline 编辑
      hover → 右侧出现 ✕ 删除按钮
```

#### 添加按钮节点

```
容器：rounded-xl border border-dashed border-gray-200 bg-white/60 px-3 py-2
      hover:border-[#5B7BFE]/40 hover:bg-[#5B7BFE]/5 cursor-pointer transition
文字：text-[12px] text-gray-400 hover:text-[#5B7BFE]
图标：Plus（lucide-react，size=14）
内容：
  第 2 层添加："+ 添加部门"
  第 3 层添加："+ 添加岗位"
```

### 4.4 连接线

- 使用 SVG `<path>` 画直角折线（非曲线）
- 线条颜色：`stroke-gray-200`，宽度 `1.5px`
- 从父节点右侧中点 → 水平延伸 → 垂直到子节点 → 水平连入子节点左侧中点

### 4.5 交互规则

| 操作 | 行为 |
|------|------|
| 点击组织名称 | inline 编辑，blur/Enter 保存 |
| 点击部门名称 | inline 编辑，blur/Enter 保存 |
| 点击岗位名称 | inline 编辑，blur/Enter 保存 |
| 点击"+ 添加部门" | 在部门列表末尾插入新节点，自动 focus 到名称输入 |
| 点击"+ 添加岗位" | 在该部门的岗位列表末尾插入新节点，自动 focus |
| hover 部门/岗位 | 显示删除按钮 |
| 点击删除按钮 | 直接删除（无确认弹窗；如果该部门下有岗位，则提示"先删除岗位"） |
| 点击负责人区域 | 展开文本输入，填写/修改负责人名称 |

### 4.6 Mock 数据结构

```typescript
type OrgNode = {
  id: string;
  name: string;
  type: 'org' | 'department' | 'position';
  leadName?: string;         // 仅部门有：负责人名称
  children: OrgNode[];
};

// 初始 mock
const MOCK_TREE: OrgNode = {
  id: 'org-1',
  name: '益语智库',
  type: 'org',
  children: [
    {
      id: 'dept-1',
      name: '咨询部',
      type: 'department',
      leadName: '张三',
      children: [
        { id: 'pos-1', name: '项目经理', type: 'position', children: [] },
        { id: 'pos-2', name: '分析师', type: 'position', children: [] },
      ],
    },
    {
      id: 'dept-2',
      name: '运营部',
      type: 'department',
      leadName: '李四',
      children: [
        { id: 'pos-3', name: '内容编辑', type: 'position', children: [] },
        { id: 'pos-4', name: '社群运营', type: 'position', children: [] },
      ],
    },
  ],
};
```

---

## 五、视图 2：邀请码管理

点击"查看邀请码"后切换到此视图。

### 5.1 顶部

```
┌─────────────────────────────────────────────────────────────┐
│  ← 返回架构图        邀请码管理                               │
│                      把邀请码发给对应部门的人，输入即可加入。    │
└─────────────────────────────────────────────────────────────┘
```

- 左上角：`← 返回架构图`（点击切回视图 1）
- 标题：`邀请码管理`
- 副标题：`把邀请码发给对应部门的人，输入即可加入。`

### 5.2 邀请码卡片列表

每个部门一张卡片，竖向排列：

```
┌────────────────────────────────────────────────┐
│  咨询部                                         │
│  负责人：张三                                    │
│                                                │
│  邀请码    ORG1-ZX01-A7C3         [复制]         │
│                                                │
│  岗位：项目经理、分析师                           │
│  已加入：2 人                                    │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│  运营部                                         │
│  负责人：李四                                    │
│                                                │
│  邀请码    ORG1-YY02-D9K4         [复制]         │
│                                                │
│  岗位：内容编辑、社群运营                         │
│  已加入：3 人                                    │
└────────────────────────────────────────────────┘
```

### 5.3 卡片样式

```
容器：rounded-2xl border border-gray-100 bg-white p-5 shadow-sm
部门名称：text-[15px] font-bold text-gray-900
负责人：text-[12px] text-gray-500 mt-0.5

邀请码区域：
  标签：text-[11px] font-semibold uppercase tracking-widest text-gray-400
  码值：text-[18px] font-mono font-bold text-[#5B7BFE] tracking-[0.15em]
        bg-[#5B7BFE]/5 rounded-xl px-4 py-2 inline-block
  复制按钮：text-[12px] text-[#5B7BFE] hover:underline cursor-pointer
           （点击后变"已复制 ✓"，2秒后恢复）

岗位列表：text-[12px] text-gray-500 mt-3
已加入人数：text-[12px] text-gray-400
```

### 5.4 邀请码生成规则（Mock）

```typescript
// 格式：组织前缀（4字符）- 部门前缀（2字符）+ 序号（2位数字）- 组织/部门校验码
// 示例：ORG1-ZX01-A7C3, ORG1-YY02-D9K4
// 具体前缀和校验码来自当前组织与部门数据，不再绑定固定机构或固定部门。
```

---

## 六、状态管理

壳阶段所有状态都是组件内部 `useState`，不需要接 API。

```typescript
// 组织架构树数据
const [tree, setTree] = useState<OrgNode>(MOCK_TREE);

// 当前视图
const [activeView, setActiveView] = useState<'tree' | 'codes'>('tree');

// 正在编辑的节点 ID（用于 inline 编辑）
const [editingNodeId, setEditingNodeId] = useState<string | null>(null);

// 编辑中的临时文字
const [editingText, setEditingText] = useState('');
```

---

## 七、不需要实现的东西

壳阶段跳过：

- ❌ 后端 API 调用
- ❌ 实际的邀请码生成 / 校验
- ❌ 员工加入流程
- ❌ 权限控制逻辑
- ❌ 保存/持久化
- ❌ 备份 / 演示数据 / 活动日志（这些保留在别处，不在新壳里）
- ❌ 动画 / 过渡效果（后续加）

---

## 八、技术约束

1. **单文件组件** — 整个壳放在一个 `OrgPermissionShell.tsx` 里，内部可以拆 sub-component 但不要拆文件
2. **只用项目已有依赖** — React、lucide-react、Tailwind CSS，不要引入新库
3. **SVG 连接线** — 用一个 `<svg>` 覆盖层 + `<path>` 画线，通过 `useRef` + `useLayoutEffect` 计算节点位置
4. **响应式** — 横向树在窄屏时允许水平滚动（`overflow-x-auto`）
5. **Tailwind 类名风格** — 与项目一致：
   - 圆角：`rounded-2xl`、`rounded-3xl`
   - 主色：`#5B7BFE`
   - 文字大小：`text-[12px]`、`text-[13px]`、`text-[15px]`
   - 卡片：`bg-white border border-gray-100 rounded-2xl shadow-sm`

---

## 九、壳完成后的验证标准

搭完壳后，应该能看到：

- [ ] 默认显示一棵横向的 mock 组织树（益语智库 → 2个部门 → 每个部门2个岗位）
- [ ] 点击任何名称可以 inline 编辑
- [ ] 点"+ 添加部门"能在树上新增一个部门节点
- [ ] 点"+ 添加岗位"能在对应部门下新增岗位节点
- [ ] hover 节点显示删除按钮，点击可删除
- [ ] 点"查看邀请码"切到邀请码视图，显示每个部门的邀请码卡片
- [ ] 点"复制"显示"已复制 ✓"反馈
- [ ] 点"返回架构图"切回树视图
- [ ] 连接线正确连接父子节点

---

## 十、参考截图描述

### 树视图整体效果

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  组织架构                                            [查看邀请码]    │
│  在这里搭建组织结构，最多支持三层。                                    │
│                                                                     │
│  ┌─────────────┐      ┌──────────┐      ┌──────────┐               │
│  │  🏢          │      │ 👥 咨询部 │──────│ 项目经理  │               │
│  │  益语智库     │──────│ 👤 张三   │      ├──────────┤               │
│  │             │      └──────────┘      │ 分析师    │               │
│  └─────────────┘      ┌──────────┐      ├──────────┤               │
│                       │ 👥 运营部 │      │+ 添加岗位 │               │
│                       │ 👤 李四   │      └──────────┘               │
│                       └──────────┘      ┌──────────┐               │
│                       ┌──────────┐      │ 内容编辑  │               │
│                       │+ 添加部门 │      ├──────────┤               │
│                       └──────────┘      │ 社群运营  │               │
│                                         ├──────────┤               │
│                                         │+ 添加岗位 │               │
│                                         └──────────┘               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

整体背景色与系统设置一致（`bg-[#F9FAFB]`），树居中显示，左右留 padding。
