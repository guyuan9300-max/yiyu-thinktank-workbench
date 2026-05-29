# 开源准备审计记录

本文件记录转公开前必须处理的阻断项和检查项。

## 当前结论

仓库尚不能直接转公开。原因：

- GitHub 远端当前仍为私有仓库，默认分支为 `main`。
- Git 历史中出现过数据库路径：`app.db`、`cloud_backend/app.db`、`cloud_backend/app/dev.db`、`cloud_backend/yiyu_cloud.db`。已复核对应文件 blob 均为 0 字节空文件，未发现可读取数据库内容；已决定公开前采用“干净初始提交”重写公开历史，避免继续暴露旧路径痕迹。
- GitHub 侧已检查：当前仓库暂无 Actions runs、workflow artifacts 和 releases。
- 转公开操作尚未执行；必须等干净公开历史分支准备完成并由仓库管理员最终确认。

## 已在本分支处理

- 删除 tracked 的 `output/`、`tests/reports/`、内部协作文档和内部评估报告。
- 删除真实对象 golden fixtures 和内部 dogfood/eval 脚本。
- 补齐 README、Apache-2.0 许可证、贡献指南、安全说明、配置模板和公开开发文档。
- 移除开发脚本中的内部云端 IP 默认值。
- 脱敏测试样本、种子账号、示例邮箱和演示对象 ID。
- 当前工作树按以下关键字做过短扫描，未再命中：真实客户样例、真实人员名、历史内网 IP、旧真实 client id、内部测试邮箱域名。
- 当前工作树排除虚拟环境、构建产物后，未发现 `.db`、`.sqlite`、证书私钥、日志文件。
- 修复云端任务权限测试夹具的 `INSERT OR REPLACE` 外键副作用，避免测试重建组织规则时清空任务挂接。
- 修复云端任务兼容时间字段：显式更新 `dueDate` 时不再被旧 `scheduled_start_at` 覆盖。
- 已从当前清理后的工作树生成无父提交分支 `codex/open-source-public-root`；该分支用于后续替换公开历史，生成后仍需随最后修改重新刷新。

## 已验证

- `git diff --check`
- `npm run typecheck:renderer`
- `python3 -m compileall backend/app cloud_backend/app`
- `cd backend && uv run pytest -q tests/test_task_cloud_shadow_sync.py tests/test_v22_ingest_pipeline.py tests/test_v22_f18_f19_schema.py`
- `cd backend && uv run pytest -q tests/test_hub_client_sample.py tests/test_understanding_basic.py tests/test_understanding_enhanced.py tests/test_template_fill.py tests/test_weekly_overview_lines.py`
- `cd cloud_backend && uv run pytest -q tests/test_bootstrap_security.py tests/test_org_object_storage_config.py tests/test_auth_refresh.py tests/test_auth_tasks.py`
- GitHub 远端状态：`visibility=PRIVATE`、默认分支 `main`、Issues 已开启、Discussions 未开启、Actions runs 为 0、artifacts 为 0、releases 为 0。

## 当前验证风险

- 本分支为开源准备做了大量文本脱敏和内部材料删除，合并前需要人工 review 大 diff，确认没有误删仍需公开的开发文档或测试资产。
- 当前树疑似密钥模式扫描仍命中 `.env.release.example`、模拟种子、测试和前端配置表单文件；人工复核为占位字段、测试密码或 UI 字段名，没有发现真实密钥明文。公开前建议用 GitHub secret scanning / gitleaks 再跑一遍。
- 尚未创建干净初始提交；创建后需要重新跑当前树扫描和关键测试。

## 公开前仍需人工确认

- 用干净初始提交替换公开历史后，所有协作者需要重新克隆仓库，不能再沿旧历史直接增量同步。
- 轮换任何曾经进入历史的真实密钥或 token。
- 转公开后立即检查 GitHub secret scanning 和 security alerts。
