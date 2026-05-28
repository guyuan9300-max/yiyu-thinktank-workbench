#!/usr/bin/env python3
"""card→surrogate 富化: 用已建 document_cards 的豆包真摘要, 重写客户所有 surrogate + master_index 的检索字段。
- 确定性拼装(不调 LLM), 不碰 Qdrant, 不删数据。
- v2_instant / 模板 surrogate 统一升级为饱满 document surrogate(检索不过滤 source_type, 升级安全)。
- 每篇: 重写 surrogate(overview←summary_200, retrieval_summary←豆包摘要+要点, core_q←good_questions,
  query_hints←keywords+key_topics+tags, entities←entities) + 重写 .md + 更新 master_index.searchable_text。
- 最后统一 write_master_index_snapshot + sync_master_index_fts(让 FTS 查到新内容)。可重跑。
用法: e_enrich_surrogates_from_cards.py [client_id|ALL]   (默认日慈 client_284afd836e)
"""
import sys, os, pathlib, time, traceback
DD = pathlib.Path(os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))
from app.db import Database
from app.services import knowledge_base as KB
from app.services.knowledge_base import (
    upsert_surrogate_record, write_surrogate_markdown, upsert_master_index_record,
    build_catalog_search_text, build_master_index_summary, _guess_document_role,
    _query_hints, _core_questions, write_master_index_snapshot, sync_master_index_fts,
)

def jlist(raw):
    if not raw:
        return []
    try:
        v = KB.from_json(raw, [])
        return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []
    except Exception:
        return []

def enrich_client(db, client_id):
    rows = db.fetchall(
        """
        SELECT kd.id AS kdid, kd.doc_uid AS doc_uid, kd.primary_category AS pcat, kd.secondary_category AS scat,
               kd.current_human_path AS chp, kd.original_path AS op, kd.import_source_path AS isp,
               ks.id AS sid, ks.source_type AS st,
               mi.id AS miid,
               dc.title AS title, dc.one_line_summary AS one, dc.summary_200 AS summ,
               dc.keywords_json AS kj, dc.tags_json AS tj, dc.entities_json AS ej,
               dc.date_range_label AS drl, dc.good_questions_json AS gqj, dc.key_topics_json AS ktj, dc.purpose AS purpose
        FROM knowledge_documents kd
        JOIN document_cards dc ON dc.knowledge_document_id = kd.id
        JOIN knowledge_surrogates ks ON ks.knowledge_document_id = kd.id
        LEFT JOIN knowledge_master_index mi ON mi.surrogate_id = ks.id
        WHERE kd.client_id = ?
        """,
        (client_id,),
    )
    n = 0
    for r in rows:
        title = str(r["title"]); cat = str(r["pcat"] or "其他资料"); sec = str(r["scat"] or "")
        one = str(r["one"] or title)
        summ = str(r["summ"] or one)
        kws = jlist(r["kj"]); tags = jlist(r["tj"]); ents = jlist(r["ej"])
        gq = jlist(r["gqj"]); kt = jlist(r["ktj"])
        dr = str(r["drl"]) if r["drl"] else None
        role = (str(r["purpose"] or "").strip() or _guess_document_role(title, summ, cat))[:40]
        # 富化 retrieval_summary: 豆包摘要为主体 + 要点/关键词/对象/时间
        bits = [f"《{KB.clean_title_for_search(title)}》。"]
        if one and one != title:
            bits.append(one if one.endswith(("。", "！", "？", ".")) else one + "。")
        if kt:
            bits.append(f"重点:{'、'.join(kt[:5])}。")
        if kws:
            bits.append(f"关键词:{'、'.join(kws[:6])}。")
        if ents:
            bits.append(f"涉及:{'、'.join(ents[:5])}。")
        if dr:
            bits.append(f"时间:{dr}。")
        retr = "".join(bits)[:300]
        qh = list(dict.fromkeys(kws + kt + tags))[:12] or _query_hints(title, kws, ents, role)
        cq = gq[:6] or _core_questions(title, cat, role, kws)
        payload = {
            "overview_summary": summ,
            "retrieval_summary": retr,
            "document_role": role,
            "core_questions": cq,
            "query_hints": qh,
            "distinct_findings": kt[:6],
            "entities": ents[:8],
            "time_markers": [dr] if dr else [],
            "source_links": [],
            "source_outline": "",
        }
        src = str(r["chp"] or r["op"] or r["isp"] or "")
        md = write_surrogate_markdown(
            DD, client_id=client_id, doc_uid=str(r["doc_uid"]),
            folder_category=cat, title=title, source_type="document", source_path=src, payload=payload,
        )
        upsert_surrogate_record(
            db, surrogate_id=str(r["sid"]), knowledge_document_id=str(r["kdid"]),
            client_id=client_id, source_type="document", title=title, folder_category=cat,
            surrogate_md_path=md, payload=payload, timestamp=KB.now_iso(),
        )
        searchable = build_catalog_search_text(
            title=title, short_summary=one, summary=summ, raw_text="",
            keywords=kws, entities=ents, primary_category=cat, secondary_category=sec, document_role=role,
        )
        upsert_master_index_record(
            db, data_dir=DD, entry_id=str(r["miid"] or f"midx_{r['doc_uid']}"),
            client_id=client_id, surrogate_id=str(r["sid"]), title=title, folder_category=cat,
            document_role=role,
            retrieval_summary=build_master_index_summary(title=title, short_summary=one, summary=summ, raw_text=""),
            searchable_text=searchable, source_path=src or None, surrogate_md_path=md,
            timestamp=KB.now_iso(), sync_after=False,
        )
        n += 1
    write_master_index_snapshot(db, DD, client_id)
    sync_master_index_fts(db, client_id)
    return n

def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "client_284afd836e"
    db = Database(DD / "app.db")
    if arg == "ALL":
        cids = [str(r[0]) for r in db.fetchall("SELECT DISTINCT client_id FROM knowledge_documents WHERE client_id IS NOT NULL AND client_id<>''")]
    else:
        cids = [arg]
    print(f"富化客户: {cids}")
    for cid in cids:
        try:
            b = db.fetchall("SELECT COUNT(*) FROM knowledge_surrogates WHERE client_id=? AND source_type='document'", (cid,))[0][0]
            t0 = time.time(); n = enrich_client(db, cid); el = time.time() - t0
            a = db.fetchall("SELECT COUNT(*) FROM knowledge_surrogates WHERE client_id=? AND source_type='document'", (cid,))[0][0]
            print(f"  {cid}: 富化 {n} 篇 | document surrogate {b}→{a} | {round(el,1)}s")
        except Exception:
            print(f"  {cid} ‼\n" + traceback.format_exc()[-1500:])

if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("‼\n" + traceback.format_exc()[-2500:])
    print("done")
