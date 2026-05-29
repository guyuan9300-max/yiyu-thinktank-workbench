"""organization 模块 schema · 4 张 mirror 表 + readonly 触发器

镜像火山云 cloud_backend 4 张表(经过裁剪,只保留本地用得到的字段):
- mirror_organizations         ← organizations
- mirror_departments           ← org_departments
- mirror_users                 ← employee_accounts(去掉敏感字段:password_hash / phone_verified_at 等)
- mirror_client_related_users  ← client_related_users

设计原则:
1. 表名加 `mirror_` 前缀,提醒"这是云端镜像,不能本地编辑"
2. 每张表带 `synced_from_cloud_at TEXT NOT NULL` 标记同步时间
3. 每张表加 readonly 触发器:
   - 业务代码 INSERT/UPDATE 时未刷新 synced_from_cloud_at → RAISE
   - 这是软约束(sync 程序刷新就能写),但能拦截绝大多数手抖误写
4. 不加 FK 到本地业务表(clients 等):FK 双向强约束,sync 顺序错就 cascade 崩;
   一致性靠 OrganizationDirectory.get_*() 容错 + 后台 reconcile job 兜底
5. 字段集是云端字段的子集,不存:
   - 敏感字段(password_hash / phone_verified_at / approved_by 等内部审计字段)
   - 派生字段(department_name 这种,会过期 → 实时 JOIN mirror_departments)
6. Mirror 表不进 cloud sync(sync 字段三元组不要):本身就是 cloud 来的
"""

# 跟外部约定的版本号(改 schema 时递增)
ORGANIZATION_SCHEMA_VERSION = 1

MIRROR_TABLE_NAMES = (
    "mirror_organizations",
    "mirror_departments",
    "mirror_users",
    "mirror_client_related_users",
)


SCHEMA_SQL = """
-- ══════════════════════════════════════════════════════════════════════════════
-- organization 模块 · cloud mirror 表
-- v2.1 SSOT:这些表的真相在火山云,本地只读缓存
-- ══════════════════════════════════════════════════════════════════════════════

-- 1) mirror_organizations:组织(目前只有 org_yiyu_default)
CREATE TABLE IF NOT EXISTS mirror_organizations (
    id                     TEXT PRIMARY KEY,
    name                   TEXT NOT NULL,
    slug                   TEXT NOT NULL DEFAULT '',
    cloud_updated_at       TEXT NOT NULL DEFAULT '',
    synced_from_cloud_at   TEXT NOT NULL
);

-- 2) mirror_departments:部门(战略发展部 / 合作发展部 / 技术创新部 ...)
CREATE TABLE IF NOT EXISTS mirror_departments (
    id                     TEXT PRIMARY KEY,
    organization_id        TEXT NOT NULL,
    name                   TEXT NOT NULL,
    color                  TEXT NOT NULL DEFAULT '',
    leader_user_id         TEXT,
    leader_name            TEXT NOT NULL DEFAULT '',
    parent_department_id   TEXT,
    active                 INTEGER NOT NULL DEFAULT 1,
    cloud_updated_at       TEXT NOT NULL DEFAULT '',
    synced_from_cloud_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mirror_departments_org
    ON mirror_departments(organization_id, active);

-- 3) mirror_users:员工(用户甲 / 乐乐 / 用户乙 / 系统管理员)
--    敏感字段不镜像(password_hash / phone_verified_at / approved_by ...)
CREATE TABLE IF NOT EXISTS mirror_users (
    id                     TEXT PRIMARY KEY,
    organization_id        TEXT NOT NULL,
    department_id          TEXT,
    full_name              TEXT NOT NULL,
    email                  TEXT NOT NULL DEFAULT '',
    primary_role           TEXT NOT NULL DEFAULT '',
    account_status         TEXT NOT NULL DEFAULT '',
    membership_status      TEXT NOT NULL DEFAULT '',
    is_department_lead     INTEGER NOT NULL DEFAULT 0,
    is_manager             INTEGER NOT NULL DEFAULT 0,
    manager_user_id        TEXT,
    task_edit_scope        TEXT NOT NULL DEFAULT 'self',
    can_approve_tasks      INTEGER NOT NULL DEFAULT 0,
    can_reassign_tasks     INTEGER NOT NULL DEFAULT 0,
    can_change_deadline    INTEGER NOT NULL DEFAULT 0,
    project_role_labels_json TEXT NOT NULL DEFAULT '[]',
    avatar_url             TEXT NOT NULL DEFAULT '',
    cloud_updated_at       TEXT NOT NULL DEFAULT '',
    synced_from_cloud_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mirror_users_org
    ON mirror_users(organization_id, account_status);
CREATE INDEX IF NOT EXISTS idx_mirror_users_dept
    ON mirror_users(department_id);

-- 4) mirror_client_related_users:项目 ↔ 同事 多对多(权限基础)
--    client_id 不加 FK 到 clients(避免 sync 顺序破坏 cascade)
CREATE TABLE IF NOT EXISTS mirror_client_related_users (
    client_id              TEXT NOT NULL,
    user_id                TEXT NOT NULL,
    order_index            INTEGER NOT NULL DEFAULT 0,
    cloud_updated_at       TEXT NOT NULL DEFAULT '',
    synced_from_cloud_at   TEXT NOT NULL,
    PRIMARY KEY (client_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_mirror_cru_user
    ON mirror_client_related_users(user_id);
CREATE INDEX IF NOT EXISTS idx_mirror_cru_client
    ON mirror_client_related_users(client_id);

-- ══════════════════════════════════════════════════════════════════════════════
-- Readonly 软约束:UPDATE 时 synced_from_cloud_at 没刷新 = 业务代码误写,拒绝
-- (sync 程序每次 UPSERT 都会刷 synced_from_cloud_at,所以不受影响)
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TRIGGER IF NOT EXISTS trg_mirror_organizations_readonly
BEFORE UPDATE ON mirror_organizations
FOR EACH ROW
WHEN NEW.synced_from_cloud_at = OLD.synced_from_cloud_at
BEGIN
  SELECT RAISE(ABORT, 'mirror_organizations is cloud-mirrored; only sync process may write');
END;

CREATE TRIGGER IF NOT EXISTS trg_mirror_departments_readonly
BEFORE UPDATE ON mirror_departments
FOR EACH ROW
WHEN NEW.synced_from_cloud_at = OLD.synced_from_cloud_at
BEGIN
  SELECT RAISE(ABORT, 'mirror_departments is cloud-mirrored; only sync process may write');
END;

CREATE TRIGGER IF NOT EXISTS trg_mirror_users_readonly
BEFORE UPDATE ON mirror_users
FOR EACH ROW
WHEN NEW.synced_from_cloud_at = OLD.synced_from_cloud_at
BEGIN
  SELECT RAISE(ABORT, 'mirror_users is cloud-mirrored; only sync process may write');
END;

CREATE TRIGGER IF NOT EXISTS trg_mirror_cru_readonly
BEFORE UPDATE ON mirror_client_related_users
FOR EACH ROW
WHEN NEW.synced_from_cloud_at = OLD.synced_from_cloud_at
BEGIN
  SELECT RAISE(ABORT, 'mirror_client_related_users is cloud-mirrored; only sync process may write');
END;
"""
