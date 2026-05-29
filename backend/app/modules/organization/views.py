"""6 个核心 SQL Views · v2.1 数据层守卫

设计原则:
1. View 是 CQRS 的 read model:统一定义"什么算 active client"、"什么算 pending task"
2. View 不带 user_id 参数(SQLite VIEW 不支持参数绑定),user filter 在 Repository 加 WHERE
3. View 名称稳定,字段集稳定;就算业务表 schema 改了,view 是抽象层
4. 临时聚合:这 6 个 view 涉及 client/event_line/task/knowledge 4 个模块,
   Week 2-3 模块化时拆到各业务模块的 views.sql

view 列表:
- v_active_clients         所有未冻结的 client
- v_user_visible_clients   active client × mirror_client_related_users(给 user filter 用)
- v_client_facts           client 的核心 fact bundle(JSON 聚合)
- v_active_event_lines     active 事件线(只挂在 active client 上)
- v_pending_tasks          所有待办任务(用 owner_id 在 Repository 加 user filter)
- v_searchable_knowledge   可搜索知识(挂在 active client 上)
"""


VIEWS_SQL = """
-- ══════════════════════════════════════════════════════════════════════════════
-- v2.1 6 个核心 SQL Views(CQRS read model)
-- ══════════════════════════════════════════════════════════════════════════════

-- 1) v_active_clients:lifecycle 守卫(frozen 不出现)
DROP VIEW IF EXISTS v_active_clients;
CREATE VIEW v_active_clients AS
  SELECT * FROM clients
  WHERE frozen_at IS NULL;

-- 2) v_user_visible_clients:active client × project member 关联
--    user filter 在 Repository 加:WHERE u.user_id = ? 或 WHERE u.user_id IS NULL OR u.user_id = ?
DROP VIEW IF EXISTS v_user_visible_clients;
CREATE VIEW v_user_visible_clients AS
  SELECT c.*, cru.user_id AS viewer_user_id, cru.order_index
  FROM v_active_clients c
  LEFT JOIN mirror_client_related_users cru ON cru.client_id = c.id;

-- 3) v_client_facts:client 的核心 fact bundle(单查询拿完所有统计)
DROP VIEW IF EXISTS v_client_facts;
CREATE VIEW v_client_facts AS
  SELECT
    c.id, c.name, c.alias, c.domain, c.type, c.stage,
    (SELECT COUNT(*) FROM event_lines el WHERE el.primary_client_id = c.id AND el.status = 'active') AS active_event_count,
    (SELECT COUNT(*) FROM commitments cm WHERE cm.client_id = c.id AND cm.status NOT IN ('fulfilled','cancelled')) AS open_commitments,
    (SELECT COUNT(*) FROM tasks t WHERE t.client_id = c.id AND t.status IN ('todo','doing')) AS pending_tasks_count,
    (SELECT COUNT(*) FROM glossary_attributes ga WHERE ga.client_id = c.id) AS glossary_attribute_count
  FROM v_active_clients c;

-- 4) v_active_event_lines:active 事件线只挂 active client
DROP VIEW IF EXISTS v_active_event_lines;
CREATE VIEW v_active_event_lines AS
  SELECT el.*
  FROM event_lines el
  WHERE el.status = 'active'
    AND (el.primary_client_id IS NULL
         OR el.primary_client_id IN (SELECT id FROM v_active_clients));

-- 5) v_pending_tasks:所有待办 + doing 中的任务
--    注意:SQLite VIEW 不能带 :viewer_user_id 参数
--    user filter 在 Repository 加:WHERE owner_id = ? 或 WHERE creator_id = ?
DROP VIEW IF EXISTS v_pending_tasks;
CREATE VIEW v_pending_tasks AS
  SELECT t.*
  FROM tasks t
  WHERE t.status IN ('todo','doing');

-- 6) v_searchable_knowledge:可搜索知识只挂 active client
DROP VIEW IF EXISTS v_searchable_knowledge;
CREATE VIEW v_searchable_knowledge AS
  SELECT k.*
  FROM knowledge_master_index k
  WHERE LENGTH(k.searchable_text) > 0
    AND k.client_id IN (SELECT id FROM v_active_clients);
"""


VIEW_NAMES = (
    "v_active_clients",
    "v_user_visible_clients",
    "v_client_facts",
    "v_active_event_lines",
    "v_pending_tasks",
    "v_searchable_knowledge",
)
