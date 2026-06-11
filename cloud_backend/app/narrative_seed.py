"""一次性 seed 工具: 给指定客户跑 v0.1 叙事生成 (用真 LLM 或 stub).

部署到 cloud 后:
    cd cloud_backend
    ARK_API_KEY=xxx python -m app.narrative_seed \\
        --db /var/lib/yiyu/cloud.db \\
        --organization-id org_yiyu_default \\
        --client-names 测试机构A,测试机构B,测试机构B

或者:
    python -m app.narrative_seed --db ... --client-ids client_riciqi,client_weiaiqianxing
    python -m app.narrative_seed --db ... --all   (全 org 所有 client)
    python -m app.narrative_seed --db ... --all --stub   (不调 LLM, 只跑 stub)

部署诊断: 跑完会打印每个 client 的 rev / generator / overallConfidence / 缺口数,
方便用户立刻判断"AI 真生成了 vs 降级了 vs 数据稀疏".
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db import Database
from app.services import client_narrative as svc
from app.services import narrative_generator as gen


def _resolve_client_ids(
    db: Database,
    organization_id: str,
    *,
    client_ids: list[str] | None,
    client_names: list[str] | None,
    all_clients: bool,
) -> list[tuple[str, str]]:
    if all_clients:
        rows = db.fetchall(
            "SELECT id, name FROM clients WHERE organization_id = ? ORDER BY updated_at DESC",
            (organization_id,),
        )
        return [(str(r["id"]), str(r["name"])) for r in rows]

    pairs: list[tuple[str, str]] = []
    if client_ids:
        for cid in client_ids:
            row = db.fetchone(
                "SELECT id, name FROM clients WHERE id = ? AND organization_id = ?",
                (cid, organization_id),
            )
            if row:
                pairs.append((str(row["id"]), str(row["name"])))
            else:
                print(f"⚠️  client_id 不存在: {cid}")
    if client_names:
        for name in client_names:
            row = db.fetchone(
                """
                SELECT id, name FROM clients
                WHERE organization_id = ? AND (name = ? OR alias = ?)
                ORDER BY updated_at DESC LIMIT 1
                """,
                (organization_id, name, name),
            )
            if row:
                pairs.append((str(row["id"]), str(row["name"])))
            else:
                print(f"⚠️  client_name 未匹配: {name}")
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for cid, n in pairs:
        if cid in seen:
            continue
        seen.add(cid)
        unique.append((cid, n))
    return unique


def seed_narratives(
    db_path: Path,
    organization_id: str,
    *,
    client_ids: list[str] | None = None,
    client_names: list[str] | None = None,
    all_clients: bool = False,
    actor_user_id: str | None = None,
    actor_display_name: str = "narrative_seed",
    use_llm: bool = True,
) -> list[dict[str, object]]:
    db = Database(db_path)
    targets = _resolve_client_ids(
        db,
        organization_id,
        client_ids=client_ids,
        client_names=client_names,
        all_clients=all_clients,
    )
    if not targets:
        print("没有找到任何 client, 退出")
        return []

    summary: list[dict[str, object]] = []
    for client_id, client_name in targets:
        try:
            new_rev = gen.regenerate_narrative(
                db,
                organization_id,
                client_id,
                triggered_by_user_id=actor_user_id,
                triggered_by_display_name=actor_display_name,
                trigger="seed",
                force=True,
                use_llm=use_llm,
            )
            latest = svc.get_latest_narrative(db, organization_id, client_id)
            row = {
                "clientId": client_id,
                "clientName": client_name,
                "rev": new_rev,
                "generator": latest.generator if latest else "?",
                "modelName": latest.modelName if latest else "?",
                "overallConfidence": latest.overallConfidence if latest else 0.0,
                "dataLayerGaps": latest.dataLayerGaps if latest else [],
                "dimsBelowMedium": (
                    [d.dimension for d in latest.dimensions if d.confidence == "low"]
                    if latest else []
                ),
            }
        except Exception as exc:  # noqa: BLE001 — seed 工具, 任何异常都得打印不能中断
            row = {
                "clientId": client_id,
                "clientName": client_name,
                "error": f"{type(exc).__name__}: {exc}",
            }
        summary.append(row)
        print(json.dumps(row, ensure_ascii=False))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="为指定客户生成 v0.1 6 维度叙事 (战略陪伴 / 事实澄清面板)")
    parser.add_argument("--db", required=True, help="cloud.db 路径")
    parser.add_argument("--organization-id", default="org_yiyu_default")
    parser.add_argument("--client-ids", help="逗号分隔的 client_id 列表")
    parser.add_argument("--client-names", help="逗号分隔的客户名 (匹配 name 或 alias)")
    parser.add_argument("--all", action="store_true", help="全 org 所有 client")
    parser.add_argument("--actor-user-id", default=None)
    parser.add_argument("--actor-name", default="narrative_seed")
    parser.add_argument("--stub", action="store_true", help="不调 LLM, 只用 stub (拼澄清原文)")
    args = parser.parse_args()

    ids = [s.strip() for s in (args.client_ids or "").split(",") if s.strip()]
    names = [s.strip() for s in (args.client_names or "").split(",") if s.strip()]

    seed_narratives(
        db_path=Path(args.db),
        organization_id=args.organization_id,
        client_ids=ids or None,
        client_names=names or None,
        all_clients=args.all,
        actor_user_id=args.actor_user_id,
        actor_display_name=args.actor_name,
        use_llm=not args.stub,
    )


if __name__ == "__main__":
    main()
