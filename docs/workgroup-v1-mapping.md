# 总组 / 子组协作方案 V1 映射稿

## 目标

把“总组 + 子组协作”方案翻译成当前软件已经存在的组织模型，先做一个不新增并行真源、能尽快落地的 V1。

这份稿子的核心判断是：

- `总组` 先映射到当前的 `organization`
- `子组` 先映射到当前的 `department`
- `子组负责人` 先映射到当前的 `leaderUserId`
- `子组层级` 先映射到当前的 `parentDepartmentId`
- `子组协作关系` 先映射到当前的 `collaborationDepartmentIds`

只有当 V1 跑通后，仍然无法承接“跨部门临时组队”“一个人长期属于多个工作组”等需求时，再进入 V1.5，新增真正独立的 `workgroup` 实体。

## 结论

### 可以直接落地的部分

当前代码里，组织模型已经具备以下能力：

- 组织主对象
- 部门对象
- 部门负责人
- 部门父子层级
- 部门协作关系
- 部门周计划
- 组织级/部门级任务控制规则
- 汇报线与层级报告

对应代码：

- 组织对象：
  - [cloud_backend/app/models.py](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/cloud_backend/app/models.py)
  - `OrgProfileRecord`
- 子组对象：
  - [cloud_backend/app/models.py](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/cloud_backend/app/models.py)
  - `OrgDepartmentRecord`
- 组织模型总对象：
  - [cloud_backend/app/models.py](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/cloud_backend/app/models.py)
  - `OrgModelProfileRecord`
- 前端设置稿：
  - [src/shared/types.ts](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/src/shared/types.ts)
  - [src/renderer/components/settings/OrganizationSetupCenter.tsx](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/src/renderer/components/settings/OrganizationSetupCenter.tsx)
  - [src/renderer/components/settings/OrganizationModelSettingsPanel.tsx](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/src/renderer/components/settings/OrganizationModelSettingsPanel.tsx)

### 当前不能完整承接的部分

V1 还不适合直接支持：

1. 一个用户长期归属多个平级工作组
2. 跨部门临时组队后形成独立生命周期
3. 工作组独立权限体系，不依赖部门/组织角色
4. 工作组独立知识边界、独立记忆边界、独立复盘边界

这些都需要真正新增 `workgroup` 层，不能只靠部门模拟。

## 一、V1 映射关系

### 1. 总组

方案中的“总组”，在 V1 中映射到：

- `organization`

对应字段：

- `organizationId`
- `name`
- `leaderUserId`
- `managementUserIds`
- `annualGoal`
- `annualStrategy`
- `quarterPlans`

V1 语义：

- 总组是全局最高层的协作母体
- 它定义共同方向、组织目标和全局控制边界
- 所有子组默认从属于同一个总组

### 2. 子组

方案中的“子组”，在 V1 中映射到：

- `department`

对应字段：

- `id`
- `name`
- `leaderUserId`
- `parentDepartmentId`
- `mission`
- `businessContext`
- `teamContext`
- `quarterPlan`
- `collaborationDepartmentIds`

V1 语义：

- 子组是稳定协作单元
- 它可以是正式部门，也可以是“类部门化工作组”
- 只要这个组是长期存在、长期协作、长期承接任务，就先放进部门模型

### 3. 子组嵌套

方案中的“再设置一些子组一起协作”，V1 中先分两类：

#### 稳定层级

如果是稳定父子关系，比如：

- 咨询策略部
- 下面长期挂一个“募资方向组”

那就直接用：

- `parentDepartmentId`

#### 平级协作

如果是两个子组之间协作，不是上下级关系，比如：

- 客户服务部
- 科技发展部

共同推进一个方向

那就用：

- `collaborationDepartmentIds`

## 二、V1 页面如何表达

### 1. 组织搭建中心

V1 不新增独立“工作组中心”页面，先在：

- [src/renderer/components/settings/OrganizationSetupCenter.tsx](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/src/renderer/components/settings/OrganizationSetupCenter.tsx)

里完成表达。

需要新增或强化的不是新壳，而是现有字段的语义和展示：

- `部门名称`
  - 改为更宽的“部门 / 子组名称”语义
- `负责人`
  - 继续沿用
- `上级组`
  - 直接暴露 `parentDepartmentId`
- `协作组`
  - 直接暴露 `collaborationDepartmentIds`
