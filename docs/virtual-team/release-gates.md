# Release Gates v3

## Current Topic

日历与任务判断系统 P0 + 虚拟项目组岗位重构

## Gate Checklist

### Gate 0: Team Model
- [x] 角色是否为真实软件岗位，而非抽象方法论人格
- [x] 是否已有外部模式扫描 owner
- [x] 外部模式扫描结果是否已经写入 `external-pattern-scans.md`

### Gate 1: Truth Source
- [x] 已识别现有底座真源
- [x] 已识别现有 judgment objects
- [ ] 已明确所有旧 heuristics 的保留/退役清单

### Gate 2: Spec Convergence
- [x] 已完成 reality audit
- [x] 已完成 external pattern scan
- [x] 已完成 strategy debate
- [x] 已形成 active plan
- [ ] 关键冲突已全部裁决

### Gate 3: Implementation Safety
- [ ] 未形成第二 judgment 真源
- [ ] 未形成前后端两套 schema
- [ ] 降级规则已统一

### Gate 4: QA & Release
- [ ] QA Engineer 已做阻塞检查
- [ ] Platform Engineer 已复核运行和发布风险
- [ ] blocking issues 全部关闭

## Current Passed Items

- 虚拟项目组的角色边界已经切到真实软件岗位
- Loop 1 审计已落文档
- 外部模式扫描第一版已落文档
- 路线辩论已落文档
- P0 当前范围已继续收敛到任务与周判断系统

## Current Blockers

1. 当前仓库已有 judgment objects，但共享链仍未完全统一  
2. `projectContext` 与 `event line memory` 仍混用  
3. 旧 heuristics 清单还没显式列出  
4. 任务详情 AI 面板与周判断仍未确认使用同一后端装配入口  

## Next Round Scope

下一轮只允许进入：
1. 旧 heuristics 清单
2. judgment contract 代码收口
3. 任务详情与周判断共用链的最小实现
4. QA 回归和 release gate 更新

不允许扩散到：
- 全战略陪伴重写
- 全客户工作台改版
- 新 knowledge engine
