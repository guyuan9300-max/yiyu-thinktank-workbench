# RUNBOOK — cloud_backend P0/P1 修复部署

> 分支:`hotfix/cloud-p0p1`(基于 `origin/main` 4641944,不含 v2.2 重构)
> Commit:`f1c2247 fix(cloud): 3 个 P0 + 6 个 P1 安全/一致性`

---

## 改动覆盖

| 严重度 | 问题 | 修复方式 |
|---|---|---|
| **P0-3** | refresh_token TOCTOU race | module-level `threading.Lock` 包 rotate 全流程 |
| **P0-4** | `/org-ai-config/secret` + `/org-object-storage-config/secret` 任意成员可读明文 | `_require_auth` → `_require_admin` |
| **P0-5** | weekly review 跨租户 task 数据泄漏 | `_task_row_or_404` 加 `organization_id` 参数,review path 显式传 |
| **P1-7** | `approve_employee` 三步无事务 | `state.db.run_in_transaction` 包 UPDATE+DELETE+INSERT |
| **P1-9** | 5 处 HTTPException detail 暴露 `str(exc)` | 改 `logger.exception` + 通用 detail |

**留下批跟进**(同 transaction wrapping pattern,P1):
- P1-8 `mobile/knowledge-mirror/publish` batch loop 无事务
- P1-10 `_save_org_model_profile` 写 10+ 表无事务

---

## 探测到的云端事实

(沿用 `RUNBOOK_CLOUD_DEDUP.md` 里的已知事实)

| 项 | 值 |
|---|---|
| 主机 | `root@101.126.34.232`(hostname: `yiyu-cloud-collab-01`) |
| OS | Ubuntu 22.04 LTS x86_64 |
| 部署目录 | `/opt/yiyu/cloud-backend/`(owner: `yiyu:yiyu`,**非 git 仓库**) |
| 进程 | `uvicorn app.main:create_app --factory --host 127.0.0.1 --port 47831` |
| 进程管理 | systemd unit `yiyu-cloud-backend.service`(enabled, User=yiyu) |
| 健康端点 | `http://127.0.0.1:47831/health` → 200 |
| DB | `/var/lib/yiyu-cloud/cloud.db` |
| 历史备份目录 | `/opt/yiyu/cloud-backend/backups/` |

---

## Step 1 — 本地准备

```bash
# 1.1 在 hotfix worktree 内确认改动干净
cd /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench-cloud-p0p1
git status --short --branch
# 期望: ## hotfix/cloud-p0p1...origin/main + (无 untracked)

# 1.2 看 commit
git log --oneline -2
# 期望: f1c2247 fix(cloud): 3 个 P0 + 6 个 P1 安全/一致性 [B4-cloud]
```

---

## Step 2 — 备份云端 DB + 留 main.py 回滚副本

```bash
ssh root@101.126.34.232 bash <<'BACKUP'
set -euo pipefail
STAMP=$(date +%Y%m%d-%H%M%S)
DB=/var/lib/yiyu-cloud/cloud.db
BACKUP=/opt/yiyu/cloud-backend/backups/cloud-before-p0p1-${STAMP}.db

# SQLite VACUUM INTO 一致性快照
sudo -u yiyu sqlite3 "$DB" "VACUUM INTO '${BACKUP}'"
ls -lh "$BACKUP"
echo "✅ DB 备份完成: $BACKUP"

# 留 main.py 回滚副本
cp /opt/yiyu/cloud-backend/app/main.py /opt/yiyu/cloud-backend/app/main.py.bak-before-p0p1-${STAMP}
echo "✅ main.py 备份完成"
BACKUP
```

---

## Step 3 — 部署新 main.py(scp + 替换)

```bash
# 3.1 scp 新 main.py 到 .new
cd /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench-cloud-p0p1
scp cloud_backend/app/main.py root@101.126.34.232:/opt/yiyu/cloud-backend/app/main.py.new

# 3.2 ssh 上去切换 + 改 owner
ssh root@101.126.34.232 bash <<'DEPLOY'
set -euo pipefail
cd /opt/yiyu/cloud-backend
# 二次校验 syntax 后再 mv
sudo -u yiyu .venv/bin/python -c "import ast; ast.parse(open('app/main.py.new').read()); print('  ✓ syntax ok')"
mv app/main.py.new app/main.py
chown yiyu:yiyu app/main.py
ls -l app/main.py app/main.py.bak-before-p0p1-*
echo "✅ main.py 已替换"
DEPLOY
```

---

## Step 4 — 重启 + 健康检查

```bash
ssh root@101.126.34.232 bash <<'RESTART'
set -e
systemctl restart yiyu-cloud-backend
sleep 3

echo "=== systemd 状态 ==="
systemctl status yiyu-cloud-backend --no-pager | head -10

echo ""
echo "=== 健康端点 ==="
curl -sf http://127.0.0.1:47831/health && echo "  ✓ /health OK"

echo ""
echo "=== 进程在监听 ==="
ss -tlnp 2>/dev/null | grep 47831 && echo "  ✓ 47831 listening"

echo ""
echo "=== 启动 logs 最近 20 行 ==="
journalctl -u yiyu-cloud-backend --no-pager -n 20 --since "1 minute ago"
RESTART
```