- `部门使命`
  - 改成“子组职责 / 协作目标”

### 2. 组织树画布

当前已有组织树/组织搭建中心，V1 里可以直接表达：

- 总组在顶
- 子组在中层
- 有父子关系的组用树连接
- 平级协作组用弱连接或协作标签展示

不必另造一套“工作组树”。

### 3. 任务与日历

V1 里不要新加一个“选择工作组”的真源字段。

任务继续先挂：

- 组织任务
- 部门任务
- 项目任务

实现规则：

- 如果任务属于总组，不挂 `clientId`
- 如果任务属于某个子组，则用现有 `orgContext.departmentId`
- 如果任务涉及多个子组协作，不新增第二真源，先以主负责子组为准，再通过：
  - `support_requests`
  - `collaborationDepartmentIds`
  - `reportingLines`
  表达跨组协同

## 三、V1 对接口的影响

### 不需要新增的接口

当前这些组织模型接口已经能承载 V1：

- `GET /api/v1/settings/org-model/profile`
- `PUT/PATCH /api/v1/settings/org-model/profile`

前提是前端把下列字段真正用起来：

- `parentDepartmentId`
- `collaborationDepartmentIds`
- `leaderUserId`

### 建议新增的轻量能力

V1 只建议新增轻量辅助接口，不建议新增完整 workgroup API：

1. `GET /api/v1/settings/org-model/group-options`
   - 返回：
     - 总组
     - 全部子组
     - 父子层级
     - 协作关系
   - 主要给任务编辑器、组织树、任务过滤器用

2. `GET /api/v1/settings/org-model/group-graph`
   - 返回：
     - 树结构
     - 协作边
   - 用于组织树/组视图渲染

这两个接口本质上还是组织模型投影，不是新真源。

## 四、V1 对任务归属的影响

你刚提出的“默认任务应先属于组织，而不是某个项目”，和这个方案是完全一致的。

V1 的归属规则应该是：

1. 默认任务先属于总组
2. 只有明确命中项目/客户语境时，才属于项目
3. 只有明确指定子组时，才下沉到子组
4. 多组协作不新增并行真源，仍然只保留一个主负责组

所以 V1 的优先级应当是：

- 组织
- 子组
- 项目

而不是：

- 项目优先

## 五、V1 能解决什么问题

### 能解决

1. 一个总组下带多个稳定子组
2. 子组有负责人
3. 子组之间有协作关系
4. 任务能按组织/子组边界归属
5. 部门/子组可承接季度计划
6. 后续周判断、战略陪伴、管理报告可按总组/子组视角计算

### 不能彻底解决

1. 临时跨部门战队
2. 同一人长期属于多个独立工作组
3. 工作组独立记忆、独立知识边界
4. 工作组独立审批链
5. 工作组独立复盘层级

## 六、什么时候进入 V1.5

出现以下任一情况时，说明该从“部门模拟工作组”升级到独立 `workgroup`：

1. 同一个人需要长期稳定地归属多个组
2. 组不再等同于部门，而是跨部门常态化协作
3. 组需要独立管理自己的资料、事件线、周判断
4. 组需要独立的权限、审批和负责人体系
5. 组生命周期短于部门，但长于单项目

这时才建议新增：

- `workgroups`
- `workgroup_members`
- `workgroup_reporting_lines`
- `workgroup_task_links`
- `workgroup_memory_scope`

## 七、我对这套方案的最终判断

### 是否可落地

可以落地。

### 是否应该现在就新造一套 `workgroup`

不应该。

### 当前最稳路线

先把这套“总组 / 子组”方案翻译成现有：

- `organization`
- `department`
- `parentDepartmentId`
- `collaborationDepartmentIds`

先做 V1，把协作关系、责任归属、任务归属和计划承接跑顺。

### 何时再升级

只有当“子组已经明显不等于部门”时，再做 V1.5。

## 八、建议的实施顺序

1. 前端组织搭建中心显式支持：
   - 上级组
   - 协作组
   - 子组语义说明
2. 任务编辑器与任务详情显式支持：
   - 默认组织任务
   - 指定主负责子组
3. 周判断 / 战略陪伴按子组聚合
4. 管理视图支持：
   - 总组视角
   - 子组视角
5. 只有确认部门模型不够用时，再开独立 `workgroup`
