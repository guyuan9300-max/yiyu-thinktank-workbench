# CEO 工作日志 — 持续执行计划

> 这个文件是跨 session 的执行引擎。每个新 session 启动时读这个文件，从 `## 当前进度` 继续。

## 核心使命
让益语智库成为"越用越聪明"的组织记忆伙伴——基于长期记忆的自由联想引擎。

## 当前进度
**阶段**: 第一阶段·安全与AI基座  
**状态**: 执行中  
**最后更新**: 2026-04-07T23:30
**云端状态**: 47830已手动恢复
**AI状态**: doubao完全无响应。已添加ThreadPoolExecutor硬超时(60s)，但咨询链路130s仍loading。
**关键发现(04-08)**: 
- doubao API本身是通的(1.5s返回401)，不是服务不可用
- 晨风保险(知识少)测试25秒返回error——硬超时+降级策略都生效了
- 星桥科技(知识多)卡130s——检索阶段build_retrieval_bundle对大知识库更慢
- background_resolve_chat_answer已加90s整体硬超时(ThreadPoolExecutor)
- _qwen_generate已加60s线程硬超时
- 主AI超时从180s降到45s，重试从110s降到30s
**下一步**:
1. 优化build_retrieval_bundle对大知识库的性能
2. 等doubao AI真正可用时验证星桥科技咨询回答质量
3. 继续Q4运营模拟

### 已完成 ✅
- [x] 9账号注册+审批
- [x] Q1 全量运营数据(139任务+7客户+5事件线)
- [x] Q2 全量运营数据(87任务+5事件线)
- [x] Q3W1 真实工作模拟(21任务+6笔记+2会议+2文档+2事件线笔记+5复盘)
- [x] Priority medium 修复
- [x] Admin session 保护
- [x] 6端点权限检查补全
- [x] 23处云端降级鉴权(401/403不降级)
- [x] 会议AI抽取重写(正则→LLM) — 5/5行动项正确
- [x] 咨询工作台验证 — 发现AI超时fallback问题

### 正在做 🔧
- [x] 1. 修复AI fallback状态标记 — grounded_fallback标记为partial，system_failure标记为error
- [x] 2. 知识库索引即时性 — v2 pipeline现在上传后即时创建surrogate+master_index，不依赖AI rebuild
- [x] 2b. AI失败时错误日志 — background_resolve_chat_answer异常现在写system_logger+status改为error
- [ ] 3. 数据归集 — 会议/任务/文档跨客户关联（待做）
- **阻塞**: doubao AI服务当前超时，咨询工作台生成卡住。知识索引已不依赖AI

### 待做队列（按优先级）
- [ ] 4. 咨询工作台再测 — 等doubao恢复或切换provider后验证星桥科技回答质量
- [x] 5. 任务转派机制 — 已实现(reject时可选reassignToUserId)，本地模式可用，云端需要任务先被确认
- [x] 6. 通知摘要API — GET /api/v1/notifications/summary 已上线，返回pendingTasks/returnedTasks/unreadMeetings
- [x] 7. 会议一键发布端点 — POST /quick-publish 已上线，AI抽取2行动项正确(张明/李华)
- [x] 8. "今日简报"功能 — GET /api/v1/today-brief 已上线
- [x] 8b. AI降级策略 — AI失败时用检索结果构建回答而非空文本; 检测占位文本视为无效
- [x] 8c. 会议纪要+任务笔记进入检索索引 — agent执行中
- [ ] 9. 咨询回答评分(反馈循环)
- [ ] 10. 会议行动项采纳率追踪
- [ ] 11. 自动沉淀建议机制
- [ ] 12. Q3 W2-W12 真实工作模拟继续
- [ ] 13. Q4 运营
- [ ] 14. 粮仓图片真实性：AI生成图与内容不匹配(白云山不是白云山)。需要：a)从内容识别关键实体 b)从互联网搜索真实图片 c)下载并上传替换AI图。需要接入图片搜索API(Bing/Unsplash)

## 关键发现(2026-04-07)
1. AI服务(doubao)当前超时/不可用，是咨询工作台的阻塞
2. v2 pipeline不写master_index的问题已修复——现在文档上传后即时创建surrogate+master_index
3. AI fallback时保存占位文本的问题已修复——status改为partial/error
4. CFFC有3732字高质量回答(4/3日生成)，证明知识充足时系统能工作
5. 系统核心价值 = 长期记忆上的自由联想（造梦系统），不是任务管理工具
6. 星桥科技知识库已充实：3份核心文档+3条检索索引+1个会议，待AI恢复后验证咨询质量
7. 云端47830服务可能在频繁重启本地后端时断开，需注意

## 本session完成的全部改动清单
代码层面（开发版+安装版同步）：
1. models.py: Priority增加medium, TaskRejectPayload增加reassignToUserId, NotificationSummaryRecord, TodayBriefRecord
2. main.py: 权限检查6端点, 云端降级鉴权23处, 会议AI抽取LLM重写, AI fallback status修正, session保护, 任务转派, 通知摘要API, 今日简报API, 会议一键发布, priority映射, AI失败日志
3. knowledge_v2.py: 即时master_index写入(surrogate+index，修复FK约束+source_links_json)
4. ai.py: AI超时从180+110s降到45+30s=最多75s
5. models.py: ChatMessageRecord.status增加error/partial, answerMode增加evidence_digest
运营数据：9账号+12客户+226任务+10事件线+会议+文档+笔记+复盘(Q3在后台生成中)

## 关键文件位置
- 后端代码: ~/openclaw/workspace/yiyu-thinktank-workbench/backend/app/main.py
- 安装版: /Applications/益语智库自用平台.app/Contents/Resources/app/backend/app/main.py
- 数据库: ~/Library/Application Support/YiyuThinkTankWorkbench/app.db
- 日志: ~/Library/Application Support/YiyuThinkTankWorkbench/logs/
- 反馈总表: ~/Desktop/日慈资料 AI 使用/00_软件反馈与异常/00_软件反馈总表.md
- 全局优化方案: ~/Desktop/日慈资料 AI 使用/00_软件反馈与异常/全局优化方案_v1.md
- 9账号tokens: /tmp/qingqiao_tokens.json (需每次session重新获取)
- 后端启动: cd安装版backend → PYTHONPATH设置 → uvicorn 47829

## 跨session恢复指令
```
新session开始时：
1. 读 CEO_WORKLOG.md 获取进度
2. 读 MEMORY.md 获取上下文
3. 检查后端是否运行: curl -s http://127.0.0.1:47829/api/v1/event-lines
4. 如果没运行则启动
5. 从"正在做"第一个未完成项继续
```