---

## Step 5 — 关键路径验证(端到端)

```bash
# 用 admin token 试一次 (要先 login 拿 access_token)
# 这里只示范命令模板,实际 token 由 ssh 操作者准备
ADMIN_TOKEN="<管理员的 access_token>"
EMPLOYEE_TOKEN="<普通成员的 access_token>"

# 5.1 P0-4: 普通成员调 /org-ai-config/secret 必须 403
curl -sf -H "Authorization: Bearer $EMPLOYEE_TOKEN" \
  http://101.126.34.232/api/v1/settings/org-ai-config/secret \
  -o /tmp/_ai_secret.json -w "HTTP %{http_code}\n"
# 期望: HTTP 403

# 5.2 P0-4: 管理员调同 endpoint 应该 200
curl -sf -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://101.126.34.232/api/v1/settings/org-ai-config/secret \
  -o /tmp/_ai_secret_admin.json -w "HTTP %{http_code}\n"
# 期望: HTTP 200

# 5.3 P0-5: weekly review 提交一个其他 org 的 task_id 必须 404
# (需要先有一个跨 org 的 task_id 用于测试)
curl -X POST -H "Authorization: Bearer $EMPLOYEE_TOKEN" \
  -H "Content-Type: application/json" \
  http://101.126.34.232/api/v1/reviews/weekly \
  -d '{"weekLabel":"2026-W21","taskEntries":[{"taskId":"task_other_org_xxx"}]}' \
  -w "\nHTTP %{http_code}\n"
# 期望: HTTP 404 "Task not found" (不再泄漏跨 org 任务)
```

---

## Step 6 — DB-level 验证 SQL

```bash
ssh root@101.126.34.232 sudo -u yiyu sqlite3 /var/lib/yiyu-cloud/cloud.db <<'VERIFY'
.headers on
.mode column

-- 6.1 没有 dangling role binding (account approved 但无 role binding)
SELECT a.id, a.full_name, a.account_status
FROM employee_accounts a
LEFT JOIN employee_role_bindings b ON b.user_id = a.id
WHERE a.account_status = 'approved'
  AND b.id IS NULL;
-- 期望: 0 行(P1-7 修复后, approve_employee 不再留 dangling state)

-- 6.2 refresh_token 没有重复(P0-3 修复后,即便并发也不会双花)
SELECT refresh_token, COUNT(*) c
FROM auth_refresh_sessions
WHERE revoked_at IS NULL
GROUP BY refresh_token
HAVING c > 1;
-- 期望: 0 行
VERIFY
```

---

## 回滚方案

### 场景 A:部署后 health 500 / 关键功能崩

```bash
ssh root@101.126.34.232 bash <<'ROLLBACK'
set -euo pipefail
systemctl stop yiyu-cloud-backend

# 找最新 main.py 备份
LATEST_BAK=$(ls -t /opt/yiyu/cloud-backend/app/main.py.bak-before-p0p1-* | head -1)
echo "rolling back from: $LATEST_BAK"
cp "$LATEST_BAK" /opt/yiyu/cloud-backend/app/main.py
chown yiyu:yiyu /opt/yiyu/cloud-backend/app/main.py

systemctl start yiyu-cloud-backend
sleep 2
curl -sf http://127.0.0.1:47831/health && echo "  ✓ rolled back, /health OK"
ROLLBACK
```

### 场景 B:DB 状态被改坏(理论上不会发生,改动只动逻辑不动 schema)

```bash
ssh root@101.126.34.232 bash <<'DB_ROLLBACK'
set -euo pipefail
systemctl stop yiyu-cloud-backend
BACKUP=$(ls -t /opt/yiyu/cloud-backend/backups/cloud-before-p0p1-*.db | head -1)
sudo -u yiyu cp "$BACKUP" /var/lib/yiyu-cloud/cloud.db
sudo -u yiyu rm -f /var/lib/yiyu-cloud/cloud.db-wal /var/lib/yiyu-cloud/cloud.db-shm
systemctl start yiyu-cloud-backend
DB_ROLLBACK
```

---

## 时间预估

| 阶段 | 用时 |
|---|---|
| Step 1(本地准备) | 1 分钟 |
| Step 2(备份) | 1 分钟 |
| Step 3(scp + 替换) | 1 分钟 |
| Step 4(重启 + 健康) | 2 分钟(含 3s sleep) |
| Step 5(端到端验证) | 5 分钟(若有手准备 token) |
| Step 6(DB 验证) | 1 分钟 |
| **合计** | **~10 分钟** |

服务中断窗口:`systemctl restart` 大约 **2-3 秒**。

---

## 我没做的(按 Step 1 边界)

- ❌ 没部署到云端
- ❌ 没动云端 DB
- ❌ P1-8 / P1-10(单次失败概率低的 transaction wrapping)留下批
- ❌ 没改本地 backend(已在 `hotfix/audit-deep-p0p1` 单独 worktree 处理)
