from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database  # noqa: E402
from app.task_pressure_seed import parse_pressure_seed_markdown, seed_task_pressure_doc  # noqa: E402


SAMPLE_MARKDOWN = """
```yaml
name:
department:
manager:
```

```yaml
name: 庆华
department: 咨询策略部
manager: 庆华
role_type: manager
week: 2026-03-09~2026-03-15
linked_quarter_goals: [Q1-G2, Q1-G4]
weekly_plan:
  - task_id: ZL-QH-01
    title: 输出客户策略备忘录
    customer_or_project: 蓝信封
    priority: P0
    due_date: 2026-03-12
    expected_output: 备忘录V1
    linked_goal: Q1-G2
weekly_review:
  overall_status: 1项完成
  key_results:
    - 已完成关键判断
  key_learnings:
    - 资料充分时判断更快
  support_needed:
    - 需要客户补更多背景
  tasks:
    - task_id: ZL-QH-01
      status: 完成
      result: 已输出备忘录V1
      reflection: 前置信息足够时推进明显更顺
      support_needed: 无
```

```yaml
name: 苏妍
department: 咨询策略部
manager: 庆华
role_type: member
week: 2026-03-09~2026-03-15
linked_quarter_goals: [Q1-G2]
weekly_plan:
  - task_id: ZL-SY-01
    title: 梳理用户画像差异
    customer_or_project: 蓝信封
    priority: P1
    due_date: 2026-03-11
    expected_output: 画像差异表
    linked_goal: Q1-G2
weekly_review:
  overall_status: 1项部分完成
  key_results:
    - 已形成初版对比
  key_learnings:
    - 平台差异很大
  support_needed:
    - 需要大周补更多评论样本
  tasks:
    - task_id: ZL-SY-01
      status: 部分完成
      result: 已完成初版对比，仍需补样本
      reflection: 数据不足时假设容易漂
      support_needed: 需要大周补更多评论样本
```
"""


def test_parse_pressure_seed_markdown_skips_template_block(tmp_path: Path):
    markdown_path = tmp_path / "seed.md"
    markdown_path.write_text(SAMPLE_MARKDOWN, encoding="utf-8")

    employees = parse_pressure_seed_markdown(markdown_path)

    assert len(employees) == 2
    assert employees[0].name == "庆华"
    assert employees[1].tasks[0].task_id == "ZL-SY-01"


def test_seed_task_pressure_doc_populates_tasks_reviews_and_collaboration(tmp_path: Path):
    markdown_path = tmp_path / "seed.md"
    markdown_path.write_text(SAMPLE_MARKDOWN, encoding="utf-8")
    db = Database(tmp_path / "cloud.db")
    db.execute(
        "INSERT INTO organizations(id, name, slug, created_at, updated_at) VALUES('org_test', '测试组织', 'test-org', '2026-03-01T00:00:00', '2026-03-01T00:00:00')"
    )

    summary = seed_task_pressure_doc(
        db,
        markdown_path=markdown_path,
        organization_id="org_test",
        replace_all=True,
        expected_employee_count=2,
    )

    assert summary["employeeCount"] == 2
    assert summary["taskCount"] == 2
    assert db.scalar("SELECT COUNT(1) AS count FROM tasks WHERE source_type = 'pressure_seed_doc_v2'") == 2
    assert db.scalar("SELECT COUNT(1) AS count FROM weekly_review_entries") == 2
    assert db.scalar("SELECT COUNT(1) AS count FROM weekly_review_task_entries") == 2
    assert db.scalar("SELECT COUNT(1) AS count FROM task_collaborators WHERE task_id = 'ZL-SY-01' AND user_id = 'user_qinghua'") == 1
